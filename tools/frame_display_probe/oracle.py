"""Execute unchanged software Real48 display calls with explicit controlled inputs."""
import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import struct

import unicorn
from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX,
    UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES,
    UC_X86_REG_SS, UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS, UC_X86_INS_IN, UC_X86_INS_OUT)

CS, DS, SS, SP, BASE = 0x1000, 0x1aa2, 0x8000, 0xfe06, 0xfdb6
REGISTERS = (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX, UC_X86_REG_SI, UC_X86_REG_DI,
    UC_X86_REG_BP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_SP)
ARITHMETIC = 0x8d5
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def next_mask(mask, opcode, cl):
    first = opcode[0]
    if first in (0x02, 0x03, 0x05, 0x12, 0x13, 0x1a, 0x1b, 0x2a, 0x2b, 0x3a, 0x3b, 0x3c):
        return mask | ARITHMETIC
    if first in (0x0a, 0x0b, 0x31, 0x32, 0x33):
        return (mask | ARITHMETIC) & ~0x10
    if first in (0x80, 0x81, 0x83):
        group = (opcode[1] >> 3) & 7
        return (mask | ARITHMETIC) & (~0x10 if group in (1, 4, 6) else 0xffffffff)
    if first in (0x41, 0x49, 0xfe):
        return mask | (ARITHMETIC & ~1)
    if first in (0xf6, 0xf7):
        group = (opcode[1] >> 3) & 7
        if group == 0:
            return (mask | ARITHMETIC) & ~0x10
        if group == 4:
            return (mask & ~ARITHMETIC) | 0x801
    if first in (0xd0, 0xd1, 0xd3):
        group = (opcode[1] >> 3) & 7
        count = (cl & 31) if first == 0xd3 else 1
        if count:
            if group in (2, 3):
                return mask | 0x801
            return (mask | ARITHMETIC) & ~(0x10 | (0x800 if count > 1 else 0))
    if first in (0xf8, 0xf9):
        return mask | 1
    return mask


def capture(executable, out, exhaustive):
    assert unicorn.__version__ == '2.1.4'
    out = out.resolve()
    assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
    original = executable.read_bytes()
    assert sha(original) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    mz = struct.unpack_from('<14H', original)
    assert mz[4] * 16 == 0x770 and mz[3] == 468
    image = bytearray(original[0x770:])
    for index in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', original, mz[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + CS) & 65535)
    def forbidden(*unused):
        raise RuntimeError('Unexpected interrupt or hardware I/O inside software Real48 phase')
    def emulator():
        cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
        cpu.mem_map(0, 1048576)
        cpu.mem_write(CS * 16, bytes(image))
        cpu.hook_add(unicorn.UC_HOOK_INTR, forbidden)
        cpu.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_IN)
        cpu.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_OUT)
        return cpu
    cpu, control_cpu = emulator(), emulator()
    baselines = {id(engine): engine.context_save() for engine in (cpu, control_cpu)}
    def initialize(engine, denominator, numerator, index):
        engine.context_restore(baselines[id(engine)])
        values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x9abc, CS, DS, 0xbeef, SS, SP)
        for register, value in zip(REGISTERS, values):
            engine.reg_write(register, value)
        engine.reg_write(UC_X86_REG_IP, 0x7966)
        engine.reg_write(UC_X86_REG_EFLAGS, 0x202 | (0x400 if index % 3 == 0 else 0) | (ARITHMETIC if index % 2 else 0))
        engine.mem_write(DS * 16 + 0x78c6, struct.pack('<2H', denominator, numerator))
        engine.mem_write(DS * 16 + 0x79b5, b'\x5a')
        engine.mem_write(SS * 16 + BASE, bytes((index + i) & 255 for i in range(128)))
    def state(engine, address, mask):
        ip = address - engine.reg_read(UC_X86_REG_CS) * 16
        return struct.pack('<13H2I', *[engine.reg_read(r) for r in REGISTERS], ip,
            engine.reg_read(UC_X86_REG_EFLAGS), mask) + bytes(engine.mem_read(SS * 16 + BASE, 128)) + \
            bytes(engine.mem_read(DS * 16 + 0x78c6, 4)) + bytes(engine.mem_read(DS * 16 + 0x79b5, 1))
    domain = (0, 1, 2, 3, 7, 66, 99, 100, 127, 128, 255, 256, 257, 32767, 32768, 65535)
    pairs = list(itertools.product(domain, domain))
    projection = bytearray(b'LZFDIR01' + struct.pack('<I5H', len(pairs), CS, DS, SS, BASE, 128))
    no_read_hook_records = bytearray()
    unique = set()
    instruction_counts = []
    out.mkdir()
    (out / 'producer.py').write_bytes(Path(__file__).read_bytes())
    states, mask = [], 0xffffffff
    def decoded(engine, address, size, unused):
        nonlocal mask
        assert address < CS * 16 + 43552
        states.append(state(engine, address, mask))
        opcode = bytes(engine.mem_read(address, size))
        unique.add((engine.reg_read(UC_X86_REG_CS) - CS, address - engine.reg_read(UC_X86_REG_CS) * 16))
        mask = next_mask(mask, opcode, engine.reg_read(UC_X86_REG_CX) & 255)
    # Separate engines keep the observer installed permanently and avoid stale hook-free translations.
    cpu.hook_add(unicorn.UC_HOOK_CODE, decoded)
    for index, (denominator, numerator) in enumerate(pairs):
        initialize(cpu, denominator, numerator, index)
        terminal = (CS + 0x920) * 16 + 0xe2 if denominator == 0 else CS * 16 + 0x799a
        states = []
        mask = 0xffffffff
        cpu.emu_start(CS * 16 + 0x7966, terminal, count=4096)
        actual_address = cpu.reg_read(UC_X86_REG_CS) * 16 + cpu.reg_read(UC_X86_REG_IP)
        assert actual_address == terminal and 0 < len(states) < 4096
        assert struct.unpack_from('<13H', states[0])[12] == 0x7966
        states.append(state(cpu, terminal, mask))
        projection.extend(struct.pack('<HHBI', denominator, numerator, denominator == 0, len(states)))
        projection.extend(b''.join(states))
        instruction_counts.append(len(states) - 1)
        observed = states[-1]
        # A separate run without any instruction or memory-read observer must agree.
        initialize(control_cpu, denominator, numerator, index)
        control_cpu.emu_start(CS * 16 + 0x7966, terminal, count=4096)
        assert control_cpu.reg_read(UC_X86_REG_CS) * 16 + control_cpu.reg_read(UC_X86_REG_IP) == terminal
        control = state(control_cpu, terminal, mask)
        assert control == observed
        no_read_hook_records.extend(control)
    assert bytes(cpu.mem_read(CS * 16, 43552)) == image[:43552]
    (out / 'instructions.bin.gz').write_bytes(gzip.compress(projection, mtime=0))
    endpoints = bytearray(b'LZFDEN01' + struct.pack('<I', 196608 if exhaustive else 0))
    if exhaustive:
        for denominator in (1, 66, 65535):
            for numerator in range(65536):
                initialize(control_cpu, denominator, numerator, numerator)
                control_cpu.emu_start(CS * 16 + 0x7966, CS * 16 + 0x799a, count=4096)
                assert (control_cpu.reg_read(UC_X86_REG_CS), control_cpu.reg_read(UC_X86_REG_IP)) == (CS, 0x799a)
                endpoints.extend(struct.pack('<2H', denominator, numerator))
                endpoints.extend(state(control_cpu, CS * 16 + 0x799a, 0xffffffff))
            print(json.dumps(dict(exhaustive_denominator=denominator, numerator_inputs=65536)), flush=True)
    assert bytes(cpu.mem_read(CS * 16, 43552)) == image[:43552]
    assert bytes(control_cpu.mem_read(CS * 16, 43552)) == image[:43552]
    (out / 'endpoints.bin.gz').write_bytes(gzip.compress(endpoints, mtime=0))
    record = dict(schema='lezac-controlled-frame-display-v1', original_executable_sha256=sha(original),
        producer_sha256=sha(Path(__file__).read_bytes()), unicorn=unicorn.__version__, instruction_cases=len(pairs),
        instruction_states=sum(count + 1 for count in instruction_counts),
        minimum_instructions=min(instruction_counts), maximum_instructions=max(instruction_counts),
        reached_original_runtime_error_cases=sum(denominator == 0 for denominator, _ in pairs),
        isolated_phase='game:7966..799a plus original software Real48 calls',
        instruction_patches=0, original_calls_stubbed=False, initial_cpu_memory_inputs_seeded=True,
        runtime_error_observation_stops_before='library:00e2', natural_gameplay_claim=False,
        full_memory_read_hooks=False, instruction_observer_matches_unobserved_endpoints=True,
        unobserved_control_sha256=sha(no_read_hook_records), code_bytes_unchanged=43552,
        exhaustive_denominators=[1, 66, 65535] if exhaustive else [], exhaustive_numerator_inputs=65536 if exhaustive else 0,
        endpoint_cases=196608 if exhaustive else 0, projection_bytes=len(projection), projection_sha256=sha(projection),
        endpoints_bytes=len(endpoints), endpoints_sha256=sha(endpoints),
        unique_instructions=[dict(relative_cs=segment, ip=ip) for segment, ip in sorted(unique)])
    (out / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({key:value for key,value in record.items() if key != 'unique_instructions'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--exhaustive', action='store_true')
    args = parser.parse_args()
    capture(args.exe, args.out, args.exhaustive)
