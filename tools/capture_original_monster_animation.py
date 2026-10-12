"""Capture the unmodified original animation prologue, not natural gameplay."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import traceback
from types import ModuleType

ROOT = None
CONTROL = None
created_output = False


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    global ROOT, CONTROL, created_output
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True, help='new output directory; never overwritten')
    parser.add_argument('--unicorn-path', type=Path)
    parser.add_argument('--actor-kind', type=int, choices=(1, 12, 30), default=1)
    parser.add_argument('--actor-behavior', type=int, choices=(2, 3), default=3)
    args = parser.parse_args()
    ROOT, CONTROL = args.root.resolve(), args.out.resolve()
    assert not sys.flags.optimize and os.environ.get('SDL_AUDIODRIVER') == 'dummy'
    assert not CONTROL.exists()
    CONTROL.mkdir(parents=True)
    created_output = True
    helper_path = ROOT / 'tools/original_bomb_cpu.py'
    helper_source = helper_path.read_bytes()
    assert sha(helper_source.replace(b'\r\n', b'\n')) == 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c'
    if args.unicorn_path:
        sys.path.insert(0, str(args.unicorn_path.resolve()))
    helper = ModuleType('original_animation_executor')
    helper.__file__ = str(helper_path)
    exec(compile(helper_source, str(helper_path), 'exec', dont_inherit=True), vars(helper))
    import unicorn
    from unicorn.x86_const import (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX,
        UC_X86_REG_DX, UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_BP, UC_X86_REG_SP,
        UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS,
        UC_X86_REG_IP, UC_X86_REG_EFLAGS)
    registers = (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX,
        UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_BP, UC_X86_REG_SP,
        UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS,
        UC_X86_REG_IP, UC_X86_REG_EFLAGS)
    original = helper.BombCPU(ROOT)
    neutral = helper.BombCPU(ROOT)
    actor = original.DATA + 0x1bae + 38
    visual = original.DATA + 0xc21e + 2 * 8
    writes = []

    def observe_write(cpu, access, address, size, value, user):
        if address <= visual + 6 < address + size:
            writes.append((address, size, value))

    original.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, observe_write)
    seeds = []
    for mode in (0, 1, 2, 3, 4, 255):
        for label, active in (
            ('upper', (9, 6, 9, 0, 0, mode, 1)),
            ('lower', (6, 6, 9, 0, 0, mode, 255)),
            ('overshoot', (8, 6, 9, 0, 0, mode, 3)),
            ('below', (7, 6, 9, 0, 0, mode, 253)),
            ('counter_wrap', (7, 6, 9, 255, 2, mode, 1)),
            ('max_delay', (7, 6, 9, 254, 255, mode, 1)),
            ('byte_wrap', (254, 6, 255, 0, 0, mode, 3)),
            ('zero_step', (9, 6, 9, 0, 0, mode, 0)),
        ):
            seeds.append((f'mode{mode}_{label}', bytes(active), bytes((43, 43, 46, 2, 2, 2, 255))))
    for step in (128, 127, 0, 1, 255):
        seeds.append((f'backup_step{step}', bytes((9, 6, 9, 0, 0, 3, 1)),
            bytes((44, 43, 46, 0, 0, 1, step))))
    lines = ['capture=monster_animation_original_v1 seeded=1 cpu_only=1 instruction_patches=0 call_stubs=0 hardware_io=0']
    report = dict(passed=False, source_sha256=__source_sha256__, helper_sha256=sha(helper_source),
        recorded_utc=datetime.now(timezone.utc).isoformat(), helper_path=str(helper_path),
        helper_normalized_sha256=sha(helper_source.replace(b'\r\n', b'\n')),
        root=str(ROOT), unicorn_version=unicorn.__version__, unicorn_path=str(unicorn.__file__),
        original_exe_sha256=sha(original.raw), cases=[], original_range='CS:6078..615A',
        compiled_cpp_comparison=False, actual_app_comparison=False, natural_route_claim=False,
        new_native_game_capture=False, original_instructions_patched=False, original_calls_stubbed=False,
        hardware_io_permitted=False, observer_neutrality=True, bytes_per_neutrality_return=1024**2,
        tracked_registers=14, audio='dummy', whole_game_complete=False)
    report.update(actor_kind=args.actor_kind, actor_behavior=args.actor_behavior,
                  stop_before_behavior_dispatch=True)
    updates = restores = descriptor_writes = 0
    for name, active, backup in seeds:
        raw = bytearray(38)
        raw[0], raw[1], raw[2], raw[21] = args.actor_kind, 2, 200, args.actor_behavior
        raw[22:29], raw[29:36] = active, backup
        for executor in (original, neutral):
            cpu = executor.cpu
            cpu.context_restore(executor.initial_context)
            cpu.mem_write(0, executor.initial_memory)
            cpu.mem_write(actor, bytes(raw))
            cpu.mem_write(executor.DATA + 0xc322, executor.descriptors)
            cpu.mem_write(visual, struct.pack('<HH4s', 104, 168, executor.descriptors[7 * 4:8 * 4]))
            cpu.mem_write(0x8f000 - 0x3a, struct.pack('<HH', 0x1bae + 38 + 22, 0x1aa2))
            cpu.mem_write(0x8f000 + 4, struct.pack('<HH', 0x1bae + 38, 0x1aa2))
            cpu.mem_write(0x8f000 - 0x13, b'\x02')
        visible = 6
        lines.append(f'case name={name} active={active.hex()} backup={backup.hex()} visible={visible} samples=12')
        case = dict(name=name, initial=active.hex(), backup=backup.hex(), ticks=[])
        report['cases'].append(case)
        for sample in range(12):
            before = bytes(original.cpu.mem_read(actor, 38))
            writes.clear()
            for executor in (original, neutral):
                executor.registers(0xf000, 0xff00)
                executor.instructions = 0
                executor.cpu.emu_start(0x16078, 0x1615a, count=10000)
                executor.assert_return(0x615a, 0xf000, 0xff00)
            assert bytes(original.cpu.mem_read(0, 1024**2)) == bytes(neutral.cpu.mem_read(0, 1024**2))
            assert [original.cpu.reg_read(r) for r in registers] == [neutral.cpu.reg_read(r) for r in registers]
            after = bytes(original.cpu.mem_read(actor, 38))
            assert after[:22] == before[:22] and after[29:] == before[29:]
            assert len(writes) in (0, 1)
            advanced = len(writes)
            if advanced:
                visible = (after[22] - 1) & 255
                descriptor_writes += 1
                if before[27] == 3 and after[22:29] == backup:
                    restores += 1
            lines.append(f'tick sample={sample} advanced={advanced} active={after[22:29].hex()} backup={after[29:36].hex()} visible={visible}')
            case['ticks'].append(dict(sample=sample, active=after[22:29].hex(), advanced=advanced,
                visible=visible, descriptor_word=bytes(original.cpu.mem_read(visual + 6, 2)).hex(),
                instructions=original.instructions,
                memory_sha256=sha(bytes(original.cpu.mem_read(0, 1024**2))),
                registers=[original.cpu.reg_read(r) for r in registers]))
            updates += 1
        lines.append('end samples=12')
    lines.append(f'complete cases={len(seeds)} updates={updates}')
    fixture = ('\n'.join(lines) + '\n').encode('ascii')
    assert len(fixture) < 128 * 1024 and restores >= 5 and descriptor_writes > 100
    fingerprint = 14695981039346656037
    for value in fixture:
        fingerprint = ((fingerprint ^ value) * 1099511628211) & ((1 << 64) - 1)
    report.update(passed=True, case_count=len(seeds), original_updates=updates,
        backup_restorations=restores, descriptor_write_boundaries=descriptor_writes,
        fixture_sha256=sha(fixture), fixture_fnv1a64=f'{fingerprint:016x}', fixture_bytes=len(fixture))
    with (CONTROL / 'monster_animation_original.txt').open('xb') as target:
        target.write(fixture)
    report_raw = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    assert len(report_raw) < 512 * 1024
    with (CONTROL / 'original-animation-v1.json').open('xb') as target:
        target.write(report_raw)
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}), flush=True)


if __name__ == '__main__':
    path = Path(__file__).resolve()
    raw = path.read_bytes()
    namespace = dict(__file__=str(path), __name__='bound_original_animation_capture', __source_sha256__=sha(raw))
    exec(compile(raw, str(path), 'exec', dont_inherit=True), namespace)
    try:
        namespace['main']()
    except BaseException:
        if namespace['created_output']:
            with (namespace['CONTROL'] / 'failure.json').open('x', encoding='utf-8') as output:
                json.dump(dict(passed=False, source_sha256=namespace['__source_sha256__'],
                    recorded_utc=datetime.now(timezone.utc).isoformat(),
                    error=traceback.format_exc()), output, indent=2, sort_keys=True)
        raise
