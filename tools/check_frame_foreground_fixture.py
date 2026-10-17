"""Authenticate the original whole foreground corpus and native palette function oracle."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from frame_foreground_probe.project import projections,clock_projection

ROOT=Path(__file__).resolve().parents[1];FIXTURE=ROOT/'tests/fixtures/frame_foreground'
MANIFEST_SHA='dfc7d3dfef4a813b9c2d96d9d3a7b0e0d19fa3fc150b1daeaf6db875b6e62f69'
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def require(value,message):
    if not value:raise ValueError(message)

def read_fixture(root=FIXTURE):
    raw=(root/'manifest.json').read_bytes();require(sha(raw)==MANIFEST_SHA,'Frozen foreground manifest differs');manifest=json.loads(raw)
    for path,digest in manifest['sources'].items():
        require(sha((ROOT/path).read_bytes())==digest,'Frozen foreground source differs: '+path)
    domain={'natural.csv.gz','natural-recipe.json','palette.bin.gz','palette-origin.json','host-rebuild.py'}
    require({item['name'] for item in manifest['files']}==domain,'Frozen foreground file domain differs')
    files={}
    for item in manifest['files']:
        raw=(root/item['name']).read_bytes()
        require(len(raw)==item['bytes'] and sha(raw)==item['sha256'],'Frozen foreground observation differs')
        files[item['name']]=raw
    recipe=json.loads(files['natural-recipe.json']);host=recipe['host_build']
    require(recipe['schema']=='lezac-instrumented-frame-foreground-v1' and recipe['status']=='observed' and recipe['passed'] is True and
        recipe['target_completed'] is True and recipe['validated_target_completed'] is True and recipe['child_exit_code']==0 and
        recipe['canonical_assets_unchanged'] is True,'Foreground natural completion differs')
    require(recipe['dosbox_sha256']==host['host_sha256']=='51f268b269597e50e70f18081189e4d0196832f80150eee8f35cea49d08ca702' and
        recipe['observed_foreground_range']=='game7903..7A13 complete pacing, HUD prelude and keyboard drain with unchanged callees',
        'Foreground host/profile differs')
    for field,name in [('producer_sha256','capture.py'),('input_route_sha256','input_route.py'),('trace_parser_sha256','trace.py')]:
        require(recipe[field]==manifest['sources']['tools/frame_foreground_probe/'+name],'Foreground producer binding differs')
    require(recipe['capture_contract_sha256']==manifest['sources']['tools/original_capture_contract.py'],'Foreground asset contract differs')
    for field,name in [('probe_sha256','lezac_work_probe.h'),('patch_sha256','dos_time_hook.patch'),
        ('clock_patch_sha256','clock_hook.patch'),('clock_api_sha256','lezac_clock_observation.h'),('rebuild_producer_sha256','rebuild.py')]:
        require(host[field]==manifest['sources']['tools/frame_foreground_probe/'+name],'Foreground observer/rebuild binding differs')
    require(host['repair_producer_sha256']==sha(files['host-rebuild.py']),'Foreground actual incremental rebuild receipt differs')
    require(set(host['device_fragment_hashes'])=={'pic_tickers_observation.inc','vga_clock_observation.inc','render_clock_observation.inc',
        'gfx_clock_observation.inc','keyboard_clock_observation.inc','mixer_clock_observation.inc'},'Foreground getter domain differs')
    for name,digest in host['device_fragment_hashes'].items():
        require(digest==manifest['sources']['tools/frame_foreground_probe/'+name],'Foreground getter binding differs')
    require(host['guest_instruction_patches']==0 and host['cpu_source_unchanged'] is True and recipe['process_memory_writes']==
        recipe['injected_instructions']==recipe['process_pauses']==0 and recipe['gameplay_state_seeded'] is False and
        recipe['clock_or_irq_state_seeded'] is False,'Foreground original mutation profile differs')
    require(recipe['trace_sha256']==sha(files['natural.csv.gz']) and recipe['trace_bytes']==len(files['natural.csv.gz']),'Foreground trace binding differs')
    cpu,cases=projections(root/'natural.csv.gz',recipe);clock=clock_projection(root/'natural.csv.gz',cases)
    require(cases==manifest['cases'] and {item['category'] for item in cases}=={0,1} and sum(item['states'] for item in cases)==108343 and
        sha(cpu)==manifest['cpu_sha256'] and sha(clock)==manifest['clock_sha256'],'Foreground projections differ')
    origin=json.loads(files['palette-origin.json'])
    with gzip.GzipFile(fileobj=io.BytesIO(files['palette.bin.gz'])) as stream:palette=stream.read(500000)
    require(len(palette)==manifest['palette_bytes'] and sha(palette)==origin['oracle_sha256'] and origin['cases']==96 and
        origin['producer_sha256']==manifest['sources']['tools/frame_foreground_probe/build_palette_oracle.py'] and
        origin['driver_sha256']==manifest['sources']['tools/frame_foreground_probe/palette_oracle_driver.cpp'] and
        origin['native_sdl_mapping'] is True and origin['original_function_bodies_changed'] is False and
        origin['original_host_execution'] is False,'Foreground native palette oracle differs')
    runtime=origin['sdl_runtime_library']
    require(runtime['verified'] is True and runtime['sha256']==origin['sdl_library_sha256']==origin['sdl_link_library_sha256'] and
        origin['runtime_identity_producer_sha256']==manifest['sources']['tools/frame_foreground_probe/sdl_provenance.py'] and
        origin['build_environment_is_complete'] is True and 'LD_PRELOAD' not in origin['build_environment'] and
        origin['run_environment_is_complete'] is True and 'LD_PRELOAD' not in origin['run_environment'] and
        bool(origin['run_environment']['LD_LIBRARY_PATH']),'Foreground actual SDL runtime provenance differs')
    require(manifest['raw_memory_published'] is False and manifest['raw_memory_available_to_frozen_checker'] is False and
        manifest['whole_game_parity'] is False and manifest['full_frame_claim'] is False,'Foreground evidence scope differs')
    print('frame_foreground_fixture=ok natural_cases=2 states=108343 palette_cases=96 raw_ram_files_verified=0 full_frame_claim=0')
    return cpu,clock,palette

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('cpu','clock','palette'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args();outputs=read_fixture()
    for name,raw in zip(('cpu','clock','palette'),outputs):
        path=getattr(args,name)
        if path:path.write_bytes(raw)
