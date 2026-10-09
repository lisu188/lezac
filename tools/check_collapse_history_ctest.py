"""Check real history CTest registrations and fail-closed exit-status behavior."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

CASES = {
    'collapse_seed_history_original': (90, 'check_collapse_seed_history.py',
        'collapse_seed_history_original=ok cases=576 production_app=1 masks=0 natural_gameplay=0 whole_game_claim=0', ()),
    'collapse_lane_history_original': (120, 'check_collapse_lane_history.py',
        'collapse_lane_history_original=ok cases=96 production_app=1 input_only=1 masks=0 natural_route=0 whole_game_claim=0', ()),
    'collapse_support_history_original': (120, 'check_collapse_lane_history.py',
        'collapse_support_history_original=ok cases=96 production_app=1 input_only=1 masks=0 natural_route=0 whole_game_claim=0',
        ('--profile', 'support')),
    'collapse_continuity_original': (240, 'check_collapse_continuity.py',
        'collapse_continuity_original=ok batches=8 cases=768 production_app=1 input_only=1 masks=0 natural_route=0 whole_game_claim=0', ()),
}
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')


def validate(rows):
    if {row['name'] for row in rows} != set(CASES) or len(rows) != len(CASES):
        raise ValueError('history CTest registration set differs')
    for row in rows:
        timeout, script, _, options = CASES[row['name']]
        properties = {value['name']: value['value'] for value in row['properties']}
        if (any(name in properties for name in ('PASS_REGULAR_EXPRESSION', 'FAIL_REGULAR_EXPRESSION',
                'SKIP_REGULAR_EXPRESSION', 'SKIP_RETURN_CODE', 'WILL_FAIL', 'DISABLED'))
                or properties.get('TIMEOUT') != timeout):
            raise ValueError('history CTest must preserve strict checker exit status')
        command = row.get('command', [])
        offset = 4 + len(options)
        if (len(command) != offset + 4 or command[1:3] != ['-S', '-B'] or Path(command[3]).name != script
                or command[4:offset] != list(options) or command[offset] != '--exe' or command[offset + 2] != '--out'):
            raise ValueError('history CTest command does not call the strict production checker')
        environment = properties.get('ENVIRONMENT', [])
        if any(value not in environment for value in
               ('SDL_AUDIODRIVER=dummy', 'SDL_VIDEODRIVER=dummy', 'PYTHONDONTWRITEBYTECODE=1')):
            raise ValueError('history CTest execution is not silent')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ctest-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='attempt-', dir=args.out))
    report = dict(passed=False, mocked_checker=True, production_app_executed=False,
                  natural_gameplay=False, whole_game_claim=False, commands=[])

    def run(label, command, expected=0):
        result = subprocess.run(command, capture_output=True, timeout=30, env=ENV)
        (out / (label + '.stdout')).write_bytes(result.stdout)
        (out / (label + '.stderr')).write_bytes(result.stderr)
        report['commands'].append(dict(label=label, returncode=result.returncode, expected_returncode=expected))
        if result.returncode != expected:
            raise ValueError('history CTest behavior differs: ' + label)
        return result.stdout

    try:
        raw = run('registration', ['ctest', '--test-dir', str(args.ctest_dir.resolve()), '--show-only=json-v1',
                                  '-R', '^collapse_((seed|lane|support)_history|continuity)_original$'])
        rows = json.loads(raw)['tests']
        validate(rows)
        mutants = 0
        for name in CASES:
            for prop, value in (('PASS_REGULAR_EXPRESSION', 'marker'), ('WILL_FAIL', True),
                                ('SKIP_RETURN_CODE', 1), ('DISABLED', True)):
                variant = json.loads(json.dumps(rows))
                next(row for row in variant if row['name'] == name)['properties'].append(dict(name=prop, value=value))
                try:
                    validate(variant)
                except ValueError:
                    mutants += 1
                else:
                    raise ValueError('history CTest registration mutant was accepted')
        helper = out / 'mocked_checker.py'
        helper.write_text('import sys\n'
            'if sys.argv[2] == "prefixed_success": print("retained=mocked-not-a-game")\n'
            'print(sys.argv[1])\n'
            'raise SystemExit(1 if sys.argv[2] == "plain_failure" else 0)\n')

        def quote(value):
            return '"' + str(value).replace('\\', '/').replace('"', '\\"') + '"'

        registrations = []
        wanted = []
        for name, (timeout, _, marker, _) in CASES.items():
            for policy in ('old_anchored_regex', 'strict_exit'):
                for mode in ('plain_success', 'prefixed_success', 'plain_failure'):
                    identifier = name + '_' + policy + '_' + mode
                    command = [sys.executable, '-S', '-B', helper, marker, mode]
                    registrations.append('add_test(' + quote(identifier) + ' ' + ' '.join(map(quote, command)) + ')')
                    registrations.append('set_tests_properties(' + quote(identifier) + ' PROPERTIES TIMEOUT ' + str(timeout) +
                        (' PASS_REGULAR_EXPRESSION ' + quote('^' + marker) if policy == 'old_anchored_regex' else '') + ')')
                    # Old policy rejects a valid prefixed marker and ignores a failing exit after a plain marker.
                    expected = (8 if mode == 'prefixed_success' else 0) if policy == 'old_anchored_regex' else (8 if mode == 'plain_failure' else 0)
                    wanted.append((identifier, expected))
        (out / 'CTestTestfile.cmake').write_text('\n'.join(registrations) + '\n')
        for identifier, expected in wanted:
            run(identifier, ['ctest', '--test-dir', str(out), '--output-on-failure', '-R', '^' + identifier + '$'], expected)
        report.update(passed=True, registrations_verified=len(CASES), registration_mutants=mutants,
                      mocked_ctest_cases=len(wanted), production_checker_commands_preserved=True)
    except BaseException as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print('collapse_history_ctest_retained=' + str(out.resolve()), flush=True)
        if sum(path.stat().st_size for path in args.out.rglob('*') if path.is_file()) >= 8 * 1024**2:
            raise ValueError('history CTest diagnostics exceed local reserve')
    print('collapse_history_ctest_contract=ok registrations=' + str(len(CASES)) + ' registration_mutants=' +
          str(mutants) + ' mocked_ctest_cases=' + str(len(wanted)) + ' production_app=0')


if __name__ == '__main__':
    main()
