"""Compare a compiled byte-addressed C++ helper with complete original DS images."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

PACKED_SHA = 'da428fa05f715f509bbb71a3ed9af6af78cc7dfaff51cad94b9e03a68b41edb8'
RAW_SHA = '3ecf90d23cbe6fd3908659d39173d29308fe118345e1e0077e7df60c18aa2a41'
CASES, STRIDE, STATE = 176, 131076, 65536


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(packed):
    if len(packed) > 1024**2 or sha(packed) != PACKED_SHA:
        raise ValueError('damage lane packed fixture pin mismatch')
    raw = gzip.decompress(packed)
    if len(raw) != 23069392 or sha(raw) != RAW_SHA:
        raise ValueError('damage lane raw fixture pin mismatch')
    if raw[:16] != struct.pack('<8sII', b'LZLB0001', CASES, STRIDE):
        raise ValueError('damage lane fixture header mismatch')
    incoming = bytearray(struct.pack('<8sII', b'LZLI0001', CASES, STATE + 4))
    expected = bytearray(struct.pack('<8sII', b'LZLO0001', CASES, STATE))
    for index in range(CASES):
        start = 16 + index * STRIDE
        operation, weight, caller = struct.unpack_from('<BBH', raw, start)
        if operation > 3:
            raise ValueError('invalid damage lane operation')
        incoming.extend(raw[start:start + 4 + STATE])
        expected.extend(raw[start + 4 + STATE:start + STRIDE])
    return bytes(incoming), bytes(expected)


def compare(actual, expected):
    if actual == expected:
        return None
    for offset, (left, right) in enumerate(zip(actual, expected)):
        if left != right:
            return dict(output_offset=offset, case=(offset - 16) // STATE if offset >= 16 else None,
                        ds_offset=(offset - 16) % STATE if offset >= 16 else None,
                        actual=left, expected=right)
    return dict(actual_bytes=len(actual), expected_bytes=len(expected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    incoming, expected = decode((args.root / 'tests/fixtures/damage_lane_bytes_original.bin.gz').read_bytes())
    if not args.exe:
        print('damage_lane_bytes_fixture=ok cases=176 full_ds_bytes=11534336 seeded=0')
        return 0
    if not args.out:
        parser.error('--out is required with --exe')
    args.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='attempt-', dir=args.out))
    before = sha(args.exe.read_bytes())
    env = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
    report = dict(passed=False, cases=CASES, compared_bytes=CASES * STATE, masks_applied=False,
                  production_app_integrated=False, whole_game_claim=False, audio='dummy', executable_sha256_before=before,
                  output_directory=str(out))
    try:
        result = subprocess.run([str(args.exe.resolve()), '--stream'], input=incoming,
                                capture_output=True, timeout=60, env=env)
        (out / 'actual.bin.gz').write_bytes(gzip.compress(result.stdout, mtime=0))
        (out / 'actual.stderr').write_bytes(result.stderr)
        difference = compare(result.stdout, expected)
        after = sha(args.exe.read_bytes())
        report.update(returncode=result.returncode, first_difference=difference, actual_sha256=sha(result.stdout),
                      expected_sha256=sha(expected), executable_sha256_after=after,
                      passed=result.returncode == 0 and not result.stderr and difference is None and before == after)
    finally:
        (out / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['passed']:
        print('damage_lane_bytes_original=ok cases=176 compared_bytes=11534336 masks=0 production_app=0 seeded=0 whole_game_claim=0')
        return 0
    print(json.dumps(report))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
