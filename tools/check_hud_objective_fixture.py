"""Authenticate the frozen original word-wrap and completion-latch endpoints."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/hud_objective'
MANIFEST_SHA = '4c2ccaa5f88cff8905da49e25205c0800bf4e7f51c478e21ba17208bd060a7f7'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_fixture(root=FIXTURE, source_root=ROOT):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen objective manifest differs')
    record = json.loads(raw)
    for name, path in [('producer_sha256', 'tools/hud_objective_oracle.py'),
                       ('shared_producer_sha256', 'tools/frame_hud_probe/oracle.py'),
                       ('font_checker_sha256', 'tools/check_frame_hud_fixture.py')]:
        require(sha((source_root / path).read_bytes()) == record[name], 'Frozen objective producer differs: ' + path)
    # The shared original-font input and every source bound by its frozen checker
    # remain authenticated, without requiring Unicorn or raw RAM in CI.
    from check_frame_hud_fixture import read_fixture as read_hud_fixture
    font = read_hud_fixture()[2][257:897]
    require(sha(font) == record['font_sha256'], 'Original objective font differs')
    compressed = (root / 'oracle.bin.gz').read_bytes()
    require(len(compressed) == record['compressed_bytes'] and sha(compressed) == record['compressed_sha256'],
            'Frozen objective endpoints differ')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        projection = stream.read(28454)
    require(len(projection) == record['projection_bytes'] == 28453 and sha(projection) == record['projection_sha256'] and
            projection[:12] == b'LZHUDOR1\x11\0\0\0', 'Original objective projection differs')
    print('hud_objective_fixture=ok cases=17 raw_ram_files_verified=0 full_frame_claim=0')
    return projection


def export(path):
    projection = read_fixture()
    if not path.exists() or path.read_bytes() != projection:
        path.write_bytes(projection)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle', type=Path)
    args = parser.parse_args()
    if args.oracle:
        export(args.oracle)
    else:
        read_fixture()
