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

from actor_pass_supervision import allow_parent_debugger, collect_guard
from actor_pass_contact_operands import (GUARD_BANKS, PROFILES, StoppedOperandReader,
                                        observe_contact_operands, verify_pinned_contact_sites)
from actor_pass_entry_operands import (ENTRY_GUARD_BANKS, ENTRY_MESSAGE, ENTRY_PROFILES,
                                      observe_entry_operands, verify_pinned_entry_sites)

EXPECTED = 'b1c719393f987cd2a98090055c8cc06d5d71589090599a36f32c4d2fd5da47f6'
WATCH_OFFSETS = (0x2520, 0x2330, 0x3abf4, 0x8acf9)
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
    calibration = args.calibrate_unit or args.calibrate_cli
    bank = getattr(args, 'contact_guard_bank', None)
    entry_bank = getattr(args, 'entry_id_guard_bank', None)
    if bank not in (None, 'all', *GUARD_BANKS):
        raise ValueError('Unknown contact guard bank')
    if entry_bank not in (None, 'all', *ENTRY_GUARD_BANKS):
        raise ValueError('Unknown entry-ID guard bank')
    if bank and entry_bank:
        raise ValueError('Contact and entry-ID guard banks are mutually exclusive')
    if args.calibrate_cli and (bank or entry_bank):
        raise ValueError('Guard banks are not invalid-argv calibrations')
    targeted = args.validation_only or bank is not None or entry_bank is not None
    calibration_kind = None
    if args.calibrate_cli:
        calibration_kind = 'invalid_argv'
    elif args.calibrate_unit:
        calibration_kind = ('unit_negative_controls_entry_id_guards' if entry_bank else
            'unit_negative_controls_contact_guards' if bank else 'unit_negative_controls')
    args.out.mkdir()
    protected = {str(p.resolve()): sha(p) for p in (args.exe, args.symbols, args.fixture, args.root / 'LEZAC.EXE',
        args.layout, Path(__file__), Path(__file__).with_name('actor_pass_guard_gdb.py'),
        Path(__file__).with_name('actor_pass_supervision.py'),
        Path(__file__).with_name('actor_pass_contact_operands.py'),
        Path(__file__).with_name('actor_pass_entry_operands.py'))}
    report = dict(status='running', historical_elf_sha256=EXPECTED, attempts=[], core_dump_limit=0,
        protected_inputs_sha256=protected, software_breakpoints=0, preload_hooks=0,
        code_or_guest_data_writes=0, debug_register_writes=0, calibration=calibration,
        calibration_kind=calibration_kind,
        late_attach=not calibration, watch_offsets=list(WATCH_OFFSETS), intermittent_hold_cleared=False,
        cleanup_owner='supervising-parent', ptrace_permission='parent-and-descendants-only',
        validation_only=targeted, contact_guard_bank=bank, entry_id_guard_bank=entry_bank,
        watch_history=[], uncaptured_failures=[])
    child = None
    captured = False
    def prepare_child():
        allow_parent_debugger()
        if calibration:
            ptrace(0, 0)
    try:
        for attempt in range(args.attempts):
            selected_bank = tuple(GUARD_BANKS)[attempt % len(GUARD_BANKS)] if bank == 'all' else bank
            watches = GUARD_BANKS[selected_bank] if selected_bank else WATCH_OFFSETS
            if entry_bank:
                selected_bank = tuple(ENTRY_GUARD_BANKS)[attempt % len(ENTRY_GUARD_BANKS)] if entry_bank == 'all' else entry_bank
                watches = ENTRY_GUARD_BANKS[selected_bank]
            arguments = [] if args.calibrate_unit else [str(args.fixture)] if args.calibrate_cli else [str(args.fixture), str(args.root)]
            child = subprocess.Popen([str(args.exe), *arguments],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                preexec_fn=prepare_child,
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
            for slot, offset in enumerate(watches):
                ptrace(6, child.pid, 848 + slot * 8, base + offset)
            ptrace(6, child.pid, 848 + 6 * 8, 0)
            enabled = [slot for slot, offset in enumerate(watches)
                       if not targeted or offset in PROFILES or offset in ENTRY_PROFILES]
            ptrace(6, child.pid, 848 + 7 * 8, sum(1 << (slot * 2) for slot in enabled))
            report['debug_register_writes'] += len(watches) + 2
            report['watch_offsets'] = list(watches)
            report['watch_history'].append(dict(attempt=attempt, bank=selected_bank,
                family='entry-id' if entry_bank else 'contact' if bank else 'default',
                offsets=list(watches), enabled_slots=enabled))
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
                        if targeted and child.returncode == 1 and b'frame_actor_pass=failed ' in stderr:
                            report['uncaptured_failures'].append(dict(attempt=attempt, stderr=stderr.decode('ascii')))
                            break
                        raise RuntimeError('Historical replay failed without a captured hardware stop')
                    break
                slot_mask = ptrace(3, child.pid, 848 + 6 * 8) & 15 if os.WSTOPSIG(status) == signal.SIGTRAP else 0
                if not slot_mask or slot_mask & (slot_mask - 1):
                    raise ValueError('Unexpected hardware observation stop')
                registers = Registers()
                ptrace(12, child.pid, 0, ctypes.addressof(registers))
                selected_slot = slot_mask.bit_length() - 1
                if registers.rip != base + watches[selected_slot]:
                    raise ValueError('Hardware stop address differs from its pinned slot')
                report.update(status='hardware_guard_stop', stopped_attempt=attempt,
                    hardware_stop_slot_mask=slot_mask, stopped_pid=child.pid,
                    runtime_base=hex(base), registers={n: int(getattr(registers, n)) for n, _ in Registers._fields_})
                with open(f'/proc/{child.pid}/mem', 'rb', buffering=0) as memory:
                    if watches[selected_slot] in PROFILES:
                        message = 'Frame actor contact ID-toggle/callee ownership differs'
                    elif watches[selected_slot] in ENTRY_PROFILES:
                        message = ENTRY_MESSAGE
                    else:
                        message = os.pread(memory.fileno(), 160, registers.rsi).split(b'\0', 1)[0].decode('ascii')
                    report['message'] = message
                    contact = message == 'Frame actor contact ID-toggle/callee ownership differs'
                    entry = watches[selected_slot] in ENTRY_PROFILES
                    if contact or entry:
                        if entry:
                            verify_pinned_entry_sites(args.exe.read_bytes())
                        else:
                            verify_pinned_contact_sites(args.exe.read_bytes())
                        reader = StoppedOperandReader(
                            lambda address, size: os.pread(memory.fileno(), size, address),
                            lambda address: ptrace(2, child.pid, address))
                        report['stop_read_witness'] = reader.report
                        live_registers = {name: int(getattr(registers, name)) for name, _ in Registers._fields_}
                        report['native_validation'] = (observe_entry_operands(reader.read, live_registers,
                            watches[selected_slot]) if entry else observe_contact_operands(reader.read,
                            registers.rsp, base, watches[selected_slot], live_registers))
                        repeated = Registers()
                        ptrace(12, child.pid, 0, ctypes.addressof(repeated))
                        witness = reader.finish(bytes(registers) == bytes(repeated))
                        if witness['status'] != 'cross_reader_agreement':
                            report['repeated_registers'] = {n: int(getattr(repeated, n)) for n, _ in Registers._fields_}
                            raise ValueError('Stopped actor memory or register observations disagree')
                    elif message == ENTRY_MESSAGE:
                        report['native_validation'] = dict(status='unsupported_entry_constructor_layout',
                            capture_phase='after-allocation-at-constructor-entry', interpretation_claim=False)
                ptrace(6, child.pid, 848 + 7 * 8, 0)
                for slot in range(len(watches)):
                    ptrace(6, child.pid, 848 + slot * 8, 0)
                ptrace(6, child.pid, 848 + 6 * 8, 0)
                report['debug_register_writes'] += len(watches) + 2
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
                report['collector'] = collect_guard(command, env, args.out)
                report['status'] = 'hardware_guard_captured'
                captured = True
                break
            (args.out / 'hardware.json').write_text(json.dumps(report, indent=2) + '\n')
            if captured:
                break
        if not captured:
            report['status'] = 'other_failures_without_target_capture' if report['uncaptured_failures'] else 'bounded_non_reproduction'
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
    if report['status'] == 'other_failures_without_target_capture':
        raise RuntimeError('Replay failures were observed without the requested validation-branch capture')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('exe', 'symbols', 'fixture', 'root', 'layout', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--attempts', type=int, default=8)
    parser.add_argument('--validation-only', action='store_true')
    guards = parser.add_mutually_exclusive_group()
    guards.add_argument('--contact-guard-bank', choices=('all', *GUARD_BANKS))
    guards.add_argument('--entry-id-guard-bank', choices=('all', *ENTRY_GUARD_BANKS))
    calibration = parser.add_mutually_exclusive_group()
    calibration.add_argument('--calibrate-unit', action='store_true')
    calibration.add_argument('--calibrate-cli', action='store_true')
    run(parser.parse_args())
