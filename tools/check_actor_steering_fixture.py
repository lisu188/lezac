"""Authenticate the frozen steering projection and exact producer inputs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/actor_steering'
MANIFEST_SHA='06bb16586bd72e2555c8ff4daafe972afadf405528a084ddd561b5849ca5c3cf'
INPUTS=('LEZAC.EXE','tools/actor_steering_oracle.py')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen steering manifest differs')
    manifest=json.loads(raw)
    for prefix,entries in (('',manifest['asset_sha256']),('tools/',manifest['source_sha256'])):
        for name,digest in entries.items():
            require(sha((root/(prefix+name)).read_bytes())==digest,'Steering input differs: '+name)
    require(manifest['schema']=='lezac-controlled-actor-steering-v1' and manifest['cases']==3736 and
        manifest['domains']==[2136,64,1536] and manifest['outcomes']==[2961,775] and
        manifest['trace_storage']=='register-delta-v1' and manifest['later_state_injected'] is False and
        manifest['real_near_return_executed'] is True and manifest['real_far_return_executed'] is True and
        manifest['production_app_comparison'] is False,'Steering proof domain differs')
    packed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(packed)==manifest['compressed_bytes'] and sha(packed)==manifest['compressed_sha256'],
        'Compressed steering projection differs')
    size=manifest['projection_bytes'];require(0<size<=192*1024*1024,'Steering projection reserve differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded=stream.read(size+1)
    require(len(decoded)==size and sha(decoded)==manifest['projection_sha256'],'Decoded steering projection differs')
    return decoded


def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz']
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Steering output must not replace an authenticated input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'Steering report/export overlap')
    result=dict(status='failed',whole_game_parity=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing steering export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=3736,bytes=len(decoded),sha256=sha(decoded))
    except Exception as error:
        result['error']=str(error);raise
    finally:
        if report:
            report.write_text(json.dumps(result,sort_keys=True)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path);parser.add_argument('--report',type=Path);args=parser.parse_args()
    print(json.dumps(run(ROOT,FIXTURE,args.out,args.report),sort_keys=True))
