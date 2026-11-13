"""Authenticate the exact original CRT calls and original-source BIOS classifier."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from crt_keyboard_probe.project import projections

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/crt_keyboard'
MANIFEST_SHA='1f31fd8d032f39673a0678c323cd52100dde362c4c9ef90ff81e4b57c08e16c9'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=FIXTURE):
    raw=(root/'manifest.json').read_bytes();require(sha(raw)==MANIFEST_SHA,'Frozen CRT keyboard manifest differs')
    manifest=json.loads(raw)
    for path,digest in manifest['sources'].items():
        require(sha((ROOT/path).read_bytes())==digest,'Frozen CRT keyboard source differs: '+path)
    require({item['name'] for item in manifest['files']}=={'classification.bin.gz','classification-origin.json',
        'natural.csv.gz','natural-recipe.json','pending.bin.gz','pending-origin.json'},'CRT keyboard file domain differs')
    files={}
    for item in manifest['files']:
        raw=(root/item['name']).read_bytes()
        require(len(raw)==item['bytes'] and sha(raw)==item['sha256'],'Frozen CRT keyboard observation differs')
        files[item['name']]=raw
    origin=json.loads(files['classification-origin.json'])
    with gzip.GzipFile(fileobj=io.BytesIO(files['classification.bin.gz'])) as stream:
        classification=stream.read(196609)
    require(len(classification)==origin['bytes']==196608 and sha(classification)==origin['projection_sha256'] and
        origin['inputs']==65536 and origin['original_function_unchanged'] is True and origin['whole_bios_handler_execution_claim'] is False,
        'Original-source BIOS classifier differs')
    pendingOrigin=json.loads(files['pending-origin.json'])
    with gzip.GzipFile(fileobj=io.BytesIO(files['pending.bin.gz'])) as stream:
        pending=stream.read(87223)
    require(len(pending)==pendingOrigin['projection_bytes']==87222 and sha(pending)==pendingOrigin['projection_sha256']==
        manifest['pending_oracle_projection_sha256'] and pendingOrigin['cases']==510 and pendingOrigin['original_calls_stubbed'] is False and
        pendingOrigin['instruction_patches']==0 and pendingOrigin['full_endpoint_flags'] is True and pendingOrigin['producer_sha256']==
        manifest['sources']['tools/crt_keyboard_probe/pending_oracle.py'],'Original pending-byte oracle differs')
    recipe=json.loads(files['natural-recipe.json'])
    require(recipe['status']=='observed' and recipe['passed'] is True and recipe['target_completed'] is True and
        recipe['validated_target_completed'] is True and recipe['child_exit_code']==0 and recipe['canonical_assets_unchanged'] is True,
        'CRT keyboard natural completion differs')
    require(recipe['bios_keyboard_service_profile']=='DOSBox 0.74-3 INT16 AH=00/01 with CB_INT16 and original BIOS queue translation' and
        recipe['dosbox_sha256']=='70b32d891bb5d8d236630da226b7d8a2316c1ce9d72d029b30477915c72c0380',
        'CRT keyboard host/service profile differs')
    for field,name in [('producer_sha256','capture.py'),('input_route_sha256','input_route.py'),('trace_parser_sha256','trace.py')]:
        require(recipe[field]==manifest['sources']['tools/crt_keyboard_probe/'+name],'CRT keyboard producer binding differs')
    require(recipe['capture_contract_sha256']==manifest['sources']['tools/original_capture_contract.py'],
        'CRT keyboard asset contract differs')
    for field,name in [('probe_sha256','lezac_work_probe.h'),('patch_sha256','dos_time_hook.patch'),
        ('clock_patch_sha256','clock_hook.patch'),('clock_api_sha256','lezac_clock_observation.h')]:
        require(recipe['host_build'][field]==manifest['sources']['tools/crt_keyboard_probe/'+name],
            'CRT keyboard observer binding differs')
    for name,digest in recipe['host_build']['device_fragment_hashes'].items():
        require(digest==manifest['sources']['tools/crt_keyboard_probe/'+name],'CRT keyboard getter binding differs')
    require(recipe['trace_sha256']==sha(files['natural.csv.gz']) and recipe['trace_bytes']==len(files['natural.csv.gz']),
        'CRT keyboard trace binding differs')
    cpu,cases=projections(root/'natural.csv.gz',recipe)
    require(cases==manifest['cases'] and {item['category'] for item in cases}==set(range(6)) and
        sum(item['states'] for item in cases)==manifest['states']==75 and sha(cpu)==manifest['cpu_sha256'],
        'CRT keyboard projection differs')
    require(manifest['raw_memory_published'] is False and manifest['irq_eligibility_claim'] is False,
        'CRT keyboard evidence scope differs')
    print('crt_keyboard_fixture=ok cases=6 states=75 classifier_inputs=65536 raw_ram_files_verified=0 irq_eligibility_claim=0')
    return cpu,classification,pending


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu',type=Path);parser.add_argument('--classification',type=Path);parser.add_argument('--pending',type=Path)
    args=parser.parse_args();cpu,classification,pending=read_fixture()
    if args.cpu:
        args.cpu.write_bytes(cpu)
    if args.classification:
        args.classification.write_bytes(classification)
    if args.pending:
        args.pending.write_bytes(pending)
