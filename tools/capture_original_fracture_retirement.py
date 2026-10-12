"""Capture complete original fracture-retirement physical banks without stubs."""
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

HELPER_SHA = 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c'
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
INPUT_BYTES, STATE_BYTES = 7670, 7664


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bank(executor):
    cpu, base = executor.cpu, executor.DATA
    raw = bytes(cpu.mem_read(base + 0x1bae, 31 * 38))
    raw += bytes(cpu.mem_read(base + 0xc21e, 33 * 8))
    raw += bytes(cpu.mem_read(base + 0x79ea, 8 * 16))
    for offset, size in ((0x208d, 1), (0xc496, 1), (0x79f9, 1), (0x2072, 2)):
        raw += bytes(cpu.mem_read(base + offset, size))
    assert len(raw) == 1575
    return raw


def sound(executor):
    cpu, base = executor.cpu, executor.DATA
    return b''.join(bytes(cpu.mem_read(base + offset, size)) for offset, size in
        ((0x2074, 2), (0x799f, 1), (0x799e, 1), (0x78c0, 2), (0x79c4, 1)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out-directory', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path)
    args = parser.parse_args()
    out = args.out_directory.resolve()
    assert not out.exists() and os.environ['SDL_AUDIODRIVER'] == 'dummy' and not sys.flags.optimize
    out.mkdir()
    if args.unicorn_path:
        sys.path.insert(0, str(args.unicorn_path.resolve()))
    helper_path = args.root / 'tools/original_bomb_cpu.py'
    helper = helper_path.read_bytes()
    assert sha(helper) == HELPER_SHA
    scope = {'__file__': str(helper_path), '__name__': 'fracture_retirement_original'}
    exec(compile(helper, str(helper_path), 'exec'), scope)
    import unicorn
    from unicorn import x86_const as regs
    observed, neutral = scope['BombCPU'](args.root), scope['BombCPU'](args.root)
    assert sha(observed.raw) == EXE_SHA
    tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
        ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
    visits, writes = Counter(), Counter()
    anchors = {0x1552c: 'increment_rest', 0x15602: 'normal_writeback', 0x1566c: 'timer_remove',
        0x1508b: 'remove', 0x1557b: 'fracture', 0x12f9f: 'actor_constructor', 0x1370e: 'seed'}
    enabled = False

    def code(cpu, address, size, _):
        if enabled and address in anchors:
            visits[anchors[address]] += 1

    def memory(cpu, access, address, size, value, _):
        if enabled:
            for byte in range(size):
                at = address + byte - observed.DATA - 0x6620
                if 0 <= at < 75:
                    writes[(at // 15, at % 15, cpu.reg_read(regs.UC_X86_REG_IP))] += 1

    observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)
    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory)
    cases = [(count, mask, timer, flags, tick, actors, priority)
        for count in (1, 2) for mask in range(1, 1 << count)
        for timer in (0, 94, 255) for flags in (0, 0x83) for tick in (0, 2)
        for actors in (0, 29, 30) for priority in (0, 5)]
    assert len(cases) == 288
    report = dict(schema='lezac.original-fracture-retirement.v1', passed=False,
        recorded_utc=datetime.now(timezone.utc).isoformat(), producer_sha256=sha(Path(__file__).read_bytes()),
        executor_sha256=HELPER_SHA, original_exe_sha256=EXE_SHA,
        original_instructions_patched=False, original_calls_stubbed=False, hardware_io_permitted=False,
        observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
        physical_debris_records=5, physical_collapse_records=5, complete_actor_bank_bytes=1575,
        complete_sound_request_latch_bytes=7, actual_app_comparison=False,
        seeded=True, natural_route=False, whole_game_claim=False, cases=[])
    requests, results, chain, totals = [], [], hashlib.sha256(), Counter()
    try:
        for index, (count, mask, timer, flags, tick, actor_count, priority) in enumerate(cases):
            inputs, outputs, snapshots = [], [], []
            visits.clear()
            for executor in (observed, neutral):
                cpu, base = executor.cpu, executor.DATA
                cpu.context_restore(executor.initial_context)
                cpu.mem_write(0, executor.initial_memory)
                cpu.mem_write(0x40000, bytes(65536))
                cpu.mem_write(0x50000, bytes(65536))
                salt = (actor_count * 11 + 19) & 255
                actors = [bytearray((salt + slot * 17 + byte * 29) & 255 for byte in range(38)) for slot in range(31)]
                actors[0][1] = 1
                visuals = [bytearray((salt + row * 31 + byte * 13) & 255 for byte in range(8)) for row in range(33)]
                visuals[32][4:] = executor.descriptors[:4]
                for slot in range(1, actor_count + 1):
                    actor = actors[slot]
                    actor[0], actor[1], actor[2], actor[20], actor[21] = 11, slot + 1, 8, 0, 5
                    actor[6:14] = bytes(8)
                    actor[22:29] = bytes((74, 74, 79, 2, 2, 1, 1))
                    actor[29:36] = bytes((43, 43, 46, 2, 2, 2, 255))
                    visuals[slot + 1][:4] = struct.pack('<HH', slot * 3, slot * 5)
                    visuals[slot + 1][4:] = executor.descriptors[74 * 4:75 * 4]
                links = bytearray((salt + byte * 19) & 255 for byte in range(128))
                links[15] = 0
                collapse = bytearray((salt + byte * 23) & 255 for byte in range(75))
                debris = bytes((salt + byte * 13) & 255 for byte in range(55))
                for slot in range(count):
                    cell = 762 + 5 * slot
                    fracture = bool(mask & (1 << slot))
                    collapse[15 * slot:15 * slot + 15] = struct.pack('<HHHbbbbHBBB',
                        cell * 2, (cell + 1) * 2, 0x8001 + slot, 0, 64 if fracture else 0,
                        0, 100 if fracture else 0, 64 if fracture else 0, flags, timer if fracture else 93, 4)
                    for own in (cell, cell + 1):
                        cpu.mem_write(0x40000 + own, b'\x60')
                        cpu.mem_write(0x50000 + own * 2, struct.pack('<H', 0x8001 + slot))
                        cpu.mem_write(0x40000 + own + 60, b'\x01')
                rng = (0x12345678, 0xffffffff)[tick // 2]
                for offset, raw in ((0xc1e0, struct.pack('<HH', 0, 0x4000)), (0xc1fe, struct.pack('<H', 0x4000)),
                        (0x6612, struct.pack('<HH', 0, 0x5000)), (0x206e, struct.pack('<H', 0x5000)),
                        (0xc204, struct.pack('<HH', 60, 33)), (0x207a, struct.pack('<4H', 0x6620, 0x209e, 199, count)),
                        (0x1afa, bytes(2)), (0x1afe, struct.pack('<I', rng)),
                        (0x78c2, struct.pack('<4H', tick, 0x4000, 0, 0)), (0x6620, collapse), (0x292b, debris),
                        (0x1bae, b''.join(actors)), (0xc21e, b''.join(visuals)), (0x79ea, links),
                        (0xc322, executor.descriptors), (0x208d, bytes((actor_count,))),
                        (0xc496, bytes((actor_count + 2,))), (0x2072, struct.pack('<H', 0x55aa)),
                        (0x2074, struct.pack('<H', 0xab12)), (0x799f, b'\x5a'),
                        (0x799e, bytes((priority,))), (0x78c0, struct.pack('<H', 0xbeef)), (0x79c4, b'\x01')):
                    cpu.mem_write(base + offset, bytes(raw))
                assert bytes(cpu.mem_read(base + 0x6c, 2)) == bytes((74, 79))
                request = struct.pack('<HHHIHHHH', 60, 33, tick, rng, 0, count, 0, 0x4000)
                request += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
                request += bytes(cpu.mem_read(base + 0x292b, 55)) + bytes(cpu.mem_read(base + 0x6620, 75))
                request += bank(executor) + sound(executor)
                inputs.append(request)
                executor.registers(0xf000, 0xff00)
                cpu.mem_write(0x8ff00, struct.pack('<H', 0xff00))
                enabled = executor is observed
                cpu.emu_start(0x15102, 0x1ff00, count=1000000)
                enabled = False
                executor.assert_return(0xff00, 0xf000, 0xff02)
                snapshots.append(bytes(cpu.mem_read(0, 1024**2)))
                bound, live = struct.unpack('<HH', bytes(cpu.mem_read(base + 0x207e, 4)))
                result = bytes(cpu.mem_read(base + 0x1afe, 4)) + struct.pack('<HH', bound - 199, live)
                result += bytes(cpu.mem_read(base + 0x78c8, 2)) + bytes(cpu.mem_read(base + 0x78c4, 2))
                result += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
                result += bytes(cpu.mem_read(base + 0x292b, 55)) + bytes(cpu.mem_read(base + 0x6620, 75))
                result += bank(executor) + sound(executor)
                outputs.append(result)
            assert inputs[0] == inputs[1] and outputs[0] == outputs[1] and snapshots[0] == snapshots[1]
            assert [observed.cpu.reg_read(r) for r in tracked] == [neutral.cpu.reg_read(r) for r in tracked]
            fractures = mask.bit_count()
            assert visits['fracture'] == visits['remove'] == visits['actor_constructor'] == fractures
            assert visits['normal_writeback'] == count - fractures and not visits['timer_remove']
            assert struct.unpack_from('<4H', outputs[0], 4) == (2 * fractures, count - fractures, 2 * fractures, 0x4000 + 2 * fractures)
            assert outputs[0][6082 + 1570] == min(30, actor_count + fractures)
            assert outputs[0][6007 + 45:6082] == inputs[0][6013 + 45:6088]
            if count == 1:
                before, after = inputs[0][6013:6028], outputs[0][6007:6022]
                assert after[:12] == before[:12] and after[14:] == before[14:]
                assert after[12] == 0x80 and after[13] == (timer + 1) & 255
            chain.update(hashlib.sha256(snapshots[0]).digest())
            requests.append(inputs[0]); results.append(outputs[0]); totals.update(visits)
            report['cases'].append(dict(index=index, count=count, fracture_mask=mask, timer=timer, flags=flags,
                tick=tick, actor_count=actor_count, sound_priority=priority, visits=dict(visits),
                input_sha256=sha(inputs[0]), output_sha256=sha(outputs[0])))
        assert all(len(raw) == INPUT_BYTES for raw in requests)
        assert all(len(raw) == STATE_BYTES for raw in results)
        fixture = b'LZFR0001' + struct.pack('<II', len(cases), INPUT_BYTES + STATE_BYTES)
        fixture += b''.join(request + result for request, result in zip(requests, results))
        packed = gzip.compress(fixture, mtime=0)
        expected = b'LZFO0001' + struct.pack('<II', len(cases), STATE_BYTES) + b''.join(results)
        (out / 'fracture_retirement_original.bin.gz').write_bytes(packed)
        (out / 'expected.bin').write_bytes(expected)
        report.update(passed=True, total_cases=len(cases), state_bytes=len(cases) * STATE_BYTES,
            original_visits=dict(totals), fixture_bytes=len(fixture), fixture_sha256=sha(fixture),
            fixture_gzip_bytes=len(packed), fixture_gzip_sha256=sha(packed), expected_sha256=sha(expected),
            full_memory_repeat_hash_chain=chain.hexdigest(),
            physical_write_sites={f'{slot}:{offset}:0x{site:04x}': count for (slot, offset, site), count in sorted(writes.items())})
    except BaseException:
        report['error'] = traceback.format_exc()
        raise
    finally:
        (out / 'capture.json').write_text(json.dumps(report, indent=2) + '\n')
        assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < 8 * 1024**2
        print(json.dumps({key: value for key, value in report.items() if key not in ('cases', 'physical_write_sites')}), flush=True)


if __name__ == '__main__':
    main()
