"""Authenticate controlled standalone-camera pixels before exporting them."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'tests/fixtures/standalone_camera'
MANIFEST_SHA = 'bc634442c50f8182c11be74de3c02cb46b21b7914da068d68df3daf696a1c520'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw = (fixture/'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA,'Frozen standalone-camera manifest differs')
    manifest = json.loads(raw)
    for prefix, entries in (('',manifest['assets']),('tools/',manifest['sources'])):
        for name,digest in entries.items():
            require(sha((root/(prefix+name)).read_bytes()) == digest,'Standalone-camera input differs: '+name)
    require(manifest['schema'] == 'lezac-controlled-standalone-camera-v1' and len(manifest['cases']) == 24,
        'Standalone-camera evidence domain differs')
    compressed = (fixture/'oracle.bin.gz').read_bytes()
    require(len(compressed) == manifest['compressed_bytes'] and sha(compressed) == manifest['compressed_sha256'],
        'Compressed standalone-camera pixels differ')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        decoded = stream.read(1536349)
    require(len(decoded) == 1536348 == manifest['projection_bytes'] and sha(decoded) == manifest['projection_sha256'],
        'Decoded standalone-camera pixels differ')
    return decoded


def run(root,fixture,out=None,report=None):
    if out and report:
        require(out.resolve() != report.resolve() and not (
            out.exists() and report.exists() and out.samefile(report)), 'Camera report/export overlap')
    result = dict(status='failed',full_frame_claim=False)
    try:
        decoded = read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes() == decoded,'Existing camera export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=24,bytes=len(decoded),sha256=sha(decoded))
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        if report:
            report.write_text(json.dumps(result,sort_keys=True)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--report',type=Path)
    args = parser.parse_args()
    print(json.dumps(run(ROOT,FIXTURE,args.out,args.report),sort_keys=True))
