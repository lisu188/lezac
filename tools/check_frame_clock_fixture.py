"""Authenticate and project the exact natural DOS-to-foreground observation corpus."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from frame_clock_probe.project import projections

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_clock'
MANIFEST_SHA = '26c9cd5a2ee07d1d61a3da7dd17dd93e30056466ed484324ee9e67dfd0433c27'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_fixture(root=FIXTURE):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen frame-clock manifest differs')
    manifest = json.loads(raw)
    require({item['name'] for item in manifest['files']} == {'r3.csv.gz', 'r3-recipe.json'}, 'Fixture file domain differs')
    files = {}
    for item in manifest['files']:
        raw = (root / item['name']).read_bytes()
        require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'Frozen frame-clock observation differs')
        files[item['name']] = raw
    recipe = json.loads(files['r3-recipe.json'])
    with gzip.GzipFile(fileobj=io.BytesIO(files['r3.csv.gz'])) as stream:
        raw = stream.read(8 * 1024**2 + 1)
    require(len(raw) < 8 * 1024**2 and raw.endswith(b'\nend\n'), 'Frame-clock trace bound or terminal differs')
    require(recipe['status'] == 'observed' and recipe['passed'] is True and recipe['target_completed'] is True and
        recipe['child_exit_code'] == 0 and recipe['canonical_assets_unchanged'] is True, 'Capture did not succeed')
    require(len(raw) == recipe['trace_bytes'] == manifest['trace_bytes'] and
        sha(raw) == recipe['trace_sha256'] == manifest['trace_sha256'], 'Frame-clock trace binding differs')
    require(recipe['dosbox_sha256'] == 'f86adc819502d49f0cf5784d314c5122b461fc9eca38ab24e02d2013d39cebd3',
        'Pinned instrumented host differs')
    for field, path in (
        ('producer_sha256', 'tools/frame_clock_probe/capture.py'),
        ('input_route_sha256', 'tools/frame_clock_probe/input_route.py'),
        ('capture_contract_sha256', 'tools/original_capture_contract.py'),
    ):
        require(recipe[field] == sha((ROOT / path).read_bytes()), 'Retained capture source differs')
    for field, name in (
        ('probe_sha256', 'lezac_work_probe.h'),
        ('patch_sha256', 'dos_time_hook.patch'),
        ('clock_patch_sha256', 'clock_hook.patch'),
        ('clock_api_sha256', 'lezac_clock_observation.h'),
    ):
        require(recipe['host_build'][field] == sha((ROOT / 'tools/frame_clock_probe' / name).read_bytes()),
            'Retained observer source differs')
    cpu, clock, cases = projections(raw, recipe)
    require([case['call'] for case in cases] == [6, 308] and
        [len(case['states']) for case in cases] == [355, 391] and
        [case['deliveries'] for case in cases] == [[], [167]], 'Frame-clock observation coverage differs')
    require(sha(cpu) == '02e59dc8f2661abe99ad8ff95c3546a25a5a0552debab1e84eaa3bca644b79cf' and
        sha(clock) == 'b3dad3b7def009f5cbdc619776cefda131adfea74f575f119abb91a150d2327a',
        'Frame-clock projection differs')
    print('frame_clock_fixture=ok cases=2 states=746 natural_irq_boundaries=1 raw_ram_files_verified=0 post_dos_natural_irq_claim=0')
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
