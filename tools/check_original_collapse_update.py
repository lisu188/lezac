"""Compare complete production collapse updates with executed-original outputs."""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from check_original_debris_update import compact
from source_guardrails import function_ranges, source_files

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/gameplay/collapse_update_original.bin.gz'
META = ROOT / 'tests/gameplay/collapse_update_original.json'
META_SHA = '1eee3a429a6b2fbfca3691b588846a4dab9c61c2b6f5102a1549c328bdfcf99e'
INITIALIZER_SHA = 'aaef4f5b7b8e4a213d7a9c11a2cc003cddd8026c89bd5cc0ee80006e945aefde'
CONTRACT = {'if (collapseUpdate) updateCollapseRecords();': 1,
            'level_.tiles = take(cells);': 1, 'randomSeed_ = le32(parameters, 6);': 1,
            'monsters_.clear();': 2,
            'destroyed_ = le16(parameters, 14);': 1,
            'nextCollapseFragmentWord_ = le16(parameters, 16);': 1,
            'appendWord(result, static_cast<uint16_t>(destroyed_));': 1,
            'appendWord(result, nextCollapseFragmentWord_);': 1}


def contract(source):
    first, last = function_ranges(source, ['debugOriginalDebrisUpdate'])['debugOriginalDebrisUpdate']
    body = compact('\n'.join(source.splitlines()[first - 1:last]))
    if any(body.count(compact(statement)) != count for statement, count in CONTRACT.items()):
        raise ValueError('complete collapse production routing differs')


def verify_initialization(data, original):
    if (data.get('schema') != 'lezac.original-collapse-update.v2'
            or data.get('record_table_initializers_executed') is not True
            or data.get('record_table_initialization_boundaries_verified') is not True
            or data.get('initialization_start') != 0x293D or data.get('initialization_end') != 0x2949
            or data.get('collapse_table_base') != 0x6620 or data.get('debris_table_base') != 0x209E
            or data.get('initialization_sha256') != INITIALIZER_SHA
            or data.get('entry_counts', {}).get('record_table_initializer') != 2395
            or hashlib.sha256(original[0x30AD:0x30B9]).hexdigest() != INITIALIZER_SHA):
        raise ValueError('collapse original record-table initialization differs')


def metadata():
    raw = META.read_bytes()
    if hashlib.sha256(raw).hexdigest() != META_SHA: raise ValueError('collapse metadata differs')
    data = json.loads(raw)
    paths = {ROOT / 'LEZAC.EXE': data['original_exe_sha256'], ROOT / 'LIVELS.SCH': data['livels_sha256'],
             ROOT / 'tools/capture_original_collapse_update.py': data['generator_sha256'], FIXTURE: data['fixture_sha256']}
    paths.update({ROOT / 'tools' / name: digest for name, digest in data['dependency_sha256'].items()})
    paths.update({ROOT / 'tests/fixtures' / name: digest for name, digest in data['native_fixture_sha256'].items()})
    for path, digest in paths.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('collapse provenance differs: ' + str(path.relative_to(ROOT)))
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    verify_initialization(data, original)
    if hashlib.sha256(original[0x770 + data['instruction_start']:0x770 + data['instruction_end']]).hexdigest() != data['instruction_sha256']:
        raise ValueError('collapse original instruction window differs')
    if (data['cases'] != 2395 or data['native_crosschecked_cases'] != 27 or data['executor'] != 'Unicorn 2.1.4'
            or data['original_calls_stubbed'] or data['original_instructions_patched']
            or not data['original_return_boundaries_verified'] or not data['word_segment_cache_initialized']
            or not data['complete_live_records_maps_rng'] or not data['destruction_fragment_counter_compared']
            or not data['actor_pool_controlled_empty'] or data['actor_records_compared'] or data['sound_state_compared']
            or data['natural_gameplay'] or data['compiled_cpp_comparison'] or data['whole_game_complete']):
        raise ValueError('collapse evidence scope differs')
    return data


def records(data):
    ih, oh = hashlib.sha256(), hashlib.sha256()
    with gzip.open(FIXTURE, 'rb') as fixture:
        if fixture.read(12) != b'LZCF0001' + struct.pack('<I', data['cases']):
            raise ValueError('collapse fixture header differs')
        for index in range(data['cases']):
            lengths = fixture.read(8)
            if len(lengths) != 8: raise ValueError('truncated collapse fixture')
            incoming_size, output_size = struct.unpack('<II', lengths)
            if not (18 <= incoming_size < 100000 and 12 <= output_size < 100000):
                raise ValueError('collapse fixture sizes differ')
            incoming, expected = fixture.read(incoming_size), fixture.read(output_size)
            if len(incoming) != incoming_size or len(expected) != output_size:
                raise ValueError('truncated collapse fixture records')
            width, height, tick, rng, fragments, collapses, destroyed, next_word = struct.unpack_from('<HHHIHHHH', incoming)
            after_fragments, after_collapses = struct.unpack_from('<HH', expected, 4)
            cells = width * height
            if (not 0 < width <= 300 or not 0 < height <= 200 or cells > 16384
                    or max(fragments, after_fragments) > 1401 or max(collapses, after_collapses) > 250
                    or incoming_size != 18 + 3 * cells + 11 * fragments + 15 * collapses
                    or output_size != 12 + 3 * cells + 11 * after_fragments + 15 * after_collapses):
                raise ValueError('collapse fixture layout differs')
            ih.update(incoming)
            oh.update(expected)
            yield incoming, expected
        if fixture.read(1) or ih.hexdigest() != data['input_sha256'] or oh.hexdigest() != data['output_sha256']:
            raise ValueError('collapse fixture digests differ')


def compare(actual, expected):
    left, right = actual.read_bytes(), expected.read_bytes()
    if left != right:
        first = next((i for i, pair in enumerate(zip(left, right)) if pair[0] != pair[1]), min(len(left), len(right)))
        raise ValueError(f'production collapse differs at byte {first}; actual={len(left)} expected={len(right)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--oracle-only', action='store_true')
    mode.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    data = metadata()
    source = '\n'.join(item.text for item in source_files(ROOT, 'app', 'runtime'))
    contract(source)
    if args.self_check:
        first, last = function_ranges(source, ['debugOriginalDebrisUpdate'])['debugOriginalDebrisUpdate']
        body = '\n'.join(source.splitlines()[first - 1:last])
        for statement in CONTRACT:
            changed = source.replace(body, body.replace(statement, '// ' + statement))
            try: contract(changed)
            except ValueError: continue
            raise ValueError('collapse checker accepted source mutation')
        clear = 'monsters_.clear();'
        clear_mutations = [body[:at] + '// ' + body[at:]
                           for at in (body.index(clear), body.rindex(clear))]
        clear_mutations.append(body.replace(clear, clear + ' ' + clear, 1))
        for changed_body in clear_mutations:
            try: contract(source.replace(body, changed_body))
            except ValueError: continue
            raise ValueError('collapse checker accepted clear occurrence mutation')
        original = (ROOT / 'LEZAC.EXE').read_bytes()
        mutations = (('collapse_table_base', 0), ('debris_table_base', 0),
                     ('record_table_initializers_executed', False),
                     ('record_table_initialization_boundaries_verified', False),
                     ('initialization_start', 0x293E), ('initialization_end', 0x2948),
                     ('initialization_sha256', '0' * 64), ('record_table_initializer', 2394))
        for key, value in mutations:
            changed = copy.deepcopy(data)
            target = changed['entry_counts'] if key == 'record_table_initializer' else changed
            target[key] = value
            try: verify_initialization(changed, original)
            except ValueError: continue
            raise ValueError('collapse checker accepted initialization mutation: ' + key)
        print('original_collapse_contract=ok source_mutants=8 initializer_mutants=8 compiled_cpp=0 clear_occurrence_mutants=3')
        return
    if args.oracle_only:
        list(records(data))
        print('original_collapse_oracle=ok cases=2395 native_crosschecks=27 compiled_cpp=0 natural_gameplay=0')
        return
    with tempfile.TemporaryDirectory(prefix='lezac-collapse-update-') as directory:
        directory = Path(directory)
        incoming, actual, expected = (directory / name for name in ('input.bin', 'actual.bin', 'expected.bin'))
        with incoming.open('wb') as request, expected.open('wb') as response:
            request.write(b'LZCU0001' + struct.pack('<I', data['cases']))
            for case_input, case_output in records(data):
                request.write(case_input)
                response.write(case_output)
        try:
            result = subprocess.run([str(args.exe.resolve()), '--debug-original-collapse-update', str(incoming), str(actual)],
                cwd=ROOT, capture_output=True, text=True, timeout=90,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'))
            if result.returncode or result.stderr or result.stdout.strip() != 'original_collapse_update=ok cases=2395':
                raise RuntimeError('compiled collapse probe failed: ' + result.stdout + result.stderr)
            compare(actual, expected)
            with actual.open('r+b') as output:
                value = output.read(1)
                output.seek(0)
                output.write(bytes((value[0] ^ 1,)))
            try: compare(actual, expected)
            except ValueError: pass
            else: raise ValueError('collapse comparator accepted output mutation')
        except Exception:
            failures = ROOT / 'build/collapse-update-failures'
            failures.mkdir(parents=True, exist_ok=True)
            retained = Path(tempfile.mkdtemp(prefix='collapse-update-', dir=failures))
            shutil.copytree(directory, retained, dirs_exist_ok=True)
            print('collapse_update_failure_retained=' + str(retained), flush=True)
            raise
    print('original_collapse_update=ok cases=2395 native_crosschecks=27 output_mutants=1 natural_gameplay=0 actors_claim=0')


if __name__ == '__main__':
    main()
