"""Check repeated original seed histories through the production contact diagnostic."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

import check_collapse_contacts_original as contacts
from source_guardrails import source_files

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/gameplay/collapse_seed_history_original.bin.gz'
METADATA = ROOT / 'tests/gameplay/collapse_seed_history_original.json'
META_SHA = 'ff99b62b1946bcd6e48743585eaf3cf7989098b8d5957f1c30516fb7410c007f'
PROFILES = ('debris_twice', 'debris_six', 'debris_thirty', 'collapse_twice',
            'collapse_six', 'debris_collapse_debris', 'collapse_debris_collapse',
            'debris_flagged_debris')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_metadata(data):
    required = dict(schema='lezac.collapse-seed-history.v1', cases=576,
        groups={name: 72 for name in PROFILES}, observer_neutrality_memory_bytes=1024**2,
        observer_neutrality_registers=14, ss_caller_offset=0xef00, ss_seed_class_offset=0xfef2,
        first_seed_defines_class=True, repeated_seed_class_retained_calls=2256,
        original_calls_stubbed=False, original_instructions_patched=False, hardware_io_permitted=False,
        actual_app_executed=False, full_collapse_update=False, natural_gameplay=False,
        original_fidelity_claim=False, whole_game_complete=False)
    if any(data.get(key) != value or type(data.get(key)) is not type(value)
           for key, value in required.items()):
        raise ValueError('original seed-history evidence boundary differs')


def metadata():
    raw = METADATA.read_bytes()
    if sha(raw) != META_SHA:
        raise ValueError('original seed-history metadata pin differs')
    data = json.loads(raw)
    validate_metadata(data)
    for path, key in ((ROOT / 'LEZAC.EXE', 'original_exe_sha256'),
                      (ROOT / 'tools/original_bomb_cpu.py', 'executor_sha256'),
                      (ROOT / 'tools/capture_original_collapse_contacts.py', 'encoder_sha256'),
                      (ROOT / 'tools/capture_original_collapse_seed_history.py', 'producer_sha256'),
                      (FIXTURE, 'fixture_sha256')):
        if sha(path.read_bytes()) != data[key]:
            raise ValueError('original seed-history source/fixture pin differs: ' + path.name)
    return data


def check_source(source):
    contacts.check_source(source)
    names = ('seedDamageLaneContact', 'blendCollapseContacts')
    ranges = contacts.contact_ranges(source, names)
    bodies = {name: contacts.compact('\n'.join(source.splitlines()[first - 1:last]))
              for name, (first, last) in ranges.items()}
    seed = bodies['seedDamageLaneContact']
    blend = bodies['blendCollapseContacts']
    if ('seedDamageLaneContact(uint16_tcell,uint8_t&seededClass)' not in seed
            or 'seededClass=' in seed
            or blend.count('seededClass=') != 1
            or blend.count('returnseedDamageLaneContact(cell,seededClass);') != 1):
        raise ValueError('production seed-class lifetime differs')


def decode(data, fixture=FIXTURE):
    incoming, expected = io.BytesIO(), io.BytesIO()
    sizes = contacts.unpack(data, incoming, expected, fixture_path=fixture)
    return incoming.getvalue(), expected.getvalue(), sizes


def run_probe(exe, out, data, production_app):
    if out.exists():
        raise ValueError('refusing to overwrite seed-history diagnostics')
    incoming, expected, sizes = decode(data)
    if max(len(incoming), len(expected)) >= 8 * 1024**2:
        raise ValueError('seed-history stream exceeds local reserve')
    out.mkdir(parents=True)
    report = dict(passed=False, production_app=production_app, extracted_methods=not production_app,
                  cases=576, masks=0, natural_gameplay=False, whole_game_claim=False,
                  input_sha256=sha(incoming), expected_sha256=sha(expected), expected_bytes=len(expected),
                  github_sha=os.environ.get('GITHUB_SHA'), original_metadata_sha256=META_SHA)
    for name, raw in (('input.bin.gz', incoming), ('expected.bin.gz', expected)):
        (out / name).write_bytes(gzip.compress(raw, mtime=0))
    # Keep each temporary stream root below the reserve independently.
    with tempfile.TemporaryDirectory(prefix='lezac-seed-input-') as input_dir, \
            tempfile.TemporaryDirectory(prefix='lezac-seed-expected-') as expected_dir, \
            tempfile.TemporaryDirectory(prefix='lezac-seed-actual-') as actual_dir:
        input_path = Path(input_dir) / 'input.bin'
        expected_path = Path(expected_dir) / 'expected.bin'
        actual_path = Path(actual_dir) / 'actual.bin'
        input_path.write_bytes(incoming)
        expected_path.write_bytes(expected)
        command = [str(exe.resolve()), '--debug-collapse-contacts-original', str(input_path), str(actual_path)]
        report['command'] = command
        result = None
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1'))
            report.update(returncode=result.returncode, stdout=result.stdout.decode(errors='replace'),
                          stderr=result.stderr.decode(errors='replace'))
            if (result.returncode != 0 or result.stderr or result.stdout.strip() !=
                    b'collapse_contacts_probe=ok cases=576 original_fidelity_claim=0'):
                raise ValueError('seed-history production diagnostic failed')
            contacts.compare((actual_path, expected_path), sizes)
            report['passed'] = True
        except BaseException as error:
            report.update(error=str(error), error_type=type(error).__name__)
            if result is None:
                for key in ('stdout', 'stderr'):
                    value = getattr(error, key, None)
                    report[key] = value.decode(errors='replace') if isinstance(value, bytes) else value
            raise
        finally:
            if actual_path.exists():
                raw = actual_path.read_bytes()
                report.update(actual_sha256=sha(raw), actual_bytes=len(raw))
                (out / 'actual.bin.gz').write_bytes(gzip.compress(raw, mtime=0))
            (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            print('collapse_seed_history_retained=' + str(out.resolve()), flush=True)
            if sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) >= 8 * 1024**2:
                raise ValueError('seed-history retained bundle exceeds local reserve')
    return report


def self_check(data, source):
    source_mutants = (
        source.replace('uint16_t cell, uint8_t& seededClass', 'uint16_t cell, uint8_t seededClass'),
        source.replace('queueTileDamage(cell % level_.width',
                       'seededClass = 0;\n        queueTileDamage(cell % level_.width'),
        source.replace('return seedDamageLaneContact(cell, seededClass);',
                       'seededClass = 0; return seedDamageLaneContact(cell, seededClass);'),
        source.replace('return seededClass ? lezac::gameplay::DamageLaneSeed::Debris',
                       'seededClass = 0; return seededClass ? lezac::gameplay::DamageLaneSeed::Debris'),
    )
    for mutated in source_mutants:
        if mutated == source:
            raise ValueError('seed-history source mutant did not apply')
        contacts.rejects(check_source, mutated)
    for key, value in (('cases', 575), ('first_seed_defines_class', False),
                       ('observer_neutrality_registers', 13), ('original_calls_stubbed', True)):
        contacts.rejects(validate_metadata, dict(data, **{key: value}))
    original = gzip.decompress(FIXTURE.read_bytes())
    variants = (original[:11], original[:-1], original + b'\0',
                original[:20] + bytes((original[20] ^ 1,)) + original[21:],
                original[:-1] + bytes((original[-1] ^ 1,)))
    with tempfile.TemporaryDirectory(prefix='lezac-seed-checker-') as directory:
        for index, variant in enumerate(variants):
            path = Path(directory) / (str(index) + '.gz')
            path.write_bytes(gzip.compress(variant, mtime=0))
            contacts.rejects(lambda value: decode(data, value), path)
    incoming, expected, _ = decode(data)
    first_input, first_output = struct.unpack_from('<II', original, 12)
    if original[20 + first_input] != ((-128 // 3) + 1) & 255 or first_output != 426:
        raise ValueError('first original repeated-debris result differs')
    if len(incoming) <= 12 or len(expected) == 0:
        raise ValueError('seed-history stream is empty')
    print('collapse_seed_history_checker=ok source_mutants=4 metadata_mutants=4 fixture_mutants=5')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--extracted-exe', type=Path)
    mode.add_argument('--self-check', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if bool(args.exe or args.extracted_exe) != bool(args.out):
        parser.error('--out is required only with an executable')
    data = metadata()
    source = '\n'.join(item.text for item in source_files(ROOT, ('app', 'gameplay'), 'runtime'))
    check_source(source)
    if args.self_check:
        self_check(data, source)
    elif args.exe or args.extracted_exe:
        run_probe(args.exe or args.extracted_exe, args.out, data, bool(args.exe))
        print('collapse_seed_history_original=ok cases=576 production_app=' + str(int(bool(args.exe))) +
              ' masks=0 natural_gameplay=0 whole_game_claim=0')
    else:
        _, expected, _ = decode(data)
        print('collapse_seed_history_fixture=ok cases=576 state_bytes=' + str(len(expected)) +
              ' production_app=0 natural_gameplay=0 whole_game_claim=0')


if __name__ == '__main__':
    main()
