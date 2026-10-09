"""Bounded first compiled reward replay and App syntax validation."""
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
ROOT = Path('/tmp/lezac-reward-writeback-20261009-t92')
STAGE = VIS / 'reward-writeback-source-t92'
BUILD = Path('/tmp/lezac-reward-writeback-build-20261009-t92')
HELPER = Path('/tmp/lezac-reward-writeback-helper-20261009-t92')
SANITIZED = Path('/tmp/lezac-reward-writeback-sanitized-20261009-t92')
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
CAP = 8 * 1024**2
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), actual_app_runtime_verified=False,
    full_game_build=False, whole_game_claim=False, commands=[])


def size(root):
    return sum(path.stat().st_size for path in root.rglob('*') if path.is_file()) if root.exists() else 0


def run(label, args, timeout=120):
    assert all(size(root) < CAP for root in (ROOT, BUILD, HELPER, SANITIZED))
    assert shutil.disk_usage('/dev/shm').free > 1503238553
    result = subprocess.run(list(map(str, args)), cwd=ROOT, env=ENV, capture_output=True, timeout=timeout)
    (BUILD / (label + '.stdout')).write_bytes(result.stdout)
    (BUILD / (label + '.stderr')).write_bytes(result.stderr)
    report['commands'].append(dict(label=label, args=list(map(str, args)), returncode=result.returncode))
    assert result.returncode == 0, (label, result.stdout[-2000:], result.stderr[-3000:])
    return result.stdout


try:
    assert not BUILD.exists() and not HELPER.exists() and not SANITIZED.exists()
    BUILD.mkdir(); SANITIZED.mkdir()
    evidence = STAGE / 'docs/recovery/evidence/reward_storage_20261009'
    fixtures = STAGE / 'tests/fixtures/reward_storage'
    evidence.mkdir(parents=True); fixtures.mkdir(parents=True)
    originals = [Path('/tmp/lezac-reward-storage-' + name + '-20261009-t91-v3') for name in ('original', 'repeat')]
    for label in ('requests', 'expected'):
        raw = (originals[0] / (label + '.bin.gz')).read_bytes()
        assert raw == (originals[1] / (label + '.bin.gz')).read_bytes()
        (fixtures / (label + '.bin.gz')).write_bytes(raw)
    for name, source in zip(('original', 'repeat'), originals):
        shutil.copyfile(source / 'original-reward-storage.json', evidence / (name + '.json'))
    for name in ('capture-reward-storage-t91-v3.py', 'validate-reward-native-t91.py',
                 'reward-animation-probe-t91.cpp', 'validate-reward-animation-extra-t91.py'):
        shutil.copyfile(VIS / name, evidence / name)
    shutil.copyfile(VIS / 'reward-native-validation-t91.json', evidence / 'native-validation.json')
    shutil.copyfile(VIS / 'reward-animation-extra-validation-t91.json', evidence / 'animation-extra-validation.json')
    paths = sorted(str(path.relative_to(STAGE)) for path in STAGE.rglob('*') if path.is_file())
    run('sparse-paths', ['git', 'sparse-checkout', 'add', *('/' + path for path in paths)])
    for relative in paths:
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STAGE / relative, target)
    run('diff-check', ['git', 'diff', '--check'])
    run('compile', ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-O1', '-I', ROOT / 'src',
                    ROOT / 'tests/gameplay/reward_storage_probe.cpp', '-o', BUILD / 'probe'])
    run('checker', ['python3', '-S', '-B', ROOT / 'tools/check_reward_storage_original.py',
                    '--root', ROOT, '--exe', BUILD / 'probe', '--out', HELPER])
    comparisons = list(HELPER.glob('*/comparison.json'))
    assert len(comparisons) == 1
    comparison = json.loads(comparisons[0].read_bytes())
    assert comparison['passed'] and comparison['first_difference'] is None
    report['compiled_comparison'] = comparison
    run('compile-sanitized', ['c++', '-std=c++17', '-O1', '-g0', '-fsanitize=address,undefined',
        '-fno-omit-frame-pointer', '-I', ROOT / 'src', ROOT / 'tests/gameplay/reward_storage_probe.cpp', '-o', BUILD / 'probe-sanitized'])
    run('sanitized', [BUILD / 'probe-sanitized', comparisons[0].parent / 'requests.bin', SANITIZED / 'actual.bin'])
    expected = gzip.decompress((fixtures / 'expected.bin.gz').read_bytes())
    assert (SANITIZED / 'actual.bin').read_bytes() == expected
    run('source-guardrails', ['python3', '-S', '-B', ROOT / 'tools/check_source_guardrails.py'])
    run('gran-guardrail', ['python3', '-S', '-B', ROOT / 'tools/check_gran_usage_guardrail.py'])
    run('app-syntax', ['c++', '-std=c++17', '-fsyntax-only', '-DSDL_MAIN_HANDLED', '-I/usr/include/SDL2',
                       '-I', ROOT / 'src', ROOT / 'src/app/app.cpp'], 240)
    report.update(passed=True, operations=4982, compared_bytes=7896470, sanitized_operations=4982,
        app_syntax_verified=True, actual_output_sha256=hashlib.sha256(expected).hexdigest())
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    report['root_bytes'] = {str(root): size(root) for root in (ROOT, BUILD, HELPER, SANITIZED)}
    assert all(count < CAP for count in report['root_bytes'].values())
    (VIS / 'reward-writeback-validation-t92.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(passed=report['passed'], roots=report['root_bytes'], failure=report.get('failure'))), flush=True)
if not report['passed']:
    raise SystemExit(1)
