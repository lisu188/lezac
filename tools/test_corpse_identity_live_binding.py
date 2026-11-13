"""Test input binding with real compiled App children, never fabricated results."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import traceback
from types import ModuleType
from unittest.mock import patch

ASSETS = ('BOMOMIMK.SPR', 'BOMPAL.PAL', 'CARO.CAR', 'FONTS.SPR', 'GRAN.MST',
    'LIVELS.SCH', 'PROEFS.SON', 'PROVA.SPR', 'RECS.DAT', 'SFONLEF.ZBG')
CAP = 8 * 1024**2


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run_checks(exe, fixture, output, mutant=None):
    output.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='run-', dir=output))
    report = dict(passed=False, cases=[], audio='dummy', compiled_baseline=True,
        compiled_mutant=mutant is not None, child_results_fabricated=False,
        original_fixture_modified=False, full_game_claim=False,
        recorded_utc=datetime.now(timezone.utc).isoformat())
    report['retained_attempt'] = str(output.resolve())
    try:
        checker_path = Path(__file__).with_name('check_corpse_identity_mutant.py')
        checker_source = checker_path.read_bytes()
        assert len(checker_source) < 64 * 1024
        checker = ModuleType('bound_corpse_identity_checker')
        checker.__file__ = str(checker_path)
        exec(compile(checker_source, str(checker_path), 'exec', dont_inherit=True), vars(checker))
        report['executed_checker_sha256'] = sha(checker_source)
        raw = checker.checked_bytes(fixture, 2 * 1024**2)
        assert sha(raw.replace(b'\r\n', b'\n')) == checker.FIXTURE_SHA256
        report['fixture_sha256'] = sha(raw)
        workspace = output / 'workspace'
        source = workspace / 'tests/fixtures/input.txt'
        source.parent.mkdir(parents=True)
        assets_root = fixture.resolve().parents[2]
        report['assets_sha256'] = {}
        for name in ASSETS:
            original = (assets_root / name).read_bytes()
            assert len(original) < 256 * 1024
            (workspace / name).write_bytes(original)
            report['assets_sha256'][name] = sha(original)
        real_run = subprocess.run

        def one_case(name, binary, replace_executed, expect_app_pass, expect_checker_pass):
            source.write_bytes(raw)
            observed = []
            retained = output / name
            row = dict(name=name, binary_path=str(binary.resolve()),
                expected_app_pass=expect_app_pass, expected_checker_pass=expect_checker_pass)
            report['cases'].append(row)

            def execute(command, **kwargs):
                target = Path(command[2])
                if replace_executed:
                    target.write_bytes(b'changed executed fixture\n')
                else:
                    source.write_bytes(b'changed caller fixture\n')
                result = real_run(command, **kwargs)
                observed.append(dict(command=command, returncode=result.returncode,
                    stdout=result.stdout.decode('utf-8', errors='replace'),
                    stderr=result.stderr.decode('utf-8', errors='replace'),
                    executed_path=str(target.resolve()), audio=kwargs['env']['SDL_AUDIODRIVER']))
                return result

            try:
                with patch.object(checker.subprocess, 'run', side_effect=execute):
                    result = checker.check(binary, source, retained)
                row['checker_passed'] = result['passed']
            except ValueError as error:
                row['checker_passed'] = False
                row['checker_error'] = str(error)
            row['actual_children'] = observed
            assert len(observed) == 1 and observed[0]['audio'] == 'dummy', row
            if expect_app_pass:
                assert observed[0]['returncode'] == 0 and 'shared_actor_order_original=ok' in observed[0]['stdout'], row
            else:
                assert observed[0]['returncode'] != 0, row
            assert row['checker_passed'] == expect_checker_pass, row
            if expect_checker_pass:
                assert 'unused birth identity' in observed[0]['stdout'] + observed[0]['stderr'], row
            elif replace_executed:
                assert 'retained fixture changed' in row['checker_error'], row
            else:
                assert 'specific unused birth' in row['checker_error'], row
            child_reports = list(retained.glob('case-*/report.json'))
            assert len(child_reports) == 1
            bound = json.loads(child_reports[0].read_bytes())
            row['retained_report'] = str(child_reports[0])
            assert Path(bound['executed_fixture_path']) != source.resolve()
            assert Path(bound['executed_fixture_path']).resolve() == Path(observed[0]['executed_path'])
            assert (child_reports[0].parent / 'fixture.txt').read_bytes() == raw
            assert bound['fixture_sha256'] == sha(raw)
            if not replace_executed:
                assert Path(bound['executed_fixture_path']).read_bytes() == raw
                assert source.read_bytes() == b'changed caller fixture\n'
            row['passed'] = True
            assert sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) < CAP

        one_case('source-replaced-baseline', exe, False, True, False)
        if mutant is not None:
            one_case('source-replaced-mutant', mutant, False, False, True)
        one_case('executed-copy-replaced', mutant or exe, True, False, False)
        assert fixture.read_bytes() == raw
        assert all(sha((assets_root / name).read_bytes()) == expected
            for name, expected in report['assets_sha256'].items())
        report.update(passed=True, case_count=len(report['cases']),
            output_bytes=sum(p.stat().st_size for p in output.rglob('*') if p.is_file()))
        return report
    except BaseException:
        report['error'] = traceback.format_exc()
        raise
    finally:
        (output / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--mutant', type=Path)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = run_checks(args.exe, args.fixture, args.out, args.mutant)
    print(f'corpse_identity_live_binding=ok cases={report["case_count"]} compiled_baseline=1 '
          f'compiled_mutant={int(report["compiled_mutant"])} real_children=1 retained_input=1 audio=dummy whole_game_claim=0')


if __name__ == '__main__':
    main()
