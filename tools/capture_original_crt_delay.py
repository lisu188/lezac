"""Controlled unchanged-original CRT delay execution; no natural-clock claim."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import unicorn
from unicorn.x86_const import (UC_X86_INS_IN, UC_X86_INS_OUT, UC_X86_REG_AX,
    UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX, UC_X86_REG_DI, UC_X86_REG_BP,
    UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS,
    UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--provider', choices=['memory', 'instruction'], default='memory')
args = parser.parse_args()
root = args.root
out = args.out
out.mkdir()
sha = lambda raw: hashlib.sha256(raw).hexdigest()
assert unicorn.__version__ == '2.1.4'
raw = (root / 'LEZAC.EXE').read_bytes()
assert sha(raw) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
header = struct.unpack_from('<14H', raw)
assert header[3] == 468 and header[4] * 16 == 0x770
image = bytearray(raw[0x770:])
for index in range(header[3]):
    offset, segment = struct.unpack_from('<HH', raw, header[12] + index * 4)
    at = segment * 16 + offset
    struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
registers = dict(ax=UC_X86_REG_AX, bx=UC_X86_REG_BX, cx=UC_X86_REG_CX,
    dx=UC_X86_REG_DX, di=UC_X86_REG_DI, bp=UC_X86_REG_BP, cs=UC_X86_REG_CS,
    ds=UC_X86_REG_DS, es=UC_X86_REG_ES, ss=UC_X86_REG_SS, sp=UC_X86_REG_SP,
    ip=UC_X86_REG_IP, flags=UC_X86_REG_EFLAGS)
initial = dict(ax=0x1234, bx=0x2345, cx=0x3456, dx=0x4567, di=0x6789, bp=0x789a,
               cs=0x1000, ds=0x1aa2, es=0x5678, ss=0x8000, sp=0xfe06, flags=0x202)
cases = [('zero', 0, [544], [248]), ('one_c1', 1, [1], [248]),
         ('one_c2', 1, [2], [248]), ('two_c2', 2, [2], [248]),
         ('zero_calibration_wrap', 1, [0], [248]), ('maximum_calibration', 1, [65535], [248]),
         ('captured16', 16, [544], [248]), ('captured81', 81, [544], [248]),
         ('captured82', 82, [544], [248]), ('changed_first_compare', 2, [544], [248, 249]),
         ('changed_fifth_compare', 2, [544], [248] * 5 + [249]),
         ('changed_then_restored', 2, [544], [248, 249, 248]),
         ('calibration_reloaded', 3, [2, 1, 0], [248]),
         ('startup500', 500, [544], [248]), ('startup1000', 1000, [544], [248]),
         ('maximum_argument_c1', 65535, [1], [248]),
         ('changed_lower_compare', 1, [544], [248, 247])]
checkpoints = set(range(41)) | {64,100,200,500,1000,5000,10000,50000,100000,500000,700000,
                               524294,524295,524296}
results = []
try:
    for name, argument, calibration, com1 in cases:
        cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
        cpu.mem_map(0, 1024**2)
        cpu.mem_write(0x10000, bytes(image))
        for register, value in initial.items():
            cpu.reg_write(registers[register], value)
        cpu.mem_write(0x1aa20 + 0x78cc, struct.pack('<H', argument))
        state = dict(dispatch=0, calibration_reads=0, com1_reads=0, defined_flags=0xffffffff)
        snapshots = []
        def snapshot():
            return dict(dispatch=state['dispatch'], calibration_reads=state['calibration_reads'],
                com1_reads=state['com1_reads'], registers={key: cpu.reg_read(value) for key, value in registers.items()},
                stack_window=bytes(cpu.mem_read(0x8fdfe, 8)).hex(' '),
                defined_flags_hex=f"{state['defined_flags']:08x}")
        def instruction(cpu, address, size, user):
            state['last_hook_address'] = address
            if address == 0x179e8:
                cpu.emu_stop()
                return
            if address in (0x179df, 0x179e3):
                return
            if not 0x1873c <= address < 0x18769:
                raise ValueError('Execution left original boundary: ' + hex(address))
            if state['dispatch'] in checkpoints:
                snapshots.append(snapshot())
            state['dispatch'] += 1
            if address in (0x18742, 0x1874b):
                state['defined_flags'] &= ~0x10
            elif address in (0x18757, 0x18760, 0x18763):
                state['defined_flags'] = 0xffffffff
            if args.provider == 'instruction':
                if address == 0x18750:
                    memory_read(cpu, 0, 0x22988, 2, 0, None)
                elif address in (0x1874d, 0x18763):
                    memory_read(cpu, 0, 0x400, 1, 0, None)
        def memory_read(cpu, access, address, size, value, user):
            if address == 0x1aa20 + 0x7f68:
                index = state['calibration_reads']
                state['calibration_reads'] += 1
                cpu.mem_write(address, struct.pack('<H', calibration[min(index, len(calibration)-1)]))
            elif address == 0x400:
                index = state['com1_reads']
                state['com1_reads'] += 1
                cpu.mem_write(address, bytes([com1[min(index, len(com1)-1)]]))
        def memory_write(cpu, access, address, size, value, user):
            if address < 0x10000 + 43552 and address + size > 0x10000:
                raise ValueError('Original code write is forbidden')
        def forbidden(*args):
            raise ValueError('Unexpected original interrupt or port I/O')
        cpu.hook_add(unicorn.UC_HOOK_CODE, instruction)
        if args.provider == 'memory':
            cpu.hook_add(unicorn.UC_HOOK_MEM_READ, memory_read, None, 0x400, 0x400)
            cpu.hook_add(unicorn.UC_HOOK_MEM_READ, memory_read, None, 0x22988, 0x22988)
        cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory_write)
        cpu.hook_add(unicorn.UC_HOOK_INTR, forbidden)
        cpu.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_IN)
        cpu.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_OUT)
        cpu.emu_start(0x179df, 0x179e8, count=10000000)
        final = snapshot()
        assert final['registers']['cs'] == 0x1000 and final['registers']['ip'] == 0x79e8, final
        assert final['registers']['sp'] == 0xfe06
        assert bytes(cpu.mem_read(0x10000, 43552)) == image[:43552]
        snapshots.append(final)
        result = dict(name=name, argument=argument,
            calibration_inputs=[dict(value=value) for value in calibration],
            com1_inputs=[dict(value=value) for value in com1],
            dispatches=state['dispatch'], calibration_reads=state['calibration_reads'],
            com1_reads=state['com1_reads'], snapshots=snapshots)
        results.append(result)
        (out / (name + '.json')).write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({key: value for key, value in result.items() if key != 'snapshots'}), flush=True)
    manifest = dict(original_executable_sha256=sha(raw), producer_sha256=sha(Path(__file__).read_bytes()),
        unicorn=unicorn.__version__, entry_cs=0x184a, entry_ip=0x29c,
        original_caller_entry_ip=0x79df, original_caller_return_ip=0x79e8,
        original_caller_instructions_executed=2,
        routine_sha256=sha(image[0x873c:0x8769]), original_code_bytes_verified=43552,
        original_calls_stubbed=False, original_instruction_patches=0, hardware_interrupts_injected=0,
        inputs_seeded=True, calibration_and_com1_reads_scripted=True,
        data_input_writes_declared=True, natural_clock_claim=False, cycle_clock_claim=False,
        input_provider=args.provider,
        read_hook_ranges=[[0x400, 0x400], [0x22988, 0x22988]] if args.provider == 'memory' else [],
        stack_window_address=0x8fdfe, stack_window_bytes=8,
        undefined_logic_auxiliary_flag_unclaimed=True,
        full_game_parity=False, initial_registers=initial, cases=results)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    assert sum(path.stat().st_size for path in out.iterdir()) < 2 * 1024**2
    print('original_crt_delay=ok cases=17 original_calls_stubbed=0 natural_clock=0')
except BaseException as error:
    (out / 'failure.json').write_text(json.dumps(dict(error=repr(error), name=name,
        partial_snapshots=snapshots, final=snapshot()), indent=2) + '\n')
    raise
