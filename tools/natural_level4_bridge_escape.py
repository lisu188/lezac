"""Original-only Level 4 drop-through and Medium-bomb escape regression."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
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
FIXTURE = ROOT / 'tests/fixtures/natural_level4_bridge_escape'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level4_bridge_escape_20261103'
FIRST, LAST, FRAMES = 13040, 13800, 761
INDICES = [13040, 13080, 13220, 13800]
MANIFEST_SHA256 = 'ffbdb50205b783ad0821bf6aca8a3a8f5708b2e27614a4d88b97685ef18c5beb'
ROUTE_SHA256 = '5fc39ddfea7b0a662d3decf83913aaf81a6d60d8b6a4b42d6c9265dc9f1d58d1'
CLAIMS = prior.CLAIMS
fidelity, original, support = prior.fidelity, prior.original, prior.support
HOST_PIN, handoff = prior.prior.HOST_PIN, prior.prior.handoff
require = fidelity.require


def manifest():
    path = EVIDENCE / 'manifest.json'
    require(fidelity.sha256(path) == MANIFEST_SHA256, 'bridge-escape manifest fingerprint differs')
    value = fidelity.strict_json(path.read_text())
    require(value['schema'] == 'lezac-native-level4-bridge-escape-evidence-v1' and
            value['expected_bytes_source'] == 'original_only' and value['native_sessions_closed'] is True and
            value['cpp_expectations_used'] is False and value['full_guest_ram_exports'] == value['core_dumps'] == 0 and
            value['raw_ds_snapshot_retention'] == 'RAM-only; not claimed durably retained' and
            (value['reference_frames'], value['reference_boundaries']) == (FRAMES, FRAMES * 2),
            'bridge-escape evidence scope differs')
    require(value['original_exe_sha256'] == original.EXE_SHA256 and value['original_exe_bytes'] == 52384,
            'bridge-escape original target differs')
    require(value['guard_input_source']['kind'] == 'cpp_typed_mutation_stimulus_only' and
            value['guard_input_source']['expected_bytes_source'] is False and
            value['guard_input_source']['indices'] == INDICES and
            value['guard_input_source']['phase'] == 'post_update' and
            not set(value['producer_pins']) & set(value['guard_producer_pins']),
            'bridge-escape C++ stimulus roles differ')
    return value


def check_route(path):
    require(fidelity.sha256(path) == ROUTE_SHA256, 'bridge-escape route fingerprint differs')
    settings, events = fidelity.read_route(path)
    previous_settings, previous = prior.check_route(prior.FIXTURE / 'route.txt')
    require(settings == {**previous_settings, 'ticks': LAST} and
            {tick: rows for tick, rows in events.items() if tick <= FIRST} == previous,
            'bridge-escape ordinary prefix differs')
    return settings, events


def validate_capture(metadata, capture, binding):
    require(capture['status'] == 'original_continuation_observed' and
            all(capture[key] is True for key in ('base_hooks_restored', 'extra_hooks_restored',
                'owned_child_terminal', 'protected_inputs_preserved', 'initial_rng_controlled',
                'normalized_control_bank_inputs', 'ordinary_gameplay_inputs_only')) and
            all(capture[key] == 0 for key in ('gameplay_state_injections', 'full_guest_ram_exports', 'core_dumps',
                'manual_input_claim', 'wall_clock_claim', 'whole_game_fidelity_claim')) and
            capture['route_sha256'] == ROUTE_SHA256 and capture['original_exe_sha256'] == original.EXE_SHA256 and
            capture['observer_sha256'] == binding['observer_sha256'] ==
                metadata['producer_pins']['capture-level4-final-t302.py'] and
            capture['base_observer_sha256'] == binding['base_observer_sha256'] ==
                metadata['producer_pins']['capture-level4-continuation-t298.py'] and
            (capture['first_full_frame_tick'], capture['last_full_frame_tick']) == (FIRST, LAST),
            'bridge-escape original producer/closure differs')
    require([(item['from_level'], item['to_level'], item['intro_frame'], item['intro_rng'])
             for item in capture['handoffs']] ==
            [(1, 2, 305, 2497022769), (2, 3, 2669, 3666694644), (3, 4, 7798, 1603369198)],
            'bridge-escape original handoffs differ')
    require(binding['host'] == HOST_PIN and binding['actual_host_sha256'] == HOST_PIN['sha256'] and
            binding['actual_pid'] > 0 and binding['whole_game_fidelity_claim'] is False,
            'bridge-escape original host differs')
    root = PurePosixPath(metadata['source_capture'])
    require(root.is_absolute() and root.is_relative_to('/dev/shm') and '..' not in root.parts and
            binding['cwd'] == str(root.parent) and binding['argv'] == [
                'dosbox', '-conf', str(root / 'dosbox.conf'), '-c', 'mount c ' + str(root / 'runtime'),
                '-c', 'c:', '-c', 'L1ORACLE.COM', '-c', 'LEZAC.EXE'], 'bridge-escape launch differs')
    canonical = {name: dict(bytes=size, sha256=digest) for name, (size, digest) in ASSET_PINS.items()}
    require(binding['canonical_source_assets'] == canonical and binding['omitted_installation_log'] == 'SETUP.LOG' and
            binding['copied_assets'] == {name: pin for name, pin in canonical.items() if name != 'SETUP.LOG'},
            'bridge-escape asset domain differs')
    require(binding['config_sha256'] == fidelity.sha256(EVIDENCE / 'dosbox.conf') and
            binding['loader_sha256'] == hashlib.sha256(original.resident_program()).hexdigest(),
            'bridge-escape config/loader differs')
    prefix = binding['prefix_header']
    settings, _ = original.read_route(ROOT / 'tests/fixtures/level1_original/completion_gate/route.txt')
    require(prefix['exe_sha256'] == original.EXE_SHA256 and prefix['dosbox_sha256'] == HOST_PIN['sha256'] and
            prefix['source_sha256'] == metadata['producer_pins']['level1_original.py'] and
            prefix['settings'] == settings and prefix['initial_rng'] == original.initial_seed(settings['seed']) and
            prefix['dimensions'] == [320, 200] and prefix['original_fidelity_claim'] is False and
            prefix['hooks'] == [[at, code] for at, code in original.HOOKS] and
            prefix['preview_draws'] == 390 and prefix['prefix_ticks'] == 3, 'bridge-escape prefix provenance differs')
    environment, geometry = binding['environment'], binding['geometry']
    require(set(environment) == {'DISPLAY', 'SDL_AUDIODRIVER', 'SDL_VIDEODRIVER', 'TMPDIR', 'TMP', 'TEMP'} and
            environment['SDL_AUDIODRIVER'] == 'dummy' and environment['SDL_VIDEODRIVER'] is None and
            re.fullmatch(r':\d+(?:\.\d+)?', environment['DISPLAY']) is not None and
            all(PurePosixPath(environment[key]).is_relative_to('/dev/shm') and
                '..' not in PurePosixPath(environment[key]).parts for key in ('TMPDIR', 'TMP', 'TEMP')),
            'bridge-escape original environment differs')
    require(set(geometry) == {'WINDOW', 'X', 'Y', 'WIDTH', 'HEIGHT', 'SCREEN'} and
            int(geometry['WINDOW']) > 0 and [int(geometry[key]) for key in ('WIDTH', 'HEIGHT', 'SCREEN')] == [320, 200, 0] and
            0 <= int(geometry['X']) <= 320 and 0 <= int(geometry['Y']) <= 280,
            'bridge-escape original geometry differs')


def validate(rows, metadata, audit):
    require(len(rows) == FRAMES * 2 + 2 and rows[0] == metadata['reference_header'] and
            rows[-1] == dict(kind='complete', frames=FRAMES, boundaries=FRAMES * 2, patches_restored=True),
            'bridge-escape reference extent differs')
    header = rows[0]
    require(header['schema'] == 'lezac-natural-level4-bridge-escape-v1' and
            (header['first_tick'], header['last_tick'], header['frames'], header['boundaries']) ==
                (FIRST, LAST, FRAMES, FRAMES * 2) and header['native_frame_offset'] == 1623 and
            header['dimensions'] == [100, 58] and header['expected_bytes_source'] == 'original_only' and
            header['route_sha256'] == ROUTE_SHA256 and header['prior_anchor_manifest'] == prior.MANIFEST_SHA256 and
            header['completed_levels'] == [1, 2, 3] and header['entered_level'] == 4 and
            header['cpp_expectations_used'] is False and header['gameplay_state_injections'] is False and
            header['full_ds_snapshots_published'] is False and header['initial_rng_controlled'] is True and
            header['normalized_control_bank_inputs'] is True and header['audio'] == 'dummy' and
            all(header[key] is value for key, value in CLAIMS.items()), 'bridge-escape reference claims differ')
    require(audit['schema'] == 'lezac-native-bridge-escape-ds-audit-v1' and audit['boundaries'] == FRAMES * 2 and
            audit['ds_redecode_differences'] == audit['full_guest_ram_exports'] == 0 and
            audit['excluded_from_ds_redecode'] == ['mapped.tiles_hex', 'mapped.words_hex', 'mapped.palette'] and
            audit['raw_ds_snapshots_published'] is False and len(audit['records']) == FRAMES * 2,
            'bridge-escape independent audit differs')
    first_sequence = audit['records'][0]['native_sequence']
    for index, (row, checked) in enumerate(zip(rows[1:-1], audit['records'])):
        tick, phase = FIRST + index // 2, ('present', 'post_update')[index % 2]
        require(set(row) == {'kind', 'section', 'index', 'phase', 'projection', 'rgb_sha256'} and
                (row['kind'], row['section'], row['index'], row['phase']) == ('boundary', 'level4', tick, phase) and
                (checked['index'], checked['phase'], checked['native_sequence']) ==
                    (tick, phase, first_sequence + 3 * (index // 2) + index % 2) and
                hashlib.sha256(original.json_bytes(row['projection'])).hexdigest() == checked['projection_sha256'] and
                row['rgb_sha256'] == checked['rgb_sha256'] and len(bytes.fromhex(checked['ds_sha256'])) == 32,
                'bridge-escape audited boundary differs')
        require((phase == 'post_update' and row['rgb_sha256'] is None) or
                (phase == 'present' and len(bytes.fromhex(row['rgb_sha256'])) == 32), 'bridge-escape RGB digest differs')
        mapped = row['projection']['mapped']
        require(set(row['projection']) == {'mapped', 'lifecycle', 'monsters', 'markers', 'terrain'} and
                mapped['level'] == 4 and mapped['frame'] == tick - 1623 and mapped['progress'] == [3, 261],
                'bridge-escape native state scope differs')
    final = rows[-2]['projection']['mapped']
    player = final['players'][0]
    require(player['xy'] == [770.0, 360.0] and player['velocity'] == [0, 0] and player['energy'] == 10 and
            player['reserve'] == 0 and player['inventory'] == [199, 3, 0, 0, 1] and final['rng'] == 1643317468 and
            not rows[-2]['projection']['terrain']['collapse'], 'bridge-escape endpoint differs')


def fixture():
    metadata = manifest()
    for directory, key in ((FIXTURE, 'fixture_pins'), (EVIDENCE, 'evidence_file_pins')):
        for name, digest in metadata[key].items():
            require(fidelity.sha256(fidelity.safe_file(directory, name)) == digest, 'bridge-escape pinned bytes differ: ' + name)
    for name, digest in {**metadata['producer_pins'], **metadata['guard_producer_pins']}.items():
        require(hashlib.sha256(gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes())).hexdigest() == digest,
                'bridge-escape frozen source differs: ' + name)
    read_canonical_assets(ROOT)
    rows = handoff.load(FIXTURE / 'reference.jsonl.gz')
    require(rows[0]['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS},
            'bridge-escape original assets differ')
    capture = fidelity.strict_json(gzip.decompress((EVIDENCE / 'capture-report.json.gz').read_bytes()).decode())
    binding = fidelity.strict_json(gzip.decompress((EVIDENCE / 'host-binding.json.gz').read_bytes()).decode())
    audit = fidelity.strict_json(gzip.decompress((EVIDENCE / 'native-audit.json.gz').read_bytes()).decode())
    validate_capture(metadata, capture, binding)
    validate(rows, metadata, audit)
    rea = fidelity.strict_json(gzip.decompress((EVIDENCE / 'rea-report.json.gz').read_bytes()).decode())
    require(rea['status'] == 'completed' and rea['target_sha256'] == original.EXE_SHA256 and
            rea['session_closed'] is True and rea['server_exit_code'] == 0 and
            rea['target_preserved'] is True and rea['rea_version'] == '6.7.0' and
            rea['source_sha256'] == metadata['producer_pins']['rea_prefix_audit.py'] and
            rea['provider']['id'] == 'ghidra' and rea['provider']['version'] == '12.1.4',
            'bridge-escape REA session differs')
    instructions = fidelity.strict_json(gzip.decompress((EVIDENCE / 'rea-byte-checks.json.gz').read_bytes()).decode())
    require([row['offset'] for row in instructions] == [0x6967, 0x6970, 0x697c, 0x6986, 0x698d, 0x699a, 0x69a1,
                0x69b6, 0x6a4a, 0x6a61, 0x6a68, 0x6a6f, 0x6a76], 'bridge-escape instruction scope differs')
    image = original.check_executable(ROOT / 'LEZAC.EXE')
    for row in instructions:
        code = bytes.fromhex(row['decoded']['bytes'])
        require(code == image[row['offset']:row['offset'] + len(code)] and row['bytes_equal'] is True,
                'bridge-escape original instruction bytes differ')
    previous = prior.fixture()
    require(all(rows[i]['projection'] == previous[-4 + i]['projection'] for i in (1, 2)),
            'bridge-escape original anchor differs')
    check_route(FIXTURE / 'route.txt')
    return rows


def compare(cpp):
    rows = fixture()
    wanted = {(row['index'], row['phase']): row for row in rows[1:-1]}
    settings, events = check_route(cpp / 'route.txt')
    count = frames = boundaries = 0
    previous = footer = None
    order = ('input', 'present', 'after_nonplayers', 'post_update')
    run = cpp / 'run'
    with (run / 'trace.jsonl').open() as stream:
        header = fidelity.strict_json(next(stream))
        require(set(header) == fidelity.HEADER_KEYS | {'capture_from_tick', 'candidate_only'} and
                header['kind'] == 'header' and header['schema'] == 'lezac.level1.scout.v1' and header['source'] == 'cpp' and
                header['ticks'] == LAST and header['capture_from_tick'] == FIRST and
                header['phase_model'] == 'cpp-pre-actors-v2' and header['state_scope'] == 'level1-observations-v2' and
                header['input_model'] == 'sdl-events-original-intro-wait-v1' and
                header['seed'] == settings['seed'] and header['step_us'] == settings['step_us'] and
                header['route_fnv1a64'] == fidelity.fnv1a64((cpp / 'route.txt').read_bytes()) and
                header['asset_fnv1a64'] == {name: fidelity.fnv1a64((ROOT / name).read_bytes()) for name in fidelity.ASSETS} and
                (header['width'], header['height']) == (320, 200) and header['candidate_only'] is True and
                header['original_fidelity_claim'] is False, 'bridge-escape C++ header differs')
        for line in stream:
            row = fidelity.strict_json(line)
            require(footer is None, 'bridge-escape data after footer')
            if row['kind'] == 'complete':
                require(set(row) == {'kind', 'ticks', 'frames', 'retained_checkpoints', 'checkpoints', 'events',
                    'capture_from_tick', 'candidate_only', 'level1_route_complete', 'original_fidelity_claim',
                    'port_functionally_complete'} and count == FRAMES * 4 and row['ticks'] == LAST and row['frames'] == FRAMES and
                    row['retained_checkpoints'] == count and row['checkpoints'] == previous + 1 and
                    row['events'] == sum(map(len, events.values())) and row['capture_from_tick'] == FIRST and
                    row['candidate_only'] is True and row['level1_route_complete'] is True and
                    row['original_fidelity_claim'] is False and row['port_functionally_complete'] is False,
                    'bridge-escape C++ footer differs')
                footer = row
                continue
            tick, phase = FIRST + count // 4, order[count % 4]
            require(row['kind'] == 'checkpoint' and (row['tick'], row['phase']) == (tick, phase) and tick <= LAST and
                    (previous is None or row['seq'] == previous + 1), 'bridge-escape C++ phase differs')
            keys = {'kind', 'seq', 'tick', 'phase', 'time_ms', 'events', 'state'}
            if phase == 'present':
                keys.update(('frame', 'rgb_fnv1a64'))
            require(set(row) == keys and row['events'] == events.get(tick - 1, []) and
                    row['time_ms'] == (tick - 1) * settings['step_us'] // 1000, 'bridge-escape C++ input/time differs')
            fidelity.validate_state(row['state'])
            if phase in ('present', 'post_update'):
                support.recovered.check_cpp(row['state'], wanted[tick, phase])
                boundaries += 1
            if phase == 'present':
                require(row['frame'] == f'frame_{tick:06d}.ppm', 'bridge-escape RGB filename differs')
                pixels = fidelity.read_ppm(fidelity.safe_file(run, row['frame']))
                require(fidelity.fnv1a64(pixels) == row['rgb_fnv1a64'] and
                        hashlib.sha256(pixels).hexdigest() == wanted[tick, phase]['rgb_sha256'],
                        'bridge-escape original RGB differs')
                frames += 1
            previous, count = row['seq'], count + 1
    require(footer is not None and (frames, boundaries) == (FRAMES, FRAMES * 2), 'bridge-escape C++ window incomplete')
    return dict(status='match', frames=frames, boundaries=boundaries, checkpoints=count, pixels=frames * 64000,
        expected_bytes_source='original_only', comparison_scope=f'{FIRST}-{LAST} only; projected fields and full RGB',
        final_destroyed=261, remaining_for_threshold=44, gameplay_state_injections=False, **CLAIMS)


def replay(exe, out):
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    case = out.resolve() / ('run-' + uuid.uuid4().hex)
    case.mkdir(parents=True)
    try:
        require(exe.is_file(), 'bridge-escape executable missing')
        shutil.copyfile(FIXTURE / 'route.txt', case / 'route.txt')
        fixture()
        assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
        command = [str(exe.resolve()), '--replay-level1-scout', str(case / 'route.txt'), str(case / 'run'),
                   str(FIRST), '--original-intro-wait', '--result-reels']
        (case / 'command.json').write_bytes(original.json_bytes(dict(command=command, assets=assets,
            executable_sha256=fidelity.sha256(exe), reader_sha256=fidelity.sha256(Path(__file__)),
            audio='dummy', video='dummy', gameplay_state_injections=False, **CLAIMS)))
        with tempfile.TemporaryDirectory(prefix='assets-', dir=case) as temporary:
            for name in fidelity.ASSETS:
                shutil.copyfile(ROOT / name, Path(temporary) / name)
            try:
                child = subprocess.run(command, cwd=temporary, capture_output=True, text=True, timeout=550,
                    env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                        LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1'))
            except subprocess.TimeoutExpired as error:
                for name, value in (('stdout.txt', error.stdout), ('stderr.txt', error.stderr)):
                    value = value.decode(errors='replace') if isinstance(value, bytes) else value or ''
                    (case / name).write_text(value, encoding='utf-8')
                (case / 'child-result.json').write_bytes(original.json_bytes(dict(exit_code=None, timed_out=True)))
                raise
            for name, value in (('stdout.txt', child.stdout), ('stderr.txt', child.stderr)):
                (case / name).write_text(value, encoding='utf-8')
            (case / 'child-result.json').write_bytes(original.json_bytes(dict(exit_code=child.returncode)))
            require(child.returncode == 0, 'bridge-escape C++ replay failed: ' + child.stderr[-1800:])
        require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'bridge-escape replay changed assets')
        report = compare(case)
    except BaseException as error:
        (case / 'comparison.json').write_bytes(original.json_bytes(dict(status='failed', error=str(error), **CLAIMS)))
        raise
    (case / 'comparison.json').write_bytes(original.json_bytes(report))
    return report


def guard():
    rows = fixture()
    wanted = {(row['index'], row['phase']): row for row in rows[1:-1]}
    inputs = handoff.load(FIXTURE / 'guard-inputs.jsonl.gz')
    require([row['index'] for row in inputs] == INDICES and
            all(row['kind'] == 'cpp_typed_mutation_stimulus_only' and row['phase'] == 'post_update' for row in inputs),
            'bridge-escape mutation stimulus scope differs')
    rejected = 0
    for row in inputs:
        state, expected = row['state'], wanted[row['index'], row['phase']]
        support.recovered.check_cpp(state, expected)
        rejected += support.recovered.guard_cpp(state, expected)
        paths = [('logic_tick',), ('players', 0, 'animation', 0), ('players', 0, 'hud_score', 0)]
        if state['monsters']:
            paths += [('monsters', 0, 'position', 0), ('monsters', 0, 'motion', 0)]
        if state['debris']:
            paths.append(('debris', 0, 0))
        if state['collapse']:
            paths.append(('collapse', 0, 2))
        for path in paths:
            changed = copy.deepcopy(state)
            target = changed
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] += 1
            try:
                support.recovered.check_cpp(changed, expected)
            except fidelity.EvidenceError:
                rejected += 1
            else:
                raise fidelity.EvidenceError('bridge-escape typed mutation accepted: ' + str(path))
    return dict(status='guarded', stimuli=len(inputs), typed_mutations_rejected=rejected,
                expected_bytes_source='original_only', **CLAIMS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('replay', 'compare', 'guard'))
    for name in ('exe', 'out', 'cpp'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.command == 'replay':
        require(args.exe is not None and args.out is not None, 'bridge-escape executable/output required')
        report = replay(args.exe, args.out)
    elif args.command == 'compare':
        require(args.cpp is not None, 'bridge-escape C++ evidence required')
        report = compare(args.cpp)
    else:
        report = guard()
    print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
