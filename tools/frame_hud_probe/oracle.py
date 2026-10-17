"""Execute unchanged original HUD callees on explicit controlled inputs, without stubs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

import unicorn
from unicorn.x86_const import (UC_X86_REG_AX,UC_X86_REG_BX,UC_X86_REG_CX,UC_X86_REG_DX,UC_X86_REG_SI,UC_X86_REG_DI,
    UC_X86_REG_BP,UC_X86_REG_CS,UC_X86_REG_DS,UC_X86_REG_ES,UC_X86_REG_SS,UC_X86_REG_SP,UC_X86_REG_IP,UC_X86_REG_EFLAGS)

REGS=(UC_X86_REG_AX,UC_X86_REG_BX,UC_X86_REG_CX,UC_X86_REG_DX,UC_X86_REG_SI,UC_X86_REG_DI,UC_X86_REG_BP,
    UC_X86_REG_CS,UC_X86_REG_DS,UC_X86_REG_ES,UC_X86_REG_SS,UC_X86_REG_SP,UC_X86_REG_IP,UC_X86_REG_EFLAGS)
HUD=((0x206e,30),(0x79b3,47),(0x1aae,7),(0x1afa,2))
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def generate(executable,capture,out):
    assert unicorn.__version__=='2.1.4';out=out.resolve();assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
    raw=executable.read_bytes();assert sha(raw)=='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    mz=struct.unpack_from('<14H',raw);image=bytearray(raw[0x770:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',raw,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    recipe=json.loads((capture/'report.json').read_bytes());sample=next(item for item in recipe['samples'] if item['name']=='gameplay-middle')
    reference=gzip.decompress((capture/'gameplay-middle.ram.gz').read_bytes());assert len(reference)==1048576 and sha(reference)==sample['ram_sha256']
    data=recipe['data_segment']*16;fontBase=struct.unpack_from('<H',reference,data+0x2070)[0];font=reference[data+fontBase:data+fontBase+640]
    profiles=[(2,2,17,3,3,50,0,0,False),(2,1,17,3,3,50,0,0,False),(2,2,17,3,2,50,0,0,False),
        (2,1,17,3,2,50,0,0,False),(17,16,17,50,49,50,0,0,False),(2,1,17,3,2,50,1,0,False),
        (2,1,17,3,2,50,2,0,False),(2,1,17,3,2,50,2,0x400,False),(2,2,17,3,3,50,0,0x400,False),
        (2,1,17,3,2,50,0,0,True)]
    for required in (0,1,99,100,32767,32768,65535):
        profiles.append((0,1,required,0,0,50,0,0,False))
    out.mkdir();output=bytearray(b'LZHUDOR1'+struct.pack('<I',len(profiles)));cases=[]
    def slices(memory):
        return bytes(memory[0x8fdb0:0x8fdb0+128])+b''.join(bytes(memory[0x1aa20+at:0x1aa20+at+size]) for at,size in HUD)
    def pixels(memory):
        return bytes(memory[0xa0000+(166+block*16+row)*320+159+x] for block in range(2) for row in range(8) for x in range(17))
    for index,(current,cached,required,byteCurrent,byteCached,byteRequired,count,direction,error) in enumerate(profiles):
        initial=bytearray(1048576);initial[0x10000:0x10000+len(image)]=image
        for at,size in HUD:
            initial[0x1aa20+at:0x1aa20+at+size]=bytes(size)
        for at,value in [(0x2070,40000),(0x2074,120),(0x2088,current),(0x208a,cached),(0x2086,required),(0x1afa,65535 if error else 0)]:
            struct.pack_into('<H',initial,0x1aa20+at,value)
        for at,value in [(0x79b5,byteCurrent),(0x79b6,byteCached),(0x79b3,byteRequired),(0x79cb,count),(0x79ce,245),(0x79cf,246)]:
            initial[0x1aa20+at]=value
        initial[0x1aa20+0x1aae:0x1aa20+0x1ab5]=bytes([4,8,12,99,16,20,24])
        initial[0x1aa20+40000:0x1aa20+40640]=font
        initial[0x8fdb0:0x8fdb0+128]=bytes((index+i)&255 for i in range(128));struct.pack_into('<2H',initial,0x8fe00,0x7a00,0xcb0f)
        for block in range(2):
            for row in range(8):
                for x in range(17):
                    initial[0xa0000+(166+block*16+row)*320+159+x]=(index+row+x)&255
        values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x9abc,0x1000,0x1aa2,0xbeef,0x8000,0xfe00,0x3184,0x202|direction)
        endpoints=[]
        for observed in (True,False):
            engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16);engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
            for register,value in zip(REGS,values):
                engine.reg_write(register,value)
            def interrupt(*unused):
                raise RuntimeError('Original HUD unexpectedly called an interrupt')
            engine.hook_add(unicorn.UC_HOOK_INTR,interrupt)
            if observed:
                engine.hook_add(unicorn.UC_HOOK_CODE,lambda *unused:None)
            end=0x192e2 if error else 0x17a00
            engine.emu_start(0x13184,end,count=100000)
            registers=[engine.reg_read(register) for register in REGS];memory=bytes(engine.mem_read(0,1048576))
            assert registers[12]==(0xe2 if error else 0x7a00) and memory[0x10000:0x10000+43552]==image[:43552]
            endpoints.append((registers,memory))
        assert endpoints[0]==endpoints[1];registers,memory=endpoints[0]
        output.extend(struct.pack('<B13HI',int(error),*values[:-1],values[-1])+slices(initial)+font+pixels(initial))
        output.extend(struct.pack('<13HI',*registers[:-1],registers[-1])+slices(memory)+pixels(memory))
        cases.append(dict(index=index,profile=list(profiles[index]),full_endpoint_flags=True,full_memory_control_identical=True))
    compressed=gzip.compress(output,mtime=0);(out/'oracle.bin.gz').write_bytes(compressed);(out/'oracle.bin').write_bytes(output)
    record=dict(cases=cases,producer_sha256=sha(Path(__file__).read_bytes()),original_executable_sha256=sha(raw),
        source_ram_sha256=sha(reference),font_sha256=sha(font),projection_sha256=sha(output),projection_bytes=len(output),
        compressed_sha256=sha(compressed),compressed_bytes=len(compressed),original_calls_stubbed=0,instruction_patches=0,
        source_code_bytes_verified=43552,natural_gameplay_claim=False,unicorn=unicorn.__version__)
    (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();generate(args.exe,args.capture,args.out)
