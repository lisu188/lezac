"""Observe complete original collapse updates with fresh targets and stack poison."""
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

INPUT, STATE = 26727, 26721
DEBRIS, COLLAPSE, BANK = 5958, 21380, 25145
CPU_SHA = 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c'
STAGING_SHA = 'f703d8bd4cd3e646c8b78ae98a78b85d15fb42d58a11f271ad06d9696c01c9d1'
READER_SHA = '50cd6bc4d44a9d805b2598d89b7c626a34c0eb5339b8350b8f8125ffa6c74c73'
BASE_SHA = '9075ffca72bcdaa17392fee1f2626ae40368c6f3c59a20f0f35fee47eb6ad507'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def matrix():
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for profile in ('debris', 'collapse', 'alternating', 'collapse-group'):
            for bound in (199, 1599, 1600):
                yield dx, dy, 6, profile, bound
    for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        for count in (1, 6):
            for profile in ('debris', 'alternating'):
                for bound in (199, 1599, 1600):
                    yield dx, dy, count, profile, bound


def request(base, case, index):
    dx, dy, count, profile, bound = case
    raw = bytearray(base)
    raw[18:DEBRIS] = bytes(DEBRIS - 18)
    raw[DEBRIS:COLLAPSE] = b'\x55' * (COLLAPSE - DEBRIS)
    for slot in range(bound - 199):
        raw[DEBRIS + slot * 11:DEBRIS + (slot + 1) * 11] = struct.pack(
            '<HHbbbbBBB', 3, 0xc0c8 + slot, -49, 49, 0, 0, 0, 0x55, 0xa5)
    width, height = ((count, count) if dx and dy else (2, count) if dx else (count, 2))
    first = 20 * 60 + 20
    last = first + (height - 1) * 60 + width - 1

    def tile(cell, glyph, word=0):
        raw[18 + cell] = glyph
        struct.pack_into('<H', raw, 18 + 1980 + 2 * cell, word)

    for cell in (122, 123):
        tile(cell, 0x60, 0x8001)
        tile(cell + 60, 1)
    for y in range(height):
        for x in range(width):
            tile(first + y * 60 + x, 0x60, 0x8002)
    for x in range(width):
        tile(first + height * 60 + x, 1)
    horizontal = [first + y * 60 + (width if dx > 0 else -1) for y in range(height)] if dx else []
    vertical = [first + (height * 60 if dy > 0 else -60) + x for x in range(width)] if dy else []
    targets = horizontal + vertical
    assert len(set(targets)) == len(targets)
    for target_index, cell in enumerate(targets):
        is_debris = profile == 'debris' or (profile == 'alternating' and target_index % 2 == 0)
        word = 0x4001 + target_index if is_debris else 0x11 + target_index
        if profile == 'collapse-group':
            word = 0x11
        tile(cell, 0x47 if is_debris else 0x41, word)
    struct.pack_into('<HHHbbbbHBBB', raw, COLLAPSE,
                     244, 246, 0x8001, 0, 0, 0, 0, 0, 0x83, 0, 2)
    struct.pack_into('<HHHbbbbHBBB', raw, COLLAPSE + 15,
                     first * 2, last * 2, 0x8002, dx * 96, dy * 96,
                     dx * 100, dy * 100, 96 * (abs(dx) + abs(dy)),
                     0x83, (0, 94, 255)[index % 3], width * height * 2)
    struct.pack_into('<HH', raw, 10, bound - 199, 2)
    assert len(raw) == INPUT
    return bytes(raw), targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path, required=True)
    parser.add_argument('--base-fixture', type=Path)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    assert not out.exists() and not sys.flags.optimize and os.environ['SDL_AUDIODRIVER'] == 'dummy'
    source = (root / 'tools/capture_original_contact_staging.py').read_bytes()
    assert sha(source) == STAGING_SHA
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.FunctionDef) and node.name in ('module', 'restore')]
    assert len(nodes) == 2
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<pinned original restoration>', 'exec'), globals())
    sys.path.insert(0, str(args.unicorn_path.resolve()))
    helper = module(root / 'tools/original_bomb_cpu.py', CPU_SHA, 'collapse_lane_history_cpu')
    reader = module(root / 'tools/capture_original_fracture_retirement.py', READER_SHA, 'collapse_lane_history_reader')
    import unicorn
    from unicorn import x86_const as regs
    observed, neutral = helper['BombCPU'](root), helper['BombCPU'](root)
    packed_base = (args.base_fixture or root / 'tests/fixtures/collapse_contact_pools_original.bin.gz').read_bytes()
    assert sha(packed_base) == BASE_SHA
    base_fixture = gzip.decompress(packed_base)
    assert sha(base_fixture) == '1955f2e3eec9bcc5fe2e943105fcc9cdaca103ba115e3bb4c8f09719b0444ea3'
    bases = [base_fixture[16 + slot * 53448:16 + slot * 53448 + INPUT] for slot in (0, 1)]
    tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
        ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
    enabled, stack_writes, calls, seeds, phases, visits = False, {}, [], [], [], Counter()

    def memory(cpu, access, address, count, value, _):
        if not enabled:
            return
        if 0x8fd00 <= address < 0x90000:
            for byte in range(count):
                stack_writes[address + byte] = dict(ip=cpu.reg_read(regs.UC_X86_REG_IP),
                    address=address, bytes=count, value=value, byte=(value >> (8 * byte)) & 255)
        if address <= observed.DATA + 0x661e < address + count:
            phases.append(dict(ip=cpu.reg_read(regs.UC_X86_REG_IP),
                               value=(value >> (8 * (observed.DATA + 0x661e - address))) & 255))

    def code(cpu, address, count, _):
        if not enabled:
            return
        if address in (0x15102, 0x13bb2, 0x13d46, 0x1370e, 0x1557b, 0x15602):
            visits[hex(address)] += 1
        if address in (0x13bb2, 0x13d46):
            sp = cpu.reg_read(regs.UC_X86_REG_SP)
            candidate = 0x80000 + ((sp - 14) & 65535)
            contacts = struct.unpack('<H', bytes(cpu.mem_read(observed.DATA + 0x2078, 2)))[0]
            assert contacts <= 30
            calls.append(dict(ip=cpu.reg_read(regs.UC_X86_REG_IP), stack_seed_class_address=candidate,
                incoming_class=cpu.mem_read(candidate, 1)[0], last_writer=stack_writes.get(candidate),
                incoming_phase=cpu.mem_read(observed.DATA + 0x661e, 1)[0],
                staged_words=bytes(cpu.mem_read(observed.DATA + 0x655e, contacts * 2)).hex()))
        if address == 0x1370e:
            sp = cpu.reg_read(regs.UC_X86_REG_SP)
            arguments = bytes(cpu.mem_read(0x80000 + sp + 2, 10))
            offset, segment, vy, vx, cell = struct.unpack('<5H', arguments)
            target = segment * 16 + offset
            seeds.append(dict(cell=cell, map_word=struct.unpack('<H', bytes(cpu.mem_read(0x50000 + cell * 2, 2)))[0],
                incoming_class=cpu.mem_read(target, 1)[0], class_address=target,
                result=cpu.mem_read(observed.DATA + 0x79c8, 1)[0]))

    observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory)
    observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)
    cases = list(matrix())
    assert len(cases) == 96
    fixture = bytearray(b'LZCH0001' + struct.pack('<II', len(cases), 53454))
    expected = bytearray(b'LZCO0001' + struct.pack('<II', len(cases), 26724))
    chain, groups, observations = hashlib.sha256(), Counter(), []
    for index, case in enumerate(cases):
        incoming, targets = request(bases[index % 2], case, index)
        history = bytes(((0, 156, 100)[index % 3], 0x5a, 0xa5))
        poison_outputs, poison_evidence = [], []
        for poison in (0, 1, 0xa5):
            snapshots, registers, outputs = [], [], []
            stack_writes.clear(); calls.clear(); seeds.clear(); phases.clear(); visits.clear()
            for executor in (observed, neutral):
                restore(executor, incoming)
                cpu, data = executor.cpu, executor.DATA
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
            poison_evidence.append(dict(poison=poison, calls=list(calls), seeds=list(seeds),
                phase_writes=list(phases), visits=dict(visits), output_sha256=sha(outputs[0])))
        assert poison_outputs[0] == poison_outputs[1] == poison_outputs[2], (index, case, 'stack poison changed observable output')
        result = poison_outputs[0]
        fixture.extend(incoming + history + result); expected.extend(result)
        groups[case[3]] += 1
        observations.append(dict(index=index, dx=case[0], dy=case[1], count=case[2], profile=case[3],
            bound=case[4], targets=targets, input_sha256=sha(incoming + history),
            initial_history=history.hex(), final_history=result[-3:].hex(), poison_variants=poison_evidence))
    packed = gzip.compress(fixture, mtime=0)
    report = dict(schema='lezac.collapse-lane-history.v1', passed=True, cases=len(cases), groups=dict(groups),
        producer_sha256=sha(Path(__file__).read_bytes()), executor_sha256=CPU_SHA, staging_sha256=STAGING_SHA,
        reader_sha256=READER_SHA, base_fixture_sha256=BASE_SHA, original_exe_sha256=sha(observed.raw),
        input_bytes=26730, state_bytes=26724, fixture_sha256=sha(packed), fixture_raw_sha256=sha(fixture),
        expected_sha256=sha(expected), full_ram_hash_chain=chain.hexdigest(),
        observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
        poison_variants_per_case=3, stack_poison_address=0x8fed2, observable_stack_poison_independence=True,
        original_calls_stubbed=False, original_instructions_patched=False, hardware_io_permitted=False,
        full_collapse_update=True, actual_app_executed=False, seeded=True, natural_route=False,
        first_seed_stack_history_generally_proven=False, original_fidelity_claim=False, whole_game_complete=False)
    out.mkdir()
    (out / 'collapse_lane_history_original.bin.gz').write_bytes(packed)
    (out / 'collapse_lane_history_original.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'observations.json').write_text(json.dumps(observations, indent=2) + '\n')
    assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < 8 * 1024**2
    print(json.dumps(dict(**report, packed_bytes=len(packed))), flush=True)


if __name__ == '__main__':
    main()
