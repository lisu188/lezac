"""Original-only full-frame regression for the Level 4 outside-column route."""
from __future__ import annotations

import argparse
import configparser
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

import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original
import natural_level4_support_column as support
from original_capture_contract import ASSET_PINS

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level4_outside_column'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level4_outside_column_20261103'
FIRST, LAST, FRAMES, PLACEMENT = 11300, 12100, 801, 11843
MANIFEST_SHA256 = 'd33679b186e5ef17636c53b59e66ada5a4b9bb9bbb9847162279b689f504f6ff'
ROUTE_SHA256 = '5007fb684c11a1e8d3affeb94645275ef6d0b9fa832462ad73c96605ad3feead'
TRANSITIONS = [(11300, 230), (11301, 237), (11310, 244), (11958, 255), (11972, 261)]
HOST_PIN = dict(path='/usr/bin/dosbox', bytes=2621536, package_version='0.74-3-5build2',
                sha256='9213fb131e11cb195bdff40c24513740ce497c5caf1cef1900ad1faad5c5026b')
CLAIMS = dict(original_fidelity_claim=False, whole_game_fidelity_claim=False,
              all_actor_fields_compared=False, manual_input_claim=False, wall_clock_claim=False,
              level4_completion_claim=False)
require = fidelity.require


def manifest():
    path = EVIDENCE / 'manifest.json'
    require(fidelity.sha256(path) == MANIFEST_SHA256, 'outside-column manifest fingerprint differs')
    metadata = fidelity.strict_json(path.read_text())
    require(metadata['schema'] == 'lezac-native-level4-outside-column-evidence-v1' and
            metadata['expected_bytes_source'] == 'original_only' and metadata['native_sessions_closed'] is True and
            metadata['original_snapshot_ds_redecode_boundaries'] == 1602 and
            metadata['raw_ds_snapshot_retention'] == 'RAM-only; not claimed durably retained' and
            metadata['full_guest_ram_exports'] == metadata['core_dumps'] == 0,
            'outside-column native provenance/scope differs')
    require(metadata['original_exe_sha256'] == original.EXE_SHA256 and metadata['original_exe_bytes'] == 52384,
            'outside-column original target differs')
    require(metadata['guard_input_source']['kind'] == 'cpp_typed_mutation_stimulus_only' and
            metadata['guard_input_source']['expected_bytes_source'] is False and
            metadata['guard_input_source']['indices'] == [11300, 11958, 12100] and
            metadata['guard_input_source']['phase'] == 'post_update', 'outside-column guard scope differs')
    groups = [set(metadata[key]) for key in ('producer_pins', 'guard_producer_pins', 'repeat_producer_pins')]
    require(sum(map(len, groups)) == len(set.union(*groups)), 'native and C++ guard producer roles overlap')
    return metadata


def check_route(path):
    require(fidelity.sha256(path) == ROUTE_SHA256, 'outside-column route fingerprint differs')
    settings, events = fidelity.read_route(path)
    prior_settings, prior = support.third.check_route(support.third.FIXTURE / 'route.txt')
    require(settings == {**prior_settings, 'ticks': LAST} and
            {tick: items for tick, items in events.items() if tick < FIRST} ==
            {tick: items for tick, items in prior.items() if tick < FIRST} and
            events[FIRST] == [dict(action='up', key='c')], 'outside-column ordinary prefix differs')
    return settings, events


def validate(rows, metadata, audit):
    require(len(rows) == 1604 and rows[0] == metadata['reference_header'] and
            rows[-1] == dict(kind='complete', frames=FRAMES, boundaries=1602, patches_restored=True),
            'outside-column reference extent/header differs')
    header = rows[0]
    require(header['schema'] == 'lezac-natural-level4-outside-column-v1' and
            (header['first_tick'], header['last_tick'], header['frames'], header['boundaries']) ==
            (FIRST, LAST, FRAMES, 1602) and header['dimensions'] == [100, 58] and
            header['native_frame_offset'] == 1623 and header['placement_tick'] == PLACEMENT and
            header['route_sha256'] == ROUTE_SHA256 and header['expected_bytes_source'] == 'original_only' and
            header['cpp_expectations_used'] is False and header['completed_levels'] == [1, 2, 3] and
            header['entered_level'] == 4 and header['initial_rng_controlled'] is True and
            header['normalized_control_bank_inputs'] is True and header['gameplay_state_injections'] is False and
            header['audio'] == 'dummy' and all(header[key] is value for key, value in CLAIMS.items()) and
            header['retained_observation_scope'] == 'projected-boundaries-and-rgb-fingerprints' and
            header['full_ds_snapshots_published'] is False and header['heap_planes_retained_as_sha256_only'] is True and
            header['prior_original_anchor'] == dict(manifest_sha256=support.third.MANIFEST_SHA256, tick=FIRST),
            'outside-column reference claim differs')
    require(audit['schema'] == 'lezac-native-outside-column-ds-audit-v1' and audit['boundaries'] == 1602 and
            audit['ds_derived_mapped_and_actor_terrain_differences'] == 0 and
            audit['excluded_from_ds_redecode'] == ['mapped.tiles_hex', 'mapped.words_hex', 'mapped.palette'] and
            audit['rgb_source'] == 'original_full_320x200_png' and audit['raw_ds_snapshots_published'] is False and
            audit['observation_method'] == 'owned_process_stopped_for_ds_and_heap_reads' and
            len(audit['records']) == 1602, 'outside-column native audit differs')
    first_sequence = audit['records'][0]['native_sequence']
    for index, (row, checked) in enumerate(zip(rows[1:-1], audit['records'])):
        tick, phase = FIRST + index // 2, ('present', 'post_update')[index % 2]
        require(set(row) == {'kind', 'section', 'index', 'phase', 'projection', 'rgb_sha256'} and
                (row['kind'], row['section'], row['index'], row['phase']) == ('boundary', 'level4', tick, phase),
                'outside-column reference order differs')
        require((checked['index'], checked['phase'], checked['native_sequence']) ==
                (tick, phase, first_sequence + 3 * (index // 2) + index % 2) and
                hashlib.sha256(original.json_bytes(row['projection'])).hexdigest() == checked['projection_sha256'] and
                row['rgb_sha256'] == checked['rgb_sha256'], 'outside-column audited boundary differs')
        require(len(bytes.fromhex(checked['ds_sha256'])) == 32 and
                ((phase == 'post_update' and row['rgb_sha256'] is None) or
                 (phase == 'present' and isinstance(row['rgb_sha256'], str) and
                  len(bytes.fromhex(row['rgb_sha256'])) == 32)), 'outside-column native/RGB digest differs')
        projection = row['projection']
        require(set(projection) == {'mapped', 'lifecycle', 'monsters', 'markers', 'terrain'},
                'outside-column projection scope differs')
        mapped, player = projection['mapped'], projection['mapped']['players'][0]
        destroyed = next(value for at, value in reversed(TRANSITIONS)
                         if tick > at or (tick == at and (phase == 'post_update' or at == FIRST)))
        medium = 4 if tick > PLACEMENT or (tick == PLACEMENT and phase == 'post_update') else 5
        require(mapped['level'] == 4 and mapped['frame'] == tick - 1623 and mapped['progress'] == [3, destroyed] and
                player['reserve'] == 0 and 0 < player['energy'] <= 22 and
                player['inventory'] == [200, medium, 0, 0, 1], 'outside-column native gameplay differs')
    final = rows[-2]['projection']['mapped']
    require(final['players'][0]['xy'] == [56.0, 352.0] and final['players'][0]['energy'] == 10 and
            final['rng'] == 171766152 and not rows[-2]['projection']['terrain']['collapse'],
            'outside-column endpoint differs')


def validate_repeat(binding, capture, audit, metadata, rows, config):
    repeat = metadata['repeat_capture']
    require(binding.get('schema') == 'lezac-native-outside-column-host-binding-v1' and
            binding.get('host') == repeat['host'] == HOST_PIN and
            binding.get('actual_host_sha256') == HOST_PIN['sha256'], 'outside-column repeat host differs')
    require(repeat['frames'] == FRAMES and repeat['boundaries'] == 1602 and repeat['reference_unchanged'] is True and
            repeat['reference_sha256'] == metadata['fixture_pins']['reference.jsonl.gz'] and
            repeat['raw_ds_snapshots_published'] is False, 'outside-column repeat scope differs')
    root = PurePosixPath(repeat['source_capture'])
    require(root.is_absolute() and root.is_relative_to('/dev/shm') and '..' not in root.parts,
            'outside-column repeat RAM root differs')
    expected_argv = ['dosbox', '-conf', str(root / 'dosbox.conf'), '-c', 'mount c ' + str(root / 'runtime'),
                     '-c', 'c:', '-c', 'L1ORACLE.COM', '-c', 'LEZAC.EXE']
    require(binding['argv'] == expected_argv and binding['cwd'] == str(root.parent) and binding['actual_pid'] > 0,
            'outside-column repeat launch differs')
    require(hashlib.sha256(config).hexdigest() == binding['config_sha256'] == repeat['config_sha256'] and
            binding['loader_sha256'] == repeat['loader_sha256'] ==
            hashlib.sha256(original.resident_program()).hexdigest(), 'outside-column repeat config/loader differs')
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(config.decode('ascii'))
    require(not parser.defaults() and {name: dict(parser[name]) for name in parser.sections()} == dict(
        sdl=dict(fullscreen='false', output='surface'), dosbox=dict(memsize='16'),
        render=dict(frameskip='0', aspect='false', scaler='none'), cpu=dict(core='normal', cycles='fixed 6000')),
        'outside-column repeat DOSBox configuration differs')
    canonical = {name: dict(bytes=size, sha256=digest) for name, (size, digest) in ASSET_PINS.items()}
    require(binding['canonical_source_assets'] == canonical and binding['omitted_installation_log'] == 'SETUP.LOG' and
            binding['copied_assets'] == {name: value for name, value in canonical.items() if name != 'SETUP.LOG'},
            'outside-column repeat canonical asset domain differs')
    environment = binding['environment']
    require(set(environment) == {'DISPLAY', 'SDL_AUDIODRIVER', 'SDL_VIDEODRIVER', 'TMPDIR', 'TMP', 'TEMP'} and
            environment['SDL_AUDIODRIVER'] == 'dummy' and environment['SDL_VIDEODRIVER'] is None and
            re.fullmatch(r':\d+(?:\.\d+)?', environment['DISPLAY']) is not None and
            all(PurePosixPath(environment[key]).is_relative_to(root.parent) and
                '..' not in PurePosixPath(environment[key]).parts for key in ('TMPDIR', 'TMP', 'TEMP')),
            'outside-column repeat environment differs')
    geometry = binding['geometry']
    require(set(geometry) == {'WINDOW', 'X', 'Y', 'WIDTH', 'HEIGHT', 'SCREEN'} and int(geometry['WINDOW']) > 0 and
            [int(geometry[key]) for key in ('WIDTH', 'HEIGHT', 'SCREEN')] == [320, 200, 0] and
            0 <= int(geometry['X']) <= 320 and 0 <= int(geometry['Y']) <= 280,
            'outside-column repeat private-window geometry differs')
    prefix = binding['prefix_header']
    prefix_settings, _ = original.read_route(ROOT / 'tests/fixtures/level1_original/completion_gate/route.txt')
    require(prefix['dosbox_sha256'] == HOST_PIN['sha256'] and prefix['exe_sha256'] == original.EXE_SHA256 and
            prefix['source_sha256'] == metadata['producer_pins']['level1_original.py'] and
            prefix['settings'] == prefix_settings and prefix['initial_rng'] == original.initial_seed(prefix_settings['seed']) and
            prefix['dimensions'] == [320, 200] and prefix['original_fidelity_claim'] is False and
            prefix['hooks'] == [[at, code] for at, code in original.HOOKS] and
            prefix['preview_draws'] == 390 and prefix['prefix_ticks'] == 3,
            'outside-column repeat prefix provenance differs')
    require(capture['status'] == 'original_continuation_observed' and
            all(capture[key] is True for key in ('base_hooks_restored', 'extra_hooks_restored', 'owned_child_terminal',
                'protected_inputs_preserved', 'initial_rng_controlled', 'normalized_control_bank_inputs',
                'ordinary_gameplay_inputs_only')) and
            all(capture[key] == 0 for key in ('gameplay_state_injections', 'full_guest_ram_exports', 'core_dumps',
                'manual_input_claim', 'wall_clock_claim', 'whole_game_fidelity_claim')) and
            binding['whole_game_fidelity_claim'] is False and
            capture['observer_sha256'] == binding['observer_sha256'] ==
                metadata['repeat_producer_pins']['capture-outside-column-host-bound-t300.py'] and
            capture['base_observer_sha256'] == binding['base_observer_sha256'] ==
                metadata['producer_pins']['capture-level4-continuation-t298.py'] and
            capture['route_sha256'] == ROUTE_SHA256 and capture['original_exe_sha256'] == original.EXE_SHA256,
            'outside-column repeat producer/closure differs')
    require(audit['schema'] == 'lezac-native-outside-column-bound-repeat-v1' and
            (audit['frames'], audit['boundaries']) == (FRAMES, 1602) and
            audit['original_reference_unchanged'] is True and audit['raw_ds_snapshots_published'] is False and
            audit['projected_differences'] == audit['rgb_differences'] == audit['ds_redecode_differences'] == 0 and
            len(audit['records']) == 1602, 'outside-column repeat audit differs')
    first = audit['records'][0]['native_sequence']
    for index, (row, repeated) in enumerate(zip(rows[1:-1], audit['records'])):
        require((repeated['index'], repeated['phase'], repeated['native_sequence']) ==
                (row['index'], row['phase'], first + 3 * (index // 2) + index % 2) and
                repeated['projection_sha256'] == hashlib.sha256(original.json_bytes(row['projection'])).hexdigest() and
                repeated['rgb_sha256'] == row['rgb_sha256'] and len(bytes.fromhex(repeated['ds_sha256'])) == 32,
                'outside-column host-bound repeated boundary differs')


def fixture(root=FIXTURE):
    metadata = manifest()
    for name, digest in metadata['fixture_pins'].items():
        require(fidelity.sha256(fidelity.safe_file(root, name)) == digest, 'outside-column fixture fingerprint differs: ' + name)
    for name, digest in metadata['evidence_file_pins'].items():
        require(fidelity.sha256(fidelity.safe_file(EVIDENCE, name)) == digest, 'outside-column evidence fingerprint differs: ' + name)
    for name, digest in {**metadata['producer_pins'], **metadata['guard_producer_pins'],
                         **metadata['repeat_producer_pins']}.items():
        require(hashlib.sha256(gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes())).hexdigest() == digest,
                'outside-column frozen producer differs: ' + name)
    capture = fidelity.strict_json(gzip.decompress((EVIDENCE / 'capture-report.json.gz').read_bytes()).decode())
    require(hashlib.sha256(gzip.decompress((EVIDENCE / 'capture-report.json.gz').read_bytes())).hexdigest() ==
            metadata['native_capture_report_sha256'] and capture['status'] == 'original_continuation_observed' and
            all(capture[key] is True for key in ('base_hooks_restored', 'extra_hooks_restored',
                'owned_child_terminal', 'protected_inputs_preserved', 'initial_rng_controlled',
                'normalized_control_bank_inputs', 'ordinary_gameplay_inputs_only')) and
            all(capture[key] == 0 for key in ('gameplay_state_injections', 'full_guest_ram_exports',
                'core_dumps', 'manual_input_claim', 'wall_clock_claim', 'whole_game_fidelity_claim')) and
            capture['observer_sha256'] == metadata['producer_pins']['capture-level4-outside-pillar-t299.py'] and
            capture['base_observer_sha256'] == metadata['producer_pins']['capture-level4-continuation-t298.py'] and
            capture['original_exe_sha256'] == original.EXE_SHA256 and
            capture['route_sha256'] == ROUTE_SHA256, 'outside-column original capture is not qualified')
    require([(r['from_level'], r['to_level'], r['intro_frame'], r['intro_rng']) for r in capture['handoffs']] ==
            [(1, 2, 305, 2497022769), (2, 3, 2669, 3666694644), (3, 4, 7798, 1603369198)],
            'outside-column original campaign handoffs differ')
    check_route(root / 'route.txt')
    rows = handoff.load(root / 'reference.jsonl.gz')
    audit = fidelity.strict_json(gzip.decompress((EVIDENCE / 'native-audit.json.gz').read_bytes()).decode())
    validate(rows, metadata, audit)
    require(rows[0]['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS},
            'outside-column original assets differ')
    baseline = {row['phase']: row['projection'] for row in support.third.fixture()[1:-1]
                if row['section'] == 'level4' and row['index'] == FIRST}
    require(all(row['projection'] == baseline[row['phase']] for row in rows[1:3]),
            'outside-column original fork anchor differs')
    rea = fidelity.strict_json(gzip.decompress((EVIDENCE / 'rea-report.json.gz').read_bytes()).decode())
    require(rea['status'] == 'completed' and rea['target_sha256'] == original.EXE_SHA256 and
            rea['session_closed'] is True and rea['server_exit_code'] == 0 and
            rea['provider']['id'] == 'ghidra' and rea['provider']['version'] == '12.1.4',
            'outside-column REA/Ghidra audit differs')
    image = original.check_executable(ROOT / 'LEZAC.EXE')
    instructions = fidelity.strict_json(gzip.decompress((EVIDENCE / 'rea-byte-checks.json.gz').read_bytes()).decode())
    require([row['offset'] for row in instructions] == [0x5999, 0x59aa, 0x59b5, 0x59ba, 0x59f2, 0x5a00, 0x68ec, 0x690c],
            'outside-column portal instruction scope differs')
    for instruction in instructions:
        code = bytes.fromhex(instruction['decoded']['bytes'])
        at = instruction['offset']
        require(code == image[at:at + len(code)] and instruction['bytes_equal'] is True,
                'outside-column portal instruction bytes differ')
    repeat_binding = fidelity.strict_json(gzip.decompress((EVIDENCE / 'repeat-host-binding.json.gz').read_bytes()).decode())
    repeat_capture = fidelity.strict_json(gzip.decompress((EVIDENCE / 'repeat-capture-report.json.gz').read_bytes()).decode())
    repeat_audit = fidelity.strict_json(gzip.decompress((EVIDENCE / 'repeat-audit.json.gz').read_bytes()).decode())
    validate_repeat(repeat_binding, repeat_capture, repeat_audit, metadata, rows,
                    (EVIDENCE / 'repeat-dosbox.conf').read_bytes())
    return rows


def compare(cpp):
    rows = fixture()
    settings, events = check_route(cpp / 'route.txt')
    wanted = {(row['index'], row['phase']): row for row in rows[1:-1]}
    run = cpp / 'run'
    order = ('input', 'present', 'after_nonplayers', 'post_update')
    count = frames = boundaries = 0
    previous = None
    footer = None
    with (run / 'trace.jsonl').open(encoding='utf-8') as stream:
        header = fidelity.strict_json(next(stream))
        require(set(header) == fidelity.HEADER_KEYS | {'capture_from_tick', 'candidate_only'} and
                header['kind'] == 'header' and header['schema'] == 'lezac.level1.scout.v1' and
                header['source'] == 'cpp' and header['capture_from_tick'] == FIRST and header['ticks'] == LAST and
                header['phase_model'] == 'cpp-pre-actors-v2' and header['state_scope'] == 'level1-observations-v2' and
                header['input_model'] == 'sdl-events-original-intro-wait-v1' and
                header['seed'] == settings['seed'] and header['step_us'] == settings['step_us'] and
                header['route_fnv1a64'] == fidelity.fnv1a64((cpp / 'route.txt').read_bytes()) and
                header['asset_fnv1a64'] == {name: fidelity.fnv1a64((ROOT / name).read_bytes()) for name in fidelity.ASSETS} and
                (header['width'], header['height']) == (320, 200) and header['candidate_only'] is True and
                header['original_fidelity_claim'] is False, 'outside-column C++ capture provenance differs')
        for line in stream:
            row = fidelity.strict_json(line)
            require(footer is None, 'outside-column data after footer')
            if row['kind'] == 'complete':
                require(set(row) == {'kind', 'ticks', 'frames', 'retained_checkpoints', 'checkpoints', 'events',
                            'capture_from_tick', 'candidate_only', 'level1_route_complete',
                            'original_fidelity_claim', 'port_functionally_complete'} and
                        count == FRAMES * 4 and row['ticks'] == LAST and row['frames'] == FRAMES and
                        row['retained_checkpoints'] == count and row['checkpoints'] == previous + 1 and
                        row['events'] == sum(map(len, events.values())) and row['capture_from_tick'] == FIRST and
                        row['candidate_only'] is True and row['level1_route_complete'] is True and
                        row['original_fidelity_claim'] is False and row['port_functionally_complete'] is False,
                        'outside-column C++ footer differs')
                footer = row
                continue
            tick, phase = FIRST + count // 4, order[count % 4]
            require(row['kind'] == 'checkpoint' and (row['tick'], row['phase']) == (tick, phase) and tick <= LAST and
                    (previous is None or row['seq'] == previous + 1), 'outside-column C++ phase/sequence differs')
            expected_keys = {'kind', 'seq', 'tick', 'phase', 'time_ms', 'events', 'state'}
            if phase == 'present':
                expected_keys.update(('frame', 'rgb_fnv1a64'))
            require(set(row) == expected_keys and row['events'] == events.get(tick - 1, []) and
                    row['time_ms'] == (tick - 1) * settings['step_us'] // 1000,
                    'outside-column C++ input/time fields differ')
            fidelity.validate_state(row['state'])
            if phase in ('present', 'post_update'):
                support.recovered.check_cpp(row['state'], wanted[tick, phase])
                boundaries += 1
            if phase == 'present':
                require(row['frame'] == f'frame_{tick:06d}.ppm', 'outside-column C++ RGB filename differs')
                pixels = fidelity.read_ppm(fidelity.safe_file(run, row['frame']))
                require(fidelity.fnv1a64(pixels) == row['rgb_fnv1a64'] and
                        hashlib.sha256(pixels).hexdigest() == wanted[tick, phase]['rgb_sha256'],
                        'outside-column original RGB differs')
                frames += 1
            previous, count = row['seq'], count + 1
    require(footer is not None and (frames, boundaries) == (FRAMES, FRAMES * 2), 'outside-column C++ window incomplete')
    return dict(status='match', frames=frames, boundaries=boundaries, pixels=frames * 64000,
        checkpoints=count, final_destroyed=261, remaining_for_threshold=44, expected_bytes_source='original_only',
        comparison_scope='11300-12100 only; projected fields and full RGB',
        results_reels_compared=False, gameplay_state_injections=False, **CLAIMS)


def replay(exe, out):
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    case = out.resolve() / ('run-' + uuid.uuid4().hex)
    case.mkdir(parents=True)
    try:
        require(exe.is_file(), 'outside-column executable missing')
        shutil.copyfile(FIXTURE / 'route.txt', case / 'route.txt')
        assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
        command = [str(exe.resolve()), '--replay-level1-scout', str(case / 'route.txt'), str(case / 'run'),
                   str(FIRST), '--original-intro-wait', '--result-reels']
        (case / 'command.json').write_bytes(original.json_bytes(dict(command=command,
            executable_sha256=fidelity.sha256(exe), reader_sha256=fidelity.sha256(Path(__file__)),
            assets=assets, audio='dummy', video='dummy', gameplay_state_injections=False, **CLAIMS)))
        fixture()
        with tempfile.TemporaryDirectory(prefix='assets-', dir=case) as temporary:
            runtime = Path(temporary)
            for name in fidelity.ASSETS:
                shutil.copyfile(ROOT / name, runtime / name)
            try:
                child = subprocess.run(command, cwd=runtime, capture_output=True, text=True, timeout=550,
                    env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                        LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1'))
            except subprocess.TimeoutExpired as error:
                for name, value in (('stdout.txt', error.stdout), ('stderr.txt', error.stderr)):
                    value = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
                    (case / name).write_text(value, encoding='utf-8')
                (case / 'child-result.json').write_bytes(original.json_bytes(dict(exit_code=None, timed_out=True)))
                raise
            for name, data in (('stdout.txt', child.stdout), ('stderr.txt', child.stderr)):
                (case / name).write_text(data, encoding='utf-8')
            (case / 'child-result.json').write_bytes(original.json_bytes(dict(exit_code=child.returncode)))
            require(child.returncode == 0, 'outside-column C++ replay failed: ' + child.stderr[-1800:])
        require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'outside-column replay changed assets')
        report = compare(case)
    except BaseException as error:
        (case / 'comparison.json').write_bytes(original.json_bytes(dict(status='failed', error=str(error), **CLAIMS)))
        raise
    (case / 'comparison.json').write_bytes(original.json_bytes(report))
    return report


def guard():
    rows = fixture()
    wanted = {(row['index'], row['phase']): row for row in rows[1:-1]}
    stimuli = handoff.load(FIXTURE / 'guard-inputs.jsonl.gz')
    require([row['index'] for row in stimuli] == [11300, 11958, 12100] and
            all(row['kind'] == 'cpp_typed_mutation_stimulus_only' and row['phase'] == 'post_update' for row in stimuli),
            'outside-column C++ mutation-stimulus roles differ')
    rejected = 0
    for row in stimuli:
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
                raise fidelity.EvidenceError('outside-column typed mutation accepted: ' + str(path))
    return dict(status='guarded', typed_mutations_rejected=rejected, stimuli=len(stimuli),
                expected_bytes_source='original_only', **CLAIMS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('replay', 'compare', 'guard'))
    for name in ('exe', 'out', 'cpp'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.command == 'replay':
        require(args.exe is not None and args.out is not None, 'outside-column executable/output required')
        report = replay(args.exe, args.out)
    elif args.command == 'compare':
        require(args.cpp is not None, 'outside-column C++ evidence required')
        report = compare(args.cpp)
    else:
        report = guard()
    print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
