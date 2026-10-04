"""Validate native flyer motion provenance, pinned bytes and production rejection."""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import struct
import subprocess
import tempfile
import tarfile

import capture_original_flyer_contacts as producer
from level1_fidelity import safe_file, strict_json

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_SHA = 'e82e0f352fd2e83fefbccfe297e3504254a0289d90952d3e6f75e7c98ea0b367'
ARCHIVE_SHA = 'b285a0969e7e070c0a996cec82f828ec4746bcd4e3b0e1b1094ee15e5ae51641'
RECORD = struct.Struct('<HBBBBBBhhBBHHHHhhhhBBI')
COUNT = 176


def require(condition, message):
    if not condition:
        raise ValueError(message)


def retained_file(root, name):
    relative = PurePosixPath(name)
    require(isinstance(name, str) and not relative.is_absolute() and relative.parts and
            all(part not in ('.', '..') and '\\' not in part and ':' not in part for part in relative.parts),
            'unsafe retained artifact name')
    path = root.joinpath(*relative.parts)
    require(path.resolve().is_relative_to(root.resolve()) and not path.is_symlink(), 'retained artifact escapes its root')
    return path


def header():
    windows = producer.FLOOR + producer.COMMON
    return b'LZFCv1\0\0' + struct.pack('<HHHH', COUNT, RECORD.size, 0x7062, 0x741E) + bytes.fromhex(producer.base.EXE_SHA) + hashlib.sha256(windows).digest()[:16]


def edges(case):
    strong = 1 <= case['glyph'] <= 0x4C
    bottom = 1 <= case['glyph'] <= 0x52
    return (case['mask'] & 7 if strong else 0) | (case['mask'] & 8 if bottom else 0)


def record(case, after):
    return RECORD.pack(case['index'], case['kind'], case['mask'], case['glyph'], case['mode'],
                       edges(case), int(bool(case['mask'] & 8 and 1 <= case['glyph'] <= 0x4C)),
                       case['vx'], case['vy'], case['frac_x'], case['frac_y'],
                       case['frame'], case['ai0'], case['ai1'], case['ai2'],
                       after['x'], after['y'], after['vx'], after['vy'],
                       after['frac_x'], after['frac_y'], after['rng'])


def validate(data, exe):
    require(len(data) == 6400 and hashlib.sha256(data).hexdigest() == FIXTURE_SHA, 'fixture extent/hash differs')
    require(data[:64] == header() and hashlib.sha256(exe).hexdigest() == producer.base.EXE_SHA, 'fixture header/original differs')
    for at, raw in producer.WINDOWS.items():
        require(exe[0x770 + at:0x770 + at + len(raw)] == raw, 'original instruction window differs')
    for index, case in enumerate(producer.CASES):
        row = RECORD.unpack_from(data, 64 + index * RECORD.size)
        require(row[:15] == (index, case['kind'], case['mask'], case['glyph'], case['mode'], edges(case),
                int(bool(case['mask'] & 8 and 1 <= case['glyph'] <= 0x4C)), case['vx'], case['vy'],
                165, 90, case['frame'], 14, 271, 75), 'case input coverage/order differs')
    require(sum(RECORD.unpack_from(data, 64 + index * 36)[7] == -32768 for index in range(COUNT)) == 8,
            'signed NEG boundary coverage differs')


def capture_bytes(directory, producer_file):
    capture = strict_json((directory / 'capture.json').read_text(encoding='utf-8'))
    require(not (directory / 'failure.json').exists() and capture['schema'] == 'lezac-flyer-contact-motion-v1' and
            capture['complete'] is True and capture['case_count'] == len(capture['cases']) == COUNT and
            capture['kind_coverage'] == list(range(1, 9)), 'native capture is failed/incomplete')
    require(capture['producer_sha256'] == hashlib.sha256(producer_file.read_bytes()).hexdigest() and
            capture['audio_driver'] == 'dummy' and capture['owned_child_returncode'] is not None and
            capture['hook_free_stack_preserved'] is True and capture['selected_actor_parameter_guard'] is True and
            capture['unseeded_bootstrap_ticks'] == 1 and capture['seeded_case_boundaries'] is True and
            capture['seeded_terrain'] is True and capture['observed_entry_exit'] == [0x7062, 0x741E] and
            all(capture[name] is False for name in ('natural_campaign_claim', 'original_fidelity_claim',
                'full_actor_update_parity_claim', 'pixel_parity_claim')), 'native provenance/closure/scope differs')
    require(capture['hooks'] == [[at, raw.hex()] for at, raw in producer.HOOKS] and
            capture['instruction_windows'] == {str(at): raw.hex() for at, raw in producer.WINDOWS.items()}, 'native instruction windows differ')
    for name, digest in capture['files'].items():
        require(hashlib.sha256(safe_file(directory, name).read_bytes()).hexdigest() == digest, 'native file differs')
    require(set(capture['assets_sha256']) == set(producer.base.ASSETS), 'native asset scope differs')
    for name, digest in capture['assets_sha256'].items():
        require(hashlib.sha256(safe_file(ROOT, name).read_bytes()).hexdigest() == digest, 'source asset differs')
    for name, digest in (capture['support_dependencies_sha256'] | capture['dependency_sha256']).items():
        require(hashlib.sha256(safe_file(ROOT / 'tools', name).read_bytes()).hexdigest() == digest, 'capture dependency differs')
    require(strict_json((directory / 'restoration.json').read_text()) ==
            {'hooks_restored': True, 'scratch_restored': True, 'child_retained_stopped': True, 'installed_hooks': 3}, 'restoration differs')
    result = bytearray(header())
    for expected, row in zip(producer.CASES, capture['cases']):
        case, before, after = row['seed'], row['before'], row['after']
        require(case == expected, 'native input case differs')
        require((before['vx'], before['vy'], before['x'], before['y'], before['frac_x'], before['frac_y'], before['rng']) ==
                (case['vx'], case['vy'], 336, 99, 165, 90, 0x12345678), 'native initial motion differs')
        require(before['kind'] == after['kind'] == case['kind'] and before['behavior'] == after['behavior'] == 4 and
                before['frame'] == after['frame'] == case['frame'] and
                before['registers'][0:2] == after['registers'][0:2] and before['registers'][3:] == after['registers'][3:] and
                before['actor_pointer'] == after['actor_pointer'] == [0x1BD4, before['registers'][1]], 'native actor/frame/stack differs')
        require(before['edges'] == after['edges'] == [int(bool(edges(case) & (1 << bit))) for bit in range(4)], 'native terrain flags differ')
        terrain = bytearray(1980)
        for bit, cells in ((1, ((41, 12), (41, 13))), (2, ((44, 12), (44, 13))),
                           (4, ((42, 11), (43, 11))), (8, ((42, 14), (43, 14)))):
            if case['mask'] & bit:
                for column, y in cells:
                    terrain[y * 60 + column] = case['glyph']
        require(hashlib.sha256(terrain).hexdigest() == row['terrain_sha256'], 'declared terrain seed differs')
        seed = bytearray(38)
        seed[0], seed[1], seed[3], seed[4], seed[0x15], seed[0x24] = case['kind'], 2, 11, 11, 4, 255
        struct.pack_into('<hhHHHHH', seed, 6, case['vx'], case['vy'], 165, 90, 14, 271, 75)
        seed[0x16:0x1D] = bytes((40, 40, 42, 0, 3, 1, 1))
        require(bytes.fromhex(row['seeded_actor_hex']) == seed, 'native actor seed differs')
        for phase in (before, after):
            raw = bytes.fromhex(phase['stack_hex'])
            require(len(raw) == 0x3A and len(phase['registers']) == 6, 'native raw stack/register extent differs')
            decoded = tuple(struct.unpack_from('<h', raw, 0x3A + at)[0] for at in (-44, -46, -12, -14))
            require(decoded == tuple(phase[key] for key in ('x', 'y', 'vx', 'vy')) and
                    (raw[42], raw[41]) == (phase['frac_x'], phase['frac_y']) and
                    [raw[0x3A + at] for at in (-35, -36, -34, -33)] == phase['edges'], 'decoded motion differs from raw locals')
        delta = tuple(struct.unpack_from('<h', bytes.fromhex(before['stack_hex']), 0x3A + at)[0] for at in (-4, -6))
        require(delta == ((-40, -20) if case['mode'] == 2 else (-96, -19)), 'native steering target input differs')
        result += record(case, after)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=ROOT / 'tests/fixtures/flyer_contact_motion_original.bin')
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--extract', nargs=2, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--producer-file', type=Path, default=ROOT / 'tools/capture_original_flyer_contacts.py')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--replay-exe', type=Path)
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()
    if args.extract:
        require(args.output is not None and not args.output.exists(), 'extraction needs a fresh output')
        first, second = [capture_bytes(directory, args.producer_file) for directory in args.extract]
        require(first == second, 'independent complete native captures differ')
        args.output.write_bytes(first)
        print(f'flyer_contact_extraction=ok cases={COUNT} bytes={len(first)} sha256={hashlib.sha256(first).hexdigest()} independent_runs=2')
        return 0
    data, exe = args.fixture.read_bytes(), (ROOT / 'LEZAC.EXE').read_bytes()
    validate(data, exe)
    if args.archive:
        path = ROOT / 'docs/recovery/evidence/flyer_contact_20261004/native-captures.tar.gz'
        require(path.stat().st_size == 87844 and hashlib.sha256(path.read_bytes()).hexdigest() == ARCHIVE_SHA,
                'retained archive extent/hash differs')
        with tempfile.TemporaryDirectory(prefix='lezac-flyer-archive-') as directory:
            temporary = Path(directory)
            with tarfile.open(path, 'r:gz') as archive:
                members = archive.getmembers()
                names = [member.name for member in members]
                require(len(members) == len(set(names)) == 24 and sum(member.size for member in members) < 4 * 1024 * 1024,
                        'retained member extent differs')
                for member in members:
                    require(member.isfile() and member.size >= 0, 'retained archive contains a non-file')
                    target = retained_file(temporary, member.name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    content = archive.extractfile(member).read()
                    require(len(content) == member.size, 'retained member bytes truncated')
                    target.write_bytes(content)
            manifest = strict_json((temporary / 'manifest.json').read_text())
            require(set(manifest) == set(names) - {'manifest.json'}, 'retained manifest scope differs')
            for name, item in manifest.items():
                content = retained_file(temporary, name).read_bytes()
                require(len(content) == item['bytes'] and hashlib.sha256(content).hexdigest() == item['sha256'], 'retained member bytes differ')
            for suffix in ('a', 'b'):
                require(capture_bytes(temporary / suffix, temporary / 'tools/capture_original_flyer_contacts.py') == data,
                        'retained native capture does not reproduce pinned fixture')
            negative = strict_json((temporary / 'negative.json').read_text())
            positive = strict_json((temporary / 'positive.json').read_text())
            require(negative['returncode'] == 1 and 'cases 112,116,120,124,128,132,136,140' in negative['stderr'] and
                    positive['returncode'] == 0 and 'cases=176 production_updates=176' in positive['stdout'] and
                    negative['audio'] == positive['audio'] == 'dummy', 'retained negative/positive diagnostic differs')
        print('flyer_contact_retained_archive=ok captures=2 cases_each=176 members=24 byte_verified=1 negative_diagnostic_preserved=1')
    elif args.capture:
        require(capture_bytes(args.capture, args.producer_file) == data, 'complete native output does not reproduce pinned fixture')
        print('flyer_contact_native_capture=ok cases=176 kinds=1..8 fixture_byte_match=1 hooks_restored=1 child_closed=1 audio=dummy')
    elif args.self_test:
        for index in range(len(data)):
            changed = bytearray(data)
            changed[index] ^= 1
            try:
                validate(bytes(changed), exe)
            except ValueError:
                continue
            raise AssertionError(f'accepted fixture mutation {index}')
        for changed, original in ((data[:-1], exe), (data + b'\0', exe), (data, exe[:-1])):
            try:
                validate(changed, original)
            except ValueError:
                continue
            raise AssertionError('accepted malformed fixture/original')
        print('flyer_contact_fixture_selftest=ok byte_mutations=6400 truncated=1 trailing=1 original_mutation=1')
    elif args.replay_exe:
        env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        command = [str(args.replay_exe.resolve()), '--debug-flyer-contact-motion-evidence']
        positive = subprocess.run([*command, str(args.fixture.resolve())], env=env, cwd=ROOT, capture_output=True, text=True, timeout=30)
        require(positive.returncode == 0 and 'flyer_contact_motion=ok cases=176 production_updates=176' in positive.stdout, 'positive production replay failed')
        mutations = [data[:-1], data + b'\0']
        for at in (0, 8, 12, 16, 48, 64, 66, 68, 70, 72, 80, 86, 92, 96, 4096, 6399):
            changed = bytearray(data)
            changed[at] ^= 1
            mutations.append(bytes(changed))
        with tempfile.TemporaryDirectory(prefix='lezac-flyer-contact-guard-') as directory:
            for index, changed in enumerate(mutations):
                path = Path(directory) / f'mutation-{index}.bin'
                path.write_bytes(changed)
                result = subprocess.run([*command, str(path)], env=env, cwd=ROOT, capture_output=True, text=True, timeout=10)
                require(result.returncode != 0 and 'flyer contact fixture bytes changed' in result.stderr and
                        'flyer_contact_motion=ok' not in result.stdout, f'production accepted malformed fixture {index}')
        print('flyer_contact_replay_guard=ok positive=1 rejected=18 audio=dummy')
    else:
        print('flyer_contact_fixture=ok cases=176 bytes=6400 kinds=1..8 signed_neg_boundaries=8 original_window=0x7062..0x741e')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
