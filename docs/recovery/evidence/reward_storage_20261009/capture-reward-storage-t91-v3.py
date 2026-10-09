"""Capture unmodified original reward passes and complete physical tables."""
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
STATE_BYTES = 1585
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


def cases():
    trajectories = [(336, 174, 0, -200), (336, 130, 389, -800),
                    (430, 174, 600, -200), (336, 174, -300, -200),
                    (336, 30, 0, 2040), (336, 174, 0, -1900),
                    (440, 174, 1800, -200)]
    result = []
    for kind, (x, y, vx, vy) in enumerate(trajectories):
        result.append(dict(label=f'lifetime-{kind}', kind=kind, count=1,
            mode=0, timer=100, parity=kind % 2, frames=241, gate='far',
            x=x, y=y, vx=vx, vy=vy, reverse=False))
    for kind in range(7):
        for gate in ('p1', 'p2', 'both', 'occupied-p1', 'occupied-both', 'dead'):
            result.append(dict(label=f'pickup-{kind}-{gate}', kind=kind, count=1,
                mode=3 if kind % 2 else 1, timer=100, parity=kind % 2,
                frames=56, gate=gate, x=240, y=168, vx=0, vy=0, reverse=False))
    for mode in range(4):
        for parity in range(2):
            for timer in (0, 1, 2, 255):
                result.append(dict(label=f'animation-{mode}-{parity}-{timer}',
                    kind=(mode + parity) % 7, count=1, mode=mode, timer=timer,
                    parity=parity, frames=8, gate='far', x=336, y=174,
                    vx=-128, vy=128, reverse=False))
    for count in (3, 29, 30):
        for mode in (2, 3):
            result.append(dict(label=f'pool-{count}-{mode}', kind=0, count=count,
                mode=mode, timer=1, parity=mode % 2, frames=100, gate='far',
                x=336, y=174, vx=-128, vy=128, reverse=mode == 3))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    assert not out.exists() and out.parent == Path('/tmp')
    assert os.environ['SDL_AUDIODRIVER'] == 'dummy' and not sys.flags.optimize
    assert shutil.disk_usage('/dev/shm').free > 1503238553
    out.mkdir()
    oracle = Path('/dev/shm/lezac-oracle-current-main-20261008-t69')
    native_root = Path('/dev/shm/lezac-shared-crosscheck-main-20261009-t75')
    sys.path.insert(0, '/dev/shm/lezac-sound-machinecode-deps-20261008-t24')
    helper = module(oracle / 'tools/original_bomb_cpu.py', HELPER_SHA)
    reader = module(native_root / 'tools/check_original_shared_actor_native.py', READER_SHA)
    native = reader.read_native(native_root)
    assert [16 - native['descriptors'][sprite * 4 + 1] for sprite in range(62, 69)] == [4, 6, 6, 6, 6, 6, 0]
    import unicorn
    from unicorn import x86_const as regs
    observed, neutral = helper.BombCPU(oracle), helper.BombCPU(oracle)
    assert observed.descriptors == native['descriptors']
    tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
               ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
    requests = bytearray(native['map'] + native['words'] + native['descriptors'])
    expected = bytearray()
    writes, instructions, actor_offsets, visual_offsets = Counter(), Counter(), Counter(), Counter()
    site_offsets = {}
    active = False
    operations = 0
    transitions = Counter()

    def observe_write(cpu, access, address, size, value, unused):
        if not active:
            return
        base = observed.DATA
        for offset in range(size):
            at = address + offset
            for label, start, length, width, counts in (
                ('actor', 0x1bae, 31 * 38, 38, actor_offsets),
                ('visual', 0xc21e, 33 * 8, 8, visual_offsets)):
                if base + start <= at < base + start + length:
                    byte = (at - base - start) % width
                    counts[byte] += 1
                    key = f'{cpu.reg_read(regs.UC_X86_REG_CS):04x}:{cpu.reg_read(regs.UC_X86_REG_IP):04x}:{label}'
                    writes[key] += 1
                    site_offsets.setdefault(key, Counter())[byte] += 1

    def observe_code(cpu, address, size, unused):
        if active and address in (0x16053, 0x15a75, 0x106ab, 0x163be, 0x1645f,
                                  0x175a7, 0x175cb, 0x1760d, 0x176f4, 0x12fb9):
            instructions[f'1000:{address - 0x10000:04x}'] += 1

    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, observe_write)
    observed.cpu.hook_add(unicorn.UC_HOOK_CODE, observe_code)

    def snapshot(executor):
        cpu, base = executor.cpu, executor.DATA
        raw = bytes(cpu.mem_read(base + 0x1bae, 31 * 38))
        raw += bytes(cpu.mem_read(base + 0xc21e, 33 * 8))
        raw += bytes(cpu.mem_read(base + 0x79ea, 8 * 16))
        for offset, size in ((0x208d, 1), (0xc496, 1), (0x79f9, 1), (0x2072, 2),
                             (0x1afe, 4), (0x79ae, 2), (0x79e8, 2), (0x79e6, 2)):
            raw += bytes(cpu.mem_read(base + offset, size))
        assert len(raw) == STATE_BYTES
        return raw

    def compare():
        nonlocal operations
        assert bytes(observed.cpu.mem_read(0, 1024**2)) == bytes(neutral.cpu.mem_read(0, 1024**2))
        assert [observed.cpu.reg_read(reg) for reg in tracked] == [neutral.cpu.reg_read(reg) for reg in tracked]
        assert bytes(observed.cpu.mem_read(0x40000, len(native['map']))) == native['map']
        assert bytes(observed.cpu.mem_read(0x50000, len(native['words']))) == native['words']
        expected.extend(snapshot(observed))
        operations += 1

    def seed(executor, index, case):
        cpu, base = executor.cpu, executor.DATA
        cpu.context_restore(executor.initial_context)
        cpu.mem_write(0, executor.initial_memory)
        for offset, raw in ((0xc1e0, struct.pack('<HH', 0, 0x4000)), (0xc1fe, struct.pack('<H', 0x4000)),
                (0xc204, struct.pack('<HH', 60, 33)), (0x206e, struct.pack('<H', 0x5000)),
                (0x6612, struct.pack('<HH', 0, 0x5000)), (0x78c4, struct.pack('<H', 0x4000))):
            cpu.mem_write(base + offset, raw)
        executor.registers(0xf000, 0xff00)
        cpu.emu_start(0x1293d, 0x12949, count=4)
        executor.assert_return(0x2949, 0xf000, 0xff00)
        cpu.emu_start(0x12852, 0x12858, count=2)
        executor.assert_return(0x2858, 0xf000, 0xff00)
        cpu.mem_write(0x40000, native['map'])
        cpu.mem_write(0x50000, native['words'])
        salt, count = index * 11, case['count']
        actors = [bytearray(((salt + slot * 17 + byte * 29) & 255) for byte in range(38)) for slot in range(31)]
        actors[0][1] = 1
        visuals = [bytearray(((salt + row * 31 + byte * 13) & 255) for byte in range(8)) for row in range(33)]
        links = bytearray(((salt + byte * 19) & 255) for byte in range(8 * 16))
        links[15] = 0
        gate = case['gate']
        positions = [(240, 168), (400, 210)]
        alive, pending = (1, 1), (0, 0)
        if gate == 'p2':
            positions.reverse()
        elif gate in ('both', 'occupied-p1', 'occupied-both', 'dead'):
            positions[1] = positions[0]
        if gate == 'occupied-p1':
            pending = (6, 0)
        elif gate == 'occupied-both':
            pending = (6, 3)
        elif gate == 'dead':
            alive = (0, 0)
        for player in range(2):
            visuals[player][:4] = struct.pack('<hh', *positions[player])
        for slot in range(1, count + 1):
            kind = (case['kind'] + slot - 1) % 7
            sprite = kind + 62
            desc = native['descriptors'][sprite * 4:(sprite + 1) * 4]
            hotspot = 16 - desc[1]
            raw = actors[slot]
            visual_index = count + 2 - slot if case['reverse'] else slot + 1
            timer = (case['timer'] + slot - 1) & 255 if count > 1 else case['timer']
            raw[0], raw[1], raw[2], raw[20], raw[21] = kind + 0x13, visual_index, timer, hotspot, 2
            raw[6:14] = struct.pack('<hhHH', case['vx'], case['vy'],
                                   (0x9a + slot * 17) & 255, (0x4e + slot * 29) & 255)
            raw[22:29] = bytes((9, 6, 9, 0, 0, case['mode'], 1))
            raw[29:36] = bytes((43, 43, 46, 2, 2, 2, 255))
            x, y = case['x'], case['y']
            if gate != 'far':
                y += hotspot
            elif count > 1:
                x += (slot % 5) * 8
                y -= (slot % 3) * 8
            visuals[visual_index][:4] = struct.pack('<hh', x, y)
            visuals[visual_index][4:8] = desc
            # Make preserved dimensions distinguishable from any animation frame.
            visuals[visual_index][4:6] = bytes((9 + slot % 11, 5 + slot % 7))
        visuals[32][4:8] = native['descriptors'][4:8]
        for offset, raw in ((0x1bae, b''.join(actors)), (0xc21e, b''.join(visuals)),
                (0x79ea, links), (0xc322, native['descriptors']), (0x208d, bytes((count,))),
                (0xc496, bytes((count + 2,))), (0x2072, struct.pack('<H', 0x55aa)),
                (0x79a6, bytes(1)), (0x79e6, bytes(alive)), (0x79ae, bytes(pending)),
                (0x79e8, bytes((0xa5, 0x5a))), (0x2080, bytes(2)),
                (0x207e, struct.pack('<H', 199)), (0x2076, bytes(2)), (0x208e, bytes(1)),
                (0x1afe, struct.pack('<I', 0x12345678 ^ (index * 0x12345))),
                (0x78c2, struct.pack('<H', 100 + case['parity'])), (0x1b89, bytes(1))):
            cpu.mem_write(base + offset, bytes(raw))

    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(),
        producer_sha256=sha(Path(__file__).read_bytes()), original_exe_sha256=sha(observed.raw),
        helper_sha256=HELPER_SHA, native_reader_sha256=READER_SHA, native_fixture_sha256=native['sha256'],
        original_instructions_patched=False, original_calls_stubbed=False, hardware_io_permitted=False,
        observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
        shared_pass=['1000:7ebb', '1000:7eea'], state_bytes=STATE_BYTES,
        state_layout='actors[31][38],visuals[33][8],links[8][16],actorCount,visualCount,linkCount,successWord,rng32,pending[2],hits[2],alive[2]',
        map_bytes=len(native['map']), word_bytes=len(native['words']), descriptor_bytes=len(native['descriptors']),
        seeded=True, natural_route=False, player_updates_executed=False,
        pending_bonus_application_executed=False, compiled_cpp_comparison=False,
        rendered_pixels_claim=False, whole_game_claim=False, cases=[])
    try:
        for index, case in enumerate(cases()):
            first = operations
            for executor in (observed, neutral):
                seed(executor, index, case)
            initial = snapshot(observed)
            requests.extend(b'S' + initial)
            compare()
            first_conversion = None
            first_empty = None
            for frame in range(100 + case['parity'], 100 + case['parity'] + case['frames']):
                before = snapshot(observed)
                requests.extend(b'U' + struct.pack('<H', frame))
                for executor in (observed, neutral):
                    executor.cpu.mem_write(executor.DATA + 0x78c2, struct.pack('<H', frame))
                    executor.registers(0xf000, 0xff00)
                    active = executor is observed
                    executor.cpu.emu_start(0x17ebb, 0x17eea, count=2000000)
                    active = False
                    executor.assert_return(0x7eea, 0xf000, 0xff00)
                after = snapshot(observed)
                if before[1570] == after[1570]:
                    for slot in range(1, after[1570] + 1):
                        old, new = before[slot * 38], after[slot * 38]
                        if old != new:
                            transitions[f'{old:02x}->{new:02x}'] += 1
                            if first_conversion is None:
                                first_conversion = operations
                if not after[1570] and first_empty is None:
                    first_empty = operations
                assert after[1581:1585] == initial[1581:1585], 'reward path changed hit/alive gates'
                compare()
            if case['label'].startswith(('lifetime-', 'pool-')) or case['gate'] in ('p1', 'p2', 'both', 'occupied-p1'):
                assert snapshot(observed)[1570] == 0, ('incomplete lifetime', case['label'])
            report['cases'].append(dict(index=index, **case, first_operation=first,
                operations=operations - first, first_conversion=first_conversion,
                first_empty=first_empty, final_count=snapshot(observed)[1570],
                final_pending=list(snapshot(observed)[1579:1581])))
            print(json.dumps(dict(case=index, label=case['label'], operations=operations,
                                  count=snapshot(observed)[1570])), flush=True)
        assert operations * STATE_BYTES < CAP
        report.update(passed=True, operations=operations, compared_table_bytes=operations * STATE_BYTES,
            actor_passes=operations - len(report['cases']), transitions=dict(transitions),
            actor_write_offsets=dict(actor_offsets), visual_write_offsets=dict(visual_offsets),
            write_sites=dict(writes), site_offsets={key: dict(value) for key, value in site_offsets.items()},
            instruction_sites=dict(instructions), observer_neutrality_returns=operations)
        for label, magic, raw in (('requests', b'LZRW0001', requests), ('expected', b'LZRO0001', expected)):
            raw = magic + struct.pack('<I', operations) + raw
            packed = gzip.compress(raw, mtime=0)
            path = out / (label + '.bin.gz')
            path.write_bytes(packed)
            report[label] = dict(path=str(path), bytes=len(packed), sha256=sha(packed), raw_bytes=len(raw), raw_sha256=sha(raw))
    finally:
        (out / 'original-reward-storage.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < CAP
    print(json.dumps(dict(path=str(out), passed=report['passed'], operations=operations,
                         cases=len(report['cases']), transitions=dict(transitions))), flush=True)


if __name__ == '__main__':
    main()
