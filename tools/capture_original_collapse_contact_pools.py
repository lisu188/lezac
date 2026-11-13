"""Observe moving collapse contacts with complete physical storage."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import traceback

INPUT_BYTES, STATE_BYTES = 26727, 26721
HELPER_SHA = 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c'
BANK_READER_SHA = '50cd6bc4d44a9d805b2598d89b7c626a34c0eb5339b8350b8f8125ffa6c74c73'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def module(path, pin, name):
    raw = path.read_bytes()
    assert sha(raw) == pin
    scope = {'__file__': str(path), '__name__': name}
    exec(compile(raw, str(path), 'exec'), scope)
    return scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out-directory', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path, required=True)
    args = parser.parse_args()
    out = args.out_directory.resolve()
    assert not out.exists() and os.environ['SDL_AUDIODRIVER'] == 'dummy' and not sys.flags.optimize
    out.mkdir()
    sys.path.insert(0, str(args.unicorn_path))
    helper = module(args.root / 'tools/original_bomb_cpu.py', HELPER_SHA, 'contact_pool_cpu')
    reader = module(args.root / 'tools/capture_original_fracture_retirement.py', BANK_READER_SHA, 'contact_bank_reader')
    import unicorn
    from unicorn import x86_const as regs
    observed, neutral = helper['BombCPU'](args.root), helper['BombCPU'](args.root)
    tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
        ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
    visits, totals, writes, guard_writes = Counter(), Counter(), Counter(), []
    enabled = False
    anchors = {0x1552c: 'increment_rest', 0x15602: 'normal_writeback', 0x1566c: 'timer_remove',
        0x1508b: 'remove', 0x1557b: 'fracture', 0x12f9f: 'actor_constructor', 0x1370e: 'seed'}

    def code(cpu, address, size, _):
        if enabled and address in anchors:
            visits[anchors[address]] += 1

    def memory(cpu, access, address, size, value, _):
        if enabled:
            for byte in range(size):
                at = address + byte - observed.DATA
                if 0x292b <= at < 0x292b + 1402 * 11:
                    writes['debris:' + str((at - 0x292b) % 11)] += 1
                if 0x6620 <= at < 0x6620 + 251 * 15:
                    writes['collapse:' + str((at - 0x6620) % 15)] += 1
            if address < observed.DATA + 0x6569 and address + size > observed.DATA + 0x655e:
                guard_writes.append(dict(ip=cpu.reg_read(regs.UC_X86_REG_IP),
                    offset=address - observed.DATA, bytes=size, value=value))

    observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)
    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory)
    capacities = ((1, 2, 0), (1400, 249, 94), (1401, 250, 255))
    cases = [(direction, target, capacity, actors)
        for direction in ('right', 'left', 'down', 'up')
        for target in ('hard', 'debris', 'collapse', 'unflagged')
        for capacity in capacities for actors in (0, 30)]
    assert len(cases) == 96
    requests, results, chain = [], [], hashlib.sha256()
    report = dict(schema='lezac.original-collapse-contact-pools.v1', passed=False,
        recorded_utc=datetime.now(timezone.utc).isoformat(), producer_sha256=sha(Path(__file__).read_bytes()),
        executor_sha256=HELPER_SHA, bank_reader_sha256=BANK_READER_SHA,
        original_exe_sha256=sha(observed.raw), original_instructions_patched=False,
        original_calls_stubbed=False, hardware_io_permitted=False,
        observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
        physical_debris_records=1402, physical_collapse_records=251, includes_capacity_guards=True,
        debris_guard_aliases_contact_words=True, debris_guard_unchanged_claim=False,
        complete_actor_bank_bytes=1575, complete_sound_bytes=7,
        existing_fragments_not_advanced=True, initial_fragment_terrain_ownership_claim=False,
        actual_app_comparison=False, seeded=True, natural_route=False, whole_game_claim=False, cases=[])
    try:
        for index, (direction, target, (initial_debris, count, timer), actor_count) in enumerate(cases):
            report['current_case'] = dict(index=index, direction=direction, target=target,
                initial_debris=initial_debris, collapse_count=count, actor_count=actor_count)
            first, last = 25 * 60 + 30, 25 * 60 + 31
            dx, dy = {'right': (96, 0), 'left': (-96, 0), 'down': (0, 96), 'up': (0, -96)}[direction]
            touch = {'right': last + 1, 'left': first - 1, 'down': first + 60, 'up': first - 60}[direction]
            target_first = touch - 1 if direction == 'left' else touch
            target_vx = -dx
            target_vy = 0 if direction == 'down' else -dy
            inputs, outputs, snapshots = [], [], []
            visits.clear()
            guard_writes.clear()
            for executor in (observed, neutral):
                cpu, base = executor.cpu, executor.DATA
                cpu.context_restore(executor.initial_context)
                cpu.mem_write(0, executor.initial_memory)
                cpu.mem_write(0x40000, bytes(65536))
                cpu.mem_write(0x50000, bytes(65536))
                actors = [bytearray((19 + slot * 17 + byte * 29) & 255 for byte in range(38)) for slot in range(31)]
                actors[0][1] = 1
                visuals = [bytearray((19 + row * 31 + byte * 13) & 255 for byte in range(8)) for row in range(33)]
                visuals[32][4:] = executor.descriptors[:4]
                for slot in range(1, actor_count + 1):
                    actor = actors[slot]
                    actor[0], actor[1], actor[2], actor[20], actor[21] = 11, slot + 1, 8, 0, 5
                    actor[6:14] = bytes(8)
                    actor[22:29] = bytes((74, 74, 79, 2, 2, 1, 1))
                    actor[29:36] = bytes((43, 43, 46, 2, 2, 2, 255))
                    visuals[slot + 1][:4] = struct.pack('<HH', slot * 3, slot * 5)
                    visuals[slot + 1][4:] = executor.descriptors[74 * 4:75 * 4]
                links = bytearray((19 + byte * 19) & 255 for byte in range(128))
                links[15] = 0
                collapse = bytearray((31 + byte * 23) & 255 for byte in range(251 * 15))
                debris = bytearray((17 + byte * 13) & 255 for byte in range(1402 * 11))
                for slot in range(initial_debris):
                    debris[slot * 11:(slot + 1) * 11] = struct.pack('<HHbbbbBBB',
                        slot % 1980, 0xc001 + slot, (slot % 31) - 15, (slot % 61) - 30,
                        (slot % 127) - 63, (slot % 125) - 62, slot % 94, 0x47, (slot * 13 + 17) & 255)
                for slot in range(count):
                    cell = (2 + 2 * (slot // 28)) * 60 + 2 + 2 * (slot % 28)
                    vx, vy, subx, suby, magnitude, rest = 0, 0, 0, 0, 0, 0
                    if slot == 0 and target == 'collapse':
                        cell, vx, vy = target_first, target_vx, target_vy
                        magnitude = abs(vx) + abs(vy)
                    if slot == count - 1:
                        cell, vx, vy = first, dx, dy
                        subx, suby = (100 if dx > 0 else -100 if dx < 0 else 0), (100 if dy > 0 else -100 if dy < 0 else 0)
                        magnitude, rest = 96, timer
                    collapse[15 * slot:15 * slot + 15] = struct.pack('<HHHbbbbHBBB',
                        cell * 2, (cell + 1) * 2, 0x8001 + slot, vx, vy, subx, suby, magnitude, 0x83, rest, 2)
                    for own in (cell, cell + 1):
                        cpu.mem_write(0x40000 + own, b'\x60')
                        cpu.mem_write(0x50000 + own * 2, struct.pack('<H', 0x8001 + slot))
                        if bytes(cpu.mem_read(0x40000 + own + 60, 1)) == b'\x00':
                            cpu.mem_write(0x40000 + own + 60, b'\x01')
                if target != 'collapse':
                    word = {'hard': 0, 'debris': 0xc001, 'unflagged': 0x0190}[target]
                    cpu.mem_write(0x40000 + touch, b'\x47' if target == 'debris' else b'\x60' if word else b'\x01')
                    cpu.mem_write(0x50000 + touch * 2, struct.pack('<H', word))
                    if target == 'debris':
                        debris[:11] = struct.pack('<HHbbbbBBB', touch, word, target_vx, target_vy, 0, 0, 0, 0x47, 0x9a)
                tick, rng, priority = (2, 0xffffffff, 5) if actor_count else (0, 0x12345678, 0)
                for offset, raw in ((0xc1e0, struct.pack('<HH', 0, 0x4000)), (0xc1fe, struct.pack('<H', 0x4000)),
                        (0x6612, struct.pack('<HH', 0, 0x5000)), (0x206e, struct.pack('<H', 0x5000)),
                        (0xc204, struct.pack('<HH', 60, 33)),
                        (0x207a, struct.pack('<4H', 0x6620, 0x209e, 199 + initial_debris, count)),
                        (0x1afa, bytes(2)), (0x1afe, struct.pack('<I', rng)),
                        (0x78c2, struct.pack('<4H', tick, 0x4000, 0, 0)), (0x6620, collapse), (0x292b, debris),
                        (0x1bae, b''.join(actors)), (0xc21e, b''.join(visuals)), (0x79ea, links),
                        (0xc322, executor.descriptors), (0x208d, bytes((actor_count,))),
                        (0xc496, bytes((actor_count + 2,))), (0x2072, struct.pack('<H', 0x55aa)),
                        (0x2074, struct.pack('<H', 0xab12)), (0x799f, b'\x5a'),
                        (0x799e, bytes((priority,))), (0x78c0, struct.pack('<H', 0xbeef)), (0x79c4, b'\x01')):
                    cpu.mem_write(base + offset, bytes(raw))
                request = struct.pack('<HHHIHHHH', 60, 33, tick, rng, initial_debris, count, 0, 0x4000)
                request += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
                request += bytes(cpu.mem_read(base + 0x292b, 1402 * 11)) + bytes(cpu.mem_read(base + 0x6620, 251 * 15))
                request += reader['bank'](executor) + reader['sound'](executor)
                inputs.append(request)
                executor.registers(0xf000, 0xff00)
                cpu.mem_write(0x8ff00, struct.pack('<H', 0xff00))
                enabled = executor is observed
                cpu.emu_start(0x15102, 0x1ff00, count=4000000)
                enabled = False
                executor.assert_return(0xff00, 0xf000, 0xff02)
                snapshots.append(bytes(cpu.mem_read(0, 1024**2)))
                bound, live = struct.unpack('<HH', bytes(cpu.mem_read(base + 0x207e, 4)))
                result = bytes(cpu.mem_read(base + 0x1afe, 4)) + struct.pack('<HH', bound - 199, live)
                result += bytes(cpu.mem_read(base + 0x78c8, 2)) + bytes(cpu.mem_read(base + 0x78c4, 2))
                result += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
                result += bytes(cpu.mem_read(base + 0x292b, 1402 * 11)) + bytes(cpu.mem_read(base + 0x6620, 251 * 15))
                result += reader['bank'](executor) + reader['sound'](executor)
                outputs.append(result)
            assert inputs[0] == inputs[1] and outputs[0] == outputs[1] and snapshots[0] == snapshots[1]
            assert [observed.cpu.reg_read(r) for r in tracked] == [neutral.cpu.reg_read(r) for r in tracked]
            live_debris, live_collapse = struct.unpack_from('<HH', outputs[0], 4)
            assert live_debris <= 1401 and live_collapse <= 250 and visits['increment_rest'] == count
            assert visits['fracture'] == visits['actor_constructor']
            for start, length in ((5952 + 1402 * 11 + 250 * 15, 15),):
                assert outputs[0][start:start + length] == inputs[0][start + 6:start + 6 + length], (
                    start, inputs[0][start + 6:start + 6 + length].hex(), outputs[0][start:start + length].hex(), dict(visits))
            chain.update(hashlib.sha256(snapshots[0]).digest())
            requests.append(inputs[0]); results.append(outputs[0]); totals.update(visits)
            report['cases'].append(dict(index=index, direction=direction, target=target,
                initial_debris=initial_debris, collapse_count=count, actor_count=actor_count,
                subject_slot=count - 1, subject_timer=timer, target_cell=touch,
                resulting_debris=live_debris, resulting_collapse=live_collapse,
                debris_guard_input=inputs[0][21369:21380].hex(),
                debris_guard_output=outputs[0][21363:21374].hex(),
                debris_guard_writes=list(guard_writes),
                visits=dict(visits), input_sha256=sha(inputs[0]), output_sha256=sha(outputs[0])))
        assert all(len(raw) == INPUT_BYTES for raw in requests)
        assert all(len(raw) == STATE_BYTES for raw in results)
        fixture = b'LZFC0001' + struct.pack('<II', len(cases), INPUT_BYTES + STATE_BYTES)
        fixture += b''.join(request + result for request, result in zip(requests, results))
        packed = gzip.compress(fixture, mtime=0)
        expected = b'LZFP0001' + struct.pack('<II', len(cases), STATE_BYTES) + b''.join(results)
        (out / 'collapse_contact_pools_original.bin.gz').write_bytes(packed)
        (out / 'expected.bin').write_bytes(expected)
        report.update(passed=True, total_cases=len(cases), state_bytes=len(cases) * STATE_BYTES,
            original_visits=dict(totals), fixture_bytes=len(fixture), fixture_sha256=sha(fixture),
            fixture_gzip_bytes=len(packed), fixture_gzip_sha256=sha(packed), expected_sha256=sha(expected),
            full_memory_repeat_hash_chain=chain.hexdigest(), physical_write_offsets=dict(writes))
    except BaseException:
        report['error'] = traceback.format_exc()
        for position, raw in enumerate(inputs):
            (out / ('failure-input-' + str(position) + '.bin')).write_bytes(raw)
        for position, raw in enumerate(outputs):
            (out / ('failure-output-' + str(position) + '.bin')).write_bytes(raw)
        for position, raw in enumerate(snapshots):
            (out / ('failure-ram-' + str(position) + '.bin.gz')).write_bytes(gzip.compress(raw, mtime=0))
        raise
    finally:
        (out / 'capture.json').write_text(json.dumps(report, indent=2) + '\n')
        assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < 8 * 1024**2
        print(json.dumps({key: value for key, value in report.items() if key not in ('cases', 'physical_write_offsets')}), flush=True)


if __name__ == '__main__':
    main()
