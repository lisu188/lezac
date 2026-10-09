"""Observe one-live-record support, tipping and retirement in the original updater."""
import argparse
import ast
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

from capture_original_collapse_lane_history import (
    BANK, BASE_SHA, COLLAPSE, CPU_SHA, DEBRIS, INPUT, READER_SHA, STAGING_SHA, sha)


def matrix():
    for width in (2, 3, 6, 7):
        for height in (1, 3):
            for layout in ('centered', 'left-edge', 'right-edge', 'none'):
                for vx in (-15, 0, 15):
                    yield width, height, layout, vx


def request(base, case, index):
    width, height, layout, vx = case
    raw = bytearray(base)
    raw[18:DEBRIS] = bytes(DEBRIS - 18)
    raw[DEBRIS:COLLAPSE] = b'\x55' * (COLLAPSE - DEBRIS)
    raw[COLLAPSE:BANK] = b'\x69' * (BANK - COLLAPSE)
    bound = (199, 1599, 1600)[(index // 3) % 3]
    for slot in range(bound - 199):
        struct.pack_into('<HHbbbbBBB', raw, DEBRIS + slot * 11,
                         3, 0xc0c8 + slot, -49, 49, 0, 0, 0, 0x55, 0xa5)
    first = 20 * 60 + 20
    last = first + (height - 1) * 60 + width - 1

    def tile(cell, glyph, word=0):
        assert 0 <= cell < 1980
        raw[18 + cell] = glyph
        struct.pack_into('<H', raw, 18 + 1980 + 2 * cell, word)

    cells = []
    for y in range(height):
        for x in range(width):
            if width == 7 and height == 3 and y == 1 and x in (2, 4):
                continue
            cell = first + y * 60 + x
            cells.append(cell)
            tile(cell, 0x60, 0x8001)
    columns = {'centered': sorted({(width - 1) // 2, width // 2}),
               'left-edge': [0], 'right-edge': [width - 1], 'none': []}[layout]
    supports = [first + height * 60 + column for column in columns]
    for cell in supports:
        tile(cell, 1)
    wall = None
    if height == 3 and vx == 0 and layout in ('left-edge', 'right-edge'):
        wall = last + 1 if layout == 'left-edge' else first - 1
        tile(wall, 1)
    above = []
    if vx:
        above = [first - 60 + width // 2]
        tile(above[0], 0x41 if width % 2 else 0x47, 0x31 if width % 2 else 0x4001)
    flags = (0, 1, 2, 0x83)[(index // 3 + index % 3) % 4]
    rest = (94 if index % 2 == 0 else 255) if vx == 0 else 0
    struct.pack_into('<HHHbbbbHBBB', raw, COLLAPSE,
                     first * 2, last * 2, 0x8001, vx, 0,
                     -120 if vx < 0 else 120 if vx > 0 else 0, 0,
                     abs(vx), flags, rest, len(cells) * 2)
    struct.pack_into('<HH', raw, 10, bound - 199, 1)
    assert len(raw) == INPUT
    return bytes(raw), dict(width=width, height=height, layout=layout, vx=vx,
        bound=bound, cells=cells, initial_supports=supports, balance_wall=wall,
        above_targets=above, flags=flags, rest=rest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path, required=True)
    parser.add_argument('--base-fixture', type=Path, required=True)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    assert not out.exists() and not sys.flags.optimize and os.environ['SDL_AUDIODRIVER'] == 'dummy'
    out.mkdir()
    source = (root / 'tools/capture_original_contact_staging.py').read_bytes()
    assert sha(source) == STAGING_SHA
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.FunctionDef) and node.name in ('module', 'restore')]
    assert len(nodes) == 2
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<pinned original restoration>', 'exec'), globals())
    sys.path.insert(0, str(args.unicorn_path.resolve()))
    helper = module(root / 'tools/original_bomb_cpu.py', CPU_SHA, 'collapse_support_cpu')
    reader = module(root / 'tools/capture_original_fracture_retirement.py', READER_SHA, 'collapse_support_reader')
    import unicorn
    from unicorn import x86_const as regs
    observed, neutral = helper['BombCPU'](root), helper['BombCPU'](root)
    packed_base = args.base_fixture.read_bytes()
    assert sha(packed_base) == BASE_SHA
    base_fixture = gzip.decompress(packed_base)
    assert sha(base_fixture) == '1955f2e3eec9bcc5fe2e943105fcc9cdaca103ba115e3bb4c8f09719b0444ea3'
    bases = [base_fixture[16 + slot * 53448:16 + slot * 53448 + INPUT] for slot in (0, 1)]
    tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
        ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
    anchors = {0x14d3c: 'support_scan', 0x14dd3: 'balance_scan', 0x14e48: 'contact_scan',
        0x1552c: 'increment_rest', 0x15602: 'normal_writeback', 0x1566c: 'timer_remove',
        0x1508b: 'remove', 0x1557b: 'fracture', 0x1370e: 'seed'}
    enabled, visits, phases = False, Counter(), []

    def code(cpu, address, size, _):
        if enabled and address in anchors:
            visits[anchors[address]] += 1

    def memory(cpu, access, address, size, value, _):
        if enabled and address <= observed.DATA + 0x661e < address + size:
            phases.append(dict(ip=cpu.reg_read(regs.UC_X86_REG_IP),
                value=(value >> (8 * (observed.DATA + 0x661e - address))) & 255))

    observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)
    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory)
    cases = list(matrix())
    assert len(cases) == 96
    fixture = bytearray(b'LZCH0001' + struct.pack('<II', 96, 53454))
    expected = bytearray(b'LZCO0001' + struct.pack('<II', 96, 26724))
    chain, groups, final_phases, totals = hashlib.sha256(), Counter(), Counter(), Counter()
    observations = []
    report = dict(schema='lezac.collapse-support-history.v1', passed=False, cases=96)
    try:
        for index, case in enumerate(cases):
            incoming, description = request(bases[index % 2], case, index)
            history = bytes(((0, 156, 100)[index % 3], 0x5a, 0xa5))
            report['current_case'] = dict(index=index, **description)
            poison_outputs, poison_evidence = [], []
            for poison in (0, 1, 0xa5):
                snapshots, registers, outputs = [], [], []
                visits.clear(); phases.clear()
                for executor in (observed, neutral):
                    # The pinned restorer accepts count 2. Change only its input count,
                    # then restore the requested live count before any code executes.
                    adapter = bytearray(incoming)
                    struct.pack_into('<H', adapter, 12, 2)
                    restore(executor, bytes(adapter))
                    cpu, data = executor.cpu, executor.DATA
                    cpu.mem_write(data + 0x2080, incoming[12:14])
                    assert bytes(cpu.mem_read(data + 0x2080, 2)) == b'\1\0'
                    cpu.mem_write(data + 0x661e, history[:1])
                    cpu.mem_write(data + 0xa06, history[1:])
                    cpu.mem_write(0x8fed2, bytes((poison,)))
                    enabled = executor is observed
                    cpu.emu_start(0x15102, 0x1ff00, count=4000000)
                    enabled = False
                    executor.assert_return(0xff00, 0xf000, 0xff02)
                    snapshot = bytes(cpu.mem_read(0, 1024**2))
                    assert snapshot[0x10000:0x1aa20] == executor.initial_memory[0x10000:0x1aa20]
                    bound, live = struct.unpack('<HH', bytes(cpu.mem_read(data + 0x207e, 4)))
                    assert 199 <= bound <= 1600 and live <= 250
                    output = bytes(cpu.mem_read(data + 0x1afe, 4)) + struct.pack('<HH', bound - 199, live)
                    output += bytes(cpu.mem_read(data + 0x78c8, 2)) + bytes(cpu.mem_read(data + 0x78c4, 2))
                    output += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
                    output += bytes(cpu.mem_read(data + 0x292b, 1402 * 11))
                    output += bytes(cpu.mem_read(data + 0x6620, 251 * 15))
                    output += reader['bank'](executor) + reader['sound'](executor)
                    output += bytes(cpu.mem_read(data + 0x661e, 1)) + bytes(cpu.mem_read(data + 0xa06, 2))
                    assert len(output) == 26724
                    snapshots.append(snapshot); outputs.append(output)
                    registers.append([cpu.reg_read(register) for register in tracked])
                assert snapshots[0] == snapshots[1] and outputs[0] == outputs[1] and registers[0] == registers[1]
                chain.update(hashlib.sha256(snapshots[0]).digest())
                poison_outputs.append(outputs[0])
                poison_evidence.append(dict(poison=poison, visits=dict(visits), phase_writes=list(phases),
                    output_sha256=sha(outputs[0])))
            if not poison_outputs[0] == poison_outputs[1] == poison_outputs[2]:
                for poison, output in zip((0, 1, 0xa5), poison_outputs):
                    (out / ('failure-case-' + str(index) + '-poison-' + str(poison) + '.bin')).write_bytes(output)
                raise AssertionError((index, case, 'stack poison changed observable output'))
            result = poison_outputs[0]
            fixture.extend(incoming + history + result); expected.extend(result)
            groups[case[2]] += 1
            final_phases[str(result[-3])] += 1
            totals.update(poison_evidence[0]['visits'])
            observations.append(dict(index=index, **description, input_sha256=sha(incoming + history),
                initial_history=history.hex(), final_history=result[-3:].hex(),
                final_collapse_live=struct.unpack_from('<H', result, 6)[0],
                final_record=result[21374:21389].hex(), poison_variants=poison_evidence))
        assert set(final_phases) == {'0', '1'} and totals['balance_scan'] > 0 and totals['timer_remove'] > 0
        assert totals['fracture'] == 0
        packed = gzip.compress(fixture, mtime=0)
        report = dict(schema='lezac.collapse-support-history.v1', passed=True, cases=96, groups=dict(groups),
            widths=[2, 3, 6, 7], heights=[1, 3], horizontal_velocities=[-15, 0, 15],
            initial_live_collapse_records=1, final_phases=dict(final_phases), original_visits=dict(totals),
            producer_sha256=sha(Path(__file__).read_bytes()), executor_sha256=CPU_SHA, staging_sha256=STAGING_SHA,
            capture_helper_sha256=sha((root / 'tools/capture_original_collapse_lane_history.py').read_bytes()),
            reader_sha256=READER_SHA, base_fixture_sha256=BASE_SHA, original_exe_sha256=sha(observed.raw),
            input_bytes=26730, state_bytes=26724, fixture_sha256=sha(packed), fixture_raw_sha256=sha(fixture),
            expected_sha256=sha(expected), full_ram_hash_chain=chain.hexdigest(),
            observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
            poison_variants_per_case=3, stack_poison_address=0x8fed2, observable_stack_poison_independence=True,
            restoration_adapter='pinned count-2 data restorer, DS:2080 restored to requested count 1 before execution',
            original_calls_stubbed=False, original_instructions_patched=False, hardware_io_permitted=False,
            full_collapse_update=True, actual_app_executed=False, seeded=True, natural_route=False,
            first_seed_stack_history_generally_proven=False, original_fidelity_claim=False, whole_game_complete=False)
        (out / 'collapse_support_history_original.bin.gz').write_bytes(packed)
    except BaseException as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        (out / 'collapse_support_history_original.json').write_text(json.dumps(report, indent=2) + '\n')
        (out / 'observations.json').write_text(json.dumps(observations, indent=2) + '\n')
        assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < 8 * 1024**2
    print(json.dumps(dict(**report, packed_bytes=len(packed))), flush=True)


if __name__ == '__main__':
    main()
