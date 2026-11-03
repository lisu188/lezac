"""Compare the production debris updater with frozen original rollover cases."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

import capture_original_debris_wrap as producer
import check_original_debris_dispatch as dispatch
import check_original_debris_update as legacy
from level1_fidelity import ASSETS

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/gameplay/debris_wrap_original.bin.gz'
META = ROOT / 'tests/gameplay/debris_wrap_original.json'
META_SHA = 'b88a5611fffffc955da8938070ac154ddcc74de09607c9be2810d954c5a9559c'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def read_cases():
    metadata_raw = META.read_bytes()
    if sha(metadata_raw) != META_SHA:
        raise ValueError('Original debris wrap metadata differs')
    meta = json.loads(metadata_raw)
    legacy.metadata()
    if (sha(Path(producer.__file__).read_bytes()) != meta['generator_sha256'] or
            sha(legacy.META.read_bytes()) != meta['legacy_metadata_sha256']):
        raise ValueError('Original debris wrap producer provenance differs')
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    if (len(original) != meta['original_exe_bytes'] or sha(original) != meta['original_exe_sha256'] or
            original[0x770 + 0x4afa:0x770 + 0x4b0d].hex() != meta['instruction_hex']):
        raise ValueError('Original debris wrap instructions differ')
    compressed = FIXTURE.read_bytes()
    if sha(compressed) != meta['fixture_sha256']:
        raise ValueError('Original debris wrap fixture differs')
    raw = gzip.decompress(compressed)
    if (len(raw) != meta['decoded_bytes'] or sha(raw) != meta['decoded_sha256'] or
            raw[:12] != b'LZDF0001' + struct.pack('<I', 276)):
        raise ValueError('Original debris wrap decoded extent differs')
    cases, at, ih, oh = [], 12, hashlib.sha256(), hashlib.sha256()
    for tick in producer.TICKS:
        for slot in producer.SLOTS:
            n, m = struct.unpack_from('<II', raw, at)
            at += 8
            incoming, expected = raw[at:at + n], raw[at + n:at + n + m]
            at += n + m
            fragments = slot - 199
            if (incoming != producer.request(tick, slot) or
                    m != 8 + 3 * 256 + fragments * 11 or len(expected) != m or
                    struct.unpack_from('<HH', expected, 4) != (fragments, 0)):
                raise ValueError('Original debris wrap case layout or input differs')
            ih.update(incoming)
            oh.update(expected)
            cases.append((incoming, expected))
    if (at != len(raw) or len(cases) != 276 or ih.hexdigest() != meta['input_sha256'] or
            oh.hexdigest() != meta['output_sha256'] or meta['wide_sum_disagreements'] != 108):
        raise ValueError('Original debris wrap case digests differ')
    return cases


def compare(actual, expected):
    if actual != expected:
        first = next((i for i, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]),
                     min(len(actual), len(expected)))
        raise ValueError(f'Production debris wrap differs at byte {first}; actual={len(actual)} expected={len(expected)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--oracle-only', action='store_true')
    args = parser.parse_args()
    out = Path(tempfile.mkdtemp(prefix='lezac-debris-wrap-'))
    report = dict(status='failed', phase='authenticate', original_gameplay=False,
        whole_game_fidelity_claim=False, full_guest_ram_exports=0)
    protected = {}
    try:
        cases = read_cases()
        protected = {str(ROOT / name): sha((ROOT / name).read_bytes()) for name in ASSETS}
        if args.oracle_only:
            report.update(status='passed', cases=len(cases), compiled_cpp=False)
        else:
            report['phase'] = 'production_contract'
            source = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
            dispatch.contract(source)
            protected[str(ROOT / 'src/app/app.cpp')] = sha((ROOT / 'src/app/app.cpp').read_bytes())
            incoming, actual, expected = (out / name for name in ('input.bin', 'actual.bin', 'expected.bin'))
            incoming.write_bytes(b'LZDU0001' + struct.pack('<I', len(cases)) + b''.join(row[0] for row in cases))
            expected.write_bytes(b''.join(row[1] for row in cases))
            report['phase'] = 'compiled_replay'
            child = subprocess.run([str(args.exe.resolve(strict=True)), '--debug-original-debris-update',
                str(incoming), str(actual)], cwd=ROOT, capture_output=True, text=True, timeout=90,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                         LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1'))
            report.update(child_exit_code=child.returncode, stdout=child.stdout, stderr=child.stderr)
            if child.returncode or child.stderr or child.stdout.strip() != 'original_debris_update=ok cases=276':
                raise ValueError('Compiled debris wrap replay did not complete')
            report['phase'] = 'compare'
            left, right = actual.read_bytes(), expected.read_bytes()
            report.update(actual_bytes=len(left), expected_bytes=len(right),
                actual_sha256=sha(left), expected_sha256=sha(right))
            compare(left, right)
            try:
                compare(bytes((left[0] ^ 1,)) + left[1:], right)
            except ValueError:
                pass
            else:
                raise ValueError('Debris wrap comparator accepted an output mutation')
            report.update(status='passed', cases=len(cases), output_mutants=1, compiled_cpp=True)
    except Exception as error:
        report['error'] = repr(error)
    finally:
        try:
            report['protected_inputs_preserved'] = (all(sha(Path(path).read_bytes()) == digest
                for path, digest in protected.items()) if protected else None)
            if report['protected_inputs_preserved'] is False:
                report.update(status='failed', preservation_error='Protected debris wrap input changed')
        except OSError as error:
            report.update(status='failed', protected_inputs_preserved=False, preservation_error=repr(error))
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    if report['status'] != 'passed':
        print('original_debris_wrap=failed artifacts=' + str(out) + ' error=' + report.get('error', 'preservation failure'))
        raise SystemExit(1)
    if args.oracle_only:
        print('original_debris_wrap_oracle=ok cases=276 native_crosschecks=18 compiled_cpp=0 natural_gameplay=0')
    else:
        print('original_debris_wrap=ok cases=276 native_crosschecks=18 rollover_counterexamples=108 output_mutants=1 natural_gameplay=0')
    print('debris_wrap_artifacts=' + str(out))


if __name__ == '__main__':
    main()
