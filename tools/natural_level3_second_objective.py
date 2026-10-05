"""Original-backed second Level 3 pickup after ordinary Level 1/2 completion."""
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
import natural_level3_objective as objective

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level3_second_objective'
EVIDENCE = ROOT / 'docs/recovery/evidence/natural_level3_second_objective_20261005'
SCHEMA = 'lezac-natural-level3-second-objective-boundaries-v1'
TICKS, FIRST_TICK, FRAMES, NATIVE_FRAMES = 4758, 4439, 320, 982
PICKUP_TICK = 4674
ROUTE_SHA256 = 'e08ebee46583df5b40b48b0000831546ae2237c0a148a92b832d8b29f3819f33'
NATIVE_SHA256 = '54dad8dd40aaf54913568ea849c722faf9ba59d796f396603dea113cffd1c048'
REFERENCE_SHA256 = '59e2518414e6a5e22cfbd5c5e11dc107cace05cbe225757ed7ddee7071fe8f81'
GUARD_INPUT_SHA256 = '3441ed6b7c616702c52d21a4f1c7b74e10e765136a383c34452ed41d82c62358'
CAPTURE_PINS = {
    'objective-observer-wrapper.py': '67fbad0106d75c06652708f8ec9667d2b607665947b26d5811d05e6c1c5206f7',
    'ledge-capture-driver.py': 'a05109d598dea2cd393eedc2788d222cd0b041f3e9a3b1b5555e55977a80e281',
    'next-pickup-capture-driver.py': 'bb8854b0dab5e3ae41cdaa61dbe00644facb52b02600d633981a541ab8d73909',
    'level3-handoff-observer.py': '98a98127128d7aededb97f92468bcdac790a2eb59a4c425e39ea333de8b5b282',
    'outcome-observer.py': '33869f46e0afa16ef9d64d7a045ed6e9dfa3e2a4c7f54f3c88add4b1ebafe774',
    'extension-observer.py': 'acb311ed85fb594afc1d92d6774036a742388339b920bcc0f81206cabfb30dec',
    'observer.py': '0af5c0a1f0ef7f87c4898ecc512784db315d281547b97bf45e57bfa5c87b1985',
    'results-observer.py': '082e5c9f7f5c1fb34675aee8d4d7bb9a69bb78f382e79b98b860a723345fc093',
    'outcome-manifest.json': '6c8851e45801a4676cd2283bf11cb63b78989c3e0e8b1ccc6ca01cc0008fde70',
    'ledge-native-audit.json': '608f3017afa8d59a75f9cfb2a3f9b62658aabde2d98243c493e8a97ab9f13921',
    'next-pickup-native-audit.json': '36c8d96946eb8539dbcc5bdb0447f7149a1a84e5be890c95622a9a7e17a3fb9c',
    'next-pickup-runtime-configuration.json': 'a5dd844fb9edd3400579cba934ee2a6811d1d92aa7c61c30aabe3ec8c70e61bd',
    'objective-controller.json': '73a68fb5b21c636c2aa6cfa2996fda7c7136e5d2dd48ee1f679d5cdf553852f8',
    'objective-input-journal.json': '9b4ef552bffc6805128128bbdfafab212660efa03d11e365b239bcdc165d3e47',
}
require = fidelity.require


def check_producer(capture):
    for name, digest in CAPTURE_PINS.items():
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'untrusted second-pickup producer: ' + name)


def check_route(route):
    require(fidelity.sha256(route) == ROUTE_SHA256, 'second-pickup route fingerprint differs')
    settings, events = fidelity.read_route(route)
    prefix_settings, prefix = fidelity.read_route(objective.FIXTURE / 'route.txt')
    require(settings['ticks'] == TICKS and all(settings[key] == prefix_settings[key] for key in ('seed', 'step_us')) and
            {tick: items for tick, items in events.items() if tick < objective.TICKS} == prefix,
            'second pickup changed the immutable first-pickup route')
    require(all(item['key'] in ('m', 'z') and item['action'] in ('down', 'up')
                for tick, items in events.items() if tick >= objective.TICKS for item in items),
            'non-movement input in no-extra-bomb extension')
    return events


def pack(capture, out):
    require(not out.exists(), 'fresh second-pickup fixture output required')
    check_producer(capture)
    require(not (capture / 'failure.json').exists() and not (capture / 'objective-observer-failure.json').exists(),
            'failed native second-pickup capture')
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
    audit = fidelity.strict_json((capture / 'next-pickup-native-audit.json').read_text())
    config = fidelity.strict_json((capture / 'next-pickup-runtime-configuration.json').read_text())
    require(audit['status'] == 'captured_and_mapped_prefix_verified' and audit['level3_frames'] == NATIVE_FRAMES and
            audit['route_ticks'] == TICKS and audit['patches_restored'] is True and
            audit['new_gameplay_state_injections'] is config['new_gameplay_state_injections'] is False and
            config['runtime_frames'] == NATIVE_FRAMES and config['route_ticks'] == TICKS and
            config['unchanged_verified_level3_prefix_frames'] == 662 and config['audio'] == 'dummy' and
            config['variant_source_sha256'] == CAPTURE_PINS['next-pickup-capture-driver.py'] and
            config['auditor_sha256'] == CAPTURE_PINS['ledge-capture-driver.py'] and
            config['parent_sha256'] == CAPTURE_PINS['objective-observer-wrapper.py'],
            'native runtime variant configuration differs')
    events = check_route(capture / 'level3-route.txt')
    base, first = campaign.fixture(), objective.fixture()
    expected = {(row['tick'], row['phase']): row for row in (*base[1:-1], *first[1:-1])}

    def prefix_sample(row, tick, level, dimensions, header):
        for field, phase, pi in (('rendered', 'present', 1), ('post', 'post_update', 2)):
            campaign.raw_state(row[field], level, dimensions)
            require(campaign.native_boundary(row[field], row['dac'][pi], header['atlas']) == expected[tick, phase]['mapped'],
                    'fresh mapped prefix differs')
        require(row['rgb_sha256'] == expected[tick, 'present']['rgb_sha256'], 'fresh prefix RGB differs')

    entry = handoff.load(capture / 'handoff.jsonl.gz')
    handoff.validate(entry)
    for index, row in enumerate(entry[1:-1]):
        prefix_sample(row, 731 + index, 2, (100, 53), entry[0])
    gameplay = handoff.load(capture / 'gameplay.jsonl.gz')
    require(len(gameplay) == 2354 and gameplay[-1]['patches_restored'] is True and
            gameplay[-1]['gate_eligible'] is True, 'incomplete Level 2 gameplay prefix')
    previous = bytes(192000)
    for index, row in enumerate(gameplay[1:-1]):
        require(row['sample'] == index and row['cpp_tick'] == 743 + index and
                row['events'] == events.get(742 + index, []) and row['gate_eligible'] == (index == 2351),
                'Level 2 route/gate prefix differs')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        prefix_sample(row, 743 + index, 2, (100, 53), gameplay[0])
    baseline = gameplay[-2]['post']
    reels = handoff.load(capture / 'results.jsonl.gz')
    require(len(reels) == 36 and reels[-1]['samples'] == 34 and reels[-1]['gameplay_frozen'] is True,
            'incomplete Level 2 results prefix')
    previous = bytes(192000)
    for index, row in enumerate(reels[1:-1]):
        require(row['sample'] == index and row['player'] == 1 and
                all(row['state'][key] == baseline[key] for key in results.FROZEN), 'results advanced gameplay')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        require(campaign.native_boundary(row['state'], row['dac'], reels[0]['atlas']) == expected[index + 42, 'result']['mapped'] and
                row['rgb_sha256'] == expected[index + 42, 'result']['rgb_sha256'], 'fresh results state/pixels differ')
    native = handoff.load(capture / 'level3-handoff.jsonl.gz')
    header = native[0]
    require(len(native) == NATIVE_FRAMES + 2 and header['frames'] == native[-1]['frames'] == NATIVE_FRAMES and
            header['dimensions'] == [150, 60] and header['first_cpp_tick'] == 3777 and
            header['ack_sequence'] + 1 == header['intro_sequence'] and
            native[-1]['kind'] == 'complete' and native[-1]['native_level3_entry_observed'] is True,
            'incomplete native second-pickup stream')
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
        require(campaign.native_boundary(header[key], header[palette], reels[0]['atlas'] if key == 'baseline' else header['atlas']) ==
                expected[tick, 'present']['mapped'] and header[digest] == expected[tick, 'present']['rgb_sha256'],
                'fresh acknowledgment/intro prefix differs')
    journal = fidelity.strict_json((capture / 'objective-input-journal.json').read_text())
    require(journal['complete'] is True and len(journal['samples']) == NATIVE_FRAMES and
            journal['new_gameplay_state_injections'] is False, 'incomplete native input journal')
    rows, previous = [], bytes(192000)
    for index, row in enumerate(native[1:-1]):
        tick = 3777 + index
        require(row['sample'] == index and row['cpp_tick'] == tick and
                row['sequences'] == [header['intro_sequence'] + 1 + index * 3 + i for i in range(3)],
                'native frame/phase alignment differs')
        for field in ('pre', 'rendered', 'post'):
            campaign.raw_state(row[field], 3, (150, 60))
            require(row[field]['frame'] == 2670 + index, 'native gameplay frame skipped')
        require(len(row['dac']) == 3, 'missing native palettes')
        for value in row['dac']:
            handoff.dac(value)
        controls = journal['samples'][index]
        wanted_events = events.get(tick - 1, []) if index >= 12 else []
        require(controls['sample'] == index and controls['cpp_tick'] == tick and controls['events'] == wanted_events,
                'native control phase differs')
        before, after = bytes.fromhex(controls['before_bank_hex']), bytes.fromhex(controls['after_bank_hex'])
        require(len(before) == len(after) == 10, 'native input bank extent differs')
        wanted_bank = bytearray(before)
        for event in wanted_events:
            wanted_bank[original.BANK[event['key']] - 0x1b78] = event['action'] != 'up'
        require(bytes(wanted_bank) == after, 'undeclared native input-bank write')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        if tick < FIRST_TICK:
            prefix_sample(row, tick, 3, (150, 60), header)
            continue
        for field, phase, pi in (('rendered', 'present', 1), ('post', 'post_update', 2)):
            rows.append({'kind': 'boundary', 'tick': tick, 'phase': phase, 'region': 'level3_second_objective',
                         'mapped': campaign.native_boundary(row[field], row['dac'][pi], header['atlas']),
                         'rgb_sha256': hashlib.sha256(previous).hexdigest() if phase == 'present' else None})
    metadata = {'kind': 'header', 'schema': SCHEMA, 'ticks': TICKS, 'first_tick': FIRST_TICK, 'frames': FRAMES,
                'native_frames': NATIVE_FRAMES, 'dimensions': [150, 60], 'route_sha256': ROUTE_SHA256,
                'native_stream_sha256': NATIVE_SHA256, 'prefix_reference_sha256': objective.REFERENCE_SHA256,
                'capture_pins': CAPTURE_PINS, 'assets': outcome['assets'], 'audio': 'dummy', 'state_injections': False,
                'completed_levels': [1, 2], 'entered_level': 3, 'natural_level3_completion_claim': False,
                'second_pickup_tick': PICKUP_TICK, **campaign.CLAIMS}
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
    require(len(rows) == 642 and rows[0]['schema'] == SCHEMA and rows[0]['ticks'] == TICKS and
            rows[0]['first_tick'] == FIRST_TICK and rows[0]['frames'] == FRAMES and rows[0]['native_frames'] == NATIVE_FRAMES and
            rows[0]['dimensions'] == [150, 60] and rows[0]['route_sha256'] == ROUTE_SHA256 and
            rows[0]['native_stream_sha256'] == NATIVE_SHA256 and rows[0]['prefix_reference_sha256'] == objective.REFERENCE_SHA256 and
            rows[0]['capture_pins'] == CAPTURE_PINS and rows[0]['state_injections'] is False and
            rows[0]['completed_levels'] == [1, 2] and rows[0]['entered_level'] == 3 and
            rows[0]['natural_level3_completion_claim'] is False and rows[0]['second_pickup_tick'] == PICKUP_TICK and
            rows[0]['audio'] == 'dummy' and all(rows[0][key] is value for key, value in campaign.CLAIMS.items()) and
            rows[-1] == {'kind': 'complete', 'frames': FRAMES, 'boundaries': 640, 'patches_restored': True},
            'second-pickup fixture contract differs')
    keys, frames = set(), 0
    for row in rows[1:-1]:
        key = row['tick'], row['phase']
        require(set(row) == {'kind', 'tick', 'phase', 'region', 'mapped', 'rgb_sha256'} and
                row['kind'] == 'boundary' and row['region'] == 'level3_second_objective' and key not in keys and
                row['mapped']['level'] == 3 and row['mapped']['frame'] == row['tick'] - 1107 and
                (row['rgb_sha256'] is None) == (row['phase'] == 'post_update'), 'invalid second-pickup boundary')
        if row['phase'] == 'post_update':
            require(row['mapped']['progress'][0] == 1 + int(row['tick'] >= PICKUP_TICK), 'native second pickup moved')
        keys.add(key)
        frames += row['rgb_sha256'] is not None
    require(keys == {(tick, phase) for tick in range(FIRST_TICK, TICKS + 1) for phase in ('present', 'post_update')} and
            frames == FRAMES, 'incomplete second-pickup coverage')
    last = rows[-2]['mapped']
    require(last['progress'] == [2, 36] and last['players'][0]['energy'] == 62 and last['players'][0]['reserve'] == 1 and
            last['players'][0]['inventory'] == [200, 17, 0, 0, 1] and last['players'][0]['xy'] == [229, 256] and
            last['score'] == 19570, 'second-pickup endpoint differs')


def fixture(root=FIXTURE):
    require(fidelity.sha256(root / 'reference.jsonl.gz') == REFERENCE_SHA256 and
            fidelity.sha256(root / 'guard-input.json') == GUARD_INPUT_SHA256, 'second-pickup fixture fingerprint differs')
    check_route(root / 'route.txt')
    rows = handoff.load(root / 'reference.jsonl.gz')
    validate(rows)
    require(rows[0]['assets'] == campaign.fixture()[0]['assets'], 'second-pickup fixture assets differ')
    return rows


def compare(cpp):
    extension, first, prefix = fixture(), objective.fixture(), campaign.fixture()
    rows = [prefix[0], *prefix[1:-1], *first[1:-1], *extension[1:-1], prefix[-1]]
    report = campaign.compare_rows(cpp, rows, FIXTURE / 'route.txt', TICKS)
    require(report['frames'] == 3731 and report['boundaries'] == 7386, 'full second-pickup coverage differs')
    return {**report, 'new_level3_frames': FRAMES, 'new_level3_boundaries': 640, 'second_pickup_tick': PICKUP_TICK,
            'natural_level3_completion_claim': False}


def guard():
    rows, mutations = fixture(), 0
    edits = (lambda r: r.pop(1), lambda r: r.insert(1, copy.deepcopy(r[1])),
             lambda r: r[0].__setitem__('dimensions', [100, 53]), lambda r: r[0].__setitem__('first_tick', 4438),
             lambda r: r[0].__setitem__('completed_levels', [1, 2, 3]), lambda r: r[0].__setitem__('state_injections', True),
             lambda r: r[0].__setitem__('prefix_reference_sha256', '0' * 64),
             lambda r: r[0].__setitem__('native_stream_sha256', '0' * 64),
             lambda r: r[0].__setitem__('all_actor_fields_compared', True), lambda r: r[-1].__setitem__('patches_restored', False),
             lambda r: r[1].__setitem__('tick', FIRST_TICK - 1), lambda r: r[1].__setitem__('phase', 'pre_update'),
             lambda r: r[1].__setitem__('rgb_sha256', None), lambda r: r[-2]['mapped']['progress'].__setitem__(0, 3),
             lambda r: r[0].__setitem__('natural_level3_completion_claim', True),
             lambda r: r[0].__setitem__('second_pickup_tick', PICKUP_TICK + 1), lambda r: r[0].__setitem__('native_frames', 981))
    for edit in edits:
        changed = copy.deepcopy(rows)
        edit(changed)
        require(changed != rows, 'vacuous second-pickup mutation')
        try:
            validate(changed)
        except fidelity.EvidenceError:
            mutations += 1
        else:
            raise fidelity.EvidenceError('second-pickup semantic mutation accepted')
    with tempfile.TemporaryDirectory(prefix='lezac-second-pickup-guard-') as temporary:
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
                raise fidelity.EvidenceError('second-pickup fixture mutation accepted')
    typed = campaign.guard_projection(fidelity.strict_json((FIXTURE / 'guard-input.json').read_text()), rows[-2]['mapped'])
    producer_mutations = 0
    with tempfile.TemporaryDirectory(prefix='lezac-second-pickup-producer-') as temporary:
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
                raise fidelity.EvidenceError('untrusted second-pickup producer accepted')
            require(not (root / 'must-not-exist').exists(), 'untrusted producer wrote output')
            (root / name).write_bytes(raw)
    require(mutations == 20 and typed == 291 and producer_mutations == len(CAPTURE_PINS), 'second-pickup guard coverage differs')
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
        (cpp / 'natural-level3-second-objective-comparison.json').write_bytes(original.json_bytes(report))
        print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
