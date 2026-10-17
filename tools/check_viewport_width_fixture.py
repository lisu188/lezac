"""Authenticate original viewport controls and all legal-width render endpoints."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

from render_view_gate_origin import authenticate, MANIFEST_SHA as ORIGIN_SHA, RECIPE_SHA

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/viewport_width'
MANIFEST_SHA = 'f27c9a82089f0bf6eae475d3ce738f0c97b1576626d596448908ba5a822517f2'
sha = lambda data: hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_fixture(root=FIXTURE, source_root=ROOT):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen width manifest differs')
    record = json.loads(raw)
    require(record['schema'] == 'lezac-original-viewport-width-v1', 'Original width schema differs')
    for name, digest in record['sources'].items():
        require(sha((source_root / name).read_bytes()) == digest, 'Original width producer differs: ' + name)
    origin = authenticate(source_root)
    sample = next(item for item in origin['samples'] if item['name'] == record['source_sample'])
    require(record['source_capture_manifest_sha256'] == ORIGIN_SHA and record['source_recipe_sha256'] == RECIPE_SHA and
            record['source_ram_sha256'] == sample['ram_sha256'] and record['code_segment'] == origin['code_segment'] and
            record['data_segment'] == origin['data_segment'], 'Original width RAM origin differs')
    compressed = (root / 'oracle.bin.gz').read_bytes()
    require(len(compressed) == record['compressed_bytes'] and sha(compressed) == record['compressed_sha256'],
            'Frozen width endpoints differ')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        projection = stream.read(6721439)
    require(len(projection) == record['projection_bytes'] == 6721438 and sha(projection) == record['projection_sha256'] and
            projection[:20] == b'LZWIDTH1' + struct.pack('<IIHH', 44, 60, 60, 33), 'Original width projection differs')
    print('viewport_width_fixture=ok controls=44 views=60 widths=20 raw_ram_files_verified=0 whole_game_claim=0')
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
