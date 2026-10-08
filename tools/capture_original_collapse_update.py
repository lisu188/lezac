"""Execute complete original collapse updates; optional Unicorn 2.1.4 analysis."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

from capture_original_debris_update import debris, room
from scan_livels_debris_sites import load_levels

EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
LEVELS_SHA = 'd8b553871014108515d6af05b0853de8ccc22e4d3e44d63533ba1167fdc8c7b2'


def collapse(first, last, word=0x8001, vx=0, vy=0, sx=0, sy=0, flags=0, rest=0, mass=4):
    return struct.pack('<HHHbbbbHBBB', first * 2, last * 2, word, vx, vy, sx, sy,
                       abs(vx) + abs(vy), flags, rest, mass)


def matrix():
    velocities = (-128, -127, -50, -1, 0, 1, 50, 127)
    for shape in ('horizontal', 'vertical', 'diagonal'):
        own_cells = [136, 137 if shape == 'horizontal' else 152 if shape == 'vertical' else 153]
        for supported in (False, True):
            for vx in velocities:
                for vy in (-128, -127, -1, 0, 1, 120, 123, 124, 127):
                    for fraction, (sx, sy) in enumerate(((0, 0), (127, 127), (-128, -128), (64, -64))):
                        tiles, words = room()
                        for cell in own_cells: tiles[cell], words[cell] = 0x60, 0x8001
                        if supported:
                            row = max(own_cells) // 16 + 1
                            for x in range(1, 15): tiles[row * 16 + x] = 1
                        record = collapse(min(own_cells), max(own_cells), vx=vx, vy=vy,
                                          sx=sx, sy=sy, flags=(0, 0x80, 3, 0x83)[fraction],
                                          rest=(0, 94, 95, 255)[fraction])
                        yield shape + ('_supported' if supported else '_airborne'), tiles, words, [], [record]
    for direction in (-1, 1):
        target = 135 if direction < 0 else 138
        for own in velocities:
            vx = min(abs(own), 127) * direction
            for other in velocities:
                for target_mass in (None, 0, 2, 18, 128):
                    tiles, words = room()
                    for x in range(1, 15): tiles[9 * 16 + x] = 1
                    for cell in (136, 137): tiles[cell], words[cell] = 0x60, 0x8001
                    word = 0xC002 if target_mass is None else 0x8002
                    tiles[target], words[target] = 0x60, word
                    source = collapse(136, 137, vx=vx, sx=127 if direction > 0 else -128)
                    fragments = [debris(target, word, other)] if target_mass is None else []
                    targets = [] if target_mass is None else [collapse(target, target, word, vx=other, mass=target_mass)]
                    yield 'debris_contact' if target_mass is None else 'collapse_contact', tiles, words, fragments, targets + [source]


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
    assert not args.out.exists() and not args.metadata.exists()
    raw = args.exe.read_bytes()
    assert unicorn.__version__ == '2.1.4' and hashlib.sha256(raw).hexdigest() == EXE_SHA
    assert hashlib.sha256(args.levels.read_bytes()).hexdigest() == LEVELS_SHA
    header = struct.unpack_from('<14H', raw)
    assert header[3] == 468 and header[4] * 16 == 0x770
    initializer = raw[0x30AD:0x30B9]
    assert hashlib.sha256(initializer).hexdigest() == 'aaef4f5b7b8e4a213d7a9c11a2cc003cddd8026c89bd5cc0ee80006e945aefde'
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
    actor_fixture = args.native_fixtures_dir / 'fracture_actor_original.txt'
    descriptor_row = next(line for line in actor_fixture.read_text().splitlines() if line.startswith('sprites descriptors='))
    descriptors = bytes.fromhex(descriptor_row.split('=', 1)[1])
    assert len(descriptors) == 92 * 4
    counts, steps = Counter(), [0]
    entries = {0x1293D: 'record_table_initializer', 0x15102: 'updater', 0x1508B: 'remove', 0x1370E: 'seed',
               0x1A5A8: 'random', 0x1165A: 'sound_latch', 0x12F9F: 'actor_constructor'}

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
        cpu.mem_write(data + 0x1BAE, bytes(31 * 38))
        cpu.mem_write(data + 0x2076, struct.pack('<6H', 0, 0, 0, 0, 199 + len(fragments), len(collapses)))
        cpu.mem_write(data + 0x208D, bytes(1))
        cpu.mem_write(data + 0x2093, bytes(0x6611 - 0x2093))
        cpu.mem_write(data + 0x6620, bytes(250 * 15))
        if fragments: cpu.mem_write(data + 0x292B, b''.join(fragments))
        cpu.mem_write(data + 0x6620, b''.join(collapses))
        cpu.mem_write(data + 0x6612, struct.pack('<HH', 0, 0x5000))
        cpu.mem_write(data + 0x206E, struct.pack('<H', 0x5000))
        cpu.mem_write(data + 0xC1E0, struct.pack('<HH', 0, 0x4000))
        cpu.mem_write(data + 0xC1FE, struct.pack('<H', 0x4000))
        cpu.mem_write(data + 0xC204, struct.pack('<H', width))
        cpu.mem_write(data + 0xC21E, bytes(32 * 8))
        cpu.mem_write(data + 0xC322, descriptors)
        cpu.mem_write(data + 0x78C2, struct.pack('<4H', tick, 0x4000, 0, 0))
        cpu.mem_write(0x40000, bytes(65536))
        cpu.mem_write(0x50000, bytes(65536))
        cpu.mem_write(0x40000, bytes(tiles))
        word_bytes = struct.pack('<' + 'H' * len(words), *words)
        cpu.mem_write(0x50000, word_bytes)
        for register, value in ((UC_X86_REG_CS, 0x1000), (UC_X86_REG_DS, 0x1AA2),
                                (UC_X86_REG_SS, 0x8000), (UC_X86_REG_SP, 0xFF00), (UC_X86_REG_EFLAGS, 0x202)):
            cpu.reg_write(register, value)
        cpu.mem_write(0x8FF00, struct.pack('<H', 0xFF00))
        # Startup 1000:293D..2949 sets the bases used by pool compaction.
        steps[0] = 0
        cpu.emu_start(0x1293D, 0x12949, count=4)
        assert steps[0] == 4 and cpu.reg_read(UC_X86_REG_IP) == 0x2949
        assert bytes(cpu.mem_read(data + 0x207A, 4)) == struct.pack('<HH', 0x6620, 0x209E)
        steps[0] = 0
        cpu.emu_start(0x15102, 0x1FF00, count=1000000)
        assert (cpu.reg_read(UC_X86_REG_CS), cpu.reg_read(UC_X86_REG_IP), cpu.reg_read(UC_X86_REG_SP)) == (0x1000, 0xFF00, 0xFF02)
        state = bytes(cpu.mem_read(data, 65536))
        bound, collapse_count = struct.unpack_from('<HH', state, 0x207E)
        assert 199 <= bound <= 1600 and collapse_count <= 250
        debris_count = bound - 199
        incoming = struct.pack('<HHHIHHHH', width, height, tick, rng, len(fragments), len(collapses), 0, 0x4000)
        incoming += bytes(tiles) + word_bytes + b''.join(fragments) + b''.join(collapses)
        result = state[0x1AFE:0x1B02] + struct.pack('<HH', debris_count, collapse_count) + state[0x78C8:0x78CA] + state[0x78C4:0x78C6]
        result += bytes(cpu.mem_read(0x40000, len(tiles))) + bytes(cpu.mem_read(0x50000, len(word_bytes)))
        result += state[0x292B:0x292B + 11 * debris_count] + state[0x6620:0x6620 + 15 * collapse_count]
        return incoming, result, state, steps[0]

    cases = []
    native = args.native_fixtures_dir / 'collapse_steps_original.txt'
    level = load_levels(args.levels)[0]
    for line in native.read_text().splitlines():
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
        assert struct.unpack_from('<4H', result, 4) == (len(expected_d), len(expected_c), int(fields['destroyed']), int(fields['next_word'], 16))
        assert result[12 + 1980 * 3:] == b''.join(expected_d + expected_c)
        assert result[:4].hex() == fields['rng']
        for cell in fields['after_cells'].split(','):
            index, tile, word = cell.split(':')
            index = int(index)
            assert result[12 + index] == int(tile, 16)
            assert struct.unpack_from('<H', result, 12 + 1980 + 2 * index)[0] == int(word, 16)
        cases.append(('native_crosscheck', request, result, instructions))
    assert len(cases) == 27
    for index, (group, tiles, words, fragments, collapses) in enumerate(matrix()):
        request, result, state, instructions = execute(16, 16, index & 65535,
            (0x12345678 ^ (index * 0x9E3779B9)) & 0xFFFFFFFF, tiles, words, fragments, collapses)
        cases.append((group, request, result, instructions))
    assert len(cases) == 2395
    ih, oh = hashlib.sha256(), hashlib.sha256()
    with args.out.open('xb') as destination, gzip.GzipFile(fileobj=destination, mode='wb', filename='', mtime=0) as fixture:
        fixture.write(b'LZCF0001' + struct.pack('<I', len(cases)))
        for group, request, result, instructions in cases:
            fixture.write(struct.pack('<II', len(request), len(result)) + request + result)
            ih.update(request)
            oh.update(result)
    metadata = dict(schema='lezac.original-collapse-update.v2', cases=len(cases),
        groups=dict(Counter(case[0] for case in cases)), native_crosschecked_cases=27,
        native_fixture_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (native, actor_fixture)},
        original_exe_sha256=EXE_SHA, livels_sha256=LEVELS_SHA,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        dependency_sha256={name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                           for name in ('capture_original_debris_update.py', 'scan_livels_debris_sites.py')},
        relocated_image_sha256=hashlib.sha256(image).hexdigest(),
        instruction_start=0x5102, instruction_end=0x568A,
        instruction_sha256=hashlib.sha256(raw[0x5872:0x5DFA]).hexdigest(),
        record_table_initializers_executed=True, record_table_initialization_boundaries_verified=True,
        initialization_start=0x293D, initialization_end=0x2949,
        initialization_sha256=hashlib.sha256(initializer).hexdigest(),
        collapse_table_base=0x6620, debris_table_base=0x209E,
        input_sha256=ih.hexdigest(), output_sha256=oh.hexdigest(), fixture_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest(),
        executor='Unicorn 2.1.4', original_calls_stubbed=False, original_instructions_patched=False,
        original_return_boundaries_verified=True, word_segment_cache_initialized=True,
        complete_live_records_maps_rng=True, destruction_fragment_counter_compared=True,
        actor_pool_controlled_empty=True, actor_records_compared=False, sound_state_compared=False,
        native_initial_map_outside_fixture_not_claimed=True, natural_gameplay=False,
        compiled_cpp_comparison=False, whole_game_complete=False, entry_counts=dict(counts),
        maximum_instructions=max(case[3] for case in cases))
    with args.metadata.open('x') as output: output.write(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
    print(json.dumps(metadata, sort_keys=True))


if __name__ == '__main__':
    main()
