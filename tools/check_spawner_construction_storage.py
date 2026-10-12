"""Validate and replay salted original spawner-construction storage evidence."""
import argparse
import gzip
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/fixtures/spawner_construction_storage_original.bin.gz'
RAW_SHA = '0b1a2ed9cb58c87e981f587f82ff88e6eab1730103084308877dceddaa3e07df'
PACKED_SHA = '2c6ab90501a9dbb28d4b377789a9cca4d6b016c2669c1a8bef8e02fa8240d0da'
SUCCESS = ('spawner_construction_storage=ok cases=1620 successful=720 physical_storage_bytes=2551500 '
           'physical_spawner_bytes=437400 '
           'rng_and_roll_bytes=8100 sound_requests=0 legacy_adoptions=0 legacy_retirements=0 '
           'production_app=1 raw_spawner_bank=1 seeded=1 natural_route=0 whole_game_claim=0')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate():
    packed = FIXTURE.read_bytes()
    require(len(packed) == 110264 and hashlib.sha256(packed).hexdigest() == PACKED_SHA,
            'spawner construction compressed fixture differs')
    raw = gzip.decompress(packed)
    require(len(raw) == 6055944 and hashlib.sha256(raw).hexdigest() == RAW_SHA,
            'spawner construction raw fixture differs')
    require(raw[:16] == b'LZSC0001' + struct.pack('<II', 1620, 1867), 'spawner construction header differs')
    return raw


def replay(exe, raw):
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    command = [str(exe.resolve()), '--debug-spawner-construction-storage']
    with tempfile.TemporaryDirectory(prefix='lezac-spawner-construction-') as name:
        path = Path(name) / 'requests.bin'
        path.write_bytes(raw)
        positive = subprocess.run(command + [str(path)], cwd=ROOT, env=environment,
                                  capture_output=True, text=True, timeout=90)
        require(positive.returncode == 0 and positive.stdout.splitlines() == [SUCCESS],
                'spawner construction positive replay failed: ' + positive.stderr)
        print(positive.stdout, end='', flush=True)
        mutations = [('truncated', raw[:-1]), ('trailing', raw + b'\x00')]
        for offset in (0, 8, 16, 384, 426, 1581, len(raw) // 2, len(raw) - 1):
            changed = bytearray(raw)
            changed[offset] ^= 1
            mutations.append((str(offset), bytes(changed)))
        for label, payload in mutations:
            path.write_bytes(payload)
            result = subprocess.run(command + [str(path)], cwd=ROOT, env=environment,
                                    capture_output=True, text=True, timeout=30)
            require(result.returncode != 0 and 'spawner construction fixture' in result.stderr and
                    'spawner_construction_storage=ok' not in result.stdout,
                    'spawner construction malformed replay accepted: ' + label)
    require(validate() == raw, 'spawner construction source fixture changed')
    print('spawner_construction_replay_guard=ok positive=1 rejected=10 audio=dummy', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    raw = validate()
    if args.exe:
        replay(args.exe, raw)
    else:
        print('spawner_construction_fixture=ok cases=1620 bytes=6055944', flush=True)


if __name__ == '__main__':
    main()
