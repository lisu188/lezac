"""Unchanged original camera instructions on explicit controlled inputs, not natural play."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX,
    UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES,
    UC_X86_REG_SS, UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS, UC_X86_INS_IN, UC_X86_INS_OUT)

REGS = (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX, UC_X86_REG_SI, UC_X86_REG_DI,
    UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_SP,
    UC_X86_REG_IP, UC_X86_REG_EFLAGS)
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
LIB_SHA = 'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c'
FIELDS = (0xc216,0xc218,0xc1f0,0xc20a,0xc20c)
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def profiles():
    result = []
    for width,height,view in ((60,40,40),(60,40,20),(100,80,40),(41,30,21)):
        half = view*4-8
        xs = (-32768,-32767,-1,0,7,8,half-1,half,half+7,half+8,width*8-half-1,width*8-half,32767)
        ys = (-32768,-1,0,7,8,79,80,87,88,height*8-81,height*8-80,32767)
        for x in xs:
            for y in ys:
                for shake in (0,3,-2):
                    result.append((width,height,view,x&65535,y&65535,shake&65535,0x200,0x3fe4,0))
    for floor,sp,error in ((0,0x200,1),(0x4000,0x3fe4,1),(0x3ddf,0x3fe4,1),(0x3dde,0x3fe4,0)):
        result.append((60,40,40,144,80,0,floor,sp,error))
    return result


def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported Unicorn loader profile')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual Unicorn library mapping differs')
    exe=(root/'LEZAC.EXE').read_bytes()
    if sha(exe)!=EXE_SHA:
        raise ValueError('Original executable differs')
    mz=struct.unpack_from('<14H',exe)
    image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4)
        at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output directory')
    out.mkdir()
    cases=profiles()
    output=bytearray(b'LZCAM001'+struct.pack('<I',len(cases)))
    coverage=set()
    states=0
    try:
        for index,profile in enumerate(cases):
            width,height,view,x,y,shake,floor,sp,error=profile
            initial=bytearray(1048576)
            initial[0x10000:0x10000+len(image)]=image
            stack=0x70000+sp-64
            initial[stack:stack+72]=bytes((i*29+index*7+11)&255 for i in range(72))
            return_ip=0x7a25 if index%2==0 else 0x7a47
            struct.pack_into('<3H',initial,0x70000+sp,return_ip,y,x)
            for offset,value in ((0xc204,width),(0x78bc,view*4-8),(0x78be,(view*4-8)//8),
                    (0x2094,(width-view)*8),(0x2096,height*8-160),(0x2098,shake),(0x1afa,floor)):
                struct.pack_into('<H',initial,0x1aa20+offset,value)
            for offset in FIELDS:
                struct.pack_into('<H',initial,0x1aa20+offset,0xa55a)
            values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x3ffe,
                0x1000,0x1aa2,0x40,0x7000,sp,0x3587,0x602 if index%2 else 0x202)
            endpoints=[]
            trace=[]
            writes=[]
            until=0x192e2 if error else 0x10000+return_ip
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576)
                engine.mem_write(0,bytes(initial))
                for reg,value in zip(REGS,values):
                    engine.reg_write(reg,value)
                def external(*unused):
                    raise ValueError('Camera crossed an unmodeled interrupt or I/O')
                def code(uc,address,size,user):
                    registers=tuple(uc.reg_read(reg) for reg in REGS)
                    coverage.add((registers[7],registers[12]))
                    trace.append(registers)
                def write(uc,access,address,size,value,user):
                    if size!=2 or not (stack<=address<stack+70 or address in {0x1aa20+o for o in FIELDS}):
                        raise ValueError('Camera wrote outside declared stack/context')
                    writes.append((address,value&65535))
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(0x13587,until,count=10000)
                registers=tuple(engine.reg_read(reg) for reg in REGS)
                final=bytes(engine.mem_read(0,1048576))
                if registers[7]*16+registers[12]!=until or final[0x10000:0x1aa20]!=image[:0xaa20]:
                    raise ValueError('Camera endpoint or unchanged code differs')
                endpoints.append((registers,final))
            if endpoints[0]!=endpoints[1]:
                raise ValueError('Camera observer affected complete memory/registers')
            registers,final=endpoints[0]
            trace.append(registers)
            states+=len(trace)
            output.extend(struct.pack('<11H13HI13HI',index,*profile[:8],return_ip,error,*values,*registers))
            output.extend(struct.pack('<5H',*(struct.unpack_from('<H',final,0x1aa20+o)[0] for o in FIELDS)))
            output.extend(final[stack:stack+72])
            output.extend(struct.pack('<I',len(trace)))
            for item in trace:
                output.extend(struct.pack('<13HI',*item))
            output.extend(struct.pack('<I',len(writes)))
            for address,value in writes:
                output.extend(struct.pack('<IH',address,value))
        raw=bytes(output)
        compressed=gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest=dict(schema='lezac-controlled-camera-v1',executable_sha256=EXE_SHA,
            producer_sha256=sha(Path(__file__).read_bytes()),unicorn_version=unicorn.__version__,
            unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            cases=len(cases),register_states=states,runtime_errors=3,
            executed_instructions=[list(pair) for pair in sorted(coverage)],
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(compressed),compressed_sha256=sha(compressed),
            controlled_initial_memory=True,full_memory_observer_control=True,raw_memory_published=False,
            natural_capture=False,full_frame_claim=False,work_clock_claim=False,
            trace_arithmetic_flags_compared=False,endpoint_all_flags_compared=True)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(cases),states=states,bytes=len(raw),compressed=len(compressed),sha256=sha(raw))))
    except Exception as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=str(error)))+'\n')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    generate(args.repo.resolve(),args.out)
