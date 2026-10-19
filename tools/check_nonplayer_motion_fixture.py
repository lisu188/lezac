"""Authenticate the frozen pre-terrain nonplayer motion projection."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/nonplayer_motion'
MANIFEST_SHA='f65a6adad669a4e301ba40c05c5ff14468c161e682e114c24f120036e9296acc'
INPUTS=('LEZAC.EXE','tools/actor_contact_oracle.py','tools/actor_motion_oracle.py',
    'tools/actor_precontact_oracle.py','tools/actor_steering_oracle.py','tools/ammo_hud_oracle.py',
    'tools/boss_links_oracle.py','tools/check_actor_motion_fixture.py','tools/frame_actor_entry_oracle.py',
    'tools/frame_camera_oracle.py','tools/frame_spawner_oracle.py','tools/frame_waiting_oracle.py',
    'tools/nonplayer_motion_oracle.py')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen nonplayer motion manifest differs')
    manifest=json.loads(raw)
    inputs={**manifest['asset_sha256'],**manifest['source_sha256']}
    require(set(inputs)==set(INPUTS),'Nonplayer motion input catalog differs')
    for name,digest in inputs.items():
        require(sha((root/name).read_bytes())==digest,'Nonplayer motion input differs: '+name)
    require(manifest['schema']=='lezac-controlled-nonplayer-motion-prefix-v1' and
        manifest['cases']==6569 and manifest['domains']==[6461,54,54] and
        manifest['outcomes']==[6539,0,30] and manifest['normalized_private_stack'] is True and
        manifest['later_state_injected'] is False and manifest['full_frame_claim'] is False and
        manifest['production_app_comparison'] is False,'Nonplayer motion proof domain differs')
    packed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(packed)==manifest['compressed_bytes'] and sha(packed)==manifest['compressed_sha256'],
        'Compressed nonplayer motion projection differs')
    size=manifest['projection_bytes']
    require(size==4296170,'Nonplayer motion projection reserve differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded=stream.read(size+1)
    require(len(decoded)==size and sha(decoded)==manifest['projection_sha256'],
        'Decoded nonplayer motion projection differs')
    return decoded


def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz']
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Nonplayer motion output must not replace an authenticated input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'Nonplayer motion report/export overlap')
    result=dict(status='failed',whole_game_parity=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing nonplayer motion export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=6569,bytes=len(decoded),sha256=sha(decoded))
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
