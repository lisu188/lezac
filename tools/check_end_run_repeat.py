"""Regrade both retained record commits across repeated native end-run checks."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

MARKER = b'original_end_run=ok flows=8 compared_saved_bytes=1472 signed_cases=49'
WARNING = 'warning: could not save records: cannot create '


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def expected_table(fixtures, flow, player):
    if flow % 2:
        name = 'end_run_after-player1-file.dat' if player == 1 else 'end_run_saved-original.dat'
    else:
        name = 'record_entry_after-player1-file.dat' if player == 1 else 'record_entry_saved-original.dat'
    return (fixtures / name).read_bytes()


def replay(exe, fixtures, out):
    out.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    native_out = evidence / 'native'
    report = dict(passed=False, native_runs=[], flows=16, compared_saved_bytes=2944,
        executable_sha256=sha(exe.read_bytes()), first_evidence_unchanged=False,
        full_app_executed=False, fresh_original_execution=False, rank8_memory_claim=False,
        whole_game_complete=False)
    first = {}
    initial_error = None
    try:
        for index in range(2):
            command = [str(exe.resolve()), str(fixtures.resolve()), str(native_out.resolve())]
            result = subprocess.run(command, env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'),
                                    capture_output=True, timeout=60)
            report['native_runs'].append(dict(command=command, exit_code=result.returncode))
            for stream in ('stdout', 'stderr'):
                (evidence / (str(index) + '.' + stream)).write_bytes(getattr(result, stream))
            require(result.returncode == 0 and MARKER in result.stdout,
                    'native end-run rerun failed: ' + result.stderr.decode(errors='replace'))
            warnings = result.stderr.decode(errors='replace').splitlines()
            require(len(warnings) == 1 and warnings[0].startswith(WARNING),
                    'unexpected native diagnostic output')
            failed_path = Path(warnings[0][len(WARNING):])
            require(failed_path.name == 'records.dat' and failed_path.parent.name == 'missing' and
                    failed_path.resolve().is_relative_to(native_out.resolve()),
                    'expected failed-save diagnostic points outside its owned run')
            final = list(native_out.rglob('records.dat'))
            require(Counter(int(path.parent.name) for path in final) ==
                    Counter({flow: index + 1 for flow in range(8)}),
                    'native rerun did not retain independent final tables')
            for path in final:
                require(path.read_bytes() == expected_table(fixtures, int(path.parent.name), 2),
                        'retained final table differs from original')
            current = {path: sha(path.read_bytes()) for path in native_out.rglob('*') if path.is_file()}
            require(all(path in current and current[path] == digest for path, digest in first.items()),
                    'first-run record evidence changed')
            if index == 0:
                first = current
        snapshots = list(native_out.rglob('after-player-*.dat'))
        require(Counter((int(path.parent.name), int(path.stem.rsplit('-', 1)[1])) for path in snapshots) ==
                Counter({(flow, player): 2 for flow in range(8) for player in (1, 2)}),
                'native run did not retain both original-backed commits')
        total = 0
        for path in snapshots:
            actual = path.read_bytes()
            require(len(actual) == 92 and actual == expected_table(fixtures, int(path.parent.name),
                    int(path.stem.rsplit('-', 1)[1])), 'retained intermediate table differs from original')
            total += len(actual)
        require(total == 2944, 'retained commit comparison size changed')
        negative = (fixtures / 'record_entry_negative-cutoff-fixture.dat').read_bytes()
        retry_expected = b'\x07' + b'\x00\x00\x00\x00\x08retry:::' + negative[1:79]
        retries = list(native_out.rglob('retry-zero.dat'))
        require(len(retries) == 2 and all(path.read_bytes() == retry_expected for path in retries),
                'zero-score retry evidence changed')
        require(sha(exe.read_bytes()) == report['executable_sha256'], 'native executable changed')
        report.update(passed=True, first_evidence_unchanged=True,
            retained_commit_files=len(snapshots), retry_zero_files=len(retries),
            retained_output_sha256={str(path.relative_to(evidence)): digest for path, digest in current.items()})
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
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not sys.flags.optimize, 'optimized Python unsupported')
    replay(args.exe, args.fixtures, args.out)
    print('original_end_run_repeat=ok invocations=2 flows=16 compared_saved_bytes=2944 first_evidence_unchanged=1')


if __name__ == '__main__':
    main()
