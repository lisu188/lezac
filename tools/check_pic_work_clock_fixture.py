"""Verify and project only the exact retained PIC/DOS observation corpus."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from pic_clock_probe.project import projections

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/pic_work_clock'
MANIFEST_SHA = '01d4f041532b9573b649488e12217cadb1781224a3cd819277169ba8a15925e4'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_fixture(root=FIXTURE):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen PIC manifest differs')
    manifest = json.loads(raw)
    require({item['name'] for item in manifest['files']} == {'r2.csv.gz', 'r2-recipe.json'}, 'Fixture file domain differs')
    files = {}
    for item in manifest['files']:
        raw = (root / item['name']).read_bytes()
        require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'Frozen PIC observation differs')
        files[item['name']] = raw
    recipe = json.loads(files['r2-recipe.json'])
    with gzip.GzipFile(fileobj=io.BytesIO(files['r2.csv.gz'])) as stream:
        raw = stream.read(8 * 1024**2 + 1)
    require(len(raw) < 8 * 1024**2 and raw.endswith(b'\nend\n'), 'PIC trace bound or terminal differs')
    require(recipe['passed'] is True and recipe['target_completed'] is True and
        recipe['child_exit_code'] == 0 and recipe['canonical_assets_unchanged'] is True, 'Capture did not succeed')
    require(len(raw) == recipe['trace_bytes'] == manifest['trace_bytes'] and
        sha(raw) == recipe['trace_sha256'] == manifest['trace_sha256'], 'PIC trace binding differs')
    require(recipe['dosbox_sha256'] == '5e177a945ed1a6821e633fafcbdd8b9a9573b87864f079b9238a65c2ab62678c',
        'Pinned instrumented host differs')
    for field, path in (
        ('producer_sha256', 'tools/pic_clock_probe/capture.py'),
        ('input_route_sha256', 'tools/pic_clock_probe/input_route.py'),
        ('capture_contract_sha256', 'tools/original_capture_contract.py'),
    ):
        require(recipe[field] == sha((ROOT / path).read_bytes()), 'Retained capture source differs')
    cpu, clock, cases = projections(raw, recipe)
    require([case['call'] for case in cases] == [1, 2, 48] and
        sum(len(case['states']) for case in cases) == 1014 and
        [case['deliveries'] for case in cases] == [[], [], [68]], 'PIC observation coverage differs')
    print('pic_work_clock_fixture=ok cases=3 states=1014 natural_irq_boundaries=1 raw_ram_files_verified=0')
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
