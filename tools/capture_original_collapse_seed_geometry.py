"""Execute original collapse seeding geometry; optional Unicorn 2.1.4 analysis."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

from scan_livels_debris_sites import load_levels, EXPECTED_DIMENSIONS

EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
LEVELS_SHA = 'd8b553871014108515d6af05b0853de8ccc22e4d3e44d63533ba1167fdc8c7b2'


def connected(words, width, seed):
    key, found, pending = words[seed], set(), [seed]
    while pending:
        cell = pending.pop()
        if cell in found or not (0 <= cell < len(words)) or words[cell] != key:
            continue
        found.add(cell)
        x, y = cell % width, cell // width
        if x > 0: pending.append(cell - 1)
        if x + 1 < width: pending.append(cell + 1)
        if y > 0: pending.append(cell - width)
        if cell + width < len(words): pending.append(cell + width)
    return found


def cases(levels):
    shapes = dict(single=[(0, 0)], horizontal=[(0, 0), (1, 0), (2, 0)],
                  vertical=[(0, 0), (0, 1), (0, 2)], diagonal=[(0, 0), (1, 1)],
                  diagonal_chain=[(0, 0), (1, 1), (2, 2)], separated=[(0, 0), (2, 0)],
                  elbow=[(0, 0), (1, 0), (1, 1)], tee=[(0, 0), (-1, 1), (0, 1), (1, 1)])
    ring = [(x, y) for y in range(5) for x in range(5) if x in (0, 4) or y in (0, 4)]
    shapes['ring'], shapes['ring_center'] = ring, ring + [(2, 2)]
    for name, points in shapes.items():
        for rotation in range(4):
            words = [0] * 256
            for x, y in points:
                for _ in range(rotation):
                    x, y = -y, x
                words[16 * (6 + y) + 6 + x] = 1
            yield 'synthetic', name + '_' + str(rotation), 16, words, 102
    for seed in (0, 15, 240, 255):
        words = [0] * 256
        words[seed] = 1
        yield 'boundary', str(seed), 16, words, seed
    for number, level in enumerate(levels, 1):
        width, words = level['width'], level['words']
        remaining = {cell for cell, word in enumerate(words) if 0 < word < 0x4000}
        while remaining:
            seed = min(remaining)
            group = connected(words, width, seed)
            remaining -= group
            name = f'level{number}_key{words[seed]}_seed{seed}'
            yield 'shipped_initial', name, width, words, seed
            if len(group) > 1:
                altered = words[:]
                removed = set(sorted(group)[1::3])
                for cell in removed:
                    altered[cell] = 0
                yield 'shipped_controlled_clear', name, width, altered, seed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--levels', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path)
    args = parser.parse_args()
    if args.unicorn_path:
        sys.path.insert(0, str(args.unicorn_path))
    import unicorn
    from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_SS,
                                  UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS,
                                  UC_X86_INS_IN, UC_X86_INS_OUT)
    raw = args.exe.read_bytes()
    if (unicorn.__version__ != '2.1.4' or hashlib.sha256(raw).hexdigest() != EXE_SHA
            or hashlib.sha256(args.levels.read_bytes()).hexdigest() != LEVELS_SHA):
        raise ValueError('original geometry executor/assets differ')
    levels = load_levels(args.levels)
    if [(level['width'], level['height']) for level in levels] != EXPECTED_DIMENSIONS:
        raise ValueError('original geometry map decode differs')
    matrix = list(cases(levels))
    header = struct.unpack_from('<14H', raw)
    if header[0] != 0x5A4D or header[3] != 468 or header[4] * 16 != 0x770:
        raise ValueError('original MZ layout differs')
    image = bytearray(raw[0x770:])
    for index in range(header[3]):
        offset, segment = struct.unpack_from('<HH', raw, header[12] + 4 * index)
        address = 16 * segment + offset
        struct.pack_into('<H', image, address, (struct.unpack_from('<H', image, address)[0] + 0x1000) & 65535)
    cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
    cpu.mem_map(0, 1024 * 1024)
    cpu.mem_write(0x10000, bytes(image))
    data = 0x1AA20
    cpu.mem_write(data + 0x1AFA, bytes(2))
    cpu.mem_write(data + 0x6612, struct.pack('<HH', 0, 0x5000))
    steps = [0]

    def observe(*args):
        steps[0] += 1

    def unexpected(*args):
        raise RuntimeError('unexpected original interrupt or hardware I/O')

    cpu.hook_add(unicorn.UC_HOOK_CODE, observe)
    cpu.hook_add(unicorn.UC_HOOK_INTR, unexpected)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_IN)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_OUT)
    groups, differing, examples = {}, {}, []
    input_hash, output_hash = hashlib.sha256(), hashlib.sha256()
    maximum = 0
    with args.out.open('xb') as destination, gzip.GzipFile(fileobj=destination, mode='wb', mtime=0, filename='') as fixture:
        fixture.write(b'LZSF0001' + struct.pack('<I', len(matrix)))
        for group, name, width, words, seed in matrix:
            before = struct.pack('<' + 'H' * len(words), *words)
            cpu.mem_write(0x50000, bytes(65536))
            cpu.mem_write(0x50000, before)
            cpu.mem_write(data + 0xC204, struct.pack('<H', width))
            cpu.mem_write(data + 0x2080, bytes(2))
            cpu.mem_write(data + 0x6620, bytes(15))
            cpu.mem_write(data + 0x79C8, b'\x7f')
            for register, value in ((UC_X86_REG_CS, 0x1000), (UC_X86_REG_DS, 0x1AA2),
                                    (UC_X86_REG_SS, 0x8000), (UC_X86_REG_SP, 0xFF00),
                                    (UC_X86_REG_EFLAGS, 0x202)):
                cpu.reg_write(register, value)
            cpu.mem_write(0x8FF00, struct.pack('<6H', 0xFF00, 0x78D6, 0x1AA2, 0, 0, seed))
            steps[0] = 0
            cpu.emu_start(0x1370E, 0x1FF00, count=200000)
            if (cpu.reg_read(UC_X86_REG_CS), cpu.reg_read(UC_X86_REG_IP), cpu.reg_read(UC_X86_REG_SP)) != (0x1000, 0xFF00, 0xFF0C):
                raise RuntimeError('original seeder did not return: ' + name)
            if cpu.mem_read(data + 0x79C8, 1)[0] != 1:
                raise RuntimeError('original seeder failed: ' + name)
            after = bytes(cpu.mem_read(0x50000, len(before)))
            marked = set()
            for cell, (word,) in enumerate(struct.iter_unpack('<H', after)):
                if word != words[cell]:
                    if words[cell] != words[seed] or word != words[cell] | 0x8000:
                        raise ValueError('unexpected original seeder map write')
                    marked.add(cell)
            record = bytes(cpu.mem_read(data + 0x6620, 15))
            incoming = struct.pack('<HHH', width, len(words), seed) + before
            result = record[:4] + struct.pack('<H', len(marked)) + record[14:15] + after
            fixture.write(struct.pack('<II', len(incoming), len(result)) + incoming + result)
            input_hash.update(incoming)
            output_hash.update(result)
            groups[group] = groups.get(group, 0) + 1
            if marked != connected(words, width, seed):
                differing[group] = differing.get(group, 0) + 1
                if len(examples) < 12 or group == 'shipped_controlled_clear' and not any(e['group'] == group for e in examples):
                    examples.append(dict(group=group, case=name, seed=seed, key=words[seed],
                                         original_cells=len(marked), four_neighbor_cells=len(connected(words, width, seed)),
                                         record_hex=record.hex()))
            maximum = max(maximum, steps[0])
    metadata = dict(schema='lezac.collapse-seed-geometry-original.v1', cases=len(matrix), groups=groups,
                    original_exe_sha256=EXE_SHA, livels_sha256=LEVELS_SHA,
                    fixture_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest(),
                    generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    decoder_sha256=hashlib.sha256(Path(__file__).with_name('scan_livels_debris_sites.py').read_bytes()).hexdigest(),
                    input_sha256=input_hash.hexdigest(), output_sha256=output_hash.hexdigest(),
                    instruction_start=0x370E, instruction_end=0x3A53,
                    instruction_sha256=hashlib.sha256(raw[0x3E7E:0x41C3]).hexdigest(),
                    mz_relocations=468, maximum_instructions=maximum, instruction_budget=200000,
                    executor='Unicorn 2.1.4', four_neighbor_differences=differing, examples=examples,
                    original_calls_stubbed=False, original_instructions_patched=False,
                    original_return_boundaries_verified=True, compiled_cpp_comparison=False,
                    natural_gameplay=False, changed_map_natural_reachability_verified=False,
                    complete_seeder_record_comparison=False, audio='dummy', whole_game_complete=False)
    with args.metadata.open('x') as output:
        json.dump(metadata, output, indent=2, sort_keys=True)
        output.write('\n')
    print(json.dumps(dict(cases=len(matrix), groups=groups, four_neighbor_differences=differing,
                         fixture_bytes=args.out.stat().st_size, maximum_instructions=maximum)))


if __name__ == '__main__':
    main()
