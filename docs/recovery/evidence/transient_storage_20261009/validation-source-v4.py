"""Bounded transient production-source validation, not an App runtime proof."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
STAGE = VIS / 'transient-writeback-source-t87'
ROOT = Path('/tmp/lezac-transient-writeback-20261009-t87')
BUILD = Path('/tmp/lezac-transient-writeback-checks-20261009-t88-v4')
CAP = 8 * 1024**2
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), source=str(ROOT),
    stage=str(STAGE), out=str(BUILD), producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    actual_app_runtime_verified=False, full_game_build=False, whole_game_claim=False, commands=[], source_sha256={})


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def size(root):
    return sum(path.stat().st_size for path in root.rglob('*') if path.is_file()) if root.exists() else 0


def guards():
    assert size(ROOT) < CAP and size(BUILD) < CAP
    assert shutil.disk_usage('/dev/shm').free > 1503238553


def run(label, arguments, timeout=120):
    guards()
    arguments = list(map(str, arguments))
    print(json.dumps(dict(starting=label)), flush=True)
    result = subprocess.run(arguments, cwd=ROOT, env=ENV, capture_output=True, timeout=timeout)
    (BUILD / (label + '.stdout')).write_bytes(result.stdout)
    (BUILD / (label + '.stderr')).write_bytes(result.stderr)
    row = dict(label=label, args=arguments, returncode=result.returncode,
        stdout_sha256=sha(result.stdout), stderr_sha256=sha(result.stderr))
    report['commands'].append(row)
    assert result.returncode == 0, (row, result.stdout[-2000:], result.stderr[-3000:])
    guards()
    return result.stdout.decode()


try:
    assert not BUILD.exists() and not (VIS / 'transient-writeback-validation-t88-v4.json').exists()
    BUILD.mkdir()
    guards()
    assert run('head', ['git', 'rev-parse', 'HEAD']).strip() == '4d3dbeee2db0194345475bcb47a9f76eedaf1bcc'
    evidence = STAGE / 'docs/recovery/evidence/transient_storage_20261009'
    fixtures = STAGE / 'tests/fixtures/transient_storage'
    evidence.mkdir(parents=True, exist_ok=True)
    fixtures.mkdir(parents=True, exist_ok=True)
    captures = [Path('/tmp/lezac-transient-storage-original-20261009-t88-v3'),
                Path('/tmp/lezac-transient-storage-repeat-20261009-t88-v4')]
    originals = [json.loads((root / 'original-transient-storage.json').read_text()) for root in captures]
    assert all(item['passed'] and item['operations'] == 256 and item['observer_neutrality_returns'] == 256 for item in originals)
    for name, root, item, producer in zip(('original', 'repeat'), captures, originals,
            (VIS / 'capture-transient-storage-t88-v3.py', VIS / 'capture-transient-storage-t88-v4.py')):
        assert sha(producer.read_bytes()) == item['producer_sha256']
        shutil.copyfile(root / 'original-transient-storage.json', evidence / (name + '.json'))
        shutil.copyfile(producer, evidence / (name + '-producer.py'))
    report['original_repeat_identity'] = {}
    for label in ('requests', 'expected'):
        packed = (captures[0] / (label + '.bin.gz')).read_bytes()
        assert packed == (captures[1] / (label + '.bin.gz')).read_bytes()
        raw = gzip.decompress(packed)
        assert all(sha(packed) == item[label]['sha256'] and sha(raw) == item[label]['raw_sha256'] for item in originals)
        shutil.copyfile(captures[0] / (label + '.bin.gz'), fixtures / (label + '.bin.gz'))
        (BUILD / (label + '.bin')).write_bytes(raw)
        report['original_repeat_identity'][label] = dict(compressed_sha256=sha(packed), raw_sha256=sha(raw), bytes=len(raw))
    for source, name, expected in (
        (Path('/dev/shm/lezac-oracle-current-main-20261008-t69/tools/original_bomb_cpu.py'),
         'original_bomb_cpu.py', originals[0]['helper_sha256']),
        (Path('/dev/shm/lezac-shared-crosscheck-main-20261009-t75/tools/check_original_shared_actor_native.py'),
         'native_reader.py', originals[0]['native_reader_sha256'])):
        assert sha(source.read_bytes()) == expected
        shutil.copyfile(source, evidence / name)
    paths = sorted(str(path.relative_to(STAGE)) for path in STAGE.rglob('*') if path.is_file())
    run('sparse-paths', ['git', 'sparse-checkout', 'add', *('/' + path for path in paths)])
    for relative in paths:
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STAGE / relative, target)
        report['source_sha256'][relative] = sha(target.read_bytes())
    run('diff-check', ['git', 'diff', '--check'])
    run('compile', ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-O1', '-I', ROOT / 'src',
                    ROOT / 'tests/gameplay/transient_storage_probe.cpp', '-o', BUILD / 'probe'])
    run('checker', ['python3', '-S', '-B', ROOT / 'tools/check_transient_storage_original.py',
                    '--exe', BUILD / 'probe', '--root', ROOT, '--out', BUILD / 'checker'])
    comparison_paths = list((BUILD / 'checker').glob('*/comparison.json'))
    assert len(comparison_paths) == 1
    comparison = json.loads(comparison_paths[0].read_text())
    assert comparison['passed'] and comparison['actual_sha256'] == originals[0]['expected']['raw_sha256']
    report['compiled_comparison'] = comparison
    run('compile-sanitized', ['c++', '-std=c++17', '-O1', '-g0', '-fsanitize=address,undefined',
        '-fno-omit-frame-pointer', '-I', ROOT / 'src', ROOT / 'tests/gameplay/transient_storage_probe.cpp',
        '-o', BUILD / 'probe-sanitized'])
    run('sanitized', [BUILD / 'probe-sanitized', BUILD / 'requests.bin', BUILD / 'sanitized.bin'])
    expected = (BUILD / 'expected.bin').read_bytes()
    assert (BUILD / 'sanitized.bin').read_bytes() == expected
    header = (ROOT / 'src/gameplay/actor_slots.hpp').read_text()
    models = (ROOT / 'src/gameplay/actor_models.hpp').read_text()
    mutations = {
        'skip-writeback': ('gameplay/actor_slots.hpp', header,
            'const Descriptor& descriptor) {\n        auto& raw', 'const Descriptor& descriptor) {\n        return;\n        auto& raw'),
        'rewrite-dimensions': ('gameplay/actor_slots.hpp', header,
            'if (animationAdvanced) { row[6] = descriptor[2]; row[7] = descriptor[3]; }',
            'if (animationAdvanced) std::copy(descriptor.begin(), descriptor.end(), row.begin() + 4);'),
        'clear-retired-tail': ('gameplay/actor_slots.hpp', header,
            'storage_.retire(slot);', 'storage_.retire(slot); auto wiped = storage_.state(); wiped.actors[oldCount].fill(0); storage_.restore(wiped);'),
        'truncate-negative-carry': ('gameplay/actor_models.hpp', models,
            'actor.x = static_cast<int16_t>(actor.x + (x >> 8));', 'actor.x = static_cast<int16_t>(actor.x + (x / 256));'),
    }
    report['compiled_mutants'] = []
    for name, (relative, source, old, new) in mutations.items():
        assert source.count(old) == 1
        folder = BUILD / name
        (folder / relative).parent.mkdir(parents=True)
        (folder / relative).write_text(source.replace(old, new))
        run(name + '-compile', ['c++', '-std=c++17', '-O1', '-I', folder, '-I', ROOT / 'src',
            ROOT / 'tests/gameplay/transient_storage_probe.cpp', '-o', folder / 'mutant'])
        run(name + '-run', [folder / 'mutant', BUILD / 'requests.bin', folder / 'actual.bin'])
        actual = (folder / 'actual.bin').read_bytes()
        assert actual != expected
        first = next(index for index, (a, b) in enumerate(zip(actual, expected)) if a != b)
        report['compiled_mutants'].append(dict(name=name, rejected=True, first_output_offset=first,
            operation=(first - 12) // 1575 + 1, state_offset=(first - 12) % 1575, actual_sha256=sha(actual)))
    run('checker-tools', ['python3', '-S', '-B', ROOT / 'tools/test_transient_storage_checker.py', '-v'])
    run('source-guardrails', ['python3', '-S', '-B', ROOT / 'tools/check_source_guardrails.py'])
    run('gran-guardrail', ['python3', '-S', '-B', ROOT / 'tools/check_gran_usage_guardrail.py'])
    run('app-syntax', ['c++', '-std=c++17', '-fsyntax-only', '-DSDL_MAIN_HANDLED', '-I/usr/include/SDL2',
        '-I', ROOT / 'src', ROOT / 'src/app/app.cpp'], timeout=240)
    run('configure', ['cmake', '-S', ROOT, '-B', BUILD / 'configure', '-G', 'Ninja',
        '-DBUILD_TESTING=ON', '-DCMAKE_BUILD_TYPE=Release'])
    tests = json.loads(run('test-registration', ['ctest', '--test-dir', BUILD / 'configure', '--show-only=json-v1',
        '-R', '^transient_storage_(helper_original|app_original|tools_contract)$']))['tests']
    assert {test['name'] for test in tests} == {'transient_storage_helper_original', 'transient_storage_app_original',
                                              'transient_storage_tools_contract'}
    for test in tests:
        props = {item['name']: item['value'] for item in test['properties']}
        assert 'SDL_AUDIODRIVER=dummy' in props['ENVIRONMENT']
    import yaml
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())
    for host in ('linux', 'windows'):
        steps = workflow['jobs'][host]['steps']
        index = next(i for i, step in enumerate(steps) if step.get('name') == 'Build')
        focused, retained = steps[index + 1:index + 3]
        assert focused['name'] == 'Complete transient physical storage regressions'
        assert focused['env']['SDL_AUDIODRIVER'] == 'dummy'
        assert 'transient_storage_(helper_original|app_original|tools_contract)' in focused['run']
        assert retained['if'] == 'always()' and retained['with']['name'] == f'transient-storage-{host}-focused'
        assert 'build/transient-storage-checks/' in retained['with']['path']
    report.update(passed=True, operations=256, compared_table_bytes=403200, sanitized_operations=256,
        compiled_mutants_rejected=4, app_syntax_verified=True, source_bytes=size(ROOT), build_bytes=size(BUILD))
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    report['source_bytes'] = size(ROOT)
    report['build_bytes'] = size(BUILD)
    report['cap_bytes'] = CAP
    (VIS / 'transient-writeback-validation-t88-v4.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=report['passed'], source_bytes=size(ROOT), build_bytes=size(BUILD),
        failure=report.get('failure'), mutants=report.get('compiled_mutants'))), flush=True)
if not report['passed']:
    raise SystemExit(1)
