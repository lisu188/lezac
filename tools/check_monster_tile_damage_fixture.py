"""Verify full original embedding-damage records and the real C++ caller."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tarfile
import tempfile

import capture_original_monster_tile_damage as producer
from check_monster_writeback_fixture import capture_report, require
from check_flyer_contact_fixture import retained_file
from level1_fidelity import strict_json

ROOT = Path(__file__).resolve().parent.parent
COUNT, ROW_SIZE = 1312, 80
SIZE = 64 + COUNT * ROW_SIZE
FIXTURE_SHA = '8417f07de35ddd512032ee8eccfadccd36be386776f0e6770f01bd05ec30d7b1'
ARCHIVE_SHA = '3ef5af26bdf845df47a9d2ec664116b235627473d3aa8ff983e897a20c3983cd'
ARCHIVE_SIZE = 382489
ARCHIVE_COUNT = 33
INPUT = struct.Struct('<HBBBBhhhhBBHBB')
MOTION = struct.Struct('<hhhhBBI')


def header():
    windows = producer.flyers.FLOOR + producer.flyers.COMMON + producer.DAMAGE + producer.IMPACT + producer.WRITEBACK
    return (b'LZTDv1\0\0' + struct.pack('<HHHH', COUNT, ROW_SIZE, 0x7062, 0x777F) +
            bytes.fromhex(producer.flyers.base.EXE_SHA) + hashlib.sha256(windows).digest()[:16])


def input_bytes(case):
    return INPUT.pack(case['index'], case['kind'], case['glyph'], case['cell_mask'], case['hp_byte'],
                      case['x'], case['y'], case['vx'], case['vy'], case['frac_x'], case['frac_y'],
                      case['frame'], 0, case['profile'])


def capture_bytes(directory, producer_file, helper_file):
    capture = capture_report(directory, producer_file, helper_file, producer)
    require(capture['health_byte_offset'] == 0x24 and capture['seeded_health_bytes'] == [0, 10] and
            capture['shared_actor_profiles'] is True and capture['natural_constructor_claim'] is False,
            'tile-damage profile/health attribution differs')
    result = bytearray(header())
    for expected, row in zip(producer.CASES, capture['cases']):
        case, before, after = row['seed'], row['before'], row['after']
        require(case == expected, 'tile-damage input coverage/order differs')
        require((before['x'], before['y'], before['vx'], before['vy'], before['frac_x'], before['frac_y']) ==
                (336, 99, case['vx'], case['vy'], 165, 90), 'tile-damage initial motion differs')
        require(before['kind'] == after['kind'] == case['kind'] and before['behavior'] == after['behavior'] == 4 and
                before['frame'] == after['frame'] == 421 and before['rng'] == after['rng'] == 0x12345678 and
                before['edges'] == after['edges'] == [0, 0, 0, 0] and
                before['registers'][:2] == after['registers'][:2] and before['registers'][3:] == after['registers'][3:] and
                before['actor_pointer'] == after['actor_pointer'] == [0x1BD4, before['registers'][1]],
                'tile-damage call/frame/stack/edge identity differs')
        terrain = bytearray(1980)
        for x, y, glyph in case['tiles']:
            terrain[y * 60 + x] = glyph
        require(hashlib.sha256(terrain).hexdigest() == row['terrain_sha256'], 'tile-damage terrain differs')
        seed = bytearray(38)
        seed[0], seed[1], seed[3], seed[4], seed[0x15], seed[0x24] = case['kind'], 2, 11, 11, 4, case['hp_byte']
        struct.pack_into('<hhHHHHH', seed, 6, case['vx'], case['vy'], 165, 90, 14, 271, 75)
        seed[0x16:0x1D] = bytes((40, 40, 42, 0, 3, 1, 1))
        require(bytes.fromhex(row['seeded_actor_hex']) == seed, 'tile-damage raw actor seed differs')
        for phase in (before, after):
            raw = bytes.fromhex(phase['stack_hex'])
            require(len(raw) == 58 and len(phase['registers']) == 6, 'tile-damage raw stack/register extent differs')
            require(tuple(struct.unpack_from('<h', raw, 58 + at)[0] for at in (-44, -46, -12, -14)) ==
                    tuple(phase[key] for key in ('x', 'y', 'vx', 'vy')) and
                    (raw[42], raw[41]) == (phase['frac_x'], phase['frac_y']) and
                    [raw[58 + at] for at in (-35, -36, -34, -33)] == phase['edges'],
                    'tile-damage decoded locals differ from raw stack')
        actor, visual = bytes.fromhex(row['writeback_actor_hex']), bytes.fromhex(row['writeback_visual_hex'])
        require(len(actor) == 38 and len(visual) == 8 and
                struct.unpack_from('<hh', visual) == (after['x'], after['y']) and
                struct.unpack_from('<hhHH', actor, 6) == (after['vx'], after['vy'], after['frac_x'], after['frac_y']),
                'tile-damage actual table writeback differs from raw locals')
        changed = {0, 2, *range(6, 14), 20, 21, 25, 27, 36}
        require(all(actor[i] == seed[i] for i in range(38) if i not in changed),
                'tile-damage changes an undeclared actor field')
        result += input_bytes(case) + MOTION.pack(*(after[key] for key in
                  ('x', 'y', 'vx', 'vy', 'frac_x', 'frac_y', 'rng'))) + actor + visual
    require(len(result) == SIZE, 'tile-damage extracted extent differs')
    return bytes(result)


def damage_cases(data):
    return [i for i in range(COUNT) if data[64 + i * ROW_SIZE + 59] == 255]


def validate(data, exe):
    require(len(data) == SIZE and hashlib.sha256(data).hexdigest() == FIXTURE_SHA, 'tile-damage fixture extent/hash differs')
    require(data[:64] == header() and hashlib.sha256(exe).hexdigest() == producer.flyers.base.EXE_SHA,
            'tile-damage header/original differs')
    for at, raw in producer.WINDOWS.items():
        require(exe[0x770 + at:0x770 + at + len(raw)] == raw, 'original tile-damage instructions differ')
    require(exe[0x770 + 0xAA97:0x770 + 0xAA97 + 19] == bytes.fromhex('2c282830312b2b3535393901020b0b0c0c0d0d'),
            'original impact-sprite data table differs')
    hits, fatal, post_only = 0, 0, 0
    for case in producer.CASES:
        offset = 64 + case['index'] * ROW_SIZE
        require(data[offset:offset + 20] == input_bytes(case), 'tile-damage fixture seed coverage differs')
        motion, actor, visual = MOTION.unpack_from(data, offset + 20), data[offset + 34:offset + 72], data[offset + 72:offset + 80]
        require(motion[2:] == (case['vx'], case['vy'], (165 + case['vx']) & 255,
                              (90 + case['vy']) & 255, 0x12345678), 'tile-damage native motion/RNG differs')
        require(struct.unpack_from('<hh', visual) == motion[:2] and struct.unpack_from('<hhHH', actor, 6) == motion[2:6],
                'tile-damage fixture tables/locals disagree')
        amount = 0 if case['profile'] == 2 else case['cell_mask'].bit_count() * (2 if case['glyph'] == 0x75 else int(1 <= case['glyph'] <= 0x4C))
        dying = amount > case['hp_byte']
        require(actor[0x24] == (case['hp_byte'] if dying else case['hp_byte'] - amount) and
                actor[0] == (12 if dying else case['kind']) and actor[0x15] == (2 if dying else 4) and
                actor[2] == (25 if dying else 0) and actor[0x19] == (255 if amount else 1) and
                actor[0x1B] == (0 if dying else 1), 'tile-damage HP/conversion/animation differs')
        hits += amount > 0
        fatal += dying
        post_only += case['profile'] == 2 and amount == 0
    require((hits, fatal, post_only) == (552, 96, 96), 'tile-damage boundary coverage differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=ROOT / 'tests/fixtures/monster_tile_damage_original.bin')
    parser.add_argument('--extract', nargs=2, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--producer-file', type=Path, default=ROOT / 'tools/capture_original_monster_tile_damage.py')
    parser.add_argument('--helper-file', type=Path, default=ROOT / 'tools/capture_original_flyer_contacts.py')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--replay-exe', type=Path)
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()
    if args.extract:
        require(args.output is not None and not args.output.exists(), 'tile-damage extraction needs a fresh output')
        first, second = [capture_bytes(path, args.producer_file, args.helper_file) for path in args.extract]
        require(first == second, 'independent full native tile-damage writebacks differ')
        args.output.write_bytes(first)
        fnv = 0xCBF29CE484222325
        for byte in first:
            fnv = ((fnv ^ byte) * 0x100000001B3) & ((1 << 64) - 1)
        print(f'monster_tile_damage_extraction=ok cases={COUNT} bytes={SIZE} sha256={hashlib.sha256(first).hexdigest()} fnv={fnv:016x} independent_runs=2')
        return 0
    data, exe = args.fixture.read_bytes(), (ROOT / 'LEZAC.EXE').read_bytes()
    validate(data, exe)
    if args.capture:
        require(capture_bytes(args.capture, args.producer_file, args.helper_file) == data, 'native tile-damage capture does not reproduce fixture')
        print('monster_tile_damage_native_capture=ok cases=1312 fixture_byte_match=1 hooks_restored=1 child_closed=1 audio=dummy')
    elif args.self_test:
        for i in range(SIZE):
            changed = bytearray(data)
            changed[i] ^= 1
            try:
                validate(changed, exe)
            except ValueError:
                continue
            raise AssertionError(f'accepted tile-damage mutation {i}')
        for changed, original in ((data[:-1], exe), (data + b'\0', exe), (data, exe[:-1])):
            try:
                validate(changed, original)
            except ValueError:
                continue
            raise AssertionError('accepted malformed tile-damage fixture/original')
        print(f'monster_tile_damage_fixture_selftest=ok byte_mutations={SIZE} truncated=1 trailing=1 original_mutation=1')
    elif args.replay_exe:
        env = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
        command = [str(args.replay_exe.resolve()), '--debug-monster-tile-damage']
        result = subprocess.run([*command, str(args.fixture.resolve())], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        require(result.returncode == 0 and 'cases=1312 production_updates=1312' in result.stdout, 'tile-damage positive production replay failed')
        mutations = [data[:-1], data + b'\0']
        for at in (0, 8, 12, 16, 48, 64, 66, 67, 68, 69, 70, 78, 84, 98, 122, SIZE - 1):
            changed = bytearray(data)
            changed[at] ^= 1
            mutations.append(changed)
        with tempfile.TemporaryDirectory(prefix='lezac-tile-damage-guard-') as directory:
            for i, changed in enumerate(mutations):
                path = Path(directory) / f'{i}.bin'
                path.write_bytes(changed)
                result = subprocess.run([*command, str(path)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
                require(result.returncode != 0 and 'monster tile-damage fixture bytes changed' in result.stderr and
                        'monster_tile_damage=ok' not in result.stdout, f'accepted malformed tile-damage fixture {i}')
        print('monster_tile_damage_replay_guard=ok positive=1 rejected=18 audio=dummy')
    elif args.archive:
        path = ROOT / 'docs/recovery/evidence/monster_tile_damage_20261004/native-captures.tar.gz'
        require(path.stat().st_size == ARCHIVE_SIZE and hashlib.sha256(path.read_bytes()).hexdigest() == ARCHIVE_SHA, 'tile-damage archive differs')
        with tempfile.TemporaryDirectory(prefix='lezac-tile-damage-archive-') as directory:
            temporary = Path(directory)
            with tarfile.open(path, 'r:gz') as archive:
                members = archive.getmembers()
                names = [member.name for member in members]
                require(len(members) == len(set(names)) == ARCHIVE_COUNT and sum(m.size for m in members) < 24 * 1024 * 1024,
                        'tile-damage retained member extent differs')
                for member in members:
                    require(member.isfile() and member.size >= 0, 'tile-damage archive contains a non-file')
                    target = retained_file(temporary, member.name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    content = archive.extractfile(member).read()
                    require(len(content) == member.size, 'tile-damage member truncated')
                    target.write_bytes(content)
            manifest = strict_json((temporary / 'manifest.json').read_text())
            require(set(manifest) == set(names) - {'manifest.json'}, 'tile-damage manifest scope differs')
            for name, item in manifest.items():
                content = retained_file(temporary, name).read_bytes()
                require(len(content) == item['bytes'] and hashlib.sha256(content).hexdigest() == item['sha256'], 'tile-damage retained member differs')
            for suffix in ('a', 'b'):
                require(capture_bytes(temporary / suffix, temporary / 'tools/capture_original_monster_tile_damage.py',
                                     temporary / 'tools/capture_original_flyer_contacts.py') == data, 'retained tile-damage capture differs')
            negative, positive = [strict_json((temporary / f'{name}.json').read_text()) for name in ('negative', 'positive')]
            expected = [i for i in damage_cases(data) if data[64 + i * ROW_SIZE + 2] >= 5]
            require(len(expected) == 276 and negative['returncode'] == 1 and negative['mismatches'] == expected and
                    negative['stderr'].strip() == 'fatal: monster production tile damage differs at cases ' + ','.join(map(str, expected)) and
                    positive['returncode'] == 0 and 'production_updates=1312' in positive['stdout'] and
                    negative['audio'] == positive['audio'] == 'dummy', 'retained tile-damage before/after replay differs')
        print(f'monster_tile_damage_retained_archive=ok captures=2 cases_each=1312 members={ARCHIVE_COUNT} byte_verified=1 negative_preserved=1')
    else:
        print(f'monster_tile_damage_fixture=ok cases={COUNT} bytes={SIZE} kinds=1..8 glyphs=8 fatal=96 post_motion_only=96 original_exit=0x777f')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
