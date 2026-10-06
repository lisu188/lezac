"""Original-backed ordinary Level 3 empty-collapse completion-gate replay."""
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
import natural_level3_return as returned
import natural_level3_gate_projections as projection

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level3_completion_gate'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level3_completion_gate_20261006'
SCHEMA = 'lezac-natural-level3-completion-gate-v1'
FIRST, LAST, FRAMES, NATIVE_FRAMES = 8420, 8905, 486, 5129
ROUTE_SHA256 = '620ed01e8f969d1d76d87c8734ff650bdd3c493c6a26f386baaeab570bd1c963'
NATIVE_SHA256 = '481da8aae48e547d58dd912fdbd5e50d00dedcfb8c21d6ec88d3f66490a999d8'
PRIOR_SHA256 = 'a1b38d1e8c1d60932c0fa05decb6453cf3c2fb599495e884bc93357d91efc632'
RAW_SHA256 = 'c2358009a2daa1aafcebbca8b42c01bd6bdd1e8563ceda41f7a7af34fd20a664'
REFERENCE_SHA256 = '8eabdc822f639a251d0058d50710f59cf7daab6d5f595cb9f39c92a3dee80de2'
GUARD_SHA256 = '6854dabf6d52737c12d274e70afeb8bf99b0e02de6c206d37679bc93442df4f2'
CONTROL_PINS = {
    'common.py': '588f6861073c51fa4985b5e1a1255a10a2c04c04654fcd7a71bba600676c7319',
    'capture.py': 'e74398c160949feb86060da460f297e08e4a953a761ea4511e7fa8b8d19fd099',
    'prepare.py': 'cca2724a03a5fca4fe09264731c698178bde7ee58ad717e9ec74155952e4cc45',
    'private-capture.py': '4af1115a09b51cc02b642cfa5e25215e0b01411c33a1906bf34880004c76f8fb',
    'retain-and-close.py': '67cec78e3f464643e40b8cf0f676794e9641300a2afb8292a3ca6b48064311d2',
    'compare.py': 'ae0d0077faa2e78e878c9af37990c8d0766bab89fb471bc41260772f42792662',
    'extract-cpp.py': '40a4c7740e22727df3f24a1d7f8a3e5625928d34ac81270103367f78a1630686',
    'native-audit.json': 'af4312013e7b3fd712bd660dc68900c1688ee65f99c350a4b017d9cebe583ec4',
    'preparation-proof.json': 'a58835ab0301cb3cc921c2f4de4828d3ea68c03d38e3878159da3bf6f55e4dba',
    'capture-terminal-receipt.json': 'd67f44221863db38b2c85887aa0d9ccff42babcee1ca68af3af227662221b72e',
    'raw-retention-complete.json': '950d9a9db5f983d06f7868b121d8bff42294936fa6ab8cc7ac26833227dea5fe',
}
CAPTURE_PINS = {
    'capture.py': CONTROL_PINS['capture.py'],
    'objective-observer-wrapper.py': '67fbad0106d75c06652708f8ec9667d2b607665947b26d5811d05e6c1c5206f7',
    **{name: campaign.CAPTURE_PINS[name] for name in ('observer.py', 'results-observer.py',
       'extension-observer.py', 'outcome-observer.py', 'level3-handoff-observer.py')},
    'outcome-manifest.json': '12bf82fb32d6df0fd684341e283351ed81283baf8c90d9a4f4f3bd17359cf628',
    'ammo-runtime-configuration.json': '89fe7e6df6b398d8e8c06cf0a7fd308393a24b8f3ee0c29bafca27b54892295d',
    'objective-input-journal.json': '35d5a0a2f6dcbf1efa4bc5935c9147b47054546b014a7e96c2ac18d7588c9e14',
    'new-suffix-ds-journal.json': '7259c81e8255d8959d580356dcd1d04cfb37552eda9146cb24bc9a96773882d4',
}
CLAIMS = {**campaign.CLAIMS, 'natural_level3_completion_claim': False,
          'original_results_and_level4_handoff_compared': False,
          'full_prefix_cpp_comparison_claim': False, 'full_actor_clock_sound_byte_parity': False}
require = fidelity.require


def check_pins(root, pins):
    for name, digest in pins.items():
        require(fidelity.sha256(fidelity.safe_file(root, name)) == digest, 'untrusted gate producer: ' + name)


def check_route(route):
    require(fidelity.sha256(route) == ROUTE_SHA256, 'gate route fingerprint differs')
    settings, events = fidelity.read_route(route)
    require(settings == {'ticks': LAST, 'seed': 305441741, 'step_us': 40800}, 'gate route settings differ')
    fidelity.require_original_intro_prelude(events)
    require(all(e['key'] in ('x', 'z', 'm', 'n') and e['action'] in ('down', 'up')
                for tick, rows in events.items() if tick > FIRST for e in rows), 'unexpected gate suffix input')
    return settings, events


def metadata(assets):
    return dict(kind='header', schema=SCHEMA, first_tick=FIRST, ticks=LAST, frames=FRAMES,
                native_frames=NATIVE_FRAMES, dimensions=[150, 60], route_sha256=ROUTE_SHA256,
                native_stream_sha256=NATIVE_SHA256, prior_native_stream_sha256=PRIOR_SHA256,
                raw_ds_sha256=RAW_SHA256, raw_ds_boundaries=1455, control_pins=CONTROL_PINS,
                capture_pins=CAPTURE_PINS, assets=assets, audio='dummy', state_injections=False,
                completed_levels=[1, 2], entered_level=3, original_gate_eligible_tick=LAST, **CLAIMS)


def native_projection(state, dac, atlas):
    return dict(mapped=campaign.native_boundary(state, dac, atlas), lifecycle=returned.native_lifecycle(state),
                monsters=projection.native_monsters(state), markers=projection.native_markers(state))


def cpp_projection(state, terrain):
    result = dict(mapped=campaign.cpp_boundary(state), lifecycle=returned.cpp_lifecycle(state),
                  monsters=projection.cpp_monsters(state), markers=projection.cpp_markers(state))
    if terrain:
        result['terrain'] = projection.cpp_terrain(state)
    return result


def pack(capture, control, prior, out):
    require(not out.exists(), 'fresh native gate fixture output required')
    check_pins(control, CONTROL_PINS)
    check_pins(capture, CAPTURE_PINS)
    for name, digest in (('level3-handoff.jsonl.gz', NATIVE_SHA256), ('new-suffix-ds.bin.gz', RAW_SHA256)):
        require(fidelity.sha256(capture / name) == digest, 'native gate bytes changed: ' + name)
    require(fidelity.sha256(prior) == PRIOR_SHA256, 'prior original prefix changed')
    receipt = fidelity.strict_json((control / 'capture-terminal-receipt.json').read_text())
    require(receipt['terminal'] is True and receipt['exit_code'] == 0, 'native gate capture not terminal-successful')
    outcome = fidelity.strict_json((capture / 'outcome-manifest.json').read_text())
    require(outcome['status'] == 'captured' and outcome['patches_restored'] is True and
            outcome['gameplay_frames'] == 2352 and outcome['result_samples'] == 34 and
            outcome['gate_cpp_tick'] == 3094 and outcome['gate_native_frame'] == 2669,
            'ordinary Level 1/2 capture prefix incomplete')
    require(not any((capture / name).exists() for name in ('failure.json', 'objective-observer-failure.json')),
            'failed native gate capture')
    for name, digest in outcome['files'].items():
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'captured file changed: ' + name)
    require(outcome['assets'] == {n: fidelity.sha256(ROOT / n) for n in fidelity.ASSETS} and
            original.fingerprint(capture) == handoff.PREFIX_SHA256, 'native asset/ordinary prefix differs')
    _, events = check_route(capture / 'level3-route.txt')
    rows, old = handoff.load(capture / 'level3-handoff.jsonl.gz'), handoff.load(prior)
    header = rows[0]
    require(len(rows) == NATIVE_FRAMES + 2 and header['frames'] == rows[-1]['frames'] == NATIVE_FRAMES and
            header['dimensions'] == [150, 60] and header['first_cpp_tick'] == 3777 and
            rows[-1]['kind'] == 'complete' and rows[-1]['native_level3_entry_observed'] is True,
            'native gate stream incomplete')
    inputs = fidelity.strict_json((capture / 'objective-input-journal.json').read_text())
    require(inputs['complete'] is True and inputs['new_gameplay_state_injections'] is False and
            len(inputs['samples']) == NATIVE_FRAMES, 'native input journal incomplete')
    boundaries, previous = [], bytes(192000)
    for index, row in enumerate(rows[1:-1]):
        tick = 3777 + index
        require(row['sample'] == index and row['cpp_tick'] == tick and
                row['sequences'] == [header['intro_sequence'] + 1 + index * 3 + i for i in range(3)],
                'native sample alignment differs')
        controls = inputs['samples'][index]
        wanted_events = events.get(tick - 1, []) if index >= 12 else []
        require(controls['sample'] == index and controls['cpp_tick'] == tick and controls['events'] == wanted_events,
                'native input boundary differs')
        before, after = bytes.fromhex(controls['before_bank_hex']), bytes.fromhex(controls['after_bank_hex'])
        require(len(before) == len(after) == 10, 'native input bank extent differs')
        bank = bytearray(before)
        for event in wanted_events:
            bank[original.BANK[event['key']] - 0x1b78] = event['action'] != 'up'
        require(bytes(bank) == after, 'undeclared input-bank write')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        for pi, field in enumerate(('pre', 'rendered', 'post')):
            state = row[field]
            campaign.raw_state(state, 3, (150, 60))
            require(state['frame'] == tick - 1107, 'native gameplay frame skipped')
            if tick <= FIRST:
                previous_row = old[index + 1]
                require(handoff.native_boundary(state, row['dac'][pi], header['atlas']) ==
                        handoff.native_boundary(previous_row[field], previous_row['dac'][pi], old[0]['atlas']) and
                        row['rgb_sha256'] == previous_row['rgb_sha256'], 'fresh original prefix differs')
            if tick >= FIRST and pi:
                boundaries.append(dict(kind='boundary', tick=tick, phase=('present', 'post_update')[pi - 1],
                                       projection=native_projection(state, row['dac'][pi], header['atlas']),
                                       rgb_sha256=hashlib.sha256(previous).hexdigest() if pi == 1 else None,
                                       native_gate=None))
    journal = fidelity.strict_json((capture / 'new-suffix-ds-journal.json').read_text())
    require(journal['complete'] is True and len(journal['records']) == 1455 and
            journal['new_gameplay_state_injections'] is False, 'raw native suffix incomplete')
    indexed = {(r['tick'], r['phase']): r for r in boundaries}
    with gzip.open(capture / 'new-suffix-ds.bin.gz', 'rb') as stream:
        for index, record in enumerate(journal['records']):
            data = stream.read(65536)
            tick, pi = FIRST + 1 + index // 3, index % 3
            row, field = rows[tick - 3777 + 1], ('pre', 'rendered', 'post')[pi]
            state = row[field]
            require(len(data) == 65536 and hashlib.sha256(data).hexdigest() == record['sha256'] and
                    record['index'] == index and record['cpp_tick'] == tick and record['stage'] == pi + 2 and
                    record['sequence'] == row['sequences'][pi], 'raw DS boundary/hash differs')
            require(data[0x79b7] == 3 and original.word(data, 0x78c2) == state['frame'] and
                    original.word(data, 0xc204) == 150 and original.word(data, 0x2096) // 8 + 21 == 60 and
                    struct.unpack_from('<I', data, 0x1afe)[0] == state['rng'] and data[0x208d] == state['actor_count'],
                    'raw DS identity differs')
            for key, offset, length in (('actors', 0x1bd4, state['actor_count'] * 38),
                    ('visuals', 0xc21e, data[0xc496] * 8), ('inventory', 0x1b6c, 12), ('scores', 0x785a, 92),
                    ('destruction', 0x78c6, 4), ('progress', 0x2076, 36), ('spawners', 0x74c6, data[0x79a6] * 30)):
                require(data[offset:offset + length].hex() == state[key], 'raw DS projection differs: ' + key)
            for player_index, player in enumerate(state['players'], 1):
                offset = 0x1b62 + player_index * 38
                visual = 0xc21e + data[offset + 1] * 8
                require(data[offset:offset + 38].hex() == player['raw'] and
                        data[visual:visual + 8].hex() == player['visual'], 'raw DS player differs')
            if pi:
                boundary = indexed[tick, ('present', 'post_update')[pi - 1]]
                boundary['projection']['terrain'] = projection.native_terrain(data)
                boundary['native_gate'] = projection.native_gate(data)
        require(not stream.read(1), 'trailing raw DS bytes')
    result = [metadata(outcome['assets']), *boundaries,
              dict(kind='complete', frames=FRAMES, boundaries=972, patches_restored=True)]
    validate(result)
    guarded = campaign.guard_inputs(rows[-2]['post'], rows[-2]['dac'][2], header['atlas'])
    campaign.guard_projection(guarded, boundaries[-1]['projection']['mapped'])
    out.mkdir(parents=True)
    with original.compressed_writer(out / 'reference.jsonl.gz') as emit:
        for row in result:
            emit(row)
    (out / 'route.txt').write_bytes((capture / 'level3-route.txt').read_bytes())
    (out / 'guard-input.json').write_bytes(original.json_bytes(guarded))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for prefix, directory, pins in (('control-', control, CONTROL_PINS), ('capture-', capture, CAPTURE_PINS)):
        for name in pins:
            (EVIDENCE / (prefix + name + '.gz')).write_bytes(gzip.compress((directory / name).read_bytes(), mtime=0))
    print(original.json_bytes(dict(status='packed', reference_sha256=fidelity.sha256(out / 'reference.jsonl.gz'),
                                   guard_sha256=fidelity.sha256(out / 'guard-input.json'))).decode(), flush=True)


def validate(rows):
    require(len(rows) == 974 and fidelity.first_difference(metadata(rows[0]['assets']), rows[0]) is None and
            rows[-1] == dict(kind='complete', frames=FRAMES, boundaries=972, patches_restored=True),
            'gate fixture contract differs')
    first_gate = None
    for index, row in enumerate(rows[1:-1]):
        tick, phase = FIRST + index // 2, ('present', 'post_update')[index % 2]
        require(set(row) == {'kind', 'tick', 'phase', 'projection', 'rgb_sha256', 'native_gate'} and
                row['kind'] == 'boundary' and row['tick'] == tick and row['phase'] == phase and
                row['projection']['mapped']['frame'] == tick - 1107 and row['projection']['mapped']['level'] == 3 and
                (row['rgb_sha256'] is None) == (phase == 'post_update'), 'invalid native gate boundary')
        require(set(row['projection']) == {'mapped', 'lifecycle', 'monsters', 'markers'} |
                ({'terrain'} if tick > FIRST else set()), 'gate projection extent differs')
        require((row['native_gate'] is None) == (tick == FIRST), 'native gate raw extent differs')
        if tick > FIRST:
            gate = row['native_gate']
            require(set(gate) == {'bonus_flag', 'destruction_flag', 'collapse_count'} and
                    all(type(v) is int for v in gate.values()) and
                    gate['bonus_flag'] in (0, 1) and gate['destruction_flag'] in (0, 1) and
                    gate['collapse_count'] == len(row['projection']['terrain']['collapse']), 'native gate/table differs')
            if phase == 'post_update' and projection.eligible(gate) and first_gate is None:
                first_gate = tick
    final = rows[-2]['projection']['mapped']
    require(first_gate == LAST and rows[-4]['native_gate']['collapse_count'] == 1 and
            rows[-2]['native_gate'] == dict(bonus_flag=1, destruction_flag=1, collapse_count=0) and
            final['progress'] == [9, 167] and final['score'] == 43620 and final['rng'] == 806698761 and
            final['players'][0]['energy'] == 66 and final['players'][0]['reserve'] == 0 and
            final['players'][0]['inventory'] == [200, 10, 0, 0, 1] and final['players'][0]['xy'] == [196.0, 264.0],
            'first empty-collapse gate/endpoint differs')


def fixture(root=FIXTURE):
    check_route(root / 'route.txt')
    require(fidelity.sha256(root / 'reference.jsonl.gz') == REFERENCE_SHA256 and
            fidelity.sha256(root / 'guard-input.json') == GUARD_SHA256, 'gate fixture fingerprint differs')
    rows = handoff.load(root / 'reference.jsonl.gz')
    validate(rows)
    require(rows[0]['assets'] == campaign.fixture()[0]['assets'], 'gate fixture assets differ')
    return rows


def check_cpp_boundary(state, expected, phase):
    fidelity.validate_state(state)
    difference = fidelity.first_difference(expected['projection'], cpp_projection(state, 'terrain' in expected['projection']))
    require(difference is None, 'gate C++ projection differs: ' + str(difference))
    if phase == 'post_update' and expected['native_gate'] is not None:
        require(state['flow'][4] == int(projection.eligible(expected['native_gate'])), 'C++ completion gate timing differs')


def guard_cpp_boundary(state, expected):
    edits = [lambda s: s['players'][0]['inventory'].__setitem__(1, s['players'][0]['inventory'][1] + 1),
             lambda s: s['players'][0]['inventory'].__setitem__(2, s['players'][0]['inventory'][2] + 1),
             lambda s: s['players'][0]['health'].__setitem__(0, s['players'][0]['health'][0] + 1),
             lambda s: s.__setitem__('random_seed', s['random_seed'] ^ 1),
             lambda s: s['players'][0].__setitem__('x', s['players'][0]['x'] + 1),
             lambda s: s['progress'].__setitem__(1, s['progress'][1] + 1),
             lambda s: s['flow'].__setitem__(4, 0)]
    edits += [lambda s, key=key: s.__setitem__(key, bytes([bytes.fromhex(s[key])[0] ^ 1]).hex() + s[key][2:])
              for key in ('tiles_hex', 'words_hex')]
    for edit in edits:
        changed = copy.deepcopy(state)
        edit(changed)
        require(changed != state, 'vacuous C++ gate mutation')
        try:
            check_cpp_boundary(changed, expected, 'post_update')
        except fidelity.EvidenceError:
            pass
        else:
            raise fidelity.EvidenceError('C++ gate mutation accepted')
    return len(edits)


def compare(cpp):
    rows = fixture()
    settings, events = check_route(cpp / 'route.txt')
    count, frames, previous_seq, mutations = 0, 0, None, 0
    with (cpp / 'trace.jsonl').open(encoding='utf-8') as stream:
        header = fidelity.strict_json(next(stream))
        require(header['schema'] == 'lezac.level1.scout.v1' and header['candidate_only'] is True and
                header['capture_from_tick'] == FIRST and header['ticks'] == LAST and
                header['seed'] == settings['seed'] and header['step_us'] == settings['step_us'] and
                header['source'] == 'cpp' and header['phase_model'] == 'cpp-pre-actors-v2' and
                header['state_scope'] == 'level1-observations-v2' and
                header['input_model'] == 'sdl-events-original-intro-wait-v1' and
                header['original_fidelity_claim'] is False and header['width'] == 320 and header['height'] == 200 and
                header['route_fnv1a64'] == fidelity.fnv1a64((cpp / 'route.txt').read_bytes()) and
                header['asset_fnv1a64'] == {name: fidelity.fnv1a64((ROOT / name).read_bytes()) for name in fidelity.ASSETS},
                'C++ scout provenance differs')
        for line in stream:
            row = fidelity.strict_json(line)
            if row['kind'] == 'complete':
                require(count == FRAMES * 4 and frames == FRAMES and row['ticks'] == LAST and
                        row['frames'] == FRAMES and row['retained_checkpoints'] == count and
                        row['candidate_only'] is True and row['capture_from_tick'] == FIRST and
                        row['events'] == sum(map(len, events.values())) and row['level1_route_complete'] is True and
                        row['checkpoints'] == previous_seq + 1 and row['original_fidelity_claim'] is False and
                        row['port_functionally_complete'] is False and not stream.read(), 'C++ scout footer differs')
                require(mutations == 9, 'C++ gate guard not exercised')
                return dict(status='match', frames=frames, boundaries=972, pixels=frames * 64000,
                            cpp_projection_mutations_rejected=mutations,
                            original_gate_eligible_tick=LAST, raw_ds_boundaries=1455,
                            full_prefix_executed_from_level1=True, completed_levels=[1, 2], **CLAIMS)
            tick, phase = FIRST + count // 4, ('input', 'present', 'after_nonplayers', 'post_update')[count % 4]
            require(row['kind'] == 'checkpoint' and row['tick'] == tick and row['phase'] == phase and tick <= LAST and
                    row['events'] == events.get(tick - 1, []) and
                    (previous_seq is None or row['seq'] == previous_seq + 1), 'C++ scout boundary order differs')
            previous_seq = row['seq']
            fidelity.validate_state(row['state'])
            if phase in ('present', 'post_update'):
                expected = rows[1 + (tick - FIRST) * 2 + int(phase == 'post_update')]
                check_cpp_boundary(row['state'], expected, phase)
                if tick == LAST and phase == 'post_update':
                    mutations = guard_cpp_boundary(row['state'], expected)
                if phase == 'present':
                    pixels = fidelity.read_ppm(fidelity.safe_file(cpp, row['frame']))
                    require(fidelity.fnv1a64(pixels) == row['rgb_fnv1a64'] and
                            hashlib.sha256(pixels).hexdigest() == expected['rgb_sha256'], 'gate RGB differs')
                    frames += 1
                else:
                    require('frame' not in row and 'rgb_fnv1a64' not in row, 'unexpected post-update RGB')
            count += 1
    raise fidelity.EvidenceError('missing C++ scout footer')


def replay(exe, out):
    out.mkdir(parents=True, exist_ok=True)
    cpp = out.resolve() / ('run-' + uuid.uuid4().hex)
    assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
    command = [str(exe.resolve()), '--replay-level1-scout', str(FIXTURE / 'route.txt'), str(cpp), str(FIRST),
               '--original-intro-wait', '--result-reels']
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                       LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1')
    result = subprocess.run(command, cwd=ROOT, env=environment, text=True, capture_output=True, timeout=550)
    require(cpp.is_dir(), 'C++ scout produced no evidence directory')
    (cpp / 'stdout.txt').write_text(result.stdout, encoding='utf-8')
    (cpp / 'stderr.txt').write_text(result.stderr, encoding='utf-8')
    (cpp / 'command.json').write_bytes(original.json_bytes(dict(command=command, executable_sha256=fidelity.sha256(exe),
        source=fidelity.source_version(ROOT), assets=assets, audio='dummy', video='dummy',
        replay_reader_sha256=fidelity.sha256(Path(__file__)),
        projection_reader_sha256=fidelity.sha256(Path(projection.__file__)), **CLAIMS)))
    require(result.returncode == 0, 'C++ scout failed: ' + result.stderr.strip())
    shutil.copyfile(FIXTURE / 'route.txt', cpp / 'route.txt')
    require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'C++ scout changed assets')
    report = compare(cpp)
    (cpp / 'comparison.json').write_bytes(original.json_bytes(report))
    return report


def guard():
    rows, rejected = fixture(), 0
    edits = [lambda r: r.pop(1), lambda r: r.insert(1, copy.deepcopy(r[1])),
             lambda r: r[0].__setitem__('completed_levels', [1, 2, 3]),
             lambda r: r[0].__setitem__('original_gate_eligible_tick', LAST - 1),
             lambda r: r[0].__setitem__('state_injections', True),
             lambda r: r[0].__setitem__('raw_ds_boundaries', 1454),
             lambda r: r[0].__setitem__('native_stream_sha256', '0' * 64),
             lambda r: r[-1].__setitem__('patches_restored', False),
             lambda r: r[1].__setitem__('tick', FIRST - 1), lambda r: r[1].__setitem__('rgb_sha256', None),
             lambda r: r[-2]['projection']['mapped']['progress'].__setitem__(1, 168),
             lambda r: r[-4]['native_gate'].__setitem__('collapse_count', 0)]
    edits += [lambda r, key=key: r[0].__setitem__(key, True) for key in CLAIMS]
    edits += [lambda r, key=key, value=value: r[-2]['native_gate'].__setitem__(key, value)
              for key, value in (('bonus_flag', 0), ('destruction_flag', 0), ('collapse_count', 1))]
    for edit in edits:
        changed = copy.deepcopy(rows)
        edit(changed)
        require(changed != rows, 'vacuous gate mutation')
        try:
            validate(changed)
        except fidelity.EvidenceError:
            rejected += 1
        else:
            raise fidelity.EvidenceError('native gate mutation accepted')
    producer_rejected = 0
    with tempfile.TemporaryDirectory(prefix='lezac-gate-guard-') as temporary:
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
                    raise fidelity.EvidenceError('gate producer mutation accepted')
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
                raise fidelity.EvidenceError('gate fixture byte mutation accepted')
    typed = campaign.guard_projection(fidelity.strict_json((FIXTURE / 'guard-input.json').read_text()),
                                      rows[-2]['projection']['mapped'])
    require(producer_rejected == len(CONTROL_PINS) + len(CAPTURE_PINS), 'gate producer guard coverage differs')
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
        require(args.cpp is not None, 'C++ scout evidence required')
        report = compare(args.cpp)
    else:
        report = guard()
    print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
