"""Original-backed Level 3 bomb/pickup route after ordinary Level 1/2 completion."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
from pathlib import Path
import tempfile
import uuid

import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original
import level1_results as results
import natural_campaign as campaign

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level3_objective'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level3_objective_20261005'
SCHEMA = 'lezac-natural-level3-objective-boundaries-v1'
TICKS, FIRST_TICK, FRAMES = 4438, 3789, 650
ROUTE_SHA256 = 'ef1dbc608c94ff670b6aae4b0bb7922063be17876009ed6110264a0ced295728'
NATIVE_SHA256 = '423787e0742896b696f4890ca7f4566291eee9c4e5f7bcf169d18780a35c09c8'
REFERENCE_SHA256 = '243af32b37aacc54d64d5853d1da3def16f30235b86f5ecbe04711862d3bd00b'
GUARD_INPUT_SHA256 = '62e56c2e8da59632001fdfa7c13033591855b67eaf81a61f19d061e37b8b91dd'
CAPTURE_PINS = {
    'objective-observer-wrapper.py': '67fbad0106d75c06652708f8ec9667d2b607665947b26d5811d05e6c1c5206f7',
    'level3-handoff-observer.py': '98a98127128d7aededb97f92468bcdac790a2eb59a4c425e39ea333de8b5b282',
    'outcome-observer.py': '33869f46e0afa16ef9d64d7a045ed6e9dfa3e2a4c7f54f3c88add4b1ebafe774',
    'extension-observer.py': 'acb311ed85fb594afc1d92d6774036a742388339b920bcc0f81206cabfb30dec',
    'observer.py': '0af5c0a1f0ef7f87c4898ecc512784db315d281547b97bf45e57bfa5c87b1985',
    'results-observer.py': '082e5c9f7f5c1fb34675aee8d4d7bb9a69bb78f382e79b98b860a723345fc093',
    'outcome-manifest.json': '1e7412b0f5d2e0b79f73629c7a096793a69b006067ce5e0da70ffb36cc2e6900',
    'objective-native-audit.json': '5fde1caae8e2819fb251b81f613780e29dae219cf80c680a4951f9efca628ec9',
    'objective-controller.json': '97d6c48b9e8690da01580e57c3eebd1e2e474f042618451f5a08996ffddfec44',
    'objective-input-journal.json': 'ba23259c321f00b79b851e65db43e2cd205936bf63927c488a43808e53b0a12e',
}
require = fidelity.require


def check_producer(capture):
    for name, digest in CAPTURE_PINS.items():
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'untrusted Level 3 producer: ' + name)


def check_route(route):
    require(fidelity.sha256(route) == ROUTE_SHA256, 'Level 3 route fingerprint differs')
    settings, events = fidelity.read_route(route)
    prefix_settings, prefix = fidelity.read_route(campaign.FIXTURE / 'route.txt')
    require(settings['ticks'] == TICKS and all(settings[key] == prefix_settings[key] for key in ('seed', 'step_us')) and
            {tick: items for tick, items in events.items() if tick < campaign.TICKS} == prefix,
            'Level 3 changed the immutable complete prefix')
    require(all(item['key'] in original.BANK for tick, items in events.items() if tick >= campaign.TICKS
                for item in items), 'non-gameplay Level 3 extension input')
    return events


def pack(capture, out):
    require(not out.exists(), 'fresh Level 3 fixture output required')
    check_producer(capture)
    require(not (capture / 'failure.json').exists() and not (capture / 'objective-observer-failure.json').exists(),
            'failed Level 3 native capture')
    outcome = fidelity.strict_json((capture / 'outcome-manifest.json').read_text())
    require(outcome['status'] == 'captured' and outcome['patches_restored'] is True and
            outcome['gameplay_frames'] == 2352 and outcome['result_samples'] == 34 and
            outcome['gate_cpp_tick'] == campaign.GATE_TICK and outcome['gate_native_frame'] == 2669,
            'incomplete ordinary Level 2 completion')
    for name, digest in outcome['files'].items():
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'native file changed: ' + name)
    require(outcome['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS} and
            original.fingerprint(capture) == handoff.PREFIX_SHA256 and
            fidelity.sha256(capture / 'level3-handoff.jsonl.gz') == NATIVE_SHA256, 'native asset/prefix/stream differs')
    events = check_route(capture / 'level3-route.txt')
    base = campaign.fixture()
    expected = {(row['tick'], row['phase']): row for row in base[1:-1]}

    def prefix_sample(row, tick, level, dimensions):
        for field, phase, pi in (('rendered', 'present', 1), ('post', 'post_update', 2)):
            campaign.raw_state(row[field], level, dimensions)
            wanted = expected[tick, phase]
            require(campaign.native_boundary(row[field], row['dac'][pi], header['atlas']) == wanted['mapped'],
                    'fresh mapped prefix differs')
        require(row['rgb_sha256'] == expected[tick, 'present']['rgb_sha256'], 'fresh prefix RGB differs')

    entry = handoff.load(capture / 'handoff.jsonl.gz')
    handoff.validate(entry)
    header = entry[0]
    for index, row in enumerate(entry[1:-1]):
        prefix_sample(row, 731 + index, 2, (100, 53))
    gameplay = handoff.load(capture / 'gameplay.jsonl.gz')
    header = gameplay[0]
    require(len(gameplay) == 2354 and gameplay[-1]['patches_restored'] is True and
            gameplay[-1]['gate_eligible'] is True, 'incomplete Level 2 gameplay prefix')
    previous = bytes(192000)
    for index, row in enumerate(gameplay[1:-1]):
        require(row['sample'] == index and row['cpp_tick'] == 743 + index and
                row['events'] == events.get(742 + index, []) and row['gate_eligible'] == (index == 2351),
                'Level 2 route/gate prefix differs')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        prefix_sample(row, 743 + index, 2, (100, 53))
    baseline = gameplay[-2]['post']
    reels = handoff.load(capture / 'results.jsonl.gz')
    require(len(reels) == 36 and reels[-1]['samples'] == 34 and reels[-1]['gameplay_frozen'] is True,
            'incomplete Level 2 results prefix')
    previous = bytes(192000)
    for index, row in enumerate(reels[1:-1]):
        require(row['sample'] == index and row['player'] == 1 and
                all(row['state'][key] == baseline[key] for key in results.FROZEN), 'result prefix advanced gameplay')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        wanted = expected[index + 42, 'result']
        require(campaign.native_boundary(row['state'], row['dac'], reels[0]['atlas']) == wanted['mapped'] and
                row['rgb_sha256'] == wanted['rgb_sha256'], 'result prefix mapped state/pixels differ')

    native = handoff.load(capture / 'level3-handoff.jsonl.gz')
    header = native[0]
    require(len(native) == 664 and header['frames'] == 662 and header['dimensions'] == [150, 60] and
            header['first_cpp_tick'] == 3777 and header['ack_sequence'] + 1 == header['intro_sequence'] and
            native[-1]['frames'] == 662 and native[-1]['native_level3_entry_observed'] is True,
            'incomplete native Level 3 stream')
    for name in ('ack', 'intro_ack'):
        queue = header[name]
        before, after = bytes.fromhex(queue['before_bda_hex']), bytes.fromhex(queue['bda_hex'])
        head, tail = queue['head'], queue['tail']
        require(len(before) == len(after) == 64 and original.word(before, 0x1a) == original.word(before, 0x1c) and
                0x1e <= head < 0x3e and head % 2 == 0 and tail == (head + 2 if head < 0x3c else 0x1e) and
                original.word(after, 0x1a) == head and original.word(after, 0x1c) == tail and
                original.word(after, head) == queue['key_word'] == 0x1c0d, 'not a fresh BIOS Return')
    for key, tick, palette, digest in (
        ('baseline', 3642, 'baseline_dac', 'ack_rgb_sha256'), ('intro', 3776, 'intro_dac', 'intro_rgb_sha256')):
        require(campaign.native_boundary(header[key], header[palette],
                reels[0]['atlas'] if key == 'baseline' else header['atlas']) == expected[tick, 'present']['mapped'] and
                header[digest] == expected[tick, 'present']['rgb_sha256'], 'fresh handoff prefix differs')
    journal = fidelity.strict_json((capture / 'objective-input-journal.json').read_text())
    require(journal['complete'] is True and len(journal['samples']) == 662 and
            journal['new_gameplay_state_injections'] is False, 'incomplete input journal')
    rows, previous = [], bytes(192000)
    for index, row in enumerate(native[1:-1]):
        tick = 3777 + index
        require(row['sample'] == index and row['cpp_tick'] == tick and
                row['sequences'] == [header['intro_sequence'] + 1 + index * 3 + i for i in range(3)],
                'Level 3 frame/phase alignment differs')
        for field in ('pre', 'rendered', 'post'):
            campaign.raw_state(row[field], 3, (150, 60))
            require(row[field]['frame'] == 2670 + index, 'native Level 3 gameplay frame skipped')
        require(len(row['dac']) == 3, 'missing native palettes')
        for value in row['dac']:
            handoff.dac(value)
        controls = journal['samples'][index]
        wanted_events = events.get(tick - 1, []) if index >= 12 else []
        require(controls['sample'] == index and controls['cpp_tick'] == tick and
                controls['events'] == wanted_events, 'native input journal phase differs')
        before, after = bytes.fromhex(controls['before_bank_hex']), bytes.fromhex(controls['after_bank_hex'])
        require(len(before) == len(after) == 10, 'input bank extent differs')
        wanted_bank = bytearray(before)
        for event in wanted_events:
            wanted_bank[original.BANK[event['key']] - 0x1b78] = event['action'] != 'up'
        require(bytes(wanted_bank) == after, 'undeclared native input-bank write')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        if index < 12:
            prefix_sample(row, tick, 3, (150, 60))
            continue
        for field, phase, pi in (('rendered', 'present', 1), ('post', 'post_update', 2)):
            rows.append({'kind': 'boundary', 'tick': tick, 'phase': phase, 'region': 'level3_objective',
                         'mapped': campaign.native_boundary(row[field], row['dac'][pi], header['atlas']),
                         'rgb_sha256': hashlib.sha256(previous).hexdigest() if phase == 'present' else None})
    metadata = {'kind': 'header', 'schema': SCHEMA, 'ticks': TICKS, 'first_tick': FIRST_TICK, 'frames': FRAMES,
                'dimensions': [150, 60], 'route_sha256': ROUTE_SHA256, 'native_stream_sha256': NATIVE_SHA256,
                'prefix_reference_sha256': campaign.REFERENCE_SHA256, 'capture_pins': CAPTURE_PINS,
                'assets': outcome['assets'], 'audio': 'dummy', 'state_injections': False,
                'completed_levels': [1, 2], 'entered_level': 3, 'natural_level3_completion_claim': False,
                'first_pickup_tick': 3988, **campaign.CLAIMS}
    footer = {'kind': 'complete', 'frames': FRAMES, 'boundaries': FRAMES * 2, 'patches_restored': True}
    validate([metadata, *rows, footer])
    guarded = campaign.guard_inputs(native[-2]['post'], native[-2]['dac'][2], header['atlas'])
    campaign.guard_projection(guarded, rows[-1]['mapped'])
    out.mkdir(parents=True)
    with original.compressed_writer(out / 'reference.jsonl.gz') as emit:
        for row in (metadata, *rows, footer):
            emit(row)
    (out / 'route.txt').write_bytes((capture / 'level3-route.txt').read_bytes())
    (out / 'guard-input.json').write_bytes(original.json_bytes(guarded))
    print(original.json_bytes({'status': 'packed', 'reference_sha256': fidelity.sha256(out / 'reference.jsonl.gz'),
                               'guard_input_sha256': fidelity.sha256(out / 'guard-input.json'),
                               'frames': FRAMES, 'boundaries': len(rows)}).decode(), flush=True)


def validate(rows):
    require(len(rows) == 1302 and rows[0]['schema'] == SCHEMA and rows[0]['ticks'] == TICKS and
            rows[0]['first_tick'] == FIRST_TICK and rows[0]['frames'] == FRAMES and
            rows[0]['dimensions'] == [150, 60] and rows[0]['route_sha256'] == ROUTE_SHA256 and
            rows[0]['native_stream_sha256'] == NATIVE_SHA256 and
            rows[0]['prefix_reference_sha256'] == campaign.REFERENCE_SHA256 and
            rows[0]['capture_pins'] == CAPTURE_PINS and rows[0]['state_injections'] is False and
            rows[0]['completed_levels'] == [1, 2] and rows[0]['entered_level'] == 3 and
            rows[0]['natural_level3_completion_claim'] is False and rows[0]['first_pickup_tick'] == 3988 and
            rows[0]['audio'] == 'dummy' and all(rows[0][key] is value for key, value in campaign.CLAIMS.items()) and
            rows[-1] == {'kind': 'complete', 'frames': FRAMES, 'boundaries': 1300, 'patches_restored': True},
            'Level 3 fixture contract differs')
    keys, frames = set(), 0
    for row in rows[1:-1]:
        key = row['tick'], row['phase']
        require(set(row) == {'kind', 'tick', 'phase', 'region', 'mapped', 'rgb_sha256'} and
                row['kind'] == 'boundary' and row['region'] == 'level3_objective' and key not in keys and
                row['mapped']['level'] == 3 and row['mapped']['frame'] == row['tick'] - 1107 and
                (row['rgb_sha256'] is None) == (row['phase'] == 'post_update'), 'invalid Level 3 boundary')
        if row['phase'] == 'post_update':
            require(row['mapped']['progress'][0] == int(row['tick'] >= 3988), 'native first pickup moved')
        keys.add(key)
        frames += row['rgb_sha256'] is not None
    require(keys == {(tick, phase) for tick in range(FIRST_TICK, TICKS + 1) for phase in ('present', 'post_update')}
            and frames == FRAMES, 'incomplete Level 3 frame/phase coverage')
    last = next(row['mapped'] for row in rows[1:-1] if row['tick'] == TICKS and row['phase'] == 'post_update')
    require(last['progress'] == [1, 36] and last['players'][0]['energy'] == 62 and
            last['players'][0]['reserve'] == 1 and last['players'][0]['inventory'] == [200, 17, 0, 0, 1] and
            last['players'][0]['xy'] == [275, 272] and last['score'] == 18770, 'Level 3 endpoint differs')


def fixture(root=FIXTURE):
    require(fidelity.sha256(root / 'reference.jsonl.gz') == REFERENCE_SHA256 and
            fidelity.sha256(root / 'guard-input.json') == GUARD_INPUT_SHA256, 'Level 3 fixture fingerprint differs')
    check_route(root / 'route.txt')
    rows = handoff.load(root / 'reference.jsonl.gz')
    validate(rows)
    require(rows[0]['assets'] == campaign.fixture()[0]['assets'], 'Level 3 fixture assets differ')
    return rows


def compare(cpp):
    extension, prefix = fixture(), campaign.fixture()
    rows = [prefix[0], *prefix[1:-1], *extension[1:-1], prefix[-1]]
    report = campaign.compare_rows(cpp, rows, FIXTURE / 'route.txt', TICKS)
    require(report['frames'] == 3411 and report['boundaries'] == 6746, 'full campaign/extension coverage differs')
    return {**report, 'new_level3_frames': FRAMES, 'new_level3_boundaries': 1300,
            'natural_level3_completion_claim': False}


def guard():
    rows, mutations = fixture(), 0
    edits = (lambda r: r.pop(1), lambda r: r.insert(1, copy.deepcopy(r[1])),
             lambda r: r[0].__setitem__('dimensions', [100, 53]),
             lambda r: r[0].__setitem__('first_tick', 3777),
             lambda r: r[0].__setitem__('completed_levels', [1, 2, 3]),
             lambda r: r[0].__setitem__('state_injections', True),
             lambda r: r[0].__setitem__('prefix_reference_sha256', '0' * 64),
             lambda r: r[0].__setitem__('native_stream_sha256', '0' * 64),
             lambda r: r[0].__setitem__('all_actor_fields_compared', True),
             lambda r: r[-1].__setitem__('patches_restored', False),
             lambda r: r[1].__setitem__('tick', FIRST_TICK - 1),
             lambda r: r[1].__setitem__('phase', 'pre_update'),
             lambda r: r[1].__setitem__('rgb_sha256', None),
             lambda r: r[-2]['mapped']['progress'].__setitem__(0, 2),
             lambda r: r[0].__setitem__('natural_level3_completion_claim', True))
    for edit in edits:
        changed = copy.deepcopy(rows)
        edit(changed)
        require(changed != rows, 'vacuous Level 3 semantic mutation')
        try:
            validate(changed)
        except fidelity.EvidenceError:
            mutations += 1
        else:
            raise fidelity.EvidenceError('Level 3 semantic mutation accepted')
    with tempfile.TemporaryDirectory(prefix='lezac-level3-guard-') as temporary:
        root = Path(temporary)
        raw = (FIXTURE / 'reference.jsonl.gz').read_bytes()
        for name in ('route.txt', 'guard-input.json'):
            (root / name).write_bytes((FIXTURE / name).read_bytes())
        for bad in (raw[:-1], raw + b'\0', bytes([raw[0] ^ 1]) + raw[1:]):
            (root / 'reference.jsonl.gz').write_bytes(bad)
            try:
                fixture(root)
            except fidelity.EvidenceError:
                mutations += 1
            else:
                raise fidelity.EvidenceError('Level 3 fixture mutation accepted')
    guarded = fidelity.strict_json((FIXTURE / 'guard-input.json').read_text())
    typed = campaign.guard_projection(guarded, rows[-2]['mapped'])
    producer_mutations = 0
    with tempfile.TemporaryDirectory(prefix='lezac-level3-producer-') as temporary:
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
                raise fidelity.EvidenceError('untrusted Level 3 producer accepted')
            require(not (root / 'must-not-exist').exists(), 'untrusted producer wrote fixture output')
            (root / name).write_bytes(raw)
    require(mutations == 18 and typed == 291 and producer_mutations == len(CAPTURE_PINS), 'Level 3 guard coverage differs')
    print(original.json_bytes({'status': 'guarded', 'mutations_rejected': mutations,
                               'typed_field_mutations_rejected': typed,
                               'producer_mutations_rejected': producer_mutations}).decode(), flush=True)


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
        (cpp / 'natural-level3-objective-comparison.json').write_bytes(original.json_bytes(report))
        print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
