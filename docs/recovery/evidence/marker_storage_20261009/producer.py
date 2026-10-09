"""Capture native launch/portal constructor tails and continuous actor passes."""
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
    import unicorn
    from unicorn import x86_const as regs
    observed, neutral = helper.BombCPU(oracle), helper.BombCPU(oracle)
    assert observed.descriptors == native['descriptors']
    tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
               ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
    requests = bytearray(native['descriptors'])
    expected = bytearray()
    sites, actor_offsets, visual_offsets = Counter(), Counter(), Counter()
    site_offsets = {}
    active = False
    operations = 0

    def hook(cpu, access, address, size, value, unused):
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
                    sites[key] += 1
                    site_offsets.setdefault(key, Counter())[byte] += 1

    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, hook)

    def snapshot(executor):
        cpu, base = executor.cpu, executor.DATA
        raw = bytes(cpu.mem_read(base + 0x1bae, 31 * 38))
        raw += bytes(cpu.mem_read(base + 0xc21e, 33 * 8))
        raw += bytes(cpu.mem_read(base + 0x79ea, 8 * 16))
        raw += bytes(cpu.mem_read(base + 0x208d, 1)) + bytes(cpu.mem_read(base + 0xc496, 1))
        raw += bytes(cpu.mem_read(base + 0x79f9, 1)) + bytes(cpu.mem_read(base + 0x2072, 2))
        assert len(raw) == 1575
        return raw

    def compare():
        nonlocal operations
        assert bytes(observed.cpu.mem_read(0, 1024**2)) == bytes(neutral.cpu.mem_read(0, 1024**2))
        assert [observed.cpu.reg_read(reg) for reg in tracked] == [neutral.cpu.reg_read(reg) for reg in tracked]
        expected.extend(snapshot(observed))
        operations += 1

    def seed(executor, salt, count, mode, vx, vy, timer, reverse):
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
        actors = [bytearray(((salt + slot * 17 + byte * 29) & 255) for byte in range(38)) for slot in range(31)]
        actors[0][1] = 1
        visuals = [bytearray(((salt + row * 31 + byte * 13) & 255) for byte in range(8)) for row in range(33)]
        links = bytearray(((salt + byte * 19) & 255) for byte in range(8 * 16))
        links[15] = 0
        for slot in range(1, count + 1):
            raw = actors[slot]
            visual_index = count + 2 - slot if reverse else slot + 1
            raw[0], raw[1], raw[2], raw[20], raw[21] = 11, visual_index, (timer + slot - 1) & 255, 0, 5
            if slot % 7 == 0:
                raw[2] = 0
            raw[6:14] = struct.pack('<hhHH', vx, vy, (slot * 63) & 255, (slot * 97) & 255)
            raw[22:29] = bytes((9, 6, 9, 0, 0, mode, 1))
            raw[29:36] = bytes((43, 43, 46, 2, 2, 2, 255))
            visuals[visual_index][:4] = struct.pack('<HH', (32760 + slot * 3) & 65535, (65530 + slot * 3) & 65535)
            visuals[visual_index][4:8] = native['descriptors'][7 * 4:8 * 4]
            visuals[visual_index][4:6] = bytes((9 + slot, 5 + slot % 7))
        visuals[32][4:8] = native['descriptors'][:4]
        for offset, raw in ((0x1bae, b''.join(actors)), (0xc21e, b''.join(visuals)),
                (0x79ea, links), (0xc322, native['descriptors']), (0x208d, bytes((count,))),
                (0xc496, bytes((count + 2,))), (0x2072, struct.pack('<H', 0x55aa)),
                (0x79a6, bytes(1)), (0x79e6, b'\x01\x00'), (0x2080, bytes(2)),
                (0x207e, struct.pack('<H', 199)), (0x2076, bytes(2)), (0x208e, bytes(1)),
                (0x1afe, struct.pack('<I', 0x12345678)), (0x78c2, struct.pack('<H', 100))):
            cpu.mem_write(base + offset, bytes(raw))

    def construct(kind, x, y):
        nonlocal active
        before = snapshot(observed)
        requests.extend(kind.encode() + struct.pack('<hh', x, y))
        for executor in (observed, neutral):
            cpu = executor.cpu
            executor.registers(0xf000, 0xff00)
            active = executor is observed
            if kind == 'L':
                cpu.mem_write(0x8f000 - 0x2c, struct.pack('<h', x))
                cpu.mem_write(0x8f000 - 0x2e, struct.pack('<h', y))
                cpu.emu_start(0x16932, 0x16964, count=1000000)
                executor.assert_return(0x6964, 0xf000, 0xff00)
            else:
                assert kind == 'P'
                cpu.mem_write(0x8f004, struct.pack('<H', 0xe000))
                cpu.mem_write(0x8e000 - 0x2c, struct.pack('<h', x))
                cpu.mem_write(0x8e000 - 0x2e, struct.pack('<h', y))
                cpu.mem_write(0x8e000 - 0x12, struct.pack('<H', 74))
                cpu.mem_write(executor.DATA + 0x006c, b'\x4a\x4f')
                cpu.emu_start(0x15a1c, 0x15a69, count=1000000)
                executor.assert_return(0x5a69, 0xf000, 0xff00)
            active = False
        after = snapshot(observed)
        admitted = before[1570] < 30
        assert after[1570] == before[1570] + int(admitted)
        assert struct.unpack_from('<H', after, 1573)[0] == int(admitted)
        if admitted:
            slot = after[1570]
            offset = slot * 38
            raw = after[offset:offset + 38]
            if kind == 'L':
                assert raw[22:27] == before[offset + 22:offset + 27]
                assert raw[27] == 0 and raw[28] == before[offset + 28]
            else:
                assert raw[22:29] == bytes((74, 74, 79, 2, 2, 1, 1)), raw[22:29].hex()
            assert raw[29:36] == before[offset + 29:offset + 36]
        else:
            assert after[:1573] == before[:1573]
        compare()
        return admitted

    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(),
        producer_sha256=sha(Path(__file__).read_bytes()), original_exe_sha256=sha(observed.raw),
        helper_sha256=HELPER_SHA, native_reader_sha256=READER_SHA, native_fixture_sha256=native['sha256'],
        original_instructions_patched=False, original_calls_stubbed=False, hardware_io_permitted=False,
        constructor_animation_is_explicit_seed=False, original_constructor_initializers_executed=True,
        launch_tail=['1000:6932', '1000:6964'], portal_tail=['1000:5a1c', '1000:5a69'],
        input_gate_and_sound_prefix_executed=False, observer_neutrality_memory_bytes=1024**2,
        observer_neutrality_registers=14, seeded=True, natural_route=False,
        compiled_cpp_comparison=False, rendered_pixels_claim=False, whole_game_claim=False, cases=[])
    admissions, refusals = Counter(), Counter()
    try:
        cases = [(mode, parity, count, vx, vy, timer, reverse) for mode in range(4) for parity in range(2)
                 for count, vx, vy, timer, reverse in ((0, 0, 0, 0, False), (1, 0, 0, 0, False),
                    (3, 2047, -2047, 1, True), (29, -32768, 32767, 0, False),
                    (30, -2047, 2047, 64, True))]
        for index, (mode, parity, count, vx, vy, timer, reverse) in enumerate(cases):
            first = operations
            for executor in (observed, neutral):
                seed(executor, index * 11, count, mode, vx, vy, timer, reverse)
            requests.extend(b'S' + snapshot(observed))
            compare()
            for kind, x, y in (('L', 32766, 32760), ('P', -32768, -2)):
                result = construct(kind, x, y)
                (admissions if result else refusals)[kind] += 1
            for frame in range(100 + parity, 116 + parity):
                requests.extend(b'U' + struct.pack('<H', frame))
                for executor in (observed, neutral):
                    executor.cpu.mem_write(executor.DATA + 0x78c2, struct.pack('<H', frame))
                    executor.registers(0xf000, 0xff00)
                    active = executor is observed
                    executor.cpu.emu_start(0x17ebb, 0x17eea, count=2000000)
                    active = False
                    executor.assert_return(0x7eea, 0xf000, 0xff00)
                compare()
                if frame in (101 + parity, 105 + parity, 111 + parity):
                    for kind, x, y in (('L', -12, -16), ('P', 32767, -32768)):
                        result = construct(kind, x, y)
                        (admissions if result else refusals)[kind] += 1
            report['cases'].append(dict(index=index, mode=mode, initial_parity=parity, initial_count=count, vx=vx, vy=vy,
                initial_timer=timer, reverse_visuals=reverse, first_operation=first, operations=operations - first))
        for mode in range(4):
            first = operations
            for executor in (observed, neutral):
                seed(executor, 201 + mode * 11, 1, mode, -128, 128, 1, False)
            requests.extend(b'S' + snapshot(observed))
            compare()
            requests.extend(b'U' + struct.pack('<H', 101))
            for executor in (observed, neutral):
                executor.cpu.mem_write(executor.DATA + 0x78c2, struct.pack('<H', 101))
                executor.registers(0xf000, 0xff00)
                active = executor is observed
                executor.cpu.emu_start(0x17ebb, 0x17eea, count=2000000)
                active = False
                executor.assert_return(0x7eea, 0xf000, 0xff00)
            assert snapshot(observed)[1570] == 0
            assert snapshot(observed)[38 + 2] == 0
            compare()
            report['cases'].append(dict(index=40 + mode, mode=mode, initial_parity=1, initial_count=1,
                vx=-128, vy=128, initial_timer=1, reverse_visuals=False, first_operation=first,
                operations=2, terminal_tail_expiry=True))
        assert operations == 1008
        assert admissions['L'] and admissions['P'] and refusals['L'] and refusals['P']
        report.update(passed=True, operations=operations, compared_table_bytes=operations * 1575,
            actor_passes=40 * 16 + 4, terminal_tail_expiry_cases=4, admissions=dict(admissions), refusals=dict(refusals),
            actor_write_offsets=dict(actor_offsets), visual_write_offsets=dict(visual_offsets),
            write_sites=dict(sites), site_offsets={key: dict(value) for key, value in site_offsets.items()},
            observer_neutrality_returns=operations)
        for label, magic, raw in (('requests', b'LZMW0001', requests), ('expected', b'LZMO0001', expected)):
            raw = magic + struct.pack('<I', operations) + raw
            packed = gzip.compress(raw, mtime=0)
            path = out / (label + '.bin.gz')
            path.write_bytes(packed)
            report[label] = dict(path=str(path), bytes=len(packed), sha256=sha(packed), raw_bytes=len(raw), raw_sha256=sha(raw))
    finally:
        (out / 'original-marker-storage.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < CAP
    print(json.dumps(dict(path=str(out), passed=report['passed'], operations=operations,
        admissions=dict(admissions), refusals=dict(refusals), write_sites=dict(sites))), flush=True)


if __name__ == '__main__':
    main()
