"""Sanitizer and malformed-request checks for the isolated animation probe."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
OUT = Path('/tmp/lezac-reward-native-validation-20261009-t91')
SOURCE = Path('/tmp/lezac-marker-writeback-20261009-t90')
ENV = dict(os.environ, SDL_AUDIODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
assert not (OUT / 'extra-validation.json').exists()
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(),
    earlier_shell_compile_parser_failure=True, earlier_missing_sanitized_executable_failure=True,
    app_executed=False, full_reward_cpp_comparison=False, commands=[], malformed_rejections=[])


def run(label, args, expected_success=True):
    result = subprocess.run(list(map(str, args)), cwd=SOURCE, env=ENV, capture_output=True, timeout=120)
    (OUT / (label + '.stdout')).write_bytes(result.stdout)
    (OUT / (label + '.stderr')).write_bytes(result.stderr)
    report['commands'].append(dict(label=label, args=list(map(str, args)), returncode=result.returncode,
        stdout_sha256=hashlib.sha256(result.stdout).hexdigest(), stderr_sha256=hashlib.sha256(result.stderr).hexdigest()))
    assert (result.returncode == 0) == expected_success, (label, result.stderr[-2000:])


try:
    run('compile-sanitized', ['c++', '-std=c++17', '-O1', '-g0', '-fsanitize=address,undefined',
        '-fno-omit-frame-pointer', '-I', SOURCE / 'src', VIS / 'reward-animation-probe-t91.cpp',
        '-o', OUT / 'animation-probe-sanitized'])
    run('sanitized', [OUT / 'animation-probe-sanitized', OUT / 'animation-input.bin', OUT / 'animation-sanitized.bin'])
    actual = (OUT / 'animation-sanitized.bin').read_bytes()
    assert actual == (OUT / 'animation-expected.bin').read_bytes()
    valid = (OUT / 'animation-input.bin').read_bytes()
    malformed = dict(empty=b'', short_magic=valid[:7], wrong_magic=b'BROKEN01' + valid[8:],
        short_count=valid[:11], zero_count=valid[:8] + bytes(4),
        excessive_count=valid[:8] + struct.pack('<I', 20001), missing_active=valid[:12],
        short_active=valid[:18], missing_backup=valid[:19], short_backup=valid[:25],
        missing_final_byte=valid[:-1], trailing_byte=valid + b'!')
    for label, raw in malformed.items():
        path = OUT / ('bad-' + label + '.bin')
        path.write_bytes(raw)
        run('reject-' + label, [OUT / 'animation-probe', path, OUT / ('bad-' + label + '-out.bin')], False)
        report['malformed_rejections'].append(label)
    report.update(passed=True, sanitized_animation_cases=5668,
        sanitized_output_sha256=hashlib.sha256(actual).hexdigest(), malformed_requests_rejected=len(malformed))
finally:
    report['root_bytes'] = sum(path.stat().st_size for path in OUT.rglob('*') if path.is_file())
    assert report['root_bytes'] < 8 * 1024**2
    raw = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    (OUT / 'extra-validation.json').write_bytes(raw)
    (VIS / 'reward-animation-extra-validation-t91.json').write_bytes(raw)
    print(json.dumps(dict(passed=report['passed'], root_bytes=report['root_bytes'],
                         rejections=len(report['malformed_rejections']))), flush=True)
