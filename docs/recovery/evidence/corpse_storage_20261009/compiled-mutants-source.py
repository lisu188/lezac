"""Run sanitizers and compiled production mutants against complete original states."""
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
REQUEST = Path('/tmp/lezac-corpse-writeback-validation-20261009-t94-v2/requests.bin')
EXPECTED = gzip.decompress((SOURCE / 'tests/fixtures/corpse_storage/expected.bin.gz').read_bytes())
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1',
           ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
CAP = 8 * 1024**2
assert shutil.disk_usage('/dev/shm').free > 1503238553
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), compiled_mutants=[],
    actual_app_runtime_verified=False, seeded=True, natural_route=False, whole_game_claim=False)
MODELS = 'src/gameplay/actor_models.hpp'
SLOTS = 'src/gameplay/actor_slots.hpp'
SOUND = 'src/sound/sound_engine.cpp'
variants = [
    ('timer-every-tick', MODELS, 'timer = static_cast<uint8_t>(timer - (tick & 1u));', 'timer = static_cast<uint8_t>(timer - 1);'),
    ('missing-255-sentinel', MODELS, 'const bool expired = timer == 0 || timer == 0xff;', 'const bool expired = timer == 0;'),
    ('missing-corpse-motion', MODELS, 'motion(corpse.x, corpse.y, corpse.vx8, corpse.vy8, corpse.fracX, corpse.fracY);', '(void)motion;'),
    ('exclusive-reward-bound', MODELS, 'roll > upperBounds[index]', 'roll >= upperBounds[index]'),
    ('reward-impulse', MODELS, 'corpse.vy8 - 200', 'corpse.vy8 - 199'),
    ('preserved-reward-mode', MODELS, 'reward.animation.mode = 0;', 'reward.animation.mode = corpse.animMode;'),
    ('fade-delay', MODELS, 'fade.animation = ActorAnimation::initialize(69, 79, 2, 1);', 'fade.animation = ActorAnimation::initialize(69, 79, 3, 1);'),
    ('corpse-visual-y', SLOTS, 'word(row, 2, static_cast<uint16_t>(corpse.y + corpse.hotspotY));', 'word(row, 2, static_cast<uint16_t>(corpse.y));'),
    ('corpse-animation-write', SLOTS, 'setActiveAnimation(order, monsterAnimation(corpse));', '/* missing physical animation */'),
    ('conversion-descriptor', SLOTS, 'setSpriteDescriptor(order, descriptor);', 'raw[20] = static_cast<uint8_t>(16 - descriptor[1]);'),
    ('conversion-fractions', SLOTS, '// 1000:766d..76f4 preserves coordinates, fractions, backup and opaque bytes.', 'std::fill(raw.begin() + 10, raw.begin() + 14, 0);'),
    ('conversion-backup', SLOTS, '// 1000:766d..76f4 preserves coordinates, fractions, backup and opaque bytes.', 'std::fill(raw.begin() + 29, raw.begin() + 36, 0);'),
    ('unsigned-priority', SOUND, 'static_cast<uint8_t>(previous ^ 0x80u) <\n                      static_cast<uint8_t>(selector ^ 0x80u)', 'previous < selector'),
    ('missing-request-globals', SOUND, '    requestCursor_ = cursor;\n    requestSelector_ = selector;', '    /* missing rejected request state */'),
]


def size(root):
    return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())


def execute(label, variant=None, sanitized=False):
    root = Path('/tmp/lezac-corpse-' + label + '-20261009-t94')
    assert not root.exists()
    root.mkdir()
    sound = SOURCE / SOUND
    if variant:
        relative, before, after = variant
        content = (SOURCE / relative).read_text()
        assert content.count(before) == 1, (label, content.count(before))
        target = root / relative
        target.parent.mkdir(parents=True)
        target.write_text(content.replace(before, after))
        if relative == SOUND:
            sound = target
    command = ['c++', '-std=c++17', '-O1', '-g0', '-I', str(root / 'src'), '-I', str(SOURCE / 'src'),
        str(SOURCE / 'tests/gameplay/corpse_storage_probe.cpp'), str(sound), str(SOURCE / 'src/resources/binary.cpp'), '-o', str(root / 'probe')]
    if sanitized:
        command[3:3] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    compiled = subprocess.run(command, cwd=SOURCE, env=ENV, capture_output=True, timeout=120)
    (root / 'compile.stdout').write_bytes(compiled.stdout)
    (root / 'compile.stderr').write_bytes(compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr[-4000:]
    ran = subprocess.run([str(root / 'probe'), str(REQUEST), str(root / 'actual.bin')], cwd=SOURCE,
        env=ENV, capture_output=True, timeout=60)
    (root / 'actual.stdout').write_bytes(ran.stdout)
    (root / 'actual.stderr').write_bytes(ran.stderr)
    assert ran.returncode == 0, (label, ran.stderr[-4000:])
    raw = (root / 'actual.bin').read_bytes()
    assert len(raw) == len(EXPECTED)
    matches = raw == EXPECTED
    assert matches if sanitized else not matches, label
    compressed = gzip.compress(raw, mtime=0)
    packed = root / 'actual.bin.gz'
    packed.write_bytes(compressed)
    assert gzip.decompress(packed.read_bytes()) == raw
    # Remove only this redundant verified raw copy; complete unique output is retained.
    raw_path = root / 'actual.bin'
    assert raw_path.resolve().parent == root.resolve()
    raw_path.unlink()
    row = dict(label=label, root=str(root), sanitized=sanitized, compiled_production_mutant=not sanitized,
        executable_sha256=hashlib.sha256((root / 'probe').read_bytes()).hexdigest(), raw_sha256=hashlib.sha256(raw).hexdigest(),
        raw_bytes=len(raw), compressed_sha256=hashlib.sha256(compressed).hexdigest(), matches_original=matches,
        differing_bytes=sum(a != b for a, b in zip(raw, EXPECTED)), root_bytes=size(root), command=command)
    assert row['root_bytes'] < CAP
    (root / 'proof.json').write_text(json.dumps(row, indent=2) + '\n')
    print(label + '=' + ('sanitizers-passed' if sanitized else 'mutant-rejected'), flush=True)
    return row


report['sanitizers'] = execute('sanitizers', sanitized=True)
for label, relative, before, after in variants:
    report['compiled_mutants'].append(execute('mutant-' + label, (relative, before, after)))
report['passed'] = True
(VIS / 'corpse-mutant-validation-t94.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, compiled_mutants_rejected=len(variants), sanitizers_passed=True)), flush=True)
