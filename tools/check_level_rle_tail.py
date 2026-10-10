"""Compare compiled production decoders with the original-executable fixture."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/level_rle_tail_original.json.gz'
FIXTURE_SHA = '8a49090e26f0b3d8d55db6dfc2341b34cab29085e9241be4acd626214898f5cb'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(raw):
    require(sha(raw) == FIXTURE_SHA, 'original decoder fixture checksum')
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        decoded = stream.read(8388609)
    require(len(decoded) <= 8388608, 'original decoder fixture size')
    value = json.loads(decoded)
    require(value['format'] == 'lezac-level-rle-tail-v1' and value['unicorn_version'] == '2.1.4', 'fixture version')
    require(value['seeded_calls'] is True and value['natural_gameplay'] is False and
            value['whole_game_complete'] is False, 'fixture evidence scope')
    require(all(value[name] is False for name in
                ('original_instructions_patched', 'interrupt_or_io_stubs', 'memory_read_hooks')), 'fixture execution scope')
    require(value['decoder_file_offset'] == 0x8a40 and value['decoder_bytes'] == 0x111, 'original decoder range')
    for name, key in (('LEZAC.EXE', 'original_exe_sha256'), ('LIVELS.SCH', 'levels_sha256')):
        require(sha((ROOT / name).read_bytes()) == value[key], 'original asset checksum: ' + name)
    cases = value['cases']
    expected = ['level' + str(i) + '_' + plane for i in range(1, 8) for plane in ('objects', 'words')]
    expected += ['boundary_' + str(i) for i in (1, 15, 16, 17, 31, 32, 33)] + ['second_run_max_tail']
    require([case['name'] for case in cases] == expected, 'fixture case identities')
    for case in cases:
        require(0 < case['target'] <= 32768 and 0 < case['tail_bytes'] <= 16, 'fixture output bounds')
        require(len(bytes.fromhex(case['buffer_before_hex'])) == 60000 and
                len(bytes.fromhex(case['encoded_hex'])) <= 60000, 'fixture input bounds')
        require(len(bytes.fromhex(case['output_hex'])) == case['target'] + case['tail_bytes'], 'fixture tail extent')
        require(case['full_ram_and_register_observer_match'] is True, 'fixture observer neutrality')
        regs = case['registers']
        require(len(regs) == 14 and (regs['CS'], regs['IP'], regs['BP'], regs['SP']) ==
                (0x1000, 0xff00, 0xf000, 0x3f10), 'fixture return registers')
    return value


def input_bytes(value):
    result = bytearray(b'LZRT0001' + struct.pack('<I', len(value['cases'])))
    for case in value['cases']:
        encoded = bytes.fromhex(case['encoded_hex'])
        result += struct.pack('<II', case['target'], len(encoded))
        result += bytes.fromhex(case['buffer_before_hex']) + encoded
    return result


def compare(value, actual):
    require(actual[:12] == b'LZRO0001' + struct.pack('<I', len(value['cases'])), 'compiled decoder header')
    at, payload, tails = 12, 0, 0
    for case in value['cases']:
        require(at + 8 <= len(actual), 'truncated compiled decoder record')
        size, tail_size = struct.unpack_from('<II', actual, at)
        at += 8
        require((size, tail_size) == (case['target'], case['tail_bytes']), 'compiled tail extent: ' + case['name'])
        expected = bytes.fromhex(case['output_hex'])
        require(actual[at:at + len(expected)] == expected, 'compiled decoder bytes: ' + case['name'])
        at += len(expected)
        payload += size
        tails += tail_size
    require(at == len(actual), 'compiled decoder trailing bytes')
    return payload, tails


def self_check(raw, value):
    rejected = 0
    for at in (0, 9, len(raw) // 2, len(raw) - 1):
        damaged = bytearray(raw)
        damaged[at] ^= 1
        try:
            load(damaged)
        except (RuntimeError, ValueError, OSError):
            rejected += 1
        else:
            raise RuntimeError('damaged original fixture accepted')
    clean = bytearray(b'LZRO0001' + struct.pack('<I', len(value['cases'])))
    for case in value['cases']:
        clean += struct.pack('<II', case['target'], case['tail_bytes']) + bytes.fromhex(case['output_hex'])
    compare(value, clean)
    first = value['cases'][0]
    for at in (0, 12, 16, 20, 20 + first['target']):
        damaged = bytearray(clean)
        damaged[at] ^= 1
        try:
            compare(value, damaged)
        except RuntimeError:
            rejected += 1
        else:
            raise RuntimeError('damaged compiled decoder output accepted')
    require(rejected == 9, 'corruption-control count')
    return rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    require(not sys.flags.optimize, 'optimized Python is unsupported')
    raw = FIXTURE.read_bytes()
    value = load(raw)
    if args.self_check:
        print('level_rle_tail_checker=ok corruption_controls=' + str(self_check(raw, value)))
    elif args.exe:
        with tempfile.TemporaryDirectory(prefix='lezac-rle-tail-') as directory:
            source, target = Path(directory) / 'input.bin', Path(directory) / 'actual.bin'
            source.write_bytes(input_bytes(value))
            env = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
            result = subprocess.run([str(args.exe.resolve()), '--replay', str(source), str(target)],
                                    capture_output=True, timeout=60, env=env)
            require(result.returncode == 0, 'compiled decoder failed: ' + result.stderr.decode(errors='replace'))
            payload, tails = compare(value, target.read_bytes())
            print('level_rle_tail_original=ok cases=22 payload_bytes=' + str(payload) +
                  ' tail_bytes=' + str(tails) + ' masks=0 natural_gameplay=0 whole_game_claim=0')
    else:
        print('level_rle_tail_fixture=ok cases=22 original_code=unchanged seeded_calls=1')


if __name__ == '__main__':
    main()
