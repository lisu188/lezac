"""Execute original collapse updates including clean-pool fracture actor records."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

from capture_original_collapse_update import collapse
from capture_original_debris_update import room
from check_original_collapse_update import metadata, records
from scan_livels_debris_sites import load_levels

ROOT = Path(__file__).resolve().parent.parent


def filled_pool(count, descriptors):
    result = bytearray()
    for index in range(count):
        actor = bytearray(38)
        actor[:3] = bytes((0x0b, 3 + index, 8 + index))
        struct.pack_into('<hhhh', actor, 6, index - 15, 15 - index, index, 255 - index)
        actor[0x14:0x1d] = bytes((0, 5, 74, 74, 79, 2, 2, 1, 1))
        result += actor + struct.pack('<HH', index * 3, index * 5) + descriptors[74 * 4:75 * 4]
    return bytes(result)


def extra_cases(descriptors):
    for count in (0, 1, 28, 29, 30):
        for tick in range(4):
            for rng in (0, 1, 0x12345678, 0xffffffff):
                tiles, words = room()
                for y in (9, 11):
                    for x in range(1, 15): tiles[y * 16 + x] = 1
                for cell, word in ((136, 0x8001), (137, 0x8001), (168, 0x8002), (169, 0x8002)):
                    tiles[cell], words[cell] = 0x60, word
                active = [collapse(136, 137, vy=64, sy=100), collapse(168, 169, 0x8002, vy=64, sy=100)]
                request = struct.pack('<HHHIHHHH', 16, 16, tick, rng, 0, 2, 0, 0x4000)
                request += bytes(tiles) + struct.pack('<256H', *words) + b''.join(active)
                yield 'two_fractures_pool_' + str(count), request, filled_pool(count, descriptors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path)
    args = parser.parse_args()
    if args.unicorn_path: sys.path.insert(0, str(args.unicorn_path))
    import unicorn
    from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_SS,
        UC_X86_REG_SP, UC_X86_REG_IP, UC_X86_REG_EFLAGS, UC_X86_INS_IN, UC_X86_INS_OUT)
    assert not args.out.exists() and not args.metadata.exists()
    previous = metadata()
    assert unicorn.__version__ == '2.1.4'
    raw = (ROOT / 'LEZAC.EXE').read_bytes()
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
    data = 0x1aa20
    initial = bytes(cpu.mem_read(data, 65536))
    native = ROOT / 'tests/fixtures/fracture_actor_original.txt'
    native_lines = native.read_text().splitlines()
    descriptor_row = next(line for line in native_lines if line.startswith('sprites descriptors='))
    descriptors = bytes.fromhex(descriptor_row.split('=', 1)[1])
    assert len(descriptors) == 368
    native_creation = dict(token.split('=', 1) for token in next(line for line in native_lines if line.startswith('tick ')).split()[1:])
    constructor_context = bytes.fromhex(native_creation['actors'].split(':')[0])[1]
    assert constructor_context == 3
    counts, steps = Counter(), [0]
    entries = {0x1293d: 'record_table_initializer', 0x15102: 'updater', 0x12f9f: 'actor_constructor',
               0x1a5a8: 'random', 0x1165a: 'sound_latch'}

    def observe(cpu, address, size, _):
        steps[0] += 1
        if address in entries: counts[entries[address]] += 1

    def unexpected(*args):
        raise RuntimeError('unexpected original interrupt or hardware I/O')

    cpu.hook_add(unicorn.UC_HOOK_CODE, observe)
    cpu.hook_add(unicorn.UC_HOOK_INTR, unexpected)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_IN)
    cpu.hook_add(unicorn.UC_HOOK_INSN, unexpected, None, 1, 0, UC_X86_INS_OUT)

    def execute(request, actors):
        width, height, tick, rng, fragments, collapses, destroyed, next_word = struct.unpack_from('<HHHIHHHH', request)
        cells = width * height
        tile_end, word_end = 18 + cells, 18 + 3 * cells
        fragment_end = word_end + 11 * fragments
        assert len(request) == fragment_end + 15 * collapses and len(actors) % 46 == 0
        before = len(actors) // 46
        assert before <= 30
        cpu.mem_write(data, initial)
        cpu.mem_write(data + 0x1afa, bytes(2))
        cpu.mem_write(data + 0x1afe, struct.pack('<I', rng))
        cpu.mem_write(data + 0x1bae, bytes(31 * 38))
        cpu.mem_write(data + 0x2076, struct.pack('<6H', 0, 0, 0, 0, 199 + fragments, collapses))
        cpu.mem_write(data + 0x208d, bytes((before,)))
        cpu.mem_write(data + 0x2093, bytes(0x6611 - 0x2093))
        cpu.mem_write(data + 0x6620, bytes(250 * 15))
        if fragments: cpu.mem_write(data + 0x292b, request[word_end:fragment_end])
        if collapses: cpu.mem_write(data + 0x6620, request[fragment_end:])
        cpu.mem_write(data + 0x6612, struct.pack('<HH', 0, 0x5000))
        cpu.mem_write(data + 0x206e, struct.pack('<H', 0x5000))
        cpu.mem_write(data + 0xc1e0, struct.pack('<HH', 0, 0x4000))
        cpu.mem_write(data + 0xc1fe, struct.pack('<H', 0x4000))
        cpu.mem_write(data + 0xc204, struct.pack('<H', width))
        cpu.mem_write(data + 0xc21e, bytes(33 * 8))
        cpu.mem_write(data + 0xc322, descriptors)
        cpu.mem_write(data + 0xc496, bytes((constructor_context + before,)))
        for index in range(before):
            cpu.mem_write(data + 0x1bae + (index + 1) * 38, actors[index * 46:index * 46 + 38])
            cpu.mem_write(data + 0xc21e + actors[index * 46 + 1] * 8, actors[index * 46 + 38:(index + 1) * 46])
        cpu.mem_write(data + 0x78c2, struct.pack('<4H', tick, next_word, 0, destroyed))
        cpu.mem_write(0x40000, bytes(65536))
        cpu.mem_write(0x50000, bytes(65536))
        cpu.mem_write(0x40000, request[18:tile_end])
        cpu.mem_write(0x50000, request[tile_end:word_end])
        for register, value in ((UC_X86_REG_CS, 0x1000), (UC_X86_REG_DS, 0x1aa2),
                                (UC_X86_REG_SS, 0x8000), (UC_X86_REG_SP, 0xff00), (UC_X86_REG_EFLAGS, 0x202)):
            cpu.reg_write(register, value)
        cpu.mem_write(0x8ff00, struct.pack('<H', 0xff00))
        steps[0] = 0
        cpu.emu_start(0x1293d, 0x12949, count=4)
        assert steps[0] == 4 and cpu.reg_read(UC_X86_REG_IP) == 0x2949
        assert bytes(cpu.mem_read(data + 0x207a, 4)) == struct.pack('<HH', 0x6620, 0x209e)
        steps[0] = 0
        cpu.emu_start(0x15102, 0x1ff00, count=1000000)
        assert (cpu.reg_read(UC_X86_REG_CS), cpu.reg_read(UC_X86_REG_IP), cpu.reg_read(UC_X86_REG_SP)) == (0x1000, 0xff00, 0xff02)
        state = bytes(cpu.mem_read(data, 65536))
        bound, after_collapses = struct.unpack_from('<HH', state, 0x207e)
        after = state[0x208d]
        assert 199 <= bound <= 1600 and after_collapses <= 250 and before <= after <= 30
        debris_count = bound - 199
        result = state[0x1afe:0x1b02] + struct.pack('<HH', debris_count, after_collapses)
        result += state[0x78c8:0x78ca] + state[0x78c4:0x78c6]
        result += bytes(cpu.mem_read(0x40000, cells)) + bytes(cpu.mem_read(0x50000, 2 * cells))
        result += state[0x292b:0x292b + 11 * debris_count] + state[0x6620:0x6620 + 15 * after_collapses]
        actor_bytes = bytearray()
        for index in range(1, after + 1):
            actor = state[0x1bae + index * 38:0x1bae + (index + 1) * 38]
            visual_slot = actor[1]
            assert constructor_context <= visual_slot <= 32
            actor_bytes += actor + state[0xc21e + visual_slot * 8:0xc21e + (visual_slot + 1) * 8]
        assert actor_bytes[:len(actors)] == actors, (before, after,
            [(i, a, b) for i, (a, b) in enumerate(zip(actor_bytes, actors)) if a != b][:20])
        return result, struct.pack('<H', after) + bytes(actor_bytes), steps[0]

    cases, admissions = [], Counter()
    for request, expected in records(previous):
        result, actors, instructions = execute(request, b'')
        assert result == expected, 'new executor must reproduce every legacy collapse result'
        cases.append(('legacy_crosscheck', request + bytes(2), result + actors, instructions))
        admissions[struct.unpack_from('<H', actors)[0]] += 1
    level = load_levels(ROOT / 'LIVELS.SCH')[0]
    tiles, words = bytearray(level['tiles']), level['words'][:]
    for y in range(17, 24):
        for x in range(19, 31): tiles[y * 60 + x], words[y * 60 + x] = int(y == 21), 0
    for cell, tile in ((1223, 0x50), (1224, 0x51)): tiles[cell], words[cell] = tile, 0x8009
    native_request = struct.pack('<HHHIHHHH', 60, 33, 114, 0x12345678, 0, 1, 0, 0x4000)
    native_request += bytes(tiles) + struct.pack('<1980H', *words) + collapse(1223, 1224, 0x8009, vy=64, sy=100)
    result, actors, instructions = execute(native_request, b'')
    native_actor, native_visual = map(bytes.fromhex, native_creation['actors'].split(':'))
    assert actors == struct.pack('<H', 1) + native_actor + native_visual
    assert result[:4].hex() == next(line for line in native_lines if line.startswith('creation_rng=')).split('=', 1)[1]
    cases.append(('native_actor_creation', native_request + bytes(2), result + actors, instructions))
    admissions[1] += 1
    for group, request, initial_actors in extra_cases(descriptors):
        result, actors, instructions = execute(request, initial_actors)
        before, after = len(initial_actors) // 46, struct.unpack_from('<H', actors)[0]
        assert after == min(before + 2, 30), (group, before, after)
        cases.append((group, request + struct.pack('<H', before) + initial_actors, result + actors, instructions))
        admissions[after - before] += 1
    ih, oh = hashlib.sha256(), hashlib.sha256()
    with args.out.open('xb') as destination, gzip.GzipFile(fileobj=destination, mode='wb', filename='', mtime=0) as fixture:
        fixture.write(b'LZAF0001' + struct.pack('<I', len(cases)))
        for group, request, result, instructions in cases:
            fixture.write(struct.pack('<II', len(request), len(result)) + request + result)
            ih.update(request)
            oh.update(result)
    dependencies = ('capture_original_collapse_update.py', 'capture_original_debris_update.py',
                    'check_original_collapse_update.py', 'check_original_debris_update.py',
                    'scan_livels_debris_sites.py', 'source_guardrails.py')
    report = dict(schema='lezac.original-collapse-actors.v1', cases=len(cases),
        groups=dict(Counter(case[0] for case in cases)), legacy_crosschecked_cases=2395,
        native_actor_creation_crosschecks=1,
        legacy_metadata_sha256=hashlib.sha256((ROOT / 'tests/gameplay/collapse_update_original.json').read_bytes()).hexdigest(),
        original_exe_sha256=hashlib.sha256(raw).hexdigest(),
        native_fixture_sha256=hashlib.sha256(native.read_bytes()).hexdigest(),
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        dependency_sha256={name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in dependencies},
        relocated_image_sha256=hashlib.sha256(image).hexdigest(),
        input_sha256=ih.hexdigest(), output_sha256=oh.hexdigest(),
        fixture_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest(),
        executor='Unicorn 2.1.4', original_calls_stubbed=False, original_instructions_patched=False,
        original_return_boundaries_verified=True, record_table_initializers_executed=True,
        actor_bytes_compared=38, visual_bytes_compared=8, actors_in_creation_order=True,
        existing_actors_unchanged=True, clean_unused_actor_slots=True, stale_slot_claim=False,
        constructor_context=constructor_context, constructor_context_native_backed=True,
        initial_pool_counts=[0, 1, 28, 29, 30], admission_counts=dict(admissions),
        complete_live_records_maps_rng=True, sound_state_compared=False,
        natural_gameplay=False, compiled_cpp_comparison=False, visual_parity_claim=False,
        whole_game_complete=False, entry_counts=dict(counts), maximum_instructions=max(case[3] for case in cases))
    with args.metadata.open('x', newline='\n') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
