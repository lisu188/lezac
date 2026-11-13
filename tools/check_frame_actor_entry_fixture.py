"""Authenticate continuous original prefix/link/actor-entry projections."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/frame_actor_entry'
MANIFEST_SHA='de91ed0e80875b96e71f31ac8d3bf8dc461aa80df99dbc797b809622a24f05ab'
INPUTS=('LEZAC.EXE','BOMOMIMK.SPR','CARO.CAR','tools/frame_actor_entry_oracle.py',
    'tools/boss_links_oracle.py','tools/frame_camera_oracle.py','tools/frame_spawner_oracle.py',
    'tools/frame_waiting_oracle.py','tools/ammo_hud_oracle.py')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=(fixture/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen frame actor manifest differs')
    manifest=json.loads(raw)
    for prefix,entries in (('',manifest['asset_sha256']),('tools/',manifest['source_sha256'])):
        for name,digest in entries.items():
            require(sha((root/(prefix+name)).read_bytes())==digest,'Frame actor input differs: '+name)
    require(manifest['schema']=='lezac-controlled-frame-actor-entry-v1' and manifest['cases']==1034 and
        manifest['continuous_prefix_cases']==238 and manifest['register_states']==9531751 and
        manifest['ordered_writes']==1293667 and manifest['later_state_injected'] is False and
        manifest['actor_body_executed'] is False,'Frame actor proof domain differs')
    packed=(fixture/'oracle.bin.gz').read_bytes()
    require(len(packed)==manifest['compressed_bytes'] and sha(packed)==manifest['compressed_sha256'],
        'Compressed frame actor projection differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        decoded=stream.read(321930742)
    require(len(decoded)==321930741==manifest['projection_bytes'] and sha(decoded)==manifest['projection_sha256'],
        'Decoded frame actor projection differs')
    return decoded


def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz']
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Frame actor output must not replace an authenticated input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'Frame actor report/export overlap')
    result=dict(status='failed',whole_game_parity=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists():
                require(out.read_bytes()==decoded,'Existing frame actor export differs; preserved')
            else:
                out.write_bytes(decoded)
        result.update(status='passed',cases=1034,bytes=len(decoded),sha256=sha(decoded))
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
    args=parser.parse_args();print(json.dumps(run(ROOT,FIXTURE,args.out,args.report),sort_keys=True))
