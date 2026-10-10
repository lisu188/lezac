"""Compare full original removal states with the input-only production App diagnostic."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from check_collapse_map import source_contract as map_contract
from check_original_collapse_actors import contract as actor_contract
from check_original_debris_update import compact

ROOT = Path(__file__).resolve().parents[1]
INITIAL, STATE, COUNT = 157806, 157796, 7
META_PIN = 'b04e4133cccb8090a6d067e35f1adecdfebca768b2462fc15b98c7c7a7629075'
FIXTURE_PIN = '9795cf7341d51e7a074303a52a42bc1379876c68d01718f31c6806f23983284e'
REMOVAL = (
    'collapseQueue_.erase(collapseQueue_.begin() + static_cast<std::ptrdiff_t>(slot));',
    'lezac::gameplay::visitCollapseRemovalWords(static_cast<uint16_t>(first * 2u),',
    'fracture ? rectangle.topRight : static_cast<uint16_t>(rectangle.topRight * 2u),',
    'static_cast<uint16_t>(last * 2u), static_cast<uint16_t>(width), [&](uint16_t cell)',
    'if (word == record.flaggedWord)',
    'setMapWord(cell, static_cast<uint16_t>(word & ~kDamagedWordBit));',
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_contract(source):
    map_contract(source)
    actor_contract(source)
    begin = source.index('            if (fracture || record.restTicks == 95) {')
    end = source.index('    void updateFlashes()', begin)
    body = compact(source[begin:end])
    for statement in REMOVAL:
        assert body.count(compact(statement)) == 1, statement
    assert body.index(compact(REMOVAL[0])) < body.index(compact(REMOVAL[1]))
    assert 'cells()' not in body


def fixture():
    metadata = (ROOT / 'tests/gameplay/collapse_removal_original.json').read_bytes()
    packed = (ROOT / 'tests/gameplay/collapse_removal_original.bin.gz').read_bytes()
    assert sha(metadata) == META_PIN and sha(packed) == FIXTURE_PIN
    report = json.loads(metadata)
    assert sha((ROOT / 'tools/capture_original_collapse_removal.py').read_bytes()) == report['producer_sha256']
    assert sha((ROOT / 'tools/capture_original_collapse_map.py').read_bytes()) == report['base_producer_sha256']
    for name, pin in report['dependencies'].items():
        assert sha((ROOT / 'tools' / (name + '.py')).read_bytes()) == pin
    assert sha((ROOT / 'LEZAC.EXE').read_bytes()) == report['original_exe_sha256']
    assert report['passed'] and report['boundaries'] == COUNT
    assert (report['observer_neutrality_memory_bytes'], report['observer_neutrality_registers']) == (1048576, 14)
    assert not any(report[key] for key in ('original_instructions_patched', 'original_calls_stubbed',
        'hardware_io_permitted', 'actual_app_executed', 'actual_app_parity_proven', 'natural_route', 'whole_game_complete'))
    raw = gzip.decompress(packed)
    assert sha(raw) == report['raw_sha256'] and len(raw) == 16 + COUNT * (INITIAL + STATE)
    assert struct.unpack_from('<8sII', raw) == (b'LZRM0001', COUNT, INITIAL + STATE)
    incoming, states, reads, writes = [], [], 0, 0
    for index, scene in enumerate(report['scenes']):
        at = 16 + index * (INITIAL + STATE)
        initial, state = raw[at:at + INITIAL], raw[at + INITIAL:at + INITIAL + STATE]
        assert sha(initial) == scene['initial_sha256'] and sha(state) == scene['state_sha256']
        assert initial[:4] == b'\x00\x01\x00\x00'
        assert initial[22:2002] == initial[26734:28714]
        assert initial[2002:5962] == initial[92270:96230]
        memory = bytearray(initial[26734:])
        for event in scene['events']:
            offset, size = int(event['address'], 16) - 0x40000, event['size']
            assert size in (1, 2) and 0 <= offset <= len(memory) - size
            if event['write']:
                memory[offset:offset + size] = event['value'].to_bytes(size, 'little')
                writes += 1
            else:
                assert int.from_bytes(memory[offset:offset + size], 'little') == event['value']
                reads += 1
        assert memory == state[26724:]
        assert state[12:1992] == state[26724:28704] and state[1992:5952] == state[92260:96220]
        incoming.append(initial)
        states.append(state)
    assert len(incoming) == COUNT and (reads, writes) == (372, 39)
    source_contract((ROOT / 'src/app/app.cpp').read_text(encoding='utf-8'))
    return report, struct.pack('<8sII', b'LZCM0001', COUNT, INITIAL) + b''.join(incoming), \
        struct.pack('<8sII', b'LZCN0001', COUNT, STATE) + b''.join(states)


def compare(actual, expected):
    assert len(actual) == len(expected), 'removal output extent differs'
    assert actual[:16] == expected[:16], 'removal output header differs'
    if actual != expected:
        offset = next(index for index, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1])
        raise AssertionError('removal output differs: scene=' + str((offset - 16) // STATE)
            + ' state_byte=' + str((offset - 16) % STATE))


def self_check(expected):
    rejected = 0
    for offset in (0, 4, 8, 12, 1992, 5952, 21374, 25139, 26714, 26721, 26724, 92260, STATE - 1):
        changed = bytearray(expected)
        changed[16 + STATE + offset] ^= 1
        try:
            compare(changed, expected)
        except AssertionError:
            rejected += 1
        else:
            raise AssertionError('accepted corrupted removal state')
    for changed in (b'badmagic' + expected[8:], expected[:8] + struct.pack('<I', COUNT + 1) + expected[12:],
                    expected[:-1], expected + b'\x00'):
        try:
            compare(changed, expected)
        except AssertionError:
            rejected += 1
        else:
            raise AssertionError('accepted malformed removal output')
    source = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
    source_rejected = 0
    for statement in REMOVAL:
        assert source.count(statement) == 1
        changed = source.replace(statement, '', 1)
        try:
            source_contract(changed)
        except (AssertionError, ValueError, KeyError):
            source_rejected += 1
        else:
            raise AssertionError('accepted removal source mutant')
    assert rejected == 17 and source_rejected == len(REMOVAL)
    print(f'collapse_removal_checker=ok rejected={rejected} source_rejected={source_rejected} masks=0')


def run(exe, out, incoming, expected):
    out.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    work = Path(tempfile.mkdtemp(prefix='lezac-collapse-removal-case-'))
    input_path, actual_path = work / 'input.bin', work / 'actual.bin'
    input_path.write_bytes(incoming)
    pin = sha(exe.read_bytes())
    report = dict(passed=False, executable=str(exe), executable_sha256=pin, raw_work=str(work),
        fixture_sha256=FIXTURE_PIN, scenes=COUNT, compared_bytes=COUNT * STATE, masks=0,
        production_app=True, seeded=True, natural_route=False, whole_game_complete=False)
    try:
        process = subprocess.run([str(exe.resolve()), '--debug-original-collapse-map', str(input_path), str(actual_path)],
            cwd=ROOT, capture_output=True, timeout=180,
            env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1'))
        (evidence / 'stdout.txt').write_bytes(process.stdout)
        (evidence / 'stderr.txt').write_bytes(process.stderr)
        report['exit_code'] = process.returncode
        assert process.returncode == 0 and not process.stderr
        marker = f'collapse_map_app=ok scenes=7 boundaries=7 compared_bytes={COUNT * STATE} map_plane_bytes=131072 masks=0 production_app=1 seeded=1 natural_route=0 whole_game_claim=0\n'.encode()
        assert process.stdout.splitlines() == [marker.rstrip(b'\n')]
        actual = actual_path.read_bytes()
        compare(actual, expected)
        assert sha(exe.read_bytes()) == pin
        report.update(passed=True, actual_sha256=sha(actual), expected_sha256=sha(expected))
    finally:
        (evidence / 'input.bin.gz').write_bytes(gzip.compress(incoming, mtime=0))
        if actual_path.exists():
            (evidence / 'actual.bin.gz').write_bytes(gzip.compress(actual_path.read_bytes(), mtime=0))
        (evidence / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'collapse_removal_original=ok scenes=7 compared_bytes={COUNT * STATE} masks=0 production_app=1 natural_route=0 whole_game_claim=0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report, incoming, expected = fixture()
    if args.self_check:
        self_check(expected)
    elif args.exe:
        assert args.out is not None
        run(args.exe, args.out, incoming, expected)
    else:
        print('collapse_removal_fixture=ok scenes=7 reads=372 writes=39 masks=0 production_app=0 whole_game_claim=0')
