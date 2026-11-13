"""Original-backed natural Level 4 cavity-bomb state and frame regression."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import uuid

import bomb_state_projection as bombs
import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original
import natural_level3_handoff as recovered
from natural_route_window import compare_window
from original_capture_contract import ASSET_PINS, read_canonical_assets
from pack_natural_level4_cavity_bomb import CLAIMS

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level4_cavity_bomb'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level4_cavity_bomb_20261104'
FIRST, LAST, FRAMES = 13700, 14700, 1001
MANIFEST_SHA256 = '2485b17d7b2f0d39e46817f23df1affc51462f9a9b0ff2a6c2c29d5810610c63'
ROUTE_SHA256 = 'a58a48cd67942a1ba49323cb7f65394acff1d9b0a5ef8928cc398db2375cbc2b'
require = fidelity.require
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def manifest():
    path = fidelity.safe_file(EVIDENCE, 'manifest.json')
    require(fidelity.sha256(path) == MANIFEST_SHA256, 'cavity-bomb manifest fingerprint differs')
    value = fidelity.strict_json(path.read_text())
    require(value['schema'] == 'lezac-native-level4-cavity-bomb-evidence-v1' and
        value['expected_bytes_source'] == 'original_only' and value['cpp_expectations_used'] is False and
        value['raw_ds_snapshots_published'] is value['screenshots_published'] is False and
        value['complete_readback_members'] == 4016 and value['original_only_bomb_present_boundaries'] == 118 and
        (value['original_exe_bytes'], value['original_exe_sha256']) == ASSET_PINS['LEZAC.EXE'] and
        value['route_planning_stimulus']['kind'] == 'cpp_route_input_only' and
        value['route_planning_stimulus']['expected_bytes_source'] is False and
        value['route_planning_stimulus']['route_sha256'] == ROUTE_SHA256 and
        all(value[key] is expected for key, expected in CLAIMS.items()), 'cavity-bomb evidence scope differs')
    return value


def check_route(path):
    require(fidelity.sha256(path) == ROUTE_SHA256, 'cavity-bomb ordinary route differs')
    settings, events = fidelity.read_route(path)
    previous_settings, previous = fidelity.read_route(recovered.FIXTURE / 'route.txt')
    require(settings == {**previous_settings, 'ticks': LAST} and
        {tick: rows for tick, rows in events.items() if tick < 9422} ==
        {tick: rows for tick, rows in previous.items() if tick < 9422} and
        events[13702] == [dict(action='down', key='z'), dict(action='down', key='m')] and
        events[14502] == [dict(action='down', key='n')], 'cavity-bomb ordinary prefix or fire timing differs')
    return settings, events


def base_row(row):
    result = dict(row)
    result.pop('native_ds_sha256')
    result['projection'] = {key: value for key, value in row['projection'].items() if key != 'bombs'}
    return result


def validate(rows, metadata, sources, capture, audit, retained, readback):
    require(len(rows) == len(sources) == 2004 and rows[0] == metadata['reference_header'] and
        rows[-1] == dict(kind='complete', frames=FRAMES, boundaries=FRAMES * 2, patches_restored=True),
        'cavity-bomb reference extent differs')
    require(sources[0]['expected_bytes_source'] == 'original_only' and sources[0]['cpp_expectations_used'] is False and
        (sources[0]['first_tick'], sources[0]['last_tick'], sources[0]['frames'], sources[0]['boundaries']) ==
            (FIRST, LAST, FRAMES, 2002) and sources[-1] == rows[-1], 'cavity-bomb original source role differs')
    header = rows[0]
    require(header['schema'] == 'lezac-natural-level4-cavity-bomb-v1' and
        (header['first_tick'], header['last_tick'], header['frames'], header['boundaries']) == (FIRST, LAST, FRAMES, 2002) and
        header['expected_bytes_source'] == 'original_only' and header['cpp_expectations_used'] is False and
        header['gameplay_state_injections'] is header['raw_ds_snapshots_published'] is header['screenshots_published'] is False and
        header['completed_levels'] == [1, 2, 3] and header['entered_level'] == 4 and
        header['native_frame_offset'] == 1623 and header['dimensions'] == [100, 58] and
        header['bomb_fields'] == list(bombs.FIELDS) and header['bomb_present_boundaries'] == 118 and
        all(header[key] is expected for key, expected in CLAIMS.items()), 'cavity-bomb reference claims differ')
    require(capture['status'] == 'original_continuation_observed' and all(capture[key] is True for key in
        ('owned_child_terminal', 'base_hooks_restored', 'extra_hooks_restored', 'protected_inputs_preserved',
            'private_snapshot_backup', 'ordinary_gameplay_inputs_only', 'initial_rng_controlled', 'normalized_control_bank_inputs')) and
        all(capture[key] == 0 for key in ('gameplay_state_injections', 'full_guest_ram_exports', 'core_dumps',
            'manual_input_claim', 'wall_clock_claim', 'whole_game_fidelity_claim', 'full_frame_claim')) and
        capture['public_raw_snapshot_upload'] is False and capture['cumulative_report_batch_interval'] == 25 and
        capture['snapshot_backups_individually_flushed'] is True and
        (capture['first_full_frame_tick'], capture['last_full_frame_tick']) == (FIRST, LAST) and
        capture['route_sha256'] == ROUTE_SHA256 and capture['original_exe_sha256'] == original.EXE_SHA256 and
        capture['route_input_source'] == 'C++ route planning stimulus only; no C++ state expectations' and
        capture['candidate_archive_sha256'] == metadata['route_planning_stimulus']['parent_archive_sha256'] and
        capture['observer_sha256'] == metadata['original_capture_observer_sha256'] ==
            metadata['producer_pins']['capture-first-cavity-blast-t343.py'], 'cavity-bomb original capture differs')
    require([(row['from_level'], row['to_level'], row['intro_frame'], row['intro_rng']) for row in capture['handoffs']] ==
        [(1, 2, 305, 2497022769), (2, 3, 2669, 3666694644), (3, 4, 7798, 1603369198)],
        'cavity-bomb original handoffs differ')
    require(audit['status'] == 'original_only_audit_passed' and audit['cpp_expectations_used'] is False and
        audit['capture_request_complete'] is True and audit['capture_requested_window'] == audit['observed_complete_window'] == [FIRST, LAST] and
        (audit['frames'], audit['boundaries'], audit['compressed_members']) == (FRAMES, 2002, 4016) and
        all(audit[key] == 0 for key in ('independent_ds_redecode_differences', 'compressed_member_readback_differences',
            'full_private_member_byte_differences', 'original_png_receipt_differences', 'prefix_repeat_differences')) and
        audit['prefix_repeat_boundaries'] == 2 and audit['private_snapshot_backup'] is True and
        audit['public_raw_snapshot_upload'] is False and len(audit['retained_member_negative_controls_rejected']) == 9,
        'cavity-bomb independent original audit differs')
    live = {(row['tick'], row['phase']): row for row in capture['checkpoints']}
    checked = {(row['tick'], row['phase']): row for row in audit['records']}
    require(len(live) == len(capture['checkpoints']) == 2008 and len(checked) == len(audit['records']) == 2002,
        'cavity-bomb native receipt inventory differs')
    catalog = {row['path']: row for row in retained}
    proof = {row['path']: row for row in readback['members']}
    require(len(catalog) == len(retained) == len(proof) == len(readback['members']) == 4016 and
        set(catalog) == set(proof) == {f'{prefix}-{tick}-{phase}.{suffix}.gz' for tick, phase in live
            for prefix, suffix in (('ds', 'bin'), ('boundary', 'json'))} and
        readback['status'] == 'verified' and readback['raw_guest_bytes_published'] == readback['screenshots_published'] == 0 and
        readback['cpp_expected_values_used'] is False, 'cavity-bomb complete readback inventory differs')
    for name, row in catalog.items():
        require(row['readback_equal'] is True and proof[name] == dict(path=name, encoded_bytes=row['encoded_bytes'],
            encoded_sha256=row['encoded_sha256'], source_bytes=row['source_bytes'], source_sha256=row['source_sha256'],
            complete_byte_readback=True) and 0 < row['encoded_bytes'] <= row['source_bytes'] + 128,
            'cavity-bomb complete member proof differs')
        if name.startswith('ds-'):
            require(row['source_bytes'] == 65536, 'cavity-bomb DS member is truncated')
    first_sequence = live[FIRST, 'present']['sequence']
    active = []
    for index, (row, source) in enumerate(zip(rows[1:-1], sources[1:-1])):
        tick, phase = FIRST + index // 2, ('present', 'post_update')[index % 2]
        require(set(row) == {'kind', 'section', 'index', 'phase', 'projection', 'rgb_sha256', 'native_ds_sha256'} and
            row['kind'] == 'boundary' and row['section'] == 'level4' and (row['index'], row['phase']) == (tick, phase) and
            set(row['projection']) == {'mapped', 'lifecycle', 'monsters', 'markers', 'terrain', 'bombs'} and
            base_row(row) == source, 'cavity-bomb source/reference boundary differs')
        receipt, verified = live[tick, phase], checked[tick, phase]
        projection = source['projection']
        require(row['native_ds_sha256'] == receipt['ds_sha256'] == verified['ds_sha256'] ==
            catalog[f'ds-{tick}-{phase}.bin.gz']['source_sha256'] and
            verified['projection_sha256'] == sha(original.json_bytes(projection)) and
            receipt['sequence'] == verified['sequence'] == first_sequence + (tick - FIRST) * 3 + (phase == 'post_update') and
            receipt['mapped'] == {key: projection['mapped'][key] for key in ('frame', 'rng', 'progress', 'players')} and
            projection['mapped']['frame'] == tick - 1623, 'cavity-bomb DS/projection/sequence identity differs')
        require((row['rgb_sha256'] is None) == (phase == 'post_update'), 'cavity-bomb RGB phase differs')
        if phase == 'present':
            require(row['rgb_sha256'] == receipt['rgb_sha256'] == verified['rgb_sha256'], 'cavity-bomb RGB receipt differs')
        bombs.validate_projection(row['projection']['bombs'])
        if row['projection']['bombs']:
            active.append(row)
    require(len(active) == 118 and (active[0]['index'], active[0]['phase']) == (14503, 'post_update') and
        (active[-1]['index'], active[-1]['phase']) == (14562, 'present') and
        active[0]['projection']['bombs'] == [dict(kind=14, counter=30, pixel_x=210, pixel_y=360,
            vx8=0, vy8=-500, fraction_x_word=0, fraction_y_word=0, behavior=2)] and
        active[-1]['projection']['bombs'][0]['counter'] == 1, 'cavity-bomb observed lifetime differs')
    final = rows[-2]['projection']['mapped']
    require(final['progress'] == [3, 280] and final['players'][0]['energy'] == 22 and
        final['players'][0]['reserve'] == 0 and final['players'][0]['inventory'] == [200, 3, 0, 0, 1] and
        final['players'][0]['xy'] == [13.0, 360.0] and final['rng'] == 1114144943,
        'cavity-bomb original endpoint differs')


def fixture():
    metadata = manifest()
    for directory, key in ((FIXTURE, 'fixture_pins'), (EVIDENCE, 'evidence_file_pins')):
        for name, digest in metadata[key].items():
            require(fidelity.sha256(fidelity.safe_file(directory, name)) == digest, 'cavity-bomb pinned file differs: ' + name)
    for name, digest in metadata['producer_pins'].items():
        require(sha(gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes())) == digest,
            'cavity-bomb frozen producer differs: ' + name)
    assets = read_canonical_assets(ROOT)
    load = lambda name: fidelity.strict_json(gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes()).decode())
    capture, audit, binding = (load(name) for name in ('capture-report.json', 'native-audit.json', 'host-binding.json'))
    require(sha(gzip.decompress((EVIDENCE / 'capture-report.json.gz').read_bytes())) == metadata['source_capture_report_sha256'] and
        sha(gzip.decompress((EVIDENCE / 'native-audit.json.gz').read_bytes())) == metadata['source_original_audit_sha256'] and
        fidelity.sha256(EVIDENCE / 'original-reference.jsonl.gz') == metadata['source_original_reference_sha256'] == audit['reference_sha256'],
        'cavity-bomb source artifact identity differs')
    root = PurePosixPath(metadata['capture_ram_root'])
    require(root.is_relative_to('/dev/shm') and binding['cwd'] == '/dev/shm' and
        binding['argv'] == ['dosbox', '-conf', str(root / 'dosbox.conf'), '-c', 'mount c ' + str(root / 'runtime'),
            '-c', 'c:', '-c', 'L1ORACLE.COM', '-c', 'LEZAC.EXE'] and
        binding['actual_host_sha256'] == binding['host']['sha256'] == '9213fb131e11cb195bdff40c24513740ce497c5caf1cef1900ad1faad5c5026b' and
        binding['environment']['SDL_AUDIODRIVER'] == 'dummy' and binding['observer_sha256'] == capture['observer_sha256'] and
        [int(binding['geometry'][key]) for key in ('WIDTH', 'HEIGHT', 'SCREEN')] == [320, 200, 0] and
        binding['config_sha256'] == sha(gzip.decompress((EVIDENCE / 'dosbox.conf.gz').read_bytes())) and
        binding['loader_sha256'] == sha(original.resident_program()) and
        binding['prefix_header']['source_sha256'] == metadata['producer_pins']['level1_original.py'] and
        binding['copied_assets'] == {name: dict(bytes=size, sha256=digest) for name, (size, digest) in ASSET_PINS.items()
            if name != 'SETUP.LOG'} and
        binding['canonical_source_assets'] == {name: dict(bytes=size, sha256=digest) for name, (size, digest) in ASSET_PINS.items()},
        'cavity-bomb original host/launch/assets binding differs')
    launch, batch, retry = (load(name) for name in ('launch-receipt.json', 'batch-controls.json', 'replace-receipt.json'))
    require(launch['observer_sha256'] == batch['observer_sha256'] == retry['observer_sha256'] == capture['observer_sha256'] and
        launch['maximum_seconds'] == retry['maximum_seconds'] == 2400 and batch['status'] == 'passed' and
        len(batch['controls']) == 8 and batch['guest_launched'] is False and retry['status'] == 'completed' and
        retry['process_replace_hook_restored'] is retry['snapshot_backups_individually_flushed'] is True and
        retry['cumulative_report_batch_interval'] == 25, 'cavity-bomb batching/cleanup provenance differs')
    rea, instructions = load('rea-report.json'), load('rea-byte-checks.json')
    require(rea['status'] == 'completed' and rea['session_closed'] is rea['target_preserved'] is True and
        rea['server_exit_code'] == 0 and rea['target_sha256'] == original.EXE_SHA256 and
        rea['provider']['id'] == 'ghidra' and rea['provider']['version'] == '12.1.4' and
        rea['source_sha256'] == metadata['producer_pins']['rea_prefix_audit.py'] and
        len(instructions) == 34, 'cavity-bomb REA identity or closure differs')
    image = original.check_executable(ROOT / 'LEZAC.EXE')
    for row in instructions:
        code = bytes.fromhex(row['decoded']['bytes'])
        require(code and code == image[row['offset']:row['offset'] + len(code)] and row['bytes_equal'] is True,
            'cavity-bomb original instruction bytes differ')
    rows = handoff.load(FIXTURE / 'reference.jsonl.gz')
    require(rows[0]['assets'] == {name: sha(assets[name]) for name in fidelity.ASSETS}, 'cavity-bomb assets differ')
    validate(rows, metadata, handoff.load(EVIDENCE / 'original-reference.jsonl.gz'), capture, audit,
        handoff.load(EVIDENCE / 'lossless-retention.jsonl.gz'), load('complete-readback.json'))
    prior = load('prior-anchor.json')
    require([base_row(row) for row in rows[1:3]] == prior['rows'] and
        prior['header']['expected_bytes_source'] == 'original_only' and prior['header']['cpp_expectations_used'] is False and
        prior['compressed_source_sha256'] == capture['previous_original_reference_sha256'], 'cavity-bomb prior overlap differs')
    check_route(FIXTURE / 'route.txt')
    return rows


def check_cpp(state, expected):
    recovered.check_cpp(state, base_row(expected))
    bombs.compare(state, expected['projection']['bombs'])


def compare(case):
    rows = fixture()
    settings, events = check_route(FIXTURE / 'route.txt')
    require((case / 'route.txt').read_bytes() == (FIXTURE / 'route.txt').read_bytes(), 'cavity-bomb replay route differs')
    result = compare_window(case, first=FIRST, last=LAST, settings=settings, events=events,
        expected={(row['index'], row['phase']): row for row in rows[1:-1]}, asset_root=ROOT, compare_state=check_cpp)
    return dict(result, bomb_fields_compared=len(bombs.FIELDS), bomb_present_boundaries=118,
        rgb_comparison='sha256-complete-RGB-frame', expected_bytes_source='original_only',
        final_destroyed=280, remaining_for_threshold=25, gameplay_state_injections=False, **CLAIMS)


def replay(exe, out):
    case = out.resolve() / ('run-' + uuid.uuid4().hex)
    case.mkdir(parents=True)
    try:
        fixture()
        require(exe.is_file(), 'cavity-bomb executable missing')
        shutil.copyfile(FIXTURE / 'route.txt', case / 'route.txt')
        assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
        command = [str(exe.resolve()), '--replay-level1-scout', str(case / 'route.txt'), str(case / 'run'),
            str(FIRST), '--original-intro-wait', '--result-reels']
        (case / 'command.json').write_bytes(original.json_bytes(dict(command=command, assets=assets,
            executable_sha256=fidelity.sha256(exe), reader_sha256=fidelity.sha256(Path(__file__)),
            source=fidelity.source_version(ROOT), audio='dummy', video='dummy', **CLAIMS)))
        with tempfile.TemporaryDirectory(prefix='assets-', dir=case) as temporary:
            for name in fidelity.ASSETS:
                shutil.copyfile(ROOT / name, Path(temporary) / name)
            try:
                child = subprocess.run(command, cwd=temporary, capture_output=True, text=True, timeout=600,
                    env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                        LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1'))
            except subprocess.TimeoutExpired as error:
                for name, value in (('stdout.txt', error.stdout), ('stderr.txt', error.stderr)):
                    (case / name).write_bytes(value.encode() if isinstance(value, str) else value or b'')
                raise
            (case / 'stdout.txt').write_text(child.stdout)
            (case / 'stderr.txt').write_text(child.stderr)
            require(child.returncode == 0, 'cavity-bomb C++ replay failed')
        require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'cavity-bomb replay changed assets')
        result = compare(case)
    except BaseException as error:
        (case / 'comparison.json').write_bytes(original.json_bytes(dict(status='failed', error=str(error), **CLAIMS)))
        raise
    (case / 'comparison.json').write_bytes(original.json_bytes(result))
    return result


def guard():
    fixture()
    controls = bombs.guard()
    return dict(status='guarded', bomb_mutations_rejected=len(controls), expected_bytes_source='original_only', **CLAIMS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('fixture', 'guard', 'compare', 'replay'))
    for name in ('exe', 'out', 'cpp'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.command == 'replay':
        require(args.exe is not None and args.out is not None, 'cavity-bomb executable/output required')
        result = replay(args.exe, args.out)
    elif args.command == 'compare':
        require(args.cpp is not None, 'cavity-bomb replay evidence required')
        result = compare(args.cpp)
    elif args.command == 'fixture':
        result = dict(status='fixture_verified', boundaries=len(fixture()) - 2, raw_guest_bytes_published=0, **CLAIMS)
    else:
        result = guard()
    print(original.json_bytes(result).decode(), flush=True)


if __name__ == '__main__':
    main()
