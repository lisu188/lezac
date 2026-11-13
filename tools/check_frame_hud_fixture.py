"""Authenticate the complete original HUD/keyboard bridge and controlled HUD endpoints."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from frame_hud_probe.project import projections,clock_projection

ROOT=Path(__file__).resolve().parents[1];FIXTURE=ROOT/'tests/fixtures/frame_hud'
MANIFEST_SHA='020505b23d9e76d502baabcf7b70e690b8804216b5a0f58b4056e8dd9719edb4'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=FIXTURE):
    raw=(root/'manifest.json').read_bytes();require(sha(raw)==MANIFEST_SHA,'Frozen frame HUD manifest differs');manifest=json.loads(raw)
    for path,digest in manifest['sources'].items():
        require(sha((ROOT/path).read_bytes())==digest,'Frozen frame HUD source differs: '+path)
    require({item['name'] for item in manifest['files']}=={'natural.csv.gz','natural-recipe.json','oracle.bin.gz','oracle-origin.json'},
        'Frame HUD file domain differs')
    files={}
    for item in manifest['files']:
        raw=(root/item['name']).read_bytes();require(len(raw)==item['bytes'] and sha(raw)==item['sha256'],'Frozen frame HUD observation differs')
        files[item['name']]=raw
    recipe=json.loads(files['natural-recipe.json']);host=recipe['host_build']
    require(recipe['schema']=='lezac-instrumented-frame-hud-v1' and recipe['status']=='observed' and recipe['passed'] is True and
        recipe['target_completed'] is True and recipe['validated_target_completed'] is True and recipe['child_exit_code']==0 and
        recipe['canonical_assets_unchanged'] is True,'Frame HUD natural completion differs')
    require(recipe['dosbox_sha256']=='b45b719d2ddf2395a288eea5b2c59be8f7a5e3e0f0027749a985ac24fa8bcb8a' and
        recipe['observed_foreground_range']=='game79E8..7A13 complete HUD prelude and keyboard drain with unchanged callees',
        'Frame HUD host/profile differs')
    for field,name in [('producer_sha256','capture.py'),('input_route_sha256','input_route.py'),('trace_parser_sha256','trace.py')]:
        require(recipe[field]==manifest['sources']['tools/frame_hud_probe/'+name],'Frame HUD producer binding differs')
    require(recipe['capture_contract_sha256']==manifest['sources']['tools/original_capture_contract.py'],'Frame HUD asset contract differs')
    for field,name in [('probe_sha256','lezac_work_probe.h'),('patch_sha256','dos_time_hook.patch'),
        ('clock_patch_sha256','clock_hook.patch'),('clock_api_sha256','lezac_clock_observation.h'),('rebuild_producer_sha256','rebuild.py')]:
        require(host[field]==manifest['sources']['tools/frame_hud_probe/'+name],'Frame HUD observer/rebuild binding differs')
    for name,digest in host['device_fragment_hashes'].items():
        require(digest==manifest['sources']['tools/frame_hud_probe/'+name],'Frame HUD getter binding differs')
    require(host['guest_instruction_patches']==0 and host['cpu_source_unchanged'] is True and recipe['process_memory_writes']==
        recipe['injected_instructions']==recipe['process_pauses']==0 and recipe['gameplay_state_seeded'] is False and
        recipe['clock_or_irq_state_seeded'] is False,'Frame HUD original mutation profile differs')
    require(recipe['trace_sha256']==sha(files['natural.csv.gz']) and recipe['trace_bytes']==len(files['natural.csv.gz']),
        'Frame HUD trace binding differs')
    cpu,cases=projections(root/'natural.csv.gz',recipe);clock=clock_projection(root/'natural.csv.gz',cases)
    require(cases==manifest['cases'] and {item['category'] for item in cases}=={0,3} and sum(item['states'] for item in cases)==693 and
        sha(cpu)==manifest['cpu_sha256'] and sha(clock)==manifest['clock_sha256'],'Frame HUD projections differ')
    origin=json.loads(files['oracle-origin.json'])
    with gzip.GzipFile(fileobj=io.BytesIO(files['oracle.bin.gz'])) as stream:
        oracle=stream.read(28454)
    require(len(oracle)==origin['projection_bytes']==28453 and sha(oracle)==origin['projection_sha256'] and len(origin['cases'])==17 and
        origin['producer_sha256']==manifest['sources']['tools/frame_hud_probe/oracle.py'] and origin['original_calls_stubbed']==0 and
        origin['instruction_patches']==0 and origin['natural_gameplay_claim'] is False,'Frame HUD original oracle differs')
    require(manifest['raw_memory_published'] is False and manifest['raw_memory_available_to_frozen_checker'] is False and
        manifest['whole_game_parity'] is False and manifest['full_frame_claim'] is False,'Frame HUD evidence scope differs')
    print('frame_hud_fixture=ok natural_cases=2 states=693 oracle_cases=17 raw_ram_files_verified=0 full_frame_claim=0')
    return cpu,clock,oracle


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('cpu','clock','oracle'):
        parser.add_argument('--'+name,type=Path)
    args=parser.parse_args();outputs=read_fixture()
    for name,raw in zip(('cpu','clock','oracle'),outputs):
        path=getattr(args,name)
        if path:
            path.write_bytes(raw)
