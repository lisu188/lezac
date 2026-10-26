"""Observe uninterrupted original post-render prefix through frame endpoints."""
import argparse
from collections import Counter
import gzip
import itertools
import json
import os
from pathlib import Path
import resource
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN,UC_X86_INS_OUT
import frame_iteration_oracle as body
import frame_spawner_oracle as spawners
from actor_motion_oracle import compact_initial
from frame_camera_oracle import EXE_SHA,LIB_SHA,REGS,sha
from oracle_failure_report import write_failure

DATA=0x1aa20
SOURCES=tuple(dict.fromkeys((*body.SOURCES,'frame_spawner_oracle.py','frame_post_render_oracle.py')))
STOPS={0x11b14:2,0x17903:1,0x177dc:4,0x18298:5,0x182b9:6,0x18224:7,0x1825e:7,0x192e2:8,0x192e9:10}


def profiles():
    rows=[dict(row,prefix_gate=1,spawner_profile=None,
        iteration_family='post_render_'+row['iteration_family']) for row in body.profiles()]
    base=next(row for row in body.profiles() if row['family']=='passes' and row['count']==0 and
        row['states']==(1,1) and row['flags']==0x202)
    for states,gate,flags in itertools.product(itertools.product((0,1,2,255),repeat=2),(0,1),(0x202,0x602)):
        rows.append(dict(base,states=states,flags=flags,prefix_gate=gate,spawner_profile=None,
            iteration_family='prefix_waiting',injected=False,duration=0,palette=0,key=0,complete=False,countdown=0))
    for count,gate,flags in itertools.product((0,1,2),range(9),(0x202,0x602)):
        profile=(count,29 if gate==6 else 30 if gate==7 else 0,32 if gate==8 else 2,gate,0x200,0x12345678)
        rows.append(dict(base,count=profile[1],flags=flags,prefix_gate=1,spawner_profile=profile,
            iteration_family='prefix_spawner',injected=False,duration=0,palette=0,key=0,complete=False,countdown=0))
    for players in (1,2):
        for dead,timer,reserves,fire,gate,flags in itertools.product(range(1,1<<players),(1,2),(0,1),(0,1),(0,1),(0x202,0x602)):
            states=tuple(0 if p>=players else 2 if dead&(1<<p) else 1 for p in range(2))
            rows.append(dict(base,states=states,hp=tuple(0 if dead&(1<<p) else 100 for p in range(2)),
                flags=flags,players=players,prefix_gate=gate,spawner_profile=None,
                lifecycle=dict(dead=dead,timer=timer,reserves=reserves,fire=fire),
                iteration_family='prefix_lifecycle',injected=False,duration=0,palette=0,key=0,complete=False,countdown=0))
    return rows

def initial_case(index,row,image,sines):
    entry,initial,_=body.initial_case(index,row,image,sines)
    entry=list(entry);entry[12]=0x7a57;entry=tuple(entry)
    initial[DATA+0x79ca]=row['prefix_gate']
    initial[DATA+0x79a6]=0
    initial[DATA+0x79b8]=row.get('players',2)
    if row['spawner_profile'] is not None:
        for address,raw in spawners.inputs(index,row['spawner_profile']):
            if DATA+0x74a8<=address<DATA+0x74a8+90 or address==DATA+0x79a6:
                initial[address:address+len(raw)]=raw
    if 'lifecycle' in row:
        life=row['lifecycle']
        for player in range(2):
            initial[DATA+0x79ea+player]=life['reserves']
            initial[DATA+0x1b7b+player*5]=life['fire']
            if life['dead']&(1<<player):
                actor=DATA+0x1b88+player*38
                initial[actor+21]=2;struct.pack_into('<H',initial,actor+16,life['timer'])
    patches=[];base=bytearray(1048576);base[0x10000:0x10000+len(image)]=image
    at=0
    while at<len(initial):
        if initial[at]==base[at]:at+=1;continue
        first=at
        while at<len(initial) and initial[at]!=base[at]:at+=1
        patches.append((first,bytes(initial[first:at])))
    rebuilt,seeds=compact_initial(image,patches)
    if rebuilt!=initial:raise ValueError('Post-render initial projection differs')
    return entry,initial,seeds

def generate(root,out):
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported iteration oracle loader')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual iteration library mapping differs')
    exe=(root/'LEZAC.EXE').read_bytes()
    if sha(exe)!=EXE_SHA:raise ValueError('Canonical iteration executable differs')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in SOURCES}
    mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+4*i);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    capacity=os.statvfs('/dev/shm')
    if capacity.f_bavail*capacity.f_frsize-64*1048576<capacity.f_blocks*capacity.f_frsize/10:
        raise ValueError('Iteration RAM reserve is insufficient')
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():raise ValueError('Use fresh RAM-only iteration output')
    out.mkdir();rows=profiles();output=bytearray(b'LZPOST01'+struct.pack('<II',len(rows),len(exe))+exe)
    index,row,initial,engine=-1,None,None,None;trace,writes,results=[],[],[]
    visits=Counter();outcomes=Counter();families=Counter();phases=Counter();states=write_count=port_count=dense_cases=0
    try:
        sines,sine_proof=body.actors.boss.sine_table(image)
        for index,row in enumerate(rows):
            trace,writes,results=[],[],[];engine=None;initial=None
            entry,initial,seeds=initial_case(index,row,image,sines)
            phase_mask=case_states=0;stop=fault=None;ports=[];dense=index%64==0 or 'coupled_' in row['iteration_family']
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16);engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,entry):engine.reg_write(register,value)
                ports=[];fault=None
                def boundary(uc,address,size,user):
                    nonlocal stop
                    if address in STOPS:stop=address;uc.emu_stop()
                def code(uc,address,size,user):
                    nonlocal case_states,phase_mask
                    if address in STOPS:boundary(uc,address,size,user);return
                    registers=tuple(uc.reg_read(register) for register in REGS)
                    if not 0x10000<=address<0x10000+len(image):
                        raise ValueError('Iteration left declared original code')
                    case_states+=1;visits[hex(address)]+=1
                    if address in (0x17a57,0x17ebb,0x1804e,0x1806a):phase_mask|={0x17a57:8,0x17ebb:1,0x1804e:2,0x1806a:4}[address]
                    if dense and len(trace)<10000:trace.append(registers)
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (DATA<=address and address+size<=0xb0001):
                        raise ValueError('Iteration write left declared memory')
                    writes.append((address,size,value&((1<<(size*8))-1)))
                def intr(uc,number,user):
                    nonlocal fault
                    if number!=0:raise ValueError('Unexpected iteration CPU interrupt')
                    fault=uc.reg_read(REGS[7])*16+uc.reg_read(REGS[12]);uc.emu_stop()
                def port_out(uc,port,size,value,user):
                    if port not in (0x3c8,0x3c9) or size!=1:raise ValueError('Unexpected original iteration output')
                    ports.append((port,size,value))
                def forbidden(*unused):raise ValueError('Unexpected original iteration input')
                engine.hook_add(unicorn.UC_HOOK_INTR,intr)
                engine.hook_add(unicorn.UC_HOOK_INSN,forbidden,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,port_out,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code);engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                else:
                    for address in STOPS:engine.hook_add(unicorn.UC_HOOK_CODE,boundary,None,address,address)
                engine.emu_start(entry[7]*16+entry[12],0,count=3000000)
                registers=tuple(engine.reg_read(register) for register in REGS);final=bytes(engine.mem_read(0,1048576))
                if (fault is None and registers[7]*16+registers[12] not in STOPS) or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Iteration endpoint/code preservation differs')
                results.append((registers,final,fault,ports[:]))
            if results[0]!=results[1]:raise ValueError('Iteration observer changed complete memory/registers/ports')
            registers,final,fault,ports=results[0];rebuilt=bytearray(initial)
            for address,size,value in writes:rebuilt[address:address+size]=value.to_bytes(size,'little')
            if rebuilt!=final:raise ValueError('Iteration writes do not reconstruct complete memory')
            outcome=9 if fault is not None else STOPS[registers[7]*16+registers[12]]
            if not dense or case_states>10000:trace=[entry]
            else:dense_cases+=1
            trace.append(registers)
            output.extend(struct.pack('<III13HI13HI',index,outcome,phase_mask,*entry,*registers));output.extend(struct.pack('<I',len(seeds)))
            for address,raw in seeds:output.extend(struct.pack('<II',address,len(raw))+raw)
            output.extend(struct.pack('<I',len(trace)))
            for column in range(14):output.extend(struct.pack('<'+('I' if column==13 else 'H')*len(trace),*(r[column] for r in trace)))
            output.extend(struct.pack('<I',len(writes)))
            for event in writes:output.extend(struct.pack('<IBH',*event))
            output.extend(struct.pack('<I',len(ports)))
            for event in ports:output.extend(struct.pack('<HBB',*event))
            if len(output)>48*1024**2:raise ValueError('Iteration compact projection exceeds reserve')
            states+=case_states;write_count+=len(writes);port_count+=len(ports);outcomes[str(outcome)]+=1;phases[str(phase_mask)]+=1;families[row['iteration_family']]+=1
            if index%64==0:print(json.dumps(dict(status='running',case=index,cases=len(rows),bytes=len(output))),flush=True)
        if sha((root/'LEZAC.EXE').read_bytes())!=EXE_SHA or any(sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()):
            raise ValueError('Iteration producer inputs changed')
        packed=gzip.compress(output,compresslevel=9,mtime=0);(out/'oracle.bin.gz').write_bytes(packed)
        manifest=dict(schema='lezac-controlled-post-render-to-frame-end-v1',cases=len(rows),dense_cases=dense_cases,
            asset_sha256={'LEZAC.EXE':EXE_SHA},source_sha256=sources,unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True,full_memory_observer_control=True,ordered_writes_reconstruct_memory=True,
            original_instructions=states,ordered_writes=write_count,ordered_ports=port_count,outcomes=dict(outcomes),phase_masks=dict(phases),
            profile_families=dict(families),helper_visits={key:visits[key] for key in ('0x17a57','0x17c3d','0x17ebb','0x12f9f','0x106ab','0x1326e','0x107c5','0x1056b','0x129db','0x17c96','0x17cc3','0x17d08','0x17d20','0x16053','0x1804e','0x145fa','0x15102','0x1806a','0x145ce','0x150be')},
            boss_sine_initializer=sine_proof,projection_bytes=len(output),projection_sha256=sha(output),compressed_bytes=len(packed),compressed_sha256=sha(packed),
            instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_inputs=0,host_hardware_io=False,
            controlled_initial_memory=True,later_state_injected=False,natural_capture=False,raw_memory_published=False,
            rendering_prefix_executed=False,post_render_prefix_executed=True,work_clock_claim=False,actual_app_integration=False,full_frame_claim=False,
            actor_pass_stability_hold_cleared=False)
        (out/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        print(json.dumps({key:manifest[key] for key in ('cases','dense_cases','original_instructions','ordered_writes','ordered_ports','outcomes','phase_masks','projection_bytes','compressed_bytes')},sort_keys=True),flush=True)
    except Exception as error:
        write_failure(out,error,case=index,profile=row,sources=sources,initial=initial,
            endpoints=[(r,m,f) for r,m,f,_ in results],current=engine,trace=trace,writes=writes,projection=output)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
