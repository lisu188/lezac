"""Authenticate and non-destructively export the complete ammunition HUD corpus."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/ammo_hud'
MANIFEST_SHA = 'd5f06c117e6bd799cdf42a955734cd3142b9f9adea5a51aca05b0de969718278'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT, fixture=FIXTURE):
    raw = (fixture / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen ammunition manifest differs')
    m = json.loads(raw)
    for field, name in [('producer_sha256', 'tools/ammo_hud_oracle.py'),
                        ('shared_oracle_sha256', 'tools/frame_camera_oracle.py'),
                        ('executable_sha256', 'LEZAC.EXE'), ('tile_atlas_sha256', 'CARO.CAR'),
                        ('sprite_atlas_sha256', 'BOMOMIMK.SPR')]:
        require(sha((root / name).read_bytes()) == m[field], 'Ammunition source differs: ' + name)
    require(m['schema'] == 'lezac-controlled-ammunition-hud-v1' and m['cases'] == 2226 and
        m['weapon_selection_values'] == [1, 2, 3, 4] and m['descriptor_indexing'] == 'one-based' and
        m['inventory_bases'] == [0x1b6c, 0x1b70] and
        m['register_states'] == 2829590 and m['runtime_errors'] == 7 and m['ordered_writes'] == 869313 and
        m['shipped_cases'] == 2048 and m['window_sprite_cases'] == 32 and len(m['executed_instructions']) == 220 and
        m['unicorn_version'] == '2.1.4' and m['unicorn_library_sha256'] ==
        'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        m['rep_trace_policy'] == 'raw-unicorn-transfer-and-zero-count-observations' and
        m['trace_storage'] == 'register-columns-v1' and
        all(m[k] is True for k in ('actual_library_mapping_verified', 'controlled_initial_memory',
            'full_memory_observer_control', 'endpoint_all_flags_compared',
            'source_bytes_rechecked_before_export', 'canonical_assets_rechecked_before_export')) and
        all(m[k] is False for k in ('raw_memory_published', 'natural_capture', 'full_frame_claim',
            'work_clock_claim', 'trace_arithmetic_flags_compared')) and
        all(type(m[k]) is int and m[k] == 0 for k in ('instruction_patches', 'calls_stubbed',
            'interrupts_delivered', 'hardware_io')), 'Ammunition evidence profile differs')
    app = (fixture / 'app.bin').read_bytes()
    require(len(app) == 18444 == m['app_bytes'] and sha(app) == m['app_sha256'], 'Frozen ammunition App fixture differs')
    compressed = (fixture / 'oracle.bin.gz').read_bytes()
    require(len(compressed) == 6724708 == m['compressed_bytes'] and sha(compressed) == m['compressed_sha256'],
            'Frozen compressed ammunition trace differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:
        decoded = source.read(93486962)
    require(len(decoded) == 93486961 == m['projection_bytes'] and sha(decoded) == m['projection_sha256'],
            'Frozen decoded ammunition trace differs')
    return decoded


def run(out=None, root=ROOT, fixture=FIXTURE):
    decoded = read_fixture(root, fixture)
    if out is not None:
        require(not out.is_symlink(), 'Existing ammunition export link preserved')
        if out.exists():
            require(out.is_file() and out.stat().st_size == len(decoded) and out.read_bytes() == decoded,
                    'Existing ammunition export differs; preserved')
        else:
            with out.open('xb') as output:
                output.write(decoded)
    return dict(status='passed', cases=2226, bytes=len(decoded), sha256=sha(decoded),
                full_frame_claim=False, work_clock_claim=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.out), sort_keys=True))
