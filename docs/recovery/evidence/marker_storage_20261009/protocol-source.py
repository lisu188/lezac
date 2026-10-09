"""Exercise compiled malformed requests and existing actor-storage contracts."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import traceback

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
ROOT = Path('/tmp/lezac-marker-writeback-20261009-t90')
OUT = Path('/tmp/lezac-marker-protocol-regressions-20261009-t90')
PROBE = Path('/tmp/lezac-marker-writeback-checks-20261009-t90-v3/probe')
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), malformed=[], commands=[],
    actual_app_runtime_verified=False, full_game_build=False, whole_game_claim=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(name, args, success=True):
    assert shutil.disk_usage('/dev/shm').free > 1503238553
    result = subprocess.run(list(map(str, args)), cwd=ROOT, env=ENV, capture_output=True, timeout=120)
    (OUT / (name + '.stdout')).write_bytes(result.stdout)
    (OUT / (name + '.stderr')).write_bytes(result.stderr)
    report['commands'].append(dict(name=name, args=list(map(str, args)), returncode=result.returncode,
        stdout_sha256=sha(result.stdout), stderr_sha256=sha(result.stderr)))
    assert (result.returncode == 0) == success, (name, result.stdout, result.stderr)
    assert sum(path.stat().st_size for path in OUT.rglob('*') if path.is_file()) < 8 * 1024**2
    return result


try:
    assert not OUT.exists() and not (VIS / 'marker-protocol-regressions-t90.json').exists()
    OUT.mkdir()
    request = gzip.decompress((ROOT / 'tests/fixtures/marker_storage/requests.bin.gz').read_bytes())
    header = b'LZMW0001' + struct.pack('<I', 1) + request[12:380]
    at, seed = 380, None
    while at < len(request):
        command = request[at]
        at += 1
        size = 1575 if command == ord('S') else 2 if command == ord('U') else 4
        if command == ord('S') and request[at + 1570] == 1:
            seed = request[at:at + size]
            break
        at += size
    assert seed is not None
    malformed = dict(bad_magic=b'badmagic' + header[8:], truncated_header=b'LZMW',
        zero_operations=header[:8] + bytes(4) + header[12:],
        excessive_operations=header[:8] + struct.pack('<I', 100001) + header[12:],
        truncated_descriptors=header[:-1], unknown_command=header + b'?', truncated_seed=header + b'S' + seed[:10],
        truncated_launch=header + b'L\x00', truncated_portal=header + b'P\x00',
        truncated_update=header + b'U\x00', trailing_bytes=request + b'x')
    for name, offset, value in (('invalid_actor_count', 1570, 31), ('invalid_visual_count', 1571, 99),
            ('inconsistent_link_count', 1572, 1), ('invalid_visual_reference', 1, 255),
            ('non_marker_kind', 38, 3), ('non_marker_behavior', 38 + 21, 4)):
        mutant = bytearray(seed)
        mutant[offset] = value
        malformed[name] = header + b'S' + mutant
    for name, raw in malformed.items():
        path = OUT / (name + '.bin')
        path.write_bytes(raw)
        result = run(name, [PROBE, path, OUT / (name + '-actual.bin')], success=False)
        assert result.returncode == 1 and result.stderr
        report['malformed'].append(dict(name=name, rejected=True, request_sha256=sha(raw)))
    run('materialize-binding', ['git', 'sparse-checkout', 'add', '/tests/gameplay/actor_slots_test.cpp'])
    run('compile-binding', ['c++', '-std=c++17', '-O1', '-I', ROOT / 'src',
        ROOT / 'tests/gameplay/actor_slots_test.cpp', '-o', OUT / 'binding-test'])
    binding = run('binding', [OUT / 'binding-test'])
    assert b'actor_slots=ok operations=1800' in binding.stdout
    run('compile-transient', ['c++', '-std=c++17', '-O1', '-I', ROOT / 'src',
        ROOT / 'tests/gameplay/transient_storage_probe.cpp', '-o', OUT / 'transient-probe'])
    run('transient-original', ['python3', '-S', '-B', ROOT / 'tools/check_transient_storage_original.py',
        '--exe', OUT / 'transient-probe', '--root', ROOT, '--out', OUT / 'transient-checker'])
    report.update(passed=True, malformed_rejected=len(malformed), binding_operations=1800, transient_operations=256,
        probe_sha256=sha(PROBE.read_bytes()), out_bytes=sum(path.stat().st_size for path in OUT.rglob('*') if path.is_file()))
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    (VIS / 'marker-protocol-regressions-t90.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=report['passed'], malformed_rejected=len(report['malformed']), failure=report.get('failure'))), flush=True)
if not report['passed']:
    raise SystemExit(1)
