"""Authenticate controlled original GRAN-loader physical-state outputs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/gran_loader'
MANIFEST_SHA='39ac07d3379534a84862e340532edd30224e6f2c0dbddc5226aead1fa5ec3db6'
INPUTS=('LEZAC.EXE','GRAN.MST','PROVA.SPR','tools/gran_loader_oracle.py','tools/frame_camera_oracle.py')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen GRAN-loader manifest differs')
    manifest=json.loads(raw)
    for prefix,entries in (('',manifest['assets']),('tools/',manifest['sources'])):
        for name,digest in entries.items():
            require(sha((root/(prefix+name)).read_bytes())==digest,'GRAN-loader input differs: '+name)
    require(manifest['schema']=='lezac-controlled-gran-loader-v1' and len(manifest['cases'])==24 and
        manifest['unknown_guest_writes']==[] and manifest['dos_file_services_modeled'] is True and
        manifest['dos_kernel_execution'] is False,'GRAN-loader evidence domain differs')
    compressed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(compressed)==manifest['compressed_bytes'] and sha(compressed)==manifest['compressed_sha256'],
        'Compressed GRAN-loader state differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        decoded=stream.read(75901)
    require(len(decoded)==75900==manifest['projection_bytes'] and sha(decoded)==manifest['projection_sha256'],
        'Decoded GRAN-loader state differs')
    return decoded


def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz']
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'GRAN output must not replace an authenticated input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'GRAN report/export overlap')
    result=dict(status='failed',whole_game_parity=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing GRAN export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=24,bytes=len(decoded),sha256=sha(decoded))
    except Exception as error:
        result['error']=str(error)
        raise
    finally:
        if report:
            report.write_text(json.dumps(result,sort_keys=True)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    print(json.dumps(run(ROOT,FIXTURE,args.out,args.report),sort_keys=True))
