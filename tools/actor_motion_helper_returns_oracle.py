"""Probe actual original helper RET instructions, not complete helper calls."""
import argparse
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha


def generate(root,out):
    out=out.resolve()
    protected=(root/'LEZAC.EXE',root/'tools/actor_motion_helper_returns_oracle.py',root/'tools/frame_camera_oracle.py')
    if not out.is_relative_to(Path('/dev/shm')) or out.exists() or any(out==p.resolve() for p in protected):
        raise ValueError('Use a new RAM-only helper-return report')
    result=dict(status='failed',scope='single actual original near RET per case',
        full_helper_execution=False,production_app_comparison=False,full_frame_claim=False,cases=[])
    try:
        if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
            raise ValueError('Unsupported helper-return runtime')
        library=Path(uclib._name).resolve(strict=True)
        def mapped():
            return sha(library.read_bytes())==LIB_SHA and any(line.endswith(str(library))
                for line in Path('/proc/self/maps').read_text().splitlines())
        if not mapped():
            raise ValueError('Actual helper-return library mapping differs')
        names=('actor_motion_helper_returns_oracle.py','frame_camera_oracle.py')
        sources={name:sha((root/'tools'/name).read_bytes()) for name in names}
        exe=(root/'LEZAC.EXE').read_bytes()
        if sha(exe)!=EXE_SHA:
            raise ValueError('Canonical helper-return executable differs')
        mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
        for i in range(mz[3]):
            offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
            struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
        for name,ip,cleanup in (('TileFracture',0x3a53,10),('TileSample',0x5b83,2),('Friction',0x5bc9,2)):
            opcode=image[ip:ip+3]
            if opcode!=bytes((0xc2,cleanup,0)):
                raise ValueError('Original helper RET opcode differs')
            for caller in (0x7f00,0x73e5):
                values=(4,0,0,0,0,0,0x3fdc,0x1000,0x1aa2,0,0x7000,0x3f8c,ip,0x202)
                initial=bytearray(1048576);initial[0x10000:0x10000+len(image)]=image
                struct.pack_into('<H',initial,0x73f8c,caller)
                expected=list(values);expected[11]+=2+cleanup;expected[12]=caller
                endpoints=[];observed_instructions=[];writes=[]
                for observed in (True,False):
                    engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                    engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
                    for register,value in zip(REGS,values):
                        engine.reg_write(register,value)
                    def reject(*unused):
                        raise ValueError('Helper RET attempted hardware I/O or interrupt')
                    def code(uc,address,size,user):
                        observed_instructions.append((address,size))
                    def write(uc,access,address,size,value,user):
                        writes.append((address,size,value))
                    engine.hook_add(unicorn.UC_HOOK_INTR,reject)
                    engine.hook_add(unicorn.UC_HOOK_INSN,reject,None,1,0,UC_X86_INS_IN)
                    engine.hook_add(unicorn.UC_HOOK_INSN,reject,None,1,0,UC_X86_INS_OUT)
                    if observed:
                        engine.hook_add(unicorn.UC_HOOK_CODE,code)
                        engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                    engine.emu_start(0x10000+ip,0,count=1)
                    registers=tuple(engine.reg_read(register) for register in REGS)
                    final=bytes(engine.mem_read(0,1048576));endpoints.append((registers,sha(final)))
                    if registers!=tuple(expected) or final!=initial:
                        raise ValueError('Original helper RET register/memory result differs')
                    del engine
                if endpoints[0]!=endpoints[1] or observed_instructions!=[(0x10000+ip,3)] or writes:
                    raise ValueError('Helper-return observer control differs')
                result['cases'].append(dict(helper=name,opcode=opcode.hex(),initial_registers=values,
                    final_registers=expected,initial_memory_sha256=sha(initial),final_memory_sha256=endpoints[0][1],
                    observed_instructions=1,ordered_writes=0,complete_memory_observer_control=True))
        if not mapped() or sha((root/'LEZAC.EXE').read_bytes())!=EXE_SHA or any(
                sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()):
            raise ValueError('Helper-return producer inputs changed')
        result.update(status='passed',asset_sha256={'LEZAC.EXE':EXE_SHA},source_sha256=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True,instruction_patches=0,later_state_injected=False,
            interrupts_delivered=0,hardware_io=0,raw_memory_published=False)
    except BaseException as error:
        result['error']=repr(error);raise
    finally:
        out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status='passed',cases=len(result['cases']),sha256=sha(out.read_bytes()),report=str(out))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
