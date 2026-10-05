"""Original-backed lower-room pickups and natural Level 3 portal return."""
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
import natural_level3_objective as first
import natural_level3_second_objective as second
import natural_level3_third_objective as third

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level3_portal'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level3_portal_20261005'
SCHEMA = 'lezac-natural-level3-portal-boundaries-v1'
TICKS, FIRST_TICK, FRAMES, NATIVE_FRAMES = 6228, 5259, 970, 2452
PICKUP_TICKS, PORTAL_TICK = (5933, 5935, 5937), 6109
ROUTE_SHA256 = '1e1edf82bda0de51a6d62a40810e120651391ac666991c31ad4c9b1836a321b6'
NATIVE_SHA256 = '6a1ed9310639a39ca067ead99f7de218bbc3d324df5d4f4bbddae4c4013d6581'
REFERENCE_SHA256 = '15c5422546823e6a8ff71472880204cdae101a162d3cbfbd6d6575bfcda59834'
GUARD_INPUT_SHA256 = 'c3a2004db6d01706a66e03d5bf19dcce58896eea72ef4dd180ea2a90daaa0f74'
CAPTURE_PINS = {
    **{key: value for key, value in third.CAPTURE_PINS.items() if key in (
        'objective-observer-wrapper.py', 'level3-handoff-observer.py', 'outcome-observer.py',
        'extension-observer.py', 'observer.py', 'results-observer.py')},
    'lower-objectives-capture-driver.py': 'f37295c233fb829b842bea49595682147a623539ecc288cc3bf00c907d4cb19a',
    'lower-objectives-native-audit.json': 'be9366a4b1f3082092a9d8b44e85518c27ef7f5279cefa0fbe2a7db4cc8edab3',
    'lower-objectives-runtime-configuration.json': '3239234e1316b08bdb26dda39c1d1c5639b980c47246840530e4f75894408378',
    'objective-controller.json': '4226d9bfd122d096eef8063f70eb03cff335075511c025850ca7eb7c607d3da3',
    'objective-input-journal.json': 'd8f033fc01a6664c51a16ed974624112e9033838bd2cc51e8de2915911d80f90',
    'outcome-manifest.json': 'd695b3829f2b916b77edcce22f7a3ec250082a5db2a2f4ef4778dc91484e0dd4',
}
require = fidelity.require


def prefix_rows():
    return [row for fixture in (campaign.fixture(), first.fixture(), second.fixture(), third.fixture())
            for row in fixture[1:-1]]


def check_producer(capture):
    for name, digest in CAPTURE_PINS.items():
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'untrusted portal producer: ' + name)


def check_route(route):
    require(fidelity.sha256(route) == ROUTE_SHA256, 'portal route fingerprint differs')
    settings, events = fidelity.read_route(route)
    baseline, prefix = fidelity.read_route(third.FIXTURE / 'route.txt')
    require(settings['ticks'] == TICKS and all(settings[key] == baseline[key] for key in ('seed', 'step_us')) and
            {tick: items for tick, items in events.items() if tick < third.TICKS} == prefix,
            'portal route changed the immutable third-pickup prefix')
    require(all(event['key'] in ('m', 'n', 'x', 'z', 'c') and event['action'] in ('down', 'up')
                for tick, items in events.items() if tick >= third.TICKS for event in items),
            'unexpected ordinary portal control')
    return events


def pack(capture, out):
    require(not out.exists(), 'fresh portal fixture output required')
    check_producer(capture)
    require(not any((capture / name).exists() for name in ('failure.json', 'objective-observer-failure.json')),
            'failed native portal capture')
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
    audit = fidelity.strict_json((capture / 'lower-objectives-native-audit.json').read_text())
    config = fidelity.strict_json((capture / 'lower-objectives-runtime-configuration.json').read_text())
    require(audit['status'] == 'captured_and_mapped_prefix_verified' and audit['patches_restored'] is True and
            audit['route_ticks'] == config['route_ticks'] == TICKS and audit['level3_frames'] == NATIVE_FRAMES and
            config['runtime_frames'] == NATIVE_FRAMES and audit['unchanged_native_prefix_frames'] == 2132 and
            audit['prior_native_stream_sha256'] == '24eca91a2bedbbc35aff0cfe9e782e041e802ef666db78e4f0c4ebc4cc09476e' and
            audit['variant_source_sha256'] == config['variant_source_sha256'] == CAPTURE_PINS['lower-objectives-capture-driver.py'] and
            audit['variant_configuration_sha256'] == CAPTURE_PINS['lower-objectives-runtime-configuration.json'] and
            audit['parent_sha256'] == config['parent_sha256'] == CAPTURE_PINS['objective-observer-wrapper.py'] and
            audit['native_stream_sha256'] == NATIVE_SHA256 and audit['route_sha256'] == config['route_sha256'] == ROUTE_SHA256 and
            audit['new_gameplay_state_injections'] is config['new_gameplay_state_injections'] is False and
            audit['audio'] == config['audio'] == 'dummy', 'native portal runtime configuration differs')
    events = check_route(capture / 'level3-route.txt')
    expected = {(row['tick'], row['phase']): row for row in prefix_rows()}
    require(len(expected) == 8386, 'canonical prefix coverage differs')

    def prefix(row, tick, header, level, dimensions):
        for field, phase, pi in (('rendered', 'present', 1), ('post', 'post_update', 2)):
            campaign.raw_state(row[field], level, dimensions)
            require(campaign.native_boundary(row[field], row['dac'][pi], header['atlas']) == expected[tick, phase]['mapped'],
                    'fresh mapped prefix differs')
        require(row['rgb_sha256'] == expected[tick, 'present']['rgb_sha256'], 'fresh prefix RGB differs')

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
            native[-1]['native_level3_entry_observed'] is True, 'incomplete native portal stream')
    for key, tick, palette, digest in (
        ('baseline', 3642, 'baseline_dac', 'ack_rgb_sha256'), ('intro', 3776, 'intro_dac', 'intro_rgb_sha256')):
        require(campaign.native_boundary(header[key], header[palette], reels[0]['atlas'] if key == 'baseline' else header['atlas']) ==
                expected[tick, 'present']['mapped'] and header[digest] == expected[tick, 'present']['rgb_sha256'],
                'fresh acknowledgment/intro prefix differs')
    journal = fidelity.strict_json((capture / 'objective-input-journal.json').read_text())
    require(journal['complete'] is True and len(journal['samples']) == NATIVE_FRAMES and
            journal['new_gameplay_state_injections'] is False, 'incomplete native portal input journal')
    rows, previous = [], bytes(192000)
    for index, row in enumerate(native[1:-1]):
        tick = 3777 + index
        require(row['sample'] == index and row['cpp_tick'] == tick and
                row['sequences'] == [header['intro_sequence'] + 1 + index * 3 + i for i in range(3)],
                'native portal frame/phase alignment differs')
        for field in ('pre', 'rendered', 'post'):
            campaign.raw_state(row[field], 3, (150, 60))
            require(row[field]['frame'] == 2670 + index, 'native portal frame skipped')
        require(len(row['dac']) == 3, 'missing native palettes')
        for value in row['dac']:
            handoff.dac(value)
        control = journal['samples'][index]
        wanted_events = events.get(tick - 1, []) if index >= 12 else []
        require(control['sample'] == index and control['cpp_tick'] == tick and control['events'] == wanted_events,
                'native portal control phase differs')
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
            rows.append({'kind': 'boundary', 'tick': tick, 'phase': phase, 'region': 'level3_portal',
                         'mapped': campaign.native_boundary(row[field], row['dac'][pi], header['atlas']),
                         'rgb_sha256': hashlib.sha256(previous).hexdigest() if phase == 'present' else None})
    metadata = {'kind': 'header', 'schema': SCHEMA, 'ticks': TICKS, 'first_tick': FIRST_TICK, 'frames': FRAMES,
                'native_frames': NATIVE_FRAMES, 'dimensions': [150, 60], 'route_sha256': ROUTE_SHA256,
                'native_stream_sha256': NATIVE_SHA256, 'prefix_reference_sha256': third.REFERENCE_SHA256,
                'capture_pins': CAPTURE_PINS, 'assets': outcome['assets'], 'audio': 'dummy', 'state_injections': False,
                'completed_levels': [1, 2], 'entered_level': 3, 'natural_level3_completion_claim': False,
                'pickup_ticks': list(PICKUP_TICKS), 'portal_tick': PORTAL_TICK, **campaign.CLAIMS}
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
    require(len(rows) == FRAMES * 2 + 2 and rows[0]['schema'] == SCHEMA and rows[0]['ticks'] == TICKS and
            rows[0]['first_tick'] == FIRST_TICK and rows[0]['frames'] == FRAMES and rows[0]['native_frames'] == NATIVE_FRAMES and
            rows[0]['dimensions'] == [150, 60] and rows[0]['route_sha256'] == ROUTE_SHA256 and
            rows[0]['native_stream_sha256'] == NATIVE_SHA256 and rows[0]['prefix_reference_sha256'] == third.REFERENCE_SHA256 and
            rows[0]['capture_pins'] == CAPTURE_PINS and rows[0]['state_injections'] is False and
            rows[0]['completed_levels'] == [1, 2] and rows[0]['entered_level'] == 3 and
            rows[0]['natural_level3_completion_claim'] is False and rows[0]['pickup_ticks'] == list(PICKUP_TICKS) and
            rows[0]['portal_tick'] == PORTAL_TICK and rows[0]['audio'] == 'dummy' and
            all(rows[0][key] is value for key, value in campaign.CLAIMS.items()) and
            rows[-1] == {'kind': 'complete', 'frames': FRAMES, 'boundaries': FRAMES * 2, 'patches_restored': True},
            'portal fixture contract differs')
    for index, row in enumerate(rows[1:-1]):
        tick, phase = FIRST_TICK + index // 2, ('present', 'post_update')[index % 2]
        require(set(row) == {'kind', 'tick', 'phase', 'region', 'mapped', 'rgb_sha256'} and
                row['kind'] == 'boundary' and row['region'] == 'level3_portal' and row['tick'] == tick and row['phase'] == phase and
                row['mapped']['level'] == 3 and row['mapped']['frame'] == tick - 1107 and
                (row['rgb_sha256'] is None) == (phase == 'post_update'), 'invalid portal boundary')
        if phase == 'post_update':
            require(row['mapped']['progress'][0] == 3 + sum(tick >= pickup for pickup in PICKUP_TICKS), 'native pickup moved')
    before = rows[(PORTAL_TICK - FIRST_TICK) * 2 + 1]['mapped']['players'][0]
    after = rows[(PORTAL_TICK - FIRST_TICK) * 2 + 2]['mapped']['players'][0]
    require(before['xy'] == [734, 376] and after['xy'] == [392, 120] and
            before['velocity'] == after['velocity'] == [0, 0] and before['fractions'] == after['fractions'] == [187, 219],
            'natural portal position/velocity/carry differs')
    last = rows[-2]['mapped']
    require(last['progress'] == [6, 57] and last['players'][0]['energy'] == 100 and last['players'][0]['reserve'] == 1 and
            last['players'][0]['inventory'] == [200, 14, 0, 0, 1] and last['players'][0]['xy'] == [392, 128] and
            last['score'] == 36220, 'portal endpoint differs')


def fixture(root=FIXTURE):
    require(fidelity.sha256(root / 'reference.jsonl.gz') == REFERENCE_SHA256 and
            fidelity.sha256(root / 'guard-input.json') == GUARD_INPUT_SHA256, 'portal fixture fingerprint differs')
    check_route(root / 'route.txt')
    rows = handoff.load(root / 'reference.jsonl.gz')
    validate(rows)
    require(rows[0]['assets'] == campaign.fixture()[0]['assets'], 'portal fixture assets differ')
    return rows


def compare(cpp):
    extension, prefix = fixture(), campaign.fixture()
    rows = [prefix[0], *prefix_rows(), *extension[1:-1], prefix[-1]]
    report = campaign.compare_rows(cpp, rows, FIXTURE / 'route.txt', TICKS)
    require(report['frames'] == 5201 and report['boundaries'] == 10326, 'full portal coverage differs')
    return {**report, 'new_level3_frames': FRAMES, 'new_level3_boundaries': FRAMES * 2,
            'pickup_ticks': list(PICKUP_TICKS), 'portal_tick': PORTAL_TICK, 'natural_level3_completion_claim': False}


def guard():
    rows, mutations = fixture(), 0
    edits = [lambda r: r.pop(1), lambda r: r.insert(1, copy.deepcopy(r[1])),
             lambda r: r.__setitem__(slice(1, 3), [r[2], r[1]]),
             lambda r: r[-1].__setitem__('patches_restored', False),
             lambda r: r[1].__setitem__('tick', FIRST_TICK - 1), lambda r: r[1].__setitem__('phase', 'pre_update'),
             lambda r: r[1].__setitem__('rgb_sha256', None),
             lambda r: r[-2]['mapped']['progress'].__setitem__(0, 7),
             lambda r: r[-2]['mapped'].__setitem__('score', 32470),
             lambda r: r[(PORTAL_TICK - FIRST_TICK) * 2 + 2]['mapped']['players'][0]['xy'].__setitem__(0, 734),
             lambda r: r[(PORTAL_TICK - FIRST_TICK) * 2 + 2]['mapped']['players'][0]['fractions'].__setitem__(0, 0)]
    for key, value in (('dimensions', [100, 53]), ('first_tick', FIRST_TICK - 1), ('ticks', TICKS - 1),
                       ('frames', FRAMES - 1), ('native_frames', NATIVE_FRAMES - 1), ('completed_levels', [1, 2, 3]),
                       ('state_injections', True), ('prefix_reference_sha256', '0' * 64),
                       ('native_stream_sha256', '0' * 64), ('route_sha256', '0' * 64), ('audio', 'speaker'),
                       ('all_actor_fields_compared', True), ('natural_level3_completion_claim', True),
                       ('pickup_ticks', [5933, 5935, 5938]), ('portal_tick', PORTAL_TICK + 1), ('capture_pins', {})):
        edits.append(lambda r, key=key, value=value: r[0].__setitem__(key, value))
    for edit in edits:
        changed = copy.deepcopy(rows)
        edit(changed)
        require(changed != rows, 'vacuous portal mutation')
        try:
            validate(changed)
        except fidelity.EvidenceError:
            mutations += 1
        else:
            raise fidelity.EvidenceError('portal semantic mutation accepted')
    with tempfile.TemporaryDirectory(prefix='lezac-portal-guard-') as temporary:
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
                raise fidelity.EvidenceError('portal fixture mutation accepted')
    typed = campaign.guard_projection(fidelity.strict_json((FIXTURE / 'guard-input.json').read_text()), rows[-2]['mapped'])
    producer_mutations = 0
    with tempfile.TemporaryDirectory(prefix='lezac-portal-producer-') as temporary:
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
                raise fidelity.EvidenceError('untrusted portal producer accepted')
            require(not (root / 'must-not-exist').exists(), 'untrusted producer wrote output')
            (root / name).write_bytes(raw)
    require(mutations == 30 and typed == 291 and producer_mutations == 12, 'portal guard coverage differs')
    print(original.json_bytes({'status': 'guarded', 'mutations_rejected': mutations,
                               'typed_field_mutations_rejected': typed, 'producer_mutations_rejected': producer_mutations}).decode(), flush=True)


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
        (cpp / 'natural-level3-portal-comparison.json').write_bytes(original.json_bytes(report))
        print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
