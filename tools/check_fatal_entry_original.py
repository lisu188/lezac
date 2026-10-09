"""Compare complete production fatal-entry states with repeated native captures."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import traceback

STATE_BYTES = 1864
OPERATIONS = 3456
ORIGINAL_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
FIXTURES = {
    'requests': ('87208a5c381d47e4645d7f868b2ad85b49543d036ae50a80a0625bd969f6ef0a',
                 '6071e5d10b1c4345e65f3d2af77cd4777d75c2403cfa1dce22b5c0b9a741944a'),
    'expected': ('202e4b6f0d511ccf7bfaac26ab82d245be23a5530421f19f8781874b97bcc50c',
                 '93ebfe626427e2ec300dc3e7c98b0d4adeda7ad442dadf3297bcd8691a6a2371'),
}
MARKER = (b'fatal_entry_original_app=ok operations=3456 seeds=1152 updates=2304 '
          b'state_bytes=1864 legacy_adoptions=0 legacy_retirements=0 sound_requests=0 '
          b'seeded=1 natural_route=0 whole_game_claim=0')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode_fixture(packed, compressed_sha, raw_sha):
    require(len(packed) < 768 * 1024, 'compressed fatal-entry fixture exceeds limit')
    require(sha(packed) == compressed_sha, 'compressed fatal-entry fixture hash mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(8 * 1024**2 + 1)
    require(len(raw) <= 8 * 1024**2, 'decompressed fatal-entry fixture exceeds limit')
    require(sha(raw) == raw_sha, 'decompressed fatal-entry fixture hash mismatch')
    return raw


def fixtures(root):
    require(sha((root / 'LEZAC.EXE').read_bytes()) == ORIGINAL_SHA, 'original executable hash mismatch')
    streams = {}
    for label, pins in FIXTURES.items():
        packed = (root / 'tests/fixtures/fatal_entry' / (label + '.bin.gz')).read_bytes()
        streams[label] = decode_fixture(packed, *pins)
    require(streams['requests'][:12] == b'LZFE0001' + struct.pack('<I', OPERATIONS), 'invalid fatal-entry request header')
    expected = streams['expected']
    require(expected[:12] == b'LZFO0001' + struct.pack('<I', OPERATIONS), 'invalid fatal-entry expected header')
    require(len(expected) == 12 + OPERATIONS * STATE_BYTES, 'invalid fatal-entry expected extent')
    return streams


def difference(actual, expected):
    if actual == expected:
        return None
    offset = next((at for at, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]), min(len(actual), len(expected)))
    return dict(output_offset=offset, operation=(offset - 12) // STATE_BYTES + 1 if offset >= 12 else None,
                state_offset=(offset - 12) % STATE_BYTES if offset >= 12 else None,
                actual=actual[offset] if offset < len(actual) else None,
                expected=expected[offset] if offset < len(expected) else None,
                actual_bytes=len(actual), expected_bytes=len(expected))


def check(root, exe, out):
    root, exe, out = root.resolve(), exe.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    # Keep the two uncompressed streams in separate bounded run roots.
    inputs = Path(tempfile.mkdtemp(prefix='fatal-entry-input-', dir=out))
    outputs = Path(tempfile.mkdtemp(prefix='fatal-entry-output-', dir=out))
    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), production_app=True,
                  operations=OPERATIONS, cases=1152, compared_bytes=OPERATIONS * STATE_BYTES,
                  state_bytes=STATE_BYTES, masks_applied=False, seeded=True, natural_route=False,
                  whole_game_claim=False, sound_interrupt_executed=False, rendered_pixels_claim=False,
                  audio='dummy', input_directory=str(inputs), output_directory=str(outputs))
    try:
        streams = fixtures(root)
        report['executable_sha256_before'] = sha(exe.read_bytes())
        for label in FIXTURES:
            packed = (root / 'tests/fixtures/fatal_entry' / (label + '.bin.gz')).read_bytes()
            (inputs / (label + '.bin.gz')).write_bytes(packed)
        (inputs / 'requests.bin').write_bytes(streams['requests'])
        actual_path = outputs / 'actual.bin'
        args = [str(exe), '--debug-fatal-entry-original', str(inputs / 'requests.bin'), str(actual_path)]
        report['args'] = args
        try:
            result = subprocess.run(args, capture_output=True, timeout=60,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1'))
            stdout, stderr = result.stdout, result.stderr
            report['returncode'] = result.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b'', error.stderr or b''
            report['timeout'] = True
            raise
        finally:
            if 'stdout' in locals():
                (outputs / 'actual.stdout').write_bytes(stdout)
                (outputs / 'actual.stderr').write_bytes(stderr)
                report.update(stdout_sha256=sha(stdout), stderr_sha256=sha(stderr))
        if actual_path.exists():
            require(actual_path.stat().st_size < 8 * 1024**2, 'fatal-entry output exceeds limit')
            actual = actual_path.read_bytes()
            report.update(actual_sha256=sha(actual), first_difference=difference(actual, streams['expected']))
        require(result.returncode == 0, 'fatal-entry executable failed')
        require(MARKER in stdout.splitlines(), 'missing fatal-entry execution marker')
        require(actual_path.exists() and report['first_difference'] is None, 'fatal-entry physical state differs from original')
        report['executable_sha256_after'] = sha(exe.read_bytes())
        require(report['executable_sha256_before'] == report['executable_sha256_after'], 'fatal-entry executable changed')
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    path = outputs / 'comparison.json'
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report, path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.exe is None:
        fixtures(args.root)
        print('fatal_entry_fixture=ok cases=1152 operations=3456 state_bytes=1864')
        return 0
    if args.out is None:
        parser.error('--out is required with --exe')
    report, path = check(args.root, args.exe, args.out)
    if not report['passed']:
        print('fatal_entry_original=failed report=' + str(path))
        print(report['error'])
        return 1
    print('fatal_entry_original=ok operations=3456 compared_bytes=6441984 production_app=1 '
          'masks=0 seeded=1 natural_route=0 whole_game_claim=0 report=' + str(path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
