"""Authenticate and preserve exports of the composed waiting-prepass evidence."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_waiting'
MANIFEST_SHA = 'ca5582df8411f7a83e19d593465b180e88e548c288b3006cd57ff40d77ab8b19'
APP_SHA = '07946b266e968b92e78180f5f2e160eb37b256b6df53c534974101056f0242bd'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def app_projection(raw):
    require(raw[:12] == b'LZWAIT01' + struct.pack('<I', 238), 'Waiting App projection input differs')
    base = 0x1aa20
    offsets = [0x79ca, 0x79a3, 0x79e6, 0x79e7, 0x79ea, 0x79eb, 0x1b7b, 0x1b80,
        0x1b74, 0x1b75, 0x1b76, 0x1b77, *range(0x1b6c, 0x1b74),
        0x1b98, 0x1b99, 0x1bbe, 0x1bbf]
    watched = {base + value for value in offsets}
    at, rows = 12, []
    for index in range(238):
        case, outcome = struct.unpack_from('<II', raw, at)
        require(case == index, 'Waiting App projection case order differs')
        at += 68
        count, = struct.unpack_from('<I', raw, at)
        at += 4
        initial = {}
        for _ in range(count):
            address, length = struct.unpack_from('<II', raw, at)
            at += 8
            for target in watched:
                if address <= target < address + length:
                    initial[target] = raw[at + target - address]
            at += length
        require(watched == initial.keys(), 'Waiting App projection seed field missing')
        states, = struct.unpack_from('<I', raw, at)
        at += 4 + states * 30
        count, = struct.unpack_from('<I', raw, at)
        at += 4
        final = dict(initial)
        for _ in range(count):
            address, size, value = struct.unpack_from('<IBH', raw, at)
            at += 7
            for byte in range(size):
                if address + byte in watched:
                    final[address + byte] = (value >> (byte * 8)) & 255
        before = lambda offset: initial[base + offset]
        after = lambda offset: final[base + offset]
        active = 164 <= index < 204
        waiting = (128 <= index < 164 and before(0x1b7b) <= 1 and before(0x1b80) <= 1) or index >= 222
        if not (active or waiting):
            continue
        require(outcome == 0 and (before(0x79e6), before(0x79e7)) == ((1, 1) if active else (2, 2)),
                'Waiting App projection admitted an incompatible stage')
        require(1 <= before(0x1b74) <= 4 and 1 <= before(0x1b75) <= 4,
                'Waiting App projection weapon is not one-based')
        row = bytearray(64)
        struct.pack_into('<H', row, 0, index)
        row[2:17] = bytes((before(0x79ca), before(0x79e6), before(0x79e7), before(0x1b7b),
            before(0x1b80), before(0x1b74) - 1, before(0x1b75) - 1, before(0x1b76), before(0x1b77),
            before(0x79a3), after(0x79a3), before(0x79ea), before(0x79eb), after(0x79ea), after(0x79eb)))
        row[17:21] = bytes(before(offset) for offset in (0x1b98, 0x1b99, 0x1bbe, 0x1bbf))
        row[21:25] = bytes(after(offset) for offset in (0x1b98, 0x1b99, 0x1bbe, 0x1bbf))
        row[25:33] = bytes(before(offset) for offset in range(0x1b6c, 0x1b74))
        row[33:41] = bytes(after(offset) for offset in range(0x1b6c, 0x1b74))
        row[41:47] = bytes(after(offset) for offset in (0x1b76, 0x1b77, 0x79e6, 0x79e7, 0x1b7b, 0x1b80))
        rows.append(row)
    require(at == len(raw) and len(rows) == 68, 'Waiting App projection tail differs')
    return b'LZWFAP01' + struct.pack('<I', len(rows)) + b''.join(rows)


def read_fixture(root=ROOT, fixture=FIXTURE):
    raw = (fixture / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen waiting manifest differs')
    m = json.loads(raw)
    for name, pin in m['asset_sha256'].items():
        require(sha((root / name).read_bytes()) == pin, 'Waiting canonical source differs: ' + name)
    for name, pin in m['dependency_sha256'].items():
        require(sha((root / 'tools' / name).read_bytes()) == pin, 'Waiting canonical source differs: ' + name)
    require(m['schema'] == 'lezac-controlled-waiting-frame-v1' and
        m['weapon_selection_values'] == [1, 2, 3, 4] and m['descriptor_indexing'] == 'one-based' and
        m['inventory_bases'] == [0x1b6c, 0x1b70] and
        (m['cases'], m['completed'], m['end_run_handoffs'], m['runtime_errors']) == (238, 230, 2, 6) and
        (m['register_states'], m['ordered_writes'], len(m['executed_instructions'])) == (291350, 121856, 502) and
        len([ip for cs, ip in m['executed_instructions'] if cs == 0x1000 and 0x7c3d <= ip < 0x7ebb]) == 191 and
        m['original_code_bytes_verified'] == 43552 and m['trace_storage'] == 'register-columns-v1' and
        m['rep_trace_policy'] == 'raw-unicorn-transfer-and-zero-count-observations' and
        m['unicorn_version'] == '2.1.4' and m['unicorn_library_sha256'] ==
        'ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c' and
        all(m[k] is True for k in ('actual_library_mapping_verified', 'full_memory_observer_control',
            'ordered_writes_reconstruct_memory', 'controlled_initial_memory',
            'source_bytes_rechecked_before_export', 'endpoint_all_flags_compared')) and
        all(m[k] is False for k in ('raw_memory_published', 'natural_capture', 'end_run_ui_executed',
            'trace_arithmetic_flags_compared', 'work_clock_claim', 'full_frame_claim', 'whole_game_parity')) and
        all(type(m[k]) is int and m[k] == 0 for k in ('instruction_patches', 'calls_stubbed',
            'interrupts_delivered', 'hardware_io')), 'Waiting evidence scope differs')
    compressed = (fixture / 'oracle.bin.gz').read_bytes()
    require(len(compressed) == 1640911 == m['compressed_bytes'] and sha(compressed) == m['compressed_sha256'],
            'Frozen compressed waiting corpus differs')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:
        decoded = source.read(27514429)
    require(len(decoded) == 27514428 == m['projection_bytes'] and sha(decoded) == m['projection_sha256'],
            'Frozen decoded waiting corpus differs')
    app = (fixture / 'app.bin').read_bytes()
    require(len(app) == 4364 and sha(app) == APP_SHA and app == app_projection(decoded),
            'Frozen waiting App projection differs')
    return decoded


def run(out=None, root=ROOT, fixture=FIXTURE):
    decoded = read_fixture(root, fixture)
    if out is not None:
        require(not out.is_symlink(), 'Existing waiting export link preserved')
        if out.exists():
            require(out.is_file() and out.stat().st_size == len(decoded) and out.read_bytes() == decoded,
                    'Existing waiting export differs; preserved')
        else:
            with out.open('xb') as target:
                target.write(decoded)
    return dict(status='passed', cases=238, bytes=len(decoded), sha256=sha(decoded),
                end_run_ui=False, full_frame_claim=False, work_clock_claim=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.out), sort_keys=True))
