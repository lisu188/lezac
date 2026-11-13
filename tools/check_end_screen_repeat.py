"""Run the native complete-frame regression twice without replacing evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HEADER = b'P6\n320 200\n255\n'
MARKER = b'end_screen=ok original_frames=2 compared_pixels=128000 differing_pixels=0 masks=0'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replay(exe, fixtures, out):
    out.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    frames = evidence / 'frames'
    report = dict(passed=False, native_runs=[], original_frames=4, compared_pixels=256000,
                  executable_sha256=sha(exe.read_bytes()), masks=0,
                  full_app_executed=False, fresh_original_execution=False, whole_game_complete=False)
    first = {}
    initial_error = None
    try:
        for index in range(2):
            command = [str(exe.resolve()), str(fixtures.resolve()), str(frames.resolve())]
            result = subprocess.run(command, env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'),
                                    capture_output=True, timeout=60)
            report['native_runs'].append(dict(command=command, exit_code=result.returncode))
            for stream in ('stdout', 'stderr'):
                (evidence / (str(index) + '.' + stream)).write_bytes(getattr(result, stream))
            require(result.returncode == 0 and not result.stderr and MARKER in result.stdout,
                    'native complete-frame rerun failed: ' + result.stderr.decode(errors='replace'))
            current = {path: sha(path.read_bytes()) for path in frames.rglob('*.ppm')}
            require(len(current) == 2 * (index + 1), 'native run did not retain independent frames')
            for path, digest in first.items():
                require(path in current and current[path] == digest, 'first run frame changed')
            for path in current:
                frame = path.read_bytes()
                number = int(path.stem.rsplit('-', 1)[1])
                require(frame[:len(HEADER)] == HEADER and
                        frame[len(HEADER):] == (fixtures / ('end_screen_' + str(number) + '.rgb')).read_bytes(),
                        'retained complete frame differs from original oracle')
            if index == 0:
                first = current
        require(sha(exe.read_bytes()) == report['executable_sha256'], 'native executable changed')
        report.update(passed=True, first_evidence_unchanged=True,
                      frame_sha256={str(path.relative_to(evidence)): digest for path, digest in current.items()})
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
    print('end_screen_repeat=ok invocations=2 original_frames=4 compared_pixels=256000 first_evidence_unchanged=1')


if __name__ == '__main__':
    main()
