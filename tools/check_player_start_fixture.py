"""Authenticate controlled original player-start traces and their App projection."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/player_start'
MANIFEST_SHA = 'f1842ce0c4dd2d01227db976237977c726767934a42ff0561bc41de6917ec2b7'
sha = lambda value: hashlib.sha256(value).hexdigest()


def read_fixture(root=ROOT, fixture=FIXTURE):
    raw = (fixture / 'manifest.json').read_bytes()
    if sha(raw) != MANIFEST_SHA:
        raise ValueError('Frozen player-start manifest differs')
    manifest = json.loads(raw)
    for key, name in [('producer_sha256', 'tools/player_start_oracle.py'),
                      ('shared_oracle_sha256', 'tools/frame_camera_oracle.py'),
                      ('executable_sha256', 'LEZAC.EXE')]:
        if sha((root / name).read_bytes()) != manifest[key]:
            raise ValueError('Player-start source differs: ' + name)
    if manifest['schema'] != 'lezac-controlled-player-start-v1' or manifest['cases'] != 1043 or \
            manifest['app_cases'] != 1040 or manifest['register_states'] != 59867 or \
            manifest['writes'] != 14053 or manifest['runtime_errors'] != 3 or \
            manifest['original_code_bytes_verified'] != 43552 or manifest['unicorn_version'] != '2.1.4' or \
            manifest['unicorn_library_sha256'] != 'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' or \
            not all(manifest[k] is True for k in ('actual_library_mapping_verified',
                'controlled_initial_memory', 'complete_memory_observer_control',
                'ordered_writes_reconstruct_full_memory', 'endpoint_all_flags_compared')) or \
            not all(manifest[k] is False for k in ('natural_capture', 'raw_memory_published',
                'production_app_comparison', 'full_frame_claim', 'whole_game_parity', 'trace_arithmetic_flags_compared')) or \
            not all(type(manifest[k]) is int and manifest[k] == 0 for k in
                ('instruction_patches', 'calls_stubbed', 'interrupts_delivered', 'hardware_io')):
        raise ValueError('Player-start evidence scope differs')
    compressed = (fixture / 'oracle.bin.gz').read_bytes()
    if len(compressed) != manifest['compressed_bytes'] or sha(compressed) != manifest['compressed_sha256']:
        raise ValueError('Frozen compressed player-start trace differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        decoded = stream.read(1985163)
    if len(decoded) != 1985162 or len(decoded) != manifest['projection_bytes'] or sha(decoded) != manifest['projection_sha256']:
        raise ValueError('Frozen decoded player-start trace differs')
    app = (fixture / 'app.bin').read_bytes()
    if len(app) != 17720 or len(app) != manifest['app_bytes'] or sha(app) != manifest['app_sha256']:
        raise ValueError('Frozen player-start App projection differs')
    return decoded, app


def run(root=ROOT, fixture=FIXTURE, out=None):
    decoded, app = read_fixture(root, fixture)
    if out:
        if out.exists():
            if out.read_bytes() != decoded:
                raise ValueError('Existing player-start export differs; preserved')
        else:
            with out.open('xb') as stream:
                stream.write(decoded)
    return dict(status='passed', cases=1043, app_cases=1040, bytes=len(decoded),
                app_bytes=len(app), full_frame_claim=False, whole_game_parity=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(out=args.out), sort_keys=True))
