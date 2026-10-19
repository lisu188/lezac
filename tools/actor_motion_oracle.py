"""Execute original actor movement/terrain and continuous actor returns."""
import argparse
from collections import Counter
import gc
import gzip
import itertools
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

from actor_contact_oracle import contact_case, contact_profiles
from actor_steering_oracle import encode_trace
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA=0x1aa20
SOURCES=('actor_motion_oracle.py','actor_steering_oracle.py','actor_contact_oracle.py',
    'actor_precontact_oracle.py','frame_actor_entry_oracle.py','boss_links_oracle.py',
    'frame_camera_oracle.py','frame_spawner_oracle.py','frame_waiting_oracle.py','ammo_hud_oracle.py')
FAULTS={0x170dc,0x170b4,0x171e7,0x173d2}


def profiles():
    rows=[]
    def add(family,**changes):
        row=dict(family=family,mode=0,behavior=4,kind=13,vx=0,vy=0,edges=0,flag_byte=1,
            ai0=24,speed=494,threshold=1000,tick=48,dx=40,dy=20,left_set=6,right_set=7,
            tiles=(1,1,1,1),sample_tiles=(0,0),current=(0,0),above=(0,0),
            width=64,cell=650,fracture=0x4001,shape='point',queue=0,rectangles=0,
            floor=0x200,bp=0x3fdc,flags=0x202,seed=0x12345678,accumulator=0,
            sound_active=0,sound_priority=0,x=80,y=80)
        row.update(changes);rows.append(row)
    # Full signed-word domain for the actual original friction routine.
    for value in range(65536):
        add('friction_word',mode=3,vx=value)
    for value in range(256):
        add('behavior_byte',behavior=value)
        for behavior,edge in itertools.product((2,3),range(4)):
            add('edge_flag_bytes',behavior=behavior,vx=-214,vy=214,edges=1<<edge,flag_byte=value)
        for field in range(4):
            tiles=[1,1,1,1];tiles[field]=value
            add('tile_cache_bytes',behavior=3 if field in (0,3) else 4,edges=2,vx=213,vy=214,tiles=tuple(tiles))
        add('facing_left_byte',behavior=3,vx=-213,edges=2,left_set=value)
        add('facing_right_byte',behavior=3,vx=213,edges=2,right_set=value)
        add('wandering_speed_byte',threshold=0,speed=value)
    velocities=(-32768,-2048,-43,-42,-1,0,1,42,43,2047,32767)
    for vx,vy,behavior,edges in itertools.product(velocities,velocities,(2,3,4),(0,2,6,15)):
        add('velocity_edges',vx=vx,vy=vy,behavior=behavior,edges=edges)
    for period,tick,speed in itertools.product((0,1,2,24,32768,65535),(0,1,23,24,25,65535),(0,1,494,32768,65535)):
        add('period_speed_words',ai0=period,tick=tick,speed=speed)
    for (dx,dy),threshold,speed in itertools.product(((-32768,-32768),(-32768,0),(-32768,1),
            (-32768,32767),(-32767,-1),(-257,0),(0,0),(40,20),(32767,32767)),
            (0,1,60,61,32767,32768,65535),(0,494,65535)):
        add('wrapped_target_distance',dx=dx,dy=dy,threshold=threshold,speed=speed)
    for tile,current,above in itertools.product(range(256),(0,1,32767,32768,65535),(0,1,32767,32768,65535)):
        add('sample_byte_words',mode=2,sample_tiles=(tile,0),current=(current,0),above=(above,0),accumulator=65535)
    for tile,above,word,queue,rectangles in itertools.product((0,103,114,115,255),
            (0,1,0x3fff,0x4000,0x7fff,0x8000),(0,32768),(0,1599,1600),(0,249,250)):
        add('kind4_terrain',kind=4,behavior=2,sample_tiles=(tile,114),above=(above,word),
            current=(word,word),fracture=above,queue=queue,rectangles=rectangles)
    for value,shape,queue,rectangles in itertools.product((0,1,2,0x3fff,0x4000,0x7fff,0x8000,0xffff),
            ('point','horizontal','vertical','rectangle','hole'),(0,1599,1600),(0,249,250)):
        add('fracture_geometry_caps',mode=1,fracture=value,shape=shape,queue=queue,rectangles=rectangles)
    for bp,floor,mode,flags in itertools.product((0x3fdc,0x700),(0x200,0x3d72,0x3d73,0xffff),range(4),(0x202,0x602)):
        add('stack_direction',bp=bp,floor=floor,mode=mode)
        rows[-1]['flags']=flags
    add('branch_boundaries',behavior=3,vx=-214,ai0=214,edges=2,tiles=(0,1,1,1))
    add('branch_boundaries',behavior=1,vx=214,edges=8)
    for mode,kind,behavior,edges,velocity in itertools.product((4,5),(1,4,13),(2,3,4),(0,2),((-214,256),(0,0),(214,-1))):
        add('continuous_actor' if mode==4 else 'real_caller',mode=mode,kind=kind,behavior=behavior,
            edges=edges,vx=velocity[0],vy=velocity[1],sample_tiles=(103,114) if kind==4 else (0,0),above=(0x4001,0))
    return rows


def make_case(index,row):
    mode=row['mode'];bp=row['bp'];patches=[]
    def put(address,raw): patches.append((address,bytes(raw)))
    def word(address,value): put(address,struct.pack('<H',value&65535))
    def dw(offset,value): word(DATA+offset,value)
    def sb(offset,value): put(0x70000+((bp+offset)&65535),bytes((value&255,)))
    def sw(offset,value): word(0x70000+((bp+offset)&65535),value)
    if mode==3:
        sp=(bp-80)&65535
        dw(0x1afa,row['floor']);word(0x70000+sp,0x7f00);word(0x70000+((sp+2)&65535),bp);sw(-12,row['vx'])
        values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,bp,0x1000,0x1aa2,0x40,0x7000,sp,0x5b86,row['flags'])
        return values,patches
    if mode>=4:
        parent=dict(contact_profiles()[0],kind=row['kind'],behavior=row['behavior'],hotspot=0,
            x=row['x'],y=row['y'],dx=row['dx'],dy=row['dy'],dx2=1000,dy2=1000,
            states=(1,0),width=1,height=1,bombs=0,triggers=0,cells=0,group=0,flames=0,
            edges=row['edges'],edge_tile=1,velocity=(row['vx'],row['vy']),life=200,hp=255,
            tick=row['tick'],floor=row['floor'],bp=bp,seed=row['seed'])
        values,patches=contact_case(index,parent)
        put(0x70000+values[11],struct.pack('<H',0x7ee4))
    else:
        values=(0xa500|row['behavior'],0x1234,0x5678,0xabcd,0x1357,0x2468,bp,
            0x1000,0x1aa2,0x40,0x7000,(bp-58)&65535,0x7018,row['flags'])
        for offset,value in ((0,0x3ffe),(2,0x7ee4),(4,0x1bd4),(6,0x5000),
                (-4,row['dx']),(-6,row['dy']),(-12,row['vx']),(-14,row['vy']),(-48,row['x']),
                (-46,row['y']),(-44,row['x']),(-42,row['cell'])):
            sw(offset,value)
        for offset,value in ((-15,row['kind']),(-49,row['behavior']),(-19,2),(-32,0),(-18,0)):
            sb(offset,value)
        for edge,offset in ((1,-34),(2,-33),(4,-35),(8,-36)):
            sb(offset,row['flag_byte'] if row['edges']&edge else 0)
    actor=bytearray((index*13+i*7)&255 for i in range(38))
    actor[0:5]=bytes((row['kind'],2,200,row['left_set'],row['right_set']))
    struct.pack_into('<2H',actor,6,row['vx']&65535,row['vy']&65535)
    actor[10:14]=bytes(4);struct.pack_into('<3H',actor,14,row['ai0'],row['speed'],row['threshold'])
    actor[20]=0;actor[21]=row['behavior'];actor[22:29]=bytes((6,6,7,1,1,0,1));actor[36]=255
    put(0x50000+0x1bd4,actor)
    if mode==5:
        put(DATA+0x1bd4,actor);dw(0x2082,1);put(DATA+0x208d,b'\x04');values=(*values[:11],0x3fe4,0x7ebb,values[13])
        put(DATA+0x79f9,b'\x00')
    for offset,value in ((0x1afa,row['floor']),(0x78c2,row['tick']),(0xc204,row['width']),
            (0xc1fe,0x4000),(0xc1e0,0),(0xc1e2,0x4000),(0x206e,0x6000),(0x2066,row['width']*2),
            (0x6612,0),(0x6614,0x6000),(0xc1e8,row['cell']),(0x2074,row['accumulator']),
            (0x207e,row['queue']),(0x2080,row['rectangles']),(0x78c0,0x2222),(0xc1fc,0xc21e)):
        dw(offset,value)
    put(DATA+0x1afe,struct.pack('<I',row['seed']))
    put(DATA+0x79c4,bytes((row['sound_active'],)));put(DATA+0x799e,bytes((row['sound_priority'],)))
    put(DATA+0xc322,bytes((1,1,0,0))*256)
    put(DATA+0x58,bytes((i*29+index*7+3)&255 for i in range(512)))
    costs=(0,1,2,255,256,32767,32768,65535,43,42,494,214)
    amounts=(1,2,3,32767,32768,65535,0,214,494,42,43,255)
    put(DATA+2,struct.pack('<12H',*costs));put(DATA+0x1a,struct.pack('<12H',*amounts))
    if mode<4:
        put(DATA+0x2054,bytes(row['tiles']))
    def plane(cell,value): word(0x60000+((cell*2)&65535),value)
    def region(cell,value):
        for y in range(-2,3):
            for x in range(-2,3):
                plane(cell+y*row['width']+x,0x7ffe)
        shapes={'point':((0,0),),'horizontal':tuple((x,0) for x in range(-1,2)),
            'vertical':tuple((0,y) for y in range(-1,2)),
            'rectangle':tuple(itertools.product(range(-1,2),repeat=2)),
            'hole':tuple((x,y) for x,y in itertools.product(range(-1,2),repeat=2) if (x,y)!=(-1,-1))}
        for x,y in shapes[row['shape']]: plane(cell+y*row['width']+x,value)
    if mode==1:
        region(row['cell'],row['fracture']);sp=(bp-80)&65535
        put(0x70000+sp,struct.pack('<6H',0x7f00,0x100,0x5000,255,128,row['cell']))
        put(0x50100,b'\x5a');put(0x40000+row['cell'],b'\x6b')
        values=(*values[:11],sp,0x370e,values[13])
    elif mode==2:
        sp=(bp-80)&65535;put(0x70000+sp,struct.pack('<2H',0x7f00,bp))
        put(0x40000+row['cell'],bytes((row['sample_tiles'][0],)))
        plane(row['cell'],row['current'][0]);plane(row['cell']-row['width'],row['above'][0])
        values=(*values[:11],sp,0x5afd,values[13])
    elif row['kind']==4:
        for number,cell in enumerate((row['cell']+row['width'],row['cell']+2*row['width']+1)):
            region(cell-row['width'],row['above'][number])
            plane(cell,row['current'][number]);put(0x40000+cell,bytes((row['sample_tiles'][number],)))
    return values,patches


def compact_initial(image,patches):
    initial=bytearray(1048576);initial[0x10000:0x10000+len(image)]=image;seeds=[]
    for address,raw in patches:
        if not 0<=address<=address+len(raw)<=1048576 or address<DATA:
            raise ValueError('Motion seed exceeds declared data/stack')
        before=initial[address:address+len(raw)]
        if len(raw)>1024:
            start=None
            for i,(old,new) in enumerate(zip(before,raw)):
                if old!=new and start is None: start=i
                if old==new and start is not None: seeds.append((address+start,raw[start:i]));start=None
            if start is not None: seeds.append((address+start,raw[start:]))
        elif before!=raw:
            seeds.append((address,raw))
        initial[address:address+len(raw)]=raw
    reconstructed=bytearray(1048576);reconstructed[0x10000:0x10000+len(image)]=image
    for address,raw in seeds: reconstructed[address:address+len(raw)]=raw
    if reconstructed!=initial: raise ValueError('Compacted initial memory differs')
    return initial,seeds


def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported actor-motion oracle runtime')
    library=Path(uclib._name).resolve(strict=True)
    def mapped():
        return sha(library.read_bytes())==LIB_SHA and any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines())
    if not mapped(): raise ValueError('Actual motion library mapping differs')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in SOURCES};exe=(root/'LEZAC.EXE').read_bytes()
    if sha(exe)!=EXE_SHA: raise ValueError('Canonical motion executable differs')
    mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists(): raise ValueError('Use a new RAM-only motion output')
    out.mkdir();index=-1;trace=[];initial=None;last_final=None
    try:
        rows=profiles();output=bytearray(b'LZMOTION'+struct.pack('<I',len(rows)))
        coverage=set();states=write_count=max_states=0;outcomes=[0]*5;domains=[0]*6
        for index,row in enumerate(rows):
            values,patches=make_case(index,row);initial,seeds=compact_initial(image,patches)
            target=0x17f00 if row['mode'] in (1,2,3) else 0x17ee4 if row['mode']>=4 else 0x173e5
            stops={target:1 if row['mode'] in (1,2,3) else 4 if row['mode']>=4 else 0,0x192e2:2}
            trace,writes,endpoints=[],[],[];stop=None;fault=None
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16);engine.mem_map(0,1048576)
                engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values): engine.reg_write(register,value)
                def intr(uc,number,user):
                    nonlocal stop,fault
                    address=uc.reg_read(REGS[7])*16+uc.reg_read(REGS[12])
                    if number!=0 or address not in FAULTS: raise ValueError('Unexpected motion CPU interrupt: '+str((number,address)))
                    fault=address;stop=address;uc.emu_stop()
                def io(*unused): raise ValueError('Motion attempted hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop
                    if address in stops: stop=address;uc.emu_stop();return
                    registers=tuple(uc.reg_read(register) for register in REGS)
                    if not (registers[7]==0x1000 and registers[12]<0x83f0 or
                            registers[7]==0x1920 and registers[12]<0x1820 or
                            registers[7]==0x18ac and 0x517<=registers[12]<0x5dc):
                        raise ValueError('Motion left declared code: '+str((registers[7],registers[12],address,size)))
                    trace.append(registers);coverage.add((registers[7],registers[12]))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (DATA<=address and address+size<=DATA+65536 or
                            0x40000<=address and address+size<=0x80001 or
                            row['mode']>=4 and 0xa0000<=address and address+size<=0xb0001):
                        raise ValueError('Motion write left declared owners: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                engine.hook_add(unicorn.UC_HOOK_INTR,intr)
                engine.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code);engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                expected_fault=fault
                engine.emu_start(values[7]*16+values[12],0 if observed or expected_fault is not None else stop,count=3000000)
                registers=tuple(engine.reg_read(register) for register in REGS);final=bytes(engine.mem_read(0,1048576));last_final=final
                if (stop not in stops and fault not in FAULTS) or registers[7]*16+registers[12]!=stop or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Motion endpoint/unchanged code differs: '+str((registers[7],registers[12])))
                endpoints.append((registers,final,fault));del engine
            if endpoints[0]!=endpoints[1]: raise ValueError('Motion observer changed complete memory/registers')
            registers,final,fault=endpoints[0];reconstructed=bytearray(initial)
            for address,size,value in writes: reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final: raise ValueError('Motion writes do not reconstruct full memory')
            trace.append(registers);outcome=3 if fault is not None else stops[stop]
            outcomes[outcome]+=1;domains[row['mode']]+=1
            output.extend(struct.pack('<III13HI13HI',index,outcome,row['mode'],*values,*registers))
            output.extend(struct.pack('<I',len(seeds)))
            for address,raw in seeds: output.extend(struct.pack('<II',address,len(raw))+raw)
            encode_trace(output,trace);output.extend(struct.pack('<I',len(writes)))
            for entry in writes: output.extend(struct.pack('<IBH',*entry))
            states+=len(trace);write_count+=len(writes);max_states=max(max_states,len(trace))
            if len(output)>192*1024*1024: raise ValueError('Motion projection exceeds RAM reserve')
            if index%2048==0:
                gc.collect();print(json.dumps(dict(status='running',case=index,cases=len(rows),states=states,bytes=len(output))),flush=True)
        if not mapped() or sha((root/'LEZAC.EXE').read_bytes())!=EXE_SHA or any(
                sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()):
            raise ValueError('Motion producer inputs changed during generation')
        raw=bytes(output);packed=gzip.compress(raw,mtime=0);(out/'oracle.bin.gz').write_bytes(packed)
        manifest=dict(schema='lezac-controlled-actor-motion-v1',cases=len(rows),domains=domains,outcomes=outcomes,
            profile_families=dict(Counter(r['family'] for r in rows)),asset_sha256={'LEZAC.EXE':EXE_SHA},source_sha256=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            original_code_bytes_verified=43552,register_states=states,maximum_case_states=max_states,ordered_writes=write_count,
            executed_instructions=[list(r) for r in sorted(coverage)],projection_bytes=len(raw),projection_sha256=sha(raw),
            compressed_bytes=len(packed),compressed_sha256=sha(packed),trace_storage='register-delta-v1',
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,initial_compaction_equivalence_verified=True,
            later_state_injected=False,instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_io=0,
            cpu_divide_faults_observed=outcomes[3],divide_fault_handler_executed=False,controlled_initial_memory=True,
            natural_capture=False,continuous_actor_cases=domains[4],real_caller_cases=domains[5],
            actor_near_return_executed=True,production_app_comparison=False,trace_arithmetic_flags_compared=False,
            endpoint_all_flags_compared=True,raw_memory_published=False,full_frame_claim=False,whole_game_parity=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(rows),states=states,writes=write_count,outcomes=outcomes,
            domains=domains,bytes=len(raw),compressed=len(packed),sha256=sha(raw))),flush=True)
    except BaseException as error:
        (out/'producer-at-failure.py').write_bytes(Path(__file__).read_bytes())
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,row=rows[index] if index>=0 else None,
            error=repr(error),sources=sources,last_register_states=trace[-32:]))+'\n')
        if initial is not None: (out/'failed-initial.bin').write_bytes(initial)
        if last_final is not None: (out/'failed-last-final.bin').write_bytes(last_final)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();generate(args.repo.resolve(),args.out)
