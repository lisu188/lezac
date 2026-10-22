"""Observe complete unchanged original boss/nonplayer/both-player actor passes."""
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
import boss_links_oracle as boss
import nonplayer_loop_oracle as loop
import player_motion_oracle as player
import player_post_oracle as post
from actor_motion_oracle import compact_initial
from actor_steering_oracle import encode_trace
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA = 0x1aa20
SOURCES = (*post.SOURCES, 'frame_actor_pass_oracle.py')
STOPS = {0x1804e: 0, 0x177dc: 1, 0x192e2: 2}
PLAYER = player.profiles()[0]


def require(yes, message):
    if not yes:
        raise ValueError(message)


def profiles():
    rows = []
    def add(family='passes', **changes):
        row = dict(family=family, count=2, states=(1, 1), behavior=-1, expiry='none',
            period=24, flags=0x202, floor=0x200, sp=0x3fe4, waiting=0,
            controls=(0, 0), hp=(100, 100), scores=(0, 0), dirty=2,
            cells=(0, 0, 0, 0), objective=115, copy=False, links=0, link_mode=0)
        row.update(changes)
        rows.append(row)
    for count, states, flags in itertools.product((0, 1, 2, 5, 30),
            itertools.product((0, 1, 2, 255), repeat=2), (0x202, 0x602)):
        add(count=count, states=states, flags=flags)
    for bits, paired, count, flags in itertools.product(range(32), (False, True), (0, 3), (0x202, 0x602)):
        add('both_controls', count=count, controls=(bits, bits if paired else bits ^ 31), flags=flags)
    for behavior, flags in itertools.product(range(7), (0x202, 0x602)):
        add('behavior', count=3, behavior=behavior, flags=flags)
    for count, expiry, flags in itertools.product((2, 5), ('none', 'first', 'last', 'all'), (0x202, 0x602)):
        add('expiry', count=count, expiry=expiry, flags=flags)
    for count, states, waiting, flags in itertools.product((0, 1, 3),
            ((0, 0), (2, 2), (0, 2), (2, 0), (255, 255)), (228, 229, 230, 255), (0x202, 0x602)):
        add('waiting_restart', count=count, states=states, waiting=waiting, flags=flags)
    for links, mode, states, flags in itertools.product((0, 1, 3), (0, 255),
            ((1, 1), (0, 1), (2, 2)), (0x202, 0x602)):
        add('boss_links', count=3, links=links, link_mode=mode, states=states, flags=flags)
    for cells, objective, flags in itertools.product(
            ((103, 0, 0, 0), (115, 115, 0, 0), (117, 0, 117, 0)), (103, 115), (0x202, 0x602)):
        add('shared_tiles', count=2, cells=cells, objective=objective, flags=flags,
            hp=(0, 0) if cells[0] == 117 else (100, 100), dirty=0, scores=(0xfffffff0, 0xfffffff0))
    for score, dirty, flags in itertools.product(
            (0, 1, 9, 10, 99, 100, 9999999, 99999999, 100000000, 0x7fffffff, 0x80000000, 0xffffffff),
            (0, 1, 2), (0x202, 0x602)):
        add('both_scores', count=0, scores=(score, score ^ 0xffffffff), dirty=dirty, flags=flags)
    for a, b, count, flags in itertools.product((0, 1, 100, 200, 201, 255),
            (0, 1, 100, 200, 201, 255), (0, 3), (0x202, 0x602)):
        add('both_health', count=count, hp=(a, b), flags=flags)
    for flags, sp in itertools.product((0x202, 0x602), (0x1fe4, 0x3fe4)):
        add('animation_copies', count=3, copy=True, flags=flags, sp=sp, dirty=0)
    for count, links, states, flags in itertools.product((0, 1, 3), (0, 1), ((1, 1), (0, 0)), (0x202, 0x602)):
        add('stack_fault', count=count, links=links, states=states, floor=65535, flags=flags)
    for states, flags in itertools.product(itertools.product((0, 1, 2), repeat=2), (0x202, 0x602)):
        add('divide_fault', count=1, behavior=4, period=0, states=states, flags=flags)
    return rows


def initial_case(index, row, image, sines):
    memories = []
    for marker in (1, 2):
        base = dict(PLAYER, marker=marker, caller=True, flags=row['flags'], floor=row['floor'],
            controls=tuple((row['controls'][marker - 1] >> bit) & 1 for bit in range(5)),
            energy=row['hp'][marker - 1], current=1 if marker == 1 else 20,
            cells=row['cells'], objective=row['objective'], score=row['scores'][marker - 1],
            capacity=row['count'], animation=3 if row['copy'] else 1,
            initial_animation_copy=row['copy'])
        profile = dict(family='whole_caller', marker=marker, flags=row['flags'], base=base,
            score=base['score'], dirty=row['dirty'], map_length=1024, map_matches=31,
            previous=0, threshold=1024, shape='equal', floor=row['floor'])
        registers, memory, seeds = post.initial_case(index, profile, image)
        memories.append(memory)
        if marker == 1:
            entry, patches = registers, list(seeds)
    def put(address, raw):
        patches.append((address, bytes(raw)))
    def data(offset, raw):
        put(DATA + offset, raw)
    def word(offset, value):
        data(offset, struct.pack('<H', value & 65535))
    for marker, memory in enumerate(memories, 1):
        at = DATA + 0x1b62 + marker * 38
        record = bytearray(memory[at:at + 38])
        record[1] = marker - 1
        put(at, record)
        data(0xc21e + (marker - 1) * 8, struct.pack('<4H', 80, 80, 0, 0))
        controls = 0x1b78 if marker == 1 else 0x1b7d
        data(controls, memory[DATA + controls:DATA + controls + 5])
        score = 0x785a if marker == 1 else 0x7888
        data(score, memory[DATA + score:DATA + score + 46])
    npc = dict(count=row['count'], states=row['states'], behavior=row['behavior'], expiry=row['expiry'],
        dx=40, dy=20, dx2=-30, dy2=-30, sp=row['sp'], flags=row['flags'],
        floor=row['floor'], period=row['period'])
    _, npc_memory, _ = loop.initial_case(index, npc, image)
    for slot in range(1, row['count'] + 1):
        record, visual = 0x1bae + slot * 38, 0xc21e + (slot + 1) * 8
        data(record, npc_memory[DATA + record:DATA + record + 38])
        data(visual, npc_memory[DATA + visual:DATA + visual + 8])
    data(0x79e6, bytes(row['states']))
    data(0x208d, bytes((row['count'],)))
    data(0xc496, bytes((row['count'] + 2,)))
    data(0x79b9, bytes((row['waiting'],)))
    data(0x79ae, bytes(2))
    data(0x79e8, bytes(2))
    data(0x1b6b, bytes((10,)) * 8)
    data(0x1b74, bytes((1, 1)))
    data(0x79f9, bytes((row['links'],)))
    data(0x7bda, sines)
    for link in range(1, row['links'] + 1):
        record = bytearray(16)
        record[:7] = bytes(((link - 1) & 1, link + 1, 3, row['link_mode'], 100, 48, 17 + link))
        struct.pack_into('<2H', record, 7, 1, 2)
        record[15] = 128
        data(0x79ea + link * 16, record)
    put(0x70000 + row['sp'] - 1024, bytes((index * 7 + n * 29 + 11) & 255 for n in range(1056)))
    entry = (*entry[:11], row['sp'], 0x7ebb, row['flags'])
    initial, seeds = compact_initial(image, patches)
    return entry, initial, seeds


def generate(root, out):
    require(unicorn.__version__ == '2.1.4' and not any(key in os.environ for key in
        ('LD_PRELOAD', 'LIBUNICORN_PATH')), 'Unsupported frame actor pass runtime')
    library = Path(uclib._name).resolve(strict=True)
    def mapped():
        return sha(library.read_bytes()) == LIB_SHA and any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines())
    require(mapped(), 'Actual pass library mapping differs')
    sources = {name: sha((root / 'tools' / name).read_bytes()) for name in SOURCES}
    require((root / 'tools/frame_actor_pass_oracle.py').read_bytes() == Path(__file__).read_bytes(),
        'Frame actor pass producer source differs')
    exe = (root / 'LEZAC.EXE').read_bytes()
    require(sha(exe) == EXE_SHA, 'Canonical pass executable differs')
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[mz[4] * 16:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + i * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
    out = out.resolve()
    require(out.is_relative_to(Path('/dev/shm')) and not out.exists(), 'Use a new RAM-only pass capture')
    out.mkdir()
    rows = profiles()
    output = bytearray(b'LZAPAS01' + struct.pack('<I', len(rows)))
    coverage, summaries = Counter(), []
    sines, sine_proof = boss.sine_table(image)
    try:
        for index, row in enumerate(rows):
            entry, initial, seeds = initial_case(index, row, image, sines)
            trace, writes, endpoints, calls = [], [], [], []
            engine, fault = None, None
            visited, counts = set(), Counter()
            post_active = False
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for register, value in zip(REGS, entry):
                    engine.reg_write(register, value)
                fault = None
                def boundary(uc, address, size, user):
                    if address in STOPS:
                        uc.emu_stop()
                        return True
                    return False
                def code(uc, address, size, user):
                    nonlocal post_active
                    if boundary(uc, address, size, user):
                        return
                    r = tuple(uc.reg_read(register) for register in REGS)
                    require((r[7] == 0x1000 and r[12] < 0x83f0) or
                        (r[7] == 0x1920 and r[12] < 0x1820) or
                        (r[7] == 0x18ac and 0x517 <= r[12] < 0x5da),
                        'Pass left declared code: ' + str((r[7], r[12])))
                    if r[7] == 0x1000:
                        if r[12] in (0x7ee1, 0x7f59):
                            marker = struct.unpack('<H', uc.mem_read(DATA + 0x2082, 2))[0]
                            calls.append((len(trace), r[12], marker, r[5], r[11], r[6], r[10]))
                        if r[12] == 0x7f5c:
                            post_active = True
                        if r[12] == 0x8044:
                            counts['post_returns' if post_active else 'prefix_8044_skips'] += 1
                            post_active = False
                    trace.append(r)
                    visited.add(address)
                    counts[address] += 1
                def write(uc, access, address, size, value, user):
                    require(size in (1, 2) and DATA <= address and address + size <= 0xb0001,
                        'Pass write left declared owners')
                    writes.append((address, size, value & ((1 << (size * 8)) - 1)))
                def intr(uc, number, user):
                    nonlocal fault
                    address = uc.reg_read(REGS[7]) * 16 + uc.reg_read(REGS[12])
                    require(number == 0 and address in actor.FAULTS, 'Unexpected pass CPU interrupt')
                    fault = address
                    uc.emu_stop()
                def io(*unused):
                    raise ValueError('Original pass attempted hardware I/O')
                engine.hook_add(unicorn.UC_HOOK_INTR, intr)
                engine.hook_add(unicorn.UC_HOOK_INSN, io, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, io, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                else:
                    for address in STOPS:
                        engine.hook_add(unicorn.UC_HOOK_CODE, boundary, None, address, address)
                engine.emu_start(entry[7] * 16 + entry[12], 0, count=3000000)
                r = tuple(engine.reg_read(register) for register in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                require((r[7] * 16 + r[12] in STOPS or fault in actor.FAULTS) and
                    final[0x10000:DATA] == image[:0xaa20], 'Pass endpoint/code differs')
                endpoints.append((r, final, fault))
                del engine
                engine = None
            require(endpoints[0] == endpoints[1], 'Pass observer changed complete state')
            endpoint, final, fault = endpoints[0]
            outcome = 3 if fault is not None else STOPS[endpoint[7] * 16 + endpoint[12]]
            if outcome < 2:
                require(all(endpoint[n] == entry[n] for n in (6, 10, 11)),
                    'Pass did not restore actual caller SS/SP/BP')
            rebuilt = bytearray(initial)
            for address, size, value in writes:
                rebuilt[address:address + size] = value.to_bytes(size, 'little')
            require(rebuilt == final, 'Pass writes do not reconstruct complete memory')
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
                actor_calls=counts[0x16053], actor_returns=counts[0x17ee4] + counts[0x17f5c],
                nonplayer_calls=counts[0x17ee1], player_calls=counts[0x17f59],
                post_calls=counts[0x17f5c], post_returns=counts['post_returns'],
                prefix_8044_skips=counts['prefix_8044_skips'], boss_calls=counts[0x1432a],
                both_players=int(sum(ip == 0x7f59 for _, ip, *_ in calls) == 2),
                life_loss_paths=int(0x130a3 in visited), vga_writes=sum(a >= 0xa0000 for a, _, _ in writes))
            coverage['outcome_' + str(outcome)] += 1
            summaries.append(dict(index=index, profile=row, outcome=outcome, calls=calls,
                visited=sorted(visited), post_returns=counts['post_returns'],
                prefix_8044_skips=counts['prefix_8044_skips']))
            require(len(output) <= 128 * 1024 * 1024, 'Pass projection exceeds RAM reserve')
            if index % 50 == 0:
                print('frame_actor_pass_capture=' + str(index + 1) + '/' + str(len(rows)), flush=True)
        require(mapped() and sha((root / 'LEZAC.EXE').read_bytes()) == EXE_SHA and
            all(sha((root / 'tools' / name).read_bytes()) == value for name, value in sources.items()),
            'Pass capture inputs changed')
        raw = bytes(output)
        packed = gzip.compress(raw, mtime=0)
        (out / 'oracle.bin.gz').write_bytes(packed)
        manifest = dict(schema='lezac-controlled-frame-actor-pass-v1', coverage=dict(coverage),
            asset_sha256={'LEZAC.EXE': EXE_SHA}, source_sha256=sources, boss_sine_initializer=sine_proof,
            projection_bytes=len(raw), projection_sha256=sha(raw), compressed_bytes=len(packed),
            compressed_sha256=sha(packed), unicorn_version=unicorn.__version__,
            unicorn_library_sha256=LIB_SHA, actual_library_mapping_verified=True,
            observer_control='register-write-trace-versus-stop-only-hooks',
            complete_memory_observer_control=True, ordered_writes_reconstruct_memory=True,
            original_code_bytes_verified=43552, instruction_patches=0, calls_stubbed=0, hardware_io=0,
            cpu_divide_faults_observed=coverage['outcome_3'], divide_fault_handler_executed=False,
            interrupts_delivered=0, later_state_injected=False, production_app_comparison=False,
            natural_capture=False, full_frame_claim=False, raw_memory_published=False)
        (out / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        (out / 'checkpoints.json').write_text(json.dumps(summaries, sort_keys=True, indent=2) + '\n')
        print(json.dumps(manifest, sort_keys=True), flush=True)
    except Exception as error:
        failure = dict(index=index, profile=row, error=str(error), sources=sources)
        if engine is not None:
            (out / 'failed-current-ram.bin').write_bytes(engine.mem_read(0, 1048576))
        for number, (registers, memory, fault) in enumerate(endpoints):
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
