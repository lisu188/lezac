"""Authenticate original render-call gates and retained VGA observations."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from render_view_gate_origin import authenticate, MANIFEST_SHA as ORIGIN_SHA, RECIPE_SHA

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/render_view_gate'
MANIFEST_SHA = '89f2c5ca2672e686fd37fa58dc6cf43bd0b4a10509cd04b501b503b72cd9da4f'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_fixture(root=FIXTURE, source_root=ROOT):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen view manifest differs')
    record = json.loads(raw)
    for key, name in [('producer_sha256', 'render_view_gate_oracle.py'), ('origin_sha256', 'render_view_gate_origin.py')]:
        require(sha((source_root / 'tools' / name).read_bytes()) == record[key], 'Frozen view producer differs: ' + name)
    origin = authenticate(source_root)
    sample = next(s for s in origin['samples'] if s['name'] == record['source_sample'])
    require(record['source_capture_manifest_sha256'] == ORIGIN_SHA and record['source_recipe_sha256'] == RECIPE_SHA and
            record['source_ram_sha256'] == sample['ram_sha256'] and record['code_segment'] == origin['code_segment'] and
            record['data_segment'] == origin['data_segment'], 'Original render RAM origin differs')
    compressed = (root / 'oracle.bin.gz').read_bytes()
    require(len(compressed) == record['compressed_bytes'] and sha(compressed) == record['compressed_sha256'], 'Frozen view endpoints differ')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        projection = stream.read(2561857)
    require(len(projection) == record['projection_bytes'] == 2561856 and sha(projection) == record['projection_sha256'] and
            projection[:12] == b'LZVIEW01\x14\0\0\0', 'Original view projection differs')
    compressed = (root / 'initialization.bin.gz').read_bytes()
    require(len(compressed) == record['initialization_compressed_bytes'] and
            sha(compressed) == record['initialization_compressed_sha256'], 'Frozen view initialization differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        initialization = stream.read(128015)
    require(len(initialization) == record['initialization_bytes'] == 128014 and
            sha(initialization) == record['initialization_sha256'] and initialization[:12] == b'LZVGIN01\2\0\0\0',
            'Original view initialization projection differs')
    print('render_view_fixture=ok cases=20 initialization_cases=2 raw_ram_files_verified=0 full_frame_claim=0')
    return projection, initialization


def export(path=None, initialization_path=None):
    projections = read_fixture()
    for output, projection in zip((path, initialization_path), projections):
        if output and (not output.exists() or output.read_bytes() != projection):
            output.write_bytes(projection)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle', type=Path)
    parser.add_argument('--initialization', type=Path)
    args = parser.parse_args()
    if args.oracle or args.initialization:
        export(args.oracle, args.initialization)
    else:
        read_fixture()
