"""Capture bounded original collapse map tails and wrapped rectangle movement.

Only input state and observer hooks are changed. The original coupled caller,
its callees and machine instructions remain unmodified. No hardware I/O runs.
"""
import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
DEBRIS, COLLAPSE, BANK, INPUT = 5958, 21380, 25145, 26727
PINS = {
    'capture_original_contact_staging': 'f703d8bd4cd3e646c8b78ae98a78b85d15fb42d58a11f271ad06d9696c01c9d1',
    'original_bomb_cpu': 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c',
    'capture_original_fracture_retirement': '50cd6bc4d44a9d805b2598d89b7c626a34c0eb5339b8350b8f8125ffa6c74c73',
    'capture_original_physics_dispatch': '927dce949bafdf712cc953a778599a52357df6a2451eff90f93857601ff563ef',
}
PRIOR_PIN = 'e6552d851b95d4b30d931887eee00d75beafede7a173dabf3add77504c83b1cf'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def functions(name, names):
    path = ROOT / 'tools' / (name + '.py')
    raw = path.read_bytes()
    assert sha(raw) == PINS[name]
    nodes = [node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), globals())


def capture(out):
    global enabled, case_index, step, word_base, observed, neutral
    assert not out.exists() and not sys.flags.optimize
    assert os.environ.get('SDL_AUDIODRIVER') == 'dummy'
    functions('capture_original_contact_staging', ('module', 'restore'))
    helper = module(ROOT / 'tools/original_bomb_cpu.py', PINS['original_bomb_cpu'], 'collapse_map_cpu')
    globals()['reader'] = module(ROOT / 'tools/capture_original_fracture_retirement.py',
        PINS['capture_original_fracture_retirement'], 'collapse_map_reader')
    import unicorn
    from unicorn import x86_const as regs
    globals().update(unicorn=unicorn, regs=regs)
    functions('capture_original_physics_dispatch', ('output', 'restore_state', 'run_dispatch'))
    observed, neutral = helper['BombCPU'](ROOT), helper['BombCPU'](ROOT)
    globals()['tracked'] = [getattr(regs, 'UC_X86_REG_' + name) for name in
        ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
    events = []
    enabled = False

    def memory(cpu, access, address, size, value, unused):
        if enabled:
            assert size in (1, 2)
            current = int.from_bytes(bytes(cpu.mem_read(address, size)), 'little') if access == unicorn.UC_MEM_READ else value
            pc = cpu.reg_read(regs.UC_X86_REG_CS) * 16 + cpu.reg_read(regs.UC_X86_REG_IP)
            events.append([case_index, step, pc, address, size, int(access == unicorn.UC_MEM_WRITE), current])

    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, memory, None, 0x40000, 0x5ffff)
    prior_packed = (ROOT / 'tests/gameplay/physics_dispatch_original.bin.gz').read_bytes()
    assert sha(prior_packed) == PRIOR_PIN
    base = gzip.decompress(prior_packed)[16:16 + 26730]
    # name, first cell, columns, rows, vx, vy, layout, solid, update count
    scenes = [
        ('logical-bottom-free', 1953, 1, 1, 0, 96, 0, False, 2),
        ('logical-tail-free', 2013, 1, 1, 0, 96, 0, False, 2),
        ('word-underflow-up', 40, 1, 1, 0, -96, 0, False, 2),
        ('word-overflow-down', 32740, 1, 1, 0, 96, 0, False, 2),
        ('word-underflow-left', 0, 1, 1, -96, 0, 0, False, 2),
        ('word-overflow-right', 32767, 1, 1, 96, 0, 0, False, 2),
        ('stationary-tail', 2013, 1, 1, 0, 0, 0, False, 2),
        ('logical-bottom-solid', 1953, 1, 1, 0, 96, 0, True, 2),
        ('shared-bottom-free', 1953, 1, 1, 0, 96, 1, False, 2),
        ('shared-bottom-solid', 1953, 1, 1, 0, 96, 1, True, 2),
        ('shared-tail-free', 2013, 1, 1, 0, 96, 1, False, 2),
        ('shared-word-overflow', 32767, 1, 1, 96, 0, 1, False, 2),
        ('bottom-two', 1952, 2, 1, 0, 96, 0, False, 2),
        ('bottom-square', 1892, 2, 2, 0, 96, 0, False, 2),
        ('row-cross-free', 58, 2, 1, 96, 0, 0, False, 1),
        ('row-cross-supported', 58, 2, 1, 96, 0, 0, False, 1),
        ('word-cross-two', 32766, 2, 1, 96, 0, 0, False, 1),
        ('word-cross-square', 32700, 2, 2, 0, 96, 0, False, 1),
        ('right-square', 1220, 2, 2, 96, 0, 0, False, 2),
    ]
    fixture = bytearray(b'LZCB0001' + struct.pack('<II', len(scenes), 34))
    records, chain = [], hashlib.sha256()
    out.mkdir(parents=True)
    for case_index, (name, first, columns, rows, vx, vy, layout, solid, steps) in enumerate(scenes):
        word_base = 0x50000 if layout == 0 else 0x407d0
        last = first + (rows - 1) * 60 + columns - 1
        incoming = bytearray(base)
        incoming[18:BANK + 1575] = bytes(BANK + 1575 - 18)
        struct.pack_into('<HHHIHHHH', incoming, 0, 60, 33, 13, 0x12345678, 0, 1, 0, 0xc100)
        incoming[COLLAPSE:COLLAPSE + 15] = struct.pack('<HHHbbbbHBBB',
            first * 2, last * 2, 0x8001, vx, vy, vx, vy,
            0 if solid else abs(vx) + abs(vy), 0x80, 0, columns * rows)
        incoming[-10:] = bytes(10)
        incoming[BANK + 1] = 1
        incoming[BANK + 1571] = 2
        delta = (-1 if vx < 0 else 1 if vx else 0) + (-60 if vy < 0 else 60 if vy else 0)
        for executor in (observed, neutral):
            restore_state(executor, bytes(incoming))
            executor.cpu.mem_write(executor.DATA + 0x6612, struct.pack('<HH', 0, word_base >> 4))
            executor.cpu.mem_write(executor.DATA + 0x206e, struct.pack('<H', word_base >> 4))
            for y in range(rows):
                for x in range(columns):
                    cell = first + y * 60 + x
                    executor.cpu.mem_write(0x40000 + cell, b'\x60')
                    executor.cpu.mem_write(word_base + ((2 * cell) & 65535), b'\x01\x80')
            if solid:
                executor.cpu.mem_write(0x40000 + ((first + delta) & 32767), b'\x01')
            if name == 'row-cross-supported':
                executor.cpu.mem_write(0x40000 + 119, b'\x01\x01')
        initial_ram = bytes(observed.cpu.mem_read(0, 1048576))
        assert initial_ram == bytes(neutral.cpu.mem_read(0, 1048576))
        (out / (name + '-initial-ram.bin.gz')).write_bytes(gzip.compress(initial_ram, mtime=0))
        planes = bytes(observed.cpu.mem_read(0x40000, 65536)) + bytes(observed.cpu.mem_read(word_base, 65536))
        # The raw probes seed maps after restore; include those actual seeds in App input.
        incoming[18:1998] = planes[:1980]
        incoming[1998:5958] = planes[65536:65536 + 3960]
        initial = bytes([layout, steps, 0, 0]) + incoming + planes
        assert len(initial) == 157806
        fixture.extend(initial)
        row = dict(name=name, layout=layout, steps=steps, first=first, last=last,
            columns=columns, rows=rows, delta=delta, initial_sha256=sha(initial),
            initial_ram_sha256=sha(initial_ram), states=[])
        for step in range(steps):
            actual, ram, registers = run_dispatch(observed, 13 + step)
            duplicate, duplicate_ram, duplicate_registers = run_dispatch(neutral, 13 + step)
            actual = actual[:1992] + bytes(observed.cpu.mem_read(word_base, 3960)) + actual[5952:]
            duplicate = duplicate[:1992] + bytes(neutral.cpu.mem_read(word_base, 3960)) + duplicate[5952:]
            assert actual == duplicate and ram == duplicate_ram and registers == duplicate_registers
            state_planes = bytes(observed.cpu.mem_read(0x40000, 65536)) + bytes(observed.cpu.mem_read(word_base, 65536))
            state = actual + state_planes
            assert len(state) == 157796
            fixture.extend(state)
            chain.update(hashlib.sha256(ram).digest())
            row['states'].append(dict(sha256=sha(state), ram_sha256=sha(ram)))
        records.append(row)
        print(name + '=captured', flush=True)
    packed = gzip.compress(fixture, mtime=0)
    event_packed = gzip.compress(json.dumps(events, separators=(',', ':')).encode(), mtime=0)
    report = dict(schema=1, scenes=len(scenes), boundaries=34, state_bytes=157796,
        input_bytes=157806, map_plane_bytes=131072, fixture_sha256=sha(packed), raw_sha256=sha(fixture),
        events_sha256=sha(event_packed), producer_sha256=sha(Path(__file__).read_bytes()),
        dependencies=PINS, prior_fixture_sha256=PRIOR_PIN, original_exe_sha256=sha(observed.raw),
        observer_neutrality_memory_bytes=1048576, observer_neutrality_registers=14,
        full_ram_hash_chain=chain.hexdigest(), reads=sum(not event[5] for event in events),
        writes=sum(bool(event[5]) for event in events), records=records,
        original_instructions_patched=False, original_calls_stubbed=False, hardware_io_permitted=False,
        seeded=True, natural_route=False, natural_heap_initialization_proven=False,
        production_app_executed=False, whole_game_complete=False, all_execution_silent=True)
    (out / 'collapse_map_original.bin.gz').write_bytes(packed)
    (out / 'collapse_map_events.json.gz').write_bytes(event_packed)
    (out / 'collapse_map_original.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'records'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path)
    args = parser.parse_args()
    if args.unicorn_path:
        sys.path.insert(0, str(args.unicorn_path.resolve()))
    capture(args.out.resolve())
