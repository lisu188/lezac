"""Compare complete shipped-profile native records with unmodified original code."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import traceback
from types import ModuleType

FIXTURE = 'tests/fixtures/shipped_monster_profiles_original.bin'
FIXTURE_SHA = 'b1c71fb54958a9cac974c30813ba55c157ff50cdb5bfa33688a97ab0cbfe79ea'
LEVELS_SHA = 'd8b553871014108515d6af05b0853de8ccc22e4d3e44d63533ba1167fdc8c7b2'
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
STATE_SIZE = 112
CASE_SIZE = 18 + 30 + 130 * STATE_SIZE
PREFIX = 64 + 368 + 1980


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def producer_sha256():
    value = globals().get('__source_sha256__')
    if value is None:
        raise RuntimeError('producer must execute from a bound source buffer')
    return value


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_source_module(path, source=None):
    """Execute the attributed buffer directly, without import bytecode caches."""
    path = path.resolve(strict=True)
    source = path.read_bytes() if source is None else source
    module = ModuleType(path.stem)
    module.__file__ = str(path)
    module.__package__ = ''
    exec(compile(source, str(path), 'exec', dont_inherit=True), vars(module))
    module.__source_sha256__ = sha(source)
    return module


def read_file(root, name):
    path = root / name
    return path.read_bytes() if path.exists() else subprocess.check_output(
        ['git', '-C', str(root), 'show', 'HEAD:' + name], timeout=30)


def read_native(root):
    raw = read_file(root, FIXTURE)
    require(sha(raw) == FIXTURE_SHA, 'native shipped profile fixture hash mismatch')
    require(len(raw) == PREFIX + 45 * CASE_SIZE, 'native fixture extent differs')
    require(raw[:64] == b'LZSPROF1' + struct.pack('<4H', 1, 45, 64, 15) + bytes.fromhex(EXE_SHA) + bytes(16),
            'native fixture header differs')
    levels = read_file(root, 'LIVELS.SCH')
    require(sha(levels) == LEVELS_SHA, 'shipped level bank hash mismatch')
    cases = []
    for case in range(45):
        at = PREFIX + case * CASE_SIZE
        index, profile, level, slot, offset, seed, frame, near, reserved = struct.unpack_from('<HHBBIIHBB', raw, at)
        require((index, profile, seed, frame, near, reserved) ==
                (case, case // 3, (0, 0x12345678, 0xffffffff)[case % 3], 420 + case, case % 3 == 0, 0),
                'native case metadata differs')
        require(levels[offset:offset + 30] == raw[at + 18:at + 48], 'shipped spawner record differs')
        cases.append(dict(index=case, profile=profile, level=level, slot=slot, at=at))
    return dict(raw=raw, sha256=sha(raw), levels_sha256=sha(levels), cases=cases)


def compare_bytes(report, actual, expected, label):
    if actual != expected:
        report['mismatch'] = dict(label=label, actual=actual.hex(), expected=expected.hex(),
            differing_offsets=[i for i, (a, b) in enumerate(zip(actual, expected)) if a != b][:64],
            actual_bytes=len(actual), expected_bytes=len(expected))
        raise ValueError('native shipped profile mismatch: ' + label)
    report['compared_bytes'] += len(actual)


def validate_executor_identity(module, expected_hash, report):
    path = Path(module.__file__).resolve(strict=True)
    actual_hash = module.__source_sha256__
    report.update(helper_path=str(path), helper_sha256=actual_hash)
    require(actual_hash == expected_hash, 'imported executor hash differs from native prerequisite')


def execute(root, native_report_path, unicorn_path, report):
    native = read_native(root)
    raw = native['raw']
    report.update(native_fixture_sha256=native['sha256'], levels_sha256=native['levels_sha256'])
    prerequisite_bytes = native_report_path.read_bytes()
    report['native_prerequisite_sha256'] = sha(prerequisite_bytes)
    prerequisite = json.loads(prerequisite_bytes.decode('utf-8'))
    require(prerequisite.get('passed') is True, 'native prerequisite did not pass')
    sys.path.insert(0, str(root / 'tools'))
    lifetime = load_source_module(root / 'tools/capture_original_bomb_lifetime.py')
    helper_path = root / 'tools/original_bomb_cpu.py'
    helper_source = helper_path.read_bytes()
    helper_hash = sha(helper_source)
    checker_hash = lifetime.native_checker.__source_sha256__
    lifetime.validate_native_report(prerequisite, helper_hash, checker_hash)
    report.update(helper_sha256=helper_hash, prerequisite_checker_sha256=checker_hash)
    if unicorn_path is not None:
        sys.path.insert(0, str(unicorn_path))
    original_bomb_cpu = load_source_module(helper_path, helper_source)
    validate_executor_identity(original_bomb_cpu, helper_hash, report)
    original = original_bomb_cpu.BombCPU(root)
    cpu, data = original.cpu, original.DATA
    require(raw[64:432] == original.descriptors, 'native descriptors differ')

    def compare_state(at, label):
        actor = bytes(cpu.mem_read(data + 0x1bd4, 38))
        for actual, expected, field in (
                (bytes(cpu.mem_read(data + 0x208d, 1)), b'\x01', 'count'),
                (bytes(cpu.mem_read(data + 0xc496, 1)), b'\x03', 'visual-count'),
                (bytes(cpu.mem_read(data + 0x78c2, 2)), raw[at:at + 2], 'frame'),
                (bytes(cpu.mem_read(data + 0x1afe, 4)), raw[at + 2:at + 6], 'rng'),
                (actor, raw[at + 6:at + 44], 'actor'),
                (bytes(cpu.mem_read(data + 0xc21e + actor[1] * 8, 8)), raw[at + 44:at + 52], 'visual'),
                (bytes(cpu.mem_read(data + 0x74c6, 30)), raw[at + 52:at + 82], 'spawner')):
            compare_bytes(report, actual, expected, label + ':' + field)

    def run_range(start, end):
        original.registers(0xf000, 0xff00)
        original.instructions = 0
        cpu.emu_start(0x10000 + start, 0x10000 + end, count=2000000)
        original.assert_return(end, 0xf000, 0xff00)
        report['instructions'] += original.instructions

    for case in native['cases']:
        report['active_case'] = case['index']
        before = case['at'] + 48
        constructed = before + STATE_SIZE
        cpu.context_restore(original.initial_context)
        cpu.mem_write(0, original.initial_memory)
        cpu.mem_write(data + 0x1b88, bytes(76 + 30 * 38))
        cpu.mem_write(data + 0xc21e, bytes(33 * 8))
        cpu.mem_write(data + 0xc322, original.descriptors)
        cpu.mem_write(0x40000, raw[432:PREFIX])
        cpu.mem_write(0x50000, bytes(3960))
        for offset, value in ((0xc1e0, struct.pack('<HH', 0, 0x4000)),
                (0xc1fe, struct.pack('<H', 0x4000)), (0xc204, struct.pack('<HH', 60, 33)),
                (0x206e, struct.pack('<H', 0x5000)), (0x6612, struct.pack('<HH', 0, 0x5000)),
                (0x78c4, struct.pack('<H', 0x4000)), (0x79a6, b'\x01'),
                (0x74c6, raw[before + 52:before + 82]), (0x208d, b'\x00'), (0x208e, b'\x00'),
                (0xc496, b'\x02'), (0x1afe, raw[before + 2:before + 6]),
                (0x78c2, raw[before:before + 2]), (0x2076, bytes(2)),
                (0x207e, struct.pack('<H', 199)), (0x2080, bytes(2)), (0x79e8, bytes(2)),
                (0x79b9, b'\x00'), (0x79f9, b'\x00'), (0x79ea, bytes((99, 99, 100, 100))),
                (0x1bac, b'\x64'), (0x1bd2, b'\x64'),
                (0xc21e, raw[before + 82:before + 98]), (0x79e6, raw[before + 98:before + 100])):
            cpu.mem_write(data + offset, value)
        run_range(0x293d, 0x2949)
        run_range(0x2852, 0x2858)
        original.entries.clear()
        run_range(0x7a6b, 0x7c3d)
        compare_state(constructed, 'constructor')
        report['constructors'] += 1
        current = dict(case, updates=0)
        report['cases'].append(current)
        for tick in range(64):
            report['active_tick'] = tick
            pre = constructed + STATE_SIZE + tick * 2 * STATE_SIZE
            post = pre + STATE_SIZE
            cpu.mem_write(data + 0x78c2, raw[pre:pre + 2])
            if tick:
                run_range(0x7a6b, 0x7c3d)
            compare_state(pre, 'pre')
            # Native player processing is outside this bounded actor experiment.
            cpu.mem_write(data + 0xc21e, raw[pre + 82:pre + 98])
            cpu.mem_write(data + 0x79e6, raw[pre + 98:pre + 100])
            run_range(0x7ebb, 0x7eea)
            compare_state(post, 'post')
            report['updates'] += 1
            current['updates'] += 1
        current['original_helpers_entered'] = dict(original.entries)
    require(report['constructors'] == 45 and report['updates'] == 2880, 'incomplete native coverage')
    require(report['compared_bytes'] == 487620, 'incomplete native byte coverage')
    report.update(passed=True, full_native_actor_records_compared=True,
        full_native_visual_records_compared=True, full_native_spawner_records_compared=True,
        native_rng_compared=True, original_startup_ranges=['CS:293d..2949', 'CS:2852..2858'],
        original_spawner_range='CS:7a6b..7c3d', original_actor_range='CS:7ebb..7eea')


def run_analysis(root, native_report, unicorn_path, out):
    report = dict(passed=False, cases=[], constructors=0, updates=0, instructions=0, compared_bytes=0,
        generator_sha256=producer_sha256(), original_instructions_patched=False,
        original_calls_stubbed=False, hardware_io_permitted=False, exogenous_player_targets=True,
        new_native_capture=False, natural_route_claim=False, compiled_cpp_comparison=False,
        whole_game_complete=False,
        limitation='Retained controlled-room kinds 1..4 / behaviors 3..4 only. Player targets are exogenous; '
                   'player processing, full world/maps, rendering, hardware timing, natural spawning, '
                   'mixed pools, boss links and compiled C++ full-record parity are not compared.')
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as destination:
        try:
            execute(root, native_report, unicorn_path, report)
        except BaseException:
            report['failure'] = traceback.format_exc()
            raise
        finally:
            report['recorded_utc'] = datetime.now(timezone.utc).isoformat()
            json.dump(report, destination, indent=2)
            destination.write('\n')
    return report


def main(argv=None):
    if sys.flags.optimize:
        raise RuntimeError('optimized Python is not supported by original shipped profile analysis')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path)
    parser.add_argument('--native-report', type=Path)
    parser.add_argument('--unicorn-path', type=Path)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.self_check:
        read_native(root)
        print('original_shipped_profile_self_check=ok profiles=15 constructors=45 updates=2880 executor_required=0 live=0')
        return 0
    if args.out is None or args.native_report is None:
        parser.error('--out and --native-report are required unless --self-check is used')
    report = run_analysis(root, args.native_report.resolve(),
        args.unicorn_path.resolve() if args.unicorn_path else None, args.out.resolve())
    print(json.dumps(dict(passed=report['passed'], constructors=report['constructors'],
        updates=report['updates'], compared_bytes=report['compared_bytes'], report=str(args.out.resolve()))))
    return 0


if __name__ == '__main__':
    raise SystemExit(load_source_module(Path(__file__)).main())
