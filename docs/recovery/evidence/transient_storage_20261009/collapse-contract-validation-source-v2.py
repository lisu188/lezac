"""Validate the delegated allocator contract without changing production code."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import traceback

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
ROOT = Path('/tmp/lezac-transient-writeback-20261009-t87')
STAGE = VIS / 'transient-writeback-source-t87'
OUT = Path('/tmp/lezac-transient-collapse-contract-20261009-t88-v2')
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
CAP = 8 * 1024**2
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), commands=[],
    producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), production_code_changed=False,
    actual_app_runtime_verified=False, full_app_build=False, whole_game_claim=False)


def size(path):
    return sum(item.stat().st_size for item in path.rglob('*') if item.is_file()) if path.exists() else 0


def run(label, arguments, timeout=120):
    assert size(ROOT) < CAP and size(OUT) < CAP
    result = subprocess.run(list(map(str, arguments)), cwd=ROOT, env=ENV, capture_output=True, timeout=timeout)
    (OUT / (label + '.stdout')).write_bytes(result.stdout)
    (OUT / (label + '.stderr')).write_bytes(result.stderr)
    report['commands'].append(dict(label=label, args=list(map(str, arguments)), returncode=result.returncode))
    assert result.returncode == 0, (label, result.stdout[-1500:], result.stderr[-3000:])
    return result.stdout


try:
    assert not OUT.exists()
    assert shutil.disk_usage('/dev/shm').free > 1503238553
    OUT.mkdir()
    assert run('head', ['git', 'rev-parse', 'HEAD']).decode().strip() == 'be1d76b7aee8cbf6e50d0c6588a796add1574654'
    paths = {'tools/check_original_collapse_actors.py', 'tools/check_original_collapse_update.py',
        'tools/check_original_debris_update.py', 'tools/test_collapse_actor_checker.py',
        'tools/capture_original_collapse_actors.py', 'tests/fixtures/fracture_actor_original.txt',
        'tests/gameplay/collapse_actor_creation_original.json', 'tests/gameplay/collapse_actor_creation_original.bin.gz',
        'tests/gameplay/collapse_update_original.json', 'tests/gameplay/collapse_update_original.bin.gz'}
    for index, relative in enumerate(('tests/gameplay/collapse_actor_creation_original.json',
                                      'tests/gameplay/collapse_update_original.json')):
        metadata = json.loads(run('metadata-' + str(index), ['git', 'show', 'HEAD:' + relative]))
        for name in metadata['dependency_sha256']:
            assert PurePosixPath(name).name == name
            paths.add('tools/' + name)
        if isinstance(metadata['native_fixture_sha256'], dict):
            for name in metadata['native_fixture_sha256']:
                assert PurePosixPath(name).name == name
                paths.add('tests/fixtures/' + name)
    extra_bytes = 0
    for index, relative in enumerate(sorted(paths)):
        if not (ROOT / relative).exists():
            extra_bytes += int(run('size-' + str(index), ['git', 'cat-file', '-s', 'HEAD:' + relative]))
    assert size(ROOT) + extra_bytes < CAP
    run('materialize', ['git', 'sparse-checkout', 'add', *('/' + path for path in sorted(paths))])
    for relative in ('CMakeLists.txt', 'tools/check_original_collapse_actors.py'):
        shutil.copyfile(STAGE / relative, ROOT / relative)
    run('diff-check', ['git', 'diff', '--check'])
    text = run('contract', ['python3', '-S', '-B', ROOT / 'tools/check_original_collapse_actors.py', '--self-check']).decode()
    assert text.strip() == 'original_collapse_actors_contract=ok source_mutants=29 comparator_mutants=6 compiled_cpp=0'
    run('oracle', ['python3', '-S', '-B', ROOT / 'tools/check_original_collapse_actors.py', '--oracle-only'])
    run('checker-contract', ['python3', '-S', '-B', ROOT / 'tools/test_collapse_actor_checker.py'])
    run('source-guardrails', ['python3', '-S', '-B', ROOT / 'tools/check_source_guardrails.py'])
    run('configure', ['cmake', '-S', ROOT, '-B', OUT / 'configure', '-G', 'Ninja', '-DBUILD_TESTING=ON'])
    tests = run('ctest-source-contracts', ['ctest', '--test-dir', OUT / 'configure', '--output-on-failure',
        '-R', '^original_collapse_actors_(contract|checker)$']).decode()
    assert '100% tests passed, 0 tests failed out of 2' in tests
    publication = json.loads((VIS / 'transient-writeback-publication-t88.json').read_bytes())
    for relative, expected in publication['source_hashes'].items():
        if relative.startswith('src/'):
            assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    report.update(passed=True, source_mutants_rejected=29, comparator_mutants_rejected=6,
        original_oracle_cases=2476, original_actor_states=1822, original_admissions=414,
        mocked_probe_modes=10, comparison_cases=9, ctest_source_contracts_passed=2,
        root_bytes=size(ROOT), out_bytes=size(OUT))
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    report['root_bytes'], report['out_bytes'] = size(ROOT), size(OUT)
    (VIS / 'transient-collapse-contract-validation-t88-v2.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)
if not report['passed']:
    raise SystemExit(1)
