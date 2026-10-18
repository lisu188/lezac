"""Authenticate complete controlled original boss-link instruction outputs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/boss_links'
MANIFEST_SHA='61028c7c10ffcd7726b21e15e426fe975bc7135800b19d3673ee8f827e6521ae'
INPUTS=('LEZAC.EXE','tools/boss_links_oracle.py','tools/frame_camera_oracle.py')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen boss-link manifest differs')
    manifest=json.loads(raw)
    require(sha((root/'LEZAC.EXE').read_bytes())==manifest['executable_sha256'],'Original link executable differs')
    for name,digest in manifest['sources'].items():
        require(sha((root/'tools'/name).read_bytes())==digest,'Original link producer differs: '+name)
    require(manifest['schema']=='lezac-controlled-boss-links-v1' and manifest['cases']==1413 and
        manifest['register_states']==368425 and manifest['writes']==45014 and
        manifest['complete_memory_observer_control'] is True and manifest['calls_stubbed']==0 and
        manifest['sine_initializer']['sha256']=='466aea5bff071d610e66710d74d2ddecc79853ece03a4ae038113e83609e72d8',
        'Original link evidence domain differs')
    compressed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(compressed)==manifest['compressed_bytes'] and sha(compressed)==manifest['compressed_sha256'],
        'Compressed original link projection differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        decoded=stream.read(11599957)
    require(len(decoded)==11599956==manifest['projection_bytes'] and sha(decoded)==manifest['projection_sha256'],
        'Decoded original link projection differs')
    return decoded


def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz']
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Link output must not replace an authenticated input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'Link report/export overlap')
    result=dict(status='failed',whole_game_parity=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing link export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=1413,bytes=len(decoded),sha256=sha(decoded))
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
