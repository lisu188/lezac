"""Validate full native coordinate-writeback bytes and production replay."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tarfile
import tempfile

import capture_original_monster_writeback as producer
from check_flyer_contact_fixture import retained_file
from level1_fidelity import safe_file, strict_json

ROOT = Path(__file__).resolve().parent.parent
COUNT = 256
RECORD = struct.Struct('<HBBhhhhBBHhhhhBBIBB')
FIXTURE_SHA = '23008c501c6e0091d3033022d0e496a45db87ed45b4c10761913158b53708e45'
ARCHIVE_SHA = '6050b6ec10ff7323aa642e1afd674db52088d28f97f321cb407409e6030b355e'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def header():
    windows = producer.flyers.FLOOR + producer.flyers.COMMON + producer.WRITEBACK
    return (b'LZCWv1\0\0' + struct.pack('<HHHH', COUNT, RECORD.size, 0x7062, 0x777F) +
            bytes.fromhex(producer.flyers.base.EXE_SHA) + hashlib.sha256(windows).digest()[:16])


def row_bytes(case, after, actor):
    return RECORD.pack(case['index'], case['kind'], case['profile'],
                       case['x'], case['y'], case['vx'], case['vy'],
                       case['frac_x'], case['frac_y'], case['frame'],
                       after['x'], after['y'], after['vx'], after['vy'],
                       after['frac_x'], after['frac_y'], after['rng'], actor[3], actor[0x19])


def validate(data, exe):
    require(len(data) == 8256 and hashlib.sha256(data).hexdigest() == FIXTURE_SHA,
            'coordinate-writeback fixture extent/hash differs')
    require(data[:64] == header() and hashlib.sha256(exe).hexdigest() == producer.flyers.base.EXE_SHA,
            'coordinate-writeback header/original differs')
    for at, raw in producer.WINDOWS.items():
        require(exe[0x770 + at:0x770 + at + len(raw)] == raw, 'original writeback window differs')
    outside = 0
    for index, case in enumerate(producer.CASES):
        row = RECORD.unpack_from(data, 64 + index * RECORD.size)
        require(row[:10] == (index, case['kind'], case['profile'], case['x'], case['y'],
                            case['vx'], case['vy'], 165, 90, 421), 'writeback input coverage/order differs')
        require(row[16:] == (0x12345678, 11, 1), 'writeback RNG/HP/animation expectation differs')
        outside += not (0 <= row[10] <= 464 and 0 <= row[11] <= 248)
    require(outside == 112, 'out-of-level writeback coverage differs')


def capture_bytes(directory, producer_file, helper_file, observer=producer, fixture_header=None):
    capture = strict_json((directory / 'capture.json').read_text(encoding='utf-8'))
    require(not (directory / 'failure.json').exists() and capture['schema'] == observer.SCHEMA and
            capture['complete'] is True and capture['case_count'] == len(capture['cases']) == len(observer.CASES) and
            capture['kind_coverage'] == sorted({case['kind'] for case in observer.CASES}) and
            capture['profile_coverage'] == sorted({case['profile'] for case in observer.CASES}),
            'native writeback capture is failed/incomplete')
    require(capture['producer_sha256'] == hashlib.sha256(producer_file.read_bytes()).hexdigest() and
            capture['support_dependencies_sha256']['capture_original_flyer_contacts.py'] ==
            hashlib.sha256(helper_file.read_bytes()).hexdigest(), 'executed writeback sources differ')
    require(capture['audio_driver'] == 'dummy' and capture['owned_child_returncode'] is not None and
            capture['hook_free_stack_preserved'] is True and capture['selected_actor_parameter_guard'] is True and
            capture['unseeded_bootstrap_ticks'] == 1 and capture['seeded_case_boundaries'] is True and
            capture['seeded_terrain'] is True and capture['complete_coordinate_writeback_observed'] is True and
            capture['observed_entry_exit'] == [0x7062, 0x777F] and
            all(capture[name] is False for name in ('natural_campaign_claim', 'original_fidelity_claim',
                'full_actor_update_parity_claim', 'pixel_parity_claim')), 'writeback provenance/closure/scope differs')
    require(capture['hooks'] == [[at, raw.hex()] for at, raw in observer.HOOKS] and
            capture['instruction_windows'] == {str(at): raw.hex() for at, raw in observer.WINDOWS.items()},
            'writeback instruction windows differ')
    for name, digest in capture['files'].items():
        require(hashlib.sha256(safe_file(directory, name).read_bytes()).hexdigest() == digest, 'native writeback file differs')
    require(set(capture['assets_sha256']) == set(observer.flyers.base.ASSETS), 'writeback asset scope differs')
    for name, digest in capture['assets_sha256'].items():
        require(hashlib.sha256(safe_file(ROOT, name).read_bytes()).hexdigest() == digest, 'source asset differs')
    for name, digest in (capture['support_dependencies_sha256'] | capture['dependency_sha256']).items():
        if name != 'capture_original_flyer_contacts.py':
            require(hashlib.sha256(safe_file(ROOT / 'tools', name).read_bytes()).hexdigest() == digest, 'writeback dependency differs')
    require(strict_json((directory / 'restoration.json').read_text()) ==
            {'hooks_restored': True, 'scratch_restored': True, 'child_retained_stopped': True, 'installed_hooks': 3},
            'writeback restoration differs')
    result = bytearray(header() if fixture_header is None else fixture_header)
    for expected, row in zip(observer.CASES, capture['cases']):
        case, before, after = row['seed'], row['before'], row['after']
        require(case == expected, 'writeback native input case differs')
        require((before['x'], before['y'], before['vx'], before['vy'], before['frac_x'], before['frac_y'], before['rng']) ==
                (case['x'], case['y'], case['vx'], case['vy'], 165, 90, 0x12345678), 'initial writeback motion differs')
        require(before['kind'] == after['kind'] == case['kind'] and before['behavior'] == after['behavior'] == 4 and
                before['frame'] == after['frame'] == 421 and before['edges'] == after['edges'] == [0, 0, 0, 0] and
                before['registers'][0:2] == after['registers'][0:2] and before['registers'][3:] == after['registers'][3:] and
                before['actor_pointer'] == after['actor_pointer'] == [0x1BD4, before['registers'][1]],
                'writeback actor/frame/stack differs')
        require(hashlib.sha256(bytes(1980)).hexdigest() == row['terrain_sha256'], 'writeback terrain differs')
        seed = bytearray(38)
        seed[0], seed[1], seed[3], seed[4], seed[0x15], seed[0x24] = case['kind'], 2, 11, 11, 4, 255
        struct.pack_into('<hhHHHHH', seed, 6, case['vx'], case['vy'], 165, 90, 14, 271, 75)
        seed[0x16:0x1D] = bytes((40, 40, 42, 0, 3, 1, 1))
        require(bytes.fromhex(row['seeded_actor_hex']) == seed, 'writeback actor seed differs')
        for phase in (before, after):
            raw = bytes.fromhex(phase['stack_hex'])
            require(len(raw) == 0x3A and len(phase['registers']) == 6, 'writeback raw stack/register extent differs')
            decoded = tuple(struct.unpack_from('<h', raw, 0x3A + at)[0] for at in (-44, -46, -12, -14))
            require(decoded == tuple(phase[key] for key in ('x', 'y', 'vx', 'vy')) and
                    (raw[42], raw[41]) == (phase['frac_x'], phase['frac_y']) and
                    [raw[0x3A + at] for at in (-35, -36, -34, -33)] == phase['edges'],
                    'writeback decoded motion differs from raw locals')
        actor = bytes.fromhex(row['writeback_actor_hex'])
        visual = bytes.fromhex(row['writeback_visual_hex'])
        require(len(actor) == 38 and len(visual) == 8 and
                struct.unpack_from('<hh', visual) == (after['x'], after['y']) and visual[4:] == bytes.fromhex('10100027'),
                'actual visual-table writeback differs from original locals/descriptor')
        struct.pack_into('<hhHH', seed, 6, after['vx'], after['vy'], after['frac_x'], after['frac_y'])
        seed[0x19] = 1
        require(actor == seed, 'actual actor-table writeback differs from original locals/unchanged fields')
        result += row_bytes(case, after, actor)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=ROOT / 'tests/fixtures/monster_coordinate_writeback_original.bin')
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--extract', nargs=2, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--producer-file', type=Path, default=ROOT / 'tools/capture_original_monster_writeback.py')
    parser.add_argument('--helper-file', type=Path, default=ROOT / 'tools/capture_original_flyer_contacts.py')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--replay-exe', type=Path)
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()
    if args.extract:
        require(args.output is not None and not args.output.exists(), 'writeback extraction needs a fresh output')
        first, second = [capture_bytes(directory, args.producer_file, args.helper_file) for directory in args.extract]
        require(first == second, 'independent complete native writebacks differ')
        args.output.write_bytes(first)
        fingerprint = 0xCBF29CE484222325
        for byte in first:
            fingerprint = ((fingerprint ^ byte) * 0x100000001B3) & ((1 << 64) - 1)
        print(f'monster_writeback_extraction=ok cases=256 bytes={len(first)} sha256={hashlib.sha256(first).hexdigest()} fnv={fingerprint:016x} independent_runs=2')
        return 0
    data, exe = args.fixture.read_bytes(), (ROOT / 'LEZAC.EXE').read_bytes()
    validate(data, exe)
    if args.archive:
        path = ROOT / 'docs/recovery/evidence/monster_writeback_20261004/native-captures.tar.gz'
        require(path.stat().st_size == 101690 and hashlib.sha256(path.read_bytes()).hexdigest() == ARCHIVE_SHA,
                'retained writeback archive extent/hash differs')
        with tempfile.TemporaryDirectory(prefix='lezac-writeback-archive-') as directory:
            temporary = Path(directory)
            with tarfile.open(path, 'r:gz') as archive:
                members = archive.getmembers()
                names = [member.name for member in members]
                require(len(members) == len(set(names)) == 27 and sum(member.size for member in members) < 4 * 1024 * 1024,
                        'retained writeback member extent differs')
                for member in members:
                    require(member.isfile() and member.size >= 0, 'retained writeback archive contains a non-file')
                    target = retained_file(temporary, member.name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    content = archive.extractfile(member).read()
                    require(len(content) == member.size, 'retained writeback member bytes truncated')
                    target.write_bytes(content)
            manifest = strict_json((temporary / 'manifest.json').read_text())
            require(set(manifest) == set(names) - {'manifest.json'}, 'retained writeback manifest scope differs')
            for name, item in manifest.items():
                content = retained_file(temporary, name).read_bytes()
                require(len(content) == item['bytes'] and hashlib.sha256(content).hexdigest() == item['sha256'],
                        'retained writeback member bytes differ')
            for suffix in ('a', 'b'):
                require(capture_bytes(temporary / suffix, temporary / 'tools/capture_original_monster_writeback.py',
                        temporary / 'tools/capture_original_flyer_contacts.py') == data,
                        'retained native writeback does not reproduce pinned fixture')
            negative = strict_json((temporary / 'negative.json').read_text())
            positive = strict_json((temporary / 'positive.json').read_text())
            outside = [index for index in range(COUNT) for row in [RECORD.unpack_from(data, 64 + index * RECORD.size)]
                       if not (0 <= row[10] <= 464 and 0 <= row[11] <= 248)]
            require(negative['returncode'] == 1 and negative['mismatch_count'] == 112 and negative['mismatches'] == outside and
                    negative['stderr'].strip() == 'fatal: monster production writeback differs at cases ' + ','.join(map(str, outside)) and
                    positive['returncode'] == 0 and 'cases=256 production_updates=256' in positive['stdout'] and
                    'outside_level=112' in positive['stdout'] and negative['audio'] == positive['audio'] == 'dummy',
                    'retained writeback negative/positive diagnostic differs')
        print('monster_writeback_retained_archive=ok captures=2 cases_each=256 members=27 byte_verified=1 negative_diagnostic_preserved=1')
    elif args.capture:
        require(capture_bytes(args.capture, args.producer_file, args.helper_file) == data,
                'complete native writeback does not reproduce pinned fixture')
        print('monster_writeback_native_capture=ok cases=256 kinds=1..8 outside=112 fixture_byte_match=1 hooks_restored=1 child_closed=1 audio=dummy')
    elif args.self_test:
        for index in range(len(data)):
            changed = bytearray(data)
            changed[index] ^= 1
            try:
                validate(bytes(changed), exe)
            except ValueError:
                continue
            raise AssertionError(f'accepted writeback fixture mutation {index}')
        for changed, original in ((data[:-1], exe), (data + b'\0', exe), (data, exe[:-1])):
            try:
                validate(changed, original)
            except ValueError:
                continue
            raise AssertionError('accepted malformed writeback fixture/original')
        print('monster_writeback_fixture_selftest=ok byte_mutations=8256 truncated=1 trailing=1 original_mutation=1')
    elif args.replay_exe:
        env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        command = [str(args.replay_exe.resolve()), '--debug-monster-coordinate-writeback']
        positive = subprocess.run([*command, str(args.fixture.resolve())], env=env, cwd=ROOT, capture_output=True, text=True, timeout=30)
        require(positive.returncode == 0 and 'monster_coordinate_writeback=ok cases=256 production_updates=256' in positive.stdout,
                'positive coordinate-writeback production replay failed')
        mutations = [data[:-1], data + b'\0']
        for at in (0, 8, 12, 16, 48, 64, 66, 67, 68, 70, 72, 78, 80, 90, 4096, 8255):
            changed = bytearray(data)
            changed[at] ^= 1
            mutations.append(bytes(changed))
        with tempfile.TemporaryDirectory(prefix='lezac-writeback-guard-') as directory:
            for index, changed in enumerate(mutations):
                path = Path(directory) / f'mutation-{index}.bin'
                path.write_bytes(changed)
                result = subprocess.run([*command, str(path)], env=env, cwd=ROOT, capture_output=True, text=True, timeout=10)
                require(result.returncode != 0 and 'monster coordinate-writeback fixture bytes changed' in result.stderr and
                        'monster_coordinate_writeback=ok' not in result.stdout, f'production accepted malformed writeback fixture {index}')
        print('monster_writeback_replay_guard=ok positive=1 rejected=18 audio=dummy')
    else:
        print('monster_writeback_fixture=ok cases=256 bytes=8256 kinds=1..8 outside=112 original_exit=0x777f')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
