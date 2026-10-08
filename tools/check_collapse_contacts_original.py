"""Compare the live C++ contact helper with executed original pool/map records."""
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
FIXTURE = ROOT / 'tests/gameplay/collapse_contacts_original.bin.gz'
METADATA = ROOT / 'tests/gameplay/collapse_contacts_original.json'
METADATA_SHA = '475425270eb27681d932a7ba20f6c2231eddbc8a779fa5e480df40ae527d1bd5'
CONTRACT = (
    'int weight = ownWeight;', 'int sum = velocity * weight;',
    'queueTileDamage(contact.cell % level_.width, contact.cell / level_.width, 0, 0, true);',
    'if (beforeDebris == debrisQueue_.size() && beforeCollapse == collapseQueue_.size()) return;',
    'sum += contribution * static_cast<int8_t>(match.phase);',
    'velocity = static_cast<int8_t>(sum / weight);',
    'debrisQueue_[index].velocityX = static_cast<int8_t>(velocity);',
    'debrisQueue_[index].velocityY = static_cast<int8_t>(velocity);',
    'collapseQueue_[index].reversePhase = static_cast<uint8_t>(velocity);',
    'collapseQueue_[index].forwardPhase = static_cast<uint8_t>(velocity);',
)


def compact(text):
    return re.sub(r'\s+', '', mask_cpp(text))


def check_source(text):
    names = ('blendCollapseContacts', 'updateCollapseRecords', 'debugCollapseContactsOriginal')
    ranges = function_ranges(text, names)
    if set(ranges) != set(names):
        raise ValueError('missing production contact helper or consumer')
    bodies = {name: compact('\n'.join(text.splitlines()[first - 1:last]))
              for name, (first, last) in ranges.items()}
    for statement in CONTRACT:
        if bodies['blendCollapseContacts'].count(compact(statement)) != 1:
            raise ValueError('production contact contract differs: ' + statement)
    for name, call in (
        ('updateCollapseRecords', 'blendCollapseContacts(result.contacts, velocity, record.affectedBytes, reverse);'),
        ('debugCollapseContactsOriginal', 'blendCollapseContacts(contacts, velocity, weight, reverse != 0);')):
        if bodies[name].count(compact(call)) != 1 or bodies[name].count('blendCollapseContacts(') != 1:
            raise ValueError('production contact consumer differs: ' + name)


def rejects(check, value):
    try:
        check(value)
    except (ValueError, RuntimeError):
        return
    raise ValueError('contact checker accepted a mutation')


def metadata():
    raw = METADATA.read_bytes()
    if hashlib.sha256(raw).hexdigest() != METADATA_SHA:
        raise ValueError('executed-original contact metadata differs')
    data = json.loads(raw)
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    generator = ROOT / 'tools/capture_original_collapse_contacts.py'
    if (data['schema'] != 'lezac.collapse-contact-original.v1' or data['cases'] != 9184
            or data['allocation_failure_cases'] != 1248 or data['partial_allocation_failure_cases'] != 672
            or data['original_calls_stubbed'] or data['original_instructions_patched']
            or not data['return_boundaries_verified'] or data['natural_gameplay']
            or data['full_collapse_update'] or data['compiled_cpp_comparison']
            or data['original_fidelity_claim'] or data['whole_game_complete']
            or hashlib.sha256(original).hexdigest() != data['original_exe_sha256']
            or hashlib.sha256(generator.read_bytes()).hexdigest() != data['generator_sha256']
            or hashlib.sha256(FIXTURE.read_bytes()).hexdigest() != data['fixture_sha256']):
        raise ValueError('executed-original contact provenance differs')
    for window in data['instruction_windows']:
        raw = original[0x770 + window['start']:0x770 + window['end']]
        if hashlib.sha256(raw).hexdigest() != window['sha256']:
            raise ValueError('original contact instruction window differs')
    return data


def unpack(data, incoming=None, expected=None):
    input_hash, output_hash = hashlib.sha256(), hashlib.sha256()
    with gzip.open(FIXTURE, 'rb') as fixture:
        if fixture.read(12) != b'LZCF0001' + struct.pack('<I', data['cases']):
            raise ValueError('original contact fixture header differs')
        if incoming:
            incoming.write(b'LZCC0001' + struct.pack('<I', data['cases']))
        for _ in range(data['cases']):
            lengths = fixture.read(8)
            if len(lengths) != 8:
                raise ValueError('truncated original contact fixture')
            size, result_size = struct.unpack('<II', lengths)
            if not (392 <= size <= 17000 and 389 <= result_size <= 17000):
                raise ValueError('invalid original contact record sizes')
            request, result = fixture.read(size), fixture.read(result_size)
            if len(request) != size or len(result) != result_size:
                raise ValueError('truncated original contact records')
            own, weight, reverse, debris, collapse, contacts = struct.unpack_from('<bBBHHB', request)
            after_debris, after_collapse = struct.unpack_from('<HH', result, 1)
            if (weight == 0 or reverse > 1 or debris > 1401 or collapse > 30 or contacts > 30
                    or after_debris > 1401 or after_collapse > 30
                    or size != 392 + 11 * debris + 15 * collapse + 4 * contacts
                    or result_size != 389 + 11 * after_debris + 15 * after_collapse):
                raise ValueError('original contact record layout differs')
            input_hash.update(request)
            output_hash.update(result)
            if incoming:
                incoming.write(request)
                expected.write(result)
        if fixture.read(1):
            raise ValueError('trailing original contact records')
    if (input_hash.hexdigest() != data['input_sha256'] or output_hash.hexdigest() != data['output_sha256']):
        raise ValueError('original contact record digest differs')


def compare(paths):
    actual, expected = paths
    with actual.open('rb') as left, expected.open('rb') as right:
        while True:
            a, b = left.read(65536), right.read(65536)
            if a != b:
                raise ValueError('compiled contact live pool/map record differs')
            if not a:
                return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--oracle-only', action='store_true')
    mode.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    data = metadata()
    source = '\n'.join(item.text for item in source_files(ROOT, 'app', 'runtime'))
    check_source(source)
    if args.self_check:
        first, last = function_ranges(source, ['blendCollapseContacts'])['blendCollapseContacts']
        lines = source.splitlines(keepends=True)
        before, helper, after = ''.join(lines[:first - 1]), ''.join(lines[first - 1:last]), ''.join(lines[last:])
        for statement in CONTRACT:
            if helper.count(statement) != 1:
                raise ValueError('contact source mutation is not unique')
            rejects(check_source, before + helper.replace(statement, '// ' + statement) + after)
        check_source(source + '\n// ' + CONTRACT[0] + '\n')
        print('collapse_contacts_contract=ok source_mutants=10 compiled_cpp=0 natural_gameplay=0')
        return
    if args.oracle_only:
        unpack(data)
        print('collapse_contacts_oracle=ok cases=9184 groups=14 capacity_failures=1248 '
              'partial_allocation_failures=672 compiled_cpp=0 natural_gameplay=0')
        return
    with tempfile.TemporaryDirectory(prefix='lezac-collapse-contacts-') as directory:
        directory = Path(directory)
        incoming, expected, actual = (directory / name for name in ('input.bin', 'expected.bin', 'actual.bin'))
        with incoming.open('wb') as input_file, expected.open('wb') as expected_file:
            unpack(data, input_file, expected_file)
        result = subprocess.run([str(args.exe.resolve()), '--debug-collapse-contacts-original',
                                 str(incoming), str(actual)], cwd=ROOT, capture_output=True, text=True,
                                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'), timeout=60)
        if (result.returncode or result.stderr or result.stdout.strip() !=
                'collapse_contacts_probe=ok cases=9184 original_fidelity_claim=0'):
            raise RuntimeError('compiled contact probe failed: ' + result.stdout + result.stderr)
        compare((actual, expected))
        for offset in (0, actual.stat().st_size - 1):
            with actual.open('r+b') as output:
                output.seek(offset)
                before = output.read(1)
                output.seek(offset)
                output.write(bytes((before[0] ^ 1,)))
            rejects(compare, (actual, expected))
            with actual.open('r+b') as output:
                output.seek(offset)
                output.write(before)
        with actual.open('ab') as output:
            output.write(b'\0')
        rejects(compare, (actual, expected))
        with actual.open('r+b') as output:
            output.truncate(actual.stat().st_size - 2)
        rejects(compare, (actual, expected))
    print('collapse_contacts_original=ok cases=9184 groups=14 capacity_failures=1248 '
          'partial_allocation_failures=672 output_mutants=4 natural_gameplay=0 whole_game_parity=0')


if __name__ == '__main__':
    main()
