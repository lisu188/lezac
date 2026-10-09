"""Compare eight unbroken production collapse updates with original state."""
import argparse
import gzip
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from unittest.mock import patch

import check_collapse_continuity as continuity
import check_collapse_lane_history as history
from check_collapse_contacts_original import compact, contact_ranges
from source_guardrails import source_files


def check_source(source):
    continuity.check_source(source)
    first, last = contact_ranges(source, ('debugOriginalDebrisUpdate',))['debugOriginalDebrisUpdate']
    diagnostic = compact('\n'.join(source.splitlines()[first - 1:last]))
    required = ('bool continuousCollapse = false',
        'if (continuousCollapse && !collapseLaneHistory)',
        '(continuousCollapse ? 12 : 96)',
        'appendWord(outputHeader, static_cast<uint16_t>(continuousCollapse ? cases * 8 : cases));',
        'const uint16_t initialTick = static_cast<uint16_t>(logicTick_);',
        'const uint32_t steps = continuousCollapse ? 8 : 1;',
        'for (uint32_t step = 0; step < steps; ++step) {',
        'logicTick_ = static_cast<uint16_t>(initialTick + step);',
        'if (!continuousCollapse || !collapseQueue_.empty()) {')
    if any(diagnostic.count(compact(token)) != 1 for token in required):
        raise ValueError('continuous collapse setup, tick or empty-queue gate differs')
    start = diagnostic.index(compact('for (uint32_t step = 0; step < steps; ++step) {'))
    end = diagnostic.index('if(input.peek()', start)
    loop = diagnostic[start:end]
    forbidden = ('resetLevel(', 'take(', '.clear()', 'restoreForFixture(', 'restoreRequestForFixture(',
                 'restoreLatchForFixture(', 'randomSeed_=', 'damageLaneData_=', 'readSeed(')
    if any(token in loop for token in forbidden) or diagnostic.count('resetLevel(') != 1:
        raise ValueError('continuous collapse restores state between observed boundaries')
    cli = compact('"--debug-original-collapse-continuous") { app.debugOriginalDebrisUpdate(argv[2], argv[3], '
                  'true, false, false, true, false, true, true, true); return 0; }')
    if cli not in compact(source) or source.count('"--debug-original-collapse-continuous"') != 1:
        raise ValueError('continuous collapse CLI dispatch differs')


def fixture(data):
    batches = []
    for incoming, expected in continuity.fixture(data):
        initial = b''.join(incoming[16 + index * history.INPUT:16 + (index + 1) * history.INPUT]
                           for index in range(0, 96, 8))
        batches.append((struct.pack('<8sII', b'LZCI0001', 12, history.INPUT) + initial, expected))
    if len(batches) != 8 or any(len(request) != 16 + 12 * history.INPUT for request, _ in batches):
        raise ValueError('continuous collapse initial-scene dimensions differ')
    return batches


def self_check(data, source):
    mutations = (
        ('bool continuousCollapse = false', 'bool continuousCollapse = true'),
        ('if (continuousCollapse && !collapseLaneHistory)', 'if (false)'),
        ('(continuousCollapse ? 12 : 96)', '(continuousCollapse ? 96 : 96)'),
        ('continuousCollapse ? cases * 8 : cases', 'cases'),
        ('const uint32_t steps = continuousCollapse ? 8 : 1;', 'const uint32_t steps = 1;'),
        ('logicTick_ = static_cast<uint16_t>(initialTick + step);', 'logicTick_ = initialTick;'),
        ('if (!continuousCollapse || !collapseQueue_.empty()) {', 'if (!continuousCollapse || collapseQueue_.empty()) {'),
        ('logicTick_ = static_cast<uint16_t>(initialTick + step);',
         'logicTick_ = static_cast<uint16_t>(initialTick + step); resetLevel(0);'),
        ('logicTick_ = static_cast<uint16_t>(initialTick + step);',
         'logicTick_ = static_cast<uint16_t>(initialTick + step); take(26730);'),
        ('true, false, false, true, false, true, true, true);', 'true, false, false, true, false, true, true, false);'),
    )
    for old, new in mutations:
        mutant = source.replace(old, new)
        if mutant == source:
            raise ValueError('continuous source mutant did not apply')
        try:
            check_source(mutant)
        except ValueError:
            pass
        else:
            raise ValueError('continuous source mutant was accepted')
    streams = fixture(data)
    marker = (b'collapse_continuous_app=ok scenes=12 steps=8 cases=96 compared_bytes=2565504 retained_debris=1402 '
        b'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 history_bytes=3 '
        b'production_app=1 seeded=1 natural_route=0 whole_game_claim=0\n')
    attempts, failures = 0, 0
    with tempfile.TemporaryDirectory(prefix='lezac-collapse-continuous-controls-') as temporary:
        root = Path(temporary)
        preserved = {}
        for mode in ('ok', 'mismatch', 'nonzero', 'stderr', 'wrong_marker', 'timeout', 'ok'):
            calls = []

            def child(command, **kwargs):
                index = len(calls)
                if len(command) != 4 or command[1] != '--debug-original-collapse-continuous':
                    raise ValueError('continuous probe command differs')
                if Path(command[2]).read_bytes() != streams[index][0]:
                    raise ValueError('continuous probe receives more than initial state')
                environment = kwargs['env']
                if environment['SDL_AUDIODRIVER'] != 'dummy' or environment['SDL_VIDEODRIVER'] != 'dummy':
                    raise ValueError('continuous probe execution is not silent')
                expected = streams[index][1]
                failed = mode != 'ok' and index == 3
                actual = expected[:-1] if failed and mode == 'timeout' else expected
                if failed and mode == 'mismatch':
                    actual = actual[:16 + 26724] + bytes([actual[16 + 26724] ^ 1]) + actual[17 + 26724:]
                Path(command[3]).write_bytes(actual)
                calls.append(actual)
                if failed and mode == 'timeout':
                    raise subprocess.TimeoutExpired(command, 90, output=b'partial continuous probe')
                return subprocess.CompletedProcess(command, 1 if failed and mode == 'nonzero' else 0,
                    b'wrong marker\n' if failed and mode == 'wrong_marker' else marker,
                    b'diagnostic error' if failed and mode == 'stderr' else b'')

            before = {path.relative_to(root) for path in root.glob('attempt-*')}
            with patch.object(history.subprocess, 'run', child):
                try:
                    continuity.run_probe(Path('mocked-not-a-game'), root, data, streams=streams, continuous=True)
                except (ValueError, subprocess.TimeoutExpired):
                    if mode == 'ok':
                        raise
                    failures += 1
                else:
                    if mode != 'ok':
                        raise ValueError('continuous probe failure was accepted')
            bundle, = [path for path in root.glob('attempt-*') if path.relative_to(root) not in before]
            top = json.loads((bundle / 'result.json').read_bytes())
            if top['passed'] != (mode == 'ok') or not top['continuous_collapse_updates']:
                raise ValueError('continuous probe result scope differs')
            if len(calls) != (8 if mode == 'ok' else 4) or len(top['completed_batches']) != (8 if mode == 'ok' else 3):
                raise ValueError('continuous probe partial progress differs')
            for index, actual in enumerate(calls):
                result, = (bundle / ('batch-' + str(index))).glob('attempt-*/result.json')
                for name, wanted in (('input.bin.gz', streams[index][0]), ('expected.bin.gz', streams[index][1]), ('actual.bin.gz', actual)):
                    if gzip.decompress(result.with_name(name).read_bytes()) != wanted:
                        raise ValueError('continuous probe did not retain exact streams')
            for path, pin in preserved.items():
                if history.sha((root / path).read_bytes()) != pin:
                    raise ValueError('continuous probe overwrote an earlier retained attempt')
            preserved = {path.relative_to(root): history.sha(path.read_bytes()) for path in root.rglob('*') if path.is_file()}
            attempts += len(calls)
    print('collapse_continuous_checker=ok source_mutants=10 mocked_failures=' + str(failures) +
          ' mocked_batches=' + str(attempts) + ' repeated_success=1 production_app=0')


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
        continuity.run_probe(args.exe, args.out, data, streams=fixture(data), continuous=True)
        print('collapse_continuous_original=ok batches=8 scenes=96 steps=8 cases=768 production_app=1 '
              'input_only=1 masks=0 natural_route=0 whole_game_claim=0')
    else:
        streams = fixture(data)
        print('collapse_continuous_fixture=ok batches=' + str(len(streams)) +
              ' scenes=96 steps=8 cases=768 state_bytes=20524032 production_app=0 natural_route=0 whole_game_claim=0')


if __name__ == '__main__':
    main()
