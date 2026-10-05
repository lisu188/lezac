"""Bounded natural Level 2 route evidence; not a campaign completion check."""
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
from original_debris_table import decode_live_debris

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level2'
FRAMES, FIRST_TICK = 500, 743
REFERENCE_SHA256 = 'c8bc377adb3dc8942273566874b9b6cbacd5b75b7c076c142dacdee54c0b8bf3'
ROUTE_SHA256 = '53b82b21f7357d0eb5a46d457e1de30687b7572e12328659e2295a3404220d1e'
SCHEMA = 'lezac-natural-level2-tables-v1'
PRODUCER = ROOT / 'docs/recovery/evidence/natural_level2_20261005'
PRODUCER_SHA256 = '788ad44a1a4592a3c0bb79fde0f4a6c20399b97e85bf3785c66b73b7640d51cd'
BASE_OBSERVER = ROOT / 'docs/recovery/evidence/pickup_landing_2026-10-01/base-observer.py'
BASE_SHA256 = 'acb311ed85fb594afc1d92d6774036a742388339b920bcc0f81206cabfb30dec'
require = fidelity.require


def compact_boundary(value):
    result = dict(value)
    for key in ('tiles_hex', 'words_hex'):
        result[key] = hashlib.sha256(bytes.fromhex(result[key])).hexdigest()
    return result


def native_tables(segment):
    last_live, debris = decode_live_debris(segment)
    count = original.word(segment, 0x2080)
    require(count <= 250, 'invalid live collapse bound')
    # Preserve every field in the original 15-byte order, excluding inactive tails.
    collapse = [list(struct.unpack_from('<HHHBBbbHBBB', segment, 0x6620 + i * 15))
                for i in range(count)]
    monsters = []
    require(segment[0x208D] <= 30 and segment[0xC496] <= 32, 'invalid live actor/visual bound')
    for index in range(segment[0x208D]):
        actor = segment[0x1BD4 + index * 38:0x1BFA + index * 38]
        if not 1 <= actor[0] <= 8:
            continue
        require(actor[21] in (3, 4) and 0 < actor[37] <= 2 and actor[1] < segment[0xC496],
                'monster escaped the bounded Level 2 route')
        x, y = struct.unpack_from('<hh', segment, 0xC21E + actor[1] * 8)
        monsters.append({'identity': [actor[0], actor[21], actor[37] - 1, 1],
                         'position': [x, y - actor[20], actor[20]],
                         'motion': list(struct.unpack_from('<hhHH', actor, 6)),
                         'ai': list(struct.unpack_from('<HHH', actor, 14)),
                         'animation': [actor[22] - 1, actor[23] - 1, actor[24] - 1,
                                       actor[25], actor[26], actor[27], struct.unpack_from('b', actor, 28)[0]],
                         'hp': actor[36] + 1})
    return {'last_live_debris': last_live,
            'debris': [list(struct.unpack('<HHbbbbBBB', bytes.fromhex(raw))) for _, raw in debris],
            'collapse': collapse, 'monsters': monsters}


def cpp_tables(state):
    monsters = sorted(state['monsters'], key=lambda monster: monster['order'])
    require(all(m['identity'][1] in (3, 4) and m['health'][1] == 1 for m in monsters),
            'C++ monster escaped the bounded Level 2 route')
    return {'last_live_debris': 199 + len(state['debris']), 'debris': state['debris'],
            'collapse': [[c[i] for i in (2, 3, 5, 6, 7, 8, 9, 12, 10, 11, 13)] for c in state['collapse']],
            'monsters': [{'identity': m['identity'], 'position': m['position'], 'motion': m['motion'],
                          'ai': m['ai'][:3], 'animation': [m['animation'][i] for i in (0, 2, 3, 7, 4, 5, 6)],
                          'hp': m['health'][0]} for m in monsters]}


def validate_segment(segment, state):
    require(len(segment) == 65536, 'truncated data segment')
    require(original.word(segment, 0xC204) == 100 and
            original.word(segment, 0x2096) // 8 + 21 == 53 and segment[0x79B7] == 2,
            'DS level or dimensions differ')
    require(original.word(segment, 0x78C2) == state['frame'] and
            struct.unpack_from('<I', segment, 0x1AFE)[0] == state['rng'], 'DS boundary frame/RNG differs')
    for key, offset, length in (('actors', 0x1BD4, segment[0x208D] * 38),
                                ('visuals', 0xC21E, segment[0xC496] * 8),
                                ('inventory', 0x1B6C, 12), ('scores', 0x785A, 92),
                                ('destruction', 0x78C6, 4), ('progress', 0x2076, 36),
                                ('spawners', 0x74C6, segment[0x79A6] * 30)):
        require(segment[offset:offset + length].hex() == state[key], 'DS retained state differs: ' + key)
    require(segment[0x208D] == state['actor_count'], 'DS actor count differs')
    for i, player in enumerate(state['players'], 1):
        offset = 0x1B62 + i * 38
        require(segment[offset:offset + 38].hex() == player['raw'], 'DS player record differs')
        visual = 0xC21E + segment[offset + 1] * 8
        require(segment[visual:visual + 8].hex() == player['visual'], 'DS player visual differs')


def check_producer(capture):
    require(fidelity.sha256(PRODUCER / 'route-explorer.py') == PRODUCER_SHA256 and
            fidelity.sha256(BASE_OBSERVER) == BASE_SHA256, 'trusted retained producer changed')
    for name, digest in (('route-explorer.py', PRODUCER_SHA256), ('base-observer.py', BASE_SHA256),
                         ('extension-observer.py', BASE_SHA256)):
        require(fidelity.sha256(fidelity.safe_file(capture, name)) == digest, 'untrusted native producer: ' + name)
    require((capture / 'route-config.json').read_bytes() == (PRODUCER / 'route-config.json').read_bytes() and
            (capture / 'route-provenance.json').read_bytes() == (PRODUCER / 'route-provenance.json').read_bytes(),
            'native producer configuration or provenance changed')


def pack(capture, cpp, out):
    require(not out.exists() and not (capture / 'failure.json').exists(), 'new output and complete native capture required')
    check_producer(capture)
    handoff.check_sources()
    native_manifest = fidelity.strict_json((capture / 'extension-manifest.json').read_text())
    require(native_manifest['status'] == 'captured' and native_manifest['frames'] == FRAMES and
            native_manifest['observer_sha256'] == BASE_SHA256 and
            native_manifest['extension_sha256'] == fidelity.sha256(capture / 'extension.jsonl.gz') and
            original.fingerprint(capture) == handoff.PREFIX_SHA256, 'native extension provenance differs')
    require(native_manifest['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS},
            'native assets differ')
    handoff.validate(handoff.load(capture / 'handoff.jsonl.gz'))
    cpp_manifest = fidelity.load_manifest(cpp)
    route = (cpp / 'route.txt').read_bytes()
    require(route == (capture / 'extension-route.txt').read_bytes(), 'different routes')
    require(cpp_manifest['asset_sha256'] == native_manifest['assets'], 'C++ assets differ')
    ds_manifest = fidelity.strict_json((capture / 'extension-ds.json').read_text())
    require(ds_manifest['snapshots'] == 1 + 3 * FRAMES and ds_manifest['frames_requested'] == FRAMES and
            ds_manifest['boundaries'] == 'initial post, then pre/rendered/post for each extension frame' and
            ds_manifest['ds_stream_sha256'] == fidelity.sha256(capture / 'extension-ds.bin.gz'), 'DS inventory differs')
    with gzip.open(capture / 'extension-ds.bin.gz', 'rb') as stream:
        segments = stream.read((1 + 3 * FRAMES) * 65536 + 1)
    require(len(segments) == (1 + 3 * FRAMES) * 65536, 'DS snapshot extent differs')
    rows = handoff.load(capture / 'extension.jsonl.gz')
    require(len(rows) == FRAMES + 2 and rows[-1]['patches_restored'] is True and
            rows[-1]['frames'] == FRAMES, 'native extension incomplete')
    validate_segment(segments[:65536], rows[0]['initial'])
    settings, events = fidelity.read_route(cpp / 'route.txt')
    require(settings['ticks'] == FIRST_TICK - 1 + FRAMES, 'route length differs')
    _, prefix_events = fidelity.read_route(handoff.FIXTURE / 'route.txt')
    require({tick: items for tick, items in events.items() if tick < FIRST_TICK - 1} == prefix_events,
            'natural prefix inputs changed')
    output = [{'kind': 'header', 'schema': SCHEMA, 'frames': FRAMES, 'first_tick': FIRST_TICK,
               'route_sha256': hashlib.sha256(route).hexdigest(), 'assets': native_manifest['assets'],
               'native_extension_sha256': native_manifest['extension_sha256'],
               'ds_stream_sha256': ds_manifest['ds_stream_sha256'],
               'prefix_canonical_sha256': handoff.PREFIX_SHA256,
               'producer_sha256': fidelity.sha256(capture / 'route-explorer.py'),
               'state_injections': False, 'audio': 'dummy', 'level_completed': False,
               'all_actor_fields_compared': False, 'original_fidelity_claim': False}]
    previous = bytes(192000)
    for index, row in enumerate(rows[1:-1]):
        tick = FIRST_TICK + index
        require(row['sample'] == index and row['cpp_tick'] == tick and
                row['events'] == events.get(tick - 1, []), 'native input alignment differs')
        require(row['sequences'] == [955 + index * 3 + i for i in range(3)], 'native boundary sequence differs')
        for phase_index, phase in enumerate(('pre', 'rendered', 'post')):
            segment = segments[(1 + index * 3 + phase_index) * 65536:(2 + index * 3 + phase_index) * 65536]
            state = row[phase]
            require(state['frame'] == 318 + index, 'native frame alignment differs')
            original.validate_raw({**state, 'tiles': state['tiles'][:3960], 'words': state['words'][:7920]})
            original.hex_bytes(state['tiles'], 5300)
            original.hex_bytes(state['words'], 10600)
            validate_segment(segment, state)
            tables = native_tables(segment)
            if phase != 'pre':
                output.append({'kind': 'boundary', 'sample': index, 'tick': tick,
                               'phase': 'present' if phase == 'rendered' else 'post_update',
                               'mapped': compact_boundary(handoff.native_boundary(state, row['dac'][phase_index], rows[0]['atlas'])),
                               'tables': tables, 'rgb_sha256': row['rgb_sha256'] if phase == 'rendered' else None})
        previous = original.decode_frame(row['rgb_delta_zlib_hex'], previous, row['rgb_sha256'])
    output.append({'kind': 'complete', 'boundaries': 2 * FRAMES, 'patches_restored': True})
    out.mkdir(parents=True)
    with original.compressed_writer(out / 'reference.jsonl.gz') as emit:
        for row in output:
            emit(row)
    (out / 'route.txt').write_bytes(route)
    print(original.json_bytes({'status': 'packed', 'bytes': (out / 'reference.jsonl.gz').stat().st_size,
                               'sha256': fidelity.sha256(out / 'reference.jsonl.gz'),
                               'route_sha256': fidelity.sha256(out / 'route.txt')}).decode(), flush=True)


def fixture(root=FIXTURE):
    require(fidelity.sha256(root / 'reference.jsonl.gz') == REFERENCE_SHA256 and
            fidelity.sha256(root / 'route.txt') == ROUTE_SHA256, 'natural Level 2 fixture fingerprint differs')
    rows = handoff.load(root / 'reference.jsonl.gz')
    require(len(rows) == 2 * FRAMES + 2 and rows[0]['schema'] == SCHEMA and
            rows[0]['frames'] == FRAMES and rows[0]['route_sha256'] == ROUTE_SHA256 and
            rows[-1] == {'kind': 'complete', 'boundaries': FRAMES * 2, 'patches_restored': True},
            'natural Level 2 fixture extent differs')
    require(rows[0]['assets'] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'fixture assets differ')
    return rows


def compare(cpp, root=FIXTURE):
    rows = fixture(root)
    manifest = fidelity.load_manifest(cpp)
    require((cpp / 'route.txt').read_bytes() == (root / 'route.txt').read_bytes(), 'different replay input')
    require(manifest['asset_sha256'] == rows[0]['assets'], 'different replay assets')
    checkpoints = {(row['tick'], row['phase']): row for row in fidelity.trace_rows(cpp, manifest)
                   if row['kind'] == 'checkpoint' and row['tick'] >= FIRST_TICK and
                   row['phase'] in ('present', 'post_update')}
    require(len(checkpoints) == 2 * FRAMES, 'missing or extra natural Level 2 boundaries')
    totals = {'debris_records': 0, 'collapse_records': 0, 'monster_states': 0}
    for index, expected in enumerate(rows[1:-1]):
        require(expected['tick'] == FIRST_TICK + index // 2 and
                expected['phase'] == ('present' if index % 2 == 0 else 'post_update'), 'fixture ordering differs')
        row = checkpoints[expected['tick'], expected['phase']]
        state = row['state']
        actual = {**expected, 'mapped': compact_boundary(handoff.boundary(state, bytes.fromhex(state['palette_rgb_hex']))),
                  'tables': cpp_tables(state),
                  'rgb_sha256': hashlib.sha256(fidelity.read_ppm(cpp / row['frame'])).hexdigest()
                  if expected['phase'] == 'present' else None}
        diff = fidelity.first_difference(expected, actual)
        require(diff is None, f"natural Level 2 differs at sample {expected['sample']} {expected['phase']}: {diff}")
        for key, table in (('debris_records', 'debris'), ('collapse_records', 'collapse'), ('monster_states', 'monsters')):
            totals[key] += len(expected['tables'][table])
    return {'status': 'match', 'frames': FRAMES, 'boundaries': 2 * FRAMES, 'pixels': 64000 * FRAMES,
            **totals, 'level_completed': False, 'all_actor_fields_compared': False, 'original_fidelity_claim': False}


def guard():
    rows = fixture()
    segment = bytearray(65536)
    struct.pack_into('<H', segment, 0x207E, 200)
    struct.pack_into('<HHbbbbBBB', segment, 0x2093 + 200 * 11, 4326, 0xc001, -2, 40, -59, 14, 76, 104, 0)
    segment[0x2093 + 201 * 11:0x2093 + 202 * 11] = bytes([255]) * 11
    tables = native_tables(segment)
    require(tables['debris'] == [[4326, 0xc001, -2, 40, -59, 14, 76, 104, 0]], 'live signed record or stale tail differs')
    rejected = 0
    for bound in (198, 1601):
        struct.pack_into('<H', segment, 0x207E, bound)
        try:
            native_tables(segment)
        except ValueError:
            rejected += 1
    require(rejected == 2, 'invalid debris bound accepted')
    selected = next(row for row in rows[1:-1] if all(row['tables'][key] for key in ('debris', 'collapse', 'monsters')))
    cpp = {'debris': copy.deepcopy(selected['tables']['debris']), 'collapse': [], 'monsters': []}
    for record in selected['tables']['collapse']:
        reconstructed = [0] * 15
        for index, value in zip((2, 3, 5, 6, 7, 8, 9, 12, 10, 11, 13), record):
            reconstructed[index] = value
        cpp['collapse'].append(reconstructed)
    for index, monster in enumerate(selected['tables']['monsters']):
        animation = [0] * 8
        for field, value in zip((0, 2, 3, 7, 4, 5, 6), monster['animation']):
            animation[field] = value
        cpp['monsters'].append({**monster, 'animation': animation, 'ai': monster['ai'] + [0],
                                'health': [monster['hp'], 1], 'order': index})
    require(cpp_tables(cpp) == selected['tables'], 'typed C++ table projection differs')
    mutations = 0
    for table, count in (('debris', 9), ('collapse', 11)):
        for field in range(count):
            changed = copy.deepcopy(cpp)
            target = field if table == 'debris' else (2, 3, 5, 6, 7, 8, 9, 12, 10, 11, 13)[field]
            changed[table][0][target] ^= 1
            require(fidelity.first_difference(selected['tables'], cpp_tables(changed)) is not None,
                    'C++ table mutation was not detected')
            mutations += 1
    for field in ('identity', 'position', 'motion', 'ai', 'animation'):
        for index in range(len(selected['tables']['monsters'][0][field])):
            changed = copy.deepcopy(cpp)
            target = (0, 2, 3, 7, 4, 5, 6)[index] if field == 'animation' else index
            changed['monsters'][0][field][target] ^= 1
            try:
                diff = fidelity.first_difference(selected['tables'], cpp_tables(changed))
            except fidelity.EvidenceError:
                diff = {'invalid_monster': True}
            require(diff is not None, 'C++ monster mutation was not detected')
            mutations += 1
    changed = copy.deepcopy(cpp)
    changed['monsters'][0]['health'][0] ^= 1
    require(fidelity.first_difference(selected['tables'], cpp_tables(changed)) is not None,
            'C++ HP mutation was not detected')
    raw = (FIXTURE / 'reference.jsonl.gz').read_bytes()
    bad = [('truncated', raw[:-1]), ('trailing', raw + b'\0'), ('changed', bytes([raw[0] ^ 1]) + raw[1:])]
    with tempfile.TemporaryDirectory(prefix='lezac-natural-level2-guard-') as temporary:
        root = Path(temporary)
        (root / 'route.txt').write_bytes((FIXTURE / 'route.txt').read_bytes())
        for name, payload in bad:
            (root / 'reference.jsonl.gz').write_bytes(payload)
            try:
                fixture(root)
            except fidelity.EvidenceError:
                continue
            raise fidelity.EvidenceError('malformed fixture accepted: ' + name)
    require((FIXTURE / 'reference.jsonl.gz').read_bytes() == raw, 'guard changed the source fixture')
    producer_rejected = 0
    with tempfile.TemporaryDirectory(prefix='lezac-natural-level2-producer-') as temporary:
        root = Path(temporary)
        sources = {'route-explorer.py': (PRODUCER / 'route-explorer.py').read_bytes(),
                   'base-observer.py': BASE_OBSERVER.read_bytes(), 'extension-observer.py': BASE_OBSERVER.read_bytes(),
                   'route-config.json': (PRODUCER / 'route-config.json').read_bytes(),
                   'route-provenance.json': (PRODUCER / 'route-provenance.json').read_bytes()}
        for name, data in sources.items():
            (root / name).write_bytes(data)
        check_producer(root)
        for name in sources:
            (root / name).write_bytes(sources[name] + b' ')
            try:
                pack(root, root, root / 'must-not-exist')
            except fidelity.EvidenceError:
                producer_rejected += 1
            else:
                raise fidelity.EvidenceError('modified producer accepted: ' + name)
            require(not (root / 'must-not-exist').exists(), 'untrusted producer generated evidence')
            (root / name).write_bytes(sources[name])
    require(producer_rejected == 5, 'modified producer guard incomplete')
    print(original.json_bytes({'status': 'guarded', 'field_mutations_rejected': mutations + 1,
                               'invalid_bounds_rejected': rejected, 'fixture_mutations_rejected': len(bad),
                               'producer_mutations_rejected': producer_rejected,
                               'stale_tail_excluded': True}).decode(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('pack', 'compare', 'replay', 'guard'))
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--cpp', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    if args.command == 'pack':
        require(args.capture and args.cpp and args.out, 'capture, C++ bundle and output required')
        pack(args.capture.resolve(), args.cpp.resolve(), args.out.resolve())
    elif args.command == 'guard':
        guard()
    else:
        if args.command == 'replay':
            require(args.exe and args.out, 'executable and new output required')
            fixture()
            args.cpp = args.out / ('run-' + uuid.uuid4().hex)
            fidelity.record(args.exe, ROOT, FIXTURE / 'route.txt', args.cpp, original_intro_wait=True)
        require(args.cpp, 'C++ bundle required')
        print(original.json_bytes(compare(args.cpp.resolve())).decode(), flush=True)


if __name__ == '__main__':
    main()
