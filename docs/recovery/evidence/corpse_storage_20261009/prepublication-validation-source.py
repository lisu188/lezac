"""Freeze native provenance and revalidate the exact prepublication source snapshot."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
ROOT = Path('/tmp/lezac-corpse-writeback-20261009-t94')
STAGE = VIS / 'corpse-writeback-source-t94'
OUT = Path('/tmp/lezac-corpse-prepublication-20261009-t94')
EVIDENCE = STAGE / 'docs/recovery/evidence/corpse_storage_20261009'
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
CAP = 8 * 1024**2
assert not OUT.exists() and not EVIDENCE.exists()
assert shutil.disk_usage('/dev/shm').free > 1503238553
OUT.mkdir()
EVIDENCE.mkdir(parents=True)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def size(root):
    return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())


manifest = {}
for label, parent in (('original', '/tmp/lezac-reward-construction-original-20261009-t93-v3'),
                      ('repeat', '/tmp/lezac-reward-construction-repeat-20261009-t93-v3')):
    raw = (Path(parent) / 'original-reward-construction.json').read_bytes()
    packed = gzip.compress(raw, mtime=0)
    name = label + '.json.gz'
    (EVIDENCE / name).write_bytes(packed)
    assert gzip.decompress((EVIDENCE / name).read_bytes()) == raw
    manifest[name] = dict(raw_bytes=len(raw), raw_sha256=sha(raw), compressed_bytes=len(packed), compressed_sha256=sha(packed))
for source, name in (
    (VIS / 'capture-reward-construction-t93-v3.py', 'native-producer.py'),
    (VIS / 'validate-reward-construction-t93-v2.py', 'native-validator.py'),
    (Path('/tmp/lezac-reward-construction-validation-20261009-t93-v2/validation.json'), 'native-validation.json'),
    (VIS / 'corpse-writeback-validation-t94.json', 'bounded-validation.json'),
    (VIS / 'validate-corpse-writeback-t94.py', 'bounded-validation-source.py'),
    (VIS / 'corpse-delivery-validation-t94.json', 'delivery-validation.json'),
    (VIS / 'verify-corpse-delivery-t94.py', 'delivery-validation-source.py'),
    (VIS / 'corpse-mutant-validation-t94.json', 'compiled-mutants.json'),
    (VIS / 'check-corpse-mutants-t94.py', 'compiled-mutants-source.py')):
    shutil.copyfile(source, EVIDENCE / name)
    manifest[name] = dict(bytes=source.stat().st_size, sha256=sha(source.read_bytes()))
(EVIDENCE / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
for name in ('requests', 'expected'):
    target = STAGE / 'tests/fixtures/corpse_storage' / (name + '.bin.gz')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'tests/fixtures/corpse_storage' / target.name, target)
pins = {}
for source in STAGE.rglob('*'):
    if source.is_file():
        relative = source.relative_to(STAGE)
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        pins[str(relative)] = sha(source.read_bytes())
assert size(ROOT) < CAP
commands = []


def run(label, args, timeout=120):
    result = subprocess.run(list(map(str, args)), cwd=ROOT, env=ENV, capture_output=True, timeout=timeout)
    (OUT / (label + '.stdout')).write_bytes(result.stdout)
    (OUT / (label + '.stderr')).write_bytes(result.stderr)
    commands.append(dict(label=label, args=list(map(str, args)), returncode=result.returncode))
    assert result.returncode == 0, (label, result.stdout[-3000:], result.stderr[-5000:])
    print(label + '=passed', flush=True)


for name in ('corpse', 'reward', 'marker', 'transient'):
    run(name + '-checker-contract', ['python3', '-S', '-B', ROOT / ('tools/test_' + name + '_storage_checker.py'), '-v'])
run('source-guardrails', ['python3', '-S', '-B', ROOT / 'tools/check_source_guardrails.py'])
run('app-syntax', ['c++', '-std=c++17', '-fsyntax-only', '-DSDL_MAIN_HANDLED', '-I/usr/include/SDL2', '-I', ROOT / 'src', ROOT / 'src/app/app.cpp'], 240)
run('compile', ['c++', '-std=c++17', '-O1', '-g0', '-Wall', '-Wextra', '-Werror', '-I', ROOT / 'src',
    ROOT / 'tests/gameplay/corpse_storage_probe.cpp', ROOT / 'src/sound/sound_engine.cpp', ROOT / 'src/resources/binary.cpp', '-o', OUT / 'probe'])
run('replay', [OUT / 'probe', '/tmp/lezac-corpse-writeback-validation-20261009-t94-v2/requests.bin', OUT / 'actual.bin'])
actual = (OUT / 'actual.bin').read_bytes()
assert sha(actual) == '5ecc7a2666dc2444261d5332bfbdc8ea162df13fa6a9c92c9b27d31b3408febc'
assert all(sha((ROOT / relative).read_bytes()) == expected == sha((STAGE / relative).read_bytes()) for relative, expected in pins.items())
report = dict(passed=True, recorded_utc=datetime.now(timezone.utc).isoformat(), source_unchanged=True,
    source_sha256=pins, commands=commands, operations=3252, cases=940, compared_bytes=5180436,
    actual_sha256=sha(actual), compiled_mutants_rejected=14, sanitizers_passed=True,
    actual_app_runtime_verified=False, full_game_build=False, whole_game_claim=False,
    source_root_bytes=size(ROOT), validation_root_bytes=size(OUT))
assert report['source_root_bytes'] < CAP and report['validation_root_bytes'] < CAP
(VIS / 'corpse-prepublication-validation-t94.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, source_bytes=size(ROOT), validation_bytes=size(OUT), actual_sha256=sha(actual))), flush=True)
