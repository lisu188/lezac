"""Authenticate the frozen tile classifier projection and its producer inputs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/actor_tile_flags'
MANIFEST_SHA='624263f35cc27ad540e6708a7e7abf57974ec62685cca5d25313f07451d4ca6d'
INPUTS=('LEZAC.EXE','tools/actor_tile_flags_oracle.py','tools/actor_contact_oracle.py',
    'tools/actor_precontact_oracle.py','tools/frame_actor_entry_oracle.py','tools/boss_links_oracle.py',
    'tools/frame_camera_oracle.py','tools/frame_spawner_oracle.py','tools/frame_waiting_oracle.py','tools/ammo_hud_oracle.py')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen tile flags manifest differs')
    manifest=json.loads(raw)
    for prefix,entries in (('',manifest['asset_sha256']),('tools/',manifest['source_sha256'])):
        for name,digest in entries.items():
            require(sha((root/(prefix+name)).read_bytes())==digest,'Tile flags input differs: '+name)
    require(manifest['schema']=='lezac-controlled-actor-tile-flags-v1' and manifest['cases']==5972 and
        manifest['domains']==[5932,40] and manifest['later_state_injected'] is False and
        manifest['expiry_after_65a8_executed'] is False and manifest['motion_after_6737_executed'] is False and
        manifest['behavior_after_7018_executed'] is False,'Tile flags proof domain differs')
    packed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(packed)==manifest['compressed_bytes'] and sha(packed)==manifest['compressed_sha256'],
        'Compressed tile flags projection differs')
    size=manifest['projection_bytes'];require(0<size<=128*1024*1024,'Tile flags projection reserve differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded=stream.read(size+1)
    require(len(decoded)==size and sha(decoded)==manifest['projection_sha256'],'Decoded tile flags projection differs')
    return decoded


def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz']
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Tile flags output must not replace an authenticated input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'Tile flags report/export overlap')
    result=dict(status='failed',whole_game_parity=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing tile flags export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=5972,bytes=len(decoded),sha256=sha(decoded))
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
