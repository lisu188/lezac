"""Execute unchanged game:791E..7966 for controlled elapsed-time inputs."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import struct

import unicorn
from unicorn.x86_const import (UC_X86_REG_AX,UC_X86_REG_BX,UC_X86_REG_CX,UC_X86_REG_DX,
    UC_X86_REG_SI,UC_X86_REG_DI,UC_X86_REG_BP,UC_X86_REG_CS,UC_X86_REG_DS,UC_X86_REG_ES,
    UC_X86_REG_SS,UC_X86_REG_SP,UC_X86_REG_IP,UC_X86_REG_EFLAGS)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--exe',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args = parser.parse_args()
assert args.out.is_relative_to(Path('/dev/shm')) and not args.out.exists()
original = args.exe.read_bytes()
sha = lambda raw:hashlib.sha256(raw).hexdigest()
assert sha(original) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
mz = struct.unpack_from('<14H',original)
image = bytearray(original[mz[4]*16:])
cs,ds,ss,sp,stack_base = 0x1000,0x1aa2,0x8000,0xfe06,0xfdb6
for index in range(mz[3]):
    offset,segment = struct.unpack_from('<HH',original,mz[12]+4*index)
    at = segment*16+offset
    struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+cs)&65535)
registers = (UC_X86_REG_AX,UC_X86_REG_BX,UC_X86_REG_CX,UC_X86_REG_DX,UC_X86_REG_SI,UC_X86_REG_DI,
    UC_X86_REG_BP,UC_X86_REG_CS,UC_X86_REG_DS,UC_X86_REG_ES,UC_X86_REG_SS,UC_X86_REG_SP,UC_X86_REG_IP)
expected_ips = [0x791e,0x7922,0x7926,0x792a,0x792d,0x792f,0x7930,0x7933,0x7935,0x7937,
    0x793a,0x793c,0x793e,0x7941,0x7943,0x7945,0x7948,0x794a,0x794d,0x794f,0x7951,0x7954,
    0x7956,0x7958,0x795c,0x795e,0x7960,0x7961,0x7963]
cpu = unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
cpu.mem_map(0,1048576)
cpu.mem_write(cs*16,bytes(image))
ips = []
def decoded(cpu,address,size,user):
    assert cs*16+0x791e <= address < cs*16+0x7966
    ips.append(address-cs*16)
def forbidden(*unused):
    raise RuntimeError('Interrupt outside isolated arithmetic phase')
cpu.hook_add(unicorn.UC_HOOK_CODE,decoded)
cpu.hook_add(unicorn.UC_HOOK_INTR,forbidden)
def state():
    return struct.pack('<13HI',*[cpu.reg_read(register) for register in registers],cpu.reg_read(UC_X86_REG_EFLAGS))
def memory():
    return bytes(cpu.mem_read(ds*16+0x2074,2))+bytes(cpu.mem_read(ds*16+0x79a4,9))
cases = list(itertools.product((0,1,59),(0,1,59),(0,1,99),(0,1,59,99,255),(0,1,59,99,255),(0,1,59,99,255)))
output = bytearray(b'LZFEL001'+struct.pack('<I5H',len(cases),cs,ds,ss,stack_base,128))
for index,(minute,second,hundredth,old_minute,old_second,old_hundredth) in enumerate(cases):
    initial = (0x2c00,0x5a5a,((index%24)<<8)|minute,(second<<8)|hundredth,
        0x1234,0x5678,0x9abc,cs,ds,0xbeef,ss,sp,0x791e)
    for register,value in zip(registers,initial):
        cpu.reg_write(register,value)
    cpu.reg_write(UC_X86_REG_EFLAGS,0x202|(0x400 if index%3==0 else 0)|(0x8d5 if index%2 else 0))
    cpu.mem_write(ds*16+0x2074,b'\xef\xbe')
    cpu.mem_write(ds*16+0x79a4,bytes((old_minute,0xa5,0x5a,0xa5,old_second,old_hundredth,0xff,0xff,0xff)))
    cpu.mem_write(ss*16+stack_base,bytes((i+index)&255 for i in range(128)))
    output.extend(state()+memory()+bytes(cpu.mem_read(ss*16+stack_base,128)))
    ips.clear()
    cpu.emu_start(cs*16+0x791e,cs*16+0x7966,count=30)
    assert ips == expected_ips and cpu.reg_read(UC_X86_REG_IP)==0x7966
    assert cpu.reg_read(UC_X86_REG_SP)==sp
    output.extend(state()+memory()+bytes(cpu.mem_read(ss*16+stack_base,128)))
assert bytes(cpu.mem_read(cs*16,43552))==image[:43552]
args.out.mkdir()
(args.out/'projection.bin').write_bytes(output)
record = dict(schema='lezac-controlled-frame-elapsed-isa-v1',cases=len(cases),instructions_per_case=29,
    original_executable_sha256=sha(original),unicorn=unicorn.__version__,instruction_patches=0,original_calls_stubbed=False,
    isolated_phase='game:791e..7966',natural_gameplay_claim=False,whole_function_or_game_claim=False,
    initial_cpu_memory_inputs_seeded=True,projection_bytes=len(output),projection_sha256=sha(output),
    producer_sha256=sha(Path(__file__).read_bytes()),code_bytes_unchanged=43552)
(args.out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
