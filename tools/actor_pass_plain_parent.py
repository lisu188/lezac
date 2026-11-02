"""Bounded, uninstrumented control for the exact historical actor-pass ELF."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import time

EXPECTED = 'b1c719393f987cd2a98090055c8cc06d5d71589090599a36f32c4d2fd5da47f6'
FIXTURE_SHA = '799531ca906973fc9f0b619855e42898aa5eb876b4086641cc6b637eb63a40d3'
MZ_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
SUCCESS = b'frame_actor_pass_original=ok cases=876 replays=7884 '
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))
    args.out = args.out.resolve()
    if args.out.exists() or not args.out.is_relative_to(Path('/dev/shm')) or not 1 <= args.attempts <= 16:
        raise ValueError('Use fresh bounded RAM diagnostics')
    for name in ('exe', 'fixture', 'root'):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    if (sha(args.exe), sha(args.fixture), sha(args.root / 'LEZAC.EXE')) != (EXPECTED, FIXTURE_SHA, MZ_SHA):
        raise ValueError('Historical executable or canonical input differs')
    if any(os.environ.get(name) for name in ('LD_PRELOAD', 'LD_AUDIT')):
        raise ValueError('Uninstrumented control rejects loader instrumentation')
    args.out.mkdir()
    protected = {str(path): sha(path) for path in
        (args.exe, args.fixture, args.root / 'LEZAC.EXE', Path(__file__).resolve())}
    report = dict(status='running', attempts=[], protected_inputs_sha256=protected,
        core_dump_limit=0, debugger_attached=False, preload_hooks=0, full_ram_artifacts=0,
        guest_state_injected=False, intermittent_hold_cleared=False, diagnosis_claim=False)
    started = time.monotonic()
    try:
        for attempt in range(args.attempts):
            result = subprocess.run([str(args.exe), str(args.fixture), str(args.root)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy', TMPDIR=str(args.out)))
            if max(len(result.stdout), len(result.stderr)) > 65536:
                raise ValueError('Historical replay diagnostic output exceeded reserve')
            for name in ('stdout', 'stderr'):
                (args.out / f'{attempt}.{name}').write_bytes(getattr(result, name))
            item = dict(attempt=attempt, exit_code=result.returncode,
                elapsed_seconds=round(time.monotonic() - started, 3),
                stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
                stderr_sha256=hashlib.sha256(result.stderr).hexdigest())
            report['attempts'].append(item)
            if result.returncode:
                if result.returncode != 1 or b'frame_actor_pass=failed ' not in result.stderr:
                    raise RuntimeError('Historical replay ended outside its reported failure contract')
                report.update(status='failure_reproduced', stderr=result.stderr.decode('ascii'))
                break
            if not result.stdout.startswith(SUCCESS) or result.stderr:
                raise ValueError('Historical replay success output differs')
            (args.out / 'plain.json').write_text(json.dumps(report, indent=2) + '\n')
        else:
            report['status'] = 'bounded_non_reproduction'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        try:
            report['protected_inputs_preserved'] = all(sha(Path(path)) == digest for path, digest in protected.items())
            if not report['protected_inputs_preserved']:
                report.update(status='failed', protected_input_error='Protected control input changed')
        except OSError as error:
            report.update(status='failed', protected_inputs_preserved=False, protected_input_error=repr(error))
        (args.out / 'plain.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['status'] == 'failed':
        raise RuntimeError(report.get('protected_input_error', 'Uninstrumented control failed'))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('exe', 'fixture', 'root', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--attempts', type=int, default=8)
    run(parser.parse_args())
