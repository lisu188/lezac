"""Extract and validate bounded shipped-profile native-constructor evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tarfile
import tempfile

import capture_original_shipped_monster_profiles as producer

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/fixtures/shipped_monster_profiles_original.bin'
HEADER = b'LZSPROF1' + struct.pack('<4H', 1, 45, 64, 15) + bytes.fromhex(producer.base.EXE_SHA) + bytes(16)
STATE_SIZE = 112
CASE_SIZE = 18 + 30 + 2 * STATE_SIZE + 64 * 2 * STATE_SIZE
SIZE = 64 + 368 + 1980 + 45 * CASE_SIZE
SHA256 = 'b1c71fb54958a9cac974c30813ba55c157ff50cdb5bfa33688a97ab0cbfe79ea'
ARCHIVE = ROOT / 'docs/recovery/evidence/shipped_monster_profiles_20261005/native-captures.tar.gz'
ARCHIVE_SHA256 = '76d4ef3eafb84dd3cce9af20c317f4aee5eca546c9774ca57d805725a38694fa'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def state(row):
    result = bytearray(struct.pack('<HI', row['frame'], row['rng']))
    for key, size in (('actor', 38), ('visual', 8), ('spawner', 30),
                      ('p1', 8), ('p2', 8), ('flags', 2)):
        raw = bytes.fromhex(row[key])
        require(len(raw) == size, 'native state extent differs: ' + key)
        result += raw
    require(len(row['registers']) == 6, 'native register extent differs')
    result += struct.pack('<6H', *row['registers'])
    require(len(result) == STATE_SIZE, 'state size differs')
    return result


def extract_files(files):
    report = json.loads(files['capture.json'])
    require(report['schema'] == producer.SCHEMA and report['cases'] == 45 and report['ticks'] == 64,
            'native profile coverage differs')
    require(report['audio_driver'] == 'dummy' and report['native_constructor'] and not report['natural_route'],
            'native provenance differs')
    restoration = json.loads(files['restoration.json'])
    require(restoration['hooks_restored'] and restoration['scratch_restored'], 'native hooks were not restored')
    for name, digest in report['files'].items():
        require(Path(name).name == name, 'invalid capture file path')
        require(hashlib.sha256(files[name]).hexdigest() == digest, 'native capture hash differs: ' + name)
    rows = json.loads(files['observations.json'])
    require(len(rows) == 45, 'native case count differs')
    payload = bytearray(HEADER + bytes.fromhex(report['sprite_descriptors']) + bytes.fromhex(report['terrain']))
    require(bytes.fromhex(report['terrain']) == producer.terrain(), 'controlled terrain differs')
    for index, row in enumerate(rows):
        level, slot, offset, shipped = producer.profiles()[index // 3]
        require((row['index'], row['profile'], row['level'], row['slot'], row['file_offset'], row['seed'], row['shipped']) ==
                (index, index // 3, level, slot, offset, producer.SEEDS[index % 3], shipped.hex()), 'profile inventory differs')
        require(row['near_start'] == (index % 3 == 0), 'initial target phase differs')
        require(row['before']['count'] == 0 and row['constructor']['count'] == 1, 'constructor allocation differs')
        require(row['before']['rng'] == row['seed'], 'constructor RNG seed differs')
        require(len(row['ticks']) == 64, 'continuous tick count differs')
        payload += struct.pack('<HHBBIIHBB', index, index // 3, level, slot, offset, row['seed'],
                               row['before']['frame'], row['near_start'], 0)
        payload += shipped + state(row['before']) + state(row['constructor'])
        previous = row['constructor']
        for tick, pair in enumerate(row['ticks']):
            pre, post = pair['pre'], pair['post']
            require(pre['count'] == post['count'] == 1, 'actor lifecycle escaped bounded case')
            require(pre['frame'] == post['frame'] == ((row['before']['frame'] + tick) & 65535), 'tick sequence differs')
            require(pre['actor'] == previous['actor'] and pre['visual'] == previous['visual'] and pre['rng'] == previous['rng'],
                    'actor or RNG was reset between continuous native updates')
            payload += state(pre) + state(post)
            previous = post
    require(len(payload) == SIZE, 'fixture extent differs')
    return bytes(payload)


def extract(capture):
    files = {}
    for path in capture.iterdir():
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16 * 1024 * 1024,
                'invalid native capture member')
        files[path.name] = path.read_bytes()
    return extract_files(files)


def archive_check():
    require(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == ARCHIVE_SHA256, 'native archive fingerprint differs')
    members = {}
    with tarfile.open(ARCHIVE, 'r:gz') as archive:
        for member in archive.getmembers():
            require(member.isfile() and member.size <= 16 * 1024 * 1024 and member.name not in members and
                    not member.name.startswith('/') and '..' not in Path(member.name).parts, 'invalid native archive member')
            members[member.name] = archive.extractfile(member).read()
    golden = validate(FIXTURE.read_bytes())
    for name in ('original-v3', 'original-v4'):
        files = {key.split('/', 1)[1]: value for key, value in members.items() if key.startswith(name + '/')}
        require(extract_files(files) == golden, 'independent native capture differs from pinned fixture')
    for name in ('original-v1', 'original-v2'):
        require(name + '/failure.json' in members and name + '/observations.json' in members,
                'incomplete native capture was not retained')
    print('shipped_monster_profile_archive=ok captures=2 constructors_each=45 updates_each=2880 failed_captures_preserved=2 byte_verified=1')


def validate(raw):
    require(len(raw) == SIZE, 'fixture size differs')
    require(hashlib.sha256(raw).hexdigest() == SHA256, 'fixture fingerprint differs')
    require(raw[:64] == HEADER, 'fixture header differs')
    return raw


def replay_guard(exe):
    raw = validate(FIXTURE.read_bytes())
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    command = [str(exe.resolve()), '--debug-shipped-monster-profiles']
    positive = subprocess.run(command + [str(FIXTURE)], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=120)
    require(positive.returncode == 0 and 'shipped_monster_profiles=ok' in positive.stdout, 'positive replay failed: ' + positive.stderr)
    cases = [('truncated', raw[:-1]), ('trailing', raw + b'\x00')]
    for index in (0, 8, 12, 48, 64, 432, 2412, 2430, 2460, 2572, 2684, 2750, SIZE // 2, SIZE - 1):
        changed = bytearray(raw)
        changed[index] ^= 1
        cases.append((str(index), changed))
    with tempfile.TemporaryDirectory(prefix='lezac-profile-guard-') as temp:
        for name, payload in cases:
            path = Path(temp) / (name + '.bin')
            path.write_bytes(payload)
            result = subprocess.run(command + [str(path)], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
            require(result.returncode != 0 and 'shipped profile fixture' in result.stderr and
                    'shipped_monster_profiles=ok' not in result.stdout, 'malformed replay accepted: ' + name)
    require(FIXTURE.read_bytes() == raw, 'source fixture changed during corruption guard')
    print(f'shipped_monster_profile_replay_guard=ok positive=1 rejected={len(cases)} audio=dummy')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()
    if args.archive:
        archive_check()
    elif args.capture:
        raw = extract(args.capture.resolve())
        if args.out:
            require(not args.out.exists(), 'new fixture output required')
            args.out.write_bytes(raw)
        else:
            require(raw == validate(FIXTURE.read_bytes()), 'fresh original capture differs from pinned fixture')
        print(json.dumps({'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                          'fnv1a64': f'{fnv(raw):016x}', 'profiles': 15, 'cases': 45, 'updates': 2880}, sort_keys=True))
    elif args.exe:
        replay_guard(args.exe)
    else:
        validate(FIXTURE.read_bytes())
        print(f'shipped_monster_profile_fixture=ok profiles=15 constructors=45 updates=2880 bytes={SIZE}')


def fnv(raw):
    value = 14695981039346656037
    for byte in raw:
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return value


if __name__ == '__main__':
    main()
