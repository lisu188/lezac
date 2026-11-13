"""Copy reviewed source edits and compare a bounded compiled probe to native bytes."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
SOURCE = Path('/tmp/lezac-corpse-writeback-20261009-t94')
STAGE = VIS / 'corpse-writeback-source-t94'
OUT = Path('/tmp/lezac-corpse-writeback-validation-20261009-t94-v2')
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
assert not OUT.exists()
assert shutil.disk_usage('/dev/shm').free > 1503238553
OUT.mkdir()
pins = {}
for path in STAGE.rglob('*'):
    if path.is_file():
        relative = path.relative_to(STAGE)
        target = SOURCE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        pins[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
requests = gzip.decompress((SOURCE / 'tests/fixtures/corpse_storage/requests.bin.gz').read_bytes())
expected = gzip.decompress((SOURCE / 'tests/fixtures/corpse_storage/expected.bin.gz').read_bytes())
assert hashlib.sha256(requests).hexdigest() == '2f623d2a057425b71466c1b3fa75d5c6968a9f347a094c0fc034aa7b2a659790'
assert hashlib.sha256(expected).hexdigest() == '5ecc7a2666dc2444261d5332bfbdc8ea162df13fa6a9c92c9b27d31b3408febc'
(OUT / 'requests.bin').write_bytes(requests)


def run(label, args, timeout=120):
    result = subprocess.run(list(map(str, args)), cwd=SOURCE, env=ENV, capture_output=True, timeout=timeout)
    (OUT / (label + '.stdout')).write_bytes(result.stdout)
    (OUT / (label + '.stderr')).write_bytes(result.stderr)
    if result.returncode:
        print(result.stderr.decode(errors='replace')[-7000:], flush=True)
    assert result.returncode == 0, (label, result.returncode)
    return result


run('compile', ['c++', '-std=c++17', '-O1', '-g0', '-Wall', '-Wextra', '-pedantic', '-I', SOURCE / 'src',
    SOURCE / 'tests/gameplay/corpse_storage_probe.cpp', SOURCE / 'src/sound/sound_engine.cpp',
    SOURCE / 'src/resources/binary.cpp', '-o', OUT / 'probe'])
result = run('probe', [OUT / 'probe', OUT / 'requests.bin', OUT / 'actual.bin'])
actual = (OUT / 'actual.bin').read_bytes()
differences = [i for i, (a, b) in enumerate(zip(actual, expected)) if a != b]
report = dict(passed=actual == expected, recorded_utc=datetime.now(timezone.utc).isoformat(),
    operations=3252, cases=940, state_bytes=1593, compared_state_bytes=3252 * 1593,
    actual_bytes=len(actual), expected_bytes=len(expected), differing_bytes=len(differences),
    first_differences=[dict(offset=i, operation=(i-12)//1593, state_offset=(i-12)%1593,
        actual=actual[i], expected=expected[i]) for i in differences[:32]],
    actual_sha256=hashlib.sha256(actual).hexdigest(), expected_sha256=hashlib.sha256(expected).hexdigest(),
    source_pins=pins, helper_executed=True, actual_app_executed=False, masks_applied=False,
    whole_game_claim=False, source=str(SOURCE), validation_root=str(OUT),
    output=result.stdout.decode(), root_bytes=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()))
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
(VIS / 'corpse-writeback-validation-t94.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report), flush=True)
assert report['root_bytes'] < 8 * 1024**2
assert report['passed']
