"""Require the compiled old-layout App to fail at the missing corpse prologue."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('SDL_AUDIODRIVER') != 'dummy':
        raise RuntimeError('dummy audio is required')
    args.out.mkdir(parents=True, exist_ok=True)
    for index in range(1, 101):
        attempt = args.out / f'attempt-{index:03d}'
        try:
            attempt.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise RuntimeError('retained attempt cap reached')
    command = [str(args.exe.resolve()), '--debug-corpse-animation-original', str(args.fixture.resolve())]
    report = dict(passed=False, command=command, expected_failure='monster animation production boundary not reached',
                  actual_app=True, original_layout_mutant=True, natural_route=False, whole_game_claim=False)
    try:
        result = subprocess.run(command, capture_output=True, timeout=30,
            env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'))
        (attempt / 'stdout.txt').write_bytes(result.stdout)
        (attempt / 'stderr.txt').write_bytes(result.stderr)
        report.update(returncode=result.returncode,
            stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
            stderr_sha256=hashlib.sha256(result.stderr).hexdigest())
        if result.returncode != 1 or report['expected_failure'].encode() not in result.stderr:
            raise RuntimeError('mutant failed for an unexpected reason or accepted the old layout')
        report['passed'] = True
    except BaseException as error:
        report['error'] = repr(error)
        if isinstance(error, subprocess.TimeoutExpired):
            (attempt / 'stdout.txt').write_bytes(error.stdout or b'')
            (attempt / 'stderr.txt').write_bytes(error.stderr or b'')
        raise
    finally:
        (attempt / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('corpse_animation_skip_mutant=rejected actual_app=1 expected_boundary_failure=1 seeded=1 natural_route=0 whole_game_claim=0')


if __name__ == '__main__':
    main()
