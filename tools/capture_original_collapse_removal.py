"""Capture unmodified original fracture cleanup, retirement and wrapped actor selection."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

import capture_original_collapse_map as base

BASE_PIN = 'cb430a6be7f33d8c27cb5cf3440f9dfbaebfbadf2ef7bdf5b3e76b1ac59b9439'
ROOT = Path(__file__).resolve().parents[1]
INITIAL, STATE = 157806, 157796


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def capture(out):
    assert not out.exists() and not sys.flags.optimize
    assert os.environ.get('SDL_AUDIODRIVER') == 'dummy'
    assert sha((ROOT / 'tools/capture_original_collapse_map.py').read_bytes()) == BASE_PIN
    scope = base.functions.__globals__
    base.functions('capture_original_contact_staging', ('module', 'restore'))
    helper = scope['module'](ROOT / 'tools/original_bomb_cpu.py', base.PINS['original_bomb_cpu'], 'removal_cpu')
    scope['reader'] = scope['module'](ROOT / 'tools/capture_original_fracture_retirement.py',
        base.PINS['capture_original_fracture_retirement'], 'removal_reader')
    import unicorn
    from unicorn import x86_const as regs
    scope.update(unicorn=unicorn, regs=regs)
    base.functions('capture_original_physics_dispatch', ('output', 'restore_state', 'run_dispatch'))
    observed, neutral = helper['BombCPU'](ROOT), helper['BombCPU'](ROOT)
    scope.update(observed=observed, neutral=neutral, enabled=False,
        tracked=[getattr(regs, 'UC_X86_REG_' + name) for name in
            ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')])
    events, visits = [], []
    case_index = -1

    def memory(cpu, access, address, size, value, unused):
        if scope['enabled']:
            assert size in (1, 2)
            current = int.from_bytes(bytes(cpu.mem_read(address, size)), 'little') if access == unicorn.UC_MEM_READ else value
            pc = cpu.reg_read(regs.UC_X86_REG_CS) * 16 + cpu.reg_read(regs.UC_X86_REG_IP)
            events.append(dict(case=case_index, pc=hex(pc), address=hex(address), size=size,
                write=access == unicorn.UC_MEM_WRITE, value=current))

    def code(cpu, address, size, unused):
        if scope['enabled'] and address in (0x1558c, 0x15595, 0x1559e, 0x1508b, 0x150c8):
            visits.append(dict(case=case_index, pc=hex(address), ax=cpu.reg_read(regs.UC_X86_REG_AX),
                di=cpu.reg_read(regs.UC_X86_REG_DI),
                first=struct.unpack('<H', bytes(cpu.mem_read(observed.DATA + 0x2068, 2)))[0],
                top_right=struct.unpack('<H', bytes(cpu.mem_read(observed.DATA + 0x206a, 2)))[0],
                last=struct.unpack('<H', bytes(cpu.mem_read(observed.DATA + 0x206c, 2)))[0],
                columns=struct.unpack('<H', bytes(cpu.mem_read(observed.DATA + 0x205a, 2)))[0],
                rng=struct.unpack('<I', bytes(cpu.mem_read(observed.DATA + 0x1afe, 4)))[0]))

    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, memory, None, 0x40000, 0x5ffff)
    observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)
    prior = (ROOT / 'tests/gameplay/physics_dispatch_original.bin.gz').read_bytes()
    assert sha(prior) == base.PRIOR_PIN
    initial_state = gzip.decompress(prior)[16:16 + 26730]
    scenes = [
        ('fracture-word-right', 32767, 1, 96, 0, 0, 0, None, [60, 16380, 16440]),
        ('fracture-word-up', 40, 1, 0, -96, 0, 0, None, [32749, 32758, 32759]),
        ('fracture-row-cross', 58, 2, 96, 0, 0, 0, None, []),
        ('fracture-clear-below', 1220, 1, 0, 0, 100, 0, 1280, [1340, 1460, 1820, 1880]),
        ('fracture-clear-tail', 1953, 1, 0, 0, 100, 0, 2013, [2073, 2913, 2973]),
        ('retirement-tail', 2013, 1, 0, 0, 0, 94, 2073, [2133]),
        ('retirement-word-end', 32767, 1, 0, 0, 0, 94, 32827, [32707]),
    ]
    out.mkdir(parents=True)
    fixture = bytearray(struct.pack('<8sII', b'LZRM0001', len(scenes), INITIAL + STATE))
    rows, chain = [], hashlib.sha256()
    for case_index, (name, first, columns, vx, vy, magnitude, rest, support, orphans) in enumerate(scenes):
        incoming = bytearray(initial_state)
        incoming[18:base.BANK + 1575] = bytes(base.BANK + 1575 - 18)
        struct.pack_into('<HHHIHHHH', incoming, 0, 60, 33, 13, 0x12345678, 0, 1, 0, 0xc100)
        incoming[base.COLLAPSE:base.COLLAPSE + 15] = struct.pack('<HHHbbbbHBBB',
            first * 2, (first + columns - 1) * 2, 0x8001, vx, vy, vx, vy, magnitude, 0x80, rest, columns)
        incoming[-10:] = bytes(10)
        incoming[base.BANK + 1] = 1
        incoming[base.BANK + 1571] = 2
        for executor in (observed, neutral):
            scope['restore_state'](executor, bytes(incoming))
            for cell in list(range(first, first + columns)) + orphans:
                executor.cpu.mem_write(0x40000 + cell, b'\x60')
                executor.cpu.mem_write(0x50000 + ((2 * cell) & 65535), b'\x01\x80')
            if support is not None:
                executor.cpu.mem_write(0x40000 + support, b'\x01')
        initial_ram = bytes(observed.cpu.mem_read(0, 1048576))
        assert initial_ram == bytes(neutral.cpu.mem_read(0, 1048576))
        planes = bytes(observed.cpu.mem_read(0x40000, 131072))
        incoming[18:1998], incoming[1998:5958] = planes[:1980], planes[65536:69496]
        initial = bytes([0, 1, 0, 0]) + incoming + planes
        event_start, visit_start = len(events), len(visits)
        actual, ram, registers = scope['run_dispatch'](observed, 13)
        duplicate, duplicate_ram, duplicate_registers = scope['run_dispatch'](neutral, 13)
        assert actual == duplicate and ram == duplicate_ram and registers == duplicate_registers
        final_planes = bytes(observed.cpu.mem_read(0x40000, 131072))
        state = actual + final_planes
        assert len(initial) == INITIAL and len(state) == STATE
        for suffix, raw in (('initial', initial), ('initial-ram', initial_ram), ('state', state), ('final-ram', ram)):
            (out / (name + '-' + suffix + '.bin.gz')).write_bytes(gzip.compress(raw, mtime=0))
        fixture.extend(initial)
        fixture.extend(state)
        chain.update(hashlib.sha256(ram).digest())
        rows.append(dict(name=name, first=first, columns=columns, velocity=[vx, vy], old_magnitude=magnitude,
            rest_ticks=rest, support=support, initial_sha256=sha(initial), state_sha256=sha(state),
            initial_ram_sha256=sha(initial_ram), final_ram_sha256=sha(ram),
            debris_count=struct.unpack_from('<H', actual, 4)[0], collapse_count=struct.unpack_from('<H', actual, 6)[0],
            actor_count=actual[25139 + 1570],
            orphan_words={str(cell): struct.unpack_from('<H', final_planes, 65536 + ((2 * cell) & 65535))[0] for cell in orphans},
            events=events[event_start:], visits=visits[visit_start:]))
    packed = gzip.compress(fixture, mtime=0)
    report = dict(schema=1, passed=True, scenes=rows, boundaries=7, initial_bytes=INITIAL, state_bytes=STATE,
        fixture_sha256=sha(packed), raw_sha256=sha(fixture), original_exe_sha256=sha(observed.raw),
        producer_sha256=sha(Path(__file__).read_bytes()), base_producer_sha256=BASE_PIN,
        dependencies=base.PINS, prior_fixture_sha256=base.PRIOR_PIN,
        observer_neutrality_memory_bytes=1048576, observer_neutrality_registers=14,
        reads=sum(not row['write'] for row in events), writes=sum(row['write'] for row in events),
        full_ram_hash_chain=chain.hexdigest(), original_instructions_patched=False, original_calls_stubbed=False,
        hardware_io_permitted=False, seeded=True, natural_route=False, actual_app_executed=False,
        actual_app_parity_proven=False, whole_game_complete=False, all_execution_silent=True)
    (out / 'collapse_removal_original.bin.gz').write_bytes(packed)
    (out / 'collapse_removal_original.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < 8388608
    print(json.dumps({key: value for key, value in report.items() if key != 'scenes'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path)
    args = parser.parse_args()
    if args.unicorn_path:
        sys.path.insert(0, str(args.unicorn_path.resolve()))
    capture(args.out.resolve())
