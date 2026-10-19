"""Authenticate the frozen movement projection and every producer input."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/actor_motion'
MANIFEST_SHA='5a92392c878cab569d73e108837835d429ef81062e605095892b21db2290ed6c'
INPUTS=('LEZAC.EXE',*('tools/'+name for name in (
    'actor_motion_oracle.py','actor_steering_oracle.py','actor_contact_oracle.py',
    'actor_precontact_oracle.py','frame_actor_entry_oracle.py','boss_links_oracle.py',
    'frame_camera_oracle.py','frame_spawner_oracle.py','frame_waiting_oracle.py','ammo_hud_oracle.py')))
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen motion manifest differs')
    manifest=json.loads(raw)
    catalog=set(manifest['asset_sha256'])|{'tools/'+name for name in manifest['source_sha256']}
    require(set(INPUTS)==catalog and len(INPUTS)==len(catalog),'Motion input catalog differs')
    for prefix,entries in (('',manifest['asset_sha256']),('tools/',manifest['source_sha256'])):
        for name,digest in entries.items():
            require(sha((root/(prefix+name)).read_bytes())==digest,'Motion input differs: '+name)
    require(manifest['schema']=='lezac-controlled-actor-motion-v1' and manifest['cases']==78927 and
        manifest['domains']==[6475,376,6416,65552,54,54] and
        manifest['trace_storage']=='register-delta-v1' and manifest['later_state_injected'] is False and
        manifest['actor_near_return_executed'] is True and manifest['divide_fault_handler_executed'] is False and
        manifest['production_app_comparison'] is False and manifest['full_frame_claim'] is False,
        'Motion proof domain differs')
    packed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(packed)==manifest['compressed_bytes'] and sha(packed)==manifest['compressed_sha256'],
        'Compressed motion projection differs')
    size=manifest['projection_bytes'];require(0<size<=192*1024*1024,'Motion projection reserve differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded=stream.read(size+1)
    require(len(decoded)==size and sha(decoded)==manifest['projection_sha256'],'Decoded motion projection differs')
    return decoded


def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz']
    def aliases(a,b):
        return a.resolve()==b.resolve() or (a.exists() and b.exists() and a.samefile(b))
    for candidate in (out,report):
        if candidate:
            require(not any(aliases(candidate,path) for path in protected),
                'Motion output must not replace an authenticated input')
    if out and report:
        require(not aliases(out,report),'Motion report/export overlap')
    result=dict(status='failed',whole_game_parity=False,full_frame_claim=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing motion export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=78927,bytes=len(decoded),sha256=sha(decoded))
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
