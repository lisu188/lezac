"""Compare the real App frame dispatcher with composed original clock/debris outputs."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

import capture_original_debris_phase as producer
import capture_original_debris_wrap as wrap
import check_original_debris_dispatch as dispatch
import check_original_debris_update as legacy
from level1_fidelity import ASSETS
from source_guardrails import function_ranges, source_files
from gameplay_source import gameplay_source_text

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / 'tests/gameplay/debris_phase_original.json'
FIXTURE = ROOT / 'tests/gameplay/debris_phase_original.bin.gz'
META_SHA = '0768b475cc14857ee0acb650e697e35cfa8745f57cd76b83d11bca99fa1002bc'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def contract(source):
    dispatch.contract(source)
    first, last = function_ranges(source, ['debugOriginalDebrisUpdate'])['debugOriginalDebrisUpdate']
    body = '\n'.join(source.splitlines()[first - 1:last])
    for statement in ('const bool debrisClockPhase = !collapseUpdate &&',
        'std::string(header.begin(), header.begin() + 8) == "LZDP0001";',
        'else if (debrisClockPhase) {\n                    updateWithControls(FrameControls{}, 0.0f);',
        'if (debrisClockPhase) appendWord(result, static_cast<uint16_t>(logicTick_));'):
        if body.count(statement) != 1:
            raise ValueError('Debris clock-phase consumer differs')
    first, last = function_ranges(source, ['updateWithControls'])['updateWithControls']
    frame = '\n'.join(source.splitlines()[first - 1:last])
    order = ('++logicTick_;', 'updateOrderedActors(dt);', 'updateFlashes();')
    if any(frame.count(token) != 1 for token in order) or not (
            frame.index(order[0]) < frame.index(order[1]) < frame.index(order[2])):
        raise ValueError('Production frame clock/debris order differs')


def read_cases():
    raw_meta = META.read_bytes()
    if sha(raw_meta) != META_SHA:
        raise ValueError('Original debris phase metadata differs')
    meta = json.loads(raw_meta)
    legacy.metadata()
    for path, digest in ((Path(producer.__file__), meta['generator_sha256']),
        (Path(wrap.__file__), meta['wrap_generator_sha256']), (legacy.META, meta['legacy_metadata_sha256'])):
        if sha(path.read_bytes()) != digest:
            raise ValueError('Original debris phase producer provenance differs')
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    if (len(original) != meta['original_exe_bytes'] or sha(original) != meta['original_exe_sha256'] or
            original[0x770 + 0x7903:0x770 + 0x7919].hex() != meta['counter_block_hex']):
        raise ValueError('Original frame-counter instructions differ')
    if (meta['cases'] != 360 or meta['native_crosschecks'] != 18 or meta['executor'] != 'Unicorn 2.1.4' or
            meta['counter_value_transferred_between_separate_controlled_calls'] is not True or
            meta['intervening_original_frame_work_executed'] is not False or
            meta['natural_gameplay'] is not False or meta['whole_game_fidelity_claim'] is not False or
            meta['original_calls_stubbed'] is not False or meta['original_instructions_patched'] is not False or
            meta['sound_state_compared'] is not False or meta['code_preserved_after_every_case'] is not True or
            meta['original_return_boundaries_verified'] is not True or meta['full_guest_ram_exports'] != 0):
        raise ValueError('Original debris phase evidence scope differs')
    compressed = FIXTURE.read_bytes()
    if sha(compressed) != meta['fixture_sha256']:
        raise ValueError('Original debris phase fixture differs')
    raw = gzip.decompress(compressed)
    if (len(raw) != meta['decoded_bytes'] or sha(raw) != meta['decoded_sha256'] or
            raw[:12] != b'LZPF0001' + struct.pack('<I', 360)):
        raise ValueError('Original debris phase decoded extent differs')
    cases, at, differences = [], 12, 0
    for tick in producer.TICKS:
        for slot in producer.SLOTS:
            n, m = struct.unpack_from('<II', raw, at)
            at += 8
            incoming, expected = raw[at:at + n], raw[at + n:at + n + m]
            at += n + m
            fragments = slot - 199
            after = (tick + 1) & 65535
            if (incoming != wrap.request(tick, slot) or m != 10 + 3 * 256 + fragments * 11 or
                    len(expected) != m or struct.unpack_from('<H', expected)[0] != after or
                    struct.unpack_from('<HH', expected, 6) != (fragments, 0)):
                raise ValueError('Original debris phase case layout differs')
            glyph = expected[10 + 3 * 256 + (fragments - 1) * 11 + 9]
            if glyph != (0x76 if ((after + slot) & 65535) % 6 > 2 else 0x70):
                raise ValueError('Original debris phase glyph differs')
            differences += glyph != (0x76 if ((tick + slot) & 65535) % 6 > 2 else 0x70)
            cases.append((incoming, expected))
    if at != len(raw) or len(cases) != 360 or differences != meta['late_counter_phase_counterexamples'] or differences != 127:
        raise ValueError('Original debris phase case domain differs')
    return cases


def compare(actual, expected):
    if actual != expected:
        first = next((i for i, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]),
                     min(len(actual), len(expected)))
        raise ValueError(f'Production debris clock phase differs at byte {first}; actual={len(actual)} expected={len(expected)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--oracle-only', action='store_true')
    args = parser.parse_args()
    out = Path(tempfile.mkdtemp(prefix='lezac-debris-phase-'))
    report = dict(status='failed', phase='authenticate', natural_gameplay=False,
        continuous_original_frame=False, whole_game_fidelity_claim=False, full_guest_ram_exports=0)
    protected = {}
    try:
        cases = read_cases()
        protected = {str(ROOT / name): sha((ROOT / name).read_bytes()) for name in ASSETS}
        if args.oracle_only:
            report.update(status='passed', cases=len(cases), compiled_cpp=False)
        else:
            report['phase'] = 'production_contract'
            source = ROOT / 'src/app/app.cpp'
            contract(gameplay_source_text(ROOT))
            protected.update({str(item.path): sha(item.path.read_bytes())
                              for item in source_files(ROOT, ('app', 'gameplay'), 'runtime')})
            incoming, actual = out / 'input.bin', out / 'actual.bin'
            incoming.write_bytes(b'LZDP0001' + struct.pack('<I', len(cases)) + b''.join(row[0] for row in cases))
            expected = b''.join(row[1] for row in cases)
            (out / 'expected.bin').write_bytes(expected)
            report['phase'] = 'compiled_replay'
            child = subprocess.run([str(args.exe.resolve(strict=True)), '--debug-original-debris-update',
                str(incoming), str(actual)], cwd=ROOT, capture_output=True, text=True, timeout=120,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                    LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1'))
            report.update(child_exit_code=child.returncode, stdout=child.stdout, stderr=child.stderr)
            if child.returncode or child.stderr or child.stdout.strip() != 'original_debris_update=ok cases=360':
                raise ValueError('Compiled debris clock-phase replay did not complete')
            report['phase'] = 'compare'
            value = actual.read_bytes()
            report.update(actual_bytes=len(value), expected_bytes=len(expected), actual_sha256=sha(value), expected_sha256=sha(expected))
            compare(value, expected)
            try:
                compare(bytes((value[0] ^ 1,)) + value[1:], expected)
            except ValueError:
                pass
            else:
                raise ValueError('Debris phase comparator accepted an output mutation')
            report.update(status='passed', cases=len(cases), compiled_cpp=True, output_mutants=1)
    except Exception as error:
        report['error'] = repr(error)
    finally:
        try:
            report['protected_inputs_preserved'] = (all(sha(Path(path).read_bytes()) == digest
                for path, digest in protected.items()) if protected else None)
            if report['protected_inputs_preserved'] is False:
                report.update(status='failed', preservation_error='Protected debris phase input changed')
        except OSError as error:
            report.update(status='failed', protected_inputs_preserved=False, preservation_error=repr(error))
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    if report['status'] != 'passed':
        print('original_debris_phase=failed artifacts=' + str(out) + ' error=' + report.get('error', 'preservation failure'))
        raise SystemExit(1)
    print('original_debris_phase=ok cases=360 phase_counterexamples=127 compiled_cpp=' + str(int(not args.oracle_only)) +
          ' natural_gameplay=0 continuous_original_frame=0')
    print('debris_phase_artifacts=' + str(out))


if __name__ == '__main__':
    main()
