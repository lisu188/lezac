"""Authenticate the frozen expiry projection and its producer inputs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/actor_expiry'
MANIFEST_SHA='6776b29677aee000904fe9ed35356e78eca7a7b85b21b4da3d34c941a18478bb'
INPUTS=('LEZAC.EXE','tools/actor_expiry_oracle.py','tools/actor_contact_oracle.py',
    'tools/actor_precontact_oracle.py','tools/frame_actor_entry_oracle.py','tools/boss_links_oracle.py',
    'tools/frame_camera_oracle.py','tools/frame_spawner_oracle.py','tools/frame_waiting_oracle.py','tools/ammo_hud_oracle.py')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen expiry manifest differs')
    manifest=json.loads(raw)
    for prefix,entries in (('',manifest['asset_sha256']),('tools/',manifest['source_sha256'])):
        for name,digest in entries.items():
            require(sha((root/(prefix+name)).read_bytes())==digest,'Expiry input differs: '+name)
    require(manifest['schema']=='lezac-controlled-actor-expiry-v1' and manifest['cases']==3258 and
        manifest['domains']==[3162,96] and manifest['physical_actor_alias_cases']==72 and
        manifest['real_caller_cases']==24 and manifest['later_state_injected'] is False and
        manifest['physical_compaction_executed'] is True and manifest['visual_compaction_executed'] is True and
        manifest['motion_after_73e5_executed'] is False and manifest['actor_near_return_executed'] is True,
        'Expiry proof domain differs')
    packed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(packed)==manifest['compressed_bytes'] and sha(packed)==manifest['compressed_sha256'],
        'Compressed expiry projection differs')
    size=manifest['projection_bytes'];require(0<size<=192*1024*1024,'Expiry projection reserve differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded=stream.read(size+1)
    require(len(decoded)==size and sha(decoded)==manifest['projection_sha256'],'Decoded expiry projection differs')
    return decoded


def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz']
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Expiry output must not replace an authenticated input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'Expiry report/export overlap')
    result=dict(status='failed',whole_game_parity=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing expiry export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=3258,bytes=len(decoded),sha256=sha(decoded))
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
