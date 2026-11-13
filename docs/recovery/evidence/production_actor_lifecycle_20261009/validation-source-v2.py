"""Bounded source/compiled-binding validation; does not build or run the App."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
ROOT = Path('/tmp/lezac-actor-lifecycle-20261009-t85')
STAGE = VIS / 'actor-lifecycle-source-t85'
BUILD = Path('/tmp/lezac-actor-lifecycle-checks-20261009-t86-v2')
OUT = VIS / 'actor-lifecycle-validation-t86-v2.json'
PATHS = ('src/gameplay/actor_slots.hpp', 'tests/gameplay/actor_slots_test.cpp', 'src/app/app.cpp', 'CMakeLists.txt', 'tools/source_ownership.json')
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
report = dict(passed=False, commands=[], source_sha256={}, actual_app_runtime_verified=False,
              full_game_build=False, natural_route_claim=False, full_raw_record_owner=False, whole_game_claim=False)


def size(root):
    return sum(path.stat().st_size for path in root.rglob('*') if path.is_file())


def guards():
    assert size(ROOT) < 8 * 1024**2
    assert not BUILD.exists() or size(BUILD) < 8 * 1024**2
    assert shutil.disk_usage('/dev/shm').free > 1503238553


def run(command, timeout=120):
    guards()
    command = list(map(str, command))
    print(json.dumps(dict(starting=command)), flush=True)
    result = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=timeout)
    row = dict(args=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    report['commands'].append(row)
    guards()
    assert result.returncode == 0, row
    print(result.stdout, end='', flush=True)
    return result.stdout


try:
    assert not OUT.exists() and not BUILD.exists()
    guards()
    run(['git', 'sparse-checkout', 'add', *('/' + path for path in PATHS)])
    for relative in PATHS:
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STAGE / relative, target)
        report['source_sha256'][relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    BUILD.mkdir()
    run(['git', 'diff', '--check'])
    run(['c++', '-std=c++17', '-O1', '-Wall', '-Wextra', '-Werror', '-I', ROOT / 'src',
         ROOT / 'tests/gameplay/actor_slots_test.cpp', '-o', BUILD / 'actor-slots'])
    run([BUILD / 'actor-slots'])
    run(['c++', '-std=c++17', '-O1', '-g0', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
         '-I', ROOT / 'src', ROOT / 'tests/gameplay/actor_slots_test.cpp', '-o', BUILD / 'actor-slots-sanitized'])
    run([BUILD / 'actor-slots-sanitized'])
    header = (ROOT / 'src/gameplay/actor_slots.hpp').read_text()
    mutations = {
        'clear-new-backup': ('orders_[slot] = order;', 'orders_[slot] = order; std::fill(storage_.actor(slot).begin() + 29, storage_.actor(slot).begin() + 36, 0);'),
        'keep-deleted-order': ('orders_[index] = orders_[index + 1]', 'orders_[index] = orders_[index]'),
        'clear-retired-tail': ('storage_.retire(slot);', 'storage_.retire(slot); auto wiped = storage_.state(); wiped.actors[oldCount].fill(0); storage_.restore(wiped);'),
    }
    for name, (old, new) in mutations.items():
        assert header.count(old) == 1
        folder = BUILD / name
        (folder / 'gameplay').mkdir(parents=True)
        (folder / 'gameplay/actor_slots.hpp').write_text(header.replace(old, new))
        run(['c++', '-std=c++17', '-O1', '-I', folder, '-I', ROOT / 'src',
             ROOT / 'tests/gameplay/actor_slots_test.cpp', '-o', folder / 'mutant'])
        result = subprocess.run([folder / 'mutant'], cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=30)
        report['commands'].append(dict(args=[str(folder / 'mutant')], returncode=result.returncode,
                                       stdout=result.stdout, stderr=result.stderr, expected_failure=True))
        assert result.returncode == 1 and result.stderr.startswith('fatal: '), (name, result)
        print(json.dumps(dict(mutant=name, rejected=True, failure=result.stderr.strip())), flush=True)
    run(['python3', '-S', '-B', 'tools/check_source_guardrails.py'])
    run(['python3', '-S', '-B', 'tools/check_gran_usage_guardrail.py'])
    run(['c++', '-std=c++17', '-fsyntax-only', '-DSDL_MAIN_HANDLED', '-I/usr/include/SDL2',
         '-I', ROOT / 'src', ROOT / 'src/app/app.cpp'], timeout=240)
    run(['cmake', '-S', ROOT, '-B', BUILD / 'configure', '-G', 'Ninja', '-DBUILD_TESTING=ON', '-DCMAKE_BUILD_TYPE=Release'])
    tests = json.loads(run(['ctest', '--test-dir', BUILD / 'configure', '--show-only=json-v1',
                           '-R', '^(actor_slots_binding_contract|production_actor_lifecycle_app)$']))['tests']
    assert {test['name'] for test in tests} == {'actor_slots_binding_contract', 'production_actor_lifecycle_app'}
    for test in tests:
        props = {prop['name']: prop['value'] for prop in test['properties']}
        assert 'SDL_AUDIODRIVER=dummy' in props['ENVIRONMENT']
    report.update(passed=True, binding_operations=1800, sanitized_binding_operations=1800,
                  compiled_binding_mutants_rejected=3, app_syntax_verified=True, root_bytes=size(ROOT), build_bytes=size(BUILD))
except Exception:
    report['failure'] = traceback.format_exc()
    raise
finally:
    report['recorded_utc'] = datetime.now(timezone.utc).isoformat()
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(report=str(OUT), passed=report['passed'])), flush=True)
