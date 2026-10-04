"""Verify original signed-coordinate boundaries and full production replay."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tarfile
import tempfile

import capture_original_monster_word_wrap as producer
import check_monster_writeback_fixture as writeback
from check_flyer_contact_fixture import retained_file
from level1_fidelity import strict_json

ROOT = Path(__file__).resolve().parent.parent
COUNT = 768
RECORD = writeback.RECORD
SIZE = 64 + COUNT * RECORD.size
FIXTURE_SHA = '585361d717dcb81ade13503fce6fe043edd1af4c3e3bf2b8a72d02dce9fa4618'
ARCHIVE_SHA = 'c4b600194b41e778a4f17809926a452b93743b77b58f05d617fe49411abd9b7a'
require = writeback.require


def header():
    windows = producer.flyers.FLOOR + producer.flyers.COMMON + producer.WRITEBACK
    return (b'LZWWv1\0\0' + struct.pack('<HHHH', COUNT, RECORD.size, 0x7062, 0x777F) +
            bytes.fromhex(producer.flyers.base.EXE_SHA) + hashlib.sha256(windows).digest()[:16])


def capture_bytes(directory, producer_file, helper_file):
    return writeback.capture_bytes(directory, producer_file, helper_file,
                                   observer=producer, fixture_header=header())


def wrapping_indices(data):
    positive, negative = [], []
    for index, case in enumerate(producer.CASES):
        row = RECORD.unpack_from(data, 64 + index * RECORD.size)
        if (case['x'] == 32760 and row[10] < 0) or (case['y'] == 32760 and row[11] < 0):
            positive.append(index)
        if (case['x'] == -32760 and row[10] > 0) or (case['y'] == -32760 and row[11] > 0):
            negative.append(index)
    return positive, negative


def validate(data, exe):
    require(len(data) == SIZE and hashlib.sha256(data).hexdigest() == FIXTURE_SHA,
            'coordinate-word fixture extent/hash differs')
    require(data[:64] == header() and hashlib.sha256(exe).hexdigest() == producer.flyers.base.EXE_SHA,
            'coordinate-word header/original differs')
    for at, raw in producer.WINDOWS.items():
        require(exe[0x770 + at:0x770 + at + len(raw)] == raw, 'original word integration/writeback window differs')
    for index, case in enumerate(producer.CASES):
        row = RECORD.unpack_from(data, 64 + index * RECORD.size)
        require(row[:10] == (index, case['kind'], case['profile'], case['x'], case['y'],
                            case['vx'], case['vy'], 165, 90, 421), 'coordinate-word input coverage/order differs')
        require(row[16:] == (0x12345678, 11, 1), 'coordinate-word RNG/actor-byte-3/animation expectation differs')
        require(row[12:14] == (case['vx'], case['vy']), 'zero-edge native velocities changed')
    positive, negative = wrapping_indices(data)
    require(len(positive) == len(negative) == 120 and not set(positive) & set(negative),
            'positive/negative word-boundary coverage differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=ROOT / 'tests/fixtures/monster_coordinate_word_wrap_original.bin')
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--extract', nargs=2, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--producer-file', type=Path, default=ROOT / 'tools/capture_original_monster_word_wrap.py')
    parser.add_argument('--helper-file', type=Path, default=ROOT / 'tools/capture_original_flyer_contacts.py')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--replay-exe', type=Path)
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()
    if args.extract:
        require(args.output is not None and not args.output.exists(), 'word extraction needs a fresh output')
        first, second = [capture_bytes(directory, args.producer_file, args.helper_file) for directory in args.extract]
        require(first == second, 'independent full native word writebacks differ')
        args.output.write_bytes(first)
        fingerprint = 0xCBF29CE484222325
        for byte in first:
            fingerprint = ((fingerprint ^ byte) * 0x100000001B3) & ((1 << 64) - 1)
        print(f'monster_word_wrap_extraction=ok cases=768 bytes={len(first)} sha256={hashlib.sha256(first).hexdigest()} fnv={fingerprint:016x} independent_runs=2')
        return 0
    data, exe = args.fixture.read_bytes(), (ROOT / 'LEZAC.EXE').read_bytes()
    validate(data, exe)
    if args.archive:
        path = ROOT / 'docs/recovery/evidence/monster_word_wrap_20261004/native-captures.tar.gz'
        require(path.stat().st_size == 195144 and hashlib.sha256(path.read_bytes()).hexdigest() == ARCHIVE_SHA,
                'retained word archive hash differs')
        with tempfile.TemporaryDirectory(prefix='lezac-word-archive-') as directory:
            temporary = Path(directory)
            with tarfile.open(path, 'r:gz') as archive:
                members = archive.getmembers()
                names = [member.name for member in members]
                require(len(members) == len(set(names)) == 29 and sum(member.size for member in members) < 8 * 1024 * 1024,
                        'retained word archive member extent differs')
                for member in members:
                    require(member.isfile() and member.size >= 0, 'retained word archive contains a non-file')
                    target = retained_file(temporary, member.name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    content = archive.extractfile(member).read()
                    require(len(content) == member.size, 'retained word member truncated')
                    target.write_bytes(content)
            manifest = strict_json((temporary / 'manifest.json').read_text())
            require(set(manifest) == set(names) - {'manifest.json'}, 'retained word manifest scope differs')
            for name, item in manifest.items():
                content = retained_file(temporary, name).read_bytes()
                require(len(content) == item['bytes'] and hashlib.sha256(content).hexdigest() == item['sha256'],
                        'retained word member bytes differ')
            for suffix in ('a', 'b'):
                require(capture_bytes(temporary / suffix, temporary / 'tools/capture_original_monster_word_wrap.py',
                        temporary / 'tools/capture_original_flyer_contacts.py') == data,
                        'retained native words do not reproduce fixture')
            negative = strict_json((temporary / 'negative.json').read_text())
            positive = strict_json((temporary / 'positive.json').read_text())
            overflow, underflow = wrapping_indices(data)
            expected = sorted(overflow + underflow)
            require(negative['returncode'] == 1 and negative['mismatch_count'] == 240 and negative['mismatches'] == expected and
                    negative['stderr'].strip() == 'fatal: monster production coordinate-word differs at cases ' + ','.join(map(str, expected)) and
                    positive['returncode'] == 0 and 'cases=768 production_updates=768' in positive['stdout'] and
                    negative['audio'] == positive['audio'] == 'dummy', 'retained word negative/positive diagnostic differs')
        print('monster_word_wrap_retained_archive=ok captures=2 cases_each=768 members=29 byte_verified=1 negative_diagnostic_preserved=1')
    elif args.capture:
        require(capture_bytes(args.capture, args.producer_file, args.helper_file) == data,
                'full native word writeback does not reproduce fixture')
        print('monster_word_wrap_native_capture=ok cases=768 kinds=1..8 positive_wrap=120 negative_wrap=120 fixture_byte_match=1 hooks_restored=1 child_closed=1 audio=dummy')
    elif args.self_test:
        for index in range(len(data)):
            changed = bytearray(data)
            changed[index] ^= 1
            try:
                validate(bytes(changed), exe)
            except ValueError:
                continue
            raise AssertionError(f'accepted word fixture mutation {index}')
        for changed, original in ((data[:-1], exe), (data + b'\0', exe), (data, exe[:-1])):
            try:
                validate(changed, original)
            except ValueError:
                continue
            raise AssertionError('accepted malformed word fixture/original')
        print('monster_word_wrap_fixture_selftest=ok byte_mutations=24640 truncated=1 trailing=1 original_mutation=1')
    elif args.replay_exe:
        env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        command = [str(args.replay_exe.resolve()), '--debug-monster-coordinate-word-wrap']
        positive = subprocess.run([*command, str(args.fixture.resolve())], env=env, cwd=ROOT, capture_output=True, text=True, timeout=30)
        require(positive.returncode == 0 and 'monster_coordinate_word_wrap=ok cases=768 production_updates=768' in positive.stdout,
                'positive coordinate-word production replay failed')
        mutations = [data[:-1], data + b'\0']
        for at in (0, 8, 12, 16, 48, 64, 66, 67, 68, 70, 72, 78, 80, 90, 4096, SIZE - 1):
            changed = bytearray(data)
            changed[at] ^= 1
            mutations.append(bytes(changed))
        with tempfile.TemporaryDirectory(prefix='lezac-word-guard-') as directory:
            for index, changed in enumerate(mutations):
                path = Path(directory) / f'mutation-{index}.bin'
                path.write_bytes(changed)
                result = subprocess.run([*command, str(path)], env=env, cwd=ROOT, capture_output=True, text=True, timeout=10)
                require(result.returncode != 0 and 'monster coordinate-word fixture bytes changed' in result.stderr and
                        'monster_coordinate_word_wrap=ok' not in result.stdout, f'production accepted malformed word fixture {index}')
        print('monster_word_wrap_replay_guard=ok positive=1 rejected=18 audio=dummy')
    else:
        print('monster_word_wrap_fixture=ok cases=768 bytes=24640 kinds=1..8 profiles=6 positive_wrap=120 negative_wrap=120 original_exit=0x777f')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
