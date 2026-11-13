"""Run complete unchanged raster instructions on real assets and declared controlled state."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import (UC_X86_REG_AX,UC_X86_REG_BX,UC_X86_REG_CX,UC_X86_REG_DX,
    UC_X86_REG_SI,UC_X86_REG_DI,UC_X86_REG_BP,UC_X86_REG_CS,UC_X86_REG_DS,UC_X86_REG_ES,
    UC_X86_REG_SS,UC_X86_REG_SP,UC_X86_REG_IP,UC_X86_REG_EFLAGS,UC_X86_INS_IN,UC_X86_INS_OUT)
from frame_world_raster_inputs import ASSETS,SCRATCH,DATA,BUFFER,STACK,assets,profiles,initial_memory

REGS=(UC_X86_REG_AX,UC_X86_REG_BX,UC_X86_REG_CX,UC_X86_REG_DX,UC_X86_REG_SI,UC_X86_REG_DI,
    UC_X86_REG_BP,UC_X86_REG_CS,UC_X86_REG_DS,UC_X86_REG_ES,UC_X86_REG_SS,UC_X86_REG_SP,
    UC_X86_REG_IP,UC_X86_REG_EFLAGS)
LIB_SHA='ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def generate(root,out):
    library=Path(uclib._name).resolve(strict=True)
    if unicorn.__version__!='2.1.4' or sha(library.read_bytes())!=LIB_SHA or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported actual Unicorn loader profile')
    if not any(line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual Unicorn mapping differs')
    loaded=assets(root)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output')
    out.mkdir()
    cases=profiles()
    output=bytearray(b'LZRAST01'+struct.pack('<I',len(cases)))
    coverage=set()
    metadata=[]
    try:
        for index,profile in enumerate(cases):
            initial,values,return_ip=initial_memory(index,profile,loaded)
            endpoints=[]
            writes=[]
            pc=[0]
            transfers=[0]
            steps=[0]
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576)
                engine.mem_write(0,bytes(initial))
                for reg,value in zip(REGS,values):
                    engine.reg_write(reg,value)
                def external(*unused):
                    raise ValueError('Raster crossed an unmodeled interrupt or I/O')
                def code(uc,address,size,user):
                    pc[0]=address-0x18ac0
                    if not 0xf4<=pc[0]<=0x3c7:
                        raise ValueError('Raster left unchanged routine')
                    coverage.add(pc[0]);steps[0]+=1
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (BUFFER<=address and address+size<=BUFFER+65538 or
                            STACK<=address and address+size<=STACK+72 or size==2 and address in {DATA+o for o in SCRATCH}):
                        raise ValueError('Raster wrote outside declared output/context/stack')
                    writes.append((address,size,value&((1<<(size*8))-1)))
                    if pc[0] in (0x153,0x1ec):
                        transfers[0]+=1
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(0x18bb4,0x10000+return_ip,count=2000000)
                registers=tuple(engine.reg_read(reg) for reg in REGS)
                final=bytes(engine.mem_read(0,1048576))
                if registers[7]!=0x1000 or registers[12]!=return_ip or final[0x10000:DATA]!=initial[0x10000:DATA]:
                    raise ValueError('Raster endpoint or unchanged code differs')
                endpoints.append((registers,final))
            if endpoints[0]!=endpoints[1]:
                raise ValueError('Raster observer affected complete memory/registers')
            registers,final=endpoints[0]
            output.extend(struct.pack('<12H13HI13HII',index,*profile,*values,*registers,transfers[0]))
            output.extend(struct.pack('<6H',*(struct.unpack_from('<H',final,DATA+o)[0] for o in SCRATCH)))
            output.extend(final[STACK:STACK+72])
            output.extend(final[BUFFER:BUFFER+65538])
            output.extend(struct.pack('<I',len(writes)))
            for address,size,value in writes:
                output.extend(struct.pack('<IBH',address,size,value))
            metadata.append(dict(index=index,profile=list(profile),writes=len(writes),rep_words=transfers[0],unicorn_steps=steps[0],
                output_sha256=sha(final[BUFFER:BUFFER+65538])))
            print(json.dumps(metadata[-1]),flush=True)
        raw=bytes(output);compressed=gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest=dict(schema='lezac-controlled-world-raster-v1',assets=ASSETS,
            sources={name:sha((root/'tools'/name).read_bytes()) for name in ('frame_world_raster_oracle.py','frame_world_raster_inputs.py')},
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            cases=metadata,instruction_addresses=sorted(coverage),projection_bytes=len(raw),projection_sha256=sha(raw),
            compressed_bytes=len(compressed),compressed_sha256=sha(compressed),
            controlled_initial_state=True,full_memory_observer_control=True,raw_memory_published=False,
            natural_capture=False,full_frame_claim=False,work_clock_claim=False,endpoint_all_flags_compared=True)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(cases),instructions=len(coverage),bytes=len(raw),compressed=len(compressed),sha256=sha(raw))))
    except Exception as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=str(error)))+'\n')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    generate(args.repo.resolve(),args.out)
