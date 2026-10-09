"""Compile deliberate marker regressions and reject each complete raw result."""
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
ROOT = Path('/tmp/lezac-marker-writeback-20261009-t90')
CAP = 8 * 1024**2
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0, str(ROOT / 'tools'))
import check_marker_storage_original as checker

request = gzip.decompress((ROOT / 'tests/fixtures/marker_storage/requests.bin.gz').read_bytes())
expected = gzip.decompress((ROOT / 'tests/fixtures/marker_storage/expected.bin.gz').read_bytes())
slots = (ROOT / 'src/gameplay/actor_slots.hpp').read_text()
models = (ROOT / 'src/gameplay/actor_models.hpp').read_text()
probe = (ROOT / 'tests/gameplay/marker_storage_probe.cpp').read_text()
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), producer_sha256=checker.sha(Path(__file__).read_bytes()),
    original_result_sha256=checker.sha(expected), compiled_app_mutants=False, whole_game_claim=False, mutants=[])


def mutate(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


marker_at = slots.index('    void writeMarker(')
prefix, writer = slots[:marker_at], slots[marker_at:]
mutants = [
    ('skip-writeback', 'gameplay/actor_slots.hpp', prefix + mutate(writer,
        'const Descriptor& descriptor) {', 'const Descriptor& descriptor) {\n        return;')),
    ('rewrite-dimensions', 'gameplay/actor_slots.hpp', prefix + mutate(writer,
        'if (animationAdvanced) { row[6] = descriptor[2]; row[7] = descriptor[3]; }',
        'if (animationAdvanced) std::copy(descriptor.begin(), descriptor.end(), row.begin() + 4);')),
    ('clear-launch-animation', 'gameplay/actor_slots.hpp', mutate(slots,
        'storage_.actor(require(order))[27] = 0;',
        'auto& raw = storage_.actor(require(order)); std::fill(raw.begin() + 22, raw.begin() + 29, 0);')),
    ('clear-backup', 'gameplay/actor_slots.hpp', mutate(slots,
        'storage_.actor(require(order))[27] = 0;',
        'storage_.actor(require(order))[27] = 0; storage_.actor(require(order))[29] = 0;')),
    ('skip-portal-initializer', 'probe.cpp', mutate(probe,
        "if (command == 'P') slots.setActiveAnimation(marker.actorOrder, marker.animation);",
        "if (command == 'P') {}")),
    ('saturating-timer', 'gameplay/actor_models.hpp', mutate(models,
        'marker.timer = static_cast<uint8_t>(marker.timer - (logicTick & 1u));',
        'if (marker.timer) marker.timer = static_cast<uint8_t>(marker.timer - (logicTick & 1u));')),
    ('clamp-coordinate', 'gameplay/actor_models.hpp', mutate(models,
        'marker.x = static_cast<int16_t>(marker.x + (x >> 8));',
        'const int nextX = marker.x + (x >> 8); marker.x = nextX > 32767 ? 32767 : nextX < -32768 ? -32768 : nextX;')),
    ('truncate-negative-carry', 'gameplay/actor_models.hpp', mutate(models,
        'marker.x = static_cast<int16_t>(marker.x + (x >> 8));', 'marker.x = static_cast<int16_t>(marker.x + (x / 256));')),
    ('skip-terminal-write', 'gameplay/actor_slots.hpp', prefix + mutate(writer,
        'const Descriptor& descriptor) {', 'const Descriptor& descriptor) {\n        if (marker.timer == 0) return;')),
    ('early-capacity-return', 'probe.cpp', mutate(probe,
        'if (slots.append(nextOrder, construction, row)) {',
        'if (slots.count() < ActorStorage::capacity && slots.append(nextOrder, construction, row)) {')),
    ('preempt-later-zero-timers', 'probe.cpp', mutate(probe,
        'const uint16_t tick = fixture::word(input);',
        'const uint16_t tick = fixture::word(input);\n'
        '                for (size_t at = 0; at < markers.size();) {\n'
        '                    if (markers[at].timer == 0) {\n'
        '                        slots.retire(markers[at].actorOrder);\n'
        '                        markers.erase(markers.begin() + static_cast<std::ptrdiff_t>(at));\n'
        '                    } else ++at;\n'
        '                }')),
]

try:
    assert not (VIS / 'marker-compiled-mutants-t90-v2.json').exists()
    for name, relative, source in mutants:
        assert shutil.disk_usage('/dev/shm').free > 1503238553
        folder = Path('/tmp/lezac-marker-mutant-' + name + '-20261009-t90-v2')
        assert not folder.exists()
        (folder / relative).parent.mkdir(parents=True)
        (folder / relative).write_text(source)
        (folder / 'requests.bin').write_bytes(request)
        source_path = folder / 'probe.cpp' if relative == 'probe.cpp' else ROOT / 'tests/gameplay/marker_storage_probe.cpp'
        args = ['c++', '-std=c++17', '-O1', '-I', str(folder), '-I', str(ROOT / 'src'), str(source_path), '-o', str(folder / 'mutant')]
        compile_result = subprocess.run(args, cwd=ROOT, env=ENV, capture_output=True, timeout=120)
        (folder / 'compile.stdout').write_bytes(compile_result.stdout)
        (folder / 'compile.stderr').write_bytes(compile_result.stderr)
        assert compile_result.returncode == 0, (name, compile_result.stderr)
        result = subprocess.run([str(folder / 'mutant'), str(folder / 'requests.bin'), str(folder / 'actual.bin')],
            cwd=ROOT, env=ENV, capture_output=True, timeout=30)
        (folder / 'actual.stdout').write_bytes(result.stdout)
        (folder / 'actual.stderr').write_bytes(result.stderr)
        assert result.returncode == 0, (name, result.stdout, result.stderr)
        actual = (folder / 'actual.bin').read_bytes()
        difference = checker.difference(actual, expected)
        assert difference is not None, ('mutant survived', name)
        size = sum(path.stat().st_size for path in folder.rglob('*') if path.is_file())
        assert size < CAP
        row = dict(name=name, rejected=True, root=str(folder), root_bytes=size, source_sha256=checker.sha(source.encode()),
            executable_sha256=checker.sha((folder / 'mutant').read_bytes()), actual_sha256=checker.sha(actual), first_difference=difference)
        report['mutants'].append(row)
        print(json.dumps(row), flush=True)
    report.update(passed=True, rejected=len(mutants), operations_per_mutant=1008, compared_bytes_per_mutant=1587600)
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    (VIS / 'marker-compiled-mutants-t90-v2.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=report['passed'], rejected=len(report['mutants']), failure=report.get('failure'))), flush=True)
if not report['passed']:
    raise SystemExit(1)
