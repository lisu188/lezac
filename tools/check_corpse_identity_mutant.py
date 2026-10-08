"""Require the compiled App mutant to fail specifically on an unused birth ID."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

FIXTURE_SHA256 = '765b724713778f7fa86e7df8fe7812de9e40b029cf85b46bc6e25ed9ecdd6e4e'
FAILURE = re.compile(r'shared-order ([a-z_]+) sample=([0-9]+): unused birth identity')


def checked_bytes(path, limit):
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('input exceeds size limit: ' + str(path))
    return raw


def check(exe, fixture, output):
    output.mkdir(parents=True, exist_ok=True)
    retained = Path(tempfile.mkdtemp(prefix='case-', dir=output))
    report = dict(passed=False, expected_mutant=True, audio='dummy',
                  recorded_utc=datetime.now(timezone.utc).isoformat())
    try:
        packed = checked_bytes(fixture, 2 * 1024**2)
        report['fixture_sha256'] = hashlib.sha256(packed).hexdigest()
        (retained / 'fixture.txt').write_bytes(packed)
        normalized = packed.replace(b'\r\n', b'\n')
        if hashlib.sha256(normalized).hexdigest() != FIXTURE_SHA256:
            raise ValueError('shared-order fixture identity mismatch')
        binary = checked_bytes(exe, 64 * 1024**2)
        report['binary_sha256'] = hashlib.sha256(binary).hexdigest()
        command = [str(exe.resolve()), '--debug-shared-actor-order-original', str(fixture.resolve())]
        report['command'] = command
        try:
            result = subprocess.run(command, cwd=fixture.resolve().parents[2], capture_output=True, timeout=60,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1'))
        except subprocess.TimeoutExpired as error:
            (retained / 'stdout.txt').write_bytes(error.stdout or b'')
            (retained / 'stderr.txt').write_bytes(error.stderr or b'')
            raise ValueError('mutant execution timed out') from error
        (retained / 'stdout.txt').write_bytes(result.stdout)
        (retained / 'stderr.txt').write_bytes(result.stderr)
        report['returncode'] = result.returncode
        if hashlib.sha256(checked_bytes(exe, 64 * 1024**2)).hexdigest() != report['binary_sha256']:
            raise ValueError('mutant binary changed during execution')
        text = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        match = FAILURE.search(text)
        if result.returncode == 0 or match is None or 'shared_actor_order_original=ok' in text:
            raise ValueError('expected the specific unused birth identity failure')
        report.update(passed=True, failed_case=match.group(1), failed_sample=int(match.group(2)))
        return report
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        (retained / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    check(args.exe, args.fixture, args.out)
    print('corpse_identity_mutant=ok rejected=1 production_app=1 original_replay=1 whole_game_claim=0', flush=True)


if __name__ == '__main__':
    main()
