"""Compare actual-App consume/seeder states with the unmodified-original fixture."""
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

CASES = 896
INPUT_BYTES = 10
STATE_BYTES = 5983
RECORD_BYTES = INPUT_BYTES + STATE_BYTES
ORIGINAL_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
PACKED_SHA = '507e54eab121fe1763746fb11d7e815dcb787f7f482552308fd688ab9b22b4e1'
RAW_SHA = 'e0b7ac8a68fae110cbb112c764049335616387495747b0c07cd18ece468c9c3d'
OUTPUT_SHA = '7ed60f56e6050d1c02c7dd03360f17359306cff1141d5d046b26699743604250'
MARKER = (b'monster_object_seeder_app=ok cases=896 compared_bytes=5360768 debris=128 collapse=128 '
          b'sound_requests=672 first_only=1 production_app=1 seeded=1 natural_route=0 whole_game_claim=0')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_format(raw):
    require(raw[:16] == b'LZOS0001' + struct.pack('<II', CASES, RECORD_BYTES), 'invalid seeder fixture header')
    require(len(raw) == 16 + CASES * RECORD_BYTES, 'invalid seeder fixture extent')


def decode_fixture(packed):
    require(len(packed) < 128 * 1024, 'compressed seeder fixture exceeds limit')
    require(sha(packed) == PACKED_SHA, 'compressed seeder fixture hash mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(6 * 1024**2 + 1)
    require(len(raw) <= 6 * 1024**2, 'decompressed seeder fixture exceeds limit')
    require(sha(raw) == RAW_SHA, 'decompressed seeder fixture hash mismatch')
    validate_format(raw)
    return raw


def fixtures(root):
    require(sha((root / 'LEZAC.EXE').read_bytes()) == ORIGINAL_SHA, 'original executable hash mismatch')
    packed = (root / 'tests/fixtures/monster_object_seeder_original.bin.gz').read_bytes()
    raw = decode_fixture(packed)
    expected = b'LZOT0001' + struct.pack('<II', CASES, STATE_BYTES)
    expected += b''.join(raw[16 + index * RECORD_BYTES + INPUT_BYTES:16 + (index + 1) * RECORD_BYTES]
                         for index in range(CASES))
    require(sha(expected) == OUTPUT_SHA, 'seeder comparison stream hash mismatch')
    return packed, raw, expected


def difference(actual, expected):
    if actual == expected:
        return None
    offset = next((at for at, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]),
                  min(len(actual), len(expected)))
    return dict(output_offset=offset, case=(offset - 16) // STATE_BYTES if offset >= 16 else None,
                state_offset=(offset - 16) % STATE_BYTES if offset >= 16 else None,
                actual=actual[offset] if offset < len(actual) else None,
                expected=expected[offset] if offset < len(expected) else None,
                actual_bytes=len(actual), expected_bytes=len(expected))


def check(root, exe, out):
    root, exe, out = root.resolve(), exe.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    # Keep each complete raw stream in its own bounded sibling run directory.
    inputs = Path(tempfile.mkdtemp(prefix='monster-seeder-input-', dir=out.parent))
    outputs = Path(tempfile.mkdtemp(prefix='attempt-', dir=out))
    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), production_app=True,
        cases=CASES, state_bytes=STATE_BYTES, compared_bytes=CASES * STATE_BYTES, masks_applied=False,
        seeded=True, natural_route=False, whole_game_claim=False, sound_interrupt_executed=False,
        rendered_pixels_claim=False, audio='dummy', input_directory=str(inputs), output_directory=str(outputs))
    try:
        packed, raw, expected = fixtures(root)
        report.update(fixture_packed_sha256=sha(packed), fixture_raw_sha256=sha(raw), expected_sha256=sha(expected))
        (inputs / 'fixture.bin.gz').write_bytes(packed)
        (inputs / 'fixture.bin').write_bytes(raw)
        report['executable_sha256_before'] = sha(exe.read_bytes())
        actual_path = outputs / 'actual.bin'
        args = [str(exe), '--debug-monster-object-seeder-original', str(inputs / 'fixture.bin'), str(actual_path)]
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
            require(actual_path.stat().st_size < 6 * 1024**2, 'seeder output exceeds limit')
            actual = actual_path.read_bytes()
            report.update(actual_sha256=sha(actual), first_difference=difference(actual, expected))
        require(result.returncode == 0, 'seeder executable failed')
        require(MARKER in stdout.splitlines(), 'missing seeder execution marker')
        require(actual_path.exists() and report['first_difference'] is None, 'seeder state differs from original')
        report['executable_sha256_after'] = sha(exe.read_bytes())
        require(report['executable_sha256_before'] == report['executable_sha256_after'], 'seeder executable changed')
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
        print('monster_object_seeder_fixture=ok cases=896 state_bytes=5983 first_seeder_calls=256')
        return 0
    if args.out is None:
        parser.error('--out is required with --exe')
    report, path = check(args.root, args.exe, args.out)
    if not report['passed']:
        print('monster_object_seeder_original=failed report=' + str(path))
        print(report['error'])
        return 1
    print('monster_object_seeder_original=ok cases=896 compared_bytes=5360768 production_app=1 '
          'masks=0 first_only=1 seeded=1 natural_route=0 whole_game_claim=0 report=' + str(path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
