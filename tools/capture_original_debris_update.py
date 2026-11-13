"""Execute full original debris updates; optional Unicorn 2.1.4 analysis."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

from scan_livels_debris_sites import load_levels

EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
LEVELS_SHA = 'd8b553871014108515d6af05b0853de8ccc22e4d3e44d63533ba1167fdc8c7b2'


def debris(cell, word, vx=0, vy=0, sx=0, sy=0, rest=0, glyph=0x60, aux=0):
    return struct.pack('<HHbbbbBBB', cell, word, vx, vy, sx, sy, rest, glyph, aux)


def room():
    tiles = bytearray(256)
    for y in range(16):
        for x in range(16):
            if x in (0, 15) or y in (0, 15): tiles[y * 16 + x] = 1
    return tiles, [0] * 256


def matrix():
    velocities = (-128, -127, -50, -1, 0, 1, 50, 127)
    for supported in (False, True):
        for vx in velocities:
            for vy in (-128, -127, -1, 0, 1, 120, 123, 124, 127):
                for sx, sy in ((0, 0), (127, 127), (-128, -128), (64, -64)):
                    tiles, words = room()
                    tiles[136], words[136] = 0x60, 0xC001
                    if supported: tiles[152] = 1
                    yield 'supported' if supported else 'airborne', tiles, words, [debris(136, 0xC001, vx, vy, sx, sy)], []
    for word in (0xFFBC, 0xFFBD, 0xFFFF):
        for glyph in (0x60, 0x75, 0x76, 0x77, 0x78):
            for rest in (0, 98, 99):
                tiles, words = room()
                tiles[136], words[136], tiles[152] = glyph, word, 1
                yield 'shatter_retire', tiles, words, [debris(136, word, rest=rest, glyph=glyph)], []
    for direction in (-1, 1):
        for own in velocities:
            for other in velocities:
                for bounce in (False, True):
                    tiles, words = room()
                    target = 136 + direction
                    for cell, word in ((136, 0xC001), (target, 0xC002)):
                        tiles[cell], words[cell], tiles[cell + 16] = 0x60, word, 1
                    vx = abs(own) * direction
                    if vx == 128: vx = 127
                    records = [debris(136, 0xC001, vx, 60 if bounce else -49,
                                      127 if direction > 0 else -128), debris(target, 0xC002, other, 20)]
                    yield 'debris_contact', tiles, words, records, []
    for mass in (0, 2, 18, 128, 254):
        for own in velocities:
            for direction in (-1, 1):
                for vy in (-49, 60):
                    tiles, words = room()
                    target = 136 + direction
                    tiles[136], words[136], tiles[152] = 0x60, 0xC001, 1
                    tiles[target], words[target] = 0x60, 0x8001
                    vx = abs(own) * direction
                    if vx == 128: vx = 127
                    collapse = struct.pack('<HHHBBBBHBBB', target * 2, target * 2, 0x8001,
                                           127, 128, 0, 0, 255, 0, 0, mass)
                    yield 'collapse_contact', tiles, words, [debris(136, 0xC001, vx, vy,
                        127 if direction > 0 else -128)], [collapse]
    for word in (0x4002, 1):
        for shape in ('single', 'diagonal', 'horizontal'):
            tiles, words = room()
            tiles[136], words[136] = 0x78, 0xC001
            tiles[120], words[120] = 0x60, word
            if shape != 'single':
                cell = 137 if shape == 'diagonal' else 121
                tiles[cell], words[cell] = 0x60, word
            yield 'cascade_' + shape, tiles, words, [debris(136, 0xC001, glyph=0x78)], []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('exe', 'levels', 'native-fixtures-dir', 'out', 'metadata'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path)
    args = parser.parse_args()
    if args.unicorn_path: sys.path.insert(0, str(args.unicorn_path))
    import unicorn
    from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_SS,
        UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS, UC_X86_INS_IN, UC_X86_INS_OUT)
    raw = args.exe.read_bytes()
    assert unicorn.__version__ == '2.1.4' and hashlib.sha256(raw).hexdigest() == EXE_SHA
    assert hashlib.sha256(args.levels.read_bytes()).hexdigest() == LEVELS_SHA
    header = struct.unpack_from('<14H', raw)
    assert header[3] == 468 and header[4] * 16 == 0x770
    image = bytearray(raw[0x770:])
    for index in range(header[3]):
        offset, segment = struct.unpack_from('<HH', raw, header[12] + 4 * index)
        address = 16 * segment + offset
        struct.pack_into('<H', image, address, (struct.unpack_from('<H', image, address)[0] + 0x1000) & 65535)
    cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
    cpu.mem_map(0, 1024**2)
    cpu.mem_write(0x10000, bytes(image))
    data = 0x1AA20
    initial = bytes(cpu.mem_read(data, 65536))
    counts = Counter()
    steps = [0]
    entries = {0x145FA: 'updater', 0x1458D: 'remove', 0x1370E: 'seed',
               0x13BB2: 'forward_blend', 0x13D46: 'reverse_blend',
               0x13D2D: 'forward_debris_write', 0x13EC1: 'reverse_debris_write',
               0x1A5A8: 'random', 0x1165A: 'sound_latch'}

    def observe(cpu, address, size, _):
        steps[0] += 1
        if address in entries: counts[entries[address]] += 1

    def unexpected(*args):
        raise RuntimeError('unexpected original interrupt or hardware I/O')

    cpu.hook_add(unicorn.UC_HOOK_CODE, observe)
    cpu.hook_add(unicorn.UC_HOOK_INTR, unexpected)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_IN)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_OUT)

    def execute(width, height, tick, rng, tiles, words, fragments, collapses):
        cpu.mem_write(data, initial)
        cpu.mem_write(data + 0x1AFA, bytes(2))
        cpu.mem_write(data + 0x1AFE, struct.pack('<I', rng))
        cpu.mem_write(data + 0x2076, struct.pack('<6H', 0, 0, 0, 0x209E, 199 + len(fragments), len(collapses)))
        cpu.mem_write(data + 0x2093, bytes(0x6611 - 0x2093))
        cpu.mem_write(data + 0x6620, bytes(250 * 15))
        if fragments: cpu.mem_write(data + 0x2093 + 2200, b''.join(fragments))
        if collapses: cpu.mem_write(data + 0x6620, b''.join(collapses))
        cpu.mem_write(data + 0x6612, struct.pack('<HH', 0, 0x5000))
        cpu.mem_write(data + 0xC1E0, struct.pack('<HH', 0, 0x4000))
        cpu.mem_write(data + 0xC1FE, struct.pack('<H', 0x4000))
        cpu.mem_write(data + 0xC204, struct.pack('<H', width))
        cpu.mem_write(data + 0x78C2, struct.pack('<H', tick))
        cpu.mem_write(0x40000, bytes(65536))
        cpu.mem_write(0x50000, bytes(65536))
        cpu.mem_write(0x40000, bytes(tiles))
        word_bytes = struct.pack('<' + 'H' * len(words), *words)
        cpu.mem_write(0x50000, word_bytes)
        for register, value in ((UC_X86_REG_CS, 0x1000), (UC_X86_REG_DS, 0x1AA2),
                                (UC_X86_REG_SS, 0x8000), (UC_X86_REG_SP, 0xFF00), (UC_X86_REG_EFLAGS, 0x202)):
            cpu.reg_write(register, value)
        cpu.mem_write(0x8FF00, struct.pack('<H', 0xFF00))
        steps[0] = 0
        cpu.emu_start(0x145FA, 0x1FF00, count=1000000)
        assert (cpu.reg_read(UC_X86_REG_CS), cpu.reg_read(UC_X86_REG_IP), cpu.reg_read(UC_X86_REG_SP)) == (0x1000, 0xFF00, 0xFF02)
        state = bytes(cpu.mem_read(data, 65536))
        bound, collapse_count = struct.unpack_from('<HH', state, 0x207E)
        assert 199 <= bound <= 1600 and collapse_count <= 250
        debris_count = bound - 199
        incoming = struct.pack('<HHHIHH', width, height, tick, rng, len(fragments), len(collapses)) + bytes(tiles) + word_bytes + b''.join(fragments) + b''.join(collapses)
        result = state[0x1AFE:0x1B02] + struct.pack('<HH', debris_count, collapse_count)
        result += bytes(cpu.mem_read(0x40000, len(tiles))) + bytes(cpu.mem_read(0x50000, len(word_bytes)))
        result += state[0x2093 + 2200:0x2093 + 2200 + 11 * debris_count] + state[0x6620:0x6620 + 15 * collapse_count]
        return incoming, result, state, steps[0]

    cases, native_pins = [], {}
    level = load_levels(args.levels)[0]
    for name in ('debris_impacts_original.txt', 'debris_rest_original.txt'):
        path = args.native_fixtures_dir / name
        native_pins[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for line in path.read_text().splitlines():
            if not line.startswith('case='): continue
            fields = dict(token.split('=', 1) for token in line.split())
            tiles, words = bytearray(level['tiles']), level['words'][:]
            for cell in fields['cells'].split(','):
                index, tile, word = cell.split(':')
                tiles[int(index)], words[int(index)] = int(tile, 16), int(word, 16)
            records = lambda value: [] if value == 'none' else [bytes.fromhex(part) for part in value.split(',')]
            request, result, state, instructions = execute(60, 33, int(fields['tick']), 0x12345678,
                tiles, words, records(fields['debris']), records(fields['collapse']))
            expected_d, expected_c = records(fields['after_debris']), records(fields['after_collapse'])
            assert struct.unpack_from('<HH', result, 4) == (len(expected_d), len(expected_c))
            at = 8 + 1980 * 3
            assert result[at:] == b''.join(expected_d + expected_c)
            assert result[:4].hex() == fields['rng']
            for cell in fields['after_cells'].split(','):
                index, tile, word = cell.split(':')
                index = int(index)
                assert result[8 + index] == int(tile, 16)
                assert struct.unpack_from('<H', result, 8 + 1980 + 2 * index)[0] == int(word, 16)
            cases.append(('native_crosscheck', request, result, instructions))
    assert len(cases) == 18
    for index, (group, tiles, words, fragments, collapses) in enumerate(matrix()):
        request, result, state, instructions = execute(16, 16, index & 65535,
            (0x12345678 ^ (index * 0x9E3779B9)) & 0xFFFFFFFF, tiles, words, fragments, collapses)
        cases.append((group, request, result, instructions))
    ih, oh = hashlib.sha256(), hashlib.sha256()
    with args.out.open('xb') as destination, gzip.GzipFile(fileobj=destination, mode='wb', filename='', mtime=0) as fixture:
        fixture.write(b'LZDF0001' + struct.pack('<I', len(cases)))
        for group, request, result, instructions in cases:
            fixture.write(struct.pack('<II', len(request), len(result)) + request + result)
            ih.update(request)
            oh.update(result)
    metadata = dict(schema='lezac.original-debris-update.v1', cases=len(cases),
        groups=dict(Counter(case[0] for case in cases)), native_crosschecked_cases=18,
        native_fixture_sha256=native_pins, original_exe_sha256=EXE_SHA, livels_sha256=LEVELS_SHA,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        decoder_sha256=hashlib.sha256(Path(__file__).with_name('scan_livels_debris_sites.py').read_bytes()).hexdigest(),
        relocated_image_sha256=hashlib.sha256(image).hexdigest(),
        instruction_start=0x45FA, instruction_end=0x4D3C,
        instruction_sha256=hashlib.sha256(raw[0x4D6A:0x54AC]).hexdigest(),
        input_sha256=ih.hexdigest(), output_sha256=oh.hexdigest(),
        fixture_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest(), executor='Unicorn 2.1.4',
        entry_counts=dict(counts), maximum_instructions=max(case[3] for case in cases),
        instruction_budget=1000000, original_calls_stubbed=False, original_instructions_patched=False,
        original_return_boundaries_verified=True, complete_live_records_maps_rng=True,
        sound_state_compared=False, spark_count_controlled_to_zero=True,
        natural_gameplay=False, compiled_cpp_comparison=False, whole_game_complete=False, audio='dummy')
    with args.metadata.open('x') as destination:
        json.dump(metadata, destination, indent=2, sort_keys=True)
        destination.write('\n')
    print(json.dumps(dict(cases=len(cases), groups=metadata['groups'], entry_counts=dict(counts),
                         maximum_instructions=metadata['maximum_instructions'], fixture_bytes=args.out.stat().st_size)))


if __name__ == '__main__':
    main()
