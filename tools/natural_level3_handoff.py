"""Original-backed ordinary Level 3 results and Level 4 handoff replay."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import uuid

import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original
import natural_campaign as campaign
import natural_level3_completion_gate as gate
import natural_level3_gate_projections as projection
import natural_level3_return as returned
import capture_original_shipped_monster_profiles as shipped

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level3_handoff'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level3_handoff_20261006'
SCHEMA = 'lezac-natural-level3-results-level4-handoff-v1'
FIRST, LAST, LEVEL4_FIRST = 8905, 9450, 9422
ROUTE_SHA256 = 'f283afd6e746f43f972dc4721139dc18e1526dd801b99168b75704737771e09f'
NATIVE_SHA256 = '01a021e68b195e49c6c9b0e5262f0eec9de345f9c84af801534c15aba3012819'
RESULTS_SHA256 = 'd8989f166d8831e4e909715bc58b23793b865cd3ebe9c6169dd997df08c32c42'
ENTRY_SHA256 = 'f86f577ff34929a2b048df5f57e159cd3b6400cce300fd59b649004dedf8550a'
RAW_SHA256 = '9af35adb416b7f31ac0233502b8387b4dc66c1e75d138b1932830f280ed96749'
REFERENCE_SHA256 = 'd97f4783a5af10afc521ec1c2c09cfcd22784a116879869e87645f032f86a05d'
GUARD_SHA256 = '559df94f74b6572654b415f6f547ca2a88ef2da89711b9e711ab0b9f3d094427'
CONTROL_PINS = {
    'common.py': '951fe90674bf682b07b4452e95409fa212fa3e6fc6da2aee8f2235f6cf9dafb7',
    'prepare.py': '09482f84a8f7f0d47301860391bc3fec2592ebb832839f0ff625fc2ec848486f',
    'capture.py': 'a42184a08c63ae9d4c614dcd0afe34636ee9a69dd7c7f9e61d6929c2c19955dc',
    'private-capture.py': '65c01489ec392d4acaf2381ac0eef211bcf244b394c1c0d3eae3e0e35f54502b',
    'retain-and-close.py': 'bef8b4cf7031c8fe09d88f927c828c2712fdb5bd2eecfdbc37cce860d2855bc9',
    'preparation-proof.json': 'c1d11a5797e36ceada904f2b218230fdf751f50f05eac1208bc38215a9bbd9ca',
    'native-audit.json': '25835f47ae09b98c668a7866125de15e18e07330776f0325f93be26445f30113',
    'capture-terminal-receipt.json': 'cb6c194849c054c0fe5473f1b41478f1f08f07f06ee0e1a9e0139229e00654f3',
    'raw-retention-complete.json': '57c2f5a68828c951336c6ec452861041c92b91588bdf5c728f48d8e9ed732b97',
    'keeper-terminal-receipt.json': '9befe6316ba292a592ef89bcc21bb8eea949fdfcef6a56693c50b436b78e43f1',
    'keeper-closure-proof.json': '9525536cc96ad1b24569d4a64a6fe6453980af7ee8d6c6d46de43f5b1cc31aab',
    'closed-controls-retention-complete.json': '37b1ec2012c73f735ebef2414e08013c3f8d1ef9578f6a5e0acb7b8301d179a4',
}
CAPTURE_PINS = {
    'capture.py': CONTROL_PINS['capture.py'],
    'objective-observer-wrapper.py': '67fbad0106d75c06652708f8ec9667d2b607665947b26d5811d05e6c1c5206f7',
    **{name: campaign.CAPTURE_PINS[name] for name in ('observer.py', 'results-observer.py',
       'extension-observer.py', 'outcome-observer.py', 'level3-handoff-observer.py')},
    'outcome-manifest.json': 'dc2779508f796b3c92b7aa37d832c51521fc84347d2476051a7709db1ed50811',
    'results-runtime-configuration.json': 'f708e91f65326ec2ad88b56b15ff7a6fbb3dc072e781ff07709bf6cf6f281273',
    'objective-input-journal.json': '35d5a0a2f6dcbf1efa4bc5935c9147b47054546b014a7e96c2ac18d7588c9e14',
    'results-handoff-ds-journal.json': 'b38117d8d3af3d4a23e2ef35d00ce53059777a75a34dd77a2b6a0a35e9b0ad4b',
}
CLAIMS = {**campaign.CLAIMS, 'full_prefix_cpp_comparison_claim': False,
          'full_actor_clock_sound_byte_parity': False, 'level4_completion_claim': False}
AUDIT_PINS = {
    'audit-native-coherence.py': '8dd2d5fa6d1cc6ae72cd0671b9ca16d892bbe738d5393f42441516b2dc8eff58',
    'native-coherence-audit.json': 'c962fe4ee0a1cdaa0030ef6de1e96264caf03f7d5b74e8b02d810327a4c2059b',
}
PROFILES = {level: {(raw[11], raw[26], slot + 1) for current, slot, _, raw in shipped.profiles()
                    if current == level} for level in (3, 4)}
require = fidelity.require


def check_pins(root, pins):
    for name, digest in pins.items():
        require(fidelity.sha256(fidelity.safe_file(root, name)) == digest, 'untrusted handoff producer: ' + name)


def check_coherence():
    check_pins(EVIDENCE, AUDIT_PINS)
    audit = fidelity.strict_json((EVIDENCE / 'native-coherence-audit.json').read_text())
    require(audit['boundaries'] == 148 and audit['normalized_bytes'] == 0 and
            audit['raw_sha256'] == RAW_SHA256 and audit['cpp_full_state_parity_claim'] is False and
            audit['differing_byte_observations'] == len(audit['differences']) == 11 and
            {row['ds_offset'] for row in audit['differences']} == {0x79a1, 0x79c4} and
            all(row['field'] == 'globals' and row['role'] == 'result' for row in audit['differences']),
            'retained native snapshot-coherence limitation changed')


def check_route(route):
    require(fidelity.sha256(route) == ROUTE_SHA256, 'handoff route fingerprint differs')
    settings, events = fidelity.read_route(route)
    prior_settings, prior_events = gate.check_route(gate.FIXTURE / 'route.txt')
    require(settings == {**prior_settings, 'ticks': LAST} and
            {tick: rows for tick, rows in events.items() if tick < FIRST} == prior_events and
            {tick: rows for tick, rows in events.items() if tick >= FIRST} == {
                9301: [dict(action='down', key='return')], 9302: [dict(action='up', key='return')],
                9421: [dict(action='down', key='return')], 9422: [dict(action='up', key='return')]},
            'ordinary route prefix or fresh Return acknowledgements differ')
    return settings, events


def metadata(assets):
    return dict(kind='header', schema=SCHEMA, first_tick=FIRST, ticks=LAST,
        result_frames=58, gameplay_frames=29, frames=90, boundaries=120, raw_ds_boundaries=148,
        repeated_native_level3_frames=5129, native_stream_sha256=NATIVE_SHA256,
        prior_native_stream_sha256=gate.NATIVE_SHA256, native_results_sha256=RESULTS_SHA256,
        native_entry_sha256=ENTRY_SHA256, raw_ds_sha256=RAW_SHA256, route_sha256=ROUTE_SHA256,
        control_pins=CONTROL_PINS, capture_pins=CAPTURE_PINS, assets=assets, audio='dummy',
        state_injections=False, completed_levels=[1, 2, 3], entered_level=4,
        original_results_and_level4_handoff_compared=True, **CLAIMS)


def native_projection(state, dac, atlas, actors=True):
    result = dict(mapped=campaign.native_boundary(state, dac, atlas), lifecycle=returned.native_lifecycle(state))
    if actors:
        level = bytes.fromhex(state['globals'])[0x17]
        result.update(monsters=projection.native_monsters(state, PROFILES[level]),
                      markers=projection.native_markers(state))
    return result


def cpp_projection(state, expected):
    result = dict(mapped=campaign.cpp_boundary(state), lifecycle=returned.cpp_lifecycle(state))
    if 'monsters' in expected:
        result.update(monsters=projection.cpp_monsters(state, PROFILES[state['level']]),
                      markers=projection.cpp_markers(state))
    if 'terrain' in expected:
        result['terrain'] = projection.cpp_terrain(state)
    return result


def boundary(section, index, phase, state, dac, atlas, rgb=None, actors=True):
    return dict(kind='boundary', section=section, index=index, phase=phase,
                projection=native_projection(state, dac, atlas, actors), rgb_sha256=rgb)


def pack(capture, control, prior, out):
    require(not out.exists(), 'fresh native handoff fixture output required')
    check_pins(control, CONTROL_PINS)
    check_pins(capture, CAPTURE_PINS)
    check_coherence()
    for name, digest in (('level3-handoff.jsonl.gz', NATIVE_SHA256), ('level3-results.jsonl.gz', RESULTS_SHA256),
                         ('level4-handoff.jsonl.gz', ENTRY_SHA256), ('results-handoff-ds.bin.gz', RAW_SHA256)):
        require(fidelity.sha256(capture / name) == digest, 'native handoff bytes changed: ' + name)
    require(fidelity.sha256(prior) == gate.NATIVE_SHA256, 'prior original gate bytes changed')
    audit = fidelity.strict_json((control / 'native-audit.json').read_text())
    require(audit['status'] == 'original_level3_gate_reels_and_level4_entry_observed' and
            audit['repeated_original_level3_frames'] == 5129 and audit['raw_ds_boundaries'] == 148 and
            audit['results_samples'] == 58 and audit['level4_frames'] == 29 and audit['patches_restored'],
            'native handoff audit incomplete')
    for name, code in (('capture-terminal-receipt.json', 0), ('keeper-terminal-receipt.json', 1)):
        receipt = fidelity.strict_json((control / name).read_text())
        require(receipt['terminal'] is True and receipt['exit_code'] == code, 'native owned session not closed')
    closed = fidelity.strict_json((control / 'closed-controls-retention-complete.json').read_text())
    require(closed['status'] == 'native_raw_and_actual_terminal_controls_retained' and
            closed['retention']['all_notes_tree_anchors_verified'] and
            closed['raw_dependency']['all_member_readback_verified'], 'native retention incomplete')
    outcome = fidelity.strict_json((capture / 'outcome-manifest.json').read_text())
    require(outcome['status'] == 'captured' and outcome['patches_restored'] and
            original.fingerprint(capture) == handoff.PREFIX_SHA256 and
            outcome['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS},
            'original gameplay prefix or assets differ')
    for name, digest in outcome['files'].items():
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'captured file changed: ' + name)
    require(not any((capture / name).exists() for name in ('failure.json', 'objective-observer-failure.json')),
            'failed native handoff capture')
    check_route(capture / 'level3-route.txt')
    records, states, rgb = [], {}, bytes(192000)
    with gzip.open(capture / 'level3-handoff.jsonl.gz', 'rt') as current, gzip.open(prior, 'rt') as old:
        head, old_head = fidelity.strict_json(next(current)), fidelity.strict_json(next(old))
        for index in range(5129):
            row, previous = fidelity.strict_json(next(current)), fidelity.strict_json(next(old))
            require(row['cpp_tick'] == previous['cpp_tick'] == 3777 + index and
                    row['rgb_sha256'] == previous['rgb_sha256'], 'fresh original gameplay prefix differs')
            rgb = original.decode_frame(row['rgb_delta_zlib_hex'], rgb, row['rgb_sha256'])
            for pi, field in enumerate(('pre', 'rendered', 'post')):
                campaign.raw_state(row[field], 3, (150, 60))
                require(handoff.native_boundary(row[field], row['dac'][pi], head['atlas']) ==
                        handoff.native_boundary(previous[field], previous['dac'][pi], old_head['atlas']),
                        'fresh native gate boundary differs')
            if index == 5128:
                for pi, field, phase in ((1, 'rendered', 'present'), (2, 'post', 'post_update')):
                    record = boundary('gate', FIRST, phase, row[field], row['dac'][pi], head['atlas'],
                                      row['rgb_sha256'] if pi == 1 else None)
                    records.append(record)
                    states['gate', FIRST, phase] = row[field]
        require(fidelity.strict_json(next(current))['frames'] == 5129 and not current.read() and
                fidelity.strict_json(next(old))['frames'] == 5129 and not old.read(), 'native prefix stream incomplete')
    reels, entry = handoff.load(capture / 'level3-results.jsonl.gz'), handoff.load(capture / 'level4-handoff.jsonl.gz')
    require(len(reels) == 60 and len(entry) == 31 and reels[-1]['gameplay_frozen'] and
            entry[-1]['native_level4_entry_observed'] and entry[0]['dimensions'] == [100, 58],
            'native result or entry stream incomplete')
    for label in ('ack', 'intro_ack'):
        queued = entry[0][label]
        before, after = bytes.fromhex(queued['before_bda_hex']), bytes.fromhex(queued['bda_hex'])
        require(len(before) == len(after) == 64 and original.word(before, 0x1a) == original.word(before, 0x1c) and
                original.word(after, queued['head']) == queued['key_word'] == 0x1c0d, 'native Return queue differs')
    rgb = bytes(192000)
    for index, row in enumerate(reels[1:-1]):
        require(row['sample'] == index and row['player'] == 1, 'native result sample order differs')
        campaign.raw_state(row['state'], 3, (150, 60))
        rgb = original.decode_frame(row['rgb_delta_zlib_hex'], rgb, row['rgb_sha256'])
        records.append(boundary('result', index + 76, 'result', row['state'], row['dac'], reels[0]['atlas'], row['rgb_sha256']))
        states['result', index + 76, 'result'] = row['state']
    for section, index, field, dac in (('ack', 9301, 'baseline', 'baseline_dac'), ('intro', 9421, 'intro', 'intro_dac')):
        records.append(boundary(section, index, 'present', entry[0][field], entry[0][dac],
            reels[0]['atlas'] if section == 'ack' else entry[0]['atlas'], entry[0][section + '_rgb_sha256'], False))
        states[section, index, 'present'] = entry[0][field]
    rgb = bytes(192000)
    for index, row in enumerate(entry[1:-1]):
        require(row['sample'] == index and row['cpp_tick'] == LEVEL4_FIRST + index, 'native entry sample order differs')
        rgb = original.decode_frame(row['rgb_delta_zlib_hex'], rgb, row['rgb_sha256'])
        for pi, field, phase in ((1, 'rendered', 'present'), (2, 'post', 'post_update')):
            campaign.raw_state(row[field], 4, (100, 58))
            records.append(boundary('level4', row['cpp_tick'], phase, row[field], row['dac'][pi], entry[0]['atlas'],
                                    row['rgb_sha256'] if pi == 1 else None))
            states['level4', row['cpp_tick'], phase] = row[field]
    indexed = {(row['section'], row['index'], row['phase']): row for row in records}
    journal = fidelity.strict_json((capture / 'results-handoff-ds-journal.json').read_text())
    require(journal['complete'] and len(journal['records']) == 148, 'native raw journal incomplete')
    roles = [('gate_post', FIRST, 4)] + [('result', None, 5)] * 58 + [('ack', 9301, 7), ('intro', 9421, 6)]
    roles += [(role, tick, stage) for tick in range(LEVEL4_FIRST, LAST + 1)
              for role, stage in (('pre', 2), ('present', 3), ('post_update', 4))]
    with gzip.open(capture / 'results-handoff-ds.bin.gz', 'rb') as stream:
        for index, (record, expected_role) in enumerate(zip(journal['records'], roles)):
            raw = stream.read(65536)
            require((record['role'], record['cpp_tick'], record['stage']) == expected_role and record['index'] == index and
                    len(raw) == 65536 and hashlib.sha256(raw).hexdigest() == record['sha256'] and
                    (not index or record['sequence'] == journal['records'][index - 1]['sequence'] + 1),
                    'native raw order/hash differs')
            role, tick, _ = expected_role
            if role == 'pre':
                require(original.word(raw, 0x78c2) == tick - 1623 and raw[0x79b7] == 4, 'native pre-frame identity differs')
                continue
            key = ('gate', FIRST, 'post_update') if role == 'gate_post' else \
                  ('result', index + 75, 'result') if role == 'result' else \
                  (role, tick, 'present') if role in ('ack', 'intro') else ('level4', tick, role)
            state = states[key]
            require(original.word(raw, 0x78c2) == state['frame'] and raw[0x79b7] == record['level'] and
                    struct.unpack_from('<I', raw, 0x1afe)[0] == state['rng'], 'raw native identity differs')
            for field, offset, length in (('actors', 0x1bd4, state['actor_count'] * 38),
                ('visuals', 0xc21e, raw[0xc496] * 8), ('inventory', 0x1b6c, 12), ('scores', 0x785a, 92),
                ('destruction', 0x78c6, 4), ('progress', 0x2076, 36), ('spawners', 0x74c6, raw[0x79a6] * 30)):
                require(raw[offset:offset + length].hex() == state[field], 'native raw projection differs: ' + field)
            for player_index, player in enumerate(state['players'], 1):
                offset = 0x1b62 + player_index * 38
                visual = 0xc21e + raw[offset + 1] * 8
                require(raw[offset:offset + 38].hex() == player['raw'] and
                        raw[visual:visual + 8].hex() == player['visual'], 'native raw player/visual differs')
            if role not in ('ack', 'intro'):
                indexed[key]['projection']['terrain'] = projection.native_terrain(raw)
            if role == 'gate_post':
                require(projection.native_gate(raw) == dict(bonus_flag=1, destruction_flag=1, collapse_count=0),
                        'native completion gate not empty/eligible')
        require(not stream.read(1), 'trailing native DS bytes')
    rows = [metadata(outcome['assets']), *records, dict(kind='complete', frames=90, boundaries=120, patches_restored=True)]
    validate(rows)
    guarded = campaign.guard_inputs(entry[-2]['post'], entry[-2]['dac'][2], entry[0]['atlas'])
    campaign.guard_projection(guarded, records[-1]['projection']['mapped'])
    out.mkdir(parents=True)
    with original.compressed_writer(out / 'reference.jsonl.gz') as emit:
        for row in rows:
            emit(row)
    (out / 'route.txt').write_bytes((capture / 'level3-route.txt').read_bytes())
    (out / 'guard-input.json').write_bytes(original.json_bytes(guarded))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for prefix, directory, pins in (('control-', control, CONTROL_PINS), ('capture-', capture, CAPTURE_PINS)):
        for name in pins:
            (EVIDENCE / (prefix + name + '.gz')).write_bytes(gzip.compress((directory / name).read_bytes(), mtime=0))
    print(original.json_bytes(dict(status='packed', reference_sha256=fidelity.sha256(out / 'reference.jsonl.gz'),
                                   guard_sha256=fidelity.sha256(out / 'guard-input.json'))).decode(), flush=True)


def keys():
    return [('gate', FIRST, phase) for phase in ('present', 'post_update')] + \
           [('result', index, 'result') for index in range(76, 134)] + [('ack', 9301, 'present'), ('intro', 9421, 'present')] + \
           [('level4', tick, phase) for tick in range(LEVEL4_FIRST, LAST + 1) for phase in ('present', 'post_update')]


def validate(rows):
    require(len(rows) == 122 and rows[0] == metadata(rows[0]['assets']) and
            rows[-1] == dict(kind='complete', frames=90, boundaries=120, patches_restored=True), 'handoff fixture contract differs')
    previous_rng = 806698761
    for key, row in zip(keys(), rows[1:-1]):
        section, index, phase = key
        level = 4 if section in ('intro', 'level4') else 3
        require(set(row) == {'kind', 'section', 'index', 'phase', 'projection', 'rgb_sha256'} and row['kind'] == 'boundary' and
                (row['section'], row['index'], row['phase']) == key and row['projection']['mapped']['level'] == level and
                row['projection']['mapped']['frame'] == (index - 1623 if section == 'level4' else 7798) and
                (row['rgb_sha256'] is None) == (phase == 'post_update'), 'native handoff boundary differs')
        expected_fields = {'mapped', 'lifecycle'}
        if section not in ('ack', 'intro'):
            expected_fields |= {'monsters', 'markers'}
        if section not in ('ack', 'intro') and key != ('gate', FIRST, 'present'):
            expected_fields.add('terrain')
        require(set(row['projection']) == expected_fields, 'native handoff projection scope differs')
        mapped = row['projection']['mapped']
        require(mapped['players'][0]['energy'] == 66 and mapped['players'][0]['reserve'] == 0 and
                mapped['players'][0]['inventory'] == [200, 10, 0, 0, int(level == 3)] and
                mapped['score'] == (43620 if section == 'gate' else 46290), 'native health/ammunition/score carryover differs')
        if section == 'result':
            if index > 76:
                previous_rng = (previous_rng * 0x08088405 + 1) & 0xffffffff
            require(mapped['rng'] == previous_rng and mapped['players'][0]['reel'][1] == (2 if index == 133 else 1),
                    'native reel/RNG cadence differs')
    final = rows[-2]['projection']['mapped']
    require(final['players'][0]['xy'] == [248.0, 360.0] and final['progress'] == [0, 0] and
            final['rng'] == 1561739296 and previous_rng == 835595830, 'native Level 4 endpoint differs')


def fixture(root=FIXTURE):
    check_coherence()
    check_route(root / 'route.txt')
    require(fidelity.sha256(root / 'reference.jsonl.gz') == REFERENCE_SHA256 and
            fidelity.sha256(root / 'guard-input.json') == GUARD_SHA256, 'handoff fixture fingerprint differs')
    rows = handoff.load(root / 'reference.jsonl.gz')
    validate(rows)
    require(rows[0]['assets'] == campaign.fixture()[0]['assets'], 'handoff fixture assets differ')
    return rows


def check_cpp(state, expected):
    fidelity.validate_state(state)
    difference = fidelity.first_difference(expected['projection'], cpp_projection(state, expected['projection']))
    require(difference is None, 'handoff C++ projection differs: ' + str(difference))
    section = expected['section']
    if section == 'gate' and expected['phase'] == 'post_update':
        require(state['flow'][4] == 1, 'C++ completion gate not entered')
    elif section == 'ack':
        require(state['flow'][4:6] == [1, 1], 'C++ acknowledgement not waiting')
    elif section == 'intro':
        require(state['flow'][3] == 1, 'C++ Level 4 intro not waiting')
    elif section == 'level4':
        require(state['flow'][:6] == [0] * 6, 'C++ Level 4 not playable')


def guard_cpp(state, expected):
    edits = [lambda s: s['players'][0].__setitem__('score', s['players'][0]['score'] + 1),
             lambda s: s.__setitem__('random_seed', s['random_seed'] ^ 1),
             lambda s: s['players'][0].__setitem__('x', s['players'][0]['x'] + 1)]
    edits += [lambda s, index=index: s['players'][0]['inventory'].__setitem__(index, s['players'][0]['inventory'][index] + 1)
              for index in (0, 1, 4)]
    edits += [lambda s, index=index: s['players'][0]['health'].__setitem__(index, s['players'][0]['health'][index] + 1)
              for index in (0, 1)]
    edits += [lambda s, name=name: s.__setitem__(name, bytes([bytes.fromhex(s[name])[0] ^ 1]).hex() + s[name][2:])
              for name in ('tiles_hex', 'words_hex')]
    index = {'gate': 4, 'ack': 5, 'intro': 3, 'level4': 3}.get(expected['section'])
    if index is not None:
        edits.append(lambda s: s['flow'].__setitem__(index, 1 - s['flow'][index]))
    for edit in edits:
        changed = copy.deepcopy(state)
        edit(changed)
        require(changed != state, 'vacuous C++ handoff mutation')
        try:
            check_cpp(changed, expected)
        except fidelity.EvidenceError:
            pass
        else:
            raise fidelity.EvidenceError('C++ handoff mutation accepted')
    return len(edits)


def compare(cpp):
    rows = fixture()
    settings, events = check_route(cpp / 'route.txt')
    wanted = {(r['section'], r['index'], r['phase']): r for r in rows[1:-1]}
    seen, frames, count, previous, mutations = set(), 0, 0, None, 0
    with (cpp / 'trace.jsonl').open(encoding='utf-8') as stream:
        header = fidelity.strict_json(next(stream))
        require(header['schema'] == 'lezac.level1.scout.v1' and header['candidate_only'] is True and
                header['capture_from_tick'] == FIRST and header['ticks'] == LAST and header['source'] == 'cpp' and
                header['phase_model'] == 'cpp-pre-actors-v2' and header['state_scope'] == 'level1-observations-v2' and
                header['input_model'] == 'sdl-events-original-intro-wait-v1' and
                header['seed'] == settings['seed'] and header['step_us'] == settings['step_us'] and
                header['route_fnv1a64'] == fidelity.fnv1a64((cpp / 'route.txt').read_bytes()) and
                header['asset_fnv1a64'] == {n: fidelity.fnv1a64((ROOT / n).read_bytes()) for n in fidelity.ASSETS} and
                header['original_fidelity_claim'] is False and (header['width'], header['height']) == (320, 200),
                'C++ handoff scout provenance differs')
        order = {'input': 0, 'present': 1, 'after_nonplayers': 2, 'post_update': 3}
        footer = None
        for line in stream:
            row = fidelity.strict_json(line)
            require(footer is None, 'C++ data after completion')
            if row['kind'] == 'complete':
                require(previous[1:3] == (LAST, 3) and row['ticks'] == LAST and row['frames'] == LAST - FIRST + 1 and
                        row['retained_checkpoints'] == count and row['checkpoints'] == previous[0] + 1 and
                        row['events'] == sum(map(len, events.values())) and row['level1_route_complete'] is True and
                        row['candidate_only'] is True and row['capture_from_tick'] == FIRST and
                        row['original_fidelity_claim'] is False and row['port_functionally_complete'] is False,
                        'C++ handoff scout footer differs')
                footer = row
                continue
            require(row['kind'] == 'checkpoint' and row['phase'] in order and FIRST <= row['tick'] <= LAST,
                    'invalid C++ handoff checkpoint')
            tick, phase = row['tick'], row['phase']
            current = row['seq'], tick, order[phase]
            if previous is None:
                require(current[1:] == (FIRST, 0), 'C++ scout starts at wrong phase')
            else:
                allowed = {(previous[1], previous[2] + 1)} if previous[2] < 3 else {(previous[1] + 1, 0)}
                if previous[2] == 1:
                    allowed.add((previous[1], 3))
                require(current[0] == previous[0] + 1 and current[1:] in allowed, 'C++ scout phases skipped/reordered')
            require(row['events'] == events.get(tick - 1, []) and row['time_ms'] == (tick - 1) * settings['step_us'] // 1000,
                    'C++ ordinary input/time boundary differs')
            fidelity.validate_state(row['state'])
            section = 'gate' if tick == FIRST else 'ack' if tick == 9301 else 'intro' if tick == 9421 else 'level4'
            key = section, tick, phase
            if key in wanted:
                require(key not in seen, 'duplicate C++ handoff boundary')
                check_cpp(row['state'], wanted[key])
                if key in (('ack', 9301, 'present'), ('intro', 9421, 'present'), ('level4', LAST, 'post_update')):
                    mutations += guard_cpp(row['state'], wanted[key])
                seen.add(key)
            if phase == 'present':
                require(row['frame'] == f'frame_{tick:06d}.ppm', 'C++ frame name differs')
                pixels = fidelity.read_ppm(fidelity.safe_file(cpp, row['frame']))
                require(fidelity.fnv1a64(pixels) == row['rgb_fnv1a64'], 'C++ RGB fingerprint differs')
                if key in wanted:
                    require(hashlib.sha256(pixels).hexdigest() == wanted[key]['rgb_sha256'], 'handoff RGB differs')
                    frames += 1
            else:
                require('frame' not in row and 'rgb_fnv1a64' not in row, 'unexpected non-presentation RGB')
            previous, count = current, count + 1
        require(footer is not None, 'missing C++ handoff footer')
    reels = [fidelity.strict_json(line) for line in (cpp / 'result_reels.jsonl').read_text().splitlines()]
    require(reels[0] == dict(kind='header', schema='lezac.level1.result-reels.v1',
            boundary='prepared-score-then-after-delayed-rng', original_fidelity_claim=False) and
            len(reels) == 136 and reels[-1] == dict(kind='complete', samples=134, original_fidelity_claim=False),
            'C++ result stream incomplete')
    for index, row in enumerate(reels[1:-1]):
        require(set(row) == {'kind', 'sample', 'player', 'frame', 'state'} and row['kind'] == 'sample' and
                row['sample'] == index and row['player'] == 1 and row['frame'] == f'result_frame_{index:06d}.ppm',
                'C++ result boundary differs')
        fidelity.validate_state(row['state'])
        if index < 76:
            continue
        key = 'result', index, 'result'
        check_cpp(row['state'], wanted[key])
        pixels = fidelity.read_ppm(fidelity.safe_file(cpp, row['frame']))
        require(hashlib.sha256(pixels).hexdigest() == wanted[key]['rgb_sha256'], 'result-reel RGB differs')
        if index == 133:
            mutations += guard_cpp(row['state'], wanted[key])
        frames += 1
        seen.add(key)
    require(seen == set(wanted) and frames == 90 and mutations == 43, 'missing handoff comparisons/guards')
    return dict(status='match', frames=frames, boundaries=len(seen), pixels=frames * 64000,
                cpp_projection_mutations_rejected=mutations, completed_levels=[1, 2, 3], entered_level=4,
                full_prefix_executed_from_level1=True, original_results_and_level4_handoff_compared=True, **CLAIMS)


def replay(exe, out):
    out.mkdir(parents=True, exist_ok=True)
    cpp = out.resolve() / ('run-' + uuid.uuid4().hex)
    assets = {n: fidelity.sha256(ROOT / n) for n in fidelity.ASSETS}
    command = [str(exe.resolve()), '--replay-level1-scout', str(FIXTURE / 'route.txt'), str(cpp), str(FIRST),
               '--original-intro-wait', '--result-reels']
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                       LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1')
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=550)
    require(cpp.is_dir(), 'C++ handoff scout produced no evidence')
    for name, text in (('stdout.txt', result.stdout), ('stderr.txt', result.stderr)):
        (cpp / name).write_text(text, encoding='utf-8')
    (cpp / 'command.json').write_bytes(original.json_bytes(dict(command=command, executable_sha256=fidelity.sha256(exe),
        source=fidelity.source_version(ROOT), assets=assets, audio='dummy', video='dummy',
        replay_reader_sha256=fidelity.sha256(Path(__file__)), projection_reader_sha256=fidelity.sha256(Path(projection.__file__)), **CLAIMS)))
    require(result.returncode == 0, 'C++ handoff scout failed: ' + result.stderr.strip())
    shutil.copyfile(FIXTURE / 'route.txt', cpp / 'route.txt')
    require(assets == {n: fidelity.sha256(ROOT / n) for n in fidelity.ASSETS}, 'C++ scout changed assets')
    report = compare(cpp)
    (cpp / 'comparison.json').write_bytes(original.json_bytes(report))
    return report


def guard():
    rows, rejected = fixture(), 0
    edits = [lambda r: r.pop(1), lambda r: r.insert(1, copy.deepcopy(r[1])),
             lambda r: r[0].__setitem__('completed_levels', [1, 2, 3, 4]),
             lambda r: r[0].__setitem__('state_injections', True),
             lambda r: r[0].__setitem__('raw_ds_boundaries', 147),
             lambda r: r[-1].__setitem__('patches_restored', False),
             lambda r: r[1].__setitem__('rgb_sha256', None),
             lambda r: r[1].__setitem__('index', FIRST - 1),
             lambda r: r[-2]['projection']['mapped'].__setitem__('rng', 0)]
    edits += [lambda r, key=key: r[0].__setitem__(key, True) for key in CLAIMS]
    for index in (0, 1, 4):
        edits.append(lambda r, i=index: r[-2]['projection']['mapped']['players'][0]['inventory'].__setitem__(i, 1))
    for edit in edits:
        changed = copy.deepcopy(rows)
        edit(changed)
        require(changed != rows, 'vacuous handoff mutation')
        try:
            validate(changed)
        except fidelity.EvidenceError:
            rejected += 1
        else:
            raise fidelity.EvidenceError('native handoff mutation accepted')
    producer_rejected = 0
    with tempfile.TemporaryDirectory(prefix='lezac-handoff-guard-') as temporary:
        root = Path(temporary)
        for prefix, pins in (('control-', CONTROL_PINS), ('capture-', CAPTURE_PINS)):
            for name in pins:
                (root / name).write_bytes(gzip.decompress((EVIDENCE / (prefix + name + '.gz')).read_bytes()))
            check_pins(root, pins)
            for name in pins:
                raw = (root / name).read_bytes()
                (root / name).write_bytes(raw + b' ')
                try:
                    check_pins(root, pins)
                except fidelity.EvidenceError:
                    producer_rejected += 1
                else:
                    raise fidelity.EvidenceError('handoff producer mutation accepted')
                (root / name).write_bytes(raw)
        for name in AUDIT_PINS:
            shutil.copyfile(EVIDENCE / name, root / name)
        check_pins(root, AUDIT_PINS)
        for name in AUDIT_PINS:
            raw = (root / name).read_bytes()
            (root / name).write_bytes(raw + b' ')
            try:
                check_pins(root, AUDIT_PINS)
            except fidelity.EvidenceError:
                producer_rejected += 1
            else:
                raise fidelity.EvidenceError('snapshot-coherence audit mutation accepted')
            (root / name).write_bytes(raw)
        for name in ('route.txt', 'guard-input.json'):
            (root / name).write_bytes((FIXTURE / name).read_bytes())
        raw = (FIXTURE / 'reference.jsonl.gz').read_bytes()
        for changed in (raw[:-1], raw + b'\0', bytes([raw[0] ^ 1]) + raw[1:]):
            (root / 'reference.jsonl.gz').write_bytes(changed)
            try:
                fixture(root)
            except fidelity.EvidenceError:
                rejected += 1
            else:
                raise fidelity.EvidenceError('handoff fixture byte mutation accepted')
    typed = campaign.guard_projection(fidelity.strict_json((FIXTURE / 'guard-input.json').read_text()), rows[-2]['projection']['mapped'])
    return dict(status='guarded', mutations_rejected=rejected, producer_mutations_rejected=producer_rejected,
                typed_field_mutations_rejected=typed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('pack', 'replay', 'compare', 'guard'))
    for name in ('capture', 'control', 'prior', 'out', 'cpp', 'exe'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.command == 'pack':
        require(all(getattr(args, n) is not None for n in ('capture', 'control', 'prior', 'out')), 'native pack inputs required')
        pack(args.capture.resolve(), args.control.resolve(), args.prior.resolve(), args.out.resolve())
        return
    if args.command == 'replay':
        require(args.exe is not None and args.out is not None, 'C++ executable/output required')
        report = replay(args.exe, args.out)
    elif args.command == 'compare':
        require(args.cpp is not None, 'C++ evidence required')
        report = compare(args.cpp)
    else:
        report = guard()
    print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
