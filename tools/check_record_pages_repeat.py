"""Repeat native record-page pixel checks while retaining complete per-run evidence."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HEADER = b'P6\n320 200\n255\n'
PROFILES = {
    'records': ('records_page_', 2, b'records_page=ok original_frames=2 compared_pixels=256000'),
    'entry': ('record_entry_', 8, b'record_entry_page=ok original_frames=8 compared_pixels=1024000'),
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replay(profile, exe, fixtures, out):
    prefix, original_frames, marker = PROFILES[profile]
    oracles = {path.stem: path.read_bytes() for path in fixtures.glob(prefix + '*.rgb')}
    require(len(oracles) == original_frames, 'original record-page frame set changed')
    expected_names = {stem + '-' + language + '.ppm.gz' for stem in oracles for language in ('english', 'italian')}
    out.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    native_out = evidence / 'native'
    report = dict(passed=False, profile=profile, native_runs=[], original_frames=original_frames,
                  compared_pixels=original_frames * 4 * 64000, masks=0,
                  executable_sha256=sha(exe.read_bytes()), full_app_executed=False,
                  fresh_original_execution=False, whole_game_complete=False)
    first = {}
    initial_error = None
    try:
        for index in range(2):
            command = [str(exe.resolve()), str(fixtures.resolve()), str(native_out.resolve())]
            result = subprocess.run(command, env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'),
                                    capture_output=True, timeout=60)
            report['native_runs'].append(dict(command=command, exit_code=result.returncode))
            for stream in ('stdout', 'stderr'):
                (evidence / (str(index) + '.' + stream)).write_bytes(getattr(result, stream))
            require(result.returncode == 0 and not result.stderr and marker in result.stdout,
                    'native record-page rerun failed: ' + result.stderr.decode(errors='replace'))
            for path in native_out.rglob('*.ppm'):
                require(not path.is_symlink() and path.resolve().is_relative_to(evidence.resolve()),
                        'native frame escaped its owned output')
                raw = path.read_bytes()
                replacement = path.with_name(path.name + '.gz')
                with replacement.open('xb') as stream:
                    stream.write(gzip.compress(raw, mtime=0))
                require(gzip.decompress(replacement.read_bytes()) == raw, 'frame compression changed pixels')
                path.unlink()
            frames = list(native_out.rglob('*.ppm.gz'))
            require(Counter(path.name for path in frames) == Counter({name: index + 1 for name in expected_names}),
                    'native run did not retain independent complete frame sets')
            for path in frames:
                raw = gzip.decompress(path.read_bytes())
                stem = path.with_suffix('').stem.rsplit('-', 1)[0]
                require(raw[:len(HEADER)] == HEADER and raw[len(HEADER):] == oracles[stem],
                        'retained complete frame differs from original oracle')
            current = {path: sha(path.read_bytes()) for path in native_out.rglob('*') if path.is_file()}
            require(all(path in current and current[path] == digest for path, digest in first.items()),
                    'first-run frame or saved record changed')
            if index == 0:
                first = current
        require(sha(exe.read_bytes()) == report['executable_sha256'], 'native executable changed')
        require(all((fixtures / (stem + '.rgb')).read_bytes() == raw for stem, raw in oracles.items()),
                'original RGB fixture changed')
        report.update(passed=True, first_evidence_unchanged=True,
            retained_output_sha256={str(path.relative_to(evidence)): digest for path, digest in current.items()},
            rgb_sha256={stem: sha(raw) for stem, raw in oracles.items()})
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
    parser.add_argument('--profile', choices=PROFILES, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not sys.flags.optimize, 'optimized Python unsupported')
    report = replay(args.profile, args.exe, args.fixtures, args.out)
    print('record_pages_repeat=ok profile=' + args.profile + ' invocations=2 compared_pixels=' +
          str(report['compared_pixels']) + ' first_evidence_unchanged=1')


if __name__ == '__main__':
    main()
