"""Require the unchanged production lifecycle diagnostic to reject the old lookup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

FAILURE = b'active sprite bank physical descriptor mismatch'


def check(exe, out):
    out.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=out))
    command = [str(exe.resolve()), '--debug-production-actor-lifecycle']
    report = dict(passed=False, command=command, actual_app=True, unchanged_diagnostic=True,
        old_normal_bank=True, audio='dummy', natural_route=False, whole_game_claim=False)
    stdout = stderr = b''
    try:
        try:
            result = subprocess.run(command, capture_output=True, timeout=30,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'))
            stdout, stderr = result.stdout, result.stderr
            report['returncode'] = result.returncode
            if result.returncode != 1 or FAILURE not in stderr:
                raise RuntimeError('old bank mutant accepted or failed for an unrelated reason')
            report['passed'] = True
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b'', error.stderr or b''
            report['timeout'] = True
            raise
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        (attempt / 'app.stdout').write_bytes(stdout)
        (attempt / 'app.stderr').write_bytes(stderr)
        report.update(stdout_sha256=hashlib.sha256(stdout).hexdigest(), stderr_sha256=hashlib.sha256(stderr).hexdigest())
        (attempt / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('actor_descriptor_bank_mutant=rejected old_normal_bank=1 actual_app=1 unchanged_diagnostic=1 natural_route=0 whole_game_claim=0')
    return attempt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    check(args.exe, args.out)


if __name__ == '__main__':
    main()
