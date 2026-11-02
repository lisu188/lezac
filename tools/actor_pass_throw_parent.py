"""Launch a bounded historical replay; attach only after the real guard throws."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time

from actor_pass_supervision import allow_parent_debugger, collect_guard

EXPECTED = 'b1c719393f987cd2a98090055c8cc06d5d71589090599a36f32c4d2fd5da47f6'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))
    args.out = args.out.resolve()
    if args.out.exists() or not args.out.is_relative_to(Path('/dev/shm')) or not 1 <= args.attempts <= 16:
        raise ValueError('Use fresh bounded RAM diagnostics')
    if sha(args.exe) != EXPECTED or os.environ.get('LD_PRELOAD'):
        raise ValueError('Historical ELF or preload environment differs')
    for name in ('exe', 'symbols', 'fixture', 'root', 'hook'):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.out.mkdir()
    protected = {str(path): sha(path) for path in (args.exe, args.symbols, args.fixture, args.root / 'LEZAC.EXE',
        args.hook, Path(__file__), Path(__file__).with_name('actor_pass_guard_gdb.py'),
        Path(__file__).with_name('actor_pass_supervision.py'))}
    report = dict(status='running', historical_elf_sha256=EXPECTED, attempts=[], core_dump_limit=0,
        hook_sha256=sha(args.hook), parent_sha256=sha(Path(__file__)),
        hook_is_host_instrumentation=True, guest_state_injected=False, intermittent_hold_cleared=False,
        protected_inputs_sha256=protected, cleanup_owner='supervising-parent',
        ptrace_permission='parent-and-descendants-only')
    environment = dict(os.environ, LD_PRELOAD=str(args.hook), SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    try:
        campaign(args, report, environment)
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        try:
            report['protected_inputs_preserved'] = all(sha(Path(path)) == digest for path, digest in protected.items())
            if not report['protected_inputs_preserved']:
                report.update(status='failed', protected_input_error='Protected diagnostic input changed')
        except OSError as error:
            report.update(status='failed', protected_inputs_preserved=False, protected_input_error=repr(error))
        (args.out / 'parent.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['status'] == 'failed':
        raise RuntimeError(report.get('protected_input_error', 'Diagnostic campaign failed'))
    print(json.dumps(report))


def campaign(args, report, environment):
    for attempt in range(args.attempts):
        child = None
        try:
            with (args.out / f'{attempt}.stdout').open('xb') as stdout, (args.out / f'{attempt}.stderr').open('xb') as stderr:
                child = subprocess.Popen([str(args.exe), str(args.fixture), str(args.root)],
                                         stdout=stdout, stderr=stderr, env=environment,
                                         preexec_fn=allow_parent_debugger)
                deadline = time.monotonic() + 180
                while True:
                    pid, status = os.waitpid(child.pid, os.WNOHANG | os.WUNTRACED)
                    if pid and os.WIFSTOPPED(status):
                        if os.WSTOPSIG(status) != signal.SIGSTOP:
                            raise ValueError('Unexpected child stop')
                        marker = (args.out / f'{attempt}.stderr').read_bytes().split(b'LEZAC_THROW_STOP:')[-1].splitlines()[0]
                        message = marker.decode('ascii')
                        if not message.startswith(('Frame actor', 'Actor ')) or len(marker) > 160:
                            raise ValueError('Throw-stop message differs')
                        if any(sha(Path(path)) != digest for path, digest in report['protected_inputs_sha256'].items()):
                            raise ValueError('Protected diagnostic input changed before handoff')
                        report.update(status='stopped_before_unwind', stopped_pid=child.pid, stopped_attempt=attempt,
                                      protected_inputs_preserved=True)
                        (args.out / 'parent.json').write_text(json.dumps(report, indent=2) + '\n')
                        debug_environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                            LEZAC_GUARD_OUT=str(args.out / 'guard'), LEZAC_GUARD_EXE=str(args.exe),
                            LEZAC_GUARD_SYMBOLS=str(args.symbols), LEZAC_GUARD_FIXTURE=str(args.fixture),
                            LEZAC_GUARD_ROOT=str(args.root), LEZAC_GUARD_ATTACH_PID=str(child.pid),
                            LEZAC_GUARD_STOP_MESSAGE=message)
                        command = ['gdb', '-q', '-nx', '-batch', '-x', str(Path(__file__).with_name('actor_pass_guard_gdb.py'))]
                        report['collector'] = collect_guard(command, debug_environment, args.out)
                        report['status'] = 'throw_captured'
                        return
                    if pid:
                        child.returncode = os.waitstatus_to_exitcode(status)
                        report['attempts'].append(dict(attempt=attempt, exit_code=child.returncode))
                        if child.returncode:
                            raise RuntimeError('Historical replay failed without a captured throw')
                        break
                    if time.monotonic() > deadline:
                        raise TimeoutError('Historical child observation bound elapsed')
                    time.sleep(.02)
        finally:
            if child is not None and child.returncode is None:
                child.kill();child.wait()
        (args.out / 'parent.json').write_text(json.dumps(report, indent=2) + '\n')
    report['status'] = 'bounded_non_reproduction'
    (args.out / 'parent.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('exe', 'symbols', 'fixture', 'root', 'hook', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--attempts', type=int, default=8)
    run(parser.parse_args())
