"""Authenticate the compact original post-render-to-frame-end corpus."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/frame_post_render'
MANIFEST_SHA='23389f696120f03b2d8d78714a747cd70ab1b3f7624affae77bd2100fef13867'
PROJECTION_BYTES=28447607
INPUTS=('LEZAC.EXE',*[f'tools/{name}.py' for name in (
    'actor_contact_oracle','actor_motion_oracle','actor_precontact_oracle','actor_steering_oracle',
    'actor_update_oracle','ammo_hud_oracle','boss_links_oracle','capture_original_collapse_update',
    'capture_original_debris_update','frame_actor_entry_oracle','frame_actor_pass_oracle',
    'frame_camera_oracle','frame_iteration_oracle','frame_post_render_oracle','frame_spawner_oracle','frame_waiting_oracle',
    'nonplayer_loop_oracle','oracle_failure_report','player_motion_oracle','player_post_oracle',
    'scan_livels_debris_sites')])
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def require(yes,message):
    if not yes: raise ValueError(message)

def bounded(path,size):
    with path.open('rb') as stream: raw=stream.read(size+1)
    require(len(raw)<=size,'Frame post-render input exceeds reserve')
    return raw

def read_fixture(root=ROOT,fixture=FIXTURE):
    raw=bounded(fixture/'manifest.json',65536)
    require(sha(raw)==MANIFEST_SHA,'Frozen frame post-render manifest differs')
    manifest=json.loads(raw)
    inputs={**manifest['asset_sha256'],**{'tools/'+k:v for k,v in manifest['source_sha256'].items()}}
    require(set(inputs)==set(INPUTS),'Frame post-render input catalog differs')
    for name,digest in inputs.items():
        require(sha(bounded(root/name,1048576))==digest,'Frame post-render input differs: '+name)
    require(manifest['schema']=='lezac-controlled-post-render-to-frame-end-v1' and manifest['cases']==1348 and
        manifest['dense_cases']==67 and manifest['outcomes']=={'1':1140,'2':16,'4':72,'5':53,'6':9,'7':16,'8':24,'9':18} and
        manifest['phase_masks']=={'8':16,'9':112,'11':2,'15':1218} and manifest['original_instructions']==4983001 and
        manifest['ordered_writes']==1431749 and manifest['ordered_ports']==480 and
        manifest['unicorn_version']=='2.1.4' and
        manifest['unicorn_library_sha256']=='ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        all(manifest[k] is True for k in ('actual_library_mapping_verified','full_memory_observer_control',
            'ordered_writes_reconstruct_memory','controlled_initial_memory','post_render_prefix_executed')) and
        all(manifest[k]==0 for k in ('instruction_patches','calls_stubbed','interrupts_delivered','hardware_inputs')) and
        all(manifest[k] is False for k in ('later_state_injected','natural_capture','raw_memory_published',
            'actual_app_integration','full_frame_claim','rendering_prefix_executed','work_clock_claim',
            'actor_pass_stability_hold_cleared','host_hardware_io')),'Frame post-render proof domain differs')
    require(manifest['projection_bytes']==PROJECTION_BYTES and manifest['compressed_bytes']==3349853,
        'Frame post-render projection reserve differs')
    packed=bounded(fixture/'oracle.bin.gz',3349853)
    require(len(packed)==manifest['compressed_bytes'] and sha(packed)==manifest['compressed_sha256'],
        'Compressed frame post-render projection differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream: decoded=stream.read(PROJECTION_BYTES+1)
    require(len(decoded)==PROJECTION_BYTES and sha(decoded)==manifest['projection_sha256'],
        'Decoded frame post-render projection differs')
    return decoded

def run(root,fixture,out=None,report=None):
    protected=[root/name for name in INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz',Path(__file__).resolve()]
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=path.resolve() and not
                (candidate.exists() and path.exists() and candidate.samefile(path)) for path in protected),
                'Frame post-render output must not replace protected input')
    if out and report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'Frame post-render report/export overlap')
    result=dict(status='failed',whole_game_parity=False)
    try:
        decoded=read_fixture(root,fixture)
        if out:
            if out.exists(): require(bounded(out,PROJECTION_BYTES)==decoded,'Existing frame post-render export differs; preserved')
            else:
                with out.open('xb') as stream: stream.write(decoded)
        result.update(status='passed',cases=1348,bytes=len(decoded),sha256=sha(decoded))
    except Exception as error:
        result['error']=str(error)
        raise
    finally:
        if report: report.write_text(json.dumps(result,sort_keys=True)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path);parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    print(json.dumps(run(ROOT,FIXTURE,args.out,args.report),sort_keys=True))
