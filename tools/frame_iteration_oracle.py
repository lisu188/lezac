"""Observe uninterrupted original actors, transient queues, and frame tail."""
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
import frame_actor_pass_oracle as actors
from actor_motion_oracle import compact_initial
from capture_original_debris_update import debris
from capture_original_collapse_update import collapse
from frame_camera_oracle import EXE_SHA,LIB_SHA,REGS,sha
from oracle_failure_report import write_failure

DATA=0x1aa20
SOURCES=tuple(dict.fromkeys((*actors.SOURCES,'frame_iteration_oracle.py',
    'capture_original_debris_update.py','capture_original_collapse_update.py','scan_livels_debris_sites.py')))
STOPS={0x17903:1,0x177dc:4,0x18298:5,0x182b9:6,0x18224:7,0x1825e:7,0x192e2:8,0x192e9:10}


def profiles():
    base=actors.profiles()
    rows=[dict(row,iteration_family='actor_'+row['family'],injected=False,duration=0,palette=0,key=0,
        complete=False,countdown=0) for row in base]
    sources=[next(row for row in base if row['family']==family and condition(row)) for family,condition in (
        ('behavior',lambda r:r['behavior']==4),('boss_links',lambda r:r['links']==3),
        ('expiry',lambda r:r['expiry']=='all'),('both_controls',lambda r:r['controls']==(31,31)))]
    for row,sparks,falling,fragments in itertools.product(sources,(False,True),(False,True),(0,1,2)):
        rows.append(dict(row,iteration_family='coupled_'+row['family'],injected=True,sparks=sparks,
            falling=falling,fragments=fragments,duration=3,palette=0,key=0,complete=False,countdown=0))
    inactive=next(row for row in base if row['family']=='passes' and row['count']==0 and row['states']==(0,0) and row['flags']==0x202)
    for duration,palette,key,complete in itertools.product((0,3,65535),(0,1,3),(0,0x1b,0x65,0x72,0x73),(False,True)):
        rows.append(dict(inactive,iteration_family='tail_routes',injected=True,sparks=False,falling=False,
            fragments=0,duration=duration,palette=palette,key=key,complete=complete,countdown=0))
    for duration,countdown,flags,fragment in itertools.product((0,3),(1,2),(0x202,0x602),(1,0x8000)):
        rows.append(dict(inactive,flags=flags,iteration_family='countdown_callback',injected=True,sparks=False,
            falling=False,fragments=0,duration=duration,palette=0,key=0,complete=True,
            countdown=countdown,fragment=fragment))
    for key,view,players,flags in itertools.product((0x65,0x72),(20,21,22,39,40,41),(0,1,2),(0x202,0x602)):
        rows.append(dict(inactive,flags=flags,iteration_family='view_boundaries',injected=True,sparks=False,
            falling=False,fragments=0,duration=0,palette=0,key=key,complete=False,countdown=0,view=view,players=players))
    return rows


def initial_case(index,row,image,sines):
    entry,initial,_=actors.initial_case(index,row,image,sines)
    def put(offset,raw):initial[DATA+offset:DATA+offset+len(raw)]=raw
    def word(offset,value):put(offset,struct.pack('<H',value&65535))
    def byte(offset,value):put(offset,bytes((value,)))
    word(0x207a,0x6620);word(0x207c,0x209e);word(0x207e,199);word(0x2080,0)
    word(0xc206,16);word(0x2098,0xa55a);word(0x209a,row['duration']);word(0x209c,0)
    byte(0x79cb,row['palette']);byte(0x2058,row['key']);byte(0x79b2,row['countdown'])
    byte(0x79c5,int(row['complete']));byte(0x79c6,int(row['complete']));byte(0x79b7,1);byte(0x79ad,20)
    for slot in range(1,4):
        byte(0x79cd+slot,slot+10)
        for component in range(1,4):
            byte(0x79ce+slot*3+component,20);byte(0x79d8+slot*3+component,20 if slot==3 else 24)
    if row['key'] in (0x65,0x72):byte(0x79b8,1);word(0xc1ea,21 if row['key']==0x65 else 40)
    if 'view' in row:word(0xc1ea,row['view']);byte(0x79b8,row['players'])
    if row['countdown']:word(0x78c4,row['fragment'])
    if row['injected']:
        word(0x2076,2 if row['sparks'] else 0)
        if row['sparks']:
            put(0x209e,debris(280,0,vx=127,sx=127,rest=2,glyph=0x75)+debris(281,0,vy=31,rest=2,glyph=0x75))
            put(0x78d6,bytes((1,2)));initial[0x40000+280:0x40000+282]=bytes((0x75,0x75))
        records=[]
        if row['fragments']==2:records.append(debris(0xffbc,0,rest=2,glyph=0x78))
        if row['fragments']:
            records.append(debris(344,0xc0aa,vx=-31,vy=31,sx=127,sy=127,rest=2))
            initial[0x40000+344]=0x60;struct.pack_into('<H',initial,0x60000+344*2,0xc0aa)
        word(0x207e,199+len(records));put(0x292b,b''.join(records))
        if row['falling']:
            word(0x2080,1);put(0x6620,collapse(536,537,vy=31,sy=127))
            for cell in (536,537):
                initial[0x40000+cell]=0x60;struct.pack_into('<H',initial,0x60000+cell*2,0x8001)
    patches=[]
    base=bytearray(1048576);base[0x10000:0x10000+len(image)]=image
    # Compact only the controlled initial differences; no handoff state is seeded.
    at=0
    while at<len(initial):
        if initial[at]==base[at]:at+=1;continue
        first=at
        while at<len(initial) and initial[at]!=base[at]:at+=1
        patches.append((first,bytes(initial[first:at])))
    rebuilt,seeds=compact_initial(image,patches)
    if rebuilt!=initial:raise ValueError('Iteration initial projection differs')
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
    out.mkdir();rows=profiles();output=bytearray(b'LZITER01'+struct.pack('<II',len(rows),len(exe))+exe)
    index,row,initial,engine=-1,None,None,None;trace,writes,results=[],[],[]
    visits=Counter();outcomes=Counter();families=Counter();phases=Counter();states=write_count=port_count=dense_cases=0
    try:
        sines,sine_proof=actors.boss.sine_table(image)
        for index,row in enumerate(rows):
            trace,writes,results=[],[],[];engine=None;initial=None
            entry,initial,seeds=initial_case(index,row,image,sines)
            phase_mask=case_states=0;stop=fault=None;ports=[];dense=index%64==0 or row['iteration_family'].startswith('coupled_')
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
                    if not (registers[7]==0x1000 and registers[12]<0x83f0 or
                        registers[7]==0x1920 and registers[12]<0x1820 or registers[7]==0x18ac and registers[12]<0x5da):
                        raise ValueError('Iteration left declared original code')
                    case_states+=1;visits[hex(address)]+=1
                    if address in (0x17ebb,0x1804e,0x1806a):phase_mask|={0x17ebb:1,0x1804e:2,0x1806a:4}[address]
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
                engine.emu_start(0x17ebb,0,count=3000000)
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
        manifest=dict(schema='lezac-controlled-actor-to-frame-end-v1',cases=len(rows),dense_cases=dense_cases,
            asset_sha256={'LEZAC.EXE':EXE_SHA},source_sha256=sources,unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True,full_memory_observer_control=True,ordered_writes_reconstruct_memory=True,
            original_instructions=states,ordered_writes=write_count,ordered_ports=port_count,outcomes=dict(outcomes),phase_masks=dict(phases),
            profile_families=dict(families),helper_visits={key:visits[key] for key in ('0x17ebb','0x16053','0x1804e','0x145fa','0x15102','0x1806a','0x145ce','0x150be')},
            boss_sine_initializer=sine_proof,projection_bytes=len(output),projection_sha256=sha(output),compressed_bytes=len(packed),compressed_sha256=sha(packed),
            instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_inputs=0,host_hardware_io=False,
            controlled_initial_memory=True,later_state_injected=False,natural_capture=False,raw_memory_published=False,
            rendering_prefix_executed=False,work_clock_claim=False,actual_app_integration=False,full_frame_claim=False,
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
