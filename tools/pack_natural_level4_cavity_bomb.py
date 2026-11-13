"""Promote compact original-only observations; never copy private DS or PNG files."""
import argparse
import copy
import gzip
import hashlib
import io
from pathlib import Path, PurePosixPath
import struct
import zipfile

import bomb_state_projection as bombs
import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original
from original_capture_contract import read_canonical_assets

ROOT = Path(__file__).resolve().parents[1]
FIRST, LAST = 13700, 14700
AUDIT_SHA = '5c314ab6ae18b46cd4df53fc7a0e8de0ce923ed6334d8360ac6ee8d84d30fa1a'
REFERENCE_SHA = '02fefbd3d55a164e7155ac535c16f023de6a265a7010fe4d5b2f20fad52b4c70'
CAPTURE_SHA = '9a53099388a013a3322584e486498fc097e3d444aa5459877012b6a3dd369c25'
OBSERVER_SHA = 'dd7b7782cdfe7a0e20fac25878b34cc1efa080412a9249f36df999488dc8f344'
ROUTE_SHA = 'a58a48cd67942a1ba49323cb7f65394acff1d9b0a5ef8928cc398db2375cbc2b'
CLAIMS = dict(original_fidelity_claim=False, whole_game_fidelity_claim=False, level4_completion_claim=False,
    all_actor_fields_compared=False, full_actor_record_equivalence=False, full_frame_claim=False,
    manual_input_claim=False, wall_clock_claim=False)
require = fidelity.require
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def compressed(raw):
    buffer = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=buffer, mode='wb', mtime=0) as stream:
        stream.write(raw)
    packed = buffer.getvalue()
    require(gzip.decompress(packed) == raw, 'promoted gzip readback differs')
    return packed


def pack(private, out):
    native = private / 'level4-t343-native-capture'
    fixture = out / 'tests/fixtures/natural_level4_cavity_bomb'
    evidence = out / 'docs/recovery/evidence/natural_level4_cavity_bomb_20261104'
    require(not fixture.exists() and not evidence.exists(), 'promotion requires fresh output directories')
    audit_raw = (private / 'level4-t344-first-blast-original-audit.json').read_bytes()
    reference_raw = (private / 'level4-t344-first-blast-original-reference.jsonl.gz').read_bytes()
    capture_raw = (native / 'report.json').read_bytes()
    require((sha(audit_raw), sha(reference_raw), sha(capture_raw)) ==
        (AUDIT_SHA, REFERENCE_SHA, CAPTURE_SHA), 'audited original source identity differs')
    audit, capture = map(lambda raw: fidelity.strict_json(raw.decode()), (audit_raw, capture_raw))
    require(audit['status'] == 'original_only_audit_passed' and audit['cpp_expectations_used'] is False and
        audit['capture_request_complete'] is True and audit['observed_complete_window'] == [FIRST, LAST] and
        (audit['frames'], audit['boundaries'], audit['compressed_members']) == (1001, 2002, 4016) and
        all(audit[key] == 0 for key in ('full_private_member_byte_differences', 'independent_ds_redecode_differences',
            'compressed_member_readback_differences', 'original_png_receipt_differences')),
        'original audit is incomplete or has differences')
    require(capture['status'] == 'original_continuation_observed' and all(capture[key] is True for key in
        ('owned_child_terminal', 'base_hooks_restored', 'extra_hooks_restored', 'protected_inputs_preserved')) and
        capture['observer_sha256'] == OBSERVER_SHA and capture['gameplay_state_injections'] is False,
        'original capture closure differs')
    records = [
        fidelity.strict_json(line) for line in (native / 'lossless-retention.jsonl').read_text().splitlines()]
    require(len(records) == len({row['path'] for row in records}) == 4016, 'original retention inventory differs')
    catalog = {row['path']: row for row in records}
    readback = []
    for row in records:
        path = fidelity.safe_file(native, row['path'])
        packed = path.read_bytes()
        decoded = gzip.decompress(packed)
        require((len(packed), sha(packed)) == (row['encoded_bytes'], row['encoded_sha256']) and
            (len(decoded), sha(decoded)) == (row['source_bytes'], row['source_sha256']) and row['readback_equal'] is True,
            'complete private member readback differs: ' + path.name)
        readback.append(dict(path=path.name, encoded_bytes=len(packed), encoded_sha256=sha(packed),
            source_bytes=len(decoded), source_sha256=sha(decoded), complete_byte_readback=True))
    source_rows = [fidelity.strict_json(line.decode()) for line in gzip.decompress(reference_raw).splitlines()]
    require(len(source_rows) == 2004 and source_rows[0]['expected_bytes_source'] == 'original_only' and
        source_rows[0]['cpp_expectations_used'] is False, 'original reference role differs')
    prior_raw = (native / 'verified-prefix-reference.jsonl.gz').read_bytes()
    prior_rows = handoff.load(native / 'verified-prefix-reference.jsonl.gz')
    require(sha(prior_raw) == capture['previous_original_reference_sha256'] and
        prior_rows[0]['expected_bytes_source'] == 'original_only' and prior_rows[0]['cpp_expectations_used'] is False and
        prior_rows[-3:-1] == source_rows[1:3], 'previous original overlap source differs')
    live = {(row['tick'], row['phase']): row for row in capture['checkpoints']}
    audited = {(row['tick'], row['phase']): row for row in audit['records']}
    rows, bomb_boundaries = [], 0
    for source in source_rows[1:-1]:
        row = copy.deepcopy(source)
        tick, phase = row['index'], row['phase']
        ds_name, boundary_name = f'ds-{tick}-{phase}.bin.gz', f'boundary-{tick}-{phase}.json.gz'
        data = gzip.decompress((native / ds_name).read_bytes())
        observed = fidelity.strict_json(gzip.decompress((native / boundary_name).read_bytes()).decode())
        require(len(data) == 65536 and sha(data) == catalog[ds_name]['source_sha256'] ==
            audited[tick, phase]['ds_sha256'] == observed['ds_sha256'] == live[tick, phase]['ds_sha256'] and
            struct.unpack_from('<H', data, 0x78c2)[0] == tick - 1623,
            'original DS identity or frame differs')
        require(row['projection'] == observed['projection'] and
            sha(original.json_bytes(row['projection'])) == audited[tick, phase]['projection_sha256'],
            'original projection receipt differs')
        row['projection']['bombs'] = bombs.native_bombs(data)
        row['native_ds_sha256'] = sha(data)
        bomb_boundaries += bool(row['projection']['bombs'])
        if phase == 'present':
            png = fidelity.safe_file(native, f'original-level4-t298-{tick}-present.png').read_bytes()
            require(sha(png) == live[tick, phase]['png_sha256'] and
                row['rgb_sha256'] == live[tick, phase]['rgb_sha256'], 'original PNG receipt differs')
        rows.append(row)
    require(bomb_boundaries == 118, 'original live-bomb coverage differs')
    route = (native / 'route.txt').read_bytes()
    require(sha(route) == ROUTE_SHA, 'promoted ordinary route differs')
    assets = read_canonical_assets(ROOT)
    header = dict(kind='header', schema='lezac-natural-level4-cavity-bomb-v1', first_tick=FIRST,
        last_tick=LAST, frames=1001, boundaries=2002, dimensions=[100, 58], native_frame_offset=1623,
        expected_bytes_source='original_only', cpp_expectations_used=False, gameplay_state_injections=False,
        raw_ds_snapshots_published=False, screenshots_published=False, audio='dummy', completed_levels=[1, 2, 3],
        entered_level=4, normalized_control_bank_inputs=True, initial_rng_controlled=True,
        route_sha256=ROUTE_SHA, assets={name: sha(assets[name]) for name in fidelity.ASSETS},
        bomb_fields=list(bombs.FIELDS), bomb_present_boundaries=118, **CLAIMS)
    payload = b''.join(original.json_bytes(row) for row in [header, *rows,
        dict(kind='complete', frames=1001, boundaries=2002, patches_restored=True)])
    fixture.mkdir(parents=True)
    evidence.mkdir(parents=True)
    files = {}

    def write(root, name, data):
        path = root / name
        with path.open('xb') as stream:
            stream.write(data)
        require(path.read_bytes() == data, 'promoted file readback differs: ' + name)
        return sha(data)

    fixture_pins = {name: write(fixture, name, data) for name, data in (
        ('route.txt', route), ('reference.jsonl.gz', compressed(payload)))}
    values = {
        'capture-report.json': capture_raw, 'native-audit.json': audit_raw,
        'host-binding.json': (native / 'host-binding.json').read_bytes(),
        'launch-receipt.json': (native / 'launch-receipt.json').read_bytes(),
        'storage-controls.json': (native / 'storage-controls.json').read_bytes(),
        'mirror-controls.json': (native / 'mirror-control-tests.json').read_bytes(),
        'batch-controls.json': (private / 'level4-t343-batch-controls/result.json').read_bytes(),
        'replace-receipt.json': (private / 'level4-t343-replace-capture-receipt.json').read_bytes(),
        'sharing-controls.json': (private / 'level4-t341-sharing-control/result.json').read_bytes(),
        'dosbox.conf': (native / 'dosbox.conf').read_bytes(),
        'lossless-retention.jsonl': (native / 'lossless-retention.jsonl').read_bytes(),
        'complete-readback.json': original.json_bytes(dict(status='verified', members=readback,
            raw_guest_bytes_published=0, screenshots_published=0, cpp_expected_values_used=False)),
        'original-reference.jsonl': gzip.decompress(reference_raw),
        'prior-anchor.json': original.json_bytes(dict(rows=prior_rows[-3:-1], header=prior_rows[0],
            compressed_source_sha256=sha(prior_raw))),
        'rea-report.json': (private / 'level4-t344b-rea-first-blast-report.json').read_bytes(),
        'rea-byte-checks.json': (private / 'level4-t344b-rea-first-blast-byte-checks.json').read_bytes(),
    }
    for name, data in values.items():
        packed = reference_raw if name == 'original-reference.jsonl' else compressed(data)
        files[name + '.gz'] = write(evidence, name + '.gz', packed)
    sources = {name: private / name for name in (
        'capture-first-cavity-blast-t343.py', 'capture-right-pole-t313.py', 'capture-upper-demolition-t308.py',
        'capture-level4-continuation-t298.py', 'capture-outside-column-host-bound-t300.py',
        'private_replace_t341.py', 'audit-original-first-blast-t344.py', 'audit-original-pickup-t329.py',
        'audit-original-upper-walk-t306.py', 'audit-closed-original-prefix-t326.py',
        'rea-first-blast-t344.py', 'rea-first-blast-t344b.py')}
    sources.update({path.name: path for path in (Path(__file__), Path(bombs.__file__),
        ROOT / 'tools/level1_original.py', ROOT / 'tools/level1_fidelity.py', ROOT / 'tools/original_capture_contract.py',
        ROOT / 'tools/capture_original_level1_handoff.py', ROOT / 'tools/capture_original_level1_results.py',
        ROOT / 'tools/capture_original_level1_typing.py', ROOT / 'tools/natural_campaign.py',
        ROOT / 'tools/natural_level3_handoff.py', ROOT / 'tools/natural_level3_gate_projections.py',
        ROOT / 'tools/natural_level3_return.py', ROOT / 'tools/original_debris_table.py')})
    source_values = {name: path.read_bytes() for name, path in sources.items()}
    rea_archive = private / 'level4-t344b-rea-first-blast-evidence.zip'
    require(sha(rea_archive.read_bytes()) == '3c3b2a1e40b81eadfbfdc81e20176c9b7227af6c14dc27a3de842d1de2fa5d26',
        'REA source evidence archive differs')
    with zipfile.ZipFile(rea_archive) as archive:
        source_values['rea_prefix_audit.py'] = archive.read('frozen-rea-helper.py')
    source_values['frozen-ds-decoder.py'] = gzip.decompress((ROOT /
        'docs/recovery/evidence/natural_level4_bridge_access_20261103/frozen-ds-decoder.py.gz').read_bytes())
    producer_pins = {}
    for name, data in source_values.items():
        producer_pins[name] = sha(data)
        files[name + '.gz'] = write(evidence, name + '.gz', compressed(data))
    metadata = dict(schema='lezac-native-level4-cavity-bomb-evidence-v1', expected_bytes_source='original_only',
        cpp_expectations_used=False, reference_header=header, fixture_pins=fixture_pins, evidence_file_pins=files,
        producer_pins=producer_pins, source_capture=str(capture['durable_capture_root']),
        capture_ram_root=str(PurePosixPath(live[FIRST, 'present']['png']).parent),
        original_exe_bytes=len(assets['LEZAC.EXE']), original_exe_sha256=sha(assets['LEZAC.EXE']),
        raw_ds_snapshots_published=False, screenshots_published=False, complete_readback_members=4016,
        source_original_audit_sha256=AUDIT_SHA, source_original_reference_sha256=REFERENCE_SHA,
        source_capture_report_sha256=CAPTURE_SHA, original_capture_observer_sha256=OBSERVER_SHA,
        route_planning_stimulus=dict(kind='cpp_route_input_only', expected_bytes_source=False,
            parent_archive_sha256=capture['candidate_archive_sha256'], route_sha256=ROUTE_SHA),
        original_only_bomb_present_boundaries=118, **CLAIMS)
    write(evidence, 'manifest.json', original.json_bytes(metadata))
    return dict(status='promoted_original_only', fixture_bytes=sum(path.stat().st_size for path in fixture.iterdir()),
        evidence_bytes=sum(path.stat().st_size for path in evidence.iterdir()), bomb_present_boundaries=118,
        manifest_sha256=fidelity.sha256(evidence / 'manifest.json'), raw_guest_bytes_published=0, screenshots_published=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT)
    args = parser.parse_args()
    print(original.json_bytes(pack(args.private_root.resolve(), args.out.resolve())).decode(), flush=True)


if __name__ == '__main__':
    main()
