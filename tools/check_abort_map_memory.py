"""Compare actual-App abort/restart map views with unmodified original RAM."""
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

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/abort_map_original'
BINARY_SHA = 'e8ca58fc0b53ebaa8056920ad1aff006b9708d14887bbca36e0bea004d941049'
METADATA_SHA = 'a92efe4b44d64059733ef7cda269965dc0eebc461ca5156c96056de9dc1c4c89'
NAMES = ['menu-initial', 'level1-intro-1', 'level1-running-1', 'game-over-after-escape-1',
         'menu-after-abort-1', 'level1-intro-2', 'level1-running-2', 'game-over-after-escape-2',
         'menu-after-abort-2', 'level1-intro-3', 'level1-running-3']
OUTPUTS = ['intro', 'first-present', 'game-over-1', 'menu-1', 'intro-2', 'running-2',
           'game-over-2', 'menu-2', 'intro-3', 'running-3']


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(metadata, packed):
    require(sha(metadata) == METADATA_SHA and sha(packed) == BINARY_SHA, 'abort fixture checksums')
    value = json.loads(metadata)
    require(value['format'] == 'lezac-abort-map-observation-v1' and value['binary_sha256'] == BINARY_SHA,
            'abort fixture version or binary identity')
    report = value['capture']
    require(report['passed'] and report['status'] == 'observed' and report['process_memory_opened_read_only'] and
            report['process_memory_writes'] == 0 and report['injected_instructions'] == 0 and
            not report['gameplay_state_seeded'] and not report['clock_rng_or_heap_seeded'] and
            report['canonical_assets_unchanged'], 'original observation provenance')
    require(not value['frame_aligned'] and not value['whole_game_complete'], 'original observation scope')
    exe = (ROOT / 'LEZAC.EXE').read_bytes()
    require(sha(exe) == report['executable_sha256'] ==
            '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec', 'original executable identity')
    require(sha((ROOT / 'LIVELS.SCH').read_bytes()) == value['levels_sha256'], 'original levels identity')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(12 + 11 * 1048576 + 1)
    require(len(raw) == 12 + 11 * 1048576 and raw[:12] == b'LZAM0001' + struct.pack('<I', 11),
            'abort RAM fixture framing')
    require([s['name'] for s in report['samples']] == NAMES, 'original boundary identities')
    header = struct.unpack_from('<14H', exe)
    windows = []
    for index, sample in enumerate(report['samples']):
        ram = raw[12 + index * 1048576:12 + (index + 1) * 1048576]
        require(sha(ram) == sample['raw_ram_sha256'], 'original RAM checksum')
        cs, ds = sample['code_segment'], sample['data_segment']
        require(ds == cs + 0xaa2 and ram[(cs - 16) * 16:(cs - 16) * 16 + 2] == b'\xcd\x20',
                'original code and PSP bases')
        image = bytearray(exe[header[4] * 16:])
        for relocation in range(header[3]):
            offset, segment = struct.unpack_from('<HH', exe, header[12] + 4 * relocation)
            at = segment * 16 + offset
            struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + cs) & 65535)
        require(ram[cs * 16:cs * 16 + 43552] == image[:43552], 'unchanged original code bytes')
        data = ram[ds * 16:ds * 16 + 65536]
        pointers = {name: struct.unpack_from('<HH', data, offset) for name, offset in [
            ('heap_start', 0x1ad6), ('heap_top', 0x1ada), ('heap_limit', 0x1ade), ('free_list', 0x1ae2),
            ('heap_error', 0x1aea), ('sound', 0x79c0), ('draw_buffer', 0x7f70), ('sprites', 0xc1e4),
            ('backdrop', 0xc498), ('raw_objects', 0x661a), ('raw_words', 0x6616),
            ('objects', 0xc1e0), ('words', 0x6612)]}
        require(all(list(p) == sample['pointers'][n] for n, p in pointers.items()), 'original pointer metadata')
        physical = lambda name: pointers[name][0] + 16 * pointers[name][1]
        at = physical('heap_start')
        for name, size in [('sound', 792), ('draw_buffer', 57000), ('sprites', 21300), ('backdrop', 60000)]:
            require(physical(name) == at, 'original persistent allocation order')
            at += (size + 7) & ~7
        if index == 0:
            require(all(pointers[n] == (0, 0) for n in ('raw_objects', 'raw_words', 'objects', 'words')) and
                    physical('heap_top') == physical('free_list') == at and not any(ram[at:at + 131072]),
                    'initial menu allocated maps or nonzero carry-in')
        else:
            require(physical('objects') == at + 8 and physical('words') == at + 2008 and
                    struct.unpack_from('<H', data, 0x78ba)[0] == 1980 and data[0x79b7] == 1,
                    'original level-1 map allocation positions')
            objects, words = physical('objects'), physical('words')
            windows.append(ram[objects:objects + 65536] + ram[words:words + 65536])
    require(len(windows) == 10 and windows[0] == windows[1] == windows[2] == windows[3] and
            all(w == windows[4] for w in windows[5:]) and windows[0] != windows[4],
            'original abort retention or second-start carry-in')
    return windows


def compare(expected, actual):
    require(len(expected) == len(actual) == 131072, 'compiled map view size')
    if expected != actual:
        differences = [(i, a, b) for i, (a, b) in enumerate(zip(expected, actual)) if a != b]
        raise RuntimeError('compiled map differs: count=' + str(len(differences)) + ' first=' + repr(differences[:16]))


def controls(metadata, packed, windows):
    count = 0
    for source in ('metadata', 'binary'):
        original = metadata if source == 'metadata' else packed
        for at in (0, len(original) // 2, len(original) - 1):
            damaged = bytearray(original)
            damaged[at] ^= 1
            try:
                load(damaged if source == 'metadata' else metadata, damaged if source == 'binary' else packed)
            except (RuntimeError, ValueError, OSError):
                count += 1
            else:
                raise RuntimeError('damaged original fixture accepted')
    for boundary, at in [(0, 0), (2, 1998), (3, 1971), (4, 1980), (6, 65536), (9, 131071)]:
        damaged = bytearray(windows[boundary])
        damaged[at] ^= 1
        try:
            compare(windows[boundary], damaged)
        except RuntimeError:
            count += 1
        else:
            raise RuntimeError('damaged compiled view accepted')
    try:
        compare(windows[4], windows[0])
    except RuntimeError:
        count += 1
    else:
        raise RuntimeError('fresh-start map incorrectly accepted for second start')
    require(count == 13, 'abort corruption control count')
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    require(not sys.flags.optimize, 'optimized Python unsupported')
    metadata, packed = FIXTURE.with_suffix('.json').read_bytes(), FIXTURE.with_suffix('.bin.gz').read_bytes()
    windows = load(metadata, packed)
    if args.self_check:
        print('abort_map_checker=ok corruption_controls=' + str(controls(metadata, packed, windows)))
    elif args.exe:
        require(args.out is not None and not args.out.exists(), 'new --out required')
        args.out.mkdir(parents=True)
        target = args.out / 'app'
        env = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1',
                   LEZAC_LOAD_ORIGINAL_ASSETS='1', LEZAC_LOAD_JSON_ASSETS='0')
        command = [str(args.exe.resolve()), '--debug-abort-map-memory', str(target.resolve())]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=60)
        (args.out / 'app.stdout').write_bytes(result.stdout)
        (args.out / 'app.stderr').write_bytes(result.stderr)
        require(result.returncode == 0, 'abort App failed: ' + result.stderr.decode(errors='replace'))
        require(b'abort_map_memory=ok cycles=3 aborts=2 views=10 bytes=1310720 audio=dummy' in result.stdout,
                'abort App boundary report')
        results = []
        for name, expected in zip(OUTPUTS, windows):
            actual = (target / ('map-' + name + '.bin')).read_bytes()
            compare(expected, actual)
            results.append(dict(boundary=name, bytes=len(actual), sha256=sha(actual), differences=0))
        report = dict(passed=True, results=results, original_ram_images=11, cpp_boundaries=10,
            compared_bytes=1310720, masks=0, full_app_executed=True, full_ram_state_compared=False,
            diagnostic_settled_boundaries=True, natural_keyboard_route=False, frame_aligned=False,
            whole_game_complete=False)
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('abort_map_original=ok original_images=11 cpp_boundaries=10 compared_bytes=1310720 masks=0 production_app=1 whole_game_claim=0')
    else:
        print('abort_map_fixture=ok ram_images=11 loaded_views=10 code=unchanged aborts=2 new_games=3')


if __name__ == '__main__':
    main()
