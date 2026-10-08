"""Compare the production flame blend with executed original instruction records."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from source_guardrails import function_ranges, mask_cpp, source_files

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/gameplay/flame_contact_word_original.json'
FIXTURE_SHA = 'b8680640cd50c88b71d7ed3e3bdfbeb5b030a971e2eb0ab367ac191441290fe5'
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
CASES_PER_GROUP = 65536
GROUP_BYTES = CASES_PER_GROUP * 8
CALL = 'return lezac::gameplay::blendFlameVelocity(own, incoming, ray.mass, weight);'
WEIGHT = 'const int weight = match.debris ? 1 : collapseQueue_[other].affectedBytes;'
WRITES = (
    'debris.velocityX = blend(ray.vx, debris.velocityX);',
    'debris.velocityY = blend(ray.vy, debris.velocityY);',
    'collapse.forwardPhase = static_cast<uint8_t>(blend(ray.vx, static_cast<int8_t>(collapse.forwardPhase)));',
    'collapse.reversePhase = static_cast<uint8_t>(blend(ray.vy, static_cast<int8_t>(collapse.reversePhase)));',
)


def compact(text):
    return re.sub(r'\s+', '', mask_cpp(text))


def fixture():
    raw = FIXTURE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FIXTURE_SHA:
        raise ValueError('executed-original flame fixture differs')
    data = json.loads(raw)
    expected = [(mass, weight) for mass in (1, 9, 221) for weight in (0, 1, 2, 8, 18, 128, 254)]
    if (data['schema'] != 'lezac.flame-contact-word-oracle.v1'
            or [(g['mass'], g['weight']) for g in data['groups']] != expected
            or any(g['cases'] != CASES_PER_GROUP or g['original_vs_word_model_mismatches']
                   for g in data['groups'])
            or data['cases'] != 1376256 or data['record_bytes'] != 8
            or data['record_layout'] != ['own_x', 'own_y', 'incoming_x', 'incoming_y',
                                         'mass', 'weight', 'result_x', 'result_y']
            or data['unwrapped_arithmetic_differences'] != 19855
            or data['natural_gameplay_comparison'] or data['full_flame_update_comparison']):
        raise ValueError('executed-original flame fixture scope differs')
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    if hashlib.sha256(original).hexdigest() != EXE_SHA or data['original_exe_sha256'] != EXE_SHA:
        raise ValueError('original flame executable differs')
    window = original[0x770 + 0x47DF:0x770 + 0x4851]
    if (data['instruction_start'] != 0x47DF or data['instruction_end_exclusive'] != 0x4851
            or data['instruction_bytes'] != 114 or window.hex() != data['instruction_hex']
            or hashlib.sha256(window).hexdigest() != data['instruction_sha256']):
        raise ValueError('original flame arithmetic instructions differ')
    return data


def production_source():
    app = '\n'.join(source.text for source in source_files(ROOT, 'app', 'runtime'))
    gameplay = '\n'.join(source.text for source in source_files(ROOT, 'gameplay', 'runtime'))
    if 'blendFlameVelocity' not in function_ranges(gameplay, ['blendFlameVelocity']):
        raise ValueError('production flame blend helper is missing')
    return app


def check_source(text):
    ranges = function_ranges(text, ['updateFlameRecords'])
    if 'updateFlameRecords' not in ranges:
        raise ValueError('runtime flame update is missing')
    first, last = ranges['updateFlameRecords']
    body = compact('\n'.join(text.splitlines()[first - 1:last]))
    for statement in (WEIGHT, CALL, *WRITES):
        if body.count(compact(statement)) != 1:
            raise ValueError('runtime flame blend consumer differs: ' + statement)
    if body.count('blendFlameVelocity(') != 1 or body.count('blend(') != 4:
        raise ValueError('runtime flame blend routing differs')


def check_records(records, data):
    if len(records) != data['cases'] * 8:
        raise ValueError('compiled flame record count differs')
    for index, group in enumerate(data['groups']):
        chunk = records[index * GROUP_BYTES:(index + 1) * GROUP_BYTES]
        if hashlib.sha256(chunk).hexdigest() != group['records_sha256']:
            raise ValueError(f"compiled flame blend differs for mass={group['mass']} weight={group['weight']}")
    if hashlib.sha256(records).hexdigest() != data['records_sha256']:
        raise ValueError('compiled flame aggregate differs')


def rejects(check, value):
    try:
        check(value)
    except (ValueError, RuntimeError):
        return
    raise ValueError('checker accepted a mutation')


def source_self_check(text):
    check_source(text)
    changes = [(CALL, 'return static_cast<int8_t>(own);'),
               (WEIGHT, 'const int weight = 0;'),
               (CALL, CALL.replace('(own, incoming,', '(incoming, own,'))]
    changes.extend((statement, '// ' + statement) for statement in WRITES)
    for before, after in changes:
        if text.count(before) != 1:
            raise ValueError('source mutation is not unique')
        rejects(check_source, text.replace(before, after))
    check_source(text + '\n// ' + CALL + '\nconst char* unused = "' + CALL + '";\n')
    return len(changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--oracle-only', action='store_true')
    mode.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    data = fixture()
    source = production_source()
    check_source(source)
    if args.self_check:
        mutations = source_self_check(source)
        print(f'flame_contact_word_contract=ok source_mutants={mutations} compiled_cpp=0 natural_gameplay=0')
        return
    if args.oracle_only:
        print('flame_contact_word_oracle=ok cases=1376256 groups=21 instructions=114 '
              'executed_original_fixture=1 compiled_cpp=0 natural_gameplay=0 whole_game_parity=0')
        return
    result = subprocess.run([str(args.exe.resolve())], cwd=ROOT,
                            env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'),
                            capture_output=True, timeout=30)
    if result.returncode or result.stderr:
        raise ValueError('compiled flame probe failed: ' + result.stderr.decode(errors='replace'))
    records = result.stdout
    check_records(records, data)
    changed = bytearray(records)
    changed[6] ^= 1
    mutants = (records[:-8], records + records[:8], bytes(changed),
               records[8:16] + records[:8] + records[16:])
    for mutant in mutants:
        rejects(lambda value: check_records(value, data), mutant)
    print('flame_contact_word=ok cases=1376256 groups=21 executed_original_fixture=1 '
          'output_mutants=4 natural_gameplay=0 whole_game_parity=0')


if __name__ == '__main__':
    main()
