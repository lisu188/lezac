"""Compare continuous compiled JollyCloud map production with original CPU output."""
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

ORIGINAL_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
PACKED_SHA = '29fd9d904aae7907290c2bb02743e05409b028f470336c03892d745533ac1678'
RAW_SHA = '7d8f208f3f413f07842db75a0c0dfebaec325602c03bff6d3f66ad762e8be2a3'
MAX_RAW = 16 * 1024**2
WINDOWS = {0x6e7e: 12, 0x81bf: 14, 0x3f27: 127, 0x370e: 184}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def decode_fixture(packed, packed_sha=PACKED_SHA, raw_sha=RAW_SHA, limit=MAX_RAW):
    require(len(packed) < 1024**2, 'compressed fixture exceeds limit')
    require(sha(packed) == packed_sha, 'compressed fixture hash mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'decompressed fixture exceeds limit')
        require(stream.read(1) == b'', 'trailing decompressed fixture bytes')
    require(sha(raw) == raw_sha, 'decompressed fixture hash mismatch')
    return json.loads(raw)


def streams(fixture):
    require(fixture['schema'] == 'lezac-jolly-cloud-original-v1', 'invalid fixture schema')
    require(fixture['executable_sha256'] == ORIGINAL_SHA, 'invalid fixture executable identity')
    require(fixture['patched_instructions'] is False and fixture['stubbed_original_calls'] is False
            and fixture['natural'] is False, 'invalid fixture provenance')
    require(len(fixture['cases']) == 8, 'invalid fixture cases')
    request = bytearray(b'LZJC0001' + struct.pack('<H', 8))
    expected = bytearray(b'LZJO0001' + struct.pack('<H', 8))
    boundaries = []
    for index, case in enumerate(fixture['cases']):
        width, initial = case['width'], case['initial']
        cells = width * 4
        require(1 <= width <= 256 and 0 <= initial['debris_count'] <= 1401, 'invalid fixture dimensions')
        require(case['index'] == index and 0 <= case['remaining'] <= 255, 'invalid fixture case identity')
        require(all(initial[key] == case[key] for key in ('remaining', 'marker', 'seed', 'debris_count')),
                'inconsistent initial scalars')
        require(len(case['samples']) == case['remaining'] + 2, 'invalid continuous sample count')
        tiles, words = bytes.fromhex(initial['tiles']), bytes.fromhex(initial['words'])
        records = bytes.fromhex(initial['debris_records'])
        require(len(tiles) == cells and len(words) == cells * 2 and len(records) == 1401 * 11,
                'invalid initial state extent')
        require(initial['tiles'] == case['initial_tiles'] and initial['words'] == case['initial_words'],
                'inconsistent initial map')
        request += struct.pack('<HBBHHI', width, initial['remaining'], case['objective'],
                               initial['marker'], initial['debris_count'], initial['seed'])
        request += tiles + words + records[:initial['debris_count'] * 11]
        expected += struct.pack('<H', len(case['samples']))
        for tick, state in enumerate(case['samples']):
            start = len(expected)
            tiles, words = bytes.fromhex(state['tiles']), bytes.fromhex(state['words'])
            records = bytes.fromhex(state['debris_records'])
            require(len(tiles) == cells and len(words) == cells * 2 and len(records) == 1401 * 11
                    and 0 <= state['debris_count'] <= 1401, 'invalid sample extent')
            expected += struct.pack('<BIHH', state['remaining'], state['seed'], state['marker'], state['debris_count'])
            expected += tiles + words + records[:state['debris_count'] * 11]
            boundaries.append(dict(case=case['index'], tick=tick, start=start, end=len(expected),
                                   tiles_start=start + 9, words_start=start + 9 + cells,
                                   records_start=start + 9 + 3 * cells))
    require(len(boundaries) == 293, 'invalid fixture trajectory coverage')
    require(len(request) < 1024**2 and len(expected) < MAX_RAW, 'protocol extent exceeds limit')
    return bytes(request), bytes(expected), boundaries


def difference(actual, expected, boundaries):
    if actual == expected:
        return None
    offset = next((i for i, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]), min(len(actual), len(expected)))
    boundary = next((row for row in boundaries if row['start'] <= offset < row['end']), None)
    area = 'header'
    if boundary:
        area = ('scalars' if offset < boundary['tiles_start'] else 'tiles' if offset < boundary['words_start']
                else 'words' if offset < boundary['records_start'] else 'active_debris_records')
    return dict(offset=offset, area=area, case=None if boundary is None else boundary['case'],
                tick=None if boundary is None else boundary['tick'],
                actual=actual[offset] if offset < len(actual) else None,
                expected=expected[offset] if offset < len(expected) else None,
                actual_bytes=len(actual), expected_bytes=len(expected))


def check(root, exe, out, app=False):
    root, exe, out = root.resolve(), exe.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='jolly-cloud-', dir=out))
    buffers = {}
    report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(),
                  production_helpers=True, production_app=app, full_frame_loop=False,
                  natural_pickup_claim=False, inactive_debris_storage_claim=False,
                  whole_game_claim=False, audio='dummy')
    try:
        original = (root / 'LEZAC.EXE').read_bytes()
        report['original_sha256'] = sha(original)
        require(report['original_sha256'] == ORIGINAL_SHA, 'original executable hash mismatch')
        packed = (root / 'tests/fixtures/jolly_cloud_original.json.gz').read_bytes()
        buffers['fixture-packed'] = packed
        fixture = decode_fixture(packed)
        report.update(generator_sha256=fixture['generator_sha256'], executor_sha256=fixture['executor_sha256'])
        require({int(address, 16) for address in fixture['instruction_windows']} == set(WINDOWS),
                'incomplete original instruction identity')
        for address, expected_hash in fixture['instruction_windows'].items():
            ip = int(address, 16)
            length = WINDOWS[ip]
            require(sha(original[0x770 + ip:0x770 + ip + length]) == expected_hash, 'original instruction mismatch')
        request, expected, boundaries = streams(fixture)
        buffers.update(request=request, expected=expected)
        report['probe_sha256_before'] = sha(exe.read_bytes())
        command = [str(exe)] + (['--debug-jolly-cloud-probe'] if app else [])
        report['command'] = command
        try:
            result = subprocess.run(command, input=request, capture_output=True, timeout=30,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'))
            buffers.update(actual=result.stdout, stderr=result.stderr)
            report['returncode'] = result.returncode
        except subprocess.TimeoutExpired as error:
            buffers.update(actual=error.stdout or b'', stderr=error.stderr or b'')
            report['timeout'] = True
            raise
        report['first_difference'] = difference(result.stdout, expected, boundaries)
        report['probe_sha256_after'] = sha(exe.read_bytes())
        require(report['probe_sha256_before'] == report['probe_sha256_after'], 'probe changed during comparison')
        require(result.returncode == 0, 'compiled rain probe failed')
        require(report['first_difference'] is None, 'compiled rain output differs')
        report.update(passed=True, cases=8, samples=293, compared_bytes=len(expected),
                      output_sha256=sha(result.stdout), fixture_sha256=sha(packed))
    except Exception:
        report['error'] = traceback.format_exc()
        report['retained_failure'] = []
        for name, data in buffers.items():
            path = directory / (name + '.bin.gz')
            compressed = gzip.compress(data, mtime=0)
            path.write_bytes(compressed)
            report['retained_failure'].append(dict(path=str(path), bytes=len(data), sha256=sha(data)))
    path = directory / 'comparison.json'
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report, path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--app', action='store_true')
    args = parser.parse_args()
    report, path = check(args.root, args.exe, args.out or args.root / 'build/jolly-cloud-checks', args.app)
    if not report['passed']:
        print('jolly_cloud_original=failed report=' + str(path))
        print(report['error'])
        return 1
    print('jolly_cloud_original=ok cases=8 samples=293 compared_bytes=%d production_app=%d natural=0 whole_game_claim=0 report=%s'
          % (report['compared_bytes'], args.app, path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
