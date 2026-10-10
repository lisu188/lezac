"""Check compiled physical storage against pinned original-machine-code output."""
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
MAX_RAW = 16 * 1024 * 1024
ORIGINAL_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
CASES = (
    ('constructor-retirement-v1', 5340,
     '744bc70c84e6497a77d9c34d0e28dc8e965f9a42fd35cd774633d2c967de605c',
     'f4a0e2564f8780601fe860e5e6899b5af0f633d7e5b4e492110936e2d27d8689',
     '6f9b6d9e813cd4544a014e2b7bd99c6aeb99c65a90b43930680cca1dc2342d62',
     '5a743e6208c4dfc3897ecff5a6ae0237b9b184007272c5cd38143ad93c0f0175'),
    ('reset-reuse-v1', 512,
     'a8f6346771820b475b865306b95514599d44210ee5076438e4f8a6026f93ef19',
     'de70122c2b508e66e0afe4f95bb2354d7f6cffd8ea679e367d3b64e836c431c0',
     'b59f08078cf852c8b4b453b2f9b9cc9a713aaa9b0f75a661af893f90b41a673b',
     'a97be43a2aa2cf697c95746acfbc1d15480ab13f0669ed5980a2feee41e42fb6'),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def decode_fixture(packed, packed_sha, raw_sha, limit=MAX_RAW):
    require(len(packed) < 512 * 1024, 'compressed fixture exceeds limit')
    require(sha(packed) == packed_sha, 'compressed fixture hash mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'decompressed fixture exceeds limit')
        require(stream.read(1) == b'', 'trailing decompressed fixture bytes')
    require(sha(raw) == raw_sha, 'decompressed fixture hash mismatch')
    return raw


def difference(actual, expected):
    if actual == expected:
        return None
    offset = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b),
                  min(len(actual), len(expected)))
    at = (offset - 12) % STATE_BYTES if offset >= 12 else None
    return dict(output_offset=offset, operation=(offset - 12) // STATE_BYTES + 1 if at is not None else None,
                state_offset=at, area=('header' if at is None else 'actors' if at < 1178 else
                                      'visuals' if at < 1442 else 'links' if at < 1570 else 'scalars'),
                actual=actual[offset] if offset < len(actual) else None,
                expected=expected[offset] if offset < len(expected) else None,
                actual_bytes=len(actual), expected_bytes=len(expected))


def read_pair(root, case, buffers, row):
    name, count, request_sha, request_raw_sha, expected_sha, expected_raw_sha = case
    decoded = []
    row['fixtures'] = []
    for label, packed_sha, raw_sha in (('requests', request_sha, request_raw_sha),
                                       ('expected', expected_sha, expected_raw_sha)):
        path = root / 'tests/fixtures/actor_storage' / (name + '-' + label + '.bin.gz')
        packed = path.read_bytes()
        buffers[name + '-' + label + '-packed'] = packed
        row['fixtures'].append(dict(path=str(path), compressed_sha256=sha(packed)))
        raw = decode_fixture(packed, packed_sha, raw_sha)
        buffers[name + '-' + label] = raw
        decoded.append(raw)
    request, expected = decoded
    require(request[:12] == b'LZAS0001' + struct.pack('<I', count), 'invalid request header/count')
    require(expected[:12] == b'LZAR0001' + struct.pack('<I', count), 'invalid output header/count')
    require(len(expected) == 12 + count * STATE_BYTES, 'invalid fixture output extent')
    return request, expected


def run_probe(exe, request, expected, buffers, row):
    try:
        result = subprocess.run([str(exe)], input=request, capture_output=True, timeout=30,
                                env=dict(os.environ, SDL_AUDIODRIVER='dummy'))
        actual, error = result.stdout, result.stderr
        row['returncode'] = result.returncode
    except subprocess.TimeoutExpired as failure:
        buffers[row['name'] + '-actual'] = failure.stdout or b''
        buffers[row['name'] + '-stderr'] = failure.stderr or b''
        row['timeout'] = True
        raise
    buffers[row['name'] + '-actual'] = actual
    buffers[row['name'] + '-stderr'] = error
    row.update(actual_sha256=sha(actual), stderr_sha256=sha(error),
               first_difference=difference(actual, expected))
    require(result.returncode == 0, 'compiled actor storage probe failed')
    require(row['first_difference'] is None, 'compiled actor storage output differs')


def save_failure(directory, buffers):
    retained = []
    for name, data in buffers.items():
        path = directory / (name + '.bin.gz')
        packed = gzip.compress(data, mtime=0)
        path.write_bytes(packed)
        retained.append(dict(path=str(path), raw_bytes=len(data), raw_sha256=sha(data),
                             compressed_bytes=len(packed), compressed_sha256=sha(packed)))
    return retained


def check(root, exe, out):
    root, exe, out = root.resolve(), exe.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='actor-storage-', dir=out))
    buffers = {}
    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(),
                  compiled_core=True, production_app=False, natural_campaign_claim=False,
                  whole_game_claim=False, audio='dummy', cases=[])
    try:
        original = (root / 'LEZAC.EXE').read_bytes()
        report['original_sha256'] = sha(original)
        require(report['original_sha256'] == ORIGINAL_SHA, 'original executable hash mismatch')
        report['probe_sha256_before'] = sha(exe.read_bytes())
        for case in CASES:
            buffers.clear()
            name, count, *_ = case
            row = dict(name=name, operations=count, compared_bytes=count * STATE_BYTES)
            report['cases'].append(row)
            request, expected = read_pair(root, case, buffers, row)
            run_probe(exe, request, expected, buffers, row)
        report['probe_sha256_after'] = sha(exe.read_bytes())
        require(report['probe_sha256_after'] == report['probe_sha256_before'], 'probe changed during comparison')
        report.update(passed=True, operations=sum(x['operations'] for x in report['cases']),
                      compared_bytes=sum(x['compared_bytes'] for x in report['cases']))
    except Exception:
        report['error'] = traceback.format_exc()
        report['retained_failure'] = save_failure(directory, buffers)
    report_path = directory / 'comparison.json'
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report, report_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report, path = check(args.root, args.exe, args.out or args.root / 'build/actor-storage-checks')
    if not report['passed']:
        print('actor_storage_core=failed report=' + str(path))
        print(report['error'])
        return 1
    print('actor_storage_core=ok operations=%d compared_bytes=%d compiled_core=1 production_app=0 whole_game_claim=0 report=%s'
          % (report['operations'], report['compared_bytes'], path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
