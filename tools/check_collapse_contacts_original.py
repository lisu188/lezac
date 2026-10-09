"""Compare the live C++ contact helper with executed original pool/map records."""
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
import sys
import tempfile

from source_guardrails import function_ranges, mask_cpp, source_files

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/gameplay/collapse_contacts_original.bin.gz'
METADATA = ROOT / 'tests/gameplay/collapse_contacts_original.json'
METADATA_SHA = '475425270eb27681d932a7ba20f6c2231eddbc8a779fa5e480df40ae527d1bd5'
CONTRACT = {
    'blendCollapseContacts': (
        'auto memory = damageLaneMemory();',
        'lezac::gameplay::writeDamageLaneWord(memory, 0x2078, static_cast<uint16_t>(contacts.size()));',
        'lezac::gameplay::writeDamageLaneWord(memory, static_cast<uint16_t>(0x655e + 2 * index), contacts[index].word);',
        'lezac::gameplay::writeDamageLaneWord(memory, static_cast<uint16_t>(0x659a + 2 * index),\n'
        '                static_cast<uint16_t>(contacts[index].cell * 2));',
        'uint8_t seededClass = 0;',
        'const auto phase = lezac::gameplay::blendDamageLaneValue(memory, static_cast<uint8_t>(velocity),\n'
        '            ownWeight, reverse, [&](uint16_t cell) { return seedDamageLaneContact(cell, seededClass); });',
        'if (phase) velocity = lezac::gameplay::damageLaneSignedByte(*phase);',
    ),
    'damageLaneMemory': (
        'return lezac::gameplay::DamageLaneMemory(damageLaneData_, debrisQueue_, collapseQueue_,\n'
        '            flameRecords_, sound_, tileSeederResult_, lanes);',
    ),
    'seedDamageLaneContact': (
        'queueTileDamage(cell % level_.width, cell / level_.width, 0, 0, true, &seededClass);',
        'if (tileSeederResult_ == 0) return lezac::gameplay::DamageLaneSeed::Failed;',
        'return seededClass ? lezac::gameplay::DamageLaneSeed::Debris : lezac::gameplay::DamageLaneSeed::Collapse;',
    ),
    'blendDamageLaneValue': (
        'uint16_t weight = ownWeight;',
        'uint32_t sum = static_cast<uint32_t>(damageLaneSignedByte(incoming) * ownWeight);',
        'const uint16_t contacts = damageLaneWord(memory, 0x2078);',
        'if (result == DamageLaneSeed::Failed) return std::nullopt;',
        'lookupDamageLaneBytes(memory, reverse);',
        'sum += static_cast<uint32_t>(damageLaneSignedByte(memory.read(0x661e)) * contribution);',
        'weight = static_cast<uint16_t>(weight + contribution);',
        'const uint8_t phase = static_cast<uint8_t>(signedSum / weight);',
        'memory.write(damageLaneWriteAddress(tag, reverse), phase);',
    ),
    'damageLaneWriteAddress': (
        'return tag < 0x4e20\n'
        '        ? static_cast<uint16_t>(0x6617 + reverse + 15u * tag)\n'
        '        : static_cast<uint16_t>(0x2097 + reverse + 11u * (tag - 0x4e20));',
    ),
}
CONSUMERS = (
    ('updateCollapseRecords', 'blendCollapseContacts(result.contacts, velocity, record.affectedBytes, reverse);'),
    ('debugCollapseContactsOriginal', 'blendCollapseContacts(contacts, velocity, weight, reverse != 0);'),
)


def compact(text):
    return re.sub(r'\s+', '', mask_cpp(text))


def contact_ranges(text, names):
    # Adapt this multiline return type and braced default for the shared parser,
    # preserving line positions and every function body.
    signature = 'damageLaneMemory(std::array<int*, 4> lanes = {})'
    parsed = text.replace(signature, 'auto ' + signature.replace('{}', '0 '))
    return function_ranges(parsed, names)


def check_source(text):
    names = (*CONTRACT, *(name for name, _ in CONSUMERS))
    ranges = contact_ranges(text, names)
    if set(ranges) != set(names):
        raise ValueError('missing production contact helper or consumer: ' + ', '.join(sorted(set(names) - set(ranges))))
    bodies = {name: compact('\n'.join(text.splitlines()[first - 1:last]))
              for name, (first, last) in ranges.items()}
    for name, statements in CONTRACT.items():
        previous = -1
        for statement in statements:
            token = compact(statement)
            position = bodies[name].find(token)
            if bodies[name].count(token) != 1 or position <= previous:
                raise ValueError('production contact contract differs: ' + name + ': ' + statement)
            previous = position
    for name, call in CONSUMERS:
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


def unpack(data, incoming=None, expected=None, fixture_path=FIXTURE):
    input_hash, output_hash = hashlib.sha256(), hashlib.sha256()
    case_sizes = []
    with gzip.open(fixture_path, 'rb') as fixture:
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
            case_sizes.append(result_size)
            if incoming:
                incoming.write(request)
                expected.write(result)
        if fixture.read(1):
            raise ValueError('trailing original contact records')
    if (input_hash.hexdigest() != data['input_sha256'] or output_hash.hexdigest() != data['output_sha256']):
        raise ValueError('original contact record digest differs')
    return tuple(case_sizes)


def compare(paths, case_sizes=()):
    actual, expected = paths
    offset = 0
    with actual.open('rb') as left, expected.open('rb') as right:
        while True:
            a, b = left.read(65536), right.read(65536)
            if a != b:
                local = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                byte_offset = offset + local
                case_byte = byte_offset
                case_index = 'unknown'
                # Use validated expected sizes, never potentially corrupt output headers.
                for index, size in enumerate(case_sizes):
                    if case_byte < size:
                        case_index = str(index)
                        break
                    case_byte -= size
                else:
                    if case_sizes:
                        case_index = 'after_last'
                raise ValueError('compiled contact live pool/map record differs '
                                 f'byte_offset={byte_offset} case_index={case_index} case_byte={case_byte} '
                                 f'actual_size={actual.stat().st_size} expected_size={expected.stat().st_size}')
            if not a:
                return
            offset += len(a)


def retain_failure(directory, command, result, error, case_sizes):
    failures = ROOT / 'build/collapse-contact-failures'
    failures.mkdir(parents=True, exist_ok=True)
    retained = Path(tempfile.mkdtemp(prefix='contact-', dir=failures))
    for name in ('input.bin', 'expected.bin', 'actual.bin'):
        path = directory / name
        if path.exists():
            shutil.copy2(path, retained / name)

    def text(value):
        return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value

    context = result if result is not None else error
    diagnostic = dict(error=str(error), error_type=type(error).__name__, command=command,
                      replay_command=[command[0], command[1], str(retained / 'input.bin'),
                                      str(retained / 'rerun-actual.bin')],
                      returncode=getattr(context, 'returncode', None),
                      stdout=text(getattr(context, 'stdout', None)), stderr=text(getattr(context, 'stderr', None)),
                      case_sizes=case_sizes, case_indices_zero_based=True,
                      github_sha=os.environ.get('GITHUB_SHA'), original_fidelity_claim=False)
    (retained / 'failure.json').write_text(json.dumps(diagnostic, indent=2) + '\n', encoding='utf-8')
    print('collapse_contact_failure_retained=' + str(retained), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--oracle-only', action='store_true')
    mode.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    data = metadata()
    source = '\n'.join(item.text for item in source_files(ROOT, ('app', 'gameplay'), 'runtime'))
    check_source(source)
    if args.self_check:
        count = 0
        for name, statements in (*CONTRACT.items(), *((name, (call,)) for name, call in CONSUMERS)):
            first, last = contact_ranges(source, [name])[name]
            lines = source.splitlines(keepends=True)
            before, helper, after = ''.join(lines[:first - 1]), ''.join(lines[first - 1:last]), ''.join(lines[last:])
            for statement in statements:
                if helper.count(statement) != 1:
                    raise ValueError('contact source mutation is not unique: ' + name)
                mutated = before + helper.replace(statement, '/* ' + statement + ' */') + after
                rejects(check_source, mutated + '\nvoid unrelatedContact() {\n' + statement + '\n}\n')
                count += 1
        statement = CONTRACT['blendCollapseContacts'][0]
        check_source(source + '\n/* ' + statement + ' */\nconst char* unused = ' + json.dumps(statement) + ';\n')
        print(f'collapse_contacts_contract=ok source_mutants={count} compiled_cpp=0 natural_gameplay=0')
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
            case_sizes = unpack(data, input_file, expected_file)
        command = [str(args.exe.resolve()), '--debug-collapse-contacts-original', str(incoming), str(actual)]
        result = None
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                    env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'), timeout=60)
            if (result.returncode or result.stderr or result.stdout.strip() !=
                    'collapse_contacts_probe=ok cases=9184 original_fidelity_claim=0'):
                raise RuntimeError('compiled contact probe failed: ' + result.stdout + result.stderr)
            compare((actual, expected), case_sizes)
        except Exception as error:
            try:
                retain_failure(directory, command, result, error, case_sizes)
            except Exception as retention_error:
                print('collapse_contact_failure_retention_failed=' + str(retention_error), file=sys.stderr)
            raise
        # Expected negative controls must not be recorded as real probe failures.
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
