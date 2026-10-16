"""Authenticate only the retained non-interrupted natural DOS-to-display controls."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

from frame_display_probe.project import projections

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_display_controls'
MANIFEST_SHA = '01d19c38085c29e5dcd692618e669b50b3b66395735614d45dadecbe0636fe61'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_fixture(root=FIXTURE):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen display-control manifest differs')
    manifest = json.loads(raw)
    require({item['name'] for item in manifest['files']} == {'r1.csv.gz', 'r1-recipe.json', 'r2.csv.gz', 'r2-recipe.json'},
        'Display-control file domain differs')
    files = {}
    for item in manifest['files']:
        raw = (root / item['name']).read_bytes()
        require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'Frozen display-control observation differs')
        files[item['name']] = raw
    cpus, clocks = [], []
    for observation in manifest['observations']:
        run = observation['run']
        recipe = json.loads(files[run + '-recipe.json'])
        with gzip.GzipFile(fileobj=io.BytesIO(files[run + '.csv.gz'])) as stream:
            raw = stream.read(8 * 1024**2 + 1)
        require(len(raw) < 8 * 1024**2 and raw.endswith(b'\nend\n'), 'Display-control trace bound or terminal differs')
        require(recipe['status'] == 'failed' and recipe['passed'] is False and recipe['target_completed'] is False and
            recipe['child_exit_code'] == 0 and recipe['canonical_assets_unchanged'] is True,
            'Failed interrupted target was relabeled')
        require(len(raw) == recipe['trace_bytes'] == observation['trace_bytes'] and
            sha(raw) == recipe['trace_sha256'] == observation['trace_sha256'], 'Display-control trace binding differs')
        require(recipe['dosbox_sha256'] == '794ba39dd57a0358049cd980c172ec5e91e8a921a114711ecd2e16525f77b0d1',
            'Pinned display observation host differs')
        for field, path in (
            ('producer_sha256', 'tools/frame_display_probe/capture.py'),
            ('input_route_sha256', 'tools/frame_display_probe/input_route.py'),
            ('capture_contract_sha256', 'tools/original_capture_contract.py'),
        ):
            require(recipe[field] == sha((ROOT / path).read_bytes()), 'Retained display capture source differs')
        for field, name in (
            ('probe_sha256', 'lezac_work_probe.h'), ('patch_sha256', 'dos_time_hook.patch'),
            ('clock_patch_sha256', 'clock_hook.patch'), ('clock_api_sha256', 'lezac_clock_observation.h'),
        ):
            require(recipe['host_build'][field] == sha((ROOT / 'tools/frame_display_probe' / name).read_bytes()),
                'Retained display observer source differs')
        cpu, clock, cases = projections(raw, recipe)
        require([case['call'] for case in cases] == [6] and len(cases[0]['states']) == 442 and
            not cases[0]['deliveries'], 'Display-control coverage differs')
        require(sha(cpu) == observation['cpu_sha256'] and sha(clock) == observation['clock_sha256'],
            'Display-control projection differs')
        cpus.append(cpu[12:]); clocks.append(clock[12:])
    cpu = b'LZFDSP01' + struct.pack('<I', 2) + b''.join(cpus)
    clock = b'LZPCLK01' + struct.pack('<I', 2) + b''.join(clocks)
    require(sha(cpu) == manifest['cpu_sha256'] and sha(clock) == manifest['clock_sha256'], 'Combined display controls differ')
    print('frame_display_controls=ok cases=2 states=884 observed_irqs=0 completed_interrupted_target_claim=0 raw_ram_files_verified=0')
    return cpu, clock


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu-projection', type=Path)
    parser.add_argument('--clock-projection', type=Path)
    args = parser.parse_args()
    cpu, clock = read_fixture()
    if args.cpu_projection:
        args.cpu_projection.write_bytes(cpu)
    if args.clock_projection:
        args.clock_projection.write_bytes(clock)
