"""Freeze reward proof and revalidate the exact source prepared for publication."""
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
STAGE = VIS / 'reward-writeback-source-t92'
ROOT = Path('/tmp/lezac-reward-writeback-20261009-t92')
BUILD = Path('/tmp/lezac-reward-prepublish-build-20261009-t92')
OUTPUT = Path('/tmp/lezac-reward-prepublish-output-20261009-t92')
OUT = VIS / 'reward-prepublication-validation-t92.json'
CAP = 8 * 1024**2
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), commands=[],
    actual_app_runtime_verified=False, whole_game_claim=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def size(root):
    return sum(path.stat().st_size for path in root.rglob('*') if path.is_file()) if root.exists() else 0


def run(label, *args, timeout=120):
    assert all(size(root) < CAP for root in (ROOT, BUILD, OUTPUT))
    assert shutil.disk_usage('/dev/shm').free > 1503238553
    result = subprocess.run(list(map(str, args)), cwd=ROOT, env=ENV, capture_output=True, timeout=timeout)
    (BUILD / (label + '.stdout')).write_bytes(result.stdout)
    (BUILD / (label + '.stderr')).write_bytes(result.stderr)
    report['commands'].append(dict(label=label, args=list(map(str, args)), returncode=result.returncode))
    assert result.returncode == 0, (label, result.stdout[-2000:], result.stderr[-3000:])
    return result.stdout


try:
    assert not OUT.exists() and not BUILD.exists() and not OUTPUT.exists()
    BUILD.mkdir(); OUTPUT.mkdir()
    validation = json.loads((VIS / 'reward-writeback-validation-t92.json').read_bytes())
    delivery = json.loads((VIS / 'reward-delivery-validation-t92-v2.json').read_bytes())
    mutants = json.loads((VIS / 'reward-compiled-mutants-t92.json').read_bytes())
    assert validation['passed'] and validation['operations'] == 4982 and validation['sanitized_operations'] == 4982
    assert delivery['passed'] and delivery['malformed_compiled_requests_rejected'] == 34
    assert delivery['reward_tests_registered'] == 5 and delivery['both_ci_hosts_wired']
    assert mutants['passed'] and mutants['compiled_rejections'] == 15 and mutants['source_unchanged']
    evidence = STAGE / 'docs/recovery/evidence/reward_storage_20261009'
    frozen = (
        ('reward-writeback-validation-t92.json', 'bounded-validation.json'),
        ('validate-reward-writeback-t92.py', 'bounded-validation-source.py'),
        ('reward-delivery-validation-t92-v2.json', 'delivery-validation.json'),
        ('verify-reward-delivery-t92-v2.py', 'delivery-validation-source.py'),
        ('reward-compiled-mutants-t92.json', 'compiled-mutants.json'),
        ('check-reward-mutants-t92.py', 'compiled-mutants-source.py'),
    )
    for source, name in frozen:
        target = evidence / name
        assert not target.exists()
        shutil.copyfile(VIS / source, target)
    paths = sorted(str(path.relative_to(STAGE)) for path in STAGE.rglob('*') if path.is_file())
    report['source_sha256'] = {relative: sha((STAGE / relative).read_bytes()) for relative in paths}
    run('sparse-paths', 'git', 'sparse-checkout', 'add', *('/' + relative for relative in paths))
    for relative in paths:
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STAGE / relative, target)
    run('diff-check', 'git', 'diff', '--check')
    run('compile', 'c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-O1', '-I', ROOT / 'src',
        ROOT / 'tests/gameplay/reward_storage_probe.cpp', '-o', BUILD / 'probe')
    requests = next(Path('/tmp/lezac-reward-writeback-helper-20261009-t92').glob('*/requests.bin'))
    stdout = run('execute', BUILD / 'probe', requests, OUTPUT / 'actual.bin')
    assert stdout.splitlines() == [b'reward_storage_probe=ok operations=4982']
    expected = gzip.decompress((ROOT / 'tests/fixtures/reward_storage/expected.bin.gz').read_bytes())
    actual = (OUTPUT / 'actual.bin').read_bytes()
    assert actual == expected
    run('checker-contract', 'python3', '-S', '-B', ROOT / 'tools/test_reward_storage_checker.py', '-v')
    run('source-guardrails', 'python3', '-S', '-B', ROOT / 'tools/check_source_guardrails.py')
    run('gran-guardrail', 'python3', '-S', '-B', ROOT / 'tools/check_gran_usage_guardrail.py')
    run('app-syntax', 'c++', '-std=c++17', '-fsyntax-only', '-DSDL_MAIN_HANDLED', '-I/usr/include/SDL2',
        '-I', ROOT / 'src', ROOT / 'src/app/app.cpp', timeout=240)
    for relative, expected_sha in report['source_sha256'].items():
        assert sha((ROOT / relative).read_bytes()) == expected_sha
        assert sha((STAGE / relative).read_bytes()) == expected_sha
    report.update(passed=True, operations=4982, compared_bytes=7896470, actual_sha256=sha(actual),
        executable_sha256=sha((BUILD / 'probe').read_bytes()), source_unchanged=True,
        requests_sha256=sha(requests.read_bytes()), frozen_reports={name: sha((evidence / name).read_bytes()) for _, name in frozen})
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    report['root_bytes'] = {str(root): size(root) for root in (ROOT, BUILD, OUTPUT)}
    assert all(count < CAP for count in report['root_bytes'].values())
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(passed=report['passed'], operations=report.get('operations'),
        roots=report['root_bytes'], failure=report.get('failure'))), flush=True)
if not report['passed']:
    raise SystemExit(1)
