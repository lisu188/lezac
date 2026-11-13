"""Repeat the native record-save oracle check without replacing earlier evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

LEVELS = {0, 1, 7, 8, 255}
MARKER = b'record_save_original=ok cases=5 compared_bytes=460 differences=0'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replay(exe, fixture, out):
    out.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    records = evidence / 'records'
    expected = fixture.read_bytes()
    report = dict(passed=False, native_runs=[], binary_cases=10, compared_bytes=920,
                  executable_sha256=sha(exe.read_bytes()), fixture_sha256=sha(expected),
                  full_app_executed=False, fresh_original_execution=False, whole_game_complete=False)
    first = {}
    initial_error = None
    try:
        for index in range(2):
            command = [str(exe.resolve()), str(fixture.resolve()), str(records.resolve())]
            result = subprocess.run(command, env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'),
                                    capture_output=True, timeout=60)
            report['native_runs'].append(dict(command=command, exit_code=result.returncode))
            for stream in ('stdout', 'stderr'):
                (evidence / (str(index) + '.' + stream)).write_bytes(getattr(result, stream))
            require(result.returncode == 0 and not result.stderr and MARKER in result.stdout,
                    'native record-save rerun failed: ' + result.stderr.decode(errors='replace'))
            current = {path: sha(path.read_bytes()) for path in records.rglob('*') if path.is_file()}
            require(len(current) == 10 * (index + 1), 'native run did not retain independent record outputs')
            for path, digest in first.items():
                require(path in current and current[path] == digest, 'first run record output changed')
            for path in current:
                require(path.name in {'record-level-' + str(level) + extension
                                     for level in LEVELS for extension in ('.dat', '.json')},
                        'native run record output name changed')
                level = int(path.stem.rsplit('-', 1)[1])
                if path.suffix == '.dat':
                    require(path.read_bytes() == expected, 'retained binary differs from original save oracle')
                else:
                    table = json.loads(path.read_bytes())['records']
                    require(len(table) == 7 and table[0]['level'] == level and table[0]['score'] == 100 and
                            table[0]['name_length'] == 8 and table[0]['encoded_name'] == 'a:::::::',
                            'retained JSON metadata changed')
            if index == 0:
                first = current
        require(sha(exe.read_bytes()) == report['executable_sha256'], 'native executable changed')
        require(sha(fixture.read_bytes()) == report['fixture_sha256'], 'original fixture changed')
        report.update(passed=True, first_evidence_unchanged=True,
                      output_sha256={str(path.relative_to(evidence)): digest for path, digest in current.items()})
    except BaseException as error:
        initial_error = error
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        try:
            (evidence / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        except BaseException:
            if initial_error is None:
                raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not sys.flags.optimize, 'optimized Python unsupported')
    replay(args.exe, args.fixture, args.out)
    print('record_save_repeat=ok invocations=2 binary_cases=10 compared_bytes=920 first_evidence_unchanged=1')


if __name__ == '__main__':
    main()
