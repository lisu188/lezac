"""Unchanged complete boss-link helper, with freshly executed original sine inputs."""
import argparse
import gzip
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT
from frame_camera_oracle import REGS, EXE_SHA, LIB_SHA, sha

DATA=0x1aa20


def profiles():
    # count, mode, gain, phase, radiusX/Y, target/self, offsets, bias, floor, SP, error
    result=[]
    def add(count=1,mode=0,gain=3,phase=17,rx=100,ry=48,target=2,self=3,
            x=0xffff,y=0x8000,bias=0x80,floor=0x200,sp=0x3fde,error=0):
        result.append((count,mode,gain,phase,rx,ry,target,self,x,y,bias,floor,sp,error))
    add(count=0)
    for count in range(1,8):
        add(count=count,mode=255)
    for value in range(256):
        add(mode=value)
    for value in range(256):
        add(gain=value)
    for value in range(256):
        add(mode=255,phase=value)
    for value in range(256):
        add(mode=255,phase=value&127,rx=value,ry=255-value)
    for value in range(256):
        add(bias=value)
    for target in (0,1,31,32,127,255):
        for self in (0,1,31,32,127,255):
            for mode in (0,255):
                add(target=target,self=self,mode=mode)
    for x in (0,1,0x7ffe,0x7fff,0x8000,0x8001,0xffff):
        for y in (0,1,0x7ffe,0x7fff,0x8000,0x8001,0xffff):
            add(x=x,y=y)
    add(count=255,mode=0)
    for floor,sp in ((0x4000,0x3fde),(0x200,0x210),(0x3dd3,0x3fde)):
        add(floor=floor,sp=sp,error=1)
    return result


def base_memory(image):
    memory=bytearray(1048576)
    memory[0x10000:0x10000+len(image)]=image
    struct.pack_into('<H',memory,DATA+0x1afa,0x200)
    return memory


def execute(initial,registers,entry,until,initializer=False,observed=True):
    engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
    engine.mem_map(0,1048576)
    engine.mem_write(0,bytes(initial))
    for reg,value in zip(REGS,registers):
        engine.reg_write(reg,value)
    trace,writes,coverage=[],[],set()
    stack=0x70000+registers[11]-1024
    def external(*unused):
        raise ValueError('Original link work crossed an interrupt or hardware I/O')
    def code(uc,address,size,user):
        row=tuple(uc.reg_read(reg) for reg in REGS)
        cs,ip=row[7],row[12]
        if not (cs==0x1000 and ((0x2714<=ip<0x2767) if initializer else (0x432a<=ip<=0x4529)) or
                cs==0x1920 and 0<=ip<0x1820):
            raise ValueError('Original link work left declared original code: '+str((cs,ip)))
        coverage.add((cs,ip))
        if not initializer:
            trace.append(row)
    def write(uc,access,address,size,value,user):
        allowed=(stack<=address and address+size<=0x74000)
        if initializer:
            allowed=allowed or (address==DATA+0x2082 and size==2) or (
                DATA+0x7bda<=address and address+size<=DATA+0x7bda+768)
        else:
            count=initial[DATA+0x79f9]
            for link in range(1,count+1):
                base=DATA+0x79ea+link*16
                allowed=allowed or (size==1 and address==base+6) or (size==2 and address in (base+11,base+13))
        if size not in (1,2,4) or not allowed:
            raise ValueError('Original link write left declared owners: '+str((address,size)))
        writes.append((address,size,value&((1<<(size*8))-1)))
    engine.hook_add(unicorn.UC_HOOK_INTR,external)
    engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
    engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
    if observed:
        engine.hook_add(unicorn.UC_HOOK_CODE,code)
        engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
    engine.emu_start(entry,until,count=4000000)
    final=bytes(engine.mem_read(0,1048576))
    registers=tuple(engine.reg_read(reg) for reg in REGS)
    if registers[7]*16+registers[12]!=until or final[0x10000:DATA]!=initial[0x10000:DATA]:
        raise ValueError('Original link endpoint or unchanged code differs')
    if observed:
        reconstructed=bytearray(initial)
        for address,size,value in writes:
            reconstructed[address:address+size]=value.to_bytes(size,'little')
        if reconstructed!=final:
            raise ValueError('Link ordered writes do not reconstruct complete memory')
    return registers,final,trace,writes,coverage


def sine_table(image):
    initial=base_memory(image)
    initial[0x73bde:0x74000]=bytes((i*29+11)&255 for i in range(0x422))
    registers=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x3ffe,
        0x1000,0x1aa2,0x40,0x7000,0x3fde,0x2714,0x202)
    observed=execute(initial,registers,0x12714,0x12767,True)
    plain=execute(initial,registers,0x12714,0x12767,True,False)
    if observed[:2]!=plain[:2]:
        raise ValueError('Sine initializer observer changed complete memory/registers')
    raw=observed[1][DATA+0x7bda:DATA+0x7bda+768]
    return raw,dict(entry='1000:2714',until='1000:2767',sha256=sha(raw),
        initial_memory_sha256=sha(initial),final_memory_sha256=sha(observed[1]),
        endpoint_registers=list(observed[0]),writes=len(observed[3]),
        code_addresses=[list(row) for row in sorted(observed[4])],
        full_memory_observer_control=True,ordered_writes_reconstruct_complete_memory=True)


def memory(index,profile,image,sines):
    count,mode,gain,phase,rx,ry,target,self,x,y,bias,floor,sp,error=profile
    initial=base_memory(image)
    initial[0x70000+sp-1024:0x70000+sp+16]=bytes((i*29+index*7+11)&255 for i in range(1040))
    struct.pack_into('<H',initial,DATA+0x1afa,floor)
    initial[DATA+0x7bda:DATA+0x7bda+768]=sines
    for visual in range(256):
        struct.pack_into('<4H',initial,DATA+0xc21e+visual*8,
            (visual*977+index*13+0x7fff)&65535,(visual*1013+index*17+0x8000)&65535,
            (visual*37+index*19+0xa55a)&65535,(visual*41+index*23+0x5aa5)&65535)
    for link in range(1,count+1):
        at=DATA+0x79ea+link*16
        initial[at:at+16]=bytes((i*11+index*7+link*19)&255 for i in range(16))
        actual_mode=(255 if link%2 else 0) if count in range(2,8) else mode
        initial[at:at+7]=bytes((target,self,gain,actual_mode,rx,ry,(phase+link-1)&255))
        struct.pack_into('<2H',initial,at+7,x,y)
        initial[at+15]=bias
    initial[DATA+0x79f9]=count
    struct.pack_into('<H',initial,0x70000+sp,0x7ec5)
    registers=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x3ffe,
        0x1000,0x1aa2,0x40,0x7000,sp,0x432a,0x602 if index%2 else 0x202)
    return initial,registers


def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported original link CPU profile')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual original link CPU mapping differs')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in ('boss_links_oracle.py','frame_camera_oracle.py')}
    exe=(root/'LEZAC.EXE').read_bytes()
    if sha(exe)!=EXE_SHA:
        raise ValueError('Original link executable differs')
    mz=struct.unpack_from('<14H',exe)
    image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4)
        at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only link output')
    out.mkdir()
    index=-1
    try:
        sines,sine_proof=sine_table(image)
        cases=profiles()
        output=bytearray(b'LZLINK01'+struct.pack('<I',len(cases))+sines)
        coverage=set();states=write_count=0
        for index,profile in enumerate(cases):
            initial,registers=memory(index,profile,image,sines)
            until=0x192e2 if profile[-1] else 0x17ec5
            observed=execute(initial,registers,0x1432a,until)
            plain=execute(initial,registers,0x1432a,until,observed=False)
            if observed[:2]!=plain[:2]:
                raise ValueError('Link observer changed complete memory/registers')
            endpoint,final,trace,writes,addresses=observed
            trace.append(endpoint);coverage.update(addresses)
            output.extend(struct.pack('<I14H',index,*profile))
            output.extend(struct.pack('<13HI13HI',*registers,*endpoint))
            output.extend(struct.pack('<I',len(trace)))
            for row in trace:
                output.extend(struct.pack('<13HI',*row))
            output.extend(struct.pack('<I',len(writes)))
            for row in writes:
                output.extend(struct.pack('<IBI',*row))
            states+=len(trace);write_count+=len(writes)
        if sha((root/'LEZAC.EXE').read_bytes())!=EXE_SHA or sha(library.read_bytes())!=LIB_SHA or any(
                sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()):
            raise ValueError('Original link producer changed during generation')
        raw=bytes(output);compressed=gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest=dict(schema='lezac-controlled-boss-links-v1',executable_sha256=EXE_SHA,sources=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            cases=len(cases),register_states=states,writes=write_count,runtime_errors=3,sine_initializer=sine_proof,
            executed_instructions=[list(row) for row in sorted(coverage)],projection_bytes=len(raw),projection_sha256=sha(raw),
            compressed_bytes=len(compressed),compressed_sha256=sha(compressed),original_code_bytes_verified=43552,
            complete_memory_observer_control=True,ordered_writes_reconstruct_full_memory=True,
            instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_io=0,
            controlled_initial_memory=True,natural_capture=False,production_app_comparison=False,
            raw_memory_published=False,full_frame_claim=False,whole_game_parity=False,
            trace_arithmetic_flags_compared=False,endpoint_all_flags_compared=True)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(cases),states=states,writes=write_count,
            sine_sha256=sha(sines),bytes=len(raw),compressed=len(compressed),sha256=sha(raw))))
    except Exception as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=str(error)))+'\n')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    generate(args.repo.resolve(),args.out)
