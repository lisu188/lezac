"""Observe consecutive original nonplayer calls on one unchanged live stack."""
import argparse
from collections import Counter
import gzip
import itertools
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

from actor_motion_oracle import make_case,compact_initial,SOURCES,FAULTS
from actor_steering_oracle import encode_trace
from frame_camera_oracle import EXE_SHA,LIB_SHA,REGS,sha

DATA=0x1aa20
STOPS={0x17eea:0,0x16737:1,0x192e2:2}


def require(value,message):
    if not value:
        raise ValueError(message)


def profiles():
    rows=[]
    def add(**changes):
        row=dict(count=2,states=(1,1),behavior=-1,expiry='none',dx=40,dy=20,
            dx2=-30,dy2=-30,sp=0x3fe4,flags=0x202,floor=0x200,period=24)
        row.update(changes)
        rows.append(row)
    for count,states in itertools.product((0,1,2,3,5,30),itertools.product((0,1,2),repeat=2)):
        add(count=count,states=states)
    for behavior in range(7):
        add(behavior=behavior)
    for count,expiry in itertools.product((2,3,5),('first','last','all')):
        add(count=count,expiry=expiry)
    for dx,dy in ((-32768,-32768),(-32768,0),(-32768,1),(-32768,32767),
            (-32767,-1),(-257,0),(0,0),(32767,32767)):
        add(dx=dx,dy=dy,dx2=10,dy2=10)
        add(dx=10,dy=10,dx2=dx,dy2=dy)
    for sp,flags in itertools.product((0x1fe4,0x3fe4),(0x202,0x602)):
        add(sp=sp,flags=flags,states=(0,1))
    add(floor=65535)
    add(behavior=4,period=0)
    return rows


def initial_case(index,profile,image):
    row=dict(mode=5,bp=0x3fdc,floor=profile['floor'],flags=profile['flags'],kind=1,
        behavior=3,x=80,y=80,dx=profile['dx'],dy=profile['dy'],edges=0,tick=49,
        seed=0x12345678,ai0=24,speed=494,threshold=65535,left_set=1,right_set=2,
        vx=214,vy=-1,width=64,cell=650,accumulator=0,queue=0,rectangles=0,
        sound_active=0,sound_priority=0)
    entry,patches=make_case(index,row)
    def put(address,raw):
        patches.append((address,bytes(raw)))
    def data(offset,raw):
        put(DATA+offset,raw)
    bp=profile['sp']-8
    put(0x70000+bp-512,bytes((index*7+n*29+11)&255 for n in range(544)))
    data(0x79e6,bytes(profile['states']))
    data(0x208d,bytes((profile['count'],)))
    data(0xc496,bytes((profile['count']+2,)))
    data(0x79f9,b'\0')
    data(0x1b89,b'\0')
    data(0x1baf,b'\1')
    data(0x79ae,bytes((255,255)))
    data(0xc21e,struct.pack('<4H',(80+profile['dx'])&65535,(80+profile['dy'])&65535,0,0))
    data(0xc226,struct.pack('<4H',(80+profile['dx2'])&65535,(80+profile['dy2'])&65535,0,0))
    put(0x40000,bytes(65536))
    put(0x60000,bytes(65536))
    for slot in range(1,profile['count']+1):
        behavior=profile['behavior'] if profile['behavior']>=0 else (3,4,2)[(slot-1)%3]
        kind=13 if behavior==2 else 32 if behavior==6 else 11 if behavior==5 else 1
        expire=profile['expiry']=='all' or profile['expiry']=='first' and slot==1 or \
            profile['expiry']=='last' and slot==profile['count']
        if expire:
            behavior,kind=5,11
        actor=bytearray(38)
        actor[:5]=bytes((kind,slot+1,1 if expire else 200,1,2))
        struct.pack_into('<2H',actor,6,214,65535)
        struct.pack_into('<3H',actor,14,profile['period'],494,65535)
        actor[21]=behavior
        actor[22:29]=bytes((6,6,7,1,1,0,1))
        actor[36]=255
        data(0x1bae+slot*38,actor)
        data(0xc21e+(slot+1)*8,struct.pack('<4H',80+slot,80,0,0))
    entry=(*entry[:11],profile['sp'],0x7ebb,profile['flags'])
    initial,seeds=compact_initial(image,patches)
    return entry,initial,seeds


def generate(root,out):
    require(unicorn.__version__=='2.1.4' and not any(k in os.environ for k in
        ('LD_PRELOAD','LIBUNICORN_PATH')),'Unsupported loop oracle runtime')
    library=Path(uclib._name).resolve(strict=True)
    def mapped():
        return sha(library.read_bytes())==LIB_SHA and any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines())
    require(mapped(),'Actual loop oracle library mapping differs')
    names=tuple(dict.fromkeys((*SOURCES,'nonplayer_loop_oracle.py')))
    sources={name:sha((root/'tools'/name).read_bytes()) for name in names}
    require((root/'tools/nonplayer_loop_oracle.py').read_bytes()==Path(__file__).read_bytes(),
        'Loop producer source differs')
    exe=(root/'LEZAC.EXE').read_bytes()
    require(sha(exe)==EXE_SHA,'Canonical loop executable differs')
    mz=struct.unpack_from('<14H',exe)
    image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4)
        at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    require(out.is_relative_to(Path('/dev/shm')) and not out.exists(),'Use a new RAM-only loop capture')
    out.mkdir()
    output=bytearray(b'LZNPL001'+struct.pack('<I',len(profiles())))
    coverage=Counter()
    summaries=[]
    try:
        for index,profile in enumerate(profiles()):
            entry,initial,seeds=initial_case(index,profile,image)
            endpoints=[]
            trace,writes,events=[],[],[]
            stop=None
            fault=None
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576)
                engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,entry):
                    engine.reg_write(register,value)
                def code(uc,address,size,user):
                    nonlocal stop
                    if address in STOPS:
                        stop=address
                        uc.emu_stop()
                        return
                    r=tuple(uc.reg_read(register) for register in REGS)
                    require((r[7]==0x1000 and r[12]<0x83f0) or
                        (r[7]==0x1920 and r[12]<0x1820) or
                        (r[7]==0x18ac and 0x517<=r[12]<0x5da),
                        'Loop left recovered original code: '+str((r[7],r[12],address)))
                    if r[7]==0x1000 and r[12] in (0x62da,0x6350,0x6500,0x654e,0x7018,0x7ee4):
                        memory=uc.mem_read(0,1048576)
                        local=lambda n:struct.unpack_from('<H',memory,r[10]*16+((r[6]+n)&65535))[0]
                        events.append((len(trace),r[12],struct.unpack_from('<H',memory,DATA+0x2082)[0],
                            *(local(n) for n in (-4,-6,-8,-10))))
                    trace.append(r)
                def write(uc,access,address,size,value,user):
                    require(size in (1,2) and DATA<=address and address+size<=0xb0001,
                        'Loop write left declared data/stack/VGA owners')
                    writes.append((address,size,value&((1<<(size*8))-1)))
                def intr(uc,number,user):
                    nonlocal fault
                    address=uc.reg_read(REGS[7])*16+uc.reg_read(REGS[12])
                    require(number==0 and address in FAULTS,'Unexpected original loop interrupt')
                    fault=address
                    uc.emu_stop()
                def io(*unused):
                    raise ValueError('Original loop attempted hardware I/O')
                engine.hook_add(unicorn.UC_HOOK_INTR,intr)
                engine.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(entry[7]*16+entry[12],0 if observed else (stop or 0),count=3000000)
                r=tuple(engine.reg_read(register) for register in REGS)
                final=bytes(engine.mem_read(0,1048576))
                require((r[7]*16+r[12] in STOPS or fault is not None) and
                    final[0x10000:DATA]==image[:0xaa20],'Original loop endpoint/code differs')
                endpoints.append((r,final,fault))
                del engine
            require(endpoints[0]==endpoints[1],'Loop observer changed complete memory/registers')
            endpoint,final,fault=endpoints[0]
            rebuilt=bytearray(initial)
            for address,size,value in writes:
                rebuilt[address:address+size]=value.to_bytes(size,'little')
            require(rebuilt==final,'Loop ordered writes do not reconstruct memory')
            trace.append(endpoint)
            outcome=3 if fault is not None else STOPS[endpoint[7]*16+endpoint[12]]
            output.extend(struct.pack('<IB13HI13HI',index,outcome,*entry,*endpoint))
            output.extend(struct.pack('<I',len(seeds)))
            for address,raw in seeds:
                output.extend(struct.pack('<II',address,len(raw))+raw)
            encode_trace(output,trace)
            output.extend(struct.pack('<I',len(writes)))
            for item in writes:
                output.extend(struct.pack('<IBH',*item))
            output.extend(struct.pack('<I',len(events)))
            for item in events:
                output.extend(struct.pack('<I6H',*item))
            calls=sum(r[7]==0x1000 and r[12]==0x6053 for r in trace)
            returns=sum(r[7]==0x1000 and r[12]==0x7ee4 for r in trace)
            coverage.update(cases=1,register_states=len(trace),ordered_writes=len(writes),events=len(events),
                actor_calls=calls,actor_returns=returns)
            coverage['outcome_'+str(outcome)]+=1
            summaries.append(dict(index=index,profile=profile,calls=calls,returns=returns,
                final_slot=struct.unpack_from('<H',final,DATA+0x2082)[0],final_count=final[DATA+0x208d],
                outcome=outcome,events=events))
            if index%10==0:
                print('nonplayer_loop_capture='+str(index+1)+'/'+str(len(profiles())),flush=True)
        require(all(sha((root/'tools'/name).read_bytes())==digest for name,digest in sources.items()) and
            sha((root/'LEZAC.EXE').read_bytes())==EXE_SHA and mapped(),'Loop producer inputs changed')
        raw=bytes(output)
        packed=gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(packed)
        manifest=dict(schema='lezac-controlled-nonplayer-loop-v1',coverage=dict(coverage),
            asset_sha256={'LEZAC.EXE':EXE_SHA},source_sha256=sources,projection_bytes=len(raw),
            projection_sha256=sha(raw),compressed_bytes=len(packed),compressed_sha256=sha(packed),
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True,original_code_bytes_verified=43552,
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,
            instruction_patches=0,calls_stubbed=0,hardware_io=0,interrupts_delivered=0,
            one_live_stack=True,later_state_injected=False,production_app_comparison=False,
            natural_capture=False,full_frame_claim=False,raw_memory_published=False)
        (out/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        (out/'checkpoints.json').write_text(json.dumps(summaries,sort_keys=True,indent=2)+'\n')
        print(json.dumps(manifest,sort_keys=True),flush=True)
    except Exception as error:
        failure=dict(index=index,profile=profile,error=str(error))
        if 'engine' in locals():
            failure['registers']=[engine.reg_read(register) for register in REGS]
            (out/'failed-ram.bin').write_bytes(engine.mem_read(0,1048576))
        (out/'failed.json').write_text(json.dumps(failure,indent=2)+'\n')
        (out/'partial-corpus.bin').write_bytes(output)
        (out/'producer-at-failure.py').write_bytes(Path(__file__).read_bytes())
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    generate(args.root,args.out)
