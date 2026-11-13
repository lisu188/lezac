"""Compile production reward mutations and preserve their complete mismatches."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
SOURCE = Path('/tmp/lezac-reward-writeback-20261009-t92')
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
CAP = 8 * 1024**2
sys.path.insert(0, str(SOURCE / 'tools'))
from check_reward_storage_original import difference

MODEL, SLOTS = 'src/gameplay/actor_models.hpp', 'src/gameplay/actor_slots.hpp'
plans = [
    ('skip-animation', MODEL, 'result.animationAdvanced = drop.animation.advance(backup);', 'result.animationAdvanced = false;', None),
    ('skip-reward-write', SLOTS, 'const Descriptor& descriptor) {', 'const Descriptor& descriptor) { return;', 'writeReward'),
    ('overwrite-dimensions', SLOTS, 'if (animationAdvanced) { row[6] = descriptor[2]; row[7] = descriptor[3]; }',
        'if (animationAdvanced) { row[4] = descriptor[0]; row[5] = descriptor[1]; row[6] = descriptor[2]; row[7] = descriptor[3]; }', 'writeReward'),
    ('clear-backup', SLOTS, 'auto& raw = storage_.actor(require(order));',
        'auto& raw = storage_.actor(require(order)); std::fill(raw.begin() + 29, raw.begin() + 36, 0);', 'setSpriteDescriptor'),
    ('skip-sprite-conversion', SLOTS, 'void setSpriteDescriptor(uint64_t order, const Descriptor& descriptor) {',
        'void setSpriteDescriptor(uint64_t order, const Descriptor& descriptor) { return;', None),
    ('skip-transient-write', SLOTS, 'const Descriptor& descriptor) {', 'const Descriptor& descriptor) { return;', 'writeTransient'),
    ('one-player-only', MODEL, 'player < touching.size()', 'player < 1', None),
    ('block-second-player', MODEL, 'if (touching[player] && !pending[player])', 'if (touching[player] && !pending[player] && !collected)', None),
    ('ignore-pending-gate', MODEL, 'if (touching[player] && !pending[player])', 'if (touching[player])', None),
    ('pickup-skip-gravity', MODEL, 'motion(marker.x, y, marker.vx8, marker.vy8, marker.fracX, marker.fracY);', '/* skipped cached motion */', None),
    ('lose-pickup-fraction', MODEL, 'marker.fracX = drop.fracX;', 'marker.fracX = 0;', None),
    ('skip-pickup-mode-clear', MODEL, 'marker.animation.mode = 0;', '/* preserved incorrect mode */', None),
    ('wrong-expiry-sprite', MODEL, 'fade.spriteIndex = 73;', 'fade.spriteIndex = 68;', None),
    ('wrong-expiry-timer', MODEL, 'fade.timer = 18;', 'fade.timer = 0;', None),
    ('unphased-timer', MODEL, 'drop.timer = static_cast<uint8_t>(drop.timer - (tick & 1u));', 'drop.timer = static_cast<uint8_t>(drop.timer - 1);', None),
]
files = (MODEL, SLOTS, 'src/gameplay/actor_storage.hpp', 'src/core/fixed_point.hpp', 'src/core/random.hpp',
         'src/diagnostics/transient_storage_fixture.hpp', 'src/diagnostics/reward_storage_fixture.hpp', 'tests/gameplay/reward_storage_probe.cpp')
comparison = next(Path('/tmp/lezac-reward-writeback-helper-20261009-t92').glob('*/comparison.json'))
request = comparison.parent / 'requests.bin'
expected = gzip.decompress((SOURCE / 'tests/fixtures/reward_storage/expected.bin.gz').read_bytes())
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), mutants=[],
    actual_app_runtime_verified=False, complete_output_preserved_losslessly=True)


def sha(raw): return hashlib.sha256(raw).hexdigest()


def size(root): return sum(path.stat().st_size for path in root.rglob('*') if path.is_file())


try:
    assert not (VIS / 'reward-compiled-mutants-t92.json').exists()
    originals = {name: (SOURCE / name).read_bytes() for name in files}
    for label, filename, old, new, scope in plans:
        root = Path('/tmp/lezac-reward-mutant-' + label + '-20261009-t92')
        assert not root.exists() and shutil.disk_usage('/dev/shm').free > 1503238553
        root.mkdir()
        for name, raw in originals.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        path = root / filename
        text = path.read_text()
        start = text.index('    void ' + scope + '(') if scope else 0
        end = text.index('\n    void ', start + 1) if scope else len(text)
        body = text[start:end]
        assert body.count(old) == 1, (label, body.count(old))
        changed = text[:start] + body.replace(old, new) + text[end:]
        path.write_text(changed)
        commands = []
        for phase, args in (
            ('compile', ['c++', '-std=c++17', '-O1', '-I', root / 'src', root / 'tests/gameplay/reward_storage_probe.cpp', '-o', root / 'probe']),
            ('execute', [root / 'probe', request, root / 'actual.bin'])):
            result = subprocess.run(list(map(str, args)), cwd=root, env=ENV, capture_output=True, timeout=120)
            (root / (phase + '.stdout')).write_bytes(result.stdout)
            (root / (phase + '.stderr')).write_bytes(result.stderr)
            commands.append(dict(phase=phase, args=list(map(str, args)), returncode=result.returncode))
            assert result.returncode == 0, (label, phase, result.stderr[-2000:])
        actual_path = root / 'actual.bin'
        actual = actual_path.read_bytes()
        first = difference(actual, expected)
        assert first is not None and len(actual) == len(expected), ('surviving or incomplete mutant', label)
        packed = gzip.compress(actual, mtime=0)
        packed_path = root / 'actual.bin.gz'
        packed_path.write_bytes(packed)
        assert gzip.decompress(packed_path.read_bytes()) == actual and size(root) < CAP
        # Only this newly generated raw output is replaced by its verified lossless copy.
        assert actual_path.resolve().is_relative_to(root.resolve()) and not actual_path.is_symlink()
        actual_path.unlink()
        item = dict(name=label, root=str(root), compiled=True, complete_execution=True, rejected=True,
            first_difference=first, output_bytes=len(actual), raw_sha256=sha(actual), compressed_sha256=sha(packed),
            lossless_replacement_verified=True, changed_source_sha256=sha(path.read_bytes()), commands=commands)
        (root / 'comparison.json').write_text(json.dumps(item, indent=2, sort_keys=True) + '\n')
        assert size(root) < CAP
        report['mutants'].append(item)
        print(json.dumps(dict(mutant=label, rejected=True, first_difference=first, retained_bytes=size(root))), flush=True)
    assert all((SOURCE / name).read_bytes() == raw for name, raw in originals.items())
    report.update(passed=True, compiled_rejections=len(plans), source_unchanged=True)
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    (VIS / 'reward-compiled-mutants-t92.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(passed=report['passed'], rejections=len(report['mutants']), failure=report.get('failure'))), flush=True)
if not report['passed']: raise SystemExit(1)
