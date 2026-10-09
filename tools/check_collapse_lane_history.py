"""Compare input-only production collapse updates with complete original state."""
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
from unittest.mock import patch

from check_collapse_contacts_original import compact, contact_ranges, rejects
from source_guardrails import source_files

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/gameplay/collapse_lane_history_original.bin.gz'
METADATA = ROOT / 'tests/gameplay/collapse_lane_history_original.json'
META_SHA = 'bc4858b73a8081cca6b996061d0e7be28c38862341a5d4237215889beba1ea4e'
CASES, INPUT, STATE = 96, 26730, 26724
RESERVE = 8 * 1024**2


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_metadata(data):
    required = dict(schema='lezac.collapse-lane-history.v1', passed=True, cases=CASES,
        groups={'debris': 36, 'collapse': 12, 'alternating': 36, 'collapse-group': 12},
        input_bytes=INPUT, state_bytes=STATE, observer_neutrality_memory_bytes=1024**2,
        observer_neutrality_registers=14, poison_variants_per_case=3, stack_poison_address=0x8fed2,
        observable_stack_poison_independence=True, original_calls_stubbed=False,
        original_instructions_patched=False, hardware_io_permitted=False, full_collapse_update=True,
        actual_app_executed=False, seeded=True, natural_route=False,
        first_seed_stack_history_generally_proven=False, original_fidelity_claim=False,
        whole_game_complete=False)
    if any(data.get(key) != value or type(data.get(key)) is not type(value)
           for key, value in required.items()):
        raise ValueError('collapse history original evidence boundary differs')


def metadata():
    raw = METADATA.read_bytes()
    if sha(raw) != META_SHA:
        raise ValueError('collapse history metadata pin differs')
    data = json.loads(raw)
    validate_metadata(data)
    for path, key in ((ROOT / 'LEZAC.EXE', 'original_exe_sha256'),
                      (ROOT / 'tools/original_bomb_cpu.py', 'executor_sha256'),
                      (ROOT / 'tools/capture_original_contact_staging.py', 'staging_sha256'),
                      (ROOT / 'tools/capture_original_fracture_retirement.py', 'reader_sha256'),
                      (ROOT / 'tools/capture_original_collapse_lane_history.py', 'producer_sha256')):
        if sha(path.read_bytes()) != data[key]:
            raise ValueError('collapse history original source pin differs: ' + path.name)
    return data


def check_source(source):
    names = ('updateCollapseRecords', 'debugOriginalDebrisUpdate')
    ranges = contact_ranges(source, names)
    bodies = {name: compact('\n'.join(source.splitlines()[first - 1:last]))
              for name, (first, last) in ranges.items()}
    update = bodies['updateCollapseRecords']
    start = update.index('autoscan=')
    end = update.index('returnresult;', start)
    scan = update[start:end]
    clear = scan.find('damageLaneData_[0x661e]=0;')
    loop = scan.find('for(intcell:cells())')
    blocked = scan.find('result.blocked=true;')
    mark = scan.find('damageLaneData_[0x661e]=1;')
    collect = scan.find('if(collectContacts')
    if (not 0 <= clear < loop < blocked < mark < collect
            or scan.count('damageLaneData_[0x661e]=') != 2):
        raise ValueError('production collapse scanner scratch ownership differs')
    diagnostic = bodies['debugOriginalDebrisUpdate']
    required = ('boolcollapseLaneHistory=false',
        'if(collapseLaneHistory&&(!fractureStorage||!laneHistory||physicalDebrisUpdate))',
        'collapseLaneHistory?"LZCI0001":"LZDH0001"',
        'collapseLaneHistory?26730:laneHistory?53454:53448',
        'collapseLaneHistory?"LZCO0001":"LZDO0001"',
        'if(fractureStorage&&!collapseLaneHistory)take(fractureStateBytes);',
        'damageLaneData_[0x661e]=history[0];', 'damageLaneData_[0x0a06]=history[1];',
        'damageLaneData_[0x0a07]=history[2];', 'elseif(collapseUpdate)updateCollapseRecords();')
    if any(compact(token) not in diagnostic for token in required):
        raise ValueError('input-only collapse history diagnostic contract differs')
    if compact('"--debug-original-collapse-lane-history"){app.debugOriginalDebrisUpdate(argv[2],argv[3],'
               'true,false,false,true,false,true,true);return0;}') not in compact(source):
        raise ValueError('input-only collapse history command dispatch differs')


def decode(data, path=FIXTURE):
    packed = path.read_bytes()
    if len(packed) > 256 * 1024 or sha(packed) != data['fixture_sha256']:
        raise ValueError('collapse history packed fixture pin differs')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(6 * 1024**2 + 1)
    if (len(raw) != 16 + CASES * (INPUT + STATE) or sha(raw) != data['fixture_raw_sha256']
            or struct.unpack_from('<8sII', raw) != (b'LZCH0001', CASES, INPUT + STATE)):
        raise ValueError('collapse history fixture dimensions or raw pin differ')
    incoming = bytearray(struct.pack('<8sII', b'LZCI0001', CASES, INPUT))
    expected = bytearray(struct.pack('<8sII', b'LZCO0001', CASES, STATE))
    for index in range(CASES):
        offset = 16 + index * (INPUT + STATE)
        incoming.extend(raw[offset:offset + INPUT])
        expected.extend(raw[offset + INPUT:offset + INPUT + STATE])
    if sha(expected) != data['expected_sha256']:
        raise ValueError('collapse history expected stream pin differs')
    return bytes(incoming), bytes(expected)


def compare(actual, expected):
    if actual == expected:
        return
    if len(actual) != len(expected):
        raise ValueError('collapse history output size differs: ' + str(len(actual)))
    offset = next(index for index, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1])
    case, field = divmod(offset - 16, STATE) if offset >= 16 else (-1, offset)
    raise ValueError('collapse history mismatch case=' + str(case) + ' state_offset=' + str(field) +
                     ' actual=' + str(actual[offset]) + ' original=' + str(expected[offset]))


def run_probe(exe, out, data):
    if out.exists():
        raise ValueError('refusing to overwrite collapse history diagnostics')
    incoming, expected = decode(data)
    out.mkdir(parents=True)
    report = dict(passed=False, production_app=True, cases=CASES, masks=0, input_only=True,
        seeded=True, natural_route=False, whole_game_claim=False, github_sha=os.environ.get('GITHUB_SHA'),
        input_sha256=sha(incoming), input_bytes=len(incoming), expected_sha256=sha(expected),
        expected_bytes=len(expected), original_metadata_sha256=META_SHA)
    for name, raw in (('input.bin.gz', incoming), ('expected.bin.gz', expected)):
        (out / name).write_bytes(gzip.compress(raw, mtime=0))
    with tempfile.TemporaryDirectory(prefix='lezac-collapse-history-input-') as input_dir, \
            tempfile.TemporaryDirectory(prefix='lezac-collapse-history-actual-') as actual_dir:
        input_path, actual_path = Path(input_dir) / 'input.bin', Path(actual_dir) / 'actual.bin'
        input_path.write_bytes(incoming)
        command = [str(exe.resolve()), '--debug-original-collapse-lane-history', str(input_path), str(actual_path)]
        report['command'] = command
        result = None
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=90,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1'))
            report.update(returncode=result.returncode, stdout=result.stdout.decode(errors='replace'),
                          stderr=result.stderr.decode(errors='replace'))
            wanted = ('collapse_lane_history_app=ok cases=96 compared_bytes=2565504 retained_debris=1402 '
                      'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 history_bytes=3 '
                      'production_app=1 seeded=1 natural_route=0 whole_game_claim=0')
            if result.returncode != 0 or result.stderr or result.stdout.strip().decode() != wanted:
                raise ValueError('collapse history production diagnostic failed')
            if actual_path.stat().st_size >= RESERVE:
                raise ValueError('collapse history actual stream exceeds local reserve')
            compare(actual_path.read_bytes(), expected)
            report['passed'] = True
        except BaseException as error:
            report.update(error=str(error), error_type=type(error).__name__)
            if result is None:
                for key in ('stdout', 'stderr'):
                    value = getattr(error, key, None)
                    report[key] = value.decode(errors='replace') if isinstance(value, bytes) else value
            raise
        finally:
            if actual_path.exists() and actual_path.stat().st_size < RESERVE:
                raw = actual_path.read_bytes()
                report.update(actual_sha256=sha(raw), actual_bytes=len(raw))
                (out / 'actual.bin.gz').write_bytes(gzip.compress(raw, mtime=0))
            (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            print('collapse_lane_history_retained=' + str(out.resolve()), flush=True)
            if sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) >= RESERVE:
                raise ValueError('collapse history retained bundle exceeds local reserve')


def self_check(data, source):
    source_mutants = (
        source.replace('damageLaneData_[0x661e] = 0;\n                for (int cell : cells())',
                       'for (int cell : cells())'),
        source.replace('result.blocked = true;\n                    damageLaneData_[0x661e] = 1;',
                       'result.blocked = true;'),
        source.replace('if (fractureStorage && !collapseLaneHistory) take(fractureStateBytes);',
                       'if (fractureStorage) take(fractureStateBytes);'),
        source.replace('true, false, false, true, false, true, true);',
                       'true, false, false, true, true, true, true);'),
    )
    for mutant in source_mutants:
        if mutant == source:
            raise ValueError('collapse history source mutant did not apply')
        rejects(check_source, mutant)
    for key, value in (('cases', 95), ('full_collapse_update', False),
                       ('observer_neutrality_registers', 13), ('original_calls_stubbed', True),
                       ('first_seed_stack_history_generally_proven', True)):
        rejects(validate_metadata, dict(data, **{key: value}))
    incoming, expected = decode(data)
    if struct.unpack_from('<8sII', incoming) != (b'LZCI0001', CASES, INPUT):
        raise ValueError('collapse history input-only header differs')
    raw = gzip.decompress(FIXTURE.read_bytes())
    variants = (raw[:11], raw[:-1], raw + b'\0', raw[:20] + bytes((raw[20] ^ 1,)) + raw[21:],
                raw[:-1] + bytes((raw[-1] ^ 1,)))
    with tempfile.TemporaryDirectory(prefix='lezac-collapse-history-checker-') as directory:
        for index, variant in enumerate(variants):
            path = Path(directory) / (str(index) + '.gz')
            path.write_bytes(gzip.compress(variant, mtime=0))
            rejects(lambda value: decode(data, value), path)
    for offset in (0, 16, 16 + 5952, len(expected) - 3, len(expected) - 1):
        mutant = expected[:offset] + bytes((expected[offset] ^ 1,)) + expected[offset + 1:]
        rejects(lambda value: compare(value, expected), mutant)
    for mode in ('ok', 'mismatch', 'nonzero', 'timeout'):
        with tempfile.TemporaryDirectory(prefix='lezac-collapse-history-runner-') as directory:
            out = Path(directory) / 'retained'
            written = expected if mode != 'mismatch' else expected[:-1] + bytes((expected[-1] ^ 1,))
            if mode == 'timeout':
                written = written[:25]

            def runner(command, **kwargs):
                if (len(command) != 4 or command[1] != '--debug-original-collapse-lane-history'
                        or Path(command[2]).read_bytes() != incoming
                        or kwargs['env']['SDL_AUDIODRIVER'] != 'dummy'
                        or kwargs['env']['SDL_VIDEODRIVER'] != 'dummy'):
                    raise ValueError('collapse history runner passed expected bytes or enabled audio')
                Path(command[3]).write_bytes(written)
                if mode == 'timeout':
                    raise subprocess.TimeoutExpired(command, 90, output=b'partial stdout', stderr=b'partial stderr')
                marker = ('collapse_lane_history_app=ok cases=96 compared_bytes=2565504 retained_debris=1402 '
                          'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 history_bytes=3 '
                          'production_app=1 seeded=1 natural_route=0 whole_game_claim=0')
                return subprocess.CompletedProcess(command, 1 if mode == 'nonzero' else 0, marker.encode(), b'')

            with patch.object(subprocess, 'run', side_effect=runner):
                try:
                    run_probe(Path(directory) / 'mocked-not-a-game', out, data)
                except (ValueError, subprocess.TimeoutExpired):
                    if mode == 'ok':
                        raise
                else:
                    if mode != 'ok':
                        raise ValueError('collapse history failure was accepted')
            report = json.loads((out / 'result.json').read_bytes())
            if (report['passed'] != (mode == 'ok') or gzip.decompress((out / 'actual.bin.gz').read_bytes()) != written
                    or gzip.decompress((out / 'input.bin.gz').read_bytes()) != incoming
                    or gzip.decompress((out / 'expected.bin.gz').read_bytes()) != expected):
                raise ValueError('collapse history runner did not retain exact diagnostic streams')
    print('collapse_lane_history_checker=ok source_mutants=4 metadata_mutants=5 fixture_mutants=5 output_mutants=5 mocked_runner_modes=4')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--self-check', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if bool(args.exe) != bool(args.out):
        parser.error('--out is required only with --exe')
    data = metadata()
    source = '\n'.join(item.text for item in source_files(ROOT, ('app', 'gameplay'), 'runtime'))
    check_source(source)
    if args.self_check:
        self_check(data, source)
    elif args.exe:
        run_probe(args.exe, args.out, data)
        print('collapse_lane_history_original=ok cases=96 production_app=1 input_only=1 masks=0 natural_route=0 whole_game_claim=0')
    else:
        incoming, expected = decode(data)
        print('collapse_lane_history_fixture=ok cases=96 input_bytes=' + str(len(incoming) - 16) +
              ' state_bytes=' + str(len(expected) - 16) + ' production_app=0 natural_route=0 whole_game_claim=0')


if __name__ == '__main__':
    main()
