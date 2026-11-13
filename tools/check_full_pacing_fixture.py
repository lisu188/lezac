"""Authenticate bounded full-pacing observations before publishing any replay input."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from full_pacing_probe.project import projections

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/full_pacing'
MANIFEST_SHA = 'b54ad24ff7959b58a3143057bbd14887693b9dbe0d50d998276d31236e1bf2e4'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_fixture(root=FIXTURE):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen pacing manifest differs')
    manifest = json.loads(raw)
    for name, digest in manifest['sources'].items():
        require(sha((ROOT / name).read_bytes()) == digest, 'Frozen pacing source differs: ' + name)
    require({item['name'] for item in manifest['files']} == {'full.bin.gz', 'gate.bin.gz', 'feedback.bin.gz',
        'oracle-manifest.json', 'natural.csv.gz', 'natural-recipe.json'}, 'Frozen pacing file domain differs')
    files = {}
    for item in manifest['files']:
        raw = (root / item['name']).read_bytes()
        require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'Frozen pacing observation differs')
        files[item['name']] = raw
    oracle = json.loads(files['oracle-manifest.json'])
    require(oracle['gate_inputs'] == 65536 and oracle['feedback_inputs'] == 327680 and len(oracle['cases']) == 15,
        'Controlled pacing domain differs')
    require(oracle['producer_sha256'] == manifest['sources']['tools/full_pacing_probe/oracle.py'] and
        oracle['mask_provider_sha256'] == manifest['sources']['tools/frame_display_probe/oracle.py'], 'Oracle source binding differs')
    controlled = {}
    for item in oracle['files']:
        compressed = files[item['name']]
        require(sha(compressed) == item['sha256'] and len(compressed) == item['bytes'], 'Oracle observation differs')
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw = stream.read(32 * 1024**2 + 1)
        require(len(raw) == item['projection_bytes'] and len(raw) <= 32 * 1024**2 and
            sha(raw) == item['projection_sha256'], 'Oracle projection differs')
        controlled[item['name']] = raw
    recipe = json.loads(files['natural-recipe.json'])
    require(recipe['status'] == 'observed' and recipe['passed'] is True and recipe['target_completed'] is True and
        recipe['validated_target_completed'] is True and recipe['child_exit_code'] == 0 and
        recipe['canonical_assets_unchanged'] is True and recipe['callback_boundary_probe'] is False,
        'Natural pacing completion or observation profile differs')
    require(recipe['trace_sha256'] == sha(files['natural.csv.gz']) and recipe['trace_bytes'] == len(files['natural.csv.gz']),
        'Natural pacing trace binding differs')
    cpu, cases = projections(root / 'natural.csv.gz', recipe)
    require(len(cases) == 1 and cases[0]['states'] == manifest['natural_states'] == 60408 and
        cases[0]['observed_irq_boundaries'] == manifest['natural_irq_boundaries'] == [42291] and
        sha(cpu) == manifest['natural_cpu_sha256'], 'Natural pacing CPU projection differs')
    require(manifest['raw_memory_published'] is False and manifest['natural_irq_eligibility_predicted'] is False and
        manifest['whole_game_parity'] is False, 'Pacing evidence scope differs')
    print('full_pacing_fixture=ok controlled_cases=15 gate_inputs=65536 feedback_inputs=327680 natural_states=60408 '
        'observed_irqs=1 irq_eligibility_claim=0 raw_ram_files_verified=0')
    return controlled['full.bin.gz'], controlled['gate.bin.gz'], controlled['feedback.bin.gz'], cpu


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('full', 'gate', 'feedback', 'cpu'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    outputs = read_fixture()
    for name, raw in zip(('full', 'gate', 'feedback', 'cpu'), outputs):
        path = getattr(args, name)
        if path:
            path.write_bytes(raw)
