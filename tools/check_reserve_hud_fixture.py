"""Authenticate and non-destructively export the controlled original reserve HUD corpus."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/reserve_hud'
MANIFEST_SHA = 'bd16b21a729eefa28d8d45786c409cf525c8c29181506f5c0861a64f106420f3'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT, fixture=FIXTURE):
    raw = (fixture / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen reserve HUD manifest differs')
    manifest = json.loads(raw)
    for field, name in [('producer_sha256', 'tools/reserve_hud_oracle.py'),
                        ('shared_oracle_sha256', 'tools/frame_camera_oracle.py'),
                        ('executable_sha256', 'LEZAC.EXE'), ('tile_atlas_sha256', 'CARO.CAR')]:
        require(sha((root / name).read_bytes()) == manifest[field], 'Reserve HUD source differs: ' + name)
    require(manifest['schema'] == 'lezac-controlled-reserve-hud-v1' and
        manifest['cases'] == 756 and manifest['register_states'] == 241599 and manifest['runtime_errors'] == 3 and
        manifest['ordered_writes'] == 104976 and manifest['rep_zero_observations'] == 18072 and
        manifest['shipped_glyph_cases'] == 512 and len(manifest['executed_instructions']) == 58 and
        manifest['unicorn_version'] == '2.1.4' and
        manifest['unicorn_library_sha256'] == 'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        manifest['rep_trace_policy'] == 'raw-unicorn-transfer-and-zero-count-observations' and
        all(manifest[k] is True for k in ('actual_library_mapping_verified', 'controlled_initial_memory',
            'full_memory_observer_control', 'endpoint_all_flags_compared')) and
        all(manifest[k] is False for k in ('raw_memory_published', 'natural_capture', 'full_frame_claim',
            'work_clock_claim', 'trace_arithmetic_flags_compared')) and
        all(type(manifest[k]) is int and manifest[k] == 0 for k in ('instruction_patches', 'calls_stubbed',
            'interrupts_delivered', 'hardware_io')), 'Reserve HUD evidence profile differs')
    compressed = (fixture / 'oracle.bin.gz').read_bytes()
    require(len(compressed) == 604667 == manifest['compressed_bytes'] and
            sha(compressed) == manifest['compressed_sha256'], 'Frozen compressed reserve HUD differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:
        decoded = source.read(8571483)
    require(len(decoded) == 8571482 == manifest['projection_bytes'] and
            sha(decoded) == manifest['projection_sha256'], 'Frozen decoded reserve HUD differs')
    return decoded


def run(out=None, root=ROOT, fixture=FIXTURE):
    decoded = read_fixture(root, fixture)
    if out is not None:
        require(not out.is_symlink(), 'Existing reserve HUD export link preserved')
        if out.exists():
            require(out.is_file() and out.stat().st_size == len(decoded) and out.read_bytes() == decoded,
                    'Existing reserve HUD export differs; preserved')
        else:
            with out.open('xb') as output:
                output.write(decoded)
    return dict(status='passed', cases=756, bytes=len(decoded), sha256=sha(decoded),
                full_frame_claim=False, work_clock_claim=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.out), sort_keys=True))
