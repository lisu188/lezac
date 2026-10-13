"""Verify original map accesses and replay them through the production memory accessor."""
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
FIXTURE = ROOT / 'tests/gameplay/map_planes_original.bin.gz'
EXPECTED = ROOT / 'tests/gameplay/map_planes_expected.bin.gz'
META = ROOT / 'tests/gameplay/map_planes_original.json'
META_SHA = '39e9d2ef9cc2cf3c0c6a291303dfbaf7d8b6378cfb5fde5aeae9065d638dc81a'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def contract(source):
    required = (
        'return mapPlaneMemory_.readObject(index, level_.tiles, level_.wordLayer);',
        'mapPlaneMemory_.writeObject(index, value, level_.tiles, level_.wordLayer);',
        'return mapPlaneMemory_.readWord(index, level_.tiles, level_.wordLayer);',
        'mapPlaneMemory_.writeWord(index, value, level_.tiles, level_.wordLayer);',
        'const int dest = static_cast<uint16_t>(pos + delta);',
        'mapPlaneMemory_.restoreSeparatedPlanesForFixture();',
        'resetLevel(index, false);',
    )
    if any(source.count(text) != 1 for text in required):
        raise ValueError('production map-plane integration differs')
    if source.count('mapPlaneMemory_.beginLevel(level_.tiles, level_.wordLayer,') != 2:
        raise ValueError('map allocation lifecycle differs')
    return required


def metadata():
    raw = META.read_bytes()
    if META_SHA is None or sha(raw) != META_SHA:
        raise ValueError('original map-plane metadata differs')
    data = json.loads(raw)
    pins = {ROOT / 'LEZAC.EXE': data['original_exe_sha256'],
        ROOT / 'tools/capture_original_map_planes.py': data['generator_sha256'],
        ROOT / 'tests/gameplay/physics_dispatch_original.bin.gz': data['prior_fixture_sha256'],
        FIXTURE: data['fixture_sha256'], EXPECTED: data['expected_fixture_sha256']}
    pins.update({ROOT / 'tools' / (name + '.py'): pin for name, pin in data['dependency_sha256'].items()})
    if any(sha(path.read_bytes()) != pin for path, pin in pins.items()):
        raise ValueError('original map-plane provenance differs')
    if (not data['passed'] or data['scenes'] != 12 or data['updates_per_scene'] != 2 or data['boundaries'] != 24 or
        data['events'] != 168 or data['reads'] != 88 or data['writes'] != 80 or
        any(data[key] for key in ('original_instructions_patched', 'original_calls_stubbed', 'hardware_io_permitted',
            'natural_route', 'natural_heap_initialization_proven', 'production_app', 'actual_cpp_comparison', 'whole_game_complete')) or
        not data['seeded'] or data['observer_neutrality_memory_bytes'] != 1048576 or data['observer_neutrality_registers'] != 14):
        raise ValueError('original map-plane evidence scope differs')
    return data


def streams(data):
    request, expected = gzip.decompress(FIXTURE.read_bytes()), gzip.decompress(EXPECTED.read_bytes())
    if len(request) != data['input_bytes'] or sha(request) != data['input_sha256']:
        raise ValueError('original map-plane input differs')
    if len(expected) != data['expected_bytes'] or sha(expected) != data['expected_sha256']:
        raise ValueError('original map-plane expected state differs')
    if request[:12] != struct.pack('<8sI', b'LZMP0001', 12) or expected[:12] != struct.pack('<8sI', b'LZMR0001', 12):
        raise ValueError('original map-plane stream headers differ')
    left, right, reads, writes = 12, 12, 0, 0
    for index, row in enumerate(data['cases']):
        layout, width, height, events = struct.unpack_from('<IHHI', request, left)
        left += 12
        planes = request[left:left + 131072]
        left += 131072
        if (width, height, layout, events) != (60, 33, int(index >= 10), row['events']) or sha(planes) != row['input_planes_sha256']:
            raise ValueError('original map-plane scene input differs')
        if layout and planes[2000:65536] != planes[65536:65536 + 63536]:
            raise ValueError('shared plane input bytes disagree')
        count, = struct.unpack_from('<I', expected, right)
        right += 4
        read_values = struct.unpack_from('<' + 'H' * count, expected, right)
        right += 2 * count
        final = expected[right:right + 131072]
        right += 131072
        if count != row['reads'] or sha(final) != row['final_planes_sha256']:
            raise ValueError('original map-plane scene output differs')
        scene_reads = scene_writes = 0
        for _ in range(events):
            plane, write, offset, value = struct.unpack_from('<BBHH', request, left)
            left += 6
            if plane > 1 or write > 1 or (plane == 1 and offset % 2) or (not write and value != 0) or (plane == 0 and value > 255):
                raise ValueError('original map access differs or supplies expected read bytes')
            scene_writes += write
            scene_reads += not write
        if scene_reads != count or scene_writes != row['writes'] or len(read_values) != count:
            raise ValueError('original map access counts differ')
        reads += scene_reads
        writes += scene_writes
    if len(data['cases']) != 12 or left != len(request) or right != len(expected) or (reads, writes) != (88, 80):
        raise ValueError('original map-plane trailing data or totals differ')
    return request, expected


def compare(actual, expected):
    if actual != expected:
        offset = next((i for i, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]), min(len(actual), len(expected)))
        raise ValueError('compiled map-plane memory differs at byte ' + str(offset))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    data = metadata()
    source = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
    required = contract(source)
    request, expected = streams(data)
    if args.self_check:
        changes = [(text, '') for text in required]
        changes.append(('mapPlaneMemory_.beginLevel(level_.tiles, level_.wordLayer,', 'unusedBeginLevel('))
        for old, new in changes:
            try:
                contract(source.replace(old, new))
            except ValueError:
                continue
            raise ValueError('map-plane contract accepted a source mutation')
        for offset in (0, 12, len(expected) - 1):
            changed = bytearray(expected)
            changed[offset] ^= 1
            try:
                compare(changed, expected)
            except ValueError:
                continue
            raise ValueError('map-plane comparator accepted a mutation')
        print('map_plane_memory_checker=ok source_mutants=8 output_mutants=3 production_app=0')
        return
    if not args.exe:
        print('map_plane_memory_fixture=ok scenes=12 events=168 reads=88 writes=80 production_app=0 natural_route=0')
        return
    with tempfile.TemporaryDirectory(prefix='lezac-map-memory-') as directory:
        root = Path(directory)
        incoming, actual = root / 'input.bin', root / 'actual.bin'
        incoming.write_bytes(request)
        environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
        result = None
        try:
            result = subprocess.run([str(args.exe.resolve()), '--replay', str(incoming), str(actual)],
                capture_output=True, env=environment, timeout=30)
            if result.returncode or result.stderr or result.stdout.strip() != b'map_plane_memory_app=ok scenes=12 reads=88 writes=80 production_app=0':
                raise ValueError('compiled map-plane replay failed: ' + repr(result))
            compare(actual.read_bytes(), expected)
        except BaseException:
            retained = Path(tempfile.mkdtemp(prefix='lezac-map-memory-failure-'))
            for name, raw in (('input', request), ('expected', expected)):
                (retained / (name + '.bin.gz')).write_bytes(gzip.compress(raw, mtime=0))
            if actual.exists():
                (retained / 'actual.bin.gz').write_bytes(gzip.compress(actual.read_bytes(), mtime=0))
            if result is not None:
                (retained / 'stdout.log').write_bytes(result.stdout)
                (retained / 'stderr.log').write_bytes(result.stderr)
            (retained / 'scope.json').write_text(json.dumps(dict(passed=False,
                original_metadata_sha256=META_SHA, input_only=True, masks=0,
                production_accessor=True, production_app=False, whole_game_complete=False)) + '\n')
            print('failure_artifacts=' + str(retained.resolve()), file=sys.stderr)
            raise
    print('map_plane_memory_original=ok scenes=12 events=168 compared_bytes=1573100 masks=0 production_accessor=1 production_app=0 natural_route=0 whole_game_claim=0')


if __name__ == '__main__':
    main()
