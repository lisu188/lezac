"""Compare all original repeated-collapse boundaries in bounded input-only App batches."""
import argparse
import gzip
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from unittest.mock import patch

import check_collapse_lane_history as history
from check_collapse_contacts_original import compact
from source_guardrails import source_files

CASES, BATCH, INPUT, STATE = 768, 96, 26730, 26724
RESERVE = 8 * 1024**2


def check_source(source):
    history.check_source(source)
    if compact('(!collapseLaneHistory && collapseCount == 0)') not in compact(source):
        raise ValueError('input-only continuity empty-queue validation differs')


def batches(raw, data):
    if (len(raw) != 16 + CASES * (INPUT + STATE)
            or struct.unpack_from('<8sII', raw) != (b'LZCH0001', CASES, INPUT + STATE)):
        raise ValueError('continuity fixture dimensions differ')
    initial_profile = 'lane' if history.profile(data)[0] == 'contact-continuity' else 'support'
    support = gzip.decompress(history.PROFILES[initial_profile]['fixture'].read_bytes())
    if struct.unpack_from('<8sII', support) != (b'LZCH0001', 96, INPUT + STATE):
        raise ValueError('continuity initial-scene fixture dimensions differ')
    requests, states, active = [], [], 0
    for index in range(CASES):
        offset = 16 + index * (INPUT + STATE)
        incoming, state = raw[offset:offset + INPUT], raw[offset + INPUT:offset + INPUT + STATE]
        scene, step = divmod(index, 8)
        prior = 16 + scene * (INPUT + STATE)
        initial = support[prior:prior + INPUT]
        tick = (struct.unpack_from('<H', initial, 4)[0] + step) & 65535
        if step == 0:
            if incoming != initial or state != support[prior + INPUT:prior + INPUT + STATE]:
                raise ValueError('continuity initial boundary differs from trusted original')
        elif incoming != struct.pack('<3H', 60, 33, tick) + states[-1]:
            raise ValueError('continuity repeated boundary order or inherited state differs')
        live = struct.unpack_from('<H', incoming, 12)[0]
        if live:
            active += 1
        elif state != incoming[6:]:
            raise ValueError('original empty-queue skip changed serialized state')
        requests.append(incoming)
        states.append(state)
    if active != data['groups']['active_update']:
        raise ValueError('continuity active/empty queue coverage differs')
    incoming = struct.pack('<8sII', b'LZCI0001', CASES, INPUT) + b''.join(requests)
    expected = struct.pack('<8sII', b'LZCO0001', CASES, STATE) + b''.join(states)
    if history.sha(incoming) != data['input_sha256'] or history.sha(expected) != data['expected_sha256']:
        raise ValueError('continuity original stream fingerprint differs')
    return [(struct.pack('<8sII', b'LZCI0001', BATCH, INPUT) + b''.join(requests[start:start + BATCH]),
             struct.pack('<8sII', b'LZCO0001', BATCH, STATE) + b''.join(states[start:start + BATCH]))
            for start in range(0, CASES, BATCH)]


def fixture(data, path=None):
    packed = (path or history.profile(data)[1]['fixture']).read_bytes()
    if len(packed) > 512 * 1024 or history.sha(packed) != data['fixture_sha256']:
        raise ValueError('continuity packed fixture fingerprint differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(16 + CASES * (INPUT + STATE) + 1)
    if history.sha(raw) != data['fixture_raw_sha256']:
        raise ValueError('continuity raw fixture fingerprint differs')
    return batches(raw, data)


def run_probe(exe, root, data, streams=None, continuous=False):
    streams = fixture(data) if streams is None else streams
    root.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='attempt-', dir=root))
    report = dict(passed=False, production_app=True, input_only=True, batches=8, cases=CASES,
        state_bytes=CASES * STATE, masks=0, seeded=True, natural_route=False,
        whole_game_complete=False, continuous_app_execution_proven=False,
        original_metadata_sha256=history.profile(data)[1]['metadata_sha256'],
        fixture_profile=history.profile(data)[0], completed_batches=[])
    if continuous:
        report.update(initial_scenes=96, boundaries_per_scene=8, continuous_collapse_updates=True)
    try:
        if len(streams) != 8:
            raise ValueError('continuity batch count differs')
        for index, batch in enumerate(streams):
            report['current_batch'] = index
            target = out / ('batch-' + str(index))
            history.run_probe(exe, target, data, streams=batch, continuous=continuous)
            result, = target.glob('attempt-*/result.json')
            child = json.loads(result.read_bytes())
            if not child['passed'] or child['cases'] != BATCH or child['fixture_profile'] != history.profile(data)[0]:
                raise ValueError('continuity production batch result differs')
            report['completed_batches'].append(dict(index=index, path=str(result.resolve()),
                input_sha256=child['input_sha256'], expected_sha256=child['expected_sha256'],
                actual_sha256=child['actual_sha256'], command=child['command'], github_sha=child['github_sha']))
        report['passed'] = True
    except BaseException as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print('collapse_continuity_retained=' + str(out.resolve()), flush=True)
        if sum(path.stat().st_size for path in root.rglob('*') if path.is_file()) >= RESERVE:
            raise ValueError('continuity retained batches exceed local reserve')


def self_check(data, source):
    def rejects(function, value):
        try:
            function(value)
        except (ValueError, OSError, EOFError):
            return
        raise ValueError('continuity negative control was accepted')

    for replacement in ('collapseCount == 0', 'false'):
        mutant = source.replace('(!collapseLaneHistory && collapseCount == 0)', replacement)
        if mutant == source:
            raise ValueError('continuity source mutant did not apply')
        rejects(check_source, mutant)
    metadata_mutants = [('cases', 767), ('continuous_original_image', False),
        ('serialized_state_sufficient_for_observed_sequence', False), ('initial_scenes', 95),
        ('boundaries_per_scene', 7), ('groups', {'active_update': 768, 'empty_queue_skip': 0}),
        ('original_caller_gate_hex', '90'), ('continuous_app_execution_proven', True),
        ('original_calls_stubbed', True)]
    if history.profile(data)[0] == 'contact-continuity':
        metadata_mutants.extend((('initial_live_collapse_records', 1),
            ('initial_scene_groups', {'debris': 96}), ('original_visits', {'0x15102': 768}),
            ('initial_calls_match_lane_fixture', False)))
    for key, value in metadata_mutants:
        rejects(history.validate_metadata, dict(data, **{key: value}))
    streams = fixture(data)
    raw = gzip.decompress(history.profile(data)[1]['fixture'].read_bytes())
    with tempfile.TemporaryDirectory(prefix='lezac-continuity-fixture-') as directory:
        for index, variant in enumerate((raw[:15], raw[:-1], raw + b'\0',
                raw[:20] + bytes((raw[20] ^ 1,)) + raw[21:], raw[:-1] + bytes((raw[-1] ^ 1,)))):
            path = Path(directory) / (str(index) + '.gz')
            path.write_bytes(gzip.compress(variant, mtime=0))
            rejects(lambda value: fixture(data, value), path)
    stride = INPUT + STATE
    reordered = raw[:16] + raw[16 + stride:16 + 2 * stride] + raw[16:16 + stride] + raw[16 + 2 * stride:]
    wrong_tick = bytearray(raw)
    wrong_tick[16 + stride + 4] ^= 1
    wrong_inheritance = bytearray(raw)
    wrong_inheritance[16 + stride + 100] ^= 1
    for variant in (reordered, bytes(wrong_tick), bytes(wrong_inheritance)):
        rejects(lambda value: batches(value, data), variant)
    incoming, expected = streams[0]
    for offset in (0, 16, 16 + 5952, len(expected) - 3, len(expected) - 1):
        mutant = expected[:offset] + bytes((expected[offset] ^ 1,)) + expected[offset + 1:]
        rejects(lambda value: history.compare(value, expected), mutant)
    attempts = 0
    for mode in ('ok', 'mismatch', 'nonzero', 'timeout'):
        with tempfile.TemporaryDirectory(prefix='lezac-continuity-runner-') as directory:
            root = Path(directory) / 'retained'
            calls = []

            def runner(command, **kwargs):
                index = len(calls)
                incoming, expected = streams[index]
                if (len(command) != 4 or command[1] != '--debug-original-collapse-lane-history'
                        or Path(command[2]).read_bytes() != incoming
                        or kwargs['env']['SDL_AUDIODRIVER'] != 'dummy'
                        or kwargs['env']['SDL_VIDEODRIVER'] != 'dummy'):
                    raise ValueError('continuity runner supplied expected bytes or enabled audio')
                failure = mode != 'ok' and index == 3
                written = expected
                if failure and mode == 'mismatch':
                    written = expected[:-1] + bytes((expected[-1] ^ 1,))
                if failure and mode == 'timeout':
                    written = expected[:25]
                calls.append(written)
                Path(command[3]).write_bytes(written)
                if failure and mode == 'timeout':
                    raise subprocess.TimeoutExpired(command, 90, output=b'partial stdout', stderr=b'partial stderr')
                marker = ('collapse_lane_history_app=ok cases=96 compared_bytes=2565504 retained_debris=1402 '
                          'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 history_bytes=3 '
                          'production_app=1 seeded=1 natural_route=0 whole_game_claim=0')
                return subprocess.CompletedProcess(command, int(failure and mode == 'nonzero'), marker.encode(), b'')

            with patch.object(history.subprocess, 'run', side_effect=runner):
                try:
                    run_probe(Path(directory) / 'mocked-not-a-game', root, data, streams)
                except (ValueError, subprocess.TimeoutExpired):
                    if mode == 'ok':
                        raise
                else:
                    if mode != 'ok':
                        raise ValueError('continuity batch failure was accepted')
            bundle, = root.glob('attempt-*')
            result = json.loads((bundle / 'result.json').read_bytes())
            if result['passed'] != (mode == 'ok') or len(calls) != (8 if mode == 'ok' else 4):
                raise ValueError('continuity failure batch tracking differs')
            for index, written in enumerate(calls):
                child, = (bundle / ('batch-' + str(index))).glob('attempt-*')
                for name, wanted in (('input.bin.gz', streams[index][0]),
                                     ('expected.bin.gz', streams[index][1]), ('actual.bin.gz', written)):
                    if gzip.decompress((child / name).read_bytes()) != wanted:
                        raise ValueError('continuity batch did not retain exact streams')
            attempts += len(calls)
            if mode == 'ok':
                retained = {path.relative_to(root): history.sha(path.read_bytes())
                            for path in root.rglob('*') if path.is_file()}
                calls.clear()
                with patch.object(history.subprocess, 'run', side_effect=runner):
                    run_probe(Path(directory) / 'mocked-not-a-game', root, data, streams)
                if len(calls) != 8 or len(list(root.glob('attempt-*'))) != 2:
                    raise ValueError('continuity repeated success reused an attempt')
                if any(history.sha((root / name).read_bytes()) != pin for name, pin in retained.items()):
                    raise ValueError('continuity repeated success changed earlier evidence')
                attempts += len(calls)
    print('collapse_continuity_checker=ok source_mutants=2 metadata_mutants=' + str(len(metadata_mutants)) + ' fixture_mutants=5 '
          'sequence_mutants=3 output_mutants=5 mocked_modes=4 mocked_batches=' + str(attempts) +
          ' repeated_success=1 production_app=0')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--self-check', action='store_true')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--profile', choices=('continuity', 'contact-continuity'), default='continuity')
    args = parser.parse_args()
    if bool(args.exe) != bool(args.out):
        parser.error('--out is required only with --exe')
    data = history.metadata(args.profile)
    source = '\n'.join(item.text for item in source_files(history.ROOT, ('app', 'gameplay'), 'runtime'))
    check_source(source)
    if args.self_check:
        self_check(data, source)
    elif args.exe:
        run_probe(args.exe, args.out, data)
        print('collapse_continuity_original=ok batches=8 cases=768 production_app=1 input_only=1 masks=0 '
              'natural_route=0 whole_game_claim=0')
    else:
        streams = fixture(data)
        print('collapse_continuity_fixture=ok batches=' + str(len(streams)) +
              ' cases=768 state_bytes=20524032 production_app=0 natural_route=0 whole_game_claim=0')


if __name__ == '__main__':
    main()
