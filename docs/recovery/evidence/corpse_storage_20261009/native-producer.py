"""Capture complete original corpse-to-reward/fade and particle-construction passes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
from types import ModuleType

CAP = 8 * 1024**2
STATE_BYTES = 1593
HELPER_SHA = 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c'
READER_SHA = 'e5aa6ec103090468f47d588d073453d87179b8d598319a481b41a7380a73fe81'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def module(path, expected):
    raw = path.read_bytes()
    assert sha(raw) == expected
    result = ModuleType(path.stem)
    result.__file__ = str(path)
    exec(compile(raw, str(path), 'exec', dont_inherit=True), vars(result))
    return result


def rng_step(seed):
    return (seed * 0x08088405 + 1) & 0xffffffff


def cases():
    seeds = {}
    for seed in range(100000):
        seeds.setdefault((rng_step(seed) >> 16) % 100, seed)
        if len(seeds) == 100:
            break
    assert len(seeds) == 100
    result = []
    def add(label, roll, count=1, mode=0, parity=1, back=False, timer=None, priority=5, active=1):
        result.append(dict(label=label, roll=roll, rng=seeds[roll], count=count, mode=mode,
            parity=parity, back=back, timer=(1 if parity else 0) if timer is None else timer,
            priority=priority, active=active, updates=2))
    for roll in range(100):
        add(f'all-rolls-{roll}', roll)
    boundaries = (39, 40, 65, 66, 71, 72, 78, 79, 83, 84, 89, 90, 93, 94, 99)
    for count in (28, 29, 30):
        for mode in range(4):
            for parity in range(2):
                for back in (False, True):
                    for roll in boundaries:
                        add(f'pool-{count}-mode-{mode}-parity-{parity}-back-{int(back)}-roll-{roll}',
                            roll, count=count, mode=mode, parity=parity, back=back)
    for priority in (0, 3, 4, 5, 127, 128, 129, 255):
        for active in (0, 1):
            for roll in (39, 40, 65, 99):
                add(f'sound-{priority}-active-{active}-roll-{roll}', roll, priority=priority, active=active)
    for mode in range(4):
        for roll in (39, 40, 65, 99):
            add(f'delayed-mode-{mode}-roll-{roll}', roll, mode=mode, parity=0, timer=1)
            add(f'underflow-mode-{mode}-roll-{roll}', roll, mode=mode, parity=1, timer=0)
            add(f'sentinel-mode-{mode}-roll-{roll}', roll, mode=mode, parity=0, timer=255)
    for mode in range(4):
        for parity in range(2):
            add(f'countdown-mode-{mode}-parity-{parity}', (39, 40, 65, 99)[mode],
                mode=mode, parity=parity, timer=25)
            result[-1]['updates'] = 56
    assert len({item['label'] for item in result}) == len(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    assert not out.exists() and out.parent == Path('/tmp')
    assert not sys.flags.optimize and os.environ['SDL_AUDIODRIVER'] == 'dummy'
    assert shutil.disk_usage('/dev/shm').free > 1503238553
    out.mkdir()
    oracle = Path('/dev/shm/lezac-oracle-current-main-20261008-t69')
    native_root = Path('/dev/shm/lezac-shared-crosscheck-main-20261009-t75')
    sys.path.insert(0, '/dev/shm/lezac-sound-machinecode-deps-20261008-t24')
    helper = module(oracle / 'tools/original_bomb_cpu.py', HELPER_SHA)
    reader = module(native_root / 'tools/check_original_shared_actor_native.py', READER_SHA)
    native = reader.read_native(native_root)
    import unicorn
    from unicorn import x86_const as regs
    observed, neutral = helper.BombCPU(oracle), helper.BombCPU(oracle)
    assert observed.descriptors == native['descriptors']
    assert bytes(observed.cpu.mem_read(observed.DATA + 0x52, 8)) == bytes((40, 65, 71, 78, 83, 89, 93, 100))
    tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
        ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
    enabled = False
    calls, values, midpoints = [], [], []
    construction = bytearray()
    writes, sites = Counter(), {}
    requests, expected = bytearray(native['map'] + native['words'] + native['descriptors']), bytearray()
    operations = 0
    variant_cases = cases()

    def observe_code(cpu, address, size, unused):
        if not enabled:
            return
        if address in (0x1766d, 0x176f4):
            phase = 0 if address == 0x1766d else 1
            boundary = len(construction) // (STATE_BYTES + 7)
            construction.extend(struct.pack('<IHB', index, tick, phase) + snapshot(observed))
            midpoints.append(dict(index=boundary, phase=phase, ip=f'{address - 0x10000:04x}'))
        if address == 0x1a5a8:
            stack = cpu.reg_read(regs.UC_X86_REG_SS) * 16 + cpu.reg_read(regs.UC_X86_REG_SP)
            span = struct.unpack('<H', bytes(cpu.mem_read(stack + 4, 2)))[0]
            calls.append(dict(span=span, seed=bytes(cpu.mem_read(observed.DATA + 0x1afe, 4)).hex()))
        elif address in (0x17674, 0x1767e, 0x17738, 0x17744):
            values.append(dict(ip=f'{address - 0x10000:04x}', value=cpu.reg_read(regs.UC_X86_REG_AX)))

    def observe_write(cpu, access, address, size, value, unused):
        if not enabled:
            return
        for offset in range(size):
            at = address + offset - observed.DATA
            for label, start, length, stride in (
                ('actor', 0x1bae, 31 * 38, 38), ('visual', 0xc21e, 33 * 8, 8)):
                if start <= at < start + length:
                    key = f'{cpu.reg_read(regs.UC_X86_REG_CS):04x}:{cpu.reg_read(regs.UC_X86_REG_IP):04x}:{label}'
                    writes[key] += 1
                    sites.setdefault(key, Counter())[(at - start) % stride] += 1

    observed.cpu.hook_add(unicorn.UC_HOOK_CODE, observe_code)
    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, observe_write)

    def snapshot(executor):
        cpu, base = executor.cpu, executor.DATA
        raw = bytes(cpu.mem_read(base + 0x1bae, 31 * 38))
        raw += bytes(cpu.mem_read(base + 0xc21e, 33 * 8))
        raw += bytes(cpu.mem_read(base + 0x79ea, 8 * 16))
        for offset, length in ((0x208d, 1), (0xc496, 1), (0x79f9, 1), (0x2072, 2),
                (0x1afe, 4), (0x79ae, 2), (0x79e8, 2), (0x79e6, 2),
                (0x79a3, 1), (0x2074, 2), (0x799f, 1), (0x799e, 1), (0x78c0, 2), (0x79c4, 1)):
            raw += bytes(cpu.mem_read(base + offset, length))
        assert len(raw) == STATE_BYTES
        return raw

    def compare():
        nonlocal operations
        memory = bytes(observed.cpu.mem_read(0, 1024**2))
        assert memory == bytes(neutral.cpu.mem_read(0, 1024**2))
        registers = [observed.cpu.reg_read(reg) for reg in tracked]
        assert registers == [neutral.cpu.reg_read(reg) for reg in tracked]
        assert bytes(observed.cpu.mem_read(0x40000, len(native['map']))) == native['map']
        assert bytes(observed.cpu.mem_read(0x50000, len(native['words']))) == native['words']
        state = snapshot(observed)
        expected.extend(state)
        operations += 1
        return state, sha(memory), registers

    def seed(executor, index, case):
        cpu, base = executor.cpu, executor.DATA
        cpu.context_restore(executor.initial_context); cpu.mem_write(0, executor.initial_memory)
        for offset, raw in ((0xc1e0, struct.pack('<HH', 0, 0x4000)), (0xc1fe, struct.pack('<H', 0x4000)),
                (0xc204, struct.pack('<HH', 60, 33)), (0x206e, struct.pack('<H', 0x5000)),
                (0x6612, struct.pack('<HH', 0, 0x5000)), (0x78c4, struct.pack('<H', 0x4000))):
            cpu.mem_write(base + offset, raw)
        executor.registers(0xf000, 0xff00)
        cpu.emu_start(0x1293d, 0x12949, count=4); executor.assert_return(0x2949, 0xf000, 0xff00)
        cpu.emu_start(0x12852, 0x12858, count=2); executor.assert_return(0x2858, 0xf000, 0xff00)
        cpu.mem_write(0x40000, native['map']); cpu.mem_write(0x50000, native['words'])
        salt, count = index * 11, case['count']
        actors = [bytearray(((salt + slot * 17 + byte * 29) & 255) for byte in range(38)) for slot in range(31)]
        visuals = [bytearray(((salt + row * 31 + byte * 13) & 255) for byte in range(8)) for row in range(33)]
        links = bytearray(((salt + byte * 19) & 255) for byte in range(8 * 16)); links[15] = 0
        actors[0][0], actors[0][1], actors[0][21] = 0, 1, 0
        visuals[0][:4] = struct.pack('<hh', 0, 0); visuals[1][:4] = struct.pack('<hh', 464, 240)
        corpse_slot = count if case['back'] else 1
        for slot in range(1, count + 1):
            raw = actors[slot]
            reference = count + 2 - slot if case['back'] else slot + 1
            raw[0], raw[1], raw[2], raw[20], raw[21] = 0x0b, reference, 200, 0, 5
            raw[6:14] = struct.pack('<hhHH', 0, 0, 0x9a, 0x4e)
            raw[22:29] = bytes((9, 6, 9, 0, 0, 0, 1))
            raw[29:36] = bytes((43, 43, 46, 2, 2, 2, 255))
            visuals[reference][:4] = struct.pack('<hh', 336, 174)
            visuals[reference][4:8] = native['descriptors'][44 * 4:45 * 4]
            visuals[reference][4:6] = bytes((9 + slot % 11, 5 + slot % 7))
        corpse = actors[corpse_slot]
        corpse[0], corpse[2], corpse[20], corpse[21] = 0x0c, case['timer'], 6, 2
        corpse[6:14] = struct.pack('<hhHH', (-300, 0, 600)[index % 3], (-800, 0, 600)[index % 3],
            (0x9a + index * 17) & 255, (0x4e + index * 29) & 255)
        corpse[22:29] = bytes((9, 6, 9, 0, 0, case['mode'], 1))
        visuals[32][4:8] = native['descriptors'][4:8]
        for offset, raw in ((0x1bae, b''.join(actors)), (0xc21e, b''.join(visuals)),
                (0x79ea, links), (0xc322, native['descriptors']), (0x208d, bytes((count,))),
                (0xc496, bytes((count + 2,))), (0x2072, struct.pack('<H', 0x55aa)),
                (0x79a6, bytes(1)), (0x79e6, bytes(2)), (0x79ae, bytes((6, 3))),
                (0x79e8, bytes((0xa5, 0x5a))), (0x2080, bytes(2)), (0x207e, struct.pack('<H', 199)),
                (0x2076, bytes(2)), (0x208e, bytes(1)), (0x1afe, struct.pack('<I', case['rng'])),
                (0x78c2, struct.pack('<H', 100 + case['parity'])), (0x1b89, bytes(1)),
                (0x79a3, bytes((0xa5,))), (0x2074, struct.pack('<H', 0xab12)),
                (0x799e, bytes((case['priority'],))), (0x799f, bytes((0x5a,))),
                (0x78c0, struct.pack('<H', 0xab12)), (0x79c4, bytes((case['active'],)))):
            cpu.mem_write(base + offset, bytes(raw))
        return corpse_slot

    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(),
        producer_sha256=sha(Path(__file__).read_bytes()), original_exe_sha256=sha(observed.raw),
        helper_sha256=HELPER_SHA, native_reader_sha256=READER_SHA, native_fixture_sha256=native['sha256'],
        original_instructions_patched=False, original_calls_stubbed=False, hardware_io_permitted=False,
        observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
        shared_pass=['1000:7ebb', '1000:7eea'], state_bytes=STATE_BYTES,
        state_layout='reward_storage_1585 + rollByte,requestCursor16,requestPriority,activePriority,activeCursor16,activeFlag',
        reward_threshold_bytes=[40, 65, 71, 78, 83, 89, 93, 100],
        seeded=True, natural_route=False, full_cpp_comparison=False, reward_allocation_executed=False,
        corpse_in_place_conversion_executed=True, particle_allocation_executed=True,
        audio='dummy', sound_request_latch_executed=True, sound_interrupt_executed=False,
        player_updates_executed=False, rendered_pixels_claim=False, whole_game_claim=False, cases=[])
    try:
        for index, case in enumerate(variant_cases):
            report['active_case'] = case['label']
            enabled = False
            slots = [seed(executor, index, case) for executor in (observed, neutral)]
            assert slots[0] == slots[1]
            corpse_slot = slots[0]
            requests.extend(b'S' + snapshot(observed))
            initial, _, _ = compare()
            row = dict(**case, corpse_slot=corpse_slot, first_operation=operations, ticks=[])
            report['cases'].append(row)
            for update in range(case['updates']):
                tick = 100 + case['parity'] + update
                calls.clear(); values.clear(); midpoints.clear()
                requests.extend(b'U' + struct.pack('<H', tick))
                for executor in (observed, neutral):
                    executor.cpu.mem_write(executor.DATA + 0x78c2, struct.pack('<H', tick))
                    executor.registers(0xf000, 0xff00)
                    enabled = executor is observed
                    executor.cpu.emu_start(0x17ebb, 0x17eea, count=2000000)
                    enabled = False
                    executor.assert_return(0x7eea, 0xf000, 0xff00)
                state, memory_sha, registers = compare()
                raw = state[corpse_slot * 38:(corpse_slot + 1) * 38]
                converted = raw[0] != 0x0c
                row['ticks'].append(dict(operation=operations, tick=tick, kind=raw[0], count=state[1570],
                    visual_count=state[1571], rng=state[1575:1579].hex(), random_calls=list(calls),
                    random_values=list(values), actor=raw.hex(),
                    visual=state[1178 + raw[1] * 8:1178 + (raw[1] + 1) * 8].hex(),
                    sound_and_roll=state[1585:].hex(), memory_sha256=memory_sha, registers=registers,
                    construction_boundaries=list(midpoints)))
                if calls:
                    assert [point['phase'] for point in midpoints] == [0, 1]
                    assert [item['span'] for item in calls] == [100, 20, 600, 600, 600, 600]
                    assert values[0] == dict(ip='7674', value=case['roll'])
                    assert state[1585] == case['roll']
                    rng = case['rng']
                    for _ in range(6): rng = rng_step(rng)
                    assert state[1575:1579] == struct.pack('<I', rng)
                    assert state[1570] == min(30, case['count'] + 2) and state[1571] == state[1570] + 2
                    assert converted
                else:
                    assert not midpoints
                    assert converted or raw[2] not in (0, 255)
                assert state[1579:1585] == initial[1579:1585]
            assert any(tick['random_calls'] for tick in row['ticks']), 'corpse failed to expire'
            assert len(expected) < CAP and len(requests) < CAP
        requests = b'LZRC0001' + struct.pack('<I', operations) + requests
        expected = b'LZCO0001' + struct.pack('<I', operations) + expected
        construction = b'LZCB0001' + struct.pack('<I', len(construction) // (STATE_BYTES + 7)) + construction
        for label, raw in (('requests', requests), ('expected', expected), ('construction', construction)):
            assert len(raw) < CAP
            packed = gzip.compress(raw, mtime=0)
            (out / (label + '.bin.gz')).write_bytes(packed)
            report[label] = dict(bytes=len(raw), raw_sha256=sha(raw), compressed_bytes=len(packed), sha256=sha(packed))
        conversions = [tick for row in report['cases'] for tick in row['ticks'] if tick['random_calls']]
        report.update(passed=True, case_count=len(variant_cases), operations=operations,
            actor_passes=sum(case['updates'] for case in variant_cases), native_bytes_compared_per_execution=operations * STATE_BYTES,
            six_draw_conversions=len(conversions), all_random_rolls_observed=list(range(100)),
            construction_boundaries=len(construction[12:]) // (STATE_BYTES + 7),
            construction_record_bytes=STATE_BYTES + 7, construction_phases=['1000:766d', '1000:76f4'],
            conversion_kinds=dict(Counter(str(tick['kind']) for tick in conversions)),
            pool_counts=[1, 28, 29, 30], inherited_modes=[0, 1, 2, 3],
            write_sites=dict(writes), site_offsets={key: dict(value) for key, value in sites.items()})
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        raw = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
        assert len(raw) < 4 * 1024**2
        (out / 'original-reward-construction.json').write_bytes(raw)
        assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < CAP
    print(json.dumps(dict(passed=report['passed'], cases=report['case_count'], operations=operations,
        native_bytes_compared_per_execution=report['native_bytes_compared_per_execution'],
        directory=str(out), output=report['expected'])), flush=True)


if __name__ == '__main__':
    main()
