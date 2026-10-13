"""Verify repeated mocked checker calls preserve every earlier diagnostic bundle."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import check_collapse_lane_history as lane
import check_collapse_seed_history as seed


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest(root):
    return {str(path.relative_to(root)): sha(path.read_bytes())
            for path in root.rglob('*') if path.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seed-fixture', type=Path, default=seed.FIXTURE)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='attempt-', dir=args.out))
    report = dict(passed=False, mocked_child=True, production_app_executed=False,
                  natural_gameplay=False, whole_game_claim=False, profiles={})
    try:
        for name in ('seed', 'lane', 'support'):
            module = seed if name == 'seed' else lane
            if name == 'seed':
                with patch.object(seed, 'FIXTURE', args.seed_fixture):
                    data = seed.metadata()
                incoming, expected, sizes = seed.decode(data, args.seed_fixture)
                decoded = (incoming, expected, sizes)
                marker = b'collapse_contacts_probe=ok cases=576 original_fidelity_claim=0'
                command_name = '--debug-collapse-contacts-original'
            else:
                data = lane.metadata(name)
                incoming, expected = lane.decode(data)
                decoded = (incoming, expected)
                marker = (b'collapse_lane_history_app=ok cases=96 compared_bytes=2565504 retained_debris=1402 '
                    b'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 history_bytes=3 '
                    b'production_app=1 seeded=1 natural_route=0 whole_game_claim=0')
                command_name = '--debug-original-collapse-lane-history'
            root = out / name
            root.mkdir()
            (root / 'existing-evidence.txt').write_text('preserve this unrelated earlier evidence\n')
            previous = manifest(root)
            outcomes = []
            for mode in ('ok', 'mismatch', 'nonzero', 'timeout', 'ok'):
                before = set(root.glob('attempt-*'))
                written = expected if mode != 'mismatch' else expected[:-1] + bytes((expected[-1] ^ 1,))
                if mode == 'timeout':
                    written = written[:25]

                def runner(command, **kwargs):
                    if (len(command) != 4 or command[1] != command_name
                            or Path(command[2]).read_bytes() != incoming
                            or kwargs['env']['SDL_AUDIODRIVER'] != 'dummy'
                            or kwargs['env']['SDL_VIDEODRIVER'] != 'dummy'):
                        raise ValueError('repeat-run child contract changed input or enabled audio')
                    Path(command[3]).write_bytes(written)
                    if mode == 'timeout':
                        raise subprocess.TimeoutExpired(command, 60, output=b'partial out', stderr=b'partial err')
                    return subprocess.CompletedProcess(command, 1 if mode == 'nonzero' else 0, marker, b'')

                failure = None
                with patch.object(module, 'decode', return_value=decoded), patch.object(subprocess, 'run', side_effect=runner):
                    try:
                        if name == 'seed':
                            module.run_probe(root / 'mocked-not-a-game', root, data, True)
                        else:
                            module.run_probe(root / 'mocked-not-a-game', root, data)
                    except (ValueError, subprocess.TimeoutExpired) as error:
                        failure = type(error).__name__
                        if mode == 'ok':
                            raise
                    else:
                        if mode != 'ok':
                            raise ValueError('repeated failing child was accepted')
                created = set(root.glob('attempt-*')) - before
                if len(created) != 1:
                    raise ValueError('checker did not create exactly one new attempt bundle')
                bundle, = created
                result = json.loads((bundle / 'result.json').read_bytes())
                if result['passed'] != (mode == 'ok'):
                    raise ValueError('repeat-run result does not reflect child failure')
                for path, wanted in (('input.bin.gz', incoming), ('expected.bin.gz', expected), ('actual.bin.gz', written)):
                    if gzip.decompress((bundle / path).read_bytes()) != wanted:
                        raise ValueError('repeat-run stream differs: ' + path)
                current = manifest(root)
                if any(current.get(path) != pin for path, pin in previous.items()):
                    raise ValueError('repeat-run modified or removed earlier evidence')
                previous = current
                outcomes.append(dict(mode=mode, failure=failure, bundle=bundle.name, files=len(current)))
            report['profiles'][name] = outcomes
        report.update(passed=True, profiles_checked=3, mocked_attempts=15,
                      failure_attempts=9, successful_attempts=6, earlier_evidence_preserved=True)
    except BaseException as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print('collapse_history_repetition_retained=' + str(out.resolve()), flush=True)
        if sum(path.stat().st_size for path in args.out.rglob('*') if path.is_file()) >= 8 * 1024**2:
            raise ValueError('repeat-run controls exceed the retained reserve')
    print('collapse_history_repetition_contract=ok profiles=3 mocked_attempts=15 failures=9 production_app=0')


if __name__ == '__main__':
    main()
