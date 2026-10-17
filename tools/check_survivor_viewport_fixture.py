"""Authenticate original elimination, survivor viewport and backdrop endpoints."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

from render_view_gate_origin import authenticate, MANIFEST_SHA as ORIGIN_SHA, RECIPE_SHA

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/survivor_viewport'
MANIFEST_SHA = '0e973a8164c0563f5cc7b34ed5782849152593918d327edcdbe79bd28d38f3d9'
sha = lambda data: hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_fixture(root=FIXTURE, source_root=ROOT):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen survivor manifest differs')
    record = json.loads(raw)
    require(record['schema'] == 'lezac-original-survivor-viewport-v1', 'Original survivor schema differs')
    for name, digest in record['sources'].items():
        require(sha((source_root / name).read_bytes()) == digest, 'Original survivor producer differs: ' + name)
    origin = authenticate(source_root)
    sample = next(item for item in origin['samples'] if item['name'] == record['source_sample'])
    require(record['source_capture_manifest_sha256'] == ORIGIN_SHA and record['source_recipe_sha256'] == RECIPE_SHA and
            record['source_ram_sha256'] == sample['ram_sha256'] and record['code_segment'] == origin['code_segment'] and
            record['data_segment'] == origin['data_segment'], 'Original survivor RAM origin differs')
    compressed = (root / 'oracle.bin.gz').read_bytes()
    require(len(compressed) == record['compressed_bytes'] and sha(compressed) == record['compressed_sha256'],
            'Frozen survivor endpoints differ')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        projection = stream.read(5665281)
    require(len(projection) == record['projection_bytes'] == 5665280 and sha(projection) == record['projection_sha256'] and
            projection[:20] == b'LZSURV01' + struct.pack('<IIHH', 8, 10, 60, 33), 'Original survivor projection differs')
    print('survivor_viewport_fixture=ok profiles=8 stages=80 raw_ram_files_verified=0 whole_game_claim=0')
    return projection


def export(path=None):
    projection = read_fixture()
    if path and (not path.exists() or path.read_bytes() != projection):
        path.write_bytes(projection)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle', type=Path)
    args = parser.parse_args()
    export(args.oracle)
