"""Capture seeded calls to the unchanged original level decoder, not gameplay."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

import unicorn
from unicorn import x86_const as x86
from original_bomb_cpu import BombCPU, EXE_SHA, LEVELS_SHA


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def capture(root):
    loader = BombCPU(root)
    initial = loader.initial_memory
    data, source, destination = loader.DATA, 0x40000, 0x60000
    decoder = 0x182d0
    registers = {name: getattr(x86, 'UC_X86_REG_' + name) for name in
                 ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')}
    cases = []

    def execute(name, target, encoded, buffer):
        before_buffer = bytes(buffer)
        buffer[:len(encoded)] = encoded
        seeded = bytearray(initial)
        seeded[source:source + 60000] = buffer
        seeded[destination:destination + 65536] = bytes(65536)
        struct.pack_into('<HH', seeded, data + 0xc498, 0, source >> 4)
        struct.pack_into('<HH', seeded, data + 0x6612, 0, destination >> 4)
        struct.pack_into('<8H', seeded, 0x83f00, 0xff00, 0x1000, target,
                         0x6612, 0x1aa2, len(encoded), 0xc498, 0x1aa2)
        before = bytes(seeded)
        results = []

        def forbidden(*unused):
            raise RuntimeError('original decoder reached hardware I/O or an interrupt')

        for observe in (True, False):
            cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
            cpu.mem_map(0, 1048576)
            cpu.mem_write(0, before)
            values = dict(AX=0, BX=0, CX=0, DX=0, SI=0, DI=0, BP=0xf000,
                          SP=0x3f00, CS=0x182d, DS=0x1aa2, ES=0, SS=0x8000, IP=0, EFLAGS=0x202)
            for register, value in values.items():
                cpu.reg_write(registers[register], value)
            cpu.hook_add(unicorn.UC_HOOK_INTR, forbidden)
            for instruction in (x86.UC_X86_INS_IN, x86.UC_X86_INS_OUT):
                cpu.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, instruction)
            writes = {}

            def write(uc, access, address, size, value, user):
                if destination <= address < destination + 65536:
                    assert size == 1 and uc.reg_read(registers['IP']) in (0x9c, 0xed)
                    writes[address - destination] = value

            if observe:
                cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
            cpu.emu_start(decoder, 0x1ff00, count=2000000)
            regs = {name: cpu.reg_read(register) for name, register in registers.items()}
            assert (regs['CS'], regs['IP'], regs['BP'], regs['SP']) == (0x1000, 0xff00, 0xf000, 0x3f10)
            after = bytes(cpu.mem_read(0, 1048576))
            assert after[0x10000:0x1aa20] == before[0x10000:0x1aa20]
            results.append((after, regs, writes))
        assert results[0][:2] == results[1][:2]
        after, regs, writes = results[0]
        written_end = max(writes) + 1
        assert set(writes) == set(range(written_end)) and target < written_end <= target + 16
        output = after[destination:destination + 65536]
        assert not any(output[written_end:])
        case = dict(name=name, target=target, encoded_hex=encoded.hex(),
                    buffer_before_hex=before_buffer.hex(), output_hex=output[:written_end].hex(),
                    tail_bytes=written_end - target, before_ram_sha256=sha(before),
                    after_ram_sha256=sha(after), registers=regs, full_ram_and_register_observer_match=True)
        cases.append(case)
        print(json.dumps(dict(case=name, target=target, tail=output[target:written_end].hex())), flush=True)

    raw = (root / 'LIVELS.SCH').read_bytes()
    cursor, buffer = 0, bytearray(60000)
    for level in range(1, 8):
        width, height = struct.unpack_from('<HH', raw, cursor)
        cursor += 8
        for plane, target in (('objects', width * height), ('words', 2 * width * height)):
            size, = struct.unpack_from('<H', raw, cursor)
            cursor += 2
            encoded = raw[cursor:cursor + size]
            cursor += size
            execute('level' + str(level) + '_' + plane, target, encoded, buffer)
        cursor += 4
        for stride in (30, 7, 14):
            count = raw[cursor]
            cursor += 1 + count * stride
    assert cursor == len(raw)
    for target in (1, 15, 16, 17, 31, 32, 33):
        execute('boundary_' + str(target), target, bytes.fromhex('ff7b9a') * 2, bytearray([0xce]) * 60000)
    execute('second_run_max_tail', 2, bytes.fromhex('0f1728'), bytearray(60000))
    assert len(cases) == 22
    return dict(format='lezac-level-rle-tail-v1', original_exe_sha256=EXE_SHA,
                levels_sha256=LEVELS_SHA, unicorn_version=unicorn.__version__,
                decoder_file_offset=0x8a40, decoder_bytes=0x111,
                seeded_calls=True, original_instructions_patched=False,
                interrupt_or_io_stubs=False, memory_read_hooks=False,
                natural_gameplay=False, whole_game_complete=False, cases=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if sys.flags.optimize or args.out.exists():
        raise RuntimeError('requires unoptimized Python and a new output path')
    report = capture(args.root)
    raw = json.dumps(report, sort_keys=True, separators=(',', ':')).encode() + b'\n'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(gzip.compress(raw, mtime=0))
    print(json.dumps(dict(passed=True, cases=len(report['cases']), bytes=args.out.stat().st_size,
                          sha256=sha(args.out.read_bytes()), natural_gameplay=False)), flush=True)


if __name__ == '__main__':
    main()
