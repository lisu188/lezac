"""Original-backed one-player Level 1/2 completion and Level 3 entry replay."""
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

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_campaign'
SCHEMA = 'lezac-natural-campaign-boundaries-v1'
TICKS, GATE_TICK, FIRST_LEVEL3_TICK = 3788, 3094, 3777
REFERENCE_SHA256 = 'c4066a05bc486fb559afa61feff391a7617f6b3ae59743efd85856b4e0b4d2fd'
GUARD_INPUT_SHA256 = 'db79b0a4cdf66dc4150a1fc598f2f6797d1f4a778e2f3bf6bad0a4f0b06e705f'
ROUTE_SHA256 = '07bd49c6456b2ce77139002e230480a947219ad5b7592bea3d81296070efc3dd'
CAPTURE_PINS = {
    'outcome-manifest.json': '473083d49378a1f8924520f9dde742470ab50a8650d1cb4e21c7183942fa1e21',
    'level3-manifest.json': '9b0301beab5e0ee0821be27a6abdcd169e72165741340b5b6109772f72dd7881',
    'outcome-observer.py': '33869f46e0afa16ef9d64d7a045ed6e9dfa3e2a4c7f54f3c88add4b1ebafe774',
    'level3-handoff-observer.py': '98a98127128d7aededb97f92468bcdac790a2eb59a4c425e39ea333de8b5b282',
    'extension-observer.py': 'acb311ed85fb594afc1d92d6774036a742388339b920bcc0f81206cabfb30dec',
    'observer.py': '0af5c0a1f0ef7f87c4898ecc512784db315d281547b97bf45e57bfa5c87b1985',
    'results-observer.py': '082e5c9f7f5c1fb34675aee8d4d7bb9a69bb78f382e79b98b860a723345fc093',
}
COUNTS = {'level1_gameplay': [305, 610], 'level1_results': [42, 42],
          'level1_ack': [1, 2], 'level2_intro': [1, 2], 'level2_entry': [12, 24],
          'level2_gameplay': [2352, 4704], 'level2_results': [34, 34],
          'level2_ack': [1, 2], 'level3_intro': [1, 2], 'level3_entry': [12, 24]}
RANGES = {'level1_gameplay': (4, 308), 'level1_results': (0, 41),
          'level1_ack': (660, 660), 'level2_intro': (730, 730), 'level2_entry': (731, 742),
          'level2_gameplay': (743, 3094), 'level2_results': (42, 75),
          'level2_ack': (3642, 3642), 'level3_intro': (3776, 3776), 'level3_entry': (3777, 3788)}
CLAIMS = {'all_actor_fields_compared': False, 'all_dac_entries_compared': False,
          'manual_input_claim': False, 'wall_clock_claim': False,
          'original_fidelity_claim': False, 'port_functionally_complete': False}
require = fidelity.require


def compact(mapped):
    result = dict(mapped)
    for key in ('tiles_hex', 'words_hex'):
        result[key] = hashlib.sha256(bytes.fromhex(result[key])).hexdigest()
    return result


def native_boundary(state, dac, atlas):
    return compact(handoff.native_boundary(state, dac, atlas) if dac is not None else
                   original.project_original(state, 1, atlas))


def cpp_boundary(state, palette=True):
    return compact(handoff.boundary(state, bytes.fromhex(state['palette_rgb_hex'])) if palette else
                   original.project_cpp(state, 1))


def raw_state(state, level, dimensions):
    width, height = dimensions
    require(len(bytes.fromhex(state['tiles'])) == width * height and
            len(bytes.fromhex(state['words'])) == width * height * 2 and
            bytes.fromhex(state['globals'])[0x17] == level, 'native map/level extent differs')
    original.validate_raw({**state, 'tiles': state['tiles'][:3960], 'words': state['words'][:7920]})


def check_producer(capture):
    for name, digest in CAPTURE_PINS.items():
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'untrusted native source: ' + name)


def check_capture(capture):
    require(not (capture / 'failure.json').exists(), 'failed native capture')
    check_producer(capture)
    outcome = fidelity.strict_json((capture / 'outcome-manifest.json').read_text())
    next_level = fidelity.strict_json((capture / 'level3-manifest.json').read_text())
    require(outcome['status'] == next_level['status'] == 'captured' and
            outcome['patches_restored'] is next_level['patches_restored'] is True and
            outcome['gameplay_frames'] == 2352 and outcome['gate_cpp_tick'] == GATE_TICK and
            outcome['gate_native_frame'] == 2669 and outcome['result_samples'] == 34 and
            next_level['first_cpp_tick'] == FIRST_LEVEL3_TICK and next_level['frames'] == 12 and
            next_level['dimensions'] == [150, 60], 'native completion extent differs')
    for name, digest in outcome['files'].items():
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'native captured bytes changed: ' + name)
    require(outcome['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'native assets differ')
    require(fidelity.sha256(capture / 'level3-route.txt') == ROUTE_SHA256 and
            original.fingerprint(capture) == handoff.PREFIX_SHA256, 'natural prefix/input differs')
    settings, events = fidelity.read_route(capture / 'level3-route.txt')
    prefix_settings, prefix_events = fidelity.read_route(handoff.FIXTURE / 'route.txt')
    require(settings['ticks'] == TICKS and all(settings[k] == prefix_settings[k] for k in ('seed', 'step_us')) and
            {tick: items for tick, items in events.items() if tick < 742} == prefix_events,
            'natural handoff prefix was changed')
    require(events[3642] == [{'action': 'down', 'key': 'return'}] and
            events[3776] == [{'action': 'down', 'key': 'return'}], 'missing separate results/intro acknowledgment')
    return outcome, events


def guard_inputs(state, dac, atlas):
    native = handoff.native_boundary(state, dac, atlas)
    player = native['players'][0]
    return {'level': native['level'], 'logic_tick': native['frame'], 'random_seed': native['rng'],
            'tiles_hex': state['tiles'], 'words_hex': state['words'], 'progress': native['progress'],
            'hud': native['hud'], 'presentation': [0, 0, 0, 0, native['red_phase']],
            'palette_rgb_hex': bytes(v << 2 | v >> 4 for v in handoff.dac(dac)).hex(),
            'players': [{'x': player['xy'][0], 'y': player['xy'][1],
                         'vx8': player['velocity'][0], 'vy8': player['velocity'][1],
                         'frac_x': player['fractions'][0], 'frac_y': player['fractions'][1],
                         'animation': player['animation'], 'health': [player['energy'], player['reserve']],
                         'inventory': player['inventory'], 'hud_score': player['reel'], 'score': native['score']},
                        {'inventory': native['p2_inventory']}]}


def guard_projection(cpp, expected):
    require(cpp_boundary(cpp) == expected, 'positive typed projection baseline differs')
    paths = [(key,) for key in ('level', 'logic_tick', 'random_seed')]
    paths += [(key, index) for key in ('progress', 'hud') for index in range(len(cpp[key]))]
    paths.append(('presentation', 4))
    paths += [('players', 0, key) for key in ('x', 'y', 'vx8', 'vy8', 'frac_x', 'frac_y', 'score')]
    paths += [('players', 0, key, index) for key in ('animation', 'health', 'inventory', 'hud_score')
              for index in range(len(cpp['players'][0][key]))]
    paths += [('players', 1, 'inventory', index) for index in range(5)]
    for path in paths:
        changed = copy.deepcopy(cpp)
        target = changed
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] += 1
        require(cpp_boundary(changed) != expected, 'typed projection mutation accepted: ' + str(path))
    for key in ('tiles_hex', 'words_hex'):
        changed = copy.deepcopy(cpp)
        raw = bytearray.fromhex(changed[key])
        raw[-1] ^= 1
        changed[key] = raw.hex()
        require(cpp_boundary(changed) != expected, 'full map-plane mutation accepted')
    for index in handoff.PALETTE_INDICES:
        changed = copy.deepcopy(cpp)
        raw = bytearray.fromhex(changed['palette_rgb_hex'])
        raw[index * 3] ^= 1
        changed['palette_rgb_hex'] = raw.hex()
        require(cpp_boundary(changed) != expected, 'covered palette mutation accepted')
    changed = copy.deepcopy(cpp)
    raw = bytearray.fromhex(changed['palette_rgb_hex'])
    raw[176 * 3:215 * 3] = bytes(39 * 3)
    changed['palette_rgb_hex'] = raw.hex()
    require(cpp_boundary(changed) == expected, 'excluded DAC scope was expanded')
    return len(paths) + 2 + len(handoff.PALETTE_INDICES)


def pack(capture, out):
    require(not out.exists(), 'new fixture output required')
    outcome, events = check_capture(capture)
    rows, keys = [], set()

    def add(tick, phase, region, mapped, rgb=None):
        require((tick, phase) not in keys, 'overlapping native boundary')
        keys.add((tick, phase))
        rows.append({'kind': 'boundary', 'tick': tick, 'phase': phase, 'region': region,
                     'mapped': mapped, 'rgb_sha256': rgb})

    def sample(row, region, atlas, previous, palette=True):
        rgb = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        for field, phase, pi in (('rendered', 'present', 1), ('post', 'post_update', 2)):
            dac = row['dac'][pi] if palette else None
            add(row['cpp_tick'], phase, region, native_boundary(row[field], dac, atlas),
                hashlib.sha256(rgb).hexdigest() if phase == 'present' else None)
        return rgb

    atlas = None
    for row in original.reference_rows(capture):
        if row['kind'] == 'header':
            atlas = row['atlas']
        elif row['kind'] == 'sample':
            for field, phase in (('rendered', 'present'), ('post', 'post_update')):
                add(row['cpp_tick'], phase, 'level1_gameplay', native_boundary(row[field], None, atlas),
                    row['rgb_sha256'] if phase == 'present' else None)
    first_rows = handoff.load(capture / 'handoff.jsonl.gz')
    first_samples = handoff.validate(first_rows)
    first_header = first_rows[0]
    previous = bytes(192000)
    for index, row in enumerate(first_samples):
        previous = sample({**row, 'cpp_tick': handoff.FIRST_TICK + index},
                          'level2_entry', first_header['atlas'], previous)

    gameplay = handoff.load(capture / 'gameplay.jsonl.gz')
    require(len(gameplay) == 2354 and gameplay[0]['first_tick'] == 743 and
            gameplay[-1]['kind'] == 'complete' and gameplay[-1]['frames'] == 2352 and
            gameplay[-1]['patches_restored'] is True, 'incomplete native Level 2 gameplay')
    require(all(gameplay[0]['initial'][key] == first_samples[-1]['post'][key] for key in results.FROZEN) and
            original.project_original(gameplay[0]['initial'], 1, gameplay[0]['atlas']) ==
            original.project_original(first_samples[-1]['post'], 1, first_header['atlas']),
            'native gameplay extension changed the handoff state')
    previous, baseline = bytes(192000), None
    for index, row in enumerate(gameplay[1:-1]):
        require(row['kind'] == 'sample' and row['sample'] == index and row['cpp_tick'] == 743 + index and
                row['events'] == events.get(742 + index, []) and
                row['sequences'] == [first_samples[-1]['sequences'][-1] + 1 + index * 3 + i for i in range(3)],
                'native gameplay input/phase alignment differs')
        for field in ('pre', 'rendered', 'post'):
            raw_state(row[field], 2, (100, 53))
            require(row[field]['frame'] == 318 + index, 'native gameplay frame skipped')
        flags = bytes.fromhex(row['post']['globals'])[0x25:0x27]
        eligible = flags == b'\x01\x01' and original.word(bytes.fromhex(row['post']['progress']), 10) == 0
        require(row['gate_eligible'] == eligible == (index == 2351), 'native completion gate moved')
        previous = sample(row, 'level2_gameplay', gameplay[0]['atlas'], previous)
        baseline = row['post']
    gate = native_boundary(baseline, gameplay[-2]['dac'][2], gameplay[0]['atlas'])
    require(gate['progress'] == [3, 243] and gate['players'][0]['energy'] == 90 and
            gate['players'][0]['reserve'] == 1, 'ordinary completion or carried health differs')

    next_rows = handoff.load(capture / 'level3-handoff.jsonl.gz')
    require(len(next_rows) == 14 and next_rows[-1]['native_level3_entry_observed'] is True and
            next_rows[-1]['frames'] == 12, 'incomplete native Level 3 entry')
    next_header = next_rows[0]
    require(next_header['first_cpp_tick'] == FIRST_LEVEL3_TICK and next_header['dimensions'] == [150, 60] and
            next_header['ack_sequence'] + 1 == next_header['intro_sequence'], 'next intro boundary differs')
    for name in ('ack', 'intro_ack'):
        queue = next_header[name]
        before, after = bytes.fromhex(queue['before_bda_hex']), bytes.fromhex(queue['bda_hex'])
        head, tail = queue['head'], queue['tail']
        require(len(before) == len(after) == 64 and original.word(before, 0x1a) == original.word(before, 0x1c) and
                0x1e <= head < 0x3e and head % 2 == 0 and tail == (head + 2 if head < 0x3c else 0x1e) and
                original.word(after, 0x1a) == head and original.word(after, 0x1c) == tail and
                original.word(after, head) == queue['key_word'] == 0x1c0d, 'not a fresh single BIOS Return')
    previous = bytes(192000)
    for index, row in enumerate(next_rows[1:-1]):
        require(row['sample'] == index and row['cpp_tick'] == FIRST_LEVEL3_TICK + index and
                row['sequences'] == [next_header['intro_sequence'] + 1 + index * 3 + i for i in range(3)],
                'native Level 3 phase alignment differs')
        for field in ('pre', 'rendered', 'post'):
            raw_state(row[field], 3, (150, 60))
            require(row[field]['frame'] == 2670 + index, 'next native frame skipped')
        previous = sample(row, 'level3_entry', next_header['atlas'], previous)

    first_reel_header, first_reels = results.fixture()
    native_reels = handoff.load(capture / 'results.jsonl.gz')
    require(len(native_reels) == 36 and native_reels[-1]['samples'] == 34 and
            native_reels[-1]['gameplay_frozen'] is True and
            all(native_reels[0]['baseline'][key] == baseline[key] for key in results.FROZEN),
            'native result baseline or extent differs')
    previous, rng = bytes(192000), None
    for index, row in enumerate(native_reels[1:-1]):
        require(row['sample'] == index and row['player'] == 1 and
                all(row['state'][key] == baseline[key] for key in results.FROZEN), 'native results advanced gameplay')
        require(rng is None or row['state']['rng'] == (rng * 0x08088405 + 1) & 0xffffffff,
                'native result RNG cadence differs')
        require(int.from_bytes(bytes.fromhex(row['state']['scores'])[:4], 'little') == 17970 and
                bytes.fromhex(row['state']['scores'])[44] == (2 if index == 33 else 1), 'native result award/phase differs')
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
        add(42 + index, 'result', 'level2_results', native_boundary(row['state'], row['dac'], gameplay[0]['atlas']),
            hashlib.sha256(previous).hexdigest())
        rng = row['state']['rng']
    for index, row in enumerate(first_reels):
        add(index, 'result', 'level1_results', native_boundary(row['state'], None, first_reel_header['atlas']),
            hashlib.sha256(row['rgb']).hexdigest())

    boundaries = ((660, 'level1_ack', first_header['baseline'], first_header['baseline_dac'], atlas,
                   first_reels[-1]['rgb']),
                  (730, 'level2_intro', first_header['intro'], first_header['intro_dac'], first_header['atlas'],
                   fidelity.read_ppm(capture / 'level2-intro-wait.ppm')),
                  (3642, 'level2_ack', next_header['baseline'], next_header['baseline_dac'], gameplay[0]['atlas'],
                   None),
                  (3776, 'level3_intro', next_header['intro'], next_header['intro_dac'], next_header['atlas'],
                   None))
    for tick, region, state, dac, boundary_atlas, rgb in boundaries:
        digest = hashlib.sha256(rgb).hexdigest() if rgb is not None else next_header[
            'ack_rgb_sha256' if region == 'level2_ack' else 'intro_rgb_sha256']
        for phase in ('present', 'post_update'):
            add(tick, phase, region, native_boundary(state, dac, boundary_atlas), digest if phase == 'present' else None)
    rows.sort(key=lambda row: (row['phase'] == 'result', row['tick'], row['phase']))
    header = {'kind': 'header', 'schema': SCHEMA, 'ticks': TICKS, 'counts': COUNTS,
              'route_sha256': ROUTE_SHA256, 'assets': outcome['assets'], 'capture_pins': CAPTURE_PINS,
              'native_gameplay_sha256': outcome['files']['gameplay.jsonl.gz'],
              'native_results_sha256': outcome['files']['results.jsonl.gz'],
              'prefix_canonical_sha256': handoff.PREFIX_SHA256, 'audio': 'dummy',
              'state_injections': False, 'seed_scope': 'single unchanged Level 1 prefix seed',
              'gate_tick': GATE_TICK, 'completed_levels': [1, 2], 'entered_level': 3, **CLAIMS}
    footer = {'kind': 'complete', 'boundaries': 5446, 'frames': 2761, 'patches_restored': True}
    validate([header, *rows, footer])
    out.mkdir(parents=True)
    with original.compressed_writer(out / 'reference.jsonl.gz') as emit:
        for row in (header, *rows, footer):
            emit(row)
    (out / 'route.txt').write_bytes((capture / 'level3-route.txt').read_bytes())
    (out / 'guard-input.json').write_bytes(original.json_bytes(
        guard_inputs(first_samples[0]['rendered'], first_samples[0]['dac'][1], first_header['atlas'])))
    print(original.json_bytes({'status': 'packed', 'sha256': fidelity.sha256(out / 'reference.jsonl.gz'),
                               'guard_input_sha256': fidelity.sha256(out / 'guard-input.json'),
                               'bytes': (out / 'reference.jsonl.gz').stat().st_size}).decode(), flush=True)


def validate(rows):
    require(len(rows) == 5448 and rows[0]['schema'] == SCHEMA and rows[0]['counts'] == COUNTS and
            rows[0]['ticks'] == TICKS and rows[0]['route_sha256'] == ROUTE_SHA256 and
            rows[0]['capture_pins'] == CAPTURE_PINS and rows[0]['completed_levels'] == [1, 2] and
            rows[0]['state_injections'] is False and rows[0]['entered_level'] == 3 and rows[0]['audio'] == 'dummy' and
            all(rows[0][key] is value for key, value in CLAIMS.items()) and
            rows[-1] == {'kind': 'complete', 'boundaries': 5446, 'frames': 2761, 'patches_restored': True},
            'natural campaign fixture contract differs')
    counts, keys = {region: [0, 0] for region in COUNTS}, set()
    region_keys = {region: set() for region in COUNTS}
    for row in rows[1:-1]:
        require(set(row) == {'kind', 'tick', 'phase', 'region', 'mapped', 'rgb_sha256'} and row['kind'] == 'boundary' and
                row['region'] in counts and row['phase'] in ('present', 'post_update', 'result') and
                (row['tick'], row['phase']) not in keys, 'invalid or duplicate campaign boundary')
        keys.add((row['tick'], row['phase']))
        region_keys[row['region']].add((row['tick'], row['phase']))
        counts[row['region']][1] += 1
        counts[row['region']][0] += row['rgb_sha256'] is not None
        require((row['rgb_sha256'] is None) == (row['phase'] == 'post_update'), 'missing/unexpected frame hash')
    require(counts == COUNTS, 'incomplete campaign region coverage')
    for region, (first, last) in RANGES.items():
        phases = ('result',) if region.endswith('results') else ('present', 'post_update')
        require(region_keys[region] == {(tick, phase) for tick in range(first, last + 1) for phase in phases},
                'campaign region alignment differs: ' + region)
    gate = next(row for row in rows[1:-1] if row['tick'] == GATE_TICK and row['phase'] == 'post_update')
    entry = next(row for row in rows[1:-1] if row['tick'] == TICKS and row['phase'] == 'post_update')
    require(gate['mapped']['progress'] == [3, 243] and entry['mapped']['level'] == 3 and
            entry['mapped']['progress'] == [0, 0] and
            all(row['mapped']['players'][0]['energy'] == 90 and row['mapped']['players'][0]['reserve'] == 1
                for row in (gate, entry)), 'completion/entry health contract differs')


def fixture(root=FIXTURE):
    require(fidelity.sha256(root / 'reference.jsonl.gz') == REFERENCE_SHA256 and
            fidelity.sha256(root / 'route.txt') == ROUTE_SHA256, 'natural campaign fingerprint differs')
    rows = handoff.load(root / 'reference.jsonl.gz')
    validate(rows)
    require(rows[0]['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'fixture assets differ')
    return rows


def compare_rows(cpp, rows, route, ticks, *, check_extra=None):
    expected = {(row['tick'], row['phase']): row for row in rows[1:-1]}
    require(len(expected) == len(rows) - 2, 'duplicate expected campaign boundary')
    expected_frames = sum(row['rgb_sha256'] is not None for row in rows[1:-1])
    manifest = fidelity.load_manifest(cpp)
    require((cpp / 'route.txt').read_bytes() == route.read_bytes() and
            manifest['asset_sha256'] == rows[0]['assets'], 'replay input/assets differ')
    seen, frames = set(), 0

    def check(row, tick, phase, path):
        nonlocal frames
        key = tick, phase
        if key not in expected:
            return
        require(key not in seen, 'duplicate replay boundary')
        wanted = expected[key]
        mapped = cpp_boundary(row['state'], 'palette' in wanted['mapped'])
        diff = fidelity.first_difference(wanted['mapped'], mapped)
        require(diff is None, f"campaign {wanted['region']} {key} differs: {diff}")
        if wanted['rgb_sha256'] is not None:
            require(hashlib.sha256(fidelity.read_ppm(path)).hexdigest() == wanted['rgb_sha256'],
                    f"campaign {wanted['region']} {key} displayed pixels differ")
            frames += 1
        if key == (GATE_TICK, 'post_update'):
            require(not row['state']['collapse'], 'C++ completed while collapse remained')
        if check_extra is not None:
            check_extra(row, wanted)
        seen.add(key)

    footer = None
    for row in fidelity.trace_rows(cpp, manifest):
        footer = row
        if row['kind'] == 'header':
            require(row['input_model'] == 'sdl-events-original-intro-wait-v1', 'wrong input boundary model')
        elif row['kind'] == 'checkpoint':
            check(row, row['tick'], row['phase'], cpp / row.get('frame', 'unused'))
    require(footer['kind'] == 'complete' and footer['ticks'] == ticks, 'incomplete full route')
    reels = [fidelity.strict_json(line) for line in (cpp / 'result_reels.jsonl').read_text().splitlines()]
    require(len(reels) == 78 and reels[-1] == {'kind': 'complete', 'samples': 76, 'original_fidelity_claim': False},
            'incomplete result stream')
    require({path.name for path in cpp.glob('result_frame_*.ppm')} == {row['frame'] for row in reels[1:-1]},
            'result image inventory differs')
    for index, row in enumerate(reels[1:-1]):
        require(row['sample'] == index and row['player'] == 1 and row['frame'] == f'result_frame_{index:06d}.ppm',
                'result sample alignment differs')
        fidelity.validate_state(row['state'])
        check(row, index, 'result', fidelity.safe_file(cpp, row['frame']))
    require(seen == set(expected) and frames == expected_frames, 'missing native campaign boundaries')
    return {'status': 'match', 'frames': frames, 'boundaries': len(seen), 'pixels': frames * 64000,
            'completed_levels': [1, 2], 'entered_level': 3, **CLAIMS}


def compare(cpp, root=FIXTURE):
    return compare_rows(cpp, fixture(root), root / 'route.txt', TICKS)


def guard():
    rows = fixture()
    mutations = 0
    for edit in (lambda r: r.pop(1), lambda r: r.insert(1, copy.deepcopy(r[1])),
                 lambda r: r[0].__setitem__('completed_levels', [1, 2, 3]),
                 lambda r: r[0].__setitem__('state_injections', True),
                 lambda r: r[-1].__setitem__('patches_restored', False),
                 lambda r: next(row for row in r[1:-1] if row['rgb_sha256'] is not None).__setitem__('rgb_sha256', None),
                 lambda r: r[1].__setitem__('tick', 1)):
        changed = copy.deepcopy(rows)
        edit(changed)
        require(changed != rows, 'campaign guard mutation did not change the input')
        try:
            validate(changed)
        except fidelity.EvidenceError:
            mutations += 1
        else:
            raise fidelity.EvidenceError('campaign semantic mutation accepted')
    with tempfile.TemporaryDirectory(prefix='lezac-campaign-guard-') as temporary:
        root = Path(temporary)
        reference, route = (FIXTURE / 'reference.jsonl.gz').read_bytes(), (FIXTURE / 'route.txt').read_bytes()
        (root / 'route.txt').write_bytes(route)
        for bad in (reference[:-1], reference + b'\0', bytes([reference[0] ^ 1]) + reference[1:]):
            (root / 'reference.jsonl.gz').write_bytes(bad)
            try:
                fixture(root)
            except fidelity.EvidenceError:
                mutations += 1
            else:
                raise fidelity.EvidenceError('campaign fixture mutation accepted')
    require(fidelity.sha256(FIXTURE / 'guard-input.json') == GUARD_INPUT_SHA256, 'typed projection guard input changed')
    cpp = fidelity.strict_json((FIXTURE / 'guard-input.json').read_text())
    expected = next(row['mapped'] for row in rows[1:-1] if row['tick'] == 731 and row['phase'] == 'present')
    require(cpp_boundary(cpp) == expected, 'positive typed projection baseline differs')
    typed_mutations = guard_projection(cpp, expected)
    producer_mutations = 0
    evidence = ROOT / 'docs/recovery/evidence/natural_campaign_20261005'
    with tempfile.TemporaryDirectory(prefix='lezac-campaign-producer-') as temporary:
        root = Path(temporary)
        for name in CAPTURE_PINS:
            path = evidence / (name + '.gz')
            (root / name).write_bytes(gzip.decompress(path.read_bytes()))
        check_producer(root)
        for name in CAPTURE_PINS:
            original_bytes = (root / name).read_bytes()
            (root / name).write_bytes(original_bytes + b' ')
            try:
                pack(root, root / 'must-not-exist')
            except fidelity.EvidenceError:
                producer_mutations += 1
            else:
                raise fidelity.EvidenceError('untrusted producer was accepted')
            require(not (root / 'must-not-exist').exists(), 'untrusted producer generated output')
            (root / name).write_bytes(original_bytes)
    require(producer_mutations == len(CAPTURE_PINS), 'producer mutation guard incomplete')
    print(original.json_bytes({'status': 'guarded', 'mutations_rejected': mutations,
                               'typed_field_mutations_rejected': typed_mutations,
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
        require(args.capture is not None and args.out is not None, 'capture and output required')
        pack(args.capture.resolve(), args.out.resolve())
    elif args.command == 'guard':
        guard()
    else:
        if args.command == 'replay':
            require(args.exe is not None and args.out is not None, 'executable and output required')
            args.out.mkdir(parents=True, exist_ok=True)
            cpp = args.out.resolve() / ('run-' + uuid.uuid4().hex)
            fidelity.record(args.exe, ROOT, FIXTURE / 'route.txt', cpp, original_intro_wait=True, result_reels=True)
        else:
            require(args.cpp is not None, 'replay required')
            cpp = args.cpp.resolve()
        report = compare(cpp)
        (cpp / 'natural-campaign-comparison.json').write_bytes(original.json_bytes(report))
        print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
