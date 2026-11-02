"""Authenticate one-case replay scope without weakening the full-corpus CLI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import check_frame_actor_pass_fixture as checker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.fixture.read_bytes() != checker.read_fixture():
        raise ValueError('Case CLI input is not the frozen full corpus')
    args.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=args.out))
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    protected = {str(path): sha(path) for path in (args.exe, args.fixture, checker.ROOT / 'LEZAC.EXE')}
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', TMPDIR=str(out))
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    report = dict(status='failed', positive_cases=[], negatives=[], protected_sha256=protected)

    def run(label, arguments):
        result = subprocess.run([str(args.exe), *map(str, arguments)], env=environment,
            capture_output=True, timeout=180, creationflags=creationflags)
        (out / (label + '.log')).write_bytes(result.stdout + result.stderr)
        return result

    try:
        for case in (0, 123, 875):
            result = run('case-' + str(case), ['--case', str(case), args.fixture, checker.ROOT])
            for token in (f'frame_actor_pass_case=ok case={case} '.encode(), b'authenticated_cases=876 ',
                          b'executed_cases=1 replays=9 ', b'full_memory=1 canonical_mz=1 ',
                          b'full_corpus_claim=0 computed_irq_cases=0 intermittent_hold_cleared=0'):
                if result.returncode or token not in result.stdout:
                    raise ValueError('One-case positive scope differs: ' + str(case))
            report['positive_cases'].append(case)
        negatives = []
        for index, value in enumerate(('', '-1', '+1', '876', '123suffix', ' 123', '999999999999999999999999')):
            negatives.append(('bad-index-' + str(index), ['--case', value, args.fixture, checker.ROOT], b'case must be an integer'))
        changed = bytearray(args.fixture.read_bytes());changed[1234] ^= 1
        bad = out / 'changed-unselected.bin';bad.write_bytes(changed)
        negatives.extend([
            ('changed-unselected', ['--case', '123', bad, checker.ROOT], b'Pass corpus fingerprint differs'),
            ('missing-fixture', ['--case', '123', out / 'missing.bin', checker.ROOT], b'frame_actor_pass=failed'),
            ('missing-mz', ['--case', '123', args.fixture, out / 'missing-root'], b'frame_actor_pass=failed'),
            ('extra-argument', ['--case', '123', args.fixture, checker.ROOT, 'extra'], b'Expected fixture'),
        ])
        for name, arguments, reason in negatives:
            result = run(name, arguments)
            if result.returncode == 0 or reason not in result.stderr or b'frame_actor_pass=failed' not in result.stderr:
                raise ValueError('Case CLI negative escaped or crashed: ' + name)
            report['negatives'].append(name)
        if any(sha(Path(path)) != digest for path, digest in protected.items()):
            raise ValueError('Case CLI changed protected inputs')
        report.update(status='passed', protected_inputs_preserved=True, full_corpus_execution_claim=False)
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('frame_actor_pass_case_cli=ok positive_cases=3 negative_controls=11 authenticated_cases=876 full_corpus_execution_claim=0')


if __name__ == '__main__':
    main()
