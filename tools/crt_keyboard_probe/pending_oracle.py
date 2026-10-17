"""Execute both complete original pending-byte CRT paths without BIOS or call stubs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

import unicorn
from unicorn.x86_const import (UC_X86_REG_AX,UC_X86_REG_BX,UC_X86_REG_CX,UC_X86_REG_DX,UC_X86_REG_SI,UC_X86_REG_DI,
    UC_X86_REG_BP,UC_X86_REG_CS,UC_X86_REG_DS,UC_X86_REG_ES,UC_X86_REG_SS,UC_X86_REG_SP,UC_X86_REG_IP,UC_X86_REG_EFLAGS)

sha=lambda raw:hashlib.sha256(raw).hexdigest()
REGS=(UC_X86_REG_AX,UC_X86_REG_BX,UC_X86_REG_CX,UC_X86_REG_DX,UC_X86_REG_SI,UC_X86_REG_DI,UC_X86_REG_BP,
    UC_X86_REG_CS,UC_X86_REG_DS,UC_X86_REG_ES,UC_X86_REG_SS,UC_X86_REG_SP,UC_X86_REG_IP)


def capture(executable,out):
    assert unicorn.__version__=='2.1.4';out=out.resolve();assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
    raw=executable.read_bytes();assert sha(raw)=='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    mz=struct.unpack_from('<14H',raw);image=bytearray(raw[0x770:])
    for index in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',raw,mz[12]+4*index);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    def unexpected(*unused):
        raise RuntimeError('Pending-byte paths unexpectedly called an interrupt')
    def emulator():
        engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16);engine.mem_map(0,1048576)
        engine.mem_write(0x10000,bytes(image));engine.hook_add(unicorn.UC_HOOK_INTR,unexpected)
        return engine
    observed,control=emulator(),emulator();work=0
    def decoded(*unused):
        nonlocal work
        work+=1
    observed.hook_add(unicorn.UC_HOOK_CODE,decoded)
    contexts={id(engine):engine.context_save() for engine in (observed,control)}
    def initialize(engine,ip,pending,flags):
        engine.context_restore(contexts[id(engine)])
        values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x9abc,0x184a,0x1aa2,0xbeef,0x8000,0xfe00,ip)
        for register,value in zip(REGS,values):
            engine.reg_write(register,value)
        engine.reg_write(UC_X86_REG_EFLAGS,flags)
        stack=bytearray((pending+i)&255 for i in range(128));struct.pack_into('<2H',stack,80,0x7a05,0x1000)
        engine.mem_write(0x8fdb0,bytes(stack));engine.mem_write(0x1aa20+0x7f6d,bytes([pending,0]))
    def state(engine):
        return struct.pack('<13HI',*[engine.reg_read(register) for register in REGS],engine.reg_read(UC_X86_REG_EFLAGS))+\
            bytes(engine.mem_read(0x8fdb0,128))+bytes(engine.mem_read(0x1aa20+0x7f6d,2))
    output=bytearray(b'LZCKOR01'+struct.pack('<I',510))
    for ip in (0x2fd,0x30f):
        for pending in range(1,256):
            flags=0x202|(0x8d5 if pending%2 else 0)|(0x400 if pending%3==0 else 0)
            initialize(observed,ip,pending,flags);work=0
            observed.emu_start(0x184a0+ip,0x17a05,count=128)
            endpoint=state(observed);assert observed.reg_read(UC_X86_REG_IP)==0x7a05 and work==(4 if ip==0x2fd else 9)
            initialize(control,ip,pending,flags);control.emu_start(0x184a0+ip,0x17a05,count=128)
            assert state(control)==endpoint
            output.extend(struct.pack('<HB2I',ip,pending,flags,work)+endpoint)
    for engine in (observed,control):
        assert bytes(engine.mem_read(0x10000,43552))==image[:43552]
    out.mkdir();compressed=gzip.compress(output,mtime=0);(out/'pending.bin.gz').write_bytes(compressed)
    (out/'pending.bin').write_bytes(output)
    record=dict(cases=510,pending_inputs=255,original_executable_sha256=sha(raw),producer_sha256=sha(Path(__file__).read_bytes()),
        projection_sha256=sha(output),projection_bytes=len(output),compressed_sha256=sha(compressed),compressed_bytes=len(compressed),
        unicorn=unicorn.__version__,original_calls_stubbed=False,instruction_patches=0,read_hooks=False,
        separate_unobserved_control_endpoints_identical=True,full_endpoint_flags=True,natural_gameplay_claim=False)
    (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();capture(args.exe,args.out)
