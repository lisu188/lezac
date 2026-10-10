"""Compare full original out-of-map seed states with the input-only production App."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from check_collapse_contacts_original import contact_ranges
from check_original_debris_update import compact

ROOT = Path(__file__).resolve().parents[1]
INITIAL, STATE, COUNT = 157806, 157796, 12
PINS = {
    'outside_map_seeding_original.bin.gz': '5e38a8ecfea7daec191122570be9404b72ba3340a9573e5f1b73bb9edc758ae3',
    'outside_map_seeding_original.json': 'f40c01875d15349388125212d5157d672cc8eb4daa819709dccf96ba8513bb98',
    'outside_map_seeding_events.json.gz': '0931f1e6a82709820364c0e6abbe24cf40051e89a0a5a77dbc29757176299d93',
}
PHYSICAL = (
    'const uint16_t start = static_cast<uint16_t>(static_cast<uint16_t>(cell * 2u) >> 1);',
    'const uint16_t word = mapPlaneMemory_.readWord(start, level_.tiles, level_.wordLayer);',
    'uint8_t lookup = mapPlaneMemory_.readObject(start, level_.tiles, level_.wordLayer);',
    'mapPlaneMemory_.writeWord(start, flaggedWord, level_.tiles, level_.wordLayer);',
    'auto geometry = lezac::gameplay::seedCollapseWordGroupPhysical(level_.width, start,',
    'return mapPlaneMemory_.readWord(physicalCell, level_.tiles, level_.wordLayer);',
    'mapPlaneMemory_.writeWord(physicalCell, flaggedWord, level_.tiles, level_.wordLayer);',
)
CALLERS = (
    'queuePhysicalTileDamage(cell, 0, 0, true, &seededClass);',
    'queuePhysicalTileDamage(contact.cell, 0, 1, true);',
    'queuePhysicalTileDamage(static_cast<uint16_t>(cell), x, y, true);',
    'queuePhysicalTileDamage(static_cast<uint16_t>(above));',
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_contract(source):
    names = ('queueTileDamage', 'queuePhysicalTileDamage', 'updateDebrisRecords')
    ranges = contact_ranges(source, names)
    assert set(ranges) == set(names)
    bodies = {name: compact('\n'.join(source.splitlines()[first - 1:last])) for name, (first, last) in ranges.items()}
    physical = bodies['queuePhysicalTileDamage']
    for token in PHYSICAL:
        assert physical.count(compact(token)) == 1
    assert 'level_.wordLayer.size()' not in physical
    assert compact('ty >= level_.height') in bodies['queueTileDamage']
    assert compact('start >= level_.wordLayer.size()') in bodies['queueTileDamage']
    assert 'above>=0' not in bodies['updateDebrisRecords']
    whole = compact(source)
    for token in CALLERS:
        assert whole.count(compact(token)) == (2 if token == CALLERS[-1] else 1)


def fixture():
    files = {name: (ROOT / 'tests/gameplay' / name).read_bytes() for name in PINS}
    assert all(sha(files[name]) == pin for name, pin in PINS.items())
    report = json.loads(files['outside_map_seeding_original.json'])
    assert report['passed'] and report['boundaries'] == COUNT
    assert sha((ROOT / 'tools/capture_original_outside_map_seeding.py').read_bytes()) == report['producer_sha256']
    assert sha((ROOT / 'tools/capture_original_collapse_map.py').read_bytes()) == report['base_producer_sha256']
    assert sha((ROOT / 'LEZAC.EXE').read_bytes()) == report['original_exe_sha256']
    for name, pin in report['dependencies'].items():
        assert sha((ROOT / 'tools' / (name + '.py')).read_bytes()) == pin
    assert (report['observer_neutrality_memory_bytes'], report['observer_neutrality_registers']) == (1048576, 14)
    assert not any(report[key] for key in ('original_instructions_patched', 'original_calls_stubbed',
        'hardware_io_permitted', 'actual_app_executed', 'actual_app_parity_proven', 'natural_route', 'whole_game_complete'))
    raw = gzip.decompress(files['outside_map_seeding_original.bin.gz'])
    assert sha(raw) == report['raw_sha256'] and len(raw) == 16 + COUNT * (INITIAL + STATE)
    assert struct.unpack_from('<8sII', raw) == (b'LZOS0001', COUNT, INITIAL + STATE)
    events = json.loads(gzip.decompress(files['outside_map_seeding_events.json.gz']))
    assert len(events) == 311 and {event[0] for event in events} == set(range(COUNT))
    inputs, states, reads, writes = [], [], 0, 0
    expected_counts = ((1, 0), (1, 0), (0, 2), (1, 1), (0, 2), (1, 1),
                       (0, 2), (0, 1), (0, 1), (2, 0), (0, 1), (1, 1))
    for index, scene in enumerate(report['scenes']):
        at = 16 + index * (INITIAL + STATE)
        initial, state = raw[at:at + INITIAL], raw[at + INITIAL:at + INITIAL + STATE]
        assert sha(initial) == scene['initial_sha256'] and sha(state) == scene['state_sha256']
        assert initial[:4] == b'\x00\x01\x00\x00'
        assert initial[22:2002] == initial[26734:28714] and initial[2002:5962] == initial[92270:96230]
        memory = bytearray(initial[26734:])
        for case, pc, address, size, write, value in events:
            if case != index:
                continue
            offset = address - 0x40000
            assert 0 <= offset <= len(memory) - size and size in (1, 2) and 0x10000 <= pc < 0x1aa20
            if write:
                memory[offset:offset + size] = value.to_bytes(size, 'little')
                writes += 1
            else:
                assert int.from_bytes(memory[offset:offset + size], 'little') == value
                reads += 1
        assert memory == state[26724:]
        assert state[12:1992] == state[26724:28704] and state[1992:5952] == state[92260:96220]
        assert struct.unpack_from('<HH', state, 4) == expected_counts[index]
        assert scene['visits'].get('0x1370e', 0) == (0 if index == 7 else 1)
        inputs.append(initial)
        states.append(state)
    assert (reads, writes) == (268, 43)
    source_contract((ROOT / 'src/app/app.cpp').read_text(encoding='utf-8'))
    return struct.pack('<8sII', b'LZCM0001', COUNT, INITIAL) + b''.join(inputs), \
        struct.pack('<8sII', b'LZCN0001', COUNT, STATE) + b''.join(states)


def compare(actual, expected):
    assert len(actual) == len(expected), 'physical seed output extent differs'
    if actual != expected:
        offset = next(index for index, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1])
        raise AssertionError('physical seed mismatch scene=' + str((offset - 16) // STATE)
            + ' state_byte=' + str((offset - 16) % STATE))


def self_check(expected):
    mutants = []
    for offset in (0, 8, 12, 16, 16 + 4, 16 + 6, 16 + 1992, 16 + 5952, 16 + 21374,
                   16 + 25139, 16 + 26724, 16 + 92260, len(expected) - 1):
        raw = bytearray(expected)
        raw[offset] ^= 1
        mutants.append(bytes(raw))
    mutants += [expected[:-1], expected + b'\0']
    for raw in mutants:
        try:
            compare(raw, expected)
        except AssertionError:
            pass
        else:
            raise AssertionError('accepted corrupt physical seed stream')
    source = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
    for token in PHYSICAL + CALLERS:
        try:
            source_contract(source.replace(token, '', 1))
        except (AssertionError, ValueError, KeyError):
            pass
        else:
            raise AssertionError('accepted physical seed source mutant')
    print(f'collapse_physical_seed_checker=ok output_rejected={len(mutants)} source_rejected=11 masks=0')


def run(exe, out, incoming, expected):
    out.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    work = Path(tempfile.mkdtemp(prefix='lezac-physical-seed-case-'))
    input_path, actual_path = work / 'input.bin', work / 'actual.bin'
    input_path.write_bytes(incoming)
    pin = sha(exe.read_bytes())
    report = dict(passed=False, executable=str(exe), executable_sha256=pin, raw_work=str(work),
        fixture_sha256=PINS['outside_map_seeding_original.bin.gz'], scenes=COUNT,
        compared_bytes=COUNT * STATE, masks=0, production_app=True, seeded=True, natural_route=False, whole_game_complete=False)
    try:
        result = subprocess.run([str(exe.resolve()), '--debug-original-collapse-map', str(input_path), str(actual_path)],
            cwd=ROOT, capture_output=True, timeout=180,
            env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1'))
        (evidence / 'stdout.txt').write_bytes(result.stdout)
        (evidence / 'stderr.txt').write_bytes(result.stderr)
        report['exit_code'] = result.returncode
        assert result.returncode == 0 and not result.stderr
        marker = b'collapse_map_app=ok scenes=12 boundaries=12 compared_bytes=1893552 map_plane_bytes=131072 masks=0 production_app=1 seeded=1 natural_route=0 whole_game_claim=0'
        assert result.stdout.splitlines() == [marker]
        actual = actual_path.read_bytes()
        compare(actual, expected)
        assert sha(exe.read_bytes()) == pin
        report.update(passed=True, actual_sha256=sha(actual), expected_sha256=sha(expected))
    finally:
        (evidence / 'input.bin.gz').write_bytes(gzip.compress(incoming, mtime=0))
        if actual_path.exists():
            (evidence / 'actual.bin.gz').write_bytes(gzip.compress(actual_path.read_bytes(), mtime=0))
        (evidence / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('collapse_physical_seed_original=ok scenes=12 compared_bytes=1893552 masks=0 production_app=1 natural_route=0 whole_game_claim=0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    incoming, expected = fixture()
    if args.self_check:
        self_check(expected)
    elif args.exe:
        assert args.out is not None
        run(args.exe, args.out, incoming, expected)
    else:
        print('collapse_physical_seed_fixture=ok scenes=12 reads=268 writes=43 masks=0 production_app=0 whole_game_claim=0')
