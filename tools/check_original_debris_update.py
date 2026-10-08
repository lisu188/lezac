"""Compare the complete production debris updater with executed-original bytes."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

from source_guardrails import function_ranges, mask_cpp, source_files

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/gameplay/debris_update_original.bin.gz'
META = ROOT / 'tests/gameplay/debris_update_original.json'
META_SHA = '99acd45538245087da6bdf174e294bcf565f57d90ced309016bf74b78cb3643c'
CONTRACT = ('level_.tiles = take(cells);', 'randomSeed_ = le32(parameters, 6);',
            'debrisQueue_.push_back(value);', 'collapseQueue_.push_back(value);',
            'updateDebrisRecords();', 'appendWord(result, record.flaggedWord);')


def compact(text):
    return re.sub(r'\s+', '', mask_cpp(text))


def contract(source):
    first, last = function_ranges(source, ['debugOriginalDebrisUpdate'])['debugOriginalDebrisUpdate']
    body = compact('\n'.join(source.splitlines()[first - 1:last]))
    for statement in CONTRACT:
        expected = 2 if statement == CONTRACT[-1] else 1
        if body.count(compact(statement)) != expected:
            raise ValueError('production debris update consumer differs')


def metadata():
    raw = META.read_bytes()
    if hashlib.sha256(raw).hexdigest() != META_SHA: raise ValueError('original debris metadata differs')
    data = json.loads(raw)
    paths = {ROOT / 'LEZAC.EXE': data['original_exe_sha256'], ROOT / 'LIVELS.SCH': data['livels_sha256'],
             ROOT / 'tools/capture_original_debris_update.py': data['generator_sha256'],
             ROOT / 'tools/scan_livels_debris_sites.py': data['decoder_sha256'], FIXTURE: data['fixture_sha256']}
    paths.update({ROOT / 'tests/fixtures' / name: digest for name, digest in data['native_fixture_sha256'].items()})
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in paths.items()):
        raise ValueError('original debris provenance differs')
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    if hashlib.sha256(original[0x770 + data['instruction_start']:0x770 + data['instruction_end']]).hexdigest() != data['instruction_sha256']:
        raise ValueError('original debris instruction window differs')
    if (data['cases'] != 1061 or data['native_crosschecked_cases'] != 18 or data['executor'] != 'Unicorn 2.1.4'
            or data['original_calls_stubbed'] or data['original_instructions_patched']
            or not data['original_return_boundaries_verified'] or not data['complete_live_records_maps_rng']
            or not data['spark_count_controlled_to_zero'] or data['sound_state_compared']
            or data['natural_gameplay'] or data['compiled_cpp_comparison'] or data['whole_game_complete']):
        raise ValueError('original debris evidence scope differs')
    return data


def records(data):
    ih, oh = hashlib.sha256(), hashlib.sha256()
    with gzip.open(FIXTURE, 'rb') as fixture:
        if fixture.read(12) != b'LZDF0001' + struct.pack('<I', data['cases']):
            raise ValueError('original debris fixture header differs')
        for index in range(data['cases']):
            lengths = fixture.read(8)
            if len(lengths) != 8: raise ValueError('truncated original debris fixture')
            incoming_size, output_size = struct.unpack('<II', lengths)
            if not (14 <= incoming_size < 100000 and 8 <= output_size < 100000):
                raise ValueError('original debris fixture sizes differ')
            incoming, expected = fixture.read(incoming_size), fixture.read(output_size)
            if len(incoming) != incoming_size or len(expected) != output_size:
                raise ValueError('truncated original debris fixture records')
            width, height, tick, rng, fragments, collapses = struct.unpack_from('<HHHIHH', incoming)
            after_fragments, after_collapses = struct.unpack_from('<HH', expected, 4)
            cells = width * height
            if (not 0 < width <= 300 or not 0 < height <= 200 or cells > 16384
                    or max(fragments, after_fragments) > 1401 or max(collapses, after_collapses) > 250
                    or incoming_size != 14 + 3 * cells + 11 * fragments + 15 * collapses
                    or output_size != 8 + 3 * cells + 11 * after_fragments + 15 * after_collapses):
                raise ValueError('original debris fixture layout differs')
            ih.update(incoming)
            oh.update(expected)
            yield incoming, expected
        if fixture.read(1) or ih.hexdigest() != data['input_sha256'] or oh.hexdigest() != data['output_sha256']:
            raise ValueError('original debris fixture digest differs')


def compare(actual, expected):
    left, right = actual.read_bytes(), expected.read_bytes()
    if left != right:
        first = next((index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]), min(len(left), len(right)))
        raise ValueError(f'production debris update differs at output byte {first}; actual={len(left)} expected={len(right)}')


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
            raise ValueError('debris update checker accepted source mutation')
        print('original_debris_contract=ok source_mutants=6 compiled_cpp=0')
        return
    if args.oracle_only:
        list(records(data))
        print('original_debris_oracle=ok cases=1061 native_crosschecks=18 compiled_cpp=0 natural_gameplay=0')
        return
    with tempfile.TemporaryDirectory(prefix='lezac-debris-update-') as directory:
        directory = Path(directory)
        incoming, actual, expected = (directory / name for name in ('input.bin', 'actual.bin', 'expected.bin'))
        with incoming.open('wb') as request, expected.open('wb') as response:
            request.write(b'LZDU0001' + struct.pack('<I', data['cases']))
            for case_input, case_output in records(data):
                request.write(case_input)
                response.write(case_output)
        try:
            result = subprocess.run([str(args.exe.resolve()), '--debug-original-debris-update', str(incoming), str(actual)],
                cwd=ROOT, capture_output=True, text=True, timeout=90,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'))
            if result.returncode or result.stderr or result.stdout.strip() != 'original_debris_update=ok cases=1061':
                raise RuntimeError('compiled debris update probe failed: ' + result.stdout + result.stderr)
            compare(actual, expected)
            with actual.open('r+b') as output:
                value = output.read(1)
                output.seek(0)
                output.write(bytes((value[0] ^ 1,)))
            try: compare(actual, expected)
            except ValueError: pass
            else: raise ValueError('debris comparator accepted output mutation')
        except Exception:
            failures = ROOT / 'build/debris-update-failures'
            failures.mkdir(parents=True, exist_ok=True)
            retained = Path(tempfile.mkdtemp(prefix='debris-update-', dir=failures))
            shutil.copytree(directory, retained, dirs_exist_ok=True)
            print('debris_update_failure_retained=' + str(retained), flush=True)
            raise
    print('original_debris_update=ok cases=1061 native_crosschecks=18 output_mutants=1 natural_gameplay=0 sound_claim=0')


if __name__ == '__main__':
    main()
