"""Observe unchanged original player health/life/score HUD and signed RTL divide."""
import argparse
from collections import Counter
import gzip
import itertools
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

import actor_update_oracle as actor
import player_motion_oracle as player
from actor_motion_oracle import compact_initial
from actor_steering_oracle import encode_trace
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA = 0x1aa20
SOURCES = (*actor.SOURCES, 'player_post_oracle.py')
STOPS = (0x18044, 0x17f00, 0x192e2)


def require(yes, message):
    if not yes:
        raise ValueError(message)


def profiles():
    rows = []
    def add(family='post', **changes):
        row = dict(family=family, marker=1, hp=100, damage=0, behavior=0, mirror=100,
            dirty=2, score=0, shape='equal', flags=0x202, map_length=64,
            map_matches=31, previous=0, threshold=64, floor=0x200, sp=0x3fe4,
            numerator=0, divisor=10, return_ip=0x7f00)
        row.update(changes)
        rows.append(row)
    for marker, hp, damage in itertools.product((1, 2), range(256), (0, 1, 255)):
        add(marker=marker, hp=hp, damage=damage, mirror=0)
    for marker, hp, damage, mirror, flags in itertools.product((1, 2), (0, 1, 100, 200, 201, 255),
            (0, 1, 100, 255), (0, 255), (0x202, 0x602)):
        add(marker=marker, hp=hp, damage=damage, mirror=mirror, behavior=2, flags=flags)
    scores = (0, 1, 9, 10, 99, 100, 9999999, 99999999, 100000000, 0x7fffffff, 0x80000000, 0xffffffff)
    for marker, score, dirty, shape, flags in itertools.product((1, 2), scores, (0, 1, 2),
            ('equal', 'lagging', 'wrap', 'alternating'), (0x202, 0x602)):
        add(marker=marker, score=score, dirty=dirty, shape=shape, flags=flags)
    for marker, flags, length in itertools.product((1, 2), (0x202, 0x602), (0, 1, 64, 65535)):
        add(marker=marker, hp=0, damage=1, flags=flags, map_length=length, map_matches=17)
    for marker, previous, matches, threshold in itertools.product((1, 2), (0, 65535),
            (0, 1, 63, 64), (0, 64, 65535)):
        add(marker=marker, hp=0, damage=1, previous=previous, map_matches=matches, threshold=threshold)
    for marker, flags, dirty, dying in itertools.product((1, 2), (0x202, 0x602), (0, 1, 2), (False, True)):
        add(marker=marker, flags=flags, dirty=dirty, hp=0 if dying else 100,
            damage=1 if dying else 0, floor=65535)
    selected = {'real_caller', 'pickup_score_carry', 'fire_super', 'empty_weapon_switch',
        'backward_animation_copy', 'fracture_above', 'objective_counter'}
    for base in player.profiles():
        if base['family'] in selected:
            add('whole_caller' if base['caller'] else 'whole_direct', marker=base['marker'],
                flags=base['flags'], score=base['score'], dirty=0, map_length=1024, base=base)
    for marker, flags in itertools.product((1, 2), (0x202, 0x602)):
        base = dict(player.profiles()[0], marker=marker, flags=flags, energy=0,
            cells=(117, 0, 117, 0), flame_mass=1)
        add('whole_direct', marker=marker, flags=flags, dirty=0, map_length=1024, base=base)
    numerators = (0, 1, -1, 9, -9, 10, -10, 32767, 32768, 65535, 65536,
        0x7fffffff, 0x80000000, 0x80000001, 0xffff0000)
    divisors = (0, 1, -1, 2, -2, 10, -10, 65535, 65536, 0x7fffffff, 0x80000000)
    for numerator, divisor, flags, return_ip in itertools.product(numerators, divisors,
            (0x202, 0x602), (0x7f00, 0x8044)):
        add('divide', numerator=numerator, divisor=divisor, flags=flags, return_ip=return_ip)
    return rows


def initial_case(index, row, image):
    marker = row['marker']
    if row['family'].startswith('whole'):
        family = 'player_caller' if row['family'] == 'whole_caller' else 'player_direct'
        entry, initial, patches = actor.initial_case(index, family, row['base'], image)
    else:
        entry = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3fdc,
            0x1000, 0x1aa2, 0x40, 0x7000, row['sp'], 0x7f5c, row['flags'])
        patches = []
    def put(address, raw):
        patches.append((address, bytes(raw)))
    def data(offset, raw):
        put(DATA + offset, raw)
    def word(offset, value):
        data(offset, struct.pack('<H', value & 65535))
    if row['family'] == 'divide':
        sp = row['sp'] - 4
        put(0x70000 + sp, struct.pack('<2H', row['return_ip'], 0x1000))
        n, d = row['numerator'] & 0xffffffff, row['divisor'] & 0xffffffff
        entry = (n & 65535, d >> 16, d & 65535, n >> 16, 0x1357, 0x2468, 0x3fdc,
            0x1920, 0x1aa2, 0x40, 0x7000, sp, 0x945, row['flags'])
        initial, seeds = compact_initial(image, patches)
        return entry, initial, seeds
    word(0x2082, marker)
    word(0x2084, 46)
    word(0x2070, 0x4000)
    word(0x79f4, 0)
    word(0x79f6, 160)
    word(0x1afa, row['floor'])
    word(0xc1fe, 0x4000)
    word(0x78ba, row['map_length'])
    word(0x2088, row['previous'])
    word(0x2086, row['threshold'])
    data(0x6c, bytes((38, 39)))
    data(0x799e, b'\0')
    data(0x79c4, b'\0')
    data(0x4000, bytes((n * 7 + 3) & 255 for n in range(1024)))
    if not row['family'].startswith('whole'):
        data(0x79b4, b'\x73')
        data(0x79e7 + marker, bytes((row['damage'],)))
        data(0x79eb + marker, bytes((row['mirror'],)))
        record = bytearray(38)
        record[:2] = bytes((marker, marker))
        record[21] = row['behavior']
        record[22:29] = bytes((2, 2, 3, 1, 2, 1, 1))
        record[36] = row['hp']
        data(0x1b62 + marker * 38, record)
    data(0x79b4, bytes((row.get('base', {}).get('objective', 115),)))
    length = row['map_length'] or 65536
    plane = bytearray(length)
    plane[:min(row['map_matches'], length)] = bytes((115,)) * min(row['map_matches'], length)
    put(0x40000, plane)
    if row['family'].startswith('whole'):
        for cell, value in zip((715, 716, 780, 779), row['base']['cells']):
            put(0x40000 + cell, bytes((value,)))
    base = 0x785a if marker == 1 else 0x7888
    record = bytearray(46)
    struct.pack_into('<I', record, 0, row['score'])
    for digit in range(9):
        target = (0x4000 + (digit % 10) * 64) & 65535
        current = target
        if row['shape'] == 'lagging':
            current = 0x4000
        elif row['shape'] == 'wrap':
            current = (0x4000 - 8) & 65535
        elif row['shape'] == 'alternating':
            current = target if digit & 1 else (target + 632) & 65535
        struct.pack_into('<H', record, 4 + digit * 2, current)
        struct.pack_into('<H', record, 24 + digit * 2, target)
    record[44] = row['dirty']
    data(base, record)
    if not row['family'].startswith('whole'):
        put(0x70000 + row['sp'] - 256, bytes((n * 29 + index * 7 + 11) & 255 for n in range(288)))
    initial, seeds = compact_initial(image, patches)
    return entry, initial, seeds


def generate(root, out):
    require(unicorn.__version__ == '2.1.4' and not any(key in os.environ for key in
        ('LD_PRELOAD', 'LIBUNICORN_PATH')), 'Unsupported player post runtime')
    library = Path(uclib._name).resolve(strict=True)
    def mapped():
        return sha(library.read_bytes()) == LIB_SHA and any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines())
    require(mapped(), 'Actual player post library mapping differs')
    sources = {name: sha((root / 'tools' / name).read_bytes()) for name in SOURCES}
    require((root / 'tools/player_post_oracle.py').read_bytes() == Path(__file__).read_bytes(),
        'Player post producer source differs')
    exe = (root / 'LEZAC.EXE').read_bytes()
    require(sha(exe) == EXE_SHA, 'Canonical player post executable differs')
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[mz[4] * 16:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + i * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
    out = out.resolve()
    require(out.is_relative_to(Path('/dev/shm')) and not out.exists(), 'Use a new RAM-only post capture')
    out.mkdir()
    rows = profiles()
    output = bytearray(b'LZPST001' + struct.pack('<I', len(rows)))
    coverage, summaries = Counter(), []
    try:
        for index, row in enumerate(rows):
            entry, initial, seeds = initial_case(index, row, image)
            trace, writes, visited, endpoints = [], [], set(), []
            stop = None
            engine = None
            prefix_skips = 0
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for register, value in zip(REGS, entry):
                    engine.reg_write(register, value)
                post_seen = False
                def boundary(uc, address, size, user):
                    nonlocal stop, post_seen, prefix_skips
                    if address == 0x17f5c:
                        post_seen = True
                    if address not in STOPS:
                        return False
                    if address == 0x18044 and row['family'] == 'whole_caller' and not post_seen:
                        if observed:
                            prefix_skips += 1
                        return False
                    stop = address
                    uc.emu_stop()
                    return True
                def code(uc, address, size, user):
                    if boundary(uc, address, size, user):
                        return
                    r = tuple(uc.reg_read(register) for register in REGS)
                    require((r[7] == 0x1000 and r[12] < 0x83f0) or
                        (r[7] == 0x1920 and r[12] < 0x1820) or
                        (r[7] == 0x18ac and 0x517 <= r[12] < 0x5da),
                        'Player post left declared code: ' + str((r[7], r[12])))
                    trace.append(r)
                    visited.add(address)
                def write(uc, access, address, size, value, user):
                    require(size in (1, 2) and DATA <= address and address + size <= 0xb0001,
                        'Player post write left declared owners')
                    writes.append((address, size, value & ((1 << (size * 8)) - 1)))
                def forbidden(*unused):
                    raise ValueError('Original player post attempted I/O or interrupt')
                engine.hook_add(unicorn.UC_HOOK_INTR, forbidden)
                engine.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, forbidden, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                else:
                    for address in (*STOPS, 0x17f5c):
                        engine.hook_add(unicorn.UC_HOOK_CODE, boundary, None, address, address)
                engine.emu_start(entry[7] * 16 + entry[12], 0, count=3000000)
                r = tuple(engine.reg_read(register) for register in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                require(r[7] * 16 + r[12] in STOPS and final[0x10000:DATA] == image[:0xaa20],
                    'Player post endpoint/code differs')
                endpoints.append((r, final))
                del engine
                engine = None
            require(endpoints[0] == endpoints[1], 'Player post observer changed complete state')
            endpoint, final = endpoints[0]
            error = endpoint[7] * 16 + endpoint[12] == 0x192e2
            outcome = 2 if error else 1 if row['family'] == 'divide' else 0
            if not error:
                require(endpoint[10] == entry[10] and endpoint[6] == entry[6] and
                    endpoint[11] == (entry[11] + (4 if row['family'] == 'divide' else 6 if entry[12] == 0x6053 else 0)) & 65535,
                    'Player post did not restore actual caller SS/SP/BP')
            if row['family'].startswith('whole') and not error:
                require({0x16053, 0x17780, 0x17f5c}.issubset(visited), 'Whole actor/post continuation missing')
            rebuilt = bytearray(initial)
            for address, size, value in writes:
                rebuilt[address:address + size] = value.to_bytes(size, 'little')
            require(rebuilt == final, 'Player post writes do not reconstruct complete memory')
            trace.append(endpoint)
            output.extend(struct.pack('<IB13HI13HI', index, outcome, *entry, *endpoint))
            output.extend(struct.pack('<I', len(seeds)))
            for address, raw in seeds:
                output.extend(struct.pack('<II', address, len(raw)) + raw)
            encode_trace(output, trace)
            output.extend(struct.pack('<I', len(writes)))
            for item in writes:
                output.extend(struct.pack('<IBH', *item))
            output.extend(struct.pack('<I', 0))
            coverage.update(cases=1, register_states=len(trace), ordered_writes=len(writes),
                whole_actor_paths=int(0x16053 in visited), actual_player_calls=int(0x17f59 in visited),
                whole_life_loss_paths=int(0x16053 in visited and 0x130a3 in visited),
                prefix_8044_skips=prefix_skips,
                life_loss_paths=int(0x130a3 in visited), score_format_paths=int(0x111b0 in visited),
                font_paths=int(0x11156 in visited), signed_divide_paths=int(0x19b45 in visited),
                vga_writes=sum(address >= 0xa0000 for address, size, value in writes))
            coverage['outcome_' + str(outcome)] += 1
            summaries.append(dict(index=index, profile=row, outcome=outcome, prefix_8044_skips=prefix_skips, visited=sorted(visited)))
            if index % 100 == 0:
                print('player_post_capture=' + str(index + 1) + '/' + str(len(rows)), flush=True)
        require(mapped() and sha((root / 'LEZAC.EXE').read_bytes()) == EXE_SHA and
            all(sha((root / 'tools' / name).read_bytes()) == value for name, value in sources.items()),
            'Player post capture inputs changed')
        raw = bytes(output)
        packed = gzip.compress(raw, mtime=0)
        (out / 'oracle.bin.gz').write_bytes(packed)
        manifest = dict(schema='lezac-controlled-player-post-v1', coverage=dict(coverage),
            asset_sha256={'LEZAC.EXE': EXE_SHA}, source_sha256=sources,
            projection_bytes=len(raw), projection_sha256=sha(raw), compressed_bytes=len(packed),
            compressed_sha256=sha(packed), unicorn_version=unicorn.__version__,
            unicorn_library_sha256=LIB_SHA, actual_library_mapping_verified=True,
            complete_memory_observer_control=True, ordered_writes_reconstruct_memory=True,
            original_code_bytes_verified=43552, instruction_patches=0, calls_stubbed=0,
            hardware_io=0, interrupts_delivered=0, later_state_injected=False,
            production_app_comparison=False, natural_capture=False, full_frame_claim=False,
            raw_memory_published=False)
        manifest['observer_control'] = 'register-write-trace-versus-stop-only-hooks'
        (out / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        (out / 'checkpoints.json').write_text(json.dumps(summaries, sort_keys=True, indent=2) + '\n')
        print(json.dumps(manifest, sort_keys=True), flush=True)
    except Exception as error:
        failure = dict(index=index, profile=row, error=str(error), sources=sources)
        if engine is not None:
            (out / 'failed-current-ram.bin').write_bytes(engine.mem_read(0, 1048576))
        for number, (registers, memory) in enumerate(endpoints):
            (out / ('failed-endpoint-' + str(number) + '.bin')).write_bytes(memory)
            failure['endpoint_' + str(number)] = registers
        (out / 'failed-initial.bin').write_bytes(initial)
        (out / 'failed.json').write_text(json.dumps(failure, indent=2) + '\n')
        (out / 'partial-corpus.bin').write_bytes(output)
        (out / 'producer-at-failure.py').write_bytes(Path(__file__).read_bytes())
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.root, args.out)
