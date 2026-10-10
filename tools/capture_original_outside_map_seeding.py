"""Observe unmodified original debris/collapse seeding outside the logical map."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

import capture_original_collapse_map as base

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def capture(out):
    assert not out.exists() and not sys.flags.optimize
    assert os.environ.get('SDL_AUDIODRIVER') == 'dummy'
    base_pin = 'cb430a6be7f33d8c27cb5cf3440f9dfbaebfbadf2ef7bdf5b3e76b1ac59b9439'
    assert sha((ROOT / 'tools/capture_original_collapse_map.py').read_bytes()) == base_pin
    scope = base.functions.__globals__
    base.functions('capture_original_contact_staging', ('module', 'restore'))
    helper = scope['module'](ROOT / 'tools/original_bomb_cpu.py', base.PINS['original_bomb_cpu'], 'outside_map_cpu')
    scope['reader'] = scope['module'](ROOT / 'tools/capture_original_fracture_retirement.py',
        base.PINS['capture_original_fracture_retirement'], 'outside_map_reader')
    import unicorn
    from unicorn import x86_const as regs
    scope.update(unicorn=unicorn, regs=regs)
    base.functions('capture_original_physics_dispatch', ('output', 'restore_state', 'run_dispatch'))
    observed, neutral = helper['BombCPU'](ROOT), helper['BombCPU'](ROOT)
    scope.update(observed=observed, neutral=neutral, enabled=False,
        tracked=[getattr(regs, 'UC_X86_REG_' + name) for name in
            ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')])
    events, seed_entries, visits = [], [], Counter()
    case_index = -1

    def memory(cpu, access, address, size, value, unused):
        if scope['enabled']:
            assert size in (1, 2)
            current = int.from_bytes(bytes(cpu.mem_read(address, size)), 'little') if access == unicorn.UC_MEM_READ else value
            pc = cpu.reg_read(regs.UC_X86_REG_CS) * 16 + cpu.reg_read(regs.UC_X86_REG_IP)
            events.append([case_index, pc, address, size, int(access == unicorn.UC_MEM_WRITE), current])

    def code(cpu, address, size, unused):
        if not scope['enabled']:
            return
        if address in (0x1370e, 0x15102, 0x1557b, 0x1508b):
            visits[hex(address)] += 1
        if address == 0x1370e:
            stack = cpu.reg_read(regs.UC_X86_REG_SS) * 16 + cpu.reg_read(regs.UC_X86_REG_SP)
            seed_entries.append(dict(case=case_index, stack_words=struct.unpack('<6H', bytes(cpu.mem_read(stack, 12))),
                ax=cpu.reg_read(regs.UC_X86_REG_AX), di=cpu.reg_read(regs.UC_X86_REG_DI),
                debris_bound=struct.unpack('<H', bytes(cpu.mem_read(observed.DATA + 0x207e, 2)))[0],
                collapse_count=struct.unpack('<H', bytes(cpu.mem_read(observed.DATA + 0x2080, 2)))[0]))

    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, memory, None, 0x40000, 0x5ffff)
    observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)
    prior = (ROOT / 'tests/gameplay/physics_dispatch_original.bin.gz').read_bytes()
    assert sha(prior) == base.PRIOR_PIN
    initial_state = gzip.decompress(prior)[16:16 + 26730]
    scenes = [
        dict(name='fracture-in-map-debris', first=1953, fracture=True, next_word=0x4100),
        dict(name='fracture-tail-debris', first=2013, fracture=True, next_word=0x4100),
        dict(name='above-tail-collapse', first=2073, target=2013, target_word=0x0012, above=True),
        dict(name='above-tail-debris', first=2073, target=2013, target_word=0x4101, above=True),
        dict(name='blocked-tail-collapse', first=2013, target=2014, target_word=0x0012),
        dict(name='blocked-tail-debris', first=2013, target=2014, target_word=0x4101),
        dict(name='above-in-map-collapse', first=1953, target=1893, target_word=0x0012, above=True),
        dict(name='above-tail-flagged-control', first=2073, target=2013, target_word=0x8012, above=True),
        dict(name='debris-consume-tail-collapse', first=2073, target=2013, target_word=0x0012, debris=True, consume=True),
        dict(name='debris-move-tail-debris', first=2073, target=2013, target_word=0x4101, debris=True),
        dict(name='debris-consume-wrap-collapse', first=40, target=32748, target_word=0x0012, debris=True, consume=True),
        dict(name='debris-move-wrap-collapse', first=40, target=32748, target_word=0x0012, debris=True),
    ]
    out.mkdir(parents=True)
    fixture = bytearray(struct.pack('<8sII', b'LZOS0001', len(scenes), 315602))
    records, chain = [], hashlib.sha256()
    for case_index, scene in enumerate(scenes):
        first, fracture, debris = scene['first'], scene.get('fracture', False), scene.get('debris', False)
        incoming = bytearray(initial_state)
        incoming[18:base.BANK + 1575] = bytes(base.BANK + 1575 - 18)
        struct.pack_into('<HHHIHHHH', incoming, 0, 60, 33, 13, 0x12345678, int(debris), int(not debris), 0, scene.get('next_word', 0xc100))
        vx = 0 if fracture else 96
        if debris:
            incoming[base.DEBRIS:base.DEBRIS + 11] = struct.pack('<HHbbbbBBB', first, 0xc100, vx, 0, vx, 0, 0, 0x60, 0)
        else:
            incoming[base.COLLAPSE:base.COLLAPSE + 15] = struct.pack('<HHHbbbbHBBB',
                first * 2, first * 2, 0x8001, vx, 0, vx, 0, 100 if fracture else vx,
                0 if scene.get('above') else 0x80, 0, 2)
        incoming[-10:] = bytes(10)
        incoming[base.BANK + 1] = 1
        incoming[base.BANK + 1571] = 2
        for executor in (observed, neutral):
            scope['restore_state'](executor, bytes(incoming))
            executor.cpu.mem_write(0x40000 + first, b'\xff' if scene.get('consume') else b'\x60')
            executor.cpu.mem_write(0x50000 + 2 * first, b'\x00\xc1' if debris else b'\x01\x80')
            if fracture:
                executor.cpu.mem_write(0x40000 + first + 60, b'\x01')
            else:
                executor.cpu.mem_write(0x40000 + scene['target'], b'\x61')
                executor.cpu.mem_write(0x50000 + 2 * scene['target'], struct.pack('<H', scene['target_word']))
        initial_ram = bytes(observed.cpu.mem_read(0, 1048576))
        assert initial_ram == bytes(neutral.cpu.mem_read(0, 1048576))
        planes = bytes(observed.cpu.mem_read(0x40000, 131072))
        incoming[18:1998], incoming[1998:5958] = planes[:1980], planes[65536:69496]
        initial = bytes([0, 1, 0, 0]) + incoming + planes
        event_start, seed_start = len(events), len(seed_entries)
        visits.clear()
        actual, ram, registers = scope['run_dispatch'](observed, 13)
        duplicate, duplicate_ram, duplicate_registers = scope['run_dispatch'](neutral, 13)
        assert actual == duplicate and ram == duplicate_ram and registers == duplicate_registers
        assert ram[0x10000:0x1aa20] == initial_ram[0x10000:0x1aa20]
        final_planes = bytes(observed.cpu.mem_read(0x40000, 131072))
        state = actual + final_planes
        assert len(initial) == 157806 and len(state) == 157796
        for suffix, raw in (('initial', initial), ('initial-ram', initial_ram), ('state', state), ('final-ram', ram)):
            (out / (scene['name'] + '-' + suffix + '.bin.gz')).write_bytes(gzip.compress(raw, mtime=0))
        fixture.extend(initial)
        fixture.extend(state)
        chain.update(hashlib.sha256(ram).digest())
        debris_count, collapse_count = struct.unpack_from('<HH', actual, 4)
        cell = first if fracture else scene['target']
        records.append(dict(**scene, initial_sha256=sha(initial), state_sha256=sha(state),
            initial_ram_sha256=sha(initial_ram), final_ram_sha256=sha(ram),
            debris_count=debris_count, collapse_count=collapse_count, added_cell=cell,
            added_cell_outside_logical_map=cell >= 1980,
            final_added_cell_word=struct.unpack_from('<H', final_planes, 65536 + 2 * cell)[0],
            map_reads=sum(not event[4] for event in events[event_start:]),
            map_writes=sum(bool(event[4]) for event in events[event_start:]),
            visits=dict(visits), seed_entries=seed_entries[seed_start:]))
        print(scene['name'] + '=captured', flush=True)
    packed = gzip.compress(fixture, mtime=0)
    event_packed = gzip.compress(json.dumps(events, separators=(',', ':')).encode(), mtime=0)
    (out / 'outside_map_seeding_original.bin.gz').write_bytes(packed)
    (out / 'map-events.json.gz').write_bytes(event_packed)
    report = dict(passed=True, schema='lezac.outside-map-seeding.v1', scenes=records, boundaries=len(scenes),
        fixture_sha256=sha(packed), raw_sha256=sha(fixture), events_sha256=sha(event_packed),
        original_exe_sha256=sha(observed.raw), producer_sha256=sha(Path(__file__).read_bytes()),
        base_producer_sha256=base_pin, dependencies=base.PINS, prior_fixture_sha256=base.PRIOR_PIN,
        observer_neutrality_memory_bytes=1048576, observer_neutrality_registers=14,
        full_ram_hash_chain=chain.hexdigest(), reads=sum(not event[4] for event in events),
        writes=sum(bool(event[4]) for event in events), original_instructions_patched=False,
        original_calls_stubbed=False, hardware_io_permitted=False, seeded=True, natural_route=False,
        actual_app_executed=False, actual_app_parity_proven=False, whole_game_complete=False, all_execution_silent=True)
    (out / 'outside_map_seeding_original.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < 8388608
    print(json.dumps({key: value for key, value in report.items() if key != 'scenes'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.unicorn_path.resolve()))
    capture(args.out.resolve())
