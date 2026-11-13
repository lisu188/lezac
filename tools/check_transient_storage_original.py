"""Compare actual transient storage to complete, pinned original CPU tables."""
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

STATE_BYTES = 1575
OPERATIONS = 256
ORIGINAL_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
FIXTURES = {
    'requests': ('4ba0dc26af45ededa21709ac4d350eb87b5faf72c4bdce56b5880df80b019d9d',
                 'ba01b9d8c3cecdd3bba753f3d3aa31400329b268951a40618e40392e54e34825'),
    'expected': ('f0bcc9827d3cb5f1996284a65145c3f03ee8a710230a34e50cd33187ef24df7f',
                 'e20420f8878ec3888f3035debc24b036aee8e0bbff76c9dd8fc1b002aa4d7071'),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def decode_fixture(packed, compressed_sha, raw_sha, limit=512 * 1024):
    require(len(packed) < 64 * 1024, 'compressed transient fixture exceeds limit')
    require(sha(packed) == compressed_sha, 'compressed transient fixture hash mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'decompressed transient fixture exceeds limit')
    require(sha(raw) == raw_sha, 'decompressed transient fixture hash mismatch')
    return raw


def difference(actual, expected):
    if actual == expected:
        return None
    offset = next((index for index, (left, right) in enumerate(zip(actual, expected)) if left != right),
                  min(len(actual), len(expected)))
    at = (offset - 12) % STATE_BYTES if offset >= 12 else None
    return dict(output_offset=offset, operation=(offset - 12) // STATE_BYTES + 1 if at is not None else None,
        state_offset=at, area=('header' if at is None else 'actors' if at < 1178 else
                              'visuals' if at < 1442 else 'links' if at < 1570 else 'scalars'),
        actual=actual[offset] if offset < len(actual) else None,
        expected=expected[offset] if offset < len(expected) else None,
        actual_bytes=len(actual), expected_bytes=len(expected))


def run_capture(exe, request, actual, production_app, row):
    args = [str(exe)] + (['--debug-transient-storage-original'] if production_app else [])
    args += [str(request), str(actual)]
    row['args'] = args
    try:
        result = subprocess.run(args, capture_output=True, timeout=30,
            env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1'))
        stdout, stderr = result.stdout, result.stderr
        row['returncode'] = result.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b'', error.stderr or b''
        row['timeout'] = True
        raise
    finally:
        if 'stdout' in locals():
            actual.with_suffix('.stdout').write_bytes(stdout)
            actual.with_suffix('.stderr').write_bytes(stderr)
            row.update(stdout_sha256=sha(stdout), stderr_sha256=sha(stderr))
    require(result.returncode == 0, 'transient executable failed')
    marker = (b'transient_storage_original_app=ok operations=256 seeds=16 updates=192 constructors=48 '
              b'legacy_adoptions=0 legacy_retirements=0 seeded=1 natural_route=0 whole_game_claim=0') if production_app \
        else b'transient_storage_probe=ok operations=256'
    require(marker in stdout.splitlines(), 'missing transient execution marker')


def check(root, exe, out, production_app):
    root, exe, out = root.resolve(), exe.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='transient-app-' if production_app else 'transient-helper-', dir=out))
    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(),
        production_app=production_app, compiled_helper=not production_app, operations=OPERATIONS,
        compared_bytes=OPERATIONS * STATE_BYTES, seeded=True, natural_route=False, whole_game_claim=False,
        masks_applied=False, audio='dummy', directory=str(directory), fixtures={})
    try:
        require(sha((root / 'LEZAC.EXE').read_bytes()) == ORIGINAL_SHA, 'original executable hash mismatch')
        report['executable_sha256_before'] = sha(exe.read_bytes())
        for label, (packed_sha, raw_sha) in FIXTURES.items():
            packed = (root / 'tests/fixtures/transient_storage' / (label + '.bin.gz')).read_bytes()
            (directory / (label + '.bin.gz')).write_bytes(packed)
            raw = decode_fixture(packed, packed_sha, raw_sha)
            (directory / (label + '.bin')).write_bytes(raw)
            report['fixtures'][label] = dict(compressed_sha256=sha(packed), raw_sha256=sha(raw), bytes=len(raw))
        request = (directory / 'requests.bin').read_bytes()
        expected = (directory / 'expected.bin').read_bytes()
        require(request[:12] == b'LZTW0001' + struct.pack('<I', OPERATIONS), 'invalid transient request header')
        require(expected[:12] == b'LZTO0001' + struct.pack('<I', OPERATIONS), 'invalid transient output header')
        require(len(expected) == 12 + OPERATIONS * STATE_BYTES, 'invalid transient output extent')
        run_capture(exe, directory / 'requests.bin', directory / 'actual.bin', production_app, report)
        actual = (directory / 'actual.bin').read_bytes()
        report.update(actual_sha256=sha(actual), first_difference=difference(actual, expected))
        require(report['first_difference'] is None, 'transient physical table differs from original')
        report['executable_sha256_after'] = sha(exe.read_bytes())
        require(report['executable_sha256_before'] == report['executable_sha256_after'], 'executable changed during comparison')
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    report_path = directory / 'comparison.json'
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report, report_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--production-app', action='store_true')
    args = parser.parse_args()
    report, path = check(args.root, args.exe, args.out, args.production_app)
    if not report['passed']:
        print('transient_storage_original=failed report=' + str(path))
        print(report['error'])
        return 1
    print('transient_storage_original=ok operations=256 compared_bytes=403200 production_app=%d '
          'masks=0 seeded=1 natural_route=0 whole_game_claim=0 report=%s' % (args.production_app, path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
