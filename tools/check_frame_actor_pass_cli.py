"""Reject malformed frame-actor-pass replays and a changed original executable."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

import check_frame_actor_pass_fixture as checker


def require(yes, message):
    if not yes:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    payload = checker.read_fixture()
    require(args.fixture.stat().st_size == len(payload) and args.fixture.read_bytes() == payload,
        'CLI input is not the frozen frame actor pass corpus')
    args.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=args.out))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    protected = {path: digest(path) for path in (args.exe, args.fixture, checker.ROOT / 'LEZAC.EXE')}
    env = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    results = []
    report = dict(status='failed', results=results)
    def run(label, arguments):
        result = subprocess.run([str(args.exe), *map(str, arguments)], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300, creationflags=flags)
        (out / (label + '.log')).write_bytes(result.stdout)
        return result
    try:
        good = run('positive', (args.fixture, checker.ROOT))
        require(good.returncode == 0 and b'frame_actor_pass_original=ok' in good.stdout and
            b'canonical_mz=1' in good.stdout, 'Frame actor pass CLI positive control failed')
        wrong_root = out / 'wrong-root'
        wrong_root.mkdir()
        mz = bytearray((checker.ROOT / 'LEZAC.EXE').read_bytes())
        mz[struct.unpack_from('<H', mz, 8)[0] * 16] ^= 1
        (wrong_root / 'LEZAC.EXE').write_bytes(mz)
        cases = [
            ('missing_argument', (args.fixture,), b'Expected fixture'),
            ('extra_argument', (args.fixture, checker.ROOT, 'extra'), b'Expected fixture'),
            ('missing_fixture', (out / 'missing.bin', checker.ROOT), b'frame_actor_pass=failed'),
            ('missing_mz', (args.fixture, out / 'missing-root'), b'frame_actor_pass=failed'),
            ('changed_mz', (args.fixture, wrong_root), b'Frame actor pass MZ fingerprint differs'),
        ]
        for name, raw, reason in (
            ('truncated', payload[:-1], b'Frame actor pass input size differs'),
            ('changed', payload[:1234] + bytes((payload[1234] ^ 1,)) + payload[1235:],
                b'Pass corpus fingerprint differs'),
            ('extra_tail', payload + b'\0', b'Frame actor pass input size differs')):
            path = out / (name + '.bin')
            path.write_bytes(raw)
            cases.append((name, (path, checker.ROOT), reason))
        for name, arguments, reason in cases:
            result = run(name, arguments)
            require(result.returncode != 0 and b'frame_actor_pass=failed' in result.stdout and reason in result.stdout,
                'Frame actor pass CLI counterexample escaped or crashed: ' + name)
            results.append(dict(case=name, rejected=True))
        require(all(digest(path) == value for path, value in protected.items()), 'CLI changed protected inputs')
        report.update(status='passed', negative_controls=len(cases), protected_inputs_preserved=True)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('frame_actor_pass_cli=ok negative_controls=8 canonical_mz_bound=1 protected_inputs_preserved=1')


if __name__ == '__main__':
    main()
