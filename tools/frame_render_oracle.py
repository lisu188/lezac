"""Execute the unchanged camera/raster/copy caller with complete observer controls."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from frame_world_raster_oracle import REGS,LIB_SHA
from frame_render_inputs import ASSETS,DATA,STACK,assets,memory,profiles
from unicorn.x86_const import UC_X86_INS_IN,UC_X86_INS_OUT

sha=lambda raw:hashlib.sha256(raw).hexdigest()


def fnv(raw):
    value=14695981039346656037
    for byte in raw:
        value=((value^byte)*1099511628211)&0xffffffffffffffff
    return value


def generate(root,out):
    library=Path(uclib._name).resolve(strict=True)
    if unicorn.__version__!='2.1.4' or sha(library.read_bytes())!=LIB_SHA or any(
            key in os.environ for key in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Actual original-CPU loader differs')
    if not any(line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual original-CPU mapping differs')
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output')
    loaded=assets(root)
    out.mkdir()
    cases=profiles()
    output=bytearray(b'LZREND01'+struct.pack('<I',len(cases)))
    coverage=set()
    metadata=[]
    try:
        for index,profile in enumerate(cases):
            initial,values=memory(index,profile,loaded)
            endpoints=[]
            writes=[]
            calls=[]
            transfers=[0]
            steps=[0]
            rep_stops=[0]
            pc=[(0,0)]
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576)
                engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):
                    engine.reg_write(register,value)
                def external(*unused):
                    raise ValueError('Render caller crossed an unmodeled interrupt or I/O')
                def code(uc,address,size,user):
                    cs,ip=uc.reg_read(REGS[7]),uc.reg_read(REGS[12])
                    if not (cs==0x1000 and (0x7a13<=ip<0x7a57 or 0x3587<=ip<=0x370b) or
                            cs==0x18ac and 0xf4<=ip<=0x416 or
                            cs==0x1920 and (0x4df<=ip<=0x4f4 or 0x92a<=ip<=0x944)):
                        raise ValueError('Render caller left unchanged recovered code')
                    if observed:
                        if (cs,ip) in ((0x18ac,0x153),(0x18ac,0x1ec),(0x18ac,0x407)) and uc.reg_read(REGS[2])==0 and pc[0]==(cs,ip):
                            rep_stops[0]+=1
                        pc[0]=(cs,ip)
                        coverage.add((cs,ip))
                        steps[0]+=1
                        if (cs,ip) in ((0x1000,0x3587),(0x18ac,0xf4),(0x18ac,0x3c8)):
                            returned=int.from_bytes(uc.mem_read(0x80000+uc.reg_read(REGS[11]),2),'little')
                            calls.append((cs,ip,returned))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (
                            0x40010<=address and address+size<=0x50012 or
                            0xa0000<=address and address+size<=0xb0002 or
                            STACK<=address and address+size<=STACK+72 or
                            size==2 and address in {DATA+offset for offset in (
                                0xc1e8,0xc1f0,0xc1f4,0xc200,0xc202,0xc20a,0xc20c,0xc210,0xc216,0xc218,0xc21a,0xc21c)}):
                        raise ValueError('Render caller wrote outside declared outputs')
                    writes.append((address,size,value&((1<<(size*8))-1)))
                    if pc[0] in ((0x18ac,0x153),(0x18ac,0x1ec),(0x18ac,0x407)):
                        transfers[0]+=1
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(0x17a13,0x192e2 if profile[-1] else 0x17a57,count=4000000)
                registers=tuple(engine.reg_read(register) for register in REGS)
                final=bytes(engine.mem_read(0,1048576))
                if (registers[7],registers[12]) not in ((0x1000,0x7a57),(0x1920,0xe2)):
                    raise ValueError('Render caller did not reach a declared endpoint')
                if final[0x10000:DATA]!=initial[0x10000:DATA]:
                    raise ValueError('Original code bytes changed')
                endpoints.append((registers,final))
            if endpoints[0]!=endpoints[1]:
                raise ValueError('Observer changed complete memory or registers')
            registers,final=endpoints[0]
            runtime_error=registers[12]==0xe2
            expected_calls=[(cs,ip,returned) for player,state in enumerate(profile[1:3]) if state
                for cs,ip,returned in ((0x1000,0x3587,(0x7a25,0x7a47)[player]),
                    (0x18ac,0xf4,(0x7a2a,0x7a4c)[player]),(0x18ac,0x3c8,(0x7a35,0x7a57)[player]))]
            if calls!=(expected_calls[:1] if profile[-1] else expected_calls):
                raise ValueError('Original camera/raster/copy call order differs')
            output.extend(struct.pack('<12H13HI13HIIIIBQQ',index,*profile,*values,*registers,
                transfers[0],steps[0],rep_stops[0],runtime_error,fnv(initial),fnv(final)))
            output.extend(struct.pack('<I',len(writes)))
            for address,size,value in writes:
                output.extend(struct.pack('<IBH',address,size,value))
            metadata.append(dict(index=index,profile=list(profile),writes=len(writes),calls=calls,
                rep_words=transfers[0],unicorn_steps=steps[0],unicorn_rep_zero_stops=rep_stops[0],runtime_error=runtime_error,
                initial_memory_sha256=sha(initial),final_memory_sha256=sha(final),
                final_vga_sha256=sha(final[0xa0000:0xafa00])))
            if index==9:
                (out/'original.idx').write_bytes(final[0xa0000:0xafa00])
            print(json.dumps(metadata[-1]),flush=True)
        raw=bytes(output)
        compressed=gzip.compress(raw,mtime=0)
        (out/'oracle.bin').write_bytes(raw)
        (out/'oracle.bin.gz').write_bytes(compressed)
        sources=('frame_render_inputs.py','frame_render_oracle.py','frame_world_raster_inputs.py','frame_world_raster_oracle.py')
        manifest=dict(schema='lezac-controlled-render-caller-v1',assets=ASSETS,
            sources={name:sha((root/'tools'/name).read_bytes()) for name in sources},cases=metadata,
            instruction_addresses=sorted(coverage),unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True,projection_bytes=len(raw),projection_sha256=sha(raw),
            compressed_bytes=len(compressed),compressed_sha256=sha(compressed),
            controlled_initial_state=True,full_memory_observer_control=True,endpoint_all_flags_compared=True,
            raw_memory_published=False,natural_capture=False,full_frame_claim=False,work_clock_claim=False,
            interrupts_and_io_rejected=True,original_calls_stubbed=0,instruction_patches=0)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(cases),bytes=len(raw),compressed=len(compressed))))
    except Exception as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=str(error)))+'\n')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    generate(args.repo.resolve(),args.out)
