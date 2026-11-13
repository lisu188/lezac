"""Authenticate the original controlled waiting-prepass map/cursor endpoints."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/waiting_placement'
MANIFEST_SHA = '3b08b01dddb5d14d23e07a69112567f189cc588809175a669ab8f624c5e75752'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def read_fixture(root=ROOT, fixture=FIXTURE):
    manifest_raw = (fixture / 'manifest.json').read_bytes()
    if sha(manifest_raw) != MANIFEST_SHA:
        raise ValueError('Frozen waiting-placement manifest differs')
    manifest = json.loads(manifest_raw)
    for key, name in [('producer_sha256', 'tools/waiting_placement_oracle.py'),
                      ('shared_oracle_sha256', 'tools/frame_camera_oracle.py'),
                      ('executable_sha256', 'LEZAC.EXE')]:
        if sha((root / name).read_bytes()) != manifest[key]:
            raise ValueError('Waiting-placement source differs: ' + name)
    if manifest['schema'] != 'lezac-controlled-waiting-map-v1' or manifest['cases'] != 320 or \
            manifest['map_reads'] != 1035 or manifest['original_code_bytes_verified'] != 43552 or \
            manifest['unicorn_version'] != '2.1.4' or manifest['unicorn_library_sha256'] != \
            'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' or \
            not all(manifest[k] is True for k in ('actual_library_mapping_verified',
                'complete_memory_observer_control', 'controlled_input', 'no_expiry_path_only')) or \
            not all(manifest[k] is False for k in ('natural_heap_initialization_proven',
                'raw_memory_published', 'full_frame_claim', 'production_app_comparison', 'whole_game_parity')) or \
            not all(type(manifest[k]) is int and manifest[k] == 0 for k in
                ('instruction_patches', 'calls_stubbed', 'interrupts_delivered', 'hardware_io')):
        raise ValueError('Waiting-placement evidence scope differs')
    raw = (fixture / 'oracle.bin').read_bytes()
    if len(raw) != 11532 or len(raw) != manifest['projection_bytes'] or sha(raw) != manifest['projection_sha256']:
        raise ValueError('Frozen waiting-placement endpoints differ')
    return raw


if __name__ == '__main__':
    value = read_fixture()
    print(json.dumps(dict(status='passed', cases=320, bytes=len(value), sha256=sha(value),
                          natural=False, whole_game_parity=False), sort_keys=True))
