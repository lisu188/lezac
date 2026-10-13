"""Check the original collapse boundary fixture and actual input-only App output."""
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

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/gameplay'
PINS = {
    'collapse_map_original.bin.gz': 'c6b8b43d6d1cab56d81c97eb959ba0cf452e2509e1412fe9587d92f38fa45f6d',
    'collapse_map_original.json': '2d2d90fcdd45884b0d5eef1c5085b8405ebce8fba1427324e065b80035b9324f',
    'collapse_map_events.json.gz': '5356c3d83679becbd9581ae1493a6e91460ed2c3b4cc63d792c7ee6ab5bc7fe1',
}
STATE, INITIAL = 157796, 157806
REGIONS = (('rng', 0), ('counts', 4), ('fragment_counters', 8), ('tiles', 12),
    ('words', 1992), ('debris', 5952), ('collapse', 21374), ('actors', 25139),
    ('sound', 26714), ('history', 26721), ('object_plane', 26724), ('word_plane', 92260))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_contract(text):
    begin = text.index('    void updateCollapseRecords() {')
    end = text.index('    void updateFlashes() {', begin)
    body = text[begin:end]
    for required in (
        'mapPlaneMemory_.readWord(cell, level_.tiles, level_.wordLayer)',
        'mapPlaneMemory_.readObject(cell, level_.tiles, level_.wordLayer)',
        'mapPlaneMemory_.writeWord(cell, value, level_.tiles, level_.wordLayer)',
        'mapPlaneMemory_.writeObject(cell, value, level_.tiles, level_.wordLayer)',
        'lezac::gameplay::CollapseRectangle rectangle(',
        'rectangle.visit(delta, [&](uint16_t cell)',
        'rectangle.translate(delta);',
        'static_cast<uint16_t>(target * 2u) / 2',
        'right = rectangle.topRight % width',
    ):
        assert body.count(required) == 1, required
    order = ('setMapWord(target, word);', 'setMapWord(cell, 0);',
             'const uint8_t tile = mapTile(cell);', 'setMapTile(cell, 0);', 'setMapTile(target, tile);')
    positions = [body.index(token) for token in order]
    assert positions == sorted(positions)
    assert 'level_.wordLayer[' not in body and 'level_.tiles[' not in body
    assert 'std::reverse(source.begin()' not in body
    assert text.count('"--debug-original-collapse-map"') == 1
    assert 'true, false, false, true, false, true, true, false, true, true);' in text


def fixture():
    files = {name: (FIXTURES / name).read_bytes() for name in PINS}
    assert all(sha(files[name]) == pin for name, pin in PINS.items())
    metadata = json.loads(files['collapse_map_original.json'])
    assert sha((ROOT / 'tools/capture_original_collapse_map.py').read_bytes()) == metadata['producer_sha256']
    for name, pin in metadata['dependencies'].items():
        assert sha((ROOT / 'tools' / (name + '.py')).read_bytes()) == pin
    assert sha((ROOT / 'LEZAC.EXE').read_bytes()) == metadata['original_exe_sha256']
    assert metadata['observer_neutrality_memory_bytes'] == 1048576 and metadata['observer_neutrality_registers'] == 14
    for key in ('original_instructions_patched', 'original_calls_stubbed', 'hardware_io_permitted',
                'natural_route', 'natural_heap_initialization_proven', 'production_app_executed', 'whole_game_complete'):
        assert metadata[key] is False
    raw = gzip.decompress(files['collapse_map_original.bin.gz'])
    assert sha(raw) == metadata['raw_sha256']
    assert struct.unpack_from('<8sII', raw) == (b'LZCB0001', 19, 34)
    rows, offset = [], 16
    for record in metadata['records']:
        initial = raw[offset:offset + INITIAL]
        offset += INITIAL
        assert len(initial) == INITIAL and sha(initial) == record['initial_sha256']
        assert initial[:4] == bytes([record['layout'], record['steps'], 0, 0])
        incoming, planes = initial[4:4 + 26730], initial[4 + 26730:]
        assert incoming[18:1998] == planes[:1980]
        assert incoming[1998:5958] == planes[65536:69496]
        if record['layout']:
            assert planes[2000:65536] == planes[65536:129072]
        states = []
        for state_record in record['states']:
            state = raw[offset:offset + STATE]
            offset += STATE
            assert len(state) == STATE and sha(state) == state_record['sha256']
            assert state[12:1992] == state[26724:28704]
            assert state[1992:5952] == state[92260:96220]
            states.append(state)
        assert len(states) == record['steps']
        rows.append((record, initial, b''.join(states)))
    assert offset == len(raw) and len(rows) == 19 and sum(row[0]['steps'] for row in rows) == 34
    events = json.loads(gzip.decompress(files['collapse_map_events.json.gz']))
    assert len(events) == 621 and sum(event[5] for event in events) == 192
    # Replay every observed access against the full seeded live map aliases.
    for index, (record, initial, expected) in enumerate(rows):
        word_base = 65536 if record['layout'] == 0 else 2000
        memory = bytearray(word_base + 65536)
        memory[:65536] = initial[26734:26734 + 65536]
        memory[word_base:word_base + 65536] = initial[26734 + 65536:]
        for step in range(record['steps']):
            for scene, boundary, pc, address, size, write, value in events:
                if (scene, boundary) != (index, step):
                    continue
                location = address - 0x40000
                assert 0 <= location <= len(memory) - size
                if write:
                    memory[location:location + size] = value.to_bytes(size, 'little')
                else:
                    assert int.from_bytes(memory[location:location + size], 'little') == value
            state = expected[step * STATE:(step + 1) * STATE]
            assert memory[:65536] + memory[word_base:word_base + 65536] == state[26724:]
    source_contract((ROOT / 'src/app/app.cpp').read_text(encoding='utf-8'))
    return metadata, rows


def compare(actual, expected, boundaries):
    header = struct.pack('<8sII', b'LZCN0001', boundaries, STATE)
    assert len(actual) == len(header) + len(expected), 'App output length mismatch'
    assert actual[:16] == header, 'App output header mismatch'
    if actual[16:] != expected:
        offset = next(index for index, (a, b) in enumerate(zip(actual[16:], expected)) if a != b)
        step, cell = divmod(offset, STATE)
        region = next(name for name, start in reversed(REGIONS) if cell >= start)
        raise AssertionError(f'App mismatch boundary={step} state_byte={cell} region={region}')


def self_check(rows):
    _, _, expected = rows[0]
    good = struct.pack('<8sII', b'LZCN0001', 2, STATE) + expected
    compare(good, expected, 2)
    rejected = 0
    for offset in (0, 8, 12, *[16 + start for _, start in REGIONS], 16 + STATE + STATE - 1):
        mutant = bytearray(good)
        mutant[offset] ^= 1
        try:
            compare(mutant, expected, 2)
        except AssertionError:
            rejected += 1
        else:
            raise AssertionError('accepted corrupted output at ' + str(offset))
    for mutant in (good[:-1], good + b'\0'):
        try:
            compare(mutant, expected, 2)
        except AssertionError:
            rejected += 1
        else:
            raise AssertionError('accepted truncated/trailing output')
    text = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
    for token in ('rectangle.translate(delta);', 'setMapWord(target, word);', 'setMapTile(cell, 0);'):
        try:
            source_contract(text.replace(token, '// removed boundary behavior'))
        except (AssertionError, ValueError):
            rejected += 1
        else:
            raise AssertionError('accepted source mutant ' + token)
    print(f'collapse_map_checker=ok rejected={rejected} masks=0', flush=True)


def app(exe, out, metadata, rows):
    out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    report = dict(passed=False, executable=str(exe), executable_sha256=sha(exe.read_bytes()),
        fixture_sha256=metadata['fixture_sha256'], scenes=19, boundaries=34,
        compared_bytes=34 * STATE, masks=0, production_app=True, seeded=True,
        natural_route=False, whole_game_complete=False, cases=[])
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
    try:
        for index, (record, initial, expected) in enumerate(rows):
            # Each retained raw case is under 0.5MiB; the artifact bundle is compressed.
            work = Path(tempfile.mkdtemp(prefix='lezac-collapse-map-case-'))
            incoming = struct.pack('<8sII', b'LZCM0001', 1, INITIAL) + initial
            (work / 'input.bin').write_bytes(incoming)
            row = dict(name=record['name'], work=str(work), steps=record['steps'], passed=False,
                input_sha256=sha(incoming), expected_sha256=sha(expected))
            report['cases'].append(row)
            process = subprocess.run([str(exe), '--debug-original-collapse-map', str(work / 'input.bin'), str(work / 'output.bin')],
                cwd=ROOT, env=environment, capture_output=True, timeout=60)
            (out / (record['name'] + '-stdout.txt')).write_bytes(process.stdout)
            (out / (record['name'] + '-stderr.txt')).write_bytes(process.stderr)
            (out / (record['name'] + '-input.bin.gz')).write_bytes(gzip.compress(incoming, mtime=0))
            actual = (work / 'output.bin').read_bytes() if (work / 'output.bin').exists() else b''
            (out / (record['name'] + '-actual.bin.gz')).write_bytes(gzip.compress(actual, mtime=0))
            row.update(exit_code=process.returncode, actual_sha256=sha(actual))
            assert process.returncode == 0, process.stderr.decode(errors='replace')
            marker = (f'collapse_map_app=ok scenes=1 boundaries={record["steps"]} '
                f'compared_bytes={record["steps"] * STATE} map_plane_bytes=131072 masks=0 '
                'production_app=1 seeded=1 natural_route=0 whole_game_claim=0')
            assert marker in process.stdout.decode().splitlines(), 'missing exact App completion marker'
            compare(actual, expected, record['steps'])
            row['passed'] = True
        report['passed'] = True
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'collapse_map_original=ok scenes=19 boundaries=34 compared_bytes={34 * STATE} masks=0 production_app=1 natural_route=0 whole_game_claim=0')


if __name__ == '__main__':
    assert not sys.flags.optimize
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    metadata, rows = fixture()
    if args.self_check:
        self_check(rows)
    elif args.exe:
        assert args.out is not None
        app(args.exe.resolve(), args.out.resolve(), metadata, rows)
    else:
        print('collapse_map_fixture=ok scenes=19 boundaries=34 events=621 reads=429 writes=192 masks=0 production_app=0 natural_route=0 whole_game_claim=0')
