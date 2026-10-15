"""Check original raw-cell debris capture and input-only production App output."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from check_outside_map_seeding import source_contract

ROOT = Path(__file__).resolve().parents[1]
INITIAL, STATE, COUNT = 157806, 157796, 2
PINS = {
    'wrapped_debris_original.bin.gz': '38715d6456dc4c0cb923ab3615b7bacd18229b159b906965712fb28b99d6825a',
    'wrapped_debris_original.json': '7f5cb0f5d488ec220dc3563a918b292cafd9e8a0cc956853c2c001806eea552c',
    'wrapped_debris_events.json.gz': 'd755697f023398127c8c47b6c0f12847d9a0242e1ddd4545aec3d4047a54f6bf',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture():
    files = {name: (ROOT / 'tests/gameplay' / name).read_bytes() for name in PINS}
    if any(sha(files[name]) != pin for name, pin in PINS.items()):
        raise ValueError('wrapped debris fixture fingerprint differs')
    report = json.loads(files['wrapped_debris_original.json'])
    assert report['passed'] and report['schema'] == 'lezac.wrapped-debris-seeding.v1'
    assert report['boundaries'] == COUNT and report['unicorn_version'] == '2.1.4'
    assert (report['observer_neutrality_memory_bytes'], report['observer_neutrality_registers']) == (1048576, 14)
    assert report['all_execution_silent'] is True
    for key in ('original_instructions_patched', 'original_calls_stubbed', 'hardware_io_permitted',
                'actual_app_executed', 'actual_app_parity_proven', 'natural_route',
                'whole_game_complete', 'original_fidelity_claim'):
        assert report[key] is False
    assert sha((ROOT / 'LEZAC.EXE').read_bytes()) == report['original_exe_sha256']
    for path, key in (('capture_original_wrapped_debris.py', 'producer_sha256'),
                      ('capture_original_outside_map_seeding.py', 'parent_producer_sha256'),
                      ('capture_original_collapse_map.py', 'base_producer_sha256')):
        assert sha((ROOT / 'tools' / path).read_bytes()) == report[key]
    for name, pin in report['dependencies'].items():
        assert sha((ROOT / 'tools' / (name + '.py')).read_bytes()) == pin
    packed = files['wrapped_debris_original.bin.gz']
    raw = gzip.decompress(packed)
    assert sha(packed) == report['fixture_sha256'] and sha(raw) == report['raw_sha256']
    assert struct.unpack_from('<8sII', raw) == (b'LZOS0001', COUNT, INITIAL + STATE)
    assert len(raw) == 16 + COUNT * (INITIAL + STATE)
    packed_events = files['wrapped_debris_events.json.gz']
    assert sha(packed_events) == report['events_sha256']
    events = json.loads(gzip.decompress(packed_events))
    assert len(events) == 24 and {event[0] for event in events} == {0, 1}
    inputs, states, reads, writes, glyph_reads = [], [], 0, 0, []
    for index, scene in enumerate(report['scenes']):
        at = 16 + index * (INITIAL + STATE)
        initial, state = raw[at:at + INITIAL], raw[at + INITIAL:at + INITIAL + STATE]
        assert sha(initial) == scene['initial_sha256'] and sha(state) == scene['state_sha256']
        assert initial[:4] == bytes([0, 1, 0, 0])
        assert (scene['raw_cell'], scene['target'], scene['target_word']) == (65516, 32748, 0x4101)
        assert scene['raw_glyph'] == (39, 56)[index]
        memory = bytearray(initial[26734:])
        assert memory[65516] == scene['raw_glyph'] and memory[32748] == 97
        for event in events:
            case, pc, address, size, write, value = event
            if case != index:
                continue
            assert 0x10000 <= pc < 0x1aa20 and size in (1, 2) and write in (0, 1)
            offset = address - 0x40000
            assert 0 <= offset <= len(memory) - size
            if write:
                memory[offset:offset + size] = value.to_bytes(size, 'little')
                writes += 1
            else:
                assert int.from_bytes(memory[offset:offset + size], 'little') == value
                reads += 1
                if pc == 0x137b8:
                    assert event[2:] == [0x40000 + 65516, 1, 0, scene['raw_glyph']]
                    glyph_reads.append(event)
        assert memory == state[26724:]
        assert initial[22:2002] == initial[26734:28714] and initial[2002:5962] == initial[92270:96230]
        assert state[12:1992] == state[26724:28704] and state[1992:5952] == state[92260:96220]
        assert struct.unpack_from('<HH', state, 4) == ((1, 0), (2, 0))[index]
        record = 5952 + index * 11
        assert struct.unpack_from('<H', state, record)[0] == 65516 and state[record + 9] == scene['raw_glyph']
        assert any(item['case'] == index and item['cell'] == 65516 for item in report['raw_seed_records'])
        inputs.append(initial)
        states.append(state)
    assert (reads, writes) == (16, 8) and glyph_reads == report['raw_glyph_reads']
    source_contract((ROOT / 'src/app/app.cpp').read_text(encoding='utf-8'))
    return struct.pack('<8sII', b'LZCM0001', COUNT, INITIAL) + b''.join(inputs), \
        struct.pack('<8sII', b'LZCN0001', COUNT, STATE) + b''.join(states)


def compare(actual, expected):
    if len(actual) != len(expected):
        raise ValueError('wrapped debris output extent differs')
    if actual != expected:
        offset = next(index for index, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1])
        raise ValueError('wrapped debris mismatch scene=' + str((offset - 16) // STATE)
                         + ' state_byte=' + str((offset - 16) % STATE))


def self_check(expected):
    offsets = [0, 8, 12]
    for scene in range(COUNT):
        offsets += [16 + scene * STATE + offset for offset in
                    (0, 4, 6, 12, 1992, 5953 + scene * 11, 5961 + scene * 11,
                     21374, 25139, 26724, 92260, STATE - 1)]
    mutants = []
    for offset in offsets:
        mutant = bytearray(expected)
        mutant[offset] ^= 1
        mutants.append(bytes(mutant))
    mutants += [expected[:-1], expected + b'\0']
    for mutant in mutants:
        try:
            compare(mutant, expected)
        except ValueError:
            pass
        else:
            raise ValueError('accepted corrupted wrapped debris output')
    print(f'wrapped_debris_checker=ok output_rejected={len(mutants)} source_contract=1 masks=0')


def run(exe, out, incoming, expected):
    out.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    input_path, actual_path = evidence / 'input.bin', evidence / 'actual.bin'
    input_path.write_bytes(incoming)
    digest = sha(exe.read_bytes())
    report = dict(passed=False, executable=str(exe), executable_sha256=digest,
        fixture_sha256=PINS['wrapped_debris_original.bin.gz'], scenes=COUNT,
        compared_bytes=COUNT * STATE, masks=0, production_app=True, seeded=True,
        natural_route=False, whole_game_complete=False, all_execution_silent=True)
    try:
        result = subprocess.run([str(exe.resolve()), '--debug-original-collapse-map',
            str(input_path.resolve()), str(actual_path.resolve())], cwd=ROOT, capture_output=True,
            timeout=180, env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'))
        (evidence / 'stdout.txt').write_bytes(result.stdout)
        (evidence / 'stderr.txt').write_bytes(result.stderr)
        report['exit_code'] = result.returncode
        if result.returncode != 0 or result.stderr:
            raise ValueError('wrapped debris App execution failed')
        marker = b'collapse_map_app=ok scenes=2 boundaries=2 compared_bytes=315592 map_plane_bytes=131072 masks=0 production_app=1 seeded=1 natural_route=0 whole_game_claim=0'
        if result.stdout.splitlines() != [marker]:
            raise ValueError('wrapped debris App protocol differs')
        actual = actual_path.read_bytes()
        compare(actual, expected)
        if sha(exe.read_bytes()) != digest:
            raise ValueError('wrapped debris executable changed during comparison')
        report.update(passed=True, actual_sha256=sha(actual), expected_sha256=sha(expected))
    except BaseException as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        (evidence / 'expected.bin.gz').write_bytes(gzip.compress(expected, mtime=0))
        for path in (input_path, actual_path):
            if path.exists():
                raw = path.read_bytes()
                replacement = path.with_name(path.name + '.gz')
                replacement.write_bytes(gzip.compress(raw, mtime=0))
                if gzip.decompress(replacement.read_bytes()) == raw:
                    path.unlink()
        (evidence / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        if sum(path.stat().st_size for path in evidence.rglob('*') if path.is_file()) >= 8388608:
            raise ValueError('wrapped debris evidence exceeds its reserve')
    print('wrapped_debris_original=ok scenes=2 compared_bytes=315592 masks=0 production_app=1 natural_route=0 whole_game_claim=0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if sys.flags.optimize:
        parser.error('checked Python execution is required')
    incoming, expected = fixture()
    if args.self_check:
        self_check(expected)
    elif args.exe:
        if args.out is None:
            parser.error('--out is required with --exe')
        run(args.exe, args.out, incoming, expected)
    else:
        print('wrapped_debris_fixture=ok scenes=2 reads=16 writes=8 masks=0 production_app=0 whole_game_claim=0')
