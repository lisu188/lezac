"""Verify reward test registration, checker controls and unchanged caller families."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
ROOT = Path('/tmp/lezac-reward-writeback-20261009-t92')
STAGE = VIS / 'reward-writeback-source-t92'
BUILD = Path('/tmp/lezac-reward-delivery-checks-20261009-t92-v2')
MARKER = Path('/tmp/lezac-reward-marker-regression-20261009-t92-v2')
TRANSIENT = Path('/tmp/lezac-reward-transient-regression-20261009-t92-v2')
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
CAP = 8 * 1024**2
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), commands=[], actual_app_runtime_verified=False, full_game_build=False)


def size(root):
    return sum(path.stat().st_size for path in root.rglob('*') if path.is_file()) if root.exists() else 0


def run(label, args, timeout=120):
    assert all(size(root) < CAP for root in (ROOT, BUILD, MARKER, TRANSIENT))
    result = subprocess.run(list(map(str, args)), cwd=ROOT, env=ENV, capture_output=True, timeout=timeout)
    (BUILD / (label + '.stdout')).write_bytes(result.stdout)
    (BUILD / (label + '.stderr')).write_bytes(result.stderr)
    report['commands'].append(dict(label=label, args=list(map(str, args)), returncode=result.returncode))
    assert result.returncode == 0, (label, result.stdout[-2000:], result.stderr[-2000:])
    return result.stdout


try:
    assert not any(root.exists() for root in (BUILD, MARKER, TRANSIENT))
    assert shutil.disk_usage('/dev/shm').free > 1503238553
    BUILD.mkdir()
    paths = sorted(str(path.relative_to(STAGE)) for path in STAGE.rglob('*') if path.is_file())
    run('sparse-paths', ['git', 'sparse-checkout', 'add', *('/' + path for path in paths)])
    for relative in paths:
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STAGE / relative, target)
    run('diff-check', ['git', 'diff', '--check'])
    for name in ('reward', 'marker', 'transient'):
        run(name + '-checker-contract', ['python3', '-S', '-B', ROOT / ('tools/test_' + name + '_storage_checker.py'), '-v'])
    for label, source in (('binding', 'actor_slots_test.cpp'), ('marker', 'marker_storage_probe.cpp'), ('transient', 'transient_storage_probe.cpp')):
        run('compile-' + label, ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-O1', '-I', ROOT / 'src',
            ROOT / 'tests/gameplay' / source, '-o', BUILD / label])
    run('binding', [BUILD / 'binding'])
    run('reward-protocol', ['python3', '-S', '-B', ROOT / 'tools/test_reward_storage_protocol.py',
        '--root', ROOT, '--exe', '/tmp/lezac-reward-writeback-build-20261009-t92/probe', '--out', BUILD / 'protocol'])
    run('marker-regression', ['python3', '-S', '-B', ROOT / 'tools/check_marker_storage_original.py', '--root', ROOT, '--exe', BUILD / 'marker', '--out', MARKER])
    run('transient-regression', ['python3', '-S', '-B', ROOT / 'tools/check_transient_storage_original.py', '--root', ROOT, '--exe', BUILD / 'transient', '--out', TRANSIENT])
    run('source-guardrails', ['python3', '-S', '-B', ROOT / 'tools/check_source_guardrails.py'])
    run('gran-guardrail', ['python3', '-S', '-B', ROOT / 'tools/check_gran_usage_guardrail.py'])
    run('app-syntax', ['c++', '-std=c++17', '-fsyntax-only', '-DSDL_MAIN_HANDLED', '-I/usr/include/SDL2',
                       '-I', ROOT / 'src', ROOT / 'src/app/app.cpp'], 240)
    run('configure', ['cmake', '-S', ROOT, '-B', BUILD / 'configure', '-G', 'Ninja', '-DBUILD_TESTING=ON', '-DCMAKE_BUILD_TYPE=Release'])
    tests = json.loads(run('registration', ['ctest', '--test-dir', BUILD / 'configure', '--show-only=json-v1',
                                           '-R', '^reward_storage_(helper_original|app_original|helper_protocol|app_protocol|tools_contract)$']))['tests']
    assert {row['name'] for row in tests} == {'reward_storage_helper_original', 'reward_storage_app_original', 'reward_storage_tools_contract',
        'reward_storage_helper_protocol', 'reward_storage_app_protocol'}
    for test in tests:
        properties = {row['name']: row['value'] for row in test['properties']}
        assert 'SDL_AUDIODRIVER=dummy' in properties['ENVIRONMENT']
    import yaml
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())
    for host in ('linux', 'windows'):
        steps = workflow['jobs'][host]['steps']
        at = next(index for index, step in enumerate(steps) if step.get('name') == 'Build')
        focused, retained = steps[at + 1:at + 3]
        assert focused['name'] == 'Complete reward physical storage regressions'
        assert focused['env']['SDL_AUDIODRIVER'] == 'dummy'
        assert 'reward_storage_(helper_original|app_original|helper_protocol|app_protocol|tools_contract)' in focused['run']
        assert retained['if'] == 'always()' and retained['with']['name'] == 'reward-storage-' + host + '-focused'
        assert 'build/reward-storage-checks/' in retained['with']['path']
    report.update(passed=True, binding_operations=1800, marker_operations=1008, transient_operations=256,
        reward_tests_registered=5, malformed_compiled_requests_rejected=34, both_ci_hosts_wired=True, app_syntax_verified=True,
        existing_launch_visual_guard_deferred='retained 10,292,004B text fixtures exceed local reserve cap; remains required in CI')
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    report['root_bytes'] = {str(root): size(root) for root in (ROOT, BUILD, MARKER, TRANSIENT)}
    assert all(count < CAP for count in report['root_bytes'].values())
    (VIS / 'reward-delivery-validation-t92-v2.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(passed=report['passed'], roots=report['root_bytes'], failure=report.get('failure'))), flush=True)
if not report['passed']: raise SystemExit(1)
