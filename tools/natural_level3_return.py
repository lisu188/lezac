"""Original-backed Level 3 return, reserve loss, reentry and dirty-gated HUD."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
from pathlib import Path
import struct
import tempfile
import uuid

import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original
import level1_results as results
import natural_campaign as campaign
import natural_level3_portal_escape as escape

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level3_return'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level3_return_20261005'
SCHEMA = 'lezac-natural-level3-return-boundaries-v1'
TICKS, FIRST_TICK, FRAMES, NATIVE_FRAMES = 7065, 6355, 711, 3289
ROUTE_SHA256 = '5e73ea2c87aaa55a9efbc0ddd5af509668be318df94a7bd401627a0f86ce11fc'
NATIVE_SHA256 = '410cd2e6d79991a41f1e3e4e585b7399321aed4f60f17a8176a5ec23bcc361b0'
REFERENCE_SHA256 = '7425bf79fff6022b3409cda2266739d7e3062489f5845af5b0f51dcadadf4075'
GUARD_INPUT_SHA256 = '0d97b3da1c995aa6a4c0605dd6bcbf484e98d94e3fad591f74564661dc5242b1'
CAPTURE_PINS = {
    **{key: value for key, value in escape.CAPTURE_PINS.items() if key in (
        'level3-handoff-observer.py', 'outcome-observer.py',
        'extension-observer.py', 'observer.py', 'results-observer.py')},
    'objective-observer-wrapper.py': '67fbad0106d75c06652708f8ec9667d2b607665947b26d5811d05e6c1c5206f7',
    'central-return-capture-driver.py': '027ae96b3899430d3228fe6af98f1d7ca8eba97009d84ed1d650cb87ae5e4547',
    'central-return-native-audit.json': 'bbc50e74ad4a8587e50eb5310990d4d06372b22593fd14360fe004c81f9f9317',
    'central-return-runtime-configuration.json': 'd8d60debcc9bed3e541cd86f1b4b6cf0a4d481238d181c3df6896bc9f88a1ac1',
    'objective-controller.json': '5617b5908f2df790e21a1ac9c5c3e00ea3c7d7d16c69af23784f58b88bbfd98c',
    'objective-input-journal.json': 'cec1f4037bcd30e2323699c2bae54ad2417eebec1297e1190cb81ee139007883',
    'outcome-manifest.json': 'c077567f541e915479e7b42b69b750c9115ac7e8bc7c490a06a30a5f8061ae11',
}
OPCODES = {0x2e49: 'c606761b02', 0x2e4e: 'c606771b02', 0x3283: '8a85731b',
           0x329d: '8a85671b', 0x32ab: '80bd751b01766e', 0x3327: 'c685751b00',
           0x332c: '807efe637604c646fe63', 0x6859: 'c685751b02', 0x6ca4: 'c685751b01',
           0x6ee0: 'c685751b01', 0x6f5c: 'c685751b01', 0x7c49: '8b3e822080bd751b007623',
           0x7c54: '8b3e822080bde579017518', 0x7c74: 'e8f7b5'}
CHECKPOINTS = {
    6580: ([574, 211], 19, 1, [200, 11, 0, 0, 1], [8, 86], 0, 65514, 1),
    6710: ([468, 183], 3, 1, [200, 9, 0, 0, 1], [8, 93], 0, 65514, 1),
    6716: ([481, 186], 100, 1, [200, 8, 0, 0, 1], [8, 93], 2, 60, 1),
    6776: ([64, 272], 100, 0, [200, 10, 2, 0, 1], [8, 93], 2, 0, 2),
    6781: ([64, 272], 100, 0, [200, 10, 2, 0, 1], [8, 93], 0, 65531, 1),
    7065: ([30, 272], 100, 0, [200, 10, 2, 0, 1], [8, 93], 0, 65531, 1),
}
require = fidelity.require


def prefix_rows():
    return [row for row in [*escape.prefix_rows(), *escape.fixture()[1:-1]] if row['tick'] < FIRST_TICK]


def check_opcodes(image):
    for offset, value in OPCODES.items():
        require(image[offset:offset + len(value) // 2].hex() == value, 'original HUD instruction differs: ' + hex(offset))


def native_lifecycle(state):
    raw = bytes.fromhex(state['players'][0]['raw'])
    return {'actor_mode': raw[21], 'countdown_word': struct.unpack_from('<H', raw, 16)[0],
            'global_player_state': bytes.fromhex(state['globals'])[0x46]}


def cpp_lifecycle(state):
    player = state['players'][0]
    return {'actor_mode': 2 if player['health'][2] else 0, 'countdown_word': player['waiting'][0] & 65535,
            'global_player_state': 0 if player['health'][1] < 0 else
                2 if player['health'][2] and not player['waiting'][2] and not state['flow'][7] else 1}


def check_producer(capture):
    for name, digest in CAPTURE_PINS.items():
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'untrusted return producer: ' + name)


def check_route(route):
    require(fidelity.sha256(route) == ROUTE_SHA256, 'return route fingerprint differs')
    settings, events = fidelity.read_route(route)
    baseline, prior = fidelity.read_route(escape.FIXTURE / 'route.txt')
    require(settings['ticks'] == TICKS and all(settings[key] == baseline[key] for key in ('seed', 'step_us')) and
            {tick: items for tick, items in events.items() if tick < FIRST_TICK - 1} ==
            {tick: items for tick, items in prior.items() if tick < FIRST_TICK - 1},
            'return route changed the immutable escape prefix')
    require(all(event['key'] in ('m', 'n', 'x', 'z', 'c') and event['action'] in ('down', 'up')
                for tick, items in events.items() if tick >= FIRST_TICK - 1 for event in items),
            'unexpected ordinary return control')
    return events


def metadata(assets):
    return {'kind': 'header', 'schema': SCHEMA, 'ticks': TICKS, 'first_tick': FIRST_TICK, 'frames': FRAMES,
            'native_frames': NATIVE_FRAMES, 'dimensions': [150, 60], 'route_sha256': ROUTE_SHA256,
            'native_stream_sha256': NATIVE_SHA256, 'prefix_reference_sha256': escape.REFERENCE_SHA256,
            'capture_pins': CAPTURE_PINS, 'assets': assets, 'audio': 'dummy', 'state_injections': False,
            'completed_levels': [1, 2], 'entered_level': 3, 'natural_level3_completion_claim': False,
            'checkpoint_ticks': list(CHECKPOINTS), 'original_hud_opcodes': {hex(k): v for k, v in OPCODES.items()},
            'native_hud_dirty_address': 'DS:1B75 + player_index_1 = DS:1B76',
            'cpp_hud_dirty_byte_directly_compared': False, **campaign.CLAIMS}


def pack(capture, out):
    require(not out.exists(), 'fresh return fixture output required')
    check_producer(capture)
    check_opcodes(original.check_executable(ROOT / 'LEZAC.EXE'))
    require(not any((capture / name).exists() for name in ('failure.json', 'objective-observer-failure.json')),
            'failed native return capture')
    outcome = fidelity.strict_json((capture / 'outcome-manifest.json').read_text())
    require(outcome['status'] == 'captured' and outcome['patches_restored'] is True and
            outcome['gameplay_frames'] == 2352 and outcome['result_samples'] == 34 and
            outcome['gate_cpp_tick'] == campaign.GATE_TICK and outcome['gate_native_frame'] == 2669,
            'incomplete ordinary Level 2 prefix')
    for name, digest in outcome['files'].items():
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'native file changed: ' + name)
    require(outcome['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS} and
            original.fingerprint(capture) == handoff.PREFIX_SHA256 and
            fidelity.sha256(capture / 'level3-handoff.jsonl.gz') == NATIVE_SHA256,
            'native assets/canonical prefix/stream differs')
    audit = fidelity.strict_json((capture / 'central-return-native-audit.json').read_text())
    config = fidelity.strict_json((capture / 'central-return-runtime-configuration.json').read_text())
    require(audit['status'] == 'captured_and_mapped_prefix_verified' and audit['patches_restored'] is True and
            audit['route_ticks'] == config['route_ticks'] == TICKS and audit['level3_frames'] == NATIVE_FRAMES and
            config['runtime_frames'] == NATIVE_FRAMES and audit['unchanged_native_prefix_frames'] == 2804 and
            audit['unchanged_native_prefix_boundaries'] == 8412 and
            audit['unchanged_verified_prefix_tick'] == config['unchanged_verified_prefix_tick'] == 6580 and
            config['unchanged_verified_level3_prefix_frames'] == 2804 and config['prior_native_frames'] == 2989 and
            audit['prior_native_stream_sha256'] == config['prior_native_stream_sha256'] ==
                '8627e8522450a2a73bd77ac7724ad5f33bb9e55b91a96767e0694df452f0ced5' and
            audit['variant_source_sha256'] == config['variant_source_sha256'] == CAPTURE_PINS['central-return-capture-driver.py'] and
            audit['variant_configuration_sha256'] == CAPTURE_PINS['central-return-runtime-configuration.json'] and
            audit['parent_sha256'] == config['parent_sha256'] == CAPTURE_PINS['objective-observer-wrapper.py'] and
            audit['native_stream_sha256'] == NATIVE_SHA256 and audit['route_sha256'] == config['route_sha256'] == ROUTE_SHA256 and
            audit['new_gameplay_state_injections'] is config['new_gameplay_state_injections'] is False and
            audit['cpp_compared'] is False and audit['audio'] == config['audio'] == 'dummy',
            'native return runtime configuration differs')
    events = check_route(capture / 'level3-route.txt')
    expected = {(row['tick'], row['phase']): row for row in prefix_rows()}
    require(len(expected) == 10578, 'canonical return prefix coverage differs')

    def prefix(row, tick, header, level, dimensions):
        for field, phase, pi in (('rendered', 'present', 1), ('post', 'post_update', 2)):
            campaign.raw_state(row[field], level, dimensions)
            require(campaign.native_boundary(row[field], row['dac'][pi], header['atlas']) == expected[tick, phase]['mapped'],
                    'fresh mapped return prefix differs')
        require(row['rgb_sha256'] == expected[tick, 'present']['rgb_sha256'], 'fresh return prefix RGB differs')

    entry = handoff.load(capture / 'handoff.jsonl.gz')
    handoff.validate(entry)
    for index, row in enumerate(entry[1:-1]):
        prefix(row, 731 + index, entry[0], 2, (100, 53))
    gameplay = handoff.load(capture / 'gameplay.jsonl.gz')
    require(len(gameplay) == 2354 and gameplay[-1]['patches_restored'] is True and
            gameplay[-1]['gate_eligible'] is True, 'incomplete Level 2 gameplay prefix')
    previous = bytes(192000)
    for index, row in enumerate(gameplay[1:-1]):
        require(row['sample'] == index and row['cpp_tick'] == 743 + index and
                row['events'] == events.get(742 + index, []) and row['gate_eligible'] == (index == 2351),
                'Level 2 input/gate prefix differs')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        prefix(row, 743 + index, gameplay[0], 2, (100, 53))
    reels = handoff.load(capture / 'results.jsonl.gz')
    require(len(reels) == 36 and reels[-1]['samples'] == 34 and reels[-1]['gameplay_frozen'] is True,
            'incomplete Level 2 results prefix')
    previous = bytes(192000)
    for index, row in enumerate(reels[1:-1]):
        require(row['sample'] == index and row['player'] == 1 and
                all(row['state'][key] == gameplay[-2]['post'][key] for key in results.FROZEN), 'results advanced gameplay')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        require(campaign.native_boundary(row['state'], row['dac'], reels[0]['atlas']) == expected[index + 42, 'result']['mapped'] and
                row['rgb_sha256'] == expected[index + 42, 'result']['rgb_sha256'], 'fresh results state/pixels differ')
    native = handoff.load(capture / 'level3-handoff.jsonl.gz')
    header = native[0]
    require(len(native) == NATIVE_FRAMES + 2 and header['frames'] == native[-1]['frames'] == NATIVE_FRAMES and
            header['first_cpp_tick'] == 3777 and header['dimensions'] == [150, 60] and
            header['ack_sequence'] + 1 == header['intro_sequence'] and native[-1]['kind'] == 'complete' and
            native[-1]['native_level3_entry_observed'] is True, 'incomplete native return stream')
    for key, tick, palette, digest in (
        ('baseline', 3642, 'baseline_dac', 'ack_rgb_sha256'), ('intro', 3776, 'intro_dac', 'intro_rgb_sha256')):
        require(campaign.native_boundary(header[key], header[palette], reels[0]['atlas'] if key == 'baseline' else header['atlas']) ==
                expected[tick, 'present']['mapped'] and header[digest] == expected[tick, 'present']['rgb_sha256'],
                'fresh acknowledgment/intro prefix differs')
    journal = fidelity.strict_json((capture / 'objective-input-journal.json').read_text())
    require(journal['complete'] is True and len(journal['samples']) == NATIVE_FRAMES and
            journal['new_gameplay_state_injections'] is False, 'incomplete native return input journal')
    rows, previous = [], bytes(192000)
    for index, row in enumerate(native[1:-1]):
        tick = 3777 + index
        require(row['sample'] == index and row['cpp_tick'] == tick and
                row['sequences'] == [header['intro_sequence'] + 1 + index * 3 + i for i in range(3)],
                'native return frame/phase alignment differs')
        for field in ('pre', 'rendered', 'post'):
            campaign.raw_state(row[field], 3, (150, 60))
            require(row[field]['frame'] == 2670 + index, 'native return frame skipped')
        require(len(row['dac']) == 3, 'missing native palettes')
        for value in row['dac']:
            handoff.dac(value)
        control = journal['samples'][index]
        wanted_events = events.get(tick - 1, []) if index >= 12 else []
        require(control['sample'] == index and control['cpp_tick'] == tick and control['events'] == wanted_events,
                'native return control phase differs')
        before, after = bytes.fromhex(control['before_bank_hex']), bytes.fromhex(control['after_bank_hex'])
        require(len(before) == len(after) == 10, 'native input bank extent differs')
        wanted = bytearray(before)
        for event in wanted_events:
            wanted[original.BANK[event['key']] - 0x1b78] = event['action'] != 'up'
        require(bytes(wanted) == after, 'undeclared native input-bank write')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        if tick < FIRST_TICK:
            prefix(row, tick, header, 3, (150, 60))
            continue
        for field, phase, pi in (('rendered', 'present', 1), ('post', 'post_update', 2)):
            rows.append({'kind': 'boundary', 'tick': tick, 'phase': phase, 'region': 'level3_return',
                         'mapped': campaign.native_boundary(row[field], row['dac'][pi], header['atlas']),
                         'lifecycle': native_lifecycle(row[field]),
                         'native_hud_dirty': bytes.fromhex(row[field]['inventory'])[10],
                         'rgb_sha256': hashlib.sha256(previous).hexdigest() if phase == 'present' else None})
    packed = [metadata(outcome['assets']), *rows,
              {'kind': 'complete', 'frames': FRAMES, 'boundaries': FRAMES * 2, 'patches_restored': True}]
    validate(packed)
    guarded = campaign.guard_inputs(native[-2]['post'], native[-2]['dac'][2], header['atlas'])
    campaign.guard_projection(guarded, rows[-1]['mapped'])
    guarded['players'][0]['health'].append(False)
    guarded['players'][0]['waiting'] = [65531, 0, True, 0]
    guarded['flow'] = [False] * 8
    require(cpp_lifecycle(guarded) == rows[-1]['lifecycle'], 'typed return lifecycle baseline differs')
    out.mkdir(parents=True)
    with original.compressed_writer(out / 'reference.jsonl.gz') as emit:
        for row in packed:
            emit(row)
    (out / 'route.txt').write_bytes((capture / 'level3-route.txt').read_bytes())
    (out / 'guard-input.json').write_bytes(original.json_bytes(guarded))
    print(original.json_bytes({'status': 'packed', 'reference_sha256': fidelity.sha256(out / 'reference.jsonl.gz'),
                               'guard_input_sha256': fidelity.sha256(out / 'guard-input.json'),
                               'frames': FRAMES, 'boundaries': len(rows)}).decode(), flush=True)


def validate(rows):
    require(len(rows) == FRAMES * 2 + 2 and rows[0] == metadata(rows[0]['assets']) and
            rows[-1] == {'kind': 'complete', 'frames': FRAMES, 'boundaries': FRAMES * 2, 'patches_restored': True},
            'return fixture contract differs')
    for index, row in enumerate(rows[1:-1]):
        tick, phase = FIRST_TICK + index // 2, ('present', 'post_update')[index % 2]
        require(set(row) == {'kind', 'tick', 'phase', 'region', 'mapped', 'rgb_sha256', 'lifecycle', 'native_hud_dirty'} and
                row['kind'] == 'boundary' and row['region'] == 'level3_return' and row['tick'] == tick and row['phase'] == phase and
                row['mapped']['level'] == 3 and row['mapped']['frame'] == tick - 1107 and
                (row['rgb_sha256'] is None) == (phase == 'post_update'), 'invalid return boundary')
        life = row['lifecycle']
        require(set(life) == {'actor_mode', 'countdown_word', 'global_player_state'} and
                all(type(value) is int for value in life.values()) and life['actor_mode'] in (0, 2) and
                0 <= life['countdown_word'] <= 65535 and life['global_player_state'] in (1, 2) and
                type(row['native_hud_dirty']) is int and 0 <= row['native_hud_dirty'] <= 255,
                'native return lifecycle/dirty byte differs')
        if tick >= 6776:
            require(row['native_hud_dirty'] == 0, 'native refill dirtied ammunition')
    for tick, (xy, energy, reserve, inventory, progress, mode, countdown, global_state) in CHECKPOINTS.items():
        row = rows[(tick - FIRST_TICK) * 2 + 2]
        player = row['mapped']['players'][0]
        require(player['xy'] == xy and player['energy'] == energy and player['reserve'] == reserve and
                player['inventory'] == inventory and row['mapped']['progress'] == progress and
                row['native_hud_dirty'] == 0 and row['lifecycle'] ==
                {'actor_mode': mode, 'countdown_word': countdown, 'global_player_state': global_state},
                'literal native return checkpoint differs: ' + str(tick))


def fixture(root=FIXTURE):
    require(fidelity.sha256(root / 'reference.jsonl.gz') == REFERENCE_SHA256 and
            fidelity.sha256(root / 'guard-input.json') == GUARD_INPUT_SHA256, 'return fixture fingerprint differs')
    check_route(root / 'route.txt')
    rows = handoff.load(root / 'reference.jsonl.gz')
    validate(rows)
    require(rows[0]['assets'] == campaign.fixture()[0]['assets'], 'return fixture assets differ')
    return rows


def compare(cpp):
    extension, prefix = fixture(), campaign.fixture()
    rows = [prefix[0], *prefix_rows(), *extension[1:-1], prefix[-1]]
    report = campaign.compare_rows(cpp, rows, FIXTURE / 'route.txt', TICKS)
    require(report['frames'] == 6038 and report['boundaries'] == 12000 and report['pixels'] == 386432000,
            'full return coverage differs')
    expected = {(row['tick'], row['phase']): row['lifecycle'] for row in extension[1:-1]}
    seen = set()
    for row in fidelity.trace_rows(cpp, fidelity.load_manifest(cpp)):
        key = row.get('tick'), row.get('phase')
        if row['kind'] != 'checkpoint' or key not in expected:
            continue
        require(key not in seen and cpp_lifecycle(row['state']) == expected[key], 'return lifecycle differs: ' + str(key))
        seen.add(key)
    require(len(seen) == FRAMES * 2, 'missing return lifecycle boundaries')
    return {**report, 'new_level3_frames': FRAMES, 'new_level3_boundaries': FRAMES * 2,
            'lifecycle_boundaries': len(seen), 'checkpoint_ticks': list(CHECKPOINTS),
            'natural_level3_completion_claim': False}


def guard():
    rows, mutations = fixture(), 0
    edits = [lambda r: r.pop(1), lambda r: r.insert(1, copy.deepcopy(r[1])),
             lambda r: r.__setitem__(slice(1, 3), [r[2], r[1]]),
             lambda r: r[-1].__setitem__('patches_restored', False),
             lambda r: r[1].__setitem__('tick', FIRST_TICK - 1), lambda r: r[1].__setitem__('phase', 'pre_update'),
             lambda r: r[1].__setitem__('rgb_sha256', None), lambda r: r[1].__setitem__('region', 'level3_portal')]
    for tick in CHECKPOINTS:
        index = (tick - FIRST_TICK) * 2 + 2
        for path in (('mapped', 'players', 0, 'xy', 0), ('mapped', 'players', 0, 'energy'),
                     ('mapped', 'players', 0, 'reserve'), ('mapped', 'players', 0, 'inventory', 1),
                     ('mapped', 'progress', 1), ('lifecycle', 'actor_mode'), ('lifecycle', 'countdown_word'),
                     ('lifecycle', 'global_player_state'), ('native_hud_dirty',)):
            def edit(r, index=index, path=path):
                target = r[index]
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] += 1
            edits.append(edit)
    for key, value in (('dimensions', [100, 53]), ('first_tick', FIRST_TICK - 1), ('ticks', TICKS - 1),
                       ('frames', FRAMES - 1), ('native_frames', NATIVE_FRAMES - 1), ('completed_levels', [1, 2, 3]),
                       ('state_injections', True), ('prefix_reference_sha256', '0' * 64),
                       ('native_stream_sha256', '0' * 64), ('route_sha256', '0' * 64), ('audio', 'speaker'),
                       ('all_actor_fields_compared', True), ('natural_level3_completion_claim', True),
                       ('checkpoint_ticks', [7065]), ('capture_pins', {}), ('original_hud_opcodes', {}),
                       ('cpp_hud_dirty_byte_directly_compared', True)):
        edits.append(lambda r, key=key, value=value: r[0].__setitem__(key, value))
    for edit in edits:
        changed = copy.deepcopy(rows)
        edit(changed)
        require(changed != rows, 'vacuous return mutation')
        try:
            validate(changed)
        except fidelity.EvidenceError:
            mutations += 1
        else:
            raise fidelity.EvidenceError('return semantic mutation accepted')
    with tempfile.TemporaryDirectory(prefix='lezac-return-guard-') as temporary:
        root = Path(temporary)
        for name in ('route.txt', 'guard-input.json'):
            (root / name).write_bytes((FIXTURE / name).read_bytes())
        raw = (FIXTURE / 'reference.jsonl.gz').read_bytes()
        for bad in (raw[:-1], raw + b'\0', bytes([raw[0] ^ 1]) + raw[1:]):
            (root / 'reference.jsonl.gz').write_bytes(bad)
            try:
                fixture(root)
            except fidelity.EvidenceError:
                mutations += 1
            else:
                raise fidelity.EvidenceError('return fixture mutation accepted')
        (root / 'reference.jsonl.gz').write_bytes(raw)
        for name in ('route.txt', 'guard-input.json'):
            saved = (root / name).read_bytes()
            (root / name).write_bytes(saved + b' ')
            try:
                fixture(root)
            except fidelity.EvidenceError:
                mutations += 1
            else:
                raise fidelity.EvidenceError('return fixture input mutation accepted')
            (root / name).write_bytes(saved)
    guarded = fidelity.strict_json((FIXTURE / 'guard-input.json').read_text())
    projection = copy.deepcopy(guarded)
    projection['players'][0]['health'] = projection['players'][0]['health'][:2]
    typed = campaign.guard_projection(projection, rows[-2]['mapped'])
    require(cpp_lifecycle(guarded) == rows[-2]['lifecycle'], 'return lifecycle baseline differs')
    life_mutations = 0
    for path in (('players', 0, 'health', 2), ('players', 0, 'waiting', 0)):
        changed = copy.deepcopy(guarded)
        target = changed
        for part in path[:-1]:
            target = target[part]
        value = target[path[-1]]
        target[path[-1]] = not value if type(value) is bool else value + 1
        require(cpp_lifecycle(changed) != rows[-2]['lifecycle'], 'typed lifecycle mutation accepted')
        life_mutations += 1
    waiting = copy.deepcopy(guarded)
    waiting['players'][0]['health'][2] = True
    waiting['players'][0]['waiting'][2] = False
    require(cpp_lifecycle(waiting)['global_player_state'] == 2, 'waiting global-state projection differs')
    for path in (('players', 0, 'waiting', 2), ('flow', 7)):
        changed = copy.deepcopy(waiting)
        target = changed
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = True
        require(cpp_lifecycle(changed)['global_player_state'] == 1, 'return global-state mutation ignored')
        life_mutations += 1
    wrapped = copy.deepcopy(guarded)
    wrapped['players'][0]['waiting'][0] += 65536
    require(cpp_lifecycle(wrapped) == rows[-2]['lifecycle'], 'return countdown lost its unsigned word')
    image = original.check_executable(ROOT / 'LEZAC.EXE')
    check_opcodes(image)
    opcode_mutations = 0
    for offset in OPCODES:
        changed = bytearray(image)
        changed[offset] ^= 1
        try:
            check_opcodes(changed)
        except fidelity.EvidenceError:
            opcode_mutations += 1
        else:
            raise fidelity.EvidenceError('original HUD instruction mutation accepted')
    producer_mutations = 0
    with tempfile.TemporaryDirectory(prefix='lezac-return-producer-') as temporary:
        root = Path(temporary)
        for name in CAPTURE_PINS:
            (root / name).write_bytes(gzip.decompress((EVIDENCE / (name + '.gz')).read_bytes()))
        check_producer(root)
        for name in CAPTURE_PINS:
            raw = (root / name).read_bytes()
            (root / name).write_bytes(raw + b' ')
            try:
                pack(root, root / 'must-not-exist')
            except fidelity.EvidenceError:
                producer_mutations += 1
            else:
                raise fidelity.EvidenceError('untrusted return producer accepted')
            require(not (root / 'must-not-exist').exists(), 'untrusted producer wrote output')
            (root / name).write_bytes(raw)
    require(mutations == 84 and typed == 291 and producer_mutations == 12 and
            life_mutations == 4 and opcode_mutations == 14, 'return guard coverage differs')
    print(original.json_bytes({'status': 'guarded', 'mutations_rejected': mutations,
                               'typed_field_mutations_rejected': typed, 'producer_mutations_rejected': producer_mutations,
                               'lifecycle_mutations_rejected': life_mutations,
                               'opcode_mutations_rejected': opcode_mutations}).decode(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('pack', 'compare', 'replay', 'guard'))
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--cpp', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    if args.command == 'pack':
        require(args.capture is not None and args.out is not None, 'native capture/output required')
        pack(args.capture.resolve(), args.out.resolve())
    elif args.command == 'guard':
        guard()
    else:
        if args.command == 'replay':
            require(args.exe is not None and args.out is not None, 'executable/output required')
            args.out.mkdir(parents=True, exist_ok=True)
            cpp = args.out.resolve() / ('run-' + uuid.uuid4().hex)
            fidelity.record(args.exe, ROOT, FIXTURE / 'route.txt', cpp, original_intro_wait=True, result_reels=True)
        else:
            require(args.cpp is not None, 'C++ replay required')
            cpp = args.cpp.resolve()
        report = compare(cpp)
        (cpp / 'natural-level3-return-comparison.json').write_bytes(original.json_bytes(report))
        print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
