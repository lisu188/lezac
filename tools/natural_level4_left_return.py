"""Original-only Level 4 Small/Medium escape and full left-return frame regression."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import uuid

import natural_level4_bridge_access as prior
from original_capture_contract import ASSET_PINS, read_canonical_assets

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level4_left_return'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level4_left_return_20261103'
FIRST, LAST, FRAMES = 13040, 14800, 1761
INDICES = [13040, 14800]
MANIFEST_SHA256 = '34e3e263c728cc13e2b6eded3e22138badd3da0db0324cf5a566b1461b6f2db6'
ROUTE_SHA256 = '28a4bc9d3949e09351d545d4eecd16470e9a5cde8f7fbe1743ac2c8b0b7872c7'
CLAIMS = prior.CLAIMS
fidelity, original, support = prior.fidelity, prior.original, prior.support
handoff, HOST_PIN = prior.prior.handoff, prior.prior.HOST_PIN
require = fidelity.require


def manifest():
    path = EVIDENCE / 'manifest.json'
    require(fidelity.sha256(path) == MANIFEST_SHA256, 'left-return manifest fingerprint differs')
    value = fidelity.strict_json(path.read_text())
    require(value['schema'] == 'lezac-native-level4-left-return-evidence-v1' and
            value['expected_bytes_source'] == 'original_only' and value['native_sessions_closed'] is True and
            value['cpp_expectations_used'] is False and value['full_guest_ram_exports'] == value['core_dumps'] == 0 and
            value['raw_ds_snapshot_retention'] == 'lossless-gzip RAM-only; not claimed durably retained' and
            value['lossless_retention_members'] == 7056 and value['all_compressed_members_independently_decoded'] is True and
            value['original_pngs_bound_to_live_receipt'] is True and
            (value['reference_frames'], value['reference_boundaries']) == (FRAMES, FRAMES * 2),
            'left-return evidence scope differs')
    require((value['original_exe_bytes'], value['original_exe_sha256']) == (52384, original.EXE_SHA256),
            'left-return original target differs')
    require(value['guard_input_source']['kind'] == 'cpp_typed_mutation_stimulus_only' and
            value['guard_input_source']['expected_bytes_source'] is False and value['guard_input_source']['indices'] == INDICES and
            value['guard_input_source']['phase'] == 'post_update' and
            not set(value['producer_pins']) & set(value['guard_producer_pins']), 'left-return stimulus role differs')
    return value


def check_route(path):
    require(fidelity.sha256(path) == ROUTE_SHA256, 'left-return route fingerprint differs')
    settings, events = fidelity.read_route(path)
    previous_settings, previous = prior.check_route(prior.FIXTURE / 'route.txt')
    require(settings == {**previous_settings, 'ticks': LAST} and
            {tick: rows for tick, rows in events.items() if tick <= FIRST} == previous,
            'left-return ordinary prefix differs')
    return settings, events


def validate_capture(metadata, capture, binding):
    require(capture['status'] == 'original_continuation_observed' and
            all(capture[key] is True for key in ('base_hooks_restored', 'extra_hooks_restored',
                'owned_child_terminal', 'protected_inputs_preserved', 'initial_rng_controlled',
                'normalized_control_bank_inputs', 'ordinary_gameplay_inputs_only')) and
            all(capture[key] == 0 for key in ('gameplay_state_injections', 'full_guest_ram_exports', 'core_dumps',
                'manual_input_claim', 'wall_clock_claim', 'whole_game_fidelity_claim', 'full_frame_claim')) and
            capture['route_sha256'] == ROUTE_SHA256 and capture['original_exe_sha256'] == original.EXE_SHA256 and
            capture['observer_sha256'] == binding['observer_sha256'] == metadata['producer_pins']['capture-left-return-t305.py'] and
            capture['base_observer_sha256'] == binding['base_observer_sha256'] ==
                metadata['producer_pins']['capture-level4-continuation-t298.py'] and
            (capture['first_full_frame_tick'], capture['last_full_frame_tick']) == (FIRST, LAST) and
            capture['snapshot_storage'] == metadata['raw_ds_snapshot_retention'] and
            capture['storage_readback'] == 'each encoded member equals its original complete bytes',
            'left-return original producer/closure differs')
    require([(item['from_level'], item['to_level'], item['intro_frame'], item['intro_rng']) for item in capture['handoffs']] ==
            [(1, 2, 305, 2497022769), (2, 3, 2669, 3666694644), (3, 4, 7798, 1603369198)],
            'left-return original handoffs differ')
    root = PurePosixPath(metadata['source_capture'])
    require(root.is_absolute() and root.is_relative_to('/dev/shm') and '..' not in root.parts and
            binding['host'] == HOST_PIN and binding['actual_host_sha256'] == HOST_PIN['sha256'] and
            binding['actual_pid'] > 0 and binding['whole_game_fidelity_claim'] is False and
            binding['cwd'] == str(root.parent) and binding['argv'] == [
                'dosbox', '-conf', str(root / 'dosbox.conf'), '-c', 'mount c ' + str(root / 'runtime'),
                '-c', 'c:', '-c', 'L1ORACLE.COM', '-c', 'LEZAC.EXE'], 'left-return original host/launch differs')
    canonical = {name: dict(bytes=size, sha256=digest) for name, (size, digest) in ASSET_PINS.items()}
    require(binding['canonical_source_assets'] == canonical and binding['omitted_installation_log'] == 'SETUP.LOG' and
            binding['copied_assets'] == {name: pin for name, pin in canonical.items() if name != 'SETUP.LOG'} and
            binding['config_sha256'] == fidelity.sha256(EVIDENCE / 'dosbox.conf') and
            binding['loader_sha256'] == hashlib.sha256(original.resident_program()).hexdigest(),
            'left-return original asset/config/loader differs')
    prefix = binding['prefix_header']
    settings, _ = original.read_route(ROOT / 'tests/fixtures/level1_original/completion_gate/route.txt')
    require(prefix['exe_sha256'] == original.EXE_SHA256 and prefix['dosbox_sha256'] == HOST_PIN['sha256'] and
            prefix['source_sha256'] == metadata['producer_pins']['level1_original.py'] and prefix['settings'] == settings and
            prefix['initial_rng'] == original.initial_seed(settings['seed']) and prefix['dimensions'] == [320, 200] and
            prefix['original_fidelity_claim'] is False and prefix['hooks'] == [[at, code] for at, code in original.HOOKS] and
            prefix['preview_draws'] == 390 and prefix['prefix_ticks'] == 3, 'left-return prefix provenance differs')
    environment, geometry = binding['environment'], binding['geometry']
    require(set(environment) == {'DISPLAY', 'SDL_AUDIODRIVER', 'SDL_VIDEODRIVER', 'TMPDIR', 'TMP', 'TEMP'} and
            environment['SDL_AUDIODRIVER'] == 'dummy' and environment['SDL_VIDEODRIVER'] == 'x11' and
            re.fullmatch(r':\d+(?:\.\d+)?', environment['DISPLAY']) is not None and
            all(PurePosixPath(environment[key]).is_relative_to('/dev/shm') and
                '..' not in PurePosixPath(environment[key]).parts for key in ('TMPDIR', 'TMP', 'TEMP')),
            'left-return original environment differs')
    require(set(geometry) == {'WINDOW', 'X', 'Y', 'WIDTH', 'HEIGHT', 'SCREEN'} and int(geometry['WINDOW']) > 0 and
            [int(geometry[key]) for key in ('WIDTH', 'HEIGHT', 'SCREEN')] == [320, 200, 0] and
            0 <= int(geometry['X']) <= 320 and 0 <= int(geometry['Y']) <= 280, 'left-return geometry differs')


def validate(rows, metadata, audit, capture, retained):
    require(len(rows) == FRAMES * 2 + 2 and rows[0] == metadata['reference_header'] and rows[-1] ==
            dict(kind='complete', frames=FRAMES, boundaries=FRAMES * 2, patches_restored=True), 'left-return reference extent differs')
    header = rows[0]
    require(header['schema'] == 'lezac-natural-level4-left-return-v1' and
            (header['first_tick'], header['last_tick'], header['frames'], header['boundaries']) == (FIRST, LAST, FRAMES, FRAMES * 2) and
            header['native_frame_offset'] == 1623 and header['dimensions'] == [100, 58] and
            header['expected_bytes_source'] == 'original_only' and header['route_sha256'] == ROUTE_SHA256 and
            header['prior_anchor_manifest'] == prior.MANIFEST_SHA256 and header['completed_levels'] == [1, 2, 3] and
            header['entered_level'] == 4 and header['cpp_expectations_used'] is False and
            header['gameplay_state_injections'] is False and header['full_ds_snapshots_published'] is False and
            header['initial_rng_controlled'] is True and header['normalized_control_bank_inputs'] is True and
            header['audio'] == 'dummy' and all(header[key] is value for key, value in CLAIMS.items()), 'left-return reference scope differs')
    require(audit['schema'] == 'lezac-native-left-return-ds-audit-v1' and audit['boundaries'] == FRAMES * 2 and
            audit['ds_redecode_differences'] == audit['full_guest_ram_exports'] == audit['compressed_member_readback_differences'] == 0 and
            audit['excluded_from_ds_redecode'] == ['mapped.tiles_hex', 'mapped.words_hex', 'mapped.palette'] and
            audit['raw_ds_snapshots_published'] is False and len(audit['records']) == FRAMES * 2 and
            audit['lossless_retention_members'] == 7056, 'left-return independent audit differs')
    live = {(row['tick'], row['phase']): row for row in capture['checkpoints']}
    stored = {row['path']: row for row in retained}
    require(len(live) == len(capture['checkpoints']) == 3528 and len(stored) == len(retained) == 7056 and
            set(stored) == {f'{prefix}-{tick}-{phase}.{suffix}.gz' for tick, phase in live
                           for prefix, suffix in (('boundary', 'json'), ('ds', 'bin'))}, 'left-return storage domain differs')
    for item in retained:
        require(set(item) == {'path', 'source_bytes', 'source_sha256', 'encoded_bytes', 'encoded_sha256', 'readback_equal'} and
                item['readback_equal'] is True and 0 < item['encoded_bytes'] <= item['source_bytes'] + 128 and
                len(bytes.fromhex(item['source_sha256'])) == len(bytes.fromhex(item['encoded_sha256'])) == 32,
                'left-return lossless receipt differs')
    sequence = audit['records'][0]['native_sequence']
    for index, (row, checked) in enumerate(zip(rows[1:-1], audit['records'])):
        tick, phase = FIRST + index // 2, ('present', 'post_update')[index % 2]
        require(set(row) == {'kind', 'section', 'index', 'phase', 'projection', 'rgb_sha256'} and
                (row['kind'], row['section'], row['index'], row['phase']) == ('boundary', 'level4', tick, phase) and
                (checked['index'], checked['phase'], checked['native_sequence']) == (tick, phase, sequence + 3 * (index // 2) + index % 2) and
                hashlib.sha256(original.json_bytes(row['projection'])).hexdigest() == checked['projection_sha256'] and
                checked['ds_sha256'] == live[tick, phase]['ds_sha256'] == stored[f'ds-{tick}-{phase}.bin.gz']['source_sha256'] and
                stored[f'ds-{tick}-{phase}.bin.gz']['source_bytes'] == 65536 and
                checked['rgb_sha256'] == row['rgb_sha256'], 'left-return audited boundary differs')
        require((phase == 'post_update' and row['rgb_sha256'] is None) or (phase == 'present' and
                row['rgb_sha256'] == live[tick, phase]['rgb_sha256'] and len(bytes.fromhex(row['rgb_sha256'])) == 32),
                'left-return RGB receipt differs')
        mapped = row['projection']['mapped']
        require(set(row['projection']) == {'mapped', 'lifecycle', 'monsters', 'markers', 'terrain'} and
                mapped['level'] == 4 and mapped['frame'] == tick - 1623 and mapped['progress'] == [3, 261] and
                live[tick, phase]['sequence'] == checked['native_sequence'] and live[tick, phase]['mapped'] ==
                    {key: mapped[key] for key in ('frame', 'rng', 'progress', 'players')}, 'left-return native state differs')
        observed = {key: value for key, value in live[tick, phase].items()
                    if key not in ('mapped', 'rgb_sha256', 'png_sha256', 'png', 'known_rgb_match')}
        observed['projection'] = row['projection']
        raw = (json.dumps(observed, sort_keys=True) + '\n').encode('utf-8')
        receipt = stored[f'boundary-{tick}-{phase}.json.gz']
        require((len(raw), hashlib.sha256(raw).hexdigest()) == (receipt['source_bytes'], receipt['source_sha256']),
                'left-return boundary readback binding differs')
    final = rows[-2]['projection']['mapped']
    player = final['players'][0]
    require(player['xy'] == [13.0, 344.0] and player['velocity'] == [0, 0] and player['energy'] == 6 and player['reserve'] == 0 and
            player['inventory'] == [198, 3, 0, 0, 1] and final['rng'] == 363217051 and
            not rows[-2]['projection']['terrain']['collapse'], 'left-return endpoint differs')


def fixture():
    metadata = manifest()
    for directory, key in ((FIXTURE, 'fixture_pins'), (EVIDENCE, 'evidence_file_pins')):
        for name, digest in metadata[key].items():
            require(fidelity.sha256(fidelity.safe_file(directory, name)) == digest, 'left-return pinned bytes differ: ' + name)
    for name, digest in {**metadata['producer_pins'], **metadata['guard_producer_pins']}.items():
        require(hashlib.sha256(gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes())).hexdigest() == digest,
                'left-return frozen source differs: ' + name)
    read_canonical_assets(ROOT)
    load = lambda name: fidelity.strict_json(gzip.decompress((EVIDENCE / name).read_bytes()).decode())
    rows = handoff.load(FIXTURE / 'reference.jsonl.gz')
    require(rows[0]['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'left-return assets differ')
    capture, binding, audit = load('capture-report.json.gz'), load('host-binding.json.gz'), load('native-audit.json.gz')
    retained = handoff.load(EVIDENCE / 'lossless-retention.jsonl.gz')
    validate_capture(metadata, capture, binding)
    validate(rows, metadata, audit, capture, retained)
    controls = load('storage-control-tests.json.gz')
    require(controls['tests'] == 6 and controls['passed'] is True and controls['guest_launched'] is False and
            controls['raw_guest_memory_published'] is False and controls['observer_sha256'] == capture['observer_sha256'],
            'left-return storage controls differ')
    rea, instructions = load('rea-report.json.gz'), load('rea-byte-checks.json.gz')
    require(rea['status'] == 'completed' and rea['target_sha256'] == original.EXE_SHA256 and rea['session_closed'] is True and
            rea['server_exit_code'] == 0 and rea['target_preserved'] is True and rea['rea_version'] == '6.7.0' and
            rea['source_sha256'] == metadata['producer_pins']['rea_prefix_audit.py'] and
            rea['provider']['id'] == 'ghidra' and rea['provider']['version'] == '12.1.4', 'left-return REA closure differs')
    require([row['offset'] for row in instructions] == [0x6f90, 0x6f93, 0x6f98, 0x6fa6, 0x6fb0, 0x6fb3, 0x6fc5, 0x6fc9,
            0x6fca, 0x6fcd, 0x6fd3, 0x6fd7, 0x6fd8, 0x6fdb, 0x6ff9, 0x7011], 'left-return instruction domain differs')
    image = original.check_executable(ROOT / 'LEZAC.EXE')
    for row in instructions:
        code = bytes.fromhex(row['decoded']['bytes'])
        require(code == image[row['offset']:row['offset'] + len(code)] and row['bytes_equal'] is True, 'left-return instruction bytes differ')
    previous = prior.fixture()
    require(all(rows[index]['projection'] == previous[-4 + index]['projection'] for index in (1, 2)), 'left-return prior anchor differs')
    check_route(FIXTURE / 'route.txt')
    return rows


def compare(cpp, *, first=FIRST, last=LAST):
    require(FIRST <= first <= last <= LAST, 'left-return requested range differs')
    wanted = {(row['index'], row['phase']): row for row in fixture()[1:-1]}
    settings, events = check_route(FIXTURE / 'route.txt')
    current, selected = fidelity.read_route(cpp / 'route.txt')
    require(current == {**settings, 'ticks': last} and selected == {tick: items for tick, items in events.items() if tick < last},
            'left-return chunk ordinary route differs')
    frames = count = boundaries = 0
    previous = footer = None
    with (cpp / 'run/trace.jsonl').open() as stream:
        header = fidelity.strict_json(next(stream))
        require(set(header) == fidelity.HEADER_KEYS | {'capture_from_tick', 'candidate_only'} and
                header['schema'] == 'lezac.level1.scout.v1' and header['source'] == 'cpp' and header['candidate_only'] is True and
                header['ticks'] == last and header['capture_from_tick'] == first and header['original_fidelity_claim'] is False and
                header['phase_model'] == 'cpp-pre-actors-v2' and header['state_scope'] == 'level1-observations-v2' and
                header['input_model'] == 'sdl-events-original-intro-wait-v1' and (header['width'], header['height']) == (320, 200) and
                header['seed'] == settings['seed'] and header['step_us'] == settings['step_us'] and
                header['route_fnv1a64'] == fidelity.fnv1a64((cpp / 'route.txt').read_bytes()) and
                header['asset_fnv1a64'] == {name: fidelity.fnv1a64((ROOT / name).read_bytes()) for name in fidelity.ASSETS},
                'left-return C++ header differs')
        for line in stream:
            row = fidelity.strict_json(line)
            require(footer is None, 'left-return data after footer')
            if row['kind'] == 'complete':
                footer = row
                require(set(row) == {'kind', 'ticks', 'frames', 'retained_checkpoints', 'checkpoints', 'events', 'capture_from_tick',
                        'candidate_only', 'level1_route_complete', 'original_fidelity_claim', 'port_functionally_complete'} and
                        row['ticks'] == last and row['capture_from_tick'] == first and row['frames'] == frames == last - first + 1 and
                        row['retained_checkpoints'] == count == frames * 4 and row['checkpoints'] == previous + 1 and
                        row['events'] == sum(map(len, selected.values())) and row['candidate_only'] is True and
                        row['level1_route_complete'] is True and row['original_fidelity_claim'] is False and
                        row['port_functionally_complete'] is False, 'left-return C++ footer differs')
                continue
            tick, phase = first + count // 4, ('input', 'present', 'after_nonplayers', 'post_update')[count % 4]
            keys = {'kind', 'seq', 'tick', 'phase', 'time_ms', 'events', 'state'} | ({'frame', 'rgb_fnv1a64'} if phase == 'present' else set())
            require(set(row) == keys and row['kind'] == 'checkpoint' and (row['tick'], row['phase']) == (tick, phase) and tick <= last and
                    (previous is None or row['seq'] == previous + 1) and row['events'] == events.get(tick - 1, []) and
                    row['time_ms'] == (tick - 1) * settings['step_us'] // 1000, 'left-return C++ phase/input/time differs')
            fidelity.validate_state(row['state'])
            if phase in ('present', 'post_update'):
                support.recovered.check_cpp(row['state'], wanted[tick, phase])
                boundaries += 1
            if phase == 'present':
                require(row['frame'] == f'frame_{tick:06d}.ppm', 'left-return RGB filename differs')
                pixels = fidelity.read_ppm(fidelity.safe_file(cpp / 'run', row['frame']))
                require(fidelity.fnv1a64(pixels) == row['rgb_fnv1a64'] and hashlib.sha256(pixels).hexdigest() == wanted[tick, phase]['rgb_sha256'],
                        'left-return original RGB differs')
                frames += 1
            previous, count = row['seq'], count + 1
    require(footer is not None and boundaries == frames * 2, 'left-return C++ window incomplete')
    return dict(status='match', first=first, last=last, frames=frames, boundaries=boundaries, checkpoints=count,
        pixels=frames * 64000, expected_bytes_source='original_only', comparison_scope='projected fields and full RGB only',
        final_destroyed=261, remaining_for_threshold=44, gameplay_state_injections=False, **CLAIMS)


def replay(exe, out):
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    case = out.resolve() / ('run-' + uuid.uuid4().hex)
    case.mkdir(parents=True)
    try:
        fixture()
        require(exe.is_file(), 'left-return executable missing')
        shutil.copyfile(FIXTURE / 'route.txt', case / 'route.txt')
        assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
        command = [str(exe.resolve()), '--replay-level1-scout', str(case / 'route.txt'), str(case / 'run'),
                   str(FIRST), '--original-intro-wait', '--result-reels']
        (case / 'command.json').write_bytes(original.json_bytes(dict(command=command, assets=assets,
            executable_sha256=fidelity.sha256(exe), reader_sha256=fidelity.sha256(Path(__file__)), audio='dummy', **CLAIMS)))
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
            require(child.returncode == 0, 'left-return C++ replay failed')
        require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'left-return replay changed assets')
        report = compare(case)
    except BaseException as error:
        (case / 'comparison.json').write_bytes(original.json_bytes(dict(status='failed', error=str(error), **CLAIMS)))
        raise
    (case / 'comparison.json').write_bytes(original.json_bytes(report))
    return report


def guard():
    wanted = {(row['index'], row['phase']): row for row in fixture()[1:-1]}
    inputs = handoff.load(FIXTURE / 'guard-inputs.jsonl.gz')
    require([row['index'] for row in inputs] == INDICES and all(row['kind'] == 'cpp_typed_mutation_stimulus_only' and
            row['phase'] == 'post_update' for row in inputs), 'left-return mutation stimulus scope differs')
    rejected = 0
    for row in inputs:
        expected = wanted[row['index'], row['phase']]
        support.recovered.check_cpp(row['state'], expected)
        rejected += support.recovered.guard_cpp(row['state'], expected)
        for path in (('logic_tick',), ('players', 0, 'animation', 0), ('players', 0, 'hud_score', 0)):
            state = copy.deepcopy(row['state'])
            target = state
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] += 1
            try:
                support.recovered.check_cpp(state, expected)
            except fidelity.EvidenceError:
                rejected += 1
            else:
                raise fidelity.EvidenceError('left-return typed mutation accepted: ' + str(path))
    return dict(status='guarded', stimuli=len(inputs), typed_mutations_rejected=rejected, expected_bytes_source='original_only', **CLAIMS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('replay', 'compare', 'guard'))
    for name in ('exe', 'out', 'cpp'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.command == 'replay':
        require(args.exe is not None and args.out is not None, 'left-return executable/output required')
        report = replay(args.exe, args.out)
    elif args.command == 'compare':
        require(args.cpp is not None, 'left-return C++ evidence required')
        report = compare(args.cpp)
    else:
        report = guard()
    print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
