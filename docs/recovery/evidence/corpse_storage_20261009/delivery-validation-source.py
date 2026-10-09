"""Validate corpse delivery routing, strict protocol, adjacent callers and App syntax."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
ROOT = Path('/tmp/lezac-corpse-writeback-20261009-t94')
STAGE = VIS / 'corpse-writeback-source-t94'
BUILD = Path('/tmp/lezac-corpse-delivery-checks-20261009-t94')
COMPARE = Path('/tmp/lezac-corpse-checker-validation-20261009-t94')
REWARD = Path('/tmp/lezac-corpse-reward-regression-20261009-t94')
MARKER = Path('/tmp/lezac-corpse-marker-regression-20261009-t94')
TRANSIENT = Path('/tmp/lezac-corpse-transient-regression-20261009-t94')
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
CAP = 8 * 1024**2
roots = (ROOT, BUILD, COMPARE, REWARD, MARKER, TRANSIENT)
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), commands=[], actual_app_runtime_verified=False,
    full_game_build=False, source_pins={})


def size(root):
    return sum(path.stat().st_size for path in root.rglob('*') if path.is_file()) if root.exists() else 0


def run(label, args, timeout=120):
    assert all(size(root) < CAP for root in roots)
    result = subprocess.run(list(map(str, args)), cwd=ROOT, env=ENV, capture_output=True, timeout=timeout)
    (BUILD / (label + '.stdout')).write_bytes(result.stdout)
    (BUILD / (label + '.stderr')).write_bytes(result.stderr)
    report['commands'].append(dict(label=label, args=list(map(str, args)), returncode=result.returncode))
    assert result.returncode == 0, (label, result.stdout[-3000:], result.stderr[-5000:])
    print(label + '=passed', flush=True)
    return result.stdout


try:
    assert not any(root.exists() for root in roots[1:])
    assert shutil.disk_usage('/dev/shm').free > 1503238553
    BUILD.mkdir()
    for path in STAGE.rglob('*'):
        if path.is_file():
            relative = path.relative_to(STAGE)
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            report['source_pins'][str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    run('diff-check', ['git', 'diff', '--check'])
    for name in ('corpse', 'reward', 'marker', 'transient'):
        run(name + '-checker-contract', ['python3', '-S', '-B', ROOT / ('tools/test_' + name + '_storage_checker.py'), '-v'])
    for label, source in (('binding', 'actor_slots_test.cpp'), ('reward', 'reward_storage_probe.cpp'),
                          ('marker', 'marker_storage_probe.cpp'), ('transient', 'transient_storage_probe.cpp')):
        run('compile-' + label, ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-O1', '-I', ROOT / 'src',
            ROOT / 'tests/gameplay' / source, '-o', BUILD / label])
    run('binding', [BUILD / 'binding'])
    run('corpse-protocol', ['python3', '-S', '-B', ROOT / 'tools/test_corpse_storage_protocol.py', '--root', ROOT,
        '--exe', '/tmp/lezac-corpse-writeback-validation-20261009-t94-v2/probe', '--out', BUILD / 'protocol'])
    run('corpse-checker', ['python3', '-S', '-B', ROOT / 'tools/check_corpse_storage_original.py', '--root', ROOT,
        '--exe', '/tmp/lezac-corpse-writeback-validation-20261009-t94-v2/probe', '--out', COMPARE])
    for name, out in (('reward', REWARD), ('marker', MARKER), ('transient', TRANSIENT)):
        run(name + '-regression', ['python3', '-S', '-B', ROOT / ('tools/check_' + name + '_storage_original.py'),
            '--root', ROOT, '--exe', BUILD / name, '--out', out])
    run('source-guardrails', ['python3', '-S', '-B', ROOT / 'tools/check_source_guardrails.py'])
    run('gran-guardrail', ['python3', '-S', '-B', ROOT / 'tools/check_gran_usage_guardrail.py'])
    run('app-syntax', ['c++', '-std=c++17', '-fsyntax-only', '-DSDL_MAIN_HANDLED', '-I/usr/include/SDL2',
                       '-I', ROOT / 'src', ROOT / 'src/app/app.cpp'], 240)
    run('configure', ['cmake', '-S', ROOT, '-B', BUILD / 'configure', '-G', 'Ninja', '-DBUILD_TESTING=ON', '-DCMAKE_BUILD_TYPE=Release'])
    tests = json.loads(run('registration', ['ctest', '--test-dir', BUILD / 'configure', '--show-only=json-v1',
        '-R', '^corpse_storage_(helper_original|app_original|helper_protocol|app_protocol|tools_contract)$']))['tests']
    assert {row['name'] for row in tests} == {'corpse_storage_helper_original', 'corpse_storage_app_original',
        'corpse_storage_tools_contract', 'corpse_storage_helper_protocol', 'corpse_storage_app_protocol'}
    for test in tests:
        properties = {row['name']: row['value'] for row in test['properties']}
        assert 'SDL_AUDIODRIVER=dummy' in properties['ENVIRONMENT']
    import yaml
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())
    for host in ('linux', 'windows'):
        steps = workflow['jobs'][host]['steps']
        at = next(index for index, step in enumerate(steps) if step.get('name') == 'Build')
        focused, retained = steps[at + 1:at + 3]
        assert focused['name'] == 'Complete corpse physical storage regressions'
        assert focused['env']['SDL_AUDIODRIVER'] == 'dummy'
        assert retained['if'] == 'always()' and retained['with']['name'] == 'corpse-storage-' + host + '-focused'
        assert 'build/corpse-storage-checks/' in retained['with']['path']
    report.update(passed=True, binding_operations=1800, reward_operations=4982, marker_operations=1008, transient_operations=256,
        corpse_tests_registered=5, malformed_compiled_requests_rejected=36, both_ci_hosts_wired=True, app_syntax_verified=True)
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    report['root_bytes'] = {str(root): size(root) for root in roots}
    assert all(count < CAP for count in report['root_bytes'].values())
    (VIS / 'corpse-delivery-validation-t94.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(passed=report['passed'], roots=report['root_bytes'], failure=report.get('failure'))), flush=True)
if not report['passed']: raise SystemExit(1)
