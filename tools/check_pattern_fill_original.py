"""Replay original pattern checkpoints through the actual App and retain repeats."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from frame_compare import read_ppm

MARKER = b'pattern_background_app=ok frames=3 original_cursor_cases=3 actual_app_fixture=1 natural_timing_claim=0 whole_game_parity=0'
HEADER = b'P6\n320 200\n255\n'

def require(value, message):
    if not value:
        raise RuntimeError(message)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def load_fixture(path):
    data = json.loads(path.read_text())
    require(data.get('schema') == 'lezac-pattern-fill-original-v1' and data.get('masks') == 0,
            'invalid pattern fixture schema or masks')
    require(data.get('instruction_alignment_claim') is False and data.get('full_game_parity') is False,
            'unsupported fixture fidelity claim')
    cases = data.get('cases', [])
    require(len(cases) == 3, 'expected three original checkpoints')
    names = set()
    for case in cases:
        name = case.get('name', '')
        require(re.fullmatch(r'[A-Za-z0-9_-]+', name) and name not in names, 'unsafe or duplicate checkpoint name')
        names.add(name)
        require(re.fullmatch(r'[0-9a-f]{64}', case.get('rgb_sha256', '')), 'invalid original RGB digest')
        for field in ('horizontal_step', 'vertical_step'):
            require(type(case.get(field)) is int and 1 <= case[field] <= 80, 'invalid original pattern step')
        for field in ('destination_offset', 'ram_cursor_destination'):
            require(type(case.get(field)) is int and 0 < case[field] < 64000, 'invalid original destination')
        require(type(case.get('ram_cursor_fraction')) is int and -8 <= case['ram_cursor_fraction'] <= 100,
                'invalid original fraction')
        require(type(case.get('ram_cursor_phase')) is int and 0 <= case['ram_cursor_phase'] <= 65535,
                'invalid original phase')
        require(case.get('ram_phase_stage') in ('Horizontal', 'Vertical', 'Write'), 'invalid original stage')
        require(case['ram_phase_stage'] != 'Vertical' or case['ram_cursor_destination'] % 320 == 0,
                'row adjustment outside a row boundary')
        colors = case.get('colors', [])
        require(len(colors) == 7 and all(type(c.get(k)) is int and 0 <= c[k] <= 255
                for c in colors for k in ('r', 'g', 'b')), 'invalid original DAC palette')
        require(case.get('ram_rgb_atomic') is False, 'unsupported atomic sample claim')
    return {case['name']: case for case in cases}

def check_frame(path, case):
    raw = path.read_bytes()
    require(raw.startswith(HEADER) and len(raw) == len(HEADER) + 192000,
            'invalid complete native frame length or header')
    width, height, pixels = read_ppm(path)
    require((width, height) == (320, 200) and sha(pixels) == case['rgb_sha256'],
            'complete original RGB digest differs')

def replay(exe, fixture, out):
    cases = load_fixture(fixture)
    out.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    frames = evidence / 'frames'
    report = dict(passed=False, native_runs=[], audio='dummy', actual_app_fixture=True,
        natural_timing_claim=False, full_game_parity=False, masks=0,
        executable_sha256=sha(exe.read_bytes()), fixture_sha256=sha(fixture.read_bytes()))
    first = {}
    initial_error = None
    try:
        for index in range(2):
            command = [str(exe.resolve()), '--debug-pattern-background-fill', str(fixture.resolve()), str(frames.resolve())]
            result = subprocess.run(command, env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'),
                                    capture_output=True, timeout=60)
            report['native_runs'].append(dict(command=command, exit_code=result.returncode))
            for stream in ('stdout', 'stderr'):
                (evidence / (str(index) + '.' + stream)).write_bytes(getattr(result, stream))
            require(result.returncode == 0 and not result.stderr and MARKER in result.stdout,
                    'native pattern replay failed: ' + result.stderr.decode(errors='replace'))
            current = {path: sha(path.read_bytes()) for path in frames.rglob('*.ppm')}
            require(len(current) == 3 * (index + 1), 'native replay did not retain three independent frames')
            for path, digest in first.items():
                require(current.get(path) == digest, 'first-run pattern frame changed')
            for path in current:
                require(path.stem in cases, 'unexpected native checkpoint')
                check_frame(path, cases[path.stem])
            if index == 0:
                first = current
        require(sha(exe.read_bytes()) == report['executable_sha256'] and
                sha(fixture.read_bytes()) == report['fixture_sha256'], 'replay inputs changed')
        report.update(passed=True, original_frames=6, verified_rgb_bytes=1152000,
                      first_evidence_unchanged=True, frame_sha256={str(p.relative_to(evidence)): d for p, d in current.items()})
    except BaseException as error:
        initial_error = error
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        try:
            (evidence / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        except BaseException:
            if initial_error is None:
                raise
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', required=True, type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    replay(args.exe, args.fixture, args.out)
    print('pattern_fill_original=ok invocations=2 original_frames=6 verified_rgb_bytes=1152000 cursor_cases=6 first_evidence_unchanged=1 actual_app_fixture=1 natural_timing_claim=0')

if __name__ == '__main__':
    main()
