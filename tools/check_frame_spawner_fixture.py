"""Authenticate and non-destructively export the controlled original spawner corpus."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_spawner'
MANIFEST_SHA = 'd977e00bd3755b31832634fbc213977fa9da8c09c5f4cf8c531a72659decc7d2'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT, fixture=FIXTURE):
    raw = (fixture / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen spawner manifest differs')
    manifest = json.loads(raw)
    for field, name in [('producer_sha256', 'tools/frame_spawner_oracle.py'),
                        ('shared_oracle_sha256', 'tools/frame_camera_oracle.py'),
                        ('executable_sha256', 'LEZAC.EXE')]:
        require(sha((root / name).read_bytes()) == manifest[field], 'Spawner source differs: ' + name)
    require(manifest['schema'] == 'lezac-controlled-spawner-frame-v1' and
        manifest['cases'] == 151 and manifest['register_states'] == 61987 and manifest['runtime_errors'] == 2 and
        len(manifest['executed_instructions']) == 344 and manifest['unicorn_version'] == '2.1.4' and
        manifest['unicorn_library_sha256'] == 'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        all(manifest[k] is True for k in ('actual_library_mapping_verified', 'controlled_initial_memory',
            'full_memory_observer_control', 'endpoint_all_flags_compared')) and
        all(manifest[k] is False for k in ('raw_memory_published', 'natural_capture', 'full_frame_claim',
            'work_clock_claim', 'trace_arithmetic_flags_compared')) and
        all(type(manifest[k]) is int and manifest[k] == 0 for k in ('instruction_patches', 'calls_stubbed',
            'interrupts_delivered', 'hardware_io')), 'Spawner evidence profile differs')
    compressed = (fixture / 'oracle.bin.gz').read_bytes()
    require(len(compressed) == 291067 == manifest['compressed_bytes'] and
            sha(compressed) == manifest['compressed_sha256'], 'Frozen compressed spawner trace differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:
        decoded = source.read(2436581)
    require(len(decoded) == 2436580 == manifest['projection_bytes'] and
            sha(decoded) == manifest['projection_sha256'], 'Frozen decoded spawner trace differs')
    return decoded


def run(out=None, root=ROOT, fixture=FIXTURE):
    decoded = read_fixture(root, fixture)
    if out is not None:
        require(not out.is_symlink(), 'Existing spawner export link preserved')
        if out.exists():
            require(out.is_file() and out.stat().st_size == len(decoded) and out.read_bytes() == decoded,
                    'Existing spawner export differs; preserved')
        else:
            with out.open('xb') as output:
                output.write(decoded)
    return dict(status='passed', cases=151, bytes=len(decoded), sha256=sha(decoded),
                full_frame_claim=False, work_clock_claim=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.out), sort_keys=True))
