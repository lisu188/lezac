"""Exhaust original 3EDA byte accumulators on controlled initial states."""
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
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA=0x1aa20
WIDTHS=(0,1,16,255,256,32767,32768,65535)
LIMIT=16*1024**2

def profiles():
    rows=[]
    for axis in (0,1):
        for velocity in range(256):
            for phase in range(256):
                xy=(velocity,phase,0,0) if not axis else (0,0,velocity,phase)
                rows.append(('x_exhaustive' if not axis else 'y_exhaustive',*xy,
                    WIDTHS[(velocity*3+phase)%len(WIDTHS)],((velocity*256+phase)*257)&65535,
                    0x3fe4,0x7000,0x202|((phase&1)*0x400),len(rows)%257==0))
    for width,velocity,phase,offset in itertools.product(WIDTHS,(128,129,255,0,1,126,127),
                                                        (128,129,255,0,1,126,127),(0,1,32767,65535)):
        rows.append(('width_edges',0,0,velocity,phase,width,offset,0x3fe4,0x7000,0x202,True))
    for index,xy in enumerate(itertools.product((128,255,1,127),repeat=4)):
        rows.append(('coupled_axes',*xy,WIDTHS[index%8],(index*257)&65535,0x3fe4,0x7000,
                     0x202|((index&1)*0x400),True))
    for ss,sp,direction,xy in itertools.product((0x7000,0x1aa2),(0,1,0x3fe4,65535),(0,1),
                                               ((127,127,128,128),(128,128,127,127))):
        rows.append(('stack_and_alias',*xy,65535,65535,sp,ss,0x202|direction*0x400,True))
    return rows

def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported motion oracle loader')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual motion oracle mapping differs')
    exe=(root/'LEZAC.EXE').read_bytes()
    if sha(exe)!=EXE_SHA:
        raise ValueError('Canonical motion executable differs')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in
             ('transient_motion_oracle.py','frame_camera_oracle.py')}
    mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    base=bytearray(1048576);base[0x10000:0x10000+len(image)]=image
    expected=bytearray(base)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only motion output')
    out.mkdir()
    rows=profiles();output=bytearray(b'LZTRMO01'+struct.pack('<II',len(rows),len(exe))+exe)
    engines=[];trace=[];writes=[];points={};coverage=set();states=0;case_states=0;dense=False
    allowed={(DATA+0x78d3,1),(DATA+0x78d5,1),(DATA+0x2090,2)}
    def external(*unused):
        raise ValueError('Motion crossed an interrupt or hardware I/O')
    def code(uc,address,size,user):
        nonlocal case_states
        if not 0x13eda<=address<=0x13f26:
            raise ValueError('Motion left declared instructions')
        case_states+=1;coverage.add(address-0x10000)
        if address in (0x13eed,0x13f13):
            points[address]=uc.reg_read(REGS[13])
        if dense:
            trace.append(tuple(uc.reg_read(register) for register in REGS))
    def write(uc,access,address,size,value,user):
        if (address,size) not in allowed:
            raise ValueError('Motion write left owned globals')
        writes.append((address,size,value&((1<<(size*8))-1)))
    for observed in (True,False):
        engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
        engine.mem_map(0,1048576);engine.mem_write(0,bytes(base))
        engine.hook_add(unicorn.UC_HOOK_INTR,external)
        engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
        engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
        if observed:
            engine.hook_add(unicorn.UC_HOOK_CODE,code)
            engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
        engines.append(engine)
    previous=[];index=-1;dense_cases=write_count=0
    try:
        for index,row in enumerate(rows):
            family,vx,fx,vy,fy,width,offset,sp,ss,flags,dense=row
            seeds=[(DATA+0x78d2,bytes((vx,fx,vy,fy))),(DATA+0xc204,struct.pack('<H',width)),
                   (DATA+0x2090,struct.pack('<H',offset)),(ss*16+sp,struct.pack('<H',0x4662))]
            values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x4567,
                    0x1000,0x1aa2,0x40,ss,sp,0x3eda,flags)
            for address,raw in previous:
                expected[address:address+len(raw)]=base[address:address+len(raw)]
                for engine in engines:
                    engine.mem_write(address,bytes(base[address:address+len(raw)]))
            for address,raw in seeds:
                expected[address:address+len(raw)]=raw
                for engine in engines:
                    engine.mem_write(address,raw)
            trace=[];writes=[];points={};case_states=0;results=[]
            for engine in engines:
                for register,value in zip(REGS,values):
                    engine.reg_write(register,value)
                engine.emu_start(0x13eda,0x14662,count=64)
                regs=tuple(engine.reg_read(register) for register in REGS)
                if (regs[7],regs[12],regs[11])!=(0x1000,0x4662,(sp+2)&65535):
                    raise ValueError('Motion original return differs')
                results.append(regs)
            if results[0]!=results[1] or set(points)!={0x13eed,0x13f13} or not 2<=len(writes)<=4:
                raise ValueError('Motion observer/register/checkpoint control differs')
            for address,size,value in writes:
                expected[address:address+size]=value.to_bytes(size,'little')
            if any(bytes(engine.mem_read(0,1048576))!=expected for engine in engines):
                raise ValueError('Motion ordered writes or full memory observer control differs')
            if dense:
                trace.append(results[0]);dense_cases+=1
            output.extend(struct.pack('<I4B4HI13HI2IH',index,vx,fx,vy,fy,width,offset,sp,ss,flags,
                                      *results[0],points[0x13eed],points[0x13f13],len(trace)))
            for column in range(14):
                output.extend(struct.pack('<'+('I' if column==13 else 'H')*len(trace),*(r[column] for r in trace)))
            output.extend(struct.pack('<B',len(writes)))
            for entry in writes:
                output.extend(struct.pack('<IBH',*entry))
            if len(output)>LIMIT:
                raise ValueError('Motion compact projection exceeds 16 MiB')
            previous=seeds;states+=case_states;write_count+=len(writes)
            if index%8192==0:
                print(json.dumps(dict(status='running',case=index,cases=len(rows),bytes=len(output))),flush=True)
        if sha((root/'LEZAC.EXE').read_bytes())!=EXE_SHA or sha(library.read_bytes())!=LIB_SHA or any(
                sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()):
            raise ValueError('Motion producer inputs changed')
        raw=bytes(output);packed=gzip.compress(raw,compresslevel=9,mtime=0)
        (out/'oracle.bin.gz').write_bytes(packed)
        manifest=dict(schema='lezac-controlled-transient-motion-v1',cases=len(rows),dense_cases=dense_cases,
            profile_families=dict(Counter(row[0] for row in rows)),asset_sha256={'LEZAC.EXE':EXE_SHA},
            source_sha256=sources,unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True,complete_memory_observer_control=True,
            complete_initial_seed_reconstruction=True,ordered_writes_reconstruct_memory=True,
            executed_instructions=sorted(coverage),original_instructions=states,ordered_writes=write_count,
            exhaustive_x_pairs=65536,exhaustive_y_pairs=65536,all_addition_flags_per_case=True,
            dense_trace_flags_compared='all',projection_bytes=len(raw),projection_sha256=sha(raw),
            compressed_bytes=len(packed),compressed_sha256=sha(packed),instruction_patches=0,calls_stubbed=0,
            interrupts_delivered=0,hardware_io=0,later_state_injected=False,controlled_initial_memory=True,
            natural_capture=False,raw_memory_published=False,actual_app_integration=False,full_frame_claim=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(rows),dense_cases=dense_cases,states=states,
            writes=write_count,raw_bytes=len(raw),compressed_bytes=len(packed))),flush=True)
    except BaseException as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=repr(error)))+'\n')
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
