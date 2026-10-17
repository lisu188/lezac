"""Authenticate complete original game keyboard-drain observations."""
import argparse
import hashlib
import json
from pathlib import Path

from game_keyboard_probe.project import projections

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/game_keyboard'
MANIFEST_SHA='e63fa1935050db496bc34dcdc486cec59e0d82935d5758984a676904ba792485'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=FIXTURE):
    raw=(root/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen game keyboard manifest differs')
    manifest=json.loads(raw)
    for path,digest in manifest['sources'].items():
        require(sha((ROOT/path).read_bytes())==digest,'Frozen game keyboard source differs: '+path)
    require({item['name'] for item in manifest['files']}=={'natural.csv.gz','natural-recipe.json'},
        'Game keyboard file domain differs')
    files={}
    for item in manifest['files']:
        raw=(root/item['name']).read_bytes()
        require(len(raw)==item['bytes'] and sha(raw)==item['sha256'],'Frozen game keyboard observation differs')
        files[item['name']]=raw
    recipe=json.loads(files['natural-recipe.json'])
    require(recipe['schema']=='lezac-instrumented-game-keyboard-v1' and recipe['status']=='observed' and
        recipe['passed'] is True and recipe['target_completed'] is True and recipe['validated_target_completed'] is True and
        recipe['child_exit_code']==0 and recipe['canonical_assets_unchanged'] is True,'Game keyboard natural completion differs')
    require(recipe['bios_keyboard_service_profile']=='DOSBox 0.74-3 INT16 AH=00/01 with CB_INT16 and original BIOS queue translation' and
        recipe['dosbox_sha256']=='9231a4f113fcb2573b56b6a1668ea152dd5ca11e9b9ab83058beb9face071ccc' and
        recipe['observed_foreground_range']=='game7A00..7A13 complete keyboard drain with unchanged CRT and BIOS INT16',
        'Game keyboard host/service profile differs')
    for field,name in [('producer_sha256','capture.py'),('input_route_sha256','input_route.py'),('trace_parser_sha256','trace.py')]:
        require(recipe[field]==manifest['sources']['tools/game_keyboard_probe/'+name],'Game keyboard producer binding differs')
    require(recipe['capture_contract_sha256']==manifest['sources']['tools/original_capture_contract.py'],
        'Game keyboard asset contract differs')
    for field,name in [('probe_sha256','lezac_work_probe.h'),('patch_sha256','dos_time_hook.patch'),
        ('clock_patch_sha256','clock_hook.patch'),('clock_api_sha256','lezac_clock_observation.h')]:
        require(recipe['host_build'][field]==manifest['sources']['tools/game_keyboard_probe/'+name],
            'Game keyboard observer binding differs')
    for name,digest in recipe['host_build']['device_fragment_hashes'].items():
        require(digest==manifest['sources']['tools/game_keyboard_probe/'+name],'Game keyboard getter binding differs')
    require(recipe['host_build']['guest_instruction_patches']==0 and recipe['host_build']['cpu_source_unchanged'] is True and
        recipe['process_memory_writes']==recipe['injected_instructions']==recipe['process_pauses']==0 and
        recipe['gameplay_state_seeded'] is False and recipe['clock_or_irq_state_seeded'] is False,
        'Game keyboard original mutation profile differs')
    require(recipe['trace_sha256']==sha(files['natural.csv.gz']) and recipe['trace_bytes']==len(files['natural.csv.gz']),
        'Game keyboard trace binding differs')
    cpu,cases=projections(root/'natural.csv.gz',recipe)
    require(cases==manifest['cases'] and {item['category'] for item in cases}=={0,1,2} and
        sum(item['states'] for item in cases)==manifest['states']==130 and sha(cpu)==manifest['cpu_sha256'],
        'Game keyboard projection differs')
    require(manifest['raw_memory_published'] is False and manifest['raw_memory_available_to_frozen_checker'] is False and
        manifest['irq_eligibility_claim'] is False and manifest['whole_game_parity'] is False,
        'Game keyboard evidence scope differs')
    print('game_keyboard_fixture=ok cases=3 states=130 raw_ram_files_verified=0 irq_eligibility_claim=0')
    return cpu


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu',type=Path)
    args=parser.parse_args();cpu=read_fixture()
    if args.cpu:
        args.cpu.write_bytes(cpu)
