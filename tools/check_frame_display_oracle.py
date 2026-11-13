"""Authenticate the exact controlled software Real48 display corpus."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_display'
MANIFEST_SHA = '4ca7b946aa191dda4d316b5fa85c851e71b4e28ca448e680f3e1c3d2ad4aea3d'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_fixture(root=FIXTURE):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Controlled display manifest differs')
    manifest = json.loads(raw)
    require(sha((ROOT / 'tools/frame_display_probe/oracle.py').read_bytes()) == manifest['producer_sha256'],
        'Controlled display producer differs')
    require({item['name'] for item in manifest['files']} == {'instructions.bin.gz', 'endpoints.bin.gz'},
        'Controlled display file domain differs')
    projections = {}
    for item in manifest['files']:
        compressed = (root / item['name']).read_bytes()
        require(len(compressed) == item['bytes'] and sha(compressed) == item['sha256'],
            'Controlled display observations differ')
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            projection = stream.read(64 * 1024**2 + 1)
        require(len(projection) == item['projection_bytes'] and len(projection) <= 64 * 1024**2 and
            sha(projection) == item['projection_sha256'], 'Controlled display projection differs')
        projections[item['name']] = projection
    print('frame_display_oracle_fixture=ok instruction_cases=256 states=148357 endpoint_cases=196608 seeded_inputs=1 natural_gameplay_claim=0')
    return projections['instructions.bin.gz'], projections['endpoints.bin.gz']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instructions', type=Path)
    parser.add_argument('--endpoints', type=Path)
    args = parser.parse_args()
    instructions, endpoints = read_fixture()
    if args.instructions:
        args.instructions.write_bytes(instructions)
    if args.endpoints:
        args.endpoints.write_bytes(endpoints)
