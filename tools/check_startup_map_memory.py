"""Check complete map views from the real App against observed original RAM."""
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
FIXTURE = ROOT / 'tests/fixtures/startup_map_original'
BINARY_SHA = '599d8944cdb5a926ffb414c0af6b25e319a8ee72b320f9e896b517507ed383cc'
METADATA_SHA = '849380da4752768f717c0843f81fd87246fec8077298e41963e33c5d9c0adeba'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(metadata, packed):
    require(sha(metadata) == METADATA_SHA and sha(packed) == BINARY_SHA, 'original startup fixture checksums')
    value = json.loads(metadata)
    require(value['format'] == 'lezac-startup-map-observation-v1', 'startup fixture version')
    require(value['natural_original_startup_observed'] is True and value['memory_writes'] == 0 and
            value['instruction_patches'] == 0, 'original observation provenance')
    require(all(value[name] is False for name in ('gameplay_state_seeded', 'clock_rng_or_heap_seeded',
                'frame_aligned', 'natural_reload_history_proven', 'whole_game_complete')), 'original observation scope')
    exe = (ROOT / 'LEZAC.EXE').read_bytes()
    levels = (ROOT / 'LIVELS.SCH').read_bytes()
    require(sha(exe) == value['original_exe_sha256'] and sha(levels) == value['levels_sha256'], 'original asset checksums')
    require(struct.unpack_from('<HH', levels) == (60, 33), 'original initial map dimensions')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(12 + 4 * 1048576 + 1)
    require(len(raw) == 12 + 4 * 1048576 and raw[:12] == b'LZSM0001' + struct.pack('<I', 4), 'RAM fixture framing')
    samples = value['samples']
    require([sample['name'] for sample in samples] == ['menu-first', 'level1-intro',
            'level1-running-first', 'level1-running-second'], 'original observation identities')
    header = struct.unpack_from('<14H', exe)
    windows = []
    for index, sample in enumerate(samples):
        ram = raw[12 + index * 1048576:12 + (index + 1) * 1048576]
        require(sha(ram) == sample['raw_ram_sha256'], 'original RAM checksum')
        cs, ds = sample['code_segment'], sample['data_segment']
        require(ds == cs + 0xaa2 and ram[(cs - 16) * 16:(cs - 16) * 16 + 2] == b'\xcd\x20', 'original code/PSP bases')
        image = bytearray(exe[header[4] * 16:])
        for relocation in range(header[3]):
            offset, segment = struct.unpack_from('<HH', exe, header[12] + 4 * relocation)
            at = segment * 16 + offset
            struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + cs) & 65535)
        require(ram[cs * 16:cs * 16 + 0xaa20] == image[:0xaa20], 'unchanged original code bytes')
        data = ram[ds * 16:ds * 16 + 65536]
        pointers = {name: struct.unpack_from('<HH', data, offset) for name, offset in
            [('heap_start', 0x1ad6), ('heap_top', 0x1ada), ('free_list', 0x1ae2), ('heap_error', 0x1aea),
             ('sound', 0x79c0), ('draw_buffer', 0x7f70), ('sprites', 0xc1e4), ('backdrop', 0xc498),
             ('raw_objects', 0x661a), ('raw_words', 0x6616), ('objects', 0xc1e0), ('words', 0x6612)]}
        require(all(list(pointer) == sample['pointers'][name] for name, pointer in pointers.items()), 'observed pointer metadata')
        physical = lambda name: pointers[name][0] + pointers[name][1] * 16
        require(pointers['heap_error'] == (0xa9, cs + 0x920), 'original allocator callback')
        at = physical('heap_start')
        for name, size in [('sound', 792), ('draw_buffer', 57000), ('sprites', 21300), ('backdrop', 60000)]:
            require(physical(name) == at, 'original persistent allocation order')
            at += (size + 7) & ~7
        if index == 0:
            require(pointers['raw_objects'] == pointers['raw_words'] == pointers['objects'] == pointers['words'] == (0, 0),
                    'original menu must not allocate map planes')
            require(physical('heap_top') == physical('free_list') == at and not any(ram[at:at + 131072]),
                    'original initial map carry-in')
            require(not any(ram[physical('backdrop'):physical('backdrop') + 60000]), 'original menu input buffer')
        else:
            require(physical('objects') == at + 8 and physical('words') == at + 2008,
                    'original initial map allocation positions')
            require(struct.unpack_from('<H', data, 0x78ba)[0] == 1980, 'original initial map cell count')
            objects, words = physical('objects'), physical('words')
            window = ram[objects:objects + 65536] + ram[words:words + 65536]
            require(len(window) == 131072, 'original complete map views')
            windows.append(window)
    require(len(windows) == 3 and windows[0] == windows[1] == windows[2], 'original map views changed during observation')
    return windows


def compare(expected, actual):
    require(len(actual) == 131072, 'compiled map view size')
    for original in expected:
        if original != actual:
            differences = [(i, a, b) for i, (a, b) in enumerate(zip(original, actual)) if a != b]
            raise RuntimeError('compiled map view differs: count=' + str(len(differences)) + ' first=' + repr(differences[:12]))


def self_check(metadata, packed, windows):
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
    for at in (0, 1996, 1998, 65536 + 3960, 131071):
        damaged = bytearray(windows[0])
        damaged[at] ^= 1
        try:
            compare(windows, damaged)
        except RuntimeError:
            count += 1
        else:
            raise RuntimeError('damaged compiled map view accepted')
    require(count == 11, 'startup-map corruption control count')
    return count


def replay(exe, out, windows):
    require(not out.exists(), 'startup map output already exists')
    out.mkdir(parents=True)
    env = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1',
               LEZAC_LOAD_ORIGINAL_ASSETS='1', LEZAC_LOAD_JSON_ASSETS='0')
    results = []
    for name, clocks in [('fixed-a', ['0', '0']), ('fixed-b', ['4128', '12352']), ('natural', [])]:
        target = out / name
        command = [str(exe.resolve()), '--debug-startup-map-memory', str(target.resolve()), *clocks]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=60)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        require(result.returncode == 0, 'full App startup failed: ' + result.stderr.decode(errors='replace'))
        require(b'startup_map_memory=ok menu_allocated=0 intro_bytes=131072 first_present_bytes=131072' in result.stdout,
                'full App allocation boundary report')
        for boundary in ('intro', 'first-present'):
            actual = (target / ('map-' + boundary + '.bin')).read_bytes()
            compare(windows, actual)
            results.append(dict(case=name, boundary=boundary, bytes=len(actual), sha256=sha(actual), differences=0))
    report = dict(passed=True, results=results, original_samples=3, compiled_boundaries=6,
                  compiled_view_bytes=786432, original_byte_comparisons=2359296, masks=0,
                  full_app_startup_executed=True, full_app_memory_state_compared=False,
                  diagnostic_settled_startup=True, natural_keyboard_route=False,
                  natural_reload_history_proven=False, whole_game_complete=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('startup_map_original=ok original_samples=3 cpp_boundaries=6 compared_bytes=786432 masks=0 production_app=1 whole_game_claim=0')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    require(not sys.flags.optimize, 'optimized Python is unsupported')
    metadata, packed = FIXTURE.with_suffix('.json').read_bytes(), FIXTURE.with_suffix('.bin.gz').read_bytes()
    windows = load(metadata, packed)
    if args.self_check:
        print('startup_map_checker=ok corruption_controls=' + str(self_check(metadata, packed, windows)))
    elif args.exe:
        require(args.out is not None, '--out is required with --exe')
        replay(args.exe, args.out, windows)
    else:
        print('startup_map_fixture=ok ram_images=4 original_samples=3 menu_unallocated=1 original_code=unchanged')


if __name__ == '__main__':
    main()
