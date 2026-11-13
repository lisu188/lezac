"""Authenticate and non-destructively export the continuous post-render corpus."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_prefix'
MANIFEST_SHA = 'cc2df2a76271145e8c743b4b790a31ba8333d1e441e14e3fe7e652cda068df43'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read_fixture(root=ROOT, fixture=FIXTURE):
    raw = (fixture / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen frame-prefix manifest differs')
    m = json.loads(raw)
    for name, pin in m['asset_sha256'].items():
        require(sha((root / name).read_bytes()) == pin, 'Prefix canonical source differs: ' + name)
    for name, pin in m['dependency_sha256'].items():
        require(sha((root / 'tools' / name).read_bytes()) == pin, 'Prefix canonical source differs: ' + name)
    require(m['schema'] == 'lezac-controlled-post-render-prefix-v1' and
        (m['cases'], m['completed'], m['end_run_handoffs'], m['runtime_errors']) == (238, 228, 2, 8) and
        (m['register_states'], m['ordered_writes'], len(m['executed_instructions'])) == (378271, 142437, 836) and
        (m['entry_ip'], m['endpoint_ip'], m['spawner_profiles']) == (0x7a57, 0x7ebb, 151) and
        m['original_code_bytes_verified'] == 43552 and m['trace_storage'] == 'register-columns-v1' and
        m['rep_trace_policy'] == 'raw-unicorn-transfer-and-zero-count-observations' and
        m['unicorn_version'] == '2.1.4' and m['unicorn_library_sha256'] ==
        'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        all(m[k] is True for k in ('actual_library_mapping_verified', 'full_memory_observer_control',
            'ordered_writes_reconstruct_memory', 'controlled_initial_memory',
            'source_bytes_rechecked_before_export', 'endpoint_all_flags_compared')) and
        all(m[k] is False for k in ('raw_memory_published', 'natural_capture', 'end_run_ui_executed',
            'active_prefix_executed', 'trace_arithmetic_flags_compared', 'work_clock_claim',
            'full_frame_claim', 'whole_game_parity')) and
        all(type(m[k]) is int and m[k] == 0 for k in ('instruction_patches', 'calls_stubbed',
            'interrupts_delivered', 'hardware_io')), 'Frame-prefix evidence scope differs')
    compressed = (fixture / 'oracle.bin.gz').read_bytes()
    require(len(compressed) == 2043589 == m['compressed_bytes'] and sha(compressed) == m['compressed_sha256'],
            'Frozen compressed frame-prefix corpus differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:
        decoded = source.read(30982064)
    require(len(decoded) == 30982063 == m['projection_bytes'] and sha(decoded) == m['projection_sha256'],
            'Frozen decoded frame-prefix corpus differs')
    return decoded


def run(out=None, root=ROOT, fixture=FIXTURE):
    decoded = read_fixture(root, fixture)
    if out is not None:
        require(not out.is_symlink(), 'Existing frame-prefix export link preserved')
        if out.exists():
            require(out.is_file() and out.stat().st_size == len(decoded) and out.read_bytes() == decoded,
                    'Existing frame-prefix export differs; preserved')
        else:
            with out.open('xb') as target:
                target.write(decoded)
    return dict(status='passed', cases=238, bytes=len(decoded), sha256=sha(decoded),
                active_prefix_executed=False, full_frame_claim=False, work_clock_claim=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.out), sort_keys=True))
