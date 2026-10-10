"""Cross-check complete original actor passes against retained native records."""
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

FIXTURE = 'tests/fixtures/shared_actor_order_original.txt'
FIXTURE_SHA = '765b724713778f7fa86e7df8fe7812de9e40b029cf85b46bc6e25ed9ecdd6e4e'
CASE_NAMES = ('retire_front', 'retire_back', 'corpse_front_full', 'effect_front_full',
              'corpse_bomb_full', 'bomb_corpse_full', 'two_bombs_full',
              'two_corpses_full', 'mixed_forward', 'mixed_reverse')


def sha(value):
    return hashlib.sha256(value).hexdigest()


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


def fields(line, keys):
    pairs = [part.split('=', 1) for part in line.split()[1:]]
    require(all(len(pair) == 2 for pair in pairs), 'malformed native fields')
    require(len(pairs) == len({pair[0] for pair in pairs}), 'duplicate native field')
    result = dict(pairs)
    require(set(result) == set(keys.split()), 'unexpected native fields')
    return result


def entries(value):
    result = []
    if value != '-':
        for pair in value.split(','):
            parts = pair.split(':')
            require(len(parts) == 2, 'malformed actor/visual pair')
            actor, visual = [bytes.fromhex(part) for part in parts]
            require(len(actor) == 38 and len(visual) == 8, 'invalid native record size')
            require(actor[1] == len(result) + 2, 'invalid ordered visual reference')
            result.append((actor, visual))
    require(len(result) <= 30, 'native actor pool overflow')
    return result


def read_native(root):
    path = root / FIXTURE
    blob = path.read_bytes() if path.exists() else subprocess.check_output(
        ['git', '-C', str(root), 'show', 'HEAD:' + FIXTURE], timeout=30)
    blob = blob.replace(b'\r\n', b'\n')
    require(sha(blob) == FIXTURE_SHA, 'native shared actor fixture hash mismatch')
    result = dict(cases=[], sha256=sha(blob))
    current = None
    complete = False
    for line in blob.decode('ascii').splitlines():
        if not line or line.startswith('#'):
            continue
        require(not complete, 'records after native completion')
        if line.startswith('capture='):
            value = fields(line, 'seeded temp_copy level player spawners')
            require(line.split()[0] == 'capture=shared_actor_order_original_v1', 'invalid native capture')
            require(value == dict(seeded='1', temp_copy='1', level='1', player='240,168', spawners='0'),
                    'invalid native provenance')
        elif line.startswith('map '):
            value = fields(line, 'bytes words')
            result['map'], result['words'] = [bytes.fromhex(value[key]) for key in ('bytes', 'words')]
            require(len(result['map']) == 1980 and len(result['words']) == 3960, 'invalid native map size')
        elif line.startswith('sprites '):
            result['descriptors'] = bytes.fromhex(fields(line, 'descriptors')['descriptors'])
            require(len(result['descriptors']) == 368, 'invalid native descriptors')
        elif line.startswith('case '):
            require(current is None, 'nested native case')
            seed = fields(line, 'name frame rng samples actors regs')
            require(seed['name'] == CASE_NAMES[len(result['cases'])], 'invalid native case order')
            require((seed['frame'], seed['rng'], seed['samples']) == ('101', '12345678', '41'),
                    'invalid native seed')
            current = dict(seed=seed, actors=entries(seed['actors']), ticks=[])
            require(current['actors'], 'empty native case')
            result['cases'].append(current)
        elif line.startswith('tick '):
            require(current is not None, 'native tick outside case')
            tick = fields(line, 'sample frame count visuals rng actors map regs')
            sample = len(current['ticks'])
            require(int(tick['sample']) == sample and int(tick['frame']) == 101 + sample,
                    'nonconsecutive native tick')
            tick['entries'] = entries(tick['actors'])
            require(len(tick['entries']) == int(tick['count']) and int(tick['visuals']) == int(tick['count']) + 2,
                    'native count mismatch')
            require(len(bytes.fromhex(tick['rng'])) == 4, 'invalid native RNG')
            current['ticks'].append(tick)
        elif line.startswith('end '):
            require(current is not None and len(current['ticks']) == 41, 'incomplete native case')
            require(fields(line, 'samples')['samples'] == '41', 'invalid native case end')
            current = None
        elif line.startswith('complete '):
            require(current is None and len(result['cases']) == 10, 'incomplete native cases')
            require(fields(line, 'cases samples') == dict(cases='10', samples='410'), 'invalid native completion')
            complete = True
        else:
            raise ValueError('unknown native record')
    require(complete, 'missing native completion')
    require(sum(len(tick['entries']) for case in result['cases'] for tick in case['ticks']) == 7685,
            'invalid native actor-state total')
    return result


def compare_bytes(report, actual, expected, label):
    if actual != expected:
        report['mismatch'] = dict(label=label, actual=actual.hex(), expected=expected.hex(),
            differing_offsets=[index for index, pair in enumerate(zip(actual, expected))
                               if pair[0] != pair[1]][:64],
            actual_bytes=len(actual), expected_bytes=len(expected))
        raise ValueError('native shared actor mismatch: ' + label)
    report['compared_bytes'] += len(actual)


def validate_executor_identity(module, expected_hash, report):
    path = Path(module.__file__).resolve(strict=True)
    actual_hash = module.__source_sha256__
    report.update(helper_path=str(path), helper_sha256=actual_hash)
    require(actual_hash == expected_hash, 'imported executor hash differs from native prerequisite')


def execute(root, native_report_path, unicorn_path, report):
    native = read_native(root)
    report['native_fixture_sha256'] = native['sha256']
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
    from unicorn.x86_const import UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_IP, UC_X86_REG_BP, UC_X86_REG_SP
    original = original_bomb_cpu.BombCPU(root)
    require(native['descriptors'] == original.descriptors, 'native descriptor mismatch')
    cpu, data = original.cpu, original.DATA
    cpu.context_restore(original.initial_context)
    cpu.mem_write(0, original.initial_memory)
    cpu.mem_write(data + 0x1bae, bytes(31 * 38))
    cpu.mem_write(data + 0xc21e, bytes(33 * 8))
    cpu.mem_write(data + 0xc322, native['descriptors'])
    for offset, value in ((0xc1e0, struct.pack('<HH', 0, 0x4000)), (0xc1fe, struct.pack('<H', 0x4000)),
            (0xc204, struct.pack('<HH', 60, 33)), (0x206e, struct.pack('<H', 0x5000)),
            (0x6612, struct.pack('<HH', 0, 0x5000)), (0x78c4, struct.pack('<H', 0x4000))):
        cpu.mem_write(data + offset, value)
    original.registers(0xf000, 0xff00)
    cpu.emu_start(0x1293d, 0x12949, count=4)
    original.assert_return(0x2949, 0xf000, 0xff00)
    require(bytes(cpu.mem_read(data + 0x207a, 4)) == struct.pack('<HH', 0x6620, 0x209e),
            'original motion-table initialization failed')
    cpu.emu_start(0x12852, 0x12858, count=2)
    original.assert_return(0x2858, 0xf000, 0xff00)
    require(bytes(cpu.mem_read(data + 0xc1fc, 2)) == struct.pack('<H', 0xc21e),
            'original visual-table initialization failed')
    report['original_startup_ranges'] = ['CS:293d..2949', 'CS:2852..2858']
    for case in native['cases']:
        seed, records = case['seed'], case['actors']
        original.entries.clear()
        cpu.mem_write(0x40000, native['map'])
        cpu.mem_write(0x50000, native['words'])
        for offset, value in ((0x79a6, bytes(1)), (0x79ea, b'\x63\x63\x64\x64'),
                (0x79e6, b'\x01\x00'), (0x2080, bytes(2)), (0x207e, struct.pack('<H', 199)),
                (0x2076, bytes(2)), (0x208e, bytes(1)), (0x79f9, bytes(1)),
                (0x1afe, struct.pack('<I', int(seed['rng'], 16))),
                (0x78c2, struct.pack('<H', int(seed['frame']))), (0xc21e, struct.pack('<HH', 240, 168)),
                (0x208d, bytes((len(records),))), (0xc496, bytes((len(records) + 2,)))):
            cpu.mem_write(data + offset, value)
        for slot, (actor, visual) in enumerate(records, 1):
            cpu.mem_write(data + 0x1bae + slot * 38, actor)
            cpu.mem_write(data + 0xc21e + actor[1] * 8, visual)
        current = dict(name=seed['name'], initial_actors=len(records), samples=0, actor_states=0, instructions=0)
        report['cases'].append(current)
        for tick in case['ticks']:
            report.update(active_case=seed['name'], active_sample=int(tick['sample']))
            original.instructions = 0
            original.boundaries.clear()
            cpu.mem_write(data + 0x78c2, struct.pack('<H', int(tick['frame'])))
            original.registers(0xf000, 0xff00)
            cpu.emu_start(0x17ebb, 0x17eea, count=2000000)
            boundary = [cpu.reg_read(reg) for reg in
                (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_IP, UC_X86_REG_BP, UC_X86_REG_SP)]
            report['active_return_boundary'] = boundary
            require(boundary == [0x1000, 0x1aa2, 0x7eea, 0xf000, 0xff00], 'incomplete original actor pass')
            compare_bytes(report, bytes(cpu.mem_read(data + 0x208d, 1)), bytes((int(tick['count']),)), 'actor count')
            compare_bytes(report, bytes(cpu.mem_read(data + 0xc496, 1)), bytes((int(tick['visuals']),)), 'visual count')
            compare_bytes(report, bytes(cpu.mem_read(data + 0x1afe, 4)), bytes.fromhex(tick['rng']), 'rng')
            for slot, (actor, visual) in enumerate(tick['entries'], 1):
                raw = bytes(cpu.mem_read(data + 0x1bae + slot * 38, 38))
                compare_bytes(report, raw, actor, 'actor:' + str(slot))
                compare_bytes(report, bytes(cpu.mem_read(data + 0xc21e + raw[1] * 8, 8)), visual, 'visual:' + str(slot))
            expected_map = bytearray(native['map'])
            if tick['map'] != '-':
                for item in tick['map'].split(','):
                    index, value = item.split(':')
                    expected_map[int(index)] = int(value, 16)
            compare_bytes(report, bytes(cpu.mem_read(0x40000, 1980)), expected_map, 'byte-map')
            # The native next pre-pass includes flame/collapse work after this capture boundary.
            original.registers(0xf000, 0xff00)
            cpu.emu_start(0x1804e, 0x1806a, count=2000000)
            original.assert_return(0x806a, 0xf000, 0xff00)
            current['samples'] += 1
            current['actor_states'] += len(tick['entries'])
            current['instructions'] += original.instructions
            report['samples'] += 1
            report['actor_states'] += len(tick['entries'])
        current['original_helpers_entered'] = dict(original.entries)
    require(report['samples'] == 410 and report['actor_states'] == 7685, 'incomplete native comparison')
    require(report['compared_bytes'] == 1167770, 'incomplete native byte coverage')
    report.update(passed=True, complete_original_actor_passes=True, full_native_actor_records_compared=True,
        full_native_visual_records_compared=True, native_byte_map_compared=True, native_rng_compared=True,
        post_actor_flame_and_collapse_range='CS:804e..806a, after native comparison')


def run_analysis(root, native_report, unicorn_path, out):
    report = dict(passed=False, cases=[], samples=0, actor_states=0, compared_bytes=0,
        generator_sha256=producer_sha256(), original_instructions_patched=False,
        original_calls_stubbed=False, hardware_io_permitted=False, new_native_capture=False,
        compiled_cpp_comparison=False, native_post_pass_word_plane_compared=False,
        natural_route_claim=False, whole_game_complete=False,
        limitation='Retained seeded mixed actor traces only. Native post-pass word plane, natural routes, '
                   'hardware timing, rendered pixels and compiled C++ byte-for-byte comparison are not covered.')
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
        raise RuntimeError('optimized Python is not supported by original shared actor analysis')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path)
    parser.add_argument('--unicorn-path', type=Path)
    parser.add_argument('--native-report', type=Path)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.self_check:
        read_native(root)
        print('original_shared_actor_self_check=ok cases=10 samples=410 actor_states=7685 executor_required=0 live=0')
        return 0
    if args.out is None or args.native_report is None:
        parser.error('--out and --native-report are required unless --self-check is used')
    report = run_analysis(root, args.native_report.resolve(),
                          args.unicorn_path.resolve() if args.unicorn_path else None, args.out.resolve())
    print(json.dumps(dict(passed=report['passed'], cases=len(report['cases']), samples=report['samples'],
        actor_states=report['actor_states'], compared_bytes=report['compared_bytes'], report=str(args.out.resolve()))))
    return 0


if __name__ == '__main__':
    raise SystemExit(load_source_module(Path(__file__)).main())
