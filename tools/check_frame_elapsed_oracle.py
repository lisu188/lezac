"""Authenticate the frozen, controlled original arithmetic-phase oracle."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/frame_elapsed'
MANIFEST_SHA='c0dedd7369a86f0dfe81480bdd14ec07756313092867c098f8232795358034df'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def read_fixture(root=FIXTURE):
    raw=(root/'manifest.json').read_bytes()
    if sha(raw)!=MANIFEST_SHA:
        raise ValueError('Controlled elapsed manifest differs')
    manifest=json.loads(raw)
    item=manifest['files'][0]
    compressed=(root/'original.bin.gz').read_bytes()
    if len(compressed)!=item['bytes'] or sha(compressed)!=item['sha256']:
        raise ValueError('Controlled elapsed observations differ')
    if sha((ROOT/'tools/frame_clock_probe/oracle.py').read_bytes())!=manifest['producer_sha256']:
        raise ValueError('Controlled elapsed oracle producer differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        projection=stream.read(2*1024**2+1)
    if len(projection)!=manifest['projection_bytes'] or sha(projection)!=manifest['projection_sha256']:
        raise ValueError('Controlled elapsed projection differs')
    print('frame_elapsed_oracle_fixture=ok cases=3375 seeded_inputs=1 natural_gameplay_claim=0')
    return projection


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projection',type=Path)
    args=parser.parse_args()
    projection=read_fixture()
    if args.projection:
        args.projection.write_bytes(projection)
