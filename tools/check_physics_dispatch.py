"""Compare uninterrupted production debris/collapse passes with original bytes."""
import argparse
import gzip
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from unittest.mock import patch

import check_collapse_continuous as continuous
from check_collapse_contacts_original import compact, contact_ranges
from source_guardrails import source_files

ROOT = Path(__file__).resolve().parents[1]
META = 'bbd42268e2e3f63e28531192780c7905fba8e1249264849f548dd358c3807108'
INPUT, STATE, CASES, STEPS, BATCH = 26730, 26724, 512, 16, 64
MODE = '--debug-original-physics-dispatch'
MARKER = ('physics_dispatch_app=ok scenes=4 steps=16 cases=64 compared_bytes=1710336 '
    'retained_debris=1402 retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 history_bytes=3 '
    'production_app=1 seeded=1 natural_route=0 whole_game_claim=0')
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
sha = continuous.history.sha


def validate_metadata(data):
    required = dict(schema='lezac.original-physics-dispatch-investigation.v1', passed=True,
        initial_scenes=32, steps_per_scene=16, expected_boundaries=512, boundaries=512,
        original_lane_indices=list(range(0, 96, 3)), original_dispatch_start='1000:804E',
        original_dispatch_end='1000:806A', original_dispatch_hex='833e7620007708813e7e20c8007203e89ac5833e8020007603e898d0',
        original_instructions_patched=False, original_calls_stubbed=False, hardware_io_permitted=False,
        production_app_executed=False, full_game_tick_proven=False, natural_route=False, whole_game_complete=False,
        observer_neutrality_memory_bytes=1048576, observer_neutrality_registers=14,
        serialized_state_sufficient_for_observed_dispatch=True, initial_calls_match_lane_fixture=True,
        boundaries_changed_by_preceding_debris=474,
        counterfactual_region_changes={'physical_debris': 474, 'tiles': 336, 'words': 336,
            'physical_collapse': 65, 'rng': 85, 'sound_state': 15},
        original_visits={'0x1804e': 512, '0x15102': 512, '0x1370e': 441, '0x145fa': 474,
            '0x1557b': 54, '0x1165a': 649, '0x12f9f': 54})
    if any(type(data.get(key)) is not type(value) or data[key] != value for key, value in required.items()):
        raise ValueError('original physics dispatch metadata scope differs')


def metadata():
    raw = (ROOT / 'tests/gameplay/physics_dispatch_original.json').read_bytes()
    if sha(raw) != META:
        raise ValueError('physics dispatch metadata fingerprint differs')
    data = json.loads(raw)
    validate_metadata(data)
    for path, key in ((ROOT / 'LEZAC.EXE', 'original_exe_sha256'),
        (ROOT / 'tools/original_bomb_cpu.py', 'executor_sha256'),
        (ROOT / 'tools/capture_original_contact_staging.py', 'staging_sha256'),
        (ROOT / 'tools/capture_original_fracture_retirement.py', 'reader_sha256'),
        (ROOT / 'tools/capture_original_physics_dispatch.py', 'producer_sha256'),
        (ROOT / 'tests/gameplay/collapse_lane_history_original.bin.gz', 'lane_fixture_sha256')):
        if sha(path.read_bytes()) != data[key]:
            raise ValueError('physics dispatch source pin differs: ' + path.name)
    return data


def batches(raw, data):
    if (len(raw) != 16 + CASES * (INPUT + STATE)
            or struct.unpack_from('<8sII', raw) != (b'LZCH0001', CASES, INPUT + STATE)):
        raise ValueError('physics dispatch fixture dimensions differ')
    lane = gzip.decompress((ROOT / 'tests/gameplay/collapse_lane_history_original.bin.gz').read_bytes())
    if struct.unpack_from('<8sII', lane) != (b'LZCH0001', 96, INPUT + STATE):
        raise ValueError('physics dispatch initial matrix differs')
    inputs, states = [], []
    for index in range(CASES):
        scene, step = divmod(index, STEPS)
        offset = 16 + index * (INPUT + STATE)
        incoming, state = raw[offset:offset + INPUT], raw[offset + INPUT:offset + INPUT + STATE]
        if struct.unpack_from('<HH', incoming) != (60, 33) or not struct.unpack_from('<H', incoming, 12)[0]:
            raise ValueError('physics dispatch input geometry or active collapse differs')
        if step == 0:
            initial = 16 + data['original_lane_indices'][scene] * (INPUT + STATE)
            if raw[offset:offset + INPUT + STATE] != lane[initial:initial + INPUT + STATE]:
                raise ValueError('physics dispatch first boundary differs from original lane matrix')
        elif (incoming[6:] != states[-1]
                or struct.unpack_from('<H', incoming, 4)[0] != (struct.unpack_from('<H', inputs[-1], 4)[0] + 1) & 65535):
            raise ValueError('physics dispatch sequence restores or skips state')
        inputs.append(incoming)
        states.append(state)
    if (sha(struct.pack('<8sII', b'LZCI0001', CASES, INPUT) + b''.join(inputs)) != data['input_sha256']
            or sha(struct.pack('<8sII', b'LZCO0001', CASES, STATE) + b''.join(states)) != data['expected_sha256']):
        raise ValueError('physics dispatch complete stream fingerprint differs')
    return [(struct.pack('<8sII', b'LZCI0001', 4, INPUT) + b''.join(inputs[start:start + BATCH:STEPS]),
             struct.pack('<8sII', b'LZCO0001', BATCH, STATE) + b''.join(states[start:start + BATCH]))
            for start in range(0, CASES, BATCH)]


def fixture(data, path=None):
    packed = (path or ROOT / 'tests/gameplay/physics_dispatch_original.bin.gz').read_bytes()
    if len(packed) > 512 * 1024 or sha(packed) != data['fixture_sha256']:
        raise ValueError('physics dispatch packed fingerprint differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(16 + CASES * (INPUT + STATE) + 1)
    if sha(raw) != data['fixture_raw_sha256']:
        raise ValueError('physics dispatch raw fingerprint differs')
    return batches(raw, data)


def check_source(source):
    continuous.check_source(source)
    first, last = contact_ranges(source, ('debugOriginalDebrisUpdate',))['debugOriginalDebrisUpdate']
    diagnostic = compact('\n'.join(source.splitlines()[first - 1:last]))
    required = ('bool physicsDispatch = false',
        'if (physicsDispatch && (!collapseLaneHistory || continuousCollapse))',
        '(physicsDispatch ? 4 : (continuousCollapse ? 12 : 96))',
        'physicsDispatch ? cases * 16 : continuousCollapse ? cases * 8 : cases',
        'const uint32_t steps = physicsDispatch ? 16 : continuousCollapse ? 8 : 1;',
        'if (physicsDispatch) { if (!debrisQueue_.empty()) updateDebrisRecords(); '
            'if (!collapseQueue_.empty()) updateCollapseRecords(); } else if (!continuousCollapse || !collapseQueue_.empty()) {')
    if any(diagnostic.count(compact(token)) != 1 for token in required):
        raise ValueError('physics dispatch mode, dimensions or original gated phase order differs')
    cli = compact('"--debug-original-physics-dispatch") { app.debugOriginalDebrisUpdate(argv[2], argv[3], '
        'true, false, false, true, false, true, true, false, true); return 0; }')
    if cli not in compact(source) or source.count('"--debug-original-physics-dispatch"') != 1:
        raise ValueError('physics dispatch CLI differs')


def compare(actual, expected):
    if actual == expected:
        return
    offset = next((index for index, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]), min(len(actual), len(expected)))
    case, field = divmod(offset - 16, STATE) if offset >= 16 else (-1, offset)
    raise ValueError('physics dispatch mismatch case=' + str(case) + ' state_offset=' + str(field)
        + ' actual_bytes=' + str(len(actual)) + ' expected_bytes=' + str(len(expected)))


def run_probe(exe, root, streams):
    root.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='attempt-', dir=root))
    report = dict(passed=False, production_app=True, input_only=True, masks=0, seeded=True, natural_route=False,
        whole_game_complete=False, full_game_tick_proven=False, continuous_physics_dispatch=True,
        batches=8, initial_scenes=32, steps=16, cases=512, state_bytes=CASES * STATE,
        original_metadata_sha256=META, completed_batches=[])
    try:
        for index, (incoming, expected) in enumerate(streams):
            target = out / ('batch-' + str(index))
            target.mkdir()
            child = dict(passed=False, production_app=True, input_only=True, masks=0, seeded=True,
                natural_route=False, full_game_tick_proven=False, whole_game_complete=False,
                initial_scenes=4, steps=16, cases=BATCH, github_sha=os.environ.get('GITHUB_SHA'),
                input_sha256=sha(incoming), expected_sha256=sha(expected), original_metadata_sha256=META)
            for name, raw in (('input.bin.gz', incoming), ('expected.bin.gz', expected)):
                (target / name).write_bytes(gzip.compress(raw, mtime=0))
            with tempfile.TemporaryDirectory(prefix='lezac-physics-input-') as input_dir, \
                    tempfile.TemporaryDirectory(prefix='lezac-physics-actual-') as actual_dir:
                input_path, actual_path = Path(input_dir) / 'input.bin', Path(actual_dir) / 'actual.bin'
                input_path.write_bytes(incoming)
                command = [str(exe.resolve()), MODE, str(input_path), str(actual_path)]
                child['command'] = command
                try:
                    result = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True, timeout=90)
                    child.update(returncode=result.returncode, stdout=result.stdout.decode(errors='replace'), stderr=result.stderr.decode(errors='replace'))
                    if result.returncode != 0 or result.stderr or result.stdout.strip().decode() != MARKER:
                        raise ValueError('physics dispatch production diagnostic failed')
                    if actual_path.stat().st_size >= 8 * 1024**2:
                        raise ValueError('physics dispatch actual exceeds reserve')
                    compare(actual_path.read_bytes(), expected)
                    child['passed'] = True
                except BaseException as error:
                    child.update(error=str(error), error_type=type(error).__name__)
                    if isinstance(error, subprocess.TimeoutExpired):
                        child.update(stdout=(error.stdout or b'').decode(errors='replace'), stderr=(error.stderr or b'').decode(errors='replace'))
                    raise
                finally:
                    if actual_path.exists() and actual_path.stat().st_size < 8 * 1024**2:
                        actual = actual_path.read_bytes()
                        child.update(actual_sha256=sha(actual), actual_bytes=len(actual))
                        (target / 'actual.bin.gz').write_bytes(gzip.compress(actual, mtime=0))
                    (target / 'result.json').write_text(json.dumps(child, indent=2) + '\n')
            report['completed_batches'].append(dict(index=index, result_sha256=sha((target / 'result.json').read_bytes()),
                input_sha256=child['input_sha256'], expected_sha256=child['expected_sha256'], actual_sha256=child['actual_sha256'],
                github_sha=child['github_sha'], command=child['command']))
        report['passed'] = True
    except BaseException as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print('physics_dispatch_retained=' + str(out.resolve()), flush=True)
        if sum(path.stat().st_size for path in root.rglob('*') if path.is_file()) >= 8 * 1024**2:
            raise ValueError('physics dispatch retained bundle exceeds reserve')


def rejects(function, *args):
    try:
        function(*args)
    except (ValueError, OSError, struct.error):
        return
    raise ValueError('physics dispatch negative control was accepted')


def self_check(data, source):
    mutations = (('bool physicsDispatch = false', 'bool physicsDispatch = true'),
        ('physicsDispatch && (!collapseLaneHistory || continuousCollapse)', 'false'),
        ('physicsDispatch ? 4 :', 'physicsDispatch ? 5 :'),
        ('physicsDispatch ? cases * 16 :', 'physicsDispatch ? cases * 8 :'),
        ('physicsDispatch ? 16 :', 'physicsDispatch ? 15 :'),
        ('if (!debrisQueue_.empty()) updateDebrisRecords();', 'if (!debrisQueue_.empty()) {}'),
        ('if (!collapseQueue_.empty()) updateCollapseRecords();', 'updateCollapseRecords();'),
        ('if (!debrisQueue_.empty()) updateDebrisRecords();\n                    if (!collapseQueue_.empty()) updateCollapseRecords();',
         'if (!collapseQueue_.empty()) updateCollapseRecords();\n                    if (!debrisQueue_.empty()) updateDebrisRecords();'),
        ('logicTick_ = static_cast<uint16_t>(initialTick + step);', 'logicTick_ = initialTick;'),
        ('logicTick_ = static_cast<uint16_t>(initialTick + step);', 'logicTick_ = static_cast<uint16_t>(initialTick + step); resetLevel(0);'),
        ('logicTick_ = static_cast<uint16_t>(initialTick + step);', 'logicTick_ = static_cast<uint16_t>(initialTick + step); take(26730);'),
        ('true, false, false, true, false, true, true, false, true);', 'true, false, false, true, false, true, true, false, false);'))
    for old, new in mutations:
        mutant = source.replace(old, new)
        if mutant == source:
            raise ValueError('physics dispatch source mutation did not apply')
        rejects(check_source, mutant)
    meta_mutants = (('boundaries', 511), ('steps_per_scene', 8), ('original_calls_stubbed', True),
        ('full_game_tick_proven', True), ('production_app_executed', True), ('observer_neutrality_registers', 13),
        ('original_visits', {'0x1804e': 512}), ('boundaries_changed_by_preceding_debris', 0))
    for key, value in meta_mutants:
        rejects(validate_metadata, dict(data, **{key: value}))
    streams = fixture(data)
    raw = gzip.decompress((ROOT / 'tests/gameplay/physics_dispatch_original.bin.gz').read_bytes())
    with tempfile.TemporaryDirectory(prefix='lezac-physics-fixture-controls-') as directory:
        for index, variant in enumerate((raw[:15], raw[:-1], raw + b'\0', raw[:20] + bytes([raw[20] ^ 1]) + raw[21:])):
            path = Path(directory) / (str(index) + '.gz')
            path.write_bytes(gzip.compress(variant, mtime=0))
            rejects(fixture, data, path)
    for offset in (20, 16 + INPUT + STATE + 6, 16 + INPUT + STATE + 4):
        variant = raw[:offset] + bytes([raw[offset] ^ 1]) + raw[offset + 1:]
        rejects(batches, variant, data)
    for offset in (0, 16, 16 + 5952, 16 + 25139, len(streams[0][1]) - 1):
        expected = streams[0][1]
        rejects(compare, expected[:offset] + bytes([expected[offset] ^ 1]) + expected[offset + 1:], expected)
    attempts, failures = 0, 0
    with tempfile.TemporaryDirectory(prefix='lezac-physics-runner-controls-') as directory:
        root = Path(directory)
        preserved = {}
        for mode in ('ok', 'mismatch', 'nonzero', 'stderr', 'wrong_marker', 'timeout', 'ok'):
            calls = []

            def runner(command, **kwargs):
                index = len(calls)
                if (len(command) != 4 or command[1] != MODE or Path(command[2]).read_bytes() != streams[index][0]
                        or kwargs['env']['SDL_AUDIODRIVER'] != 'dummy' or kwargs['env']['SDL_VIDEODRIVER'] != 'dummy'):
                    raise ValueError('physics dispatch runner received expected state or enabled audio')
                expected = streams[index][1]
                failed = index == 3 and mode != 'ok'
                actual = expected[:31] if failed and mode == 'timeout' else expected
                if failed and mode == 'mismatch':
                    actual = expected[:-1] + bytes([expected[-1] ^ 1])
                Path(command[3]).write_bytes(actual)
                calls.append(actual)
                if failed and mode == 'timeout':
                    raise subprocess.TimeoutExpired(command, 90, output=b'partial physics stdout', stderr=b'partial physics stderr')
                return subprocess.CompletedProcess(command, 1 if failed and mode == 'nonzero' else 0,
                    b'wrong marker' if failed and mode == 'wrong_marker' else MARKER.encode(),
                    b'error' if failed and mode == 'stderr' else b'')

            before = set(root.glob('attempt-*'))
            with patch.object(subprocess, 'run', side_effect=runner):
                try:
                    run_probe(Path('mocked-not-a-game'), root, streams)
                except (ValueError, subprocess.TimeoutExpired):
                    if mode == 'ok':
                        raise
                    failures += 1
                else:
                    if mode != 'ok':
                        raise ValueError('physics dispatch runner failure was accepted')
            out, = set(root.glob('attempt-*')) - before
            top = json.loads((out / 'result.json').read_bytes())
            if top['passed'] != (mode == 'ok') or len(top['completed_batches']) != (8 if mode == 'ok' else 3):
                raise ValueError('physics dispatch partial result differs')
            for index, actual in enumerate(calls):
                child = json.loads((out / ('batch-' + str(index)) / 'result.json').read_bytes())
                if child['passed'] != (mode == 'ok' or index < 3):
                    raise ValueError('physics dispatch child disposition differs')
                for name, wanted in (('input.bin.gz', streams[index][0]), ('expected.bin.gz', streams[index][1]), ('actual.bin.gz', actual)):
                    if gzip.decompress((out / ('batch-' + str(index)) / name).read_bytes()) != wanted:
                        raise ValueError('physics dispatch retained bytes differ')
            for path, pin in preserved.items():
                if sha(path.read_bytes()) != pin:
                    raise ValueError('physics dispatch rerun changed prior evidence')
            preserved = {path: sha(path.read_bytes()) for path in root.rglob('*') if path.is_file()}
            attempts += len(calls)
    print('physics_dispatch_checker=ok source_mutants=12 metadata_mutants=8 fixture_mutants=4 sequence_mutants=3 '
        'output_mutants=5 mocked_failures=' + str(failures) + ' mocked_batches=' + str(attempts) + ' production_app=0')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if bool(args.exe) != bool(args.out):
        parser.error('--out is required only with --exe')
    data = metadata()
    source = '\n'.join(item.text for item in source_files(ROOT, ('app', 'gameplay'), 'runtime'))
    check_source(source)
    if args.self_check:
        self_check(data, source)
    elif args.exe:
        run_probe(args.exe, args.out, fixture(data))
        print('physics_dispatch_original=ok batches=8 scenes=32 steps=16 cases=512 production_app=1 input_only=1 masks=0 natural_route=0 whole_game_claim=0')
    else:
        fixture(data)
        print('physics_dispatch_fixture=ok scenes=32 steps=16 cases=512 production_app=0 masks=0 natural_route=0 whole_game_claim=0')


if __name__ == '__main__':
    main()
