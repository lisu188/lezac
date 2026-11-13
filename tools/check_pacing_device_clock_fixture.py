"""Authenticate original device-clock observations before producing replay inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from pacing_clock_probe.project import projections, clock_projection

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/pacing_device_clock'
MANIFEST_SHA='0d5b442afea976e629ce9e281a271a19b6133bb6509c3327c11273901e90c047'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(value,message):
    if not value:
        raise ValueError(message)


def read_fixture(root=FIXTURE):
    raw=(root/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen device-clock manifest differs')
    manifest=json.loads(raw)
    for path,digest in manifest['sources'].items():
        require(sha((ROOT/path).read_bytes())==digest,'Frozen device-clock source differs: '+path)
    require({item['name'] for item in manifest['files']}=={'r1.csv.gz','r1-recipe.json','r2.csv.gz','r2-recipe.json'},
        'Device-clock fixture domain differs')
    for item in manifest['files']:
        raw=(root/item['name']).read_bytes()
        require(len(raw)==item['bytes'] and sha(raw)==item['sha256'],'Frozen device-clock observation differs')
    cpus=[];clocks=[]
    for observation in manifest['observations']:
        run=observation['run']
        recipe=json.loads((root/(run+'-recipe.json')).read_bytes())
        trace=root/(run+'.csv.gz')
        require(recipe['status']=='observed' and recipe['passed'] is True and recipe['target_completed'] is True and
            recipe['validated_target_completed'] is True and recipe['canonical_assets_unchanged'] is True and
            recipe['child_exit_code']==0 and recipe['dosbox_sha256']=='b080dd7d6af89aa56f0d38bea764553432217f09462fed93cee5a4df95b810a8',
            'Device-clock capture profile differs')
        require(recipe['trace_sha256']==sha(trace.read_bytes()) and recipe['trace_bytes']==trace.stat().st_size,
            'Device-clock trace binding differs')
        for field,name in [('producer_sha256','capture.py'),('input_route_sha256','input_route.py'),('trace_parser_sha256','trace.py')]:
            require(recipe[field]==manifest['sources']['tools/pacing_clock_probe/'+name],'Device-clock producer binding differs')
        require(recipe['capture_contract_sha256']==manifest['sources']['tools/original_capture_contract.py'],
            'Device-clock canonical asset contract differs')
        for field,name in [('probe_sha256','lezac_work_probe.h'),('patch_sha256','dos_time_hook.patch'),
                           ('clock_patch_sha256','clock_hook.patch'),('clock_api_sha256','lezac_clock_observation.h')]:
            require(recipe['host_build'][field]==manifest['sources']['tools/pacing_clock_probe/'+name],
                'Device-clock observer binding differs')
        require(recipe['host_build']['callback_identity']=='direct original function pointer equality' and
            recipe['host_build']['guest_instruction_patches']==0 and recipe['host_build']['cpu_source_unchanged'] is True,
            'Device-clock host instrumentation differs')
        for name,digest in recipe['host_build']['device_fragment_hashes'].items():
            require(digest==manifest['sources']['tools/pacing_clock_probe/'+name],'Device-clock getter binding differs')
        cpu,cases=projections(trace,recipe)
        clock=clock_projection(trace,cases)
        require(len(cases)==1 and cases[0]['states']==observation['states'] and
            cases[0]['observed_irq_boundaries']==observation['irq_boundaries'] and sha(cpu)==observation['cpu_sha256'] and
            sha(clock)==observation['clock_sha256'],'Device-clock projection differs')
        cpus.append(cpu[12:]);clocks.append(clock[12:])
    cpu=b'LZFPAC01'+struct.pack('<I',2)+b''.join(cpus)
    clock=b'LZPDCL01'+struct.pack('<I',2)+b''.join(clocks)
    require(sha(cpu)==manifest['cpu_sha256'] and sha(clock)==manifest['clock_sha256'],'Combined device-clock projection differs')
    require(manifest['raw_memory_published'] is False and manifest['projection_is_not_execution_proof'] is True,
        'Device-clock evidence scope differs')
    print('pacing_device_clock_fixture=ok cases=2 states=132794 observed_irqs=2 raw_ram_files_verified=0 execution_proof=0')
    return cpu,clock


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu',type=Path)
    parser.add_argument('--clock',type=Path)
    args=parser.parse_args()
    cpu,clock=read_fixture()
    if args.cpu:
        args.cpu.write_bytes(cpu)
    if args.clock:
        args.clock.write_bytes(clock)
