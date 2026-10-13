"""Compare production collapse geometry with executed original word-plane writes."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile

from source_guardrails import function_ranges, mask_cpp, source_files

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/gameplay/collapse_seed_geometry_original.bin.gz'
META = ROOT / 'tests/gameplay/collapse_seed_geometry_original.json'
META_SHA = 'ae20124be0e1489ca0acb04985339805de2f7da63678709bdb3f72f8d003d881'
CONTRACT = (
    'auto geometry = lezac::gameplay::seedCollapseWordGroupPhysical(level_.width, start,',
    'record.startOffsetBytes = geometry.firstOffsetBytes;',
    'record.endOffsetBytes = geometry.lastOffsetBytes;',
    'record.affectedBytes = static_cast<uint8_t>((geometry.cells.size() * 2) & 0xff);',
    'record.count = static_cast<int>(geometry.cells.size());',
    'if (!preserveCollapseGlyphs) markDamagedTile(x, y);',
)


def compact(text):
    return re.sub(r'\s+', '', mask_cpp(text))


def check_source(text):
    first, last = function_ranges(text, ['queuePhysicalTileDamage'])['queuePhysicalTileDamage']
    body = compact('\n'.join(text.splitlines()[first - 1:last]))
    for statement in CONTRACT:
        if body.count(compact(statement)) != 1:
            raise ValueError('production seeder geometry consumer differs')
    cap = compact('if (collapseQueue_.size() >= kCollapseCapacity) return;')
    if cap not in body or body.index(cap) > body.index(compact(CONTRACT[0])):
        raise ValueError('production seeder capacity gate differs')
    if 'pushNeighbor(' in body or 'std::vector<size_t>stack' in body:
        raise ValueError('production seeder still uses a flood fill')


def rejects(check, value):
    try:
        check(value)
    except (ValueError, RuntimeError):
        return
    raise ValueError('geometry checker accepted a mutation')


def metadata():
    raw = META.read_bytes()
    if hashlib.sha256(raw).hexdigest() != META_SHA:
        raise ValueError('original geometry metadata differs')
    data = json.loads(raw)
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    if (data['cases'] != 1124 or data['groups'] != dict(synthetic=40, boundary=4, shipped_initial=540, shipped_controlled_clear=540)
            or data['four_neighbor_differences'] != dict(synthetic=12, shipped_controlled_clear=156)
            or data['original_calls_stubbed'] or data['original_instructions_patched']
            or not data['original_return_boundaries_verified'] or data['compiled_cpp_comparison']
            or data['natural_gameplay'] or data['changed_map_natural_reachability_verified']
            or data['complete_seeder_record_comparison'] or data['whole_game_complete']
            or hashlib.sha256(original).hexdigest() != data['original_exe_sha256']
            or hashlib.sha256((ROOT / 'LIVELS.SCH').read_bytes()).hexdigest() != data['livels_sha256']
            or hashlib.sha256((ROOT / 'tools/capture_original_collapse_seed_geometry.py').read_bytes()).hexdigest() != data['generator_sha256']
            or hashlib.sha256((ROOT / 'tools/scan_livels_debris_sites.py').read_bytes()).hexdigest() != data['decoder_sha256']
            or hashlib.sha256(FIXTURE.read_bytes()).hexdigest() != data['fixture_sha256']
            or hashlib.sha256(original[0x770 + data['instruction_start']:0x770 + data['instruction_end']]).hexdigest() != data['instruction_sha256']):
        raise ValueError('original geometry provenance differs')
    return data


def unpack(data, incoming=None, expected=None):
    ih, oh = hashlib.sha256(), hashlib.sha256()
    with gzip.open(FIXTURE, 'rb') as fixture:
        if fixture.read(12) != b'LZSF0001' + struct.pack('<I', data['cases']):
            raise ValueError('original geometry fixture header differs')
        if incoming:
            incoming.write(b'LZSG0001' + struct.pack('<I', data['cases']))
        for _ in range(data['cases']):
            lengths = fixture.read(8)
            if len(lengths) != 8:
                raise ValueError('truncated original geometry fixture')
            size, result_size = struct.unpack('<II', lengths)
            if not (8 <= size <= 65542 and 9 <= result_size <= 65543):
                raise ValueError('original geometry record size differs')
            request, result = fixture.read(size), fixture.read(result_size)
            if len(request) != size or len(result) != result_size:
                raise ValueError('truncated original geometry records')
            width, cells, seed = struct.unpack_from('<HHH', request)
            if width == 0 or width > 300 or seed >= cells or size != 6 + 2 * cells or result_size != 7 + 2 * cells:
                raise ValueError('original geometry record layout differs')
            ih.update(request)
            oh.update(result)
            if incoming:
                incoming.write(request)
                expected.write(result)
        if fixture.read(1) or ih.hexdigest() != data['input_sha256'] or oh.hexdigest() != data['output_sha256']:
            raise ValueError('original geometry fixture digest differs')


def compare(paths):
    actual, expected = paths
    with actual.open('rb') as left, expected.open('rb') as right:
        while True:
            a, b = left.read(65536), right.read(65536)
            if a != b:
                raise ValueError('compiled production geometry differs')
            if not a:
                return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--self-check', action='store_true')
    mode.add_argument('--oracle-only', action='store_true')
    parser.add_argument('--four-neighbor-exe', type=Path)
    parser.add_argument('--eight-neighbor-exe', type=Path)
    args = parser.parse_args()
    data = metadata()
    source = '\n'.join(item.text for item in source_files(ROOT, 'app', 'runtime'))
    check_source(source)
    if args.self_check:
        for statement in CONTRACT:
            if source.count(statement) != 1:
                raise ValueError('production geometry source mutation is not unique')
            rejects(check_source, source.replace(statement, '// ' + statement))
        print('collapse_seed_contract=ok source_mutants=6 compiled_cpp=0 natural_gameplay=0')
        return
    if args.oracle_only:
        unpack(data)
        print('collapse_seed_oracle=ok cases=1124 shipped_initial=540 controlled_clear=540 flood_differences=168 compiled_cpp=0 natural_gameplay=0')
        return
    if not args.four_neighbor_exe or not args.eight_neighbor_exe:
        raise ValueError('compiled flood negative controls are required')
    with tempfile.TemporaryDirectory(prefix='lezac-collapse-seed-') as directory:
        directory = Path(directory)
        incoming, expected = directory / 'input.bin', directory / 'expected.bin'
        with incoming.open('wb') as input_file, expected.open('wb') as expected_file:
            unpack(data, input_file, expected_file)
        for name, executable in (('production', args.exe), ('four', args.four_neighbor_exe), ('eight', args.eight_neighbor_exe)):
            actual = directory / (name + '.bin')
            result = subprocess.run([str(executable.resolve()), str(incoming), str(actual)], capture_output=True,
                                    text=True, timeout=60, env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'))
            if result.returncode or result.stderr or result.stdout.strip() != 'collapse_seed_probe=ok cases=1124':
                raise RuntimeError('compiled geometry probe failed: ' + result.stdout + result.stderr)
            if name == 'production':
                compare((actual, expected))
                with actual.open('r+b') as output:
                    before = output.read(1)
                    output.seek(0)
                    output.write(bytes((before[0] ^ 1,)))
                rejects(compare, (actual, expected))
            else:
                rejects(compare, (actual, expected))
    print('collapse_seed_geometry=ok cases=1124 compiled_flood_mutants=2 output_mutants=1 natural_gameplay=0 full_seeder_claim=0')


if __name__ == '__main__':
    main()
