"""Execute the unchanged original start locator on controlled portal tables."""
import argparse
import gzip
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT
from frame_camera_oracle import REGS, EXE_SHA, LIB_SHA, sha


def profiles():
    result = []
    for marker in (1, 2):
        for flags in range(256):
            for key in (0, 0x1234):
                result.append((marker, [(key, 104 + flags, 168 + flags, flags)], 0x200, 0x3fe0, 0))
        for portals in ([], [(9, 111, 222, marker ^ 3)],
                [(0, 11, 22, 0), (7, 333, 444, marker), (0, 555, 666, marker)],
                [(9, 777, 888, marker), (0, 999, 1111, marker)],
                [(65535, 0, 0, 3)], [(65535, 65535, 65535, 3)],
                [(65535, 32768, 32767, 3)], [(65535, 17, 24, 3)]):
            result.append((marker, portals, 0x200, 0x3fe0, 0))
    for floor, sp in ((0x4000, 0x3fe0), (0x200, 0x210), (0x3dcf, 0x3fe0)):
        result.append((1, [(0, 104, 168, 1)], floor, sp, 1))
    return result


def generate(root, out):
    if unicorn.__version__ != '2.1.4' or any(k in os.environ for k in ('LD_PRELOAD', 'LIBUNICORN_PATH')):
        raise ValueError('Unsupported Unicorn loader profile')
    library = Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes()) != LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual Unicorn library mapping differs')
    exe = (root / 'LEZAC.EXE').read_bytes()
    if sha(exe) != EXE_SHA:
        raise ValueError('Original executable differs')
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[mz[4] * 16:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + i * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output directory')
    out.mkdir()
    cases = profiles()
    output = bytearray(b'LZSTART1' + struct.pack('<I', len(cases)))
    app = bytearray(b'LZSTAPP1' + struct.pack('<I', len(cases) - 3))
    coverage, states, write_count = set(), 0, 0
    try:
        for index, (marker, portals, floor, sp, error) in enumerate(cases):
            initial = bytearray(1048576)
            initial[0x10000:0x10000 + len(image)] = image
            stack = 0x70000 + sp - 96
            initial[stack:stack + 112] = bytes((i * 29 + index * 7 + 11) & 255 for i in range(112))
            actor, visual = 0x1b88 + (marker - 1) * 38, 0xc21e + (marker - 1) * 8
            initial[0x1aa20 + actor:0x1aa20 + actor + 38] = bytes((i * 11 + index * 7 + 19) & 255 for i in range(38))
            initial[0x1aa20 + actor + 1] = marker - 1
            initial[0x1aa20 + visual:0x1aa20 + visual + 8] = bytes((i * 13 + index * 3 + 7) & 255 for i in range(8))
            initial[0x1aa20 + 0x79a5] = len(portals)
            struct.pack_into('<H', initial, 0x1aa20 + 0x1afa, floor)
            records = b''.join(struct.pack('<3HB', *portal) for portal in portals)
            initial[0x1aa20 + 0x771e:0x1aa20 + 0x771e + len(records)] = records
            struct.pack_into('<4H', initial, 0x70000 + sp, 0x7d23, 0x7b00 | marker, actor, 0x1aa2)
            values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                      0x1000, 0x1aa2, 0x40, 0x7000, sp, 0x56b, 0x602 if index % 2 else 0x202)
            trace, writes, endpoints = [], [], []
            until = 0x192e2 if error else 0x17d23
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for reg, value in zip(REGS, values):
                    engine.reg_write(reg, value)
                def external(*unused):
                    raise ValueError('Start locator crossed an unmodeled interrupt or I/O')
                def code(uc, address, size, user):
                    registers = tuple(uc.reg_read(reg) for reg in REGS)
                    if not (registers[7] == 0x1000 and 0x56b <= registers[12] < 0x625 or
                            registers[7] == 0x1920 and 0x4df <= registers[12] < 0x4f7):
                        raise ValueError('Start locator left declared original code')
                    coverage.add((registers[7], registers[12]))
                    trace.append(registers)
                def write(uc, access, address, size, value, user):
                    allowed = stack <= address and address + size <= stack + 112 or \
                        size == 1 and address == 0x1aa20 + actor + 2 or \
                        size == 2 and address in (0x1aa20 + visual, 0x1aa20 + visual + 2)
                    if size not in (1, 2) or not allowed:
                        raise ValueError('Start locator wrote outside stack/actor/visual owners')
                    writes.append((address, size, value & ((1 << (size * 8)) - 1)))
                engine.hook_add(unicorn.UC_HOOK_INTR, external)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                engine.emu_start(0x1056b, until, count=10000)
                registers = tuple(engine.reg_read(reg) for reg in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                if registers[7] * 16 + registers[12] != until or final[0x10000:0x1aa20] != image[:0xaa20]:
                    raise ValueError('Start locator endpoint or original code differs')
                endpoints.append((registers, final))
            if endpoints[0] != endpoints[1]:
                raise ValueError('Start observer affected complete memory/registers')
            registers, final = endpoints[0]
            reconstructed = bytearray(initial)
            for address, size, value in writes:
                reconstructed[address:address + size] = value.to_bytes(size, 'little')
            if reconstructed != final:
                raise ValueError('Ordered writes do not reconstruct complete final memory')
            trace.append(registers)
            states += len(trace)
            write_count += len(writes)
            output.extend(struct.pack('<6H', index, marker, len(portals), floor, sp, error))
            output.extend(records)
            output.extend(struct.pack('<13HI13HI', *values, *registers))
            output.extend(struct.pack('<I', len(trace)))
            for row in trace:
                output.extend(struct.pack('<13HI', *row))
            output.extend(struct.pack('<I', len(writes)))
            for row in writes:
                output.extend(struct.pack('<IBH', *row))
            if not error:
                x, y = struct.unpack_from('<2H', final, 0x1aa20 + visual)
                if final[0x1aa20 + actor + 2] != 0:
                    raise ValueError('Original locator did not clear idle byte')
                app.extend(struct.pack('<5H', index, marker, len(portals), x, y))
                app.extend(records)
        raw = bytes(output)
        compressed = gzip.compress(raw, mtime=0)
        (out / 'oracle.bin.gz').write_bytes(compressed)
        (out / 'app.bin').write_bytes(app)
        manifest = dict(schema='lezac-controlled-player-start-v1', executable_sha256=EXE_SHA,
            producer_sha256=sha(Path(__file__).read_bytes()),
            shared_oracle_sha256=sha((root / 'tools/frame_camera_oracle.py').read_bytes()),
            unicorn_version=unicorn.__version__, unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True, cases=len(cases), app_cases=len(cases)-3,
            register_states=states, writes=write_count, runtime_errors=3,
            executed_instructions=[list(pair) for pair in sorted(coverage)],
            projection_bytes=len(raw), projection_sha256=sha(raw),
            compressed_bytes=len(compressed), compressed_sha256=sha(compressed),
            app_bytes=len(app), app_sha256=sha(app), original_code_bytes_verified=43552,
            complete_memory_observer_control=True, ordered_writes_reconstruct_full_memory=True,
            instruction_patches=0, calls_stubbed=0, interrupts_delivered=0, hardware_io=0,
            controlled_initial_memory=True, natural_capture=False, production_app_comparison=False,
            raw_memory_published=False, full_frame_claim=False, whole_game_parity=False,
            trace_arithmetic_flags_compared=False, endpoint_all_flags_compared=True)
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print(json.dumps(dict(status='passed', cases=len(cases), states=states, writes=write_count,
                              bytes=len(raw), compressed=len(compressed), sha256=sha(raw))))
    except Exception as error:
        (out / 'failed.json').write_text(json.dumps(dict(status='failed', case=index, error=str(error))) + '\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.repo.resolve(), args.out)
