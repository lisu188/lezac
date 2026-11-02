"""Observe the unchanged historical replay using a late hardware-only guard stop."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import time

EXPECTED = 'b1c719393f987cd2a98090055c8cc06d5d71589090599a36f32c4d2fd5da47f6'
WATCH_OFFSETS = (0x2520, 0x2330)  # Pinned invalid_argument and runtime_error constructor PLTs.
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


class Registers(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
        'r15 r14 r13 r12 rbp rbx r11 r10 r9 r8 rax rcx rdx rsi rdi orig_rax rip cs eflags rsp ss fs_base gs_base ds es fs gs'.split()]


libc = ctypes.CDLL(None, use_errno=True)
libc.ptrace.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p]
libc.ptrace.restype = ctypes.c_long


def ptrace(request, pid, address=0, data=0):
    ctypes.set_errno(0)
    result = libc.ptrace(request, pid, ctypes.c_void_p(address), ctypes.c_void_p(data))
    if result == -1 and ctypes.get_errno():
        raise OSError(ctypes.get_errno(), 'Owned-child ptrace request failed: ' + str(request))
    return result


def run(args):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))
    args.out = args.out.resolve()
    if platform.machine() != 'x86_64' or args.out.exists() or not args.out.is_relative_to(Path('/dev/shm')):
        raise ValueError('Use a fresh x86-64 RAM diagnostic directory')
    if not 1 <= args.attempts <= 16 or sha(args.exe) != EXPECTED or os.environ.get('LD_PRELOAD'):
        raise ValueError('Historical executable, attempt bound or preload environment differs')
    for name in ('exe', 'symbols', 'fixture', 'root', 'layout'):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    layout = json.loads(args.layout.read_bytes())
    if layout != dict(debug_offset=848, register_bytes=ctypes.sizeof(Registers), word_bytes=8):
        raise ValueError('Compiled native ptrace layout differs')
    args.out.mkdir()
    protected = {str(p.resolve()): sha(p) for p in (args.exe, args.symbols, args.fixture, args.root / 'LEZAC.EXE',
        args.layout, Path(__file__), Path(__file__).with_name('actor_pass_guard_gdb.py'))}
    calibration = args.calibrate_unit or args.calibrate_cli
    report = dict(status='running', historical_elf_sha256=EXPECTED, attempts=[], core_dump_limit=0,
        protected_inputs_sha256=protected, software_breakpoints=0, preload_hooks=0,
        code_or_guest_data_writes=0, debug_register_writes=0, calibration=calibration,
        calibration_kind='invalid_argv' if args.calibrate_cli else ('unit_negative_controls' if calibration else None),
        late_attach=not calibration, watch_offsets=list(WATCH_OFFSETS), intermittent_hold_cleared=False)
    child = None
    try:
        for attempt in range(args.attempts):
            arguments = [] if args.calibrate_unit else [str(args.fixture)] if args.calibrate_cli else [str(args.fixture), str(args.root)]
            child = subprocess.Popen([str(args.exe), *arguments],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                preexec_fn=(lambda: ptrace(0, 0)) if calibration else None,
                env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                         TMPDIR=str(args.out)))
            if calibration:
                os.waitpid(child.pid, 0)
                ptrace(0x4200, child.pid, 0, 1 << 20)
            else:
                time.sleep(.1)
                if child.poll() is not None:
                    raise ValueError('Historical replay exited before late attach')
                ptrace(0x4206, child.pid, 0, 1 << 20)
                ptrace(0x4207, child.pid)
                os.waitpid(child.pid, 0)
            maps = Path(f'/proc/{child.pid}/maps').read_text().splitlines()
            executable = args.exe.resolve()
            owned = [line.split() for line in maps if line.endswith(str(executable)) and 'x' in line.split()[1]]
            if len(owned) != 1:
                raise ValueError('Owned historical executable mapping differs')
            base = int(owned[0][0].split('-')[0], 16) - int(owned[0][2], 16)
            for slot, offset in enumerate(WATCH_OFFSETS):
                ptrace(6, child.pid, 848 + slot * 8, base + offset)
            ptrace(6, child.pid, 848 + 6 * 8, 0)
            ptrace(6, child.pid, 848 + 7 * 8, 5)
            report['debug_register_writes'] += 4
            ptrace(7, child.pid)
            deadline = time.monotonic() + 180
            while True:
                pid, status = os.waitpid(child.pid, os.WNOHANG)
                if not pid:
                    if time.monotonic() > deadline:
                        raise TimeoutError('Hardware guard observation bound elapsed')
                    time.sleep(.02)
                    continue
                if os.WIFEXITED(status) or os.WIFSIGNALED(status):
                    child.returncode = os.waitstatus_to_exitcode(status)
                    stdout, stderr = child.communicate()
                    (args.out / f'{attempt}.stdout').write_bytes(stdout)
                    (args.out / f'{attempt}.stderr').write_bytes(stderr)
                    report['attempts'].append(dict(attempt=attempt, exit_code=child.returncode))
                    if child.returncode:
                        raise RuntimeError('Historical replay failed without a captured hardware stop')
                    break
                slot_mask = ptrace(3, child.pid, 848 + 6 * 8) & 3 if os.WSTOPSIG(status) == signal.SIGTRAP else 0
                if not slot_mask:
                    raise ValueError('Unexpected hardware observation stop')
                registers = Registers()
                ptrace(12, child.pid, 0, ctypes.addressof(registers))
                with open(f'/proc/{child.pid}/mem', 'rb', buffering=0) as memory:
                    message = os.pread(memory.fileno(), 160, registers.rsi).split(b'\0', 1)[0].decode('ascii')
                report.update(status='hardware_guard_stop', message=message, stopped_attempt=attempt,
                    hardware_stop_slot_mask=slot_mask,
                    stopped_pid=child.pid, runtime_base=hex(base), registers={n: int(getattr(registers, n)) for n, _ in Registers._fields_})
                ptrace(6, child.pid, 848 + 7 * 8, 0)
                ptrace(6, child.pid, 848, 0)
                ptrace(6, child.pid, 848 + 8, 0)
                ptrace(6, child.pid, 848 + 6 * 8, 0)
                report['debug_register_writes'] += 4
                ptrace(17, child.pid, 0, signal.SIGSTOP)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    state = Path(f'/proc/{child.pid}/status').read_text()
                    if 'State:\tT ' in state and 'TracerPid:\t0\n' in state:
                        break
                    time.sleep(.01)
                else:
                    raise TimeoutError('Hardware-stop handoff did not settle')
                if any(sha(Path(p)) != digest for p, digest in protected.items()):
                    raise ValueError('Protected hardware-capture input changed')
                report['protected_inputs_preserved'] = True
                (args.out / 'hardware.json').write_text(json.dumps(report, indent=2) + '\n')
                env = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                    LEZAC_GUARD_OUT=str(args.out / 'guard'), LEZAC_GUARD_EXE=str(executable),
                    LEZAC_GUARD_SYMBOLS=str(args.symbols.resolve()), LEZAC_GUARD_FIXTURE=str(args.fixture.resolve()),
                    LEZAC_GUARD_ROOT=str(args.root.resolve()), LEZAC_GUARD_ATTACH_PID=str(child.pid),
                    LEZAC_GUARD_STOP_MESSAGE=message, LEZAC_GUARD_CALIBRATION=str(int(calibration)))
                command = ['gdb', '-q', '-nx', '-batch', '-x', str(Path(__file__).with_name('actor_pass_guard_gdb.py'))]
                os.execvpe('gdb', command, env)
            (args.out / 'hardware.json').write_text(json.dumps(report, indent=2) + '\n')
        report['status'] = 'bounded_non_reproduction'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        if child is not None and child.returncode is None:
            child.kill();child.wait()
        try:
            report['protected_inputs_preserved'] = all(sha(Path(path)) == digest for path, digest in protected.items())
            if not report['protected_inputs_preserved']:
                report.update(status='failed', protected_input_error='Protected hardware-capture input changed')
        except OSError as error:
            report.update(status='failed', protected_inputs_preserved=False, protected_input_error=repr(error))
        (args.out / 'hardware.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['status'] == 'failed':
        raise RuntimeError(report.get('protected_input_error', 'Hardware observation failed'))
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('exe', 'symbols', 'fixture', 'root', 'layout', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--attempts', type=int, default=8)
    calibration = parser.add_mutually_exclusive_group()
    calibration.add_argument('--calibrate-unit', action='store_true')
    calibration.add_argument('--calibrate-cli', action='store_true')
    run(parser.parse_args())
