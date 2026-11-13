"""Bounded native fixture/helper and production-source validation."""
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
ROOT = Path('/tmp/lezac-marker-writeback-20261009-t90')
STAGE = VIS / 'marker-writeback-source-t90'
BUILD = Path('/tmp/lezac-marker-writeback-checks-20261009-t90-v3')
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
    assert not BUILD.exists() and not (VIS / 'marker-writeback-validation-t90-v3.json').exists()
    BUILD.mkdir()
    guards()
    assert run('head', ['git', 'rev-parse', 'HEAD']).strip() == 'e4eec22870b9e475e2346414a7a3bbb5821f07ce'
    evidence = STAGE / 'docs/recovery/evidence/marker_storage_20261009'
    fixtures = STAGE / 'tests/fixtures/marker_storage'
    evidence.mkdir(parents=True, exist_ok=True)
    fixtures.mkdir(parents=True, exist_ok=True)
    captures = [Path('/tmp/lezac-marker-storage-' + part + '-20261009-t90-v3') for part in ('original', 'repeat')]
    originals = [json.loads((root / 'original-marker-storage.json').read_text()) for root in captures]
    assert all(item['passed'] and item['operations'] == 1008 and item['observer_neutrality_returns'] == 1008 for item in originals)
    producer = VIS / 'capture-marker-storage-t90-v3.py'
    assert all(sha(producer.read_bytes()) == item['producer_sha256'] for item in originals)
    shutil.copyfile(producer, evidence / 'producer.py')
    for name, root in zip(('original', 'repeat'), captures):
        shutil.copyfile(root / 'original-marker-storage.json', evidence / (name + '.json'))
    report['original_repeat_identity'] = {}
    for label in ('requests', 'expected'):
        packed = (captures[0] / (label + '.bin.gz')).read_bytes()
        assert packed == (captures[1] / (label + '.bin.gz')).read_bytes()
        raw = gzip.decompress(packed)
        assert all(sha(packed) == item[label]['sha256'] and sha(raw) == item[label]['raw_sha256'] for item in originals)
        shutil.copyfile(captures[0] / (label + '.bin.gz'), fixtures / (label + '.bin.gz'))
        report['original_repeat_identity'][label] = dict(compressed_sha256=sha(packed), raw_sha256=sha(raw), bytes=len(raw))
    paths = sorted(str(path.relative_to(STAGE)) for path in STAGE.rglob('*') if path.is_file())
    run('sparse-paths', ['git', 'sparse-checkout', 'add', *('/' + path for path in paths)])
    for relative in paths:
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STAGE / relative, target)
        report['source_sha256'][relative] = sha(target.read_bytes())
    run('diff-check', ['git', 'diff', '--check'])
    run('compile', ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-O1', '-I', ROOT / 'src',
                    ROOT / 'tests/gameplay/marker_storage_probe.cpp', '-o', BUILD / 'probe'])
    run('checker', ['python3', '-S', '-B', ROOT / 'tools/check_marker_storage_original.py',
                    '--exe', BUILD / 'probe', '--root', ROOT, '--out', BUILD / 'checker'])
    comparison_paths = list((BUILD / 'checker').glob('*/comparison.json'))
    assert len(comparison_paths) == 1
    comparison = json.loads(comparison_paths[0].read_text())
    assert comparison['passed'] and comparison['actual_sha256'] == originals[0]['expected']['raw_sha256']
    report['compiled_comparison'] = comparison
    run('compile-sanitized', ['c++', '-std=c++17', '-O1', '-g0', '-fsanitize=address,undefined',
        '-fno-omit-frame-pointer', '-I', ROOT / 'src', ROOT / 'tests/gameplay/marker_storage_probe.cpp',
        '-o', BUILD / 'probe-sanitized'])
    run('sanitized', [BUILD / 'probe-sanitized', comparison_paths[0].parent / 'requests.bin', BUILD / 'sanitized.bin'])
    assert (BUILD / 'sanitized.bin').read_bytes() == (comparison_paths[0].parent / 'expected.bin').read_bytes()
    run('source-guardrails', ['python3', '-S', '-B', ROOT / 'tools/check_source_guardrails.py'])
    run('gran-guardrail', ['python3', '-S', '-B', ROOT / 'tools/check_gran_usage_guardrail.py'])
    report['deferred_existing_launch_guard'] = dict(passed=False, executed=False, reason='disk reserve and 10,292,004B original text fixtures; remains required in CI')
    run('checker-tools', ['python3', '-S', '-B', ROOT / 'tools/test_marker_storage_checker.py', '-v'])
    run('app-syntax', ['c++', '-std=c++17', '-fsyntax-only', '-DSDL_MAIN_HANDLED', '-I/usr/include/SDL2',
        '-I', ROOT / 'src', ROOT / 'src/app/app.cpp'], timeout=240)
    run('configure', ['cmake', '-S', ROOT, '-B', BUILD / 'configure', '-G', 'Ninja',
        '-DBUILD_TESTING=ON', '-DCMAKE_BUILD_TYPE=Release'])
    tests = json.loads(run('registration', ['ctest', '--test-dir', BUILD / 'configure', '--show-only=json-v1',
        '-R', '^marker_storage_(helper_original|app_original|tools_contract)$']))['tests']
    assert {test['name'] for test in tests} == {'marker_storage_helper_original', 'marker_storage_app_original', 'marker_storage_tools_contract'}
    for test in tests:
        props = {item['name']: item['value'] for item in test['properties']}
        assert 'SDL_AUDIODRIVER=dummy' in props['ENVIRONMENT']
    import yaml
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())
    for host in ('linux', 'windows'):
        steps = workflow['jobs'][host]['steps']
        index = next(i for i, step in enumerate(steps) if step.get('name') == 'Build')
        focused, retained = steps[index + 1:index + 3]
        assert focused['name'] == 'Complete marker physical storage regressions'
        assert focused['env']['SDL_AUDIODRIVER'] == 'dummy'
        assert 'marker_storage_(helper_original|app_original|tools_contract)' in focused['run']
        assert retained['if'] == 'always()' and retained['with']['name'] == f'marker-storage-{host}-focused'
        assert 'build/marker-storage-checks/' in retained['with']['path']
    report.update(passed=True, operations=1008, compared_table_bytes=1587600, sanitized_operations=1008,
        app_syntax_verified=True, source_bytes=size(ROOT), build_bytes=size(BUILD))
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    report['source_bytes'] = size(ROOT)
    report['build_bytes'] = size(BUILD)
    report['cap_bytes'] = CAP
    (VIS / 'marker-writeback-validation-t90-v3.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=report['passed'], source_bytes=size(ROOT), build_bytes=size(BUILD),
        failure=report.get('failure'))), flush=True)
if not report['passed']:
    raise SystemExit(1)
