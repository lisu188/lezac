"""Require the actual App regression to reject three equal-final-seed controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

CONTROLS = {
    'sound_after_particles': 'corpse reward sound draw ordering changed',
    'swap_axes': 'corpse reward particle draw ordering changed',
    'reverse_particles': 'corpse reward particle draw ordering changed',
}


def check(exe, out):
    out.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=out))
    report = dict(passed=False, actual_app=True, unchanged_diagnostic=True, controls=[], audio='dummy',
                  natural_route=False, whole_game_claim=False)
    try:
        for mode, failure in CONTROLS.items():
            command = [str(exe.resolve()), '--debug-original-corpse-reward-animation-mode']
            row = dict(mode=mode, command=command, expected_failure=failure)
            report['controls'].append(row)
            stdout = stderr = b''
            try:
                result = subprocess.run(command, capture_output=True, timeout=30,
                    env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                             LEZAC_REWARD_RNG_MUTANT=mode))
                stdout, stderr = result.stdout, result.stderr
                row['returncode'] = result.returncode
                if result.returncode != 1 or failure.encode() not in stderr:
                    raise RuntimeError('RNG mutant accepted or failed for an unrelated reason: ' + mode)
                row['rejected_after_final_seed_check'] = True
            except subprocess.TimeoutExpired as error:
                stdout, stderr = error.stdout or b'', error.stderr or b''
                row['timeout'] = True
                raise
            finally:
                (attempt / (mode + '.stdout')).write_bytes(stdout)
                (attempt / (mode + '.stderr')).write_bytes(stderr)
                row.update(stdout_sha256=hashlib.sha256(stdout).hexdigest(), stderr_sha256=hashlib.sha256(stderr).hexdigest())
        report['passed'] = True
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        (attempt / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('corpse_reward_rng_mutants=rejected controls=3 actual_app=1 equal_final_seed=1 natural_route=0 whole_game_claim=0')
    return attempt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    check(args.exe, args.out)


if __name__ == '__main__':
    main()
