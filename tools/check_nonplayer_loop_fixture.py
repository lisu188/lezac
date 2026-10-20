"""Authenticate the frozen original consecutive-actor caller projection."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/nonplayer_loop'
MANIFEST_SHA='63413defbef7be8db9bbcee979a472e87f41c4c859c8b8886aafa3db580e097a'
INPUTS=('LEZAC.EXE','tools/actor_contact_oracle.py','tools/actor_motion_oracle.py',
    'tools/actor_precontact_oracle.py','tools/actor_steering_oracle.py','tools/ammo_hud_oracle.py',
    'tools/boss_links_oracle.py','tools/frame_actor_entry_oracle.py','tools/frame_camera_oracle.py',
    'tools/frame_spawner_oracle.py','tools/frame_waiting_oracle.py','tools/nonplayer_loop_oracle.py')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen nonplayer loop manifest differs')
    manifest=json.loads(raw)
    inputs={**manifest['asset_sha256'],**{'tools/'+name:digest for name,digest in manifest['source_sha256'].items()}}
    require(set(inputs)==set(INPUTS),'Nonplayer loop input catalog differs')
    for name,digest in inputs.items():
        require(sha((root/name).read_bytes())==digest,'Nonplayer loop input differs: '+name)
    require(manifest['schema']=='lezac-controlled-nonplayer-loop-v1' and
        manifest['coverage']==dict(cases=92,register_states=213051,ordered_writes=38232,events=2294,
            actor_calls=453,actor_returns=449,outcome_0=88,outcome_1=2,outcome_2=1,outcome_3=1) and
        manifest['one_live_stack'] is True and manifest['later_state_injected'] is False and
        manifest['production_app_comparison'] is False and manifest['full_frame_claim'] is False,
        'Nonplayer loop proof domain differs')
    packed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(packed)==manifest['compressed_bytes'] and sha(packed)==manifest['compressed_sha256'],
        'Compressed nonplayer loop projection differs')
    size=manifest['projection_bytes']
    require(size==2396804,'Nonplayer loop projection reserve differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded=stream.read(size+1)
    require(len(decoded)==size and sha(decoded)==manifest['projection_sha256'],
        'Decoded nonplayer loop projection differs')
    return decoded


def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz']
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Nonplayer loop output must not replace an authenticated input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'Nonplayer loop report/export overlap')
    result=dict(status='failed',whole_game_parity=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing nonplayer loop export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=92,bytes=len(decoded),sha256=sha(decoded))
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
