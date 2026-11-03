"""Run inside GDB: retain bounded typed state at an unexpected ownership throw."""
import hashlib
import json
import os
from pathlib import Path
import resource
import struct

import gdb

EXPECTED = 'b1c719393f987cd2a98090055c8cc06d5d71589090599a36f32c4d2fd5da47f6'
REGS = 'ax bx cx dx si di bp cs ds es ss sp ip flags'.split()
FIELDS = 'gameSegment idToggleMask callerSs callerSp callerBp outcome actorKind dispatchedInstructions timerInstructions timerDeliveries'.split()


def executable_segments(path):
    raw = path.read_bytes()
    if raw[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Expected a little-endian ELF64 image')
    offset, = struct.unpack_from('<Q', raw, 32)
    stride, count = struct.unpack_from('<HH', raw, 54)
    if stride != 56 or count > 64 or offset + stride * count > len(raw):
        raise ValueError('ELF program-header bounds differ')
    result = []
    for i in range(count):
        kind, flags, start, address, _, size, _, _ = struct.unpack_from('<II6Q', raw, offset + i * stride)
        if kind == 1 and flags & 1:
            if start + size > len(raw) or size > 2 * 1024**2:
                raise ValueError('Owned executable reserve differs')
            result.append((address, raw[start:start + size]))
    if not result:
        raise ValueError('No owned executable bytes')
    return result


def snapshot(value, depth=0):
    if depth > 8 or value.is_optimized_out:
        return {'unavailable': 'depth or optimized value'}
    result = {'type': str(value.type), 'address': str(value.address)}
    if str(value.type.strip_typedefs()).endswith('DosGetTimeRegisters'):
        result['registers'] = {key: int(value[key]) for key in REGS}
        return result
    for name in FIELDS:
        try:
            result[name] = int(value[name])
        except (gdb.error, TypeError, ValueError):
            pass
    for name in ('registers', 'cpu', 'state_'):
        try:
            child = value[name]
            if name == 'registers':
                result[name] = {key: int(child[key]) for key in REGS}
            else:
                result[name] = snapshot(child, depth + 1)
        except (gdb.error, TypeError, ValueError):
            pass
    try:
        callee = value['callee']
        index = int(callee['_M_index'])
        result['callee_index'] = index
        if 0 <= index < 8:
            selected = callee.type.strip_typedefs().template_argument(index)
            child = callee['_M_u'].address.cast(selected.pointer()).dereference()
            result['callee'] = snapshot(child, depth + 1)
    except (gdb.error, RuntimeError, TypeError, ValueError):
        pass
    return result


class OwnershipThrow(gdb.Breakpoint):
    message = None

    def stop(self):
        try:
            address = int(gdb.newest_frame().read_register('rsi'))
            raw = bytes(gdb.selected_inferior().read_memory(address, 160)).split(b'\0', 1)[0]
            text = raw.decode('ascii')
            if text.startswith(('Frame actor', 'Actor ')) and ('ownership differs' in text or 'ID-toggle' in text):
                self.message = text
                return True
        except (gdb.error, UnicodeError):
            pass
        return False


def local_value(frame, name):
    try:
        block = frame.block()
    except RuntimeError as error:
        raise ValueError('Frame has no lexical block') from error
    while block and not block.is_global and not block.is_static:
        for symbol in block:
            if symbol.name == name and (symbol.is_argument or symbol.is_variable):
                return frame.read_var(symbol)
        if block.function:
            break
        block = block.superblock
    raise ValueError('Local variable is unavailable: ' + name)


def run():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    out = Path(os.environ['LEZAC_GUARD_OUT']).resolve()
    executable = Path(os.environ['LEZAC_GUARD_EXE']).resolve(strict=True)
    symbols = Path(os.environ['LEZAC_GUARD_SYMBOLS']).resolve(strict=True)
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM diagnostic directory')
    if hashlib.sha256(executable.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Historical ELF identity differs')
    segments = executable_segments(executable)
    if segments != executable_segments(symbols):
        raise ValueError('External DWARF build has different executable bytes')
    protected = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in
        (executable, symbols, Path(os.environ['LEZAC_GUARD_FIXTURE']).resolve(strict=True),
         Path(os.environ['LEZAC_GUARD_ROOT']).resolve(strict=True) / 'LEZAC.EXE', Path(__file__).resolve())}
    out.mkdir()
    for command in ('set pagination off', 'set confirm off', 'set print frame-arguments none',
                    'set disable-randomization off', 'set startup-with-shell off', 'set breakpoint pending on'):
        gdb.execute(command)
    gdb.execute('file ' + str(executable))
    gdb.execute('set args ' + os.environ['LEZAC_GUARD_FIXTURE'] + ' ' + os.environ['LEZAC_GUARD_ROOT'])
    attach = int(os.environ.get('LEZAC_GUARD_ATTACH_PID', '0'))
    watch = None if attach else OwnershipThrow('_ZNSt16invalid_argumentC1EPKc', internal=True)
    report = dict(status='bounded_non_reproduction', historical_elf_sha256=EXPECTED,
        external_dwarf_executable_bytes_identical=True, runs=0, core_dump_limit=0,
        manual_register_or_data_writes=0, debugger_inferior_function_calls=0, full_ram_artifacts=0,
        tool_installed_software_breakpoints=not bool(attach), attached_after_throw_stop=bool(attach),
        calibration=os.environ.get('LEZAC_GUARD_CALIBRATION', '0') == '1',
        optimized_dwarf_values_are_advisory=True,
        protected_inputs_sha256=protected,
        tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        intermittent_hold_cleared=False)
    exits = []
    gdb.events.exited.connect(lambda event: exits.append(getattr(event, 'exit_code', None)))
    for attempt in range(1 if attach else 8):
        report['runs'] = attempt + 1
        if attach:
            gdb.execute('attach ' + str(attach), to_string=True)
            message = os.environ['LEZAC_GUARD_STOP_MESSAGE']
        else:
            gdb.execute('run', to_string=True)
            message = watch.message
        if not message:
            if gdb.selected_inferior().pid:
                report['status'] = 'unexpected_stop'
                break
            if len(exits) != attempt + 1 or exits[-1] != 0:
                raise ValueError('Historical replay failed without a captured ownership throw')
            continue
        gdb.execute('disable breakpoints')
        inferior = gdb.selected_inferior()
        maps = Path(f'/proc/{inferior.pid}/maps').read_text().splitlines()
        owned = [line.split() for line in maps if line.endswith(str(executable)) and 'x' in line.split()[1]]
        if len(owned) != 1:
            raise ValueError('Owned runtime image mapping differs')
        base = int(owned[0][0].split('-')[0], 16) - int(owned[0][2], 16)
        report['main_before_relocation'] = str(gdb.parse_and_eval('(void*)&main'))
        gdb.execute('add-symbol-file ' + str(symbols) + ' -o ' + hex(base), to_string=True)
        gdb.execute('sharedlibrary', to_string=True)
        report['main_after_relocation'] = str(gdb.parse_and_eval('(void*)&main'))
        report['shared_library_info'] = gdb.execute('info sharedlibrary', to_string=True)
        report['external_dwarf_relocated_base'] = hex(base)
        observed = []
        for address, raw in segments:
            actual = bytes(inferior.read_memory(base + address, len(raw)))
            if actual != raw:
                raise ValueError('Owned code changed before the throw')
            observed.append(dict(address=address, bytes=len(raw), sha256=hashlib.sha256(actual).hexdigest()))
        frame = gdb.newest_frame()
        report.update(status='failure_throw_captured', message=message, pid=inferior.pid,
                      owned_code_verified=observed, frames=[], registers={}, case_context=[], backtrace=[])
        for name in 'rax rbx rcx rdx rsi rdi rbp rsp rip r8 r9 r10 r11 r12 r13 r14 r15 eflags'.split():
            report['registers'][name] = str(frame.read_register(name))
        frame_count = 0
        while frame and frame_count < 64:
            frame_count += 1
            item = dict(name=frame.name(), pc=hex(frame.pc()), variables={})
            report['backtrace'].append(dict(name=(item['name'] or '')[:300], pc=item['pc']))
            for name in ('index', 'row', 'cursor', 'mode', 'limit', 'budget'):
                try:
                    item['variables'][name] = int(local_value(frame, name))
                except (gdb.error, TypeError, ValueError):
                    pass
            if item['variables']:
                report['case_context'].append(dict(name=item['name'], pc=item['pc'], **item['variables']))
            if len(report['frames']) >= 16 or not (item['name'] and (
                    'lezac::core::' in item['name'] or 'namespace)::' in item['name'] or item['variables'])):
                frame = frame.older()
                continue
            for name in ('this', 'state', 'child', 'active', 'actual', 'expected'):
                try:
                    value = local_value(frame, name)
                    if value.type.code == gdb.TYPE_CODE_PTR:
                        value = value.dereference()
                    if 'lezac::core::' in str(value.type):
                        item['variables'][name] = snapshot(value)
                except (gdb.error, TypeError, ValueError):
                    pass
            report['frames'].append(item)
            frame = frame.older()
        break
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != report['tool_sha256']:
        raise ValueError('Guard capture source changed during execution')
    if any(hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest for path, digest in protected.items()):
        raise ValueError('Protected guard-capture input changed')
    report['protected_inputs_preserved'] = True
    raw = (json.dumps(report, indent=2) + '\n').encode()
    if len(raw) > 65536:
        report['frames'] = report.get('frames', [])[:8]
        raw = (json.dumps(report, indent=2) + '\n').encode()
    if len(raw) > 65536:
        raise ValueError('Typed guard report exceeded its bounded reserve')
    (out / 'guard.json').write_bytes(raw)
    if gdb.selected_inferior().pid:
        gdb.execute('kill')
    print('actor_guard_capture=' + report['status'] + ' bytes=' + str(len(raw)))
    if report['status'] == 'unexpected_stop':
        gdb.execute('quit 1')


try:
    run()
except BaseException as error:
    out = Path(os.environ['LEZAC_GUARD_OUT']).resolve()
    if out.is_relative_to(Path('/dev/shm')) and out.is_dir():
        path = out / 'capture-error.json'
        if not path.exists():
            with path.open('x') as stream:
                json.dump(dict(status='failed', error=repr(error), full_ram_artifacts=0), stream)
    if gdb.selected_inferior().pid:
        gdb.execute('kill')
    gdb.execute('quit 1')
