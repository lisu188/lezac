"""Execute unchanged original reserve HUD 29DB..2A3E and the complete 1156 blitter."""
import argparse
import gzip
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha


def profiles():
    result = [(player, reserve, (player - 1) * 180, 0x8000, 0x202, 0x200, 0x3fe4)
              for player in (1, 2) for reserve in range(256)]
    for player in (1, 2):
        for reserve in (0, 1, 2, 3, 255):
            for base in (0xffe0, 0xe340, 0x2050):
                for flags in (0x202, 0x602):
                    for x in (0, 0xfff8, 0x8000, 0x0fe0):
                        result.append((player, reserve, x, base, flags, 0x200, 0x3fe4))
    for floor, sp in ((0x4000, 0x3fe4), (0, 0x200), (0x3dd9, 0x3fe4), (0x3dd8, 0x3fe4)):
        result.append((1, 3, 48, 0x8000, 0x202, floor, sp))
    return result


def inputs(index, profile, tiles):
    player, reserve, x, base, flags, floor, sp = profile
    seeds = []
    cells = {}
    for start in (base, (base + 0x1cc0) & 65535):
        for offset in range(-80, 82):
            cells[0x1aa20 + ((start + offset) & 65535)] = (offset * 37 + index * 11 + 5) & 255
    # Nonzero destination/background bytes expose opaque writes and byte/word wrap.
    direction = -1 if flags & 0x400 else 1
    for slot in range(3) if index >= 512 else ():
        start = (x + 0xf000 + slot * 9) & 65535
        for row in range(8):
            for column in range(-2, 6):
                offset = (start + row * (312 + direction * 8) + column * 2 * direction) & 65535
                for byte in (0, 1):
                    cells[0xa0000 + offset + byte] = (index + row * 23 + column * 13 + byte * 7) & 255
    for address in sorted(cells):
        if seeds and address == seeds[-1][0] + len(seeds[-1][1]):
            seeds[-1][1].append(cells[address])
        else:
            seeds.append((address, bytearray((cells[address],))))
    seeds = [(address, bytes(raw)) for address, raw in seeds]
    if index < 512:
        seeds.append((0x1aa20 + base, tiles[:64]))
        seeds.append((0x1aa20 + base + 0x1cc0, tiles[115 * 64:116 * 64]))
    seeds.append((0x70000 + sp - 64, bytes((i * 29 + index * 7 + 11) & 255 for i in range(72))))
    seeds.append((0x70000 + sp, struct.pack('<HH', 0x7d0c, player)))
    for offset, value in ((0xc208, base), (0x79f2 + player * 2, x), (0x1afa, floor),
                          (0x2072, 0xa55a), (0x2074, 0x5aa5)):
        seeds.append((0x1aa20 + offset, struct.pack('<H', value)))
    seeds.append((0x1aa20 + 0x79e9 + player, bytes((reserve,))))
    return seeds


def generate(root, out):
    if unicorn.__version__ != '2.1.4' or any(k in os.environ for k in ('LD_PRELOAD', 'LIBUNICORN_PATH')):
        raise ValueError('Unsupported Unicorn loader profile')
    library = Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes()) != LIB_SHA or not any(
            line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual Unicorn library mapping differs')
    exe = (root / 'LEZAC.EXE').read_bytes()
    if sha(exe) != EXE_SHA:
        raise ValueError('Original executable differs')
    atlas = (root / 'CARO.CAR').read_bytes()
    if len(atlas) != 8450 or atlas[:2] != bytes((0, 132)):
        raise ValueError('Original CARO atlas geometry differs')
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
    output = bytearray(b'LZRSHD01' + struct.pack('<I', len(cases)))
    coverage, states, errors, write_total, rep_zero = set(), 0, 0, 0, 0
    try:
        for index, profile in enumerate(cases):
            initial = bytearray(1048576)
            initial[0x10000:0x10000 + len(image)] = image
            seeds = inputs(index, profile, atlas[2:])
            for address, raw in seeds:
                initial[address:address + len(raw)] = raw
            values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                      0x1000, 0x1aa2, 0x40, 0x7000, profile[6], 0x29db, profile[4])
            endpoints, trace, writes = [], [], []
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for reg, value in zip(REGS, values):
                    engine.reg_write(reg, value)
                def external(*unused):
                    raise ValueError('Reserve HUD crossed an unmodeled interrupt or I/O')
                def code(uc, address, size, user):
                    registers = tuple(uc.reg_read(reg) for reg in REGS)
                    trace.append(registers)
                    coverage.add((registers[7], registers[12]))
                def write(uc, access, address, size, value, user):
                    if size not in (1, 2) or not (0x1aa20 <= address < 0x2aa20 or
                            0x70000 <= address < 0x74008 or 0xa0000 <= address < 0xb0001):
                        raise ValueError('Reserve HUD wrote outside data/stack/VGA')
                    writes.append((address, size, value & ((1 << (size * 8)) - 1)))
                engine.hook_add(unicorn.UC_HOOK_INTR, external)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                floor, sp = profile[5:]
                error = sp == 0x200 or floor > 0x3dd8
                until = 0x192e2 if error else 0x17d0c
                engine.emu_start(0x129db, until, count=10000)
                registers = tuple(engine.reg_read(reg) for reg in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                if registers[7] * 16 + registers[12] != until:
                    raise ValueError('Reserve HUD did not reach declared endpoint')
                if final[0x10000:0x1aa20] != image[:0xaa20]:
                    raise ValueError('Original code changed during execution')
                endpoints.append((registers, final))
            if endpoints[0] != endpoints[1]:
                raise ValueError('Reserve HUD observation affected complete memory/registers')
            registers, final = endpoints[0]
            expected = bytearray(initial)
            for address, size, value in writes:
                expected[address:address + size] = value.to_bytes(size, 'little')
            if expected != final:
                raise ValueError('Observed writes do not reconstruct complete final memory')
            trace.append(registers)
            states += len(trace)
            write_total += len(writes)
            rep_zero += sum(r[7] == 0x1000 and r[12] == 0x116a and r[2] == 0 for r in trace)
            errors += int(error)
            output.extend(struct.pack('<II13HI13HI', index, int(error), *values, *registers))
            output.extend(struct.pack('<I', len(seeds)))
            for address, raw in seeds:
                output.extend(struct.pack('<II', address, len(raw)) + raw)
            output.extend(struct.pack('<I', len(trace)))
            for item in trace:
                output.extend(struct.pack('<13HI', *item))
            output.extend(struct.pack('<I', len(writes)))
            for address, size, value in writes:
                output.extend(struct.pack('<IBH', address, size, value))
        raw = bytes(output)
        compressed = gzip.compress(raw, mtime=0)
        (out / 'oracle.bin.gz').write_bytes(compressed)
        manifest = dict(schema='lezac-controlled-reserve-hud-v1', executable_sha256=EXE_SHA,
            tile_atlas_sha256=sha(atlas), shipped_glyph_cases=512,
            producer_sha256=sha(Path(__file__).read_bytes()),
            shared_oracle_sha256=sha(Path(__file__).with_name('frame_camera_oracle.py').read_bytes()),
            unicorn_version=unicorn.__version__, unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True, cases=len(cases), register_states=states,
            runtime_errors=errors, ordered_writes=write_total, rep_zero_observations=rep_zero,
            executed_instructions=[list(pair) for pair in sorted(coverage)],
            projection_bytes=len(raw), projection_sha256=sha(raw), compressed_bytes=len(compressed),
            compressed_sha256=sha(compressed), controlled_initial_memory=True,
            full_memory_observer_control=True, raw_memory_published=False, natural_capture=False,
            full_frame_claim=False, work_clock_claim=False, trace_arithmetic_flags_compared=False,
            endpoint_all_flags_compared=True, instruction_patches=0, calls_stubbed=0,
            interrupts_delivered=0, hardware_io=0,
            rep_trace_policy='raw-unicorn-transfer-and-zero-count-observations')
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print(json.dumps(dict(status='passed', cases=len(cases), states=states, runtime_errors=errors,
                              bytes=len(raw), compressed=len(compressed), sha256=sha(raw))), flush=True)
    except Exception as error:
        (out / 'failed.json').write_text(json.dumps(dict(status='failed', case=index, error=str(error))) + '\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.repo.resolve(), args.out)
