"""Capture complete DS images from unmodified original damage-lane helpers."""
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

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--unicorn-path', type=Path, required=True)
args = parser.parse_args()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


assert not args.out.exists() and os.environ['SDL_AUDIODRIVER'] == 'dummy' and not sys.flags.optimize
sys.path.insert(0, str(args.unicorn_path))
source = (args.root / 'tools/capture_original_contact_staging.py').read_bytes()
assert hashlib.sha256(source).hexdigest() == 'f703d8bd4cd3e646c8b78ae98a78b85d15fb42d58a11f271ad06d9696c01c9d1'
tree = ast.parse(source)
node, = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'module']
exec(compile(ast.Module(body=[node], type_ignores=[]), '<pinned module loader>', 'exec'), globals())
helper = module(args.root / 'tools/original_bomb_cpu.py',
    'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c', 'damage_lane_bytes_cpu')
import unicorn
from unicorn import x86_const as regs
observed, neutral = helper['BombCPU'](args.root), helper['BombCPU'](args.root)
registers = [getattr(regs, 'UC_X86_REG_' + name) for name in
             ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
events, enabled = [], False
visits = Counter()


def memory(cpu, access, address, count, value, _):
    if enabled and observed.DATA <= address < observed.DATA + 65536:
        events.append(dict(ip=cpu.reg_read(regs.UC_X86_REG_IP), offset=address - observed.DATA,
                           bytes=count, value=value))


def code(cpu, address, size, _):
    if enabled and address in (0x13a7e, 0x13b18, 0x13bb2, 0x13d46, 0x1370e):
        visits[hex(address)] += 1


observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory)
observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)


def word(data, offset, value):
    struct.pack_into('<H', data, offset, value & 65535)


def fragment(data, index, flagged, vx=-49, vy=20):
    offset = 0x292b + 11 * index
    word(data, offset + 2, flagged)
    data[offset + 4:offset + 6] = bytes((vx & 255, vy & 255))


def collapse(data, index, flagged, vx=-100, vy=1, weight=2):
    offset = 0x6620 + 15 * index
    word(data, offset + 4, flagged)
    data[offset + 6:offset + 8] = bytes((vx & 255, vy & 255))
    data[offset + 14] = weight


def initial(salt, phase):
    data = bytearray((index * 37 + (index >> 8) * 13 + salt) & 255 for index in range(65536))
    word(data, 0x207e, 202)
    word(data, 0x2080, 3)
    for index in range(3):
        fragment(data, index, 0xc001 + index, (-49, 100, 1)[index], (20, -100, -1)[index])
        collapse(data, index, 0x8001 + index, (-100, 127, 9)[index], (1, -128, 8)[index], (2, 255, 0)[index])
    data[0x661e] = phase & 255
    return data


cases = []
for profile in range(16):
    for reverse in (False, True):
        for phase in (-100, -1, 1, 100):
            data = initial(profile, phase)
            cursor = (0x1234, 0x7fff, 0x8007, 0x8001, 0x8001, 0x8003, 0x8001, 0x80fa,
                      0xc001, 0xc001, 0xc003, 0xc001, 0xf001, 0xf001, 0xc001, 0xc001)[profile]
            if profile == 3:
                word(data, 0x2080, 0)
            if profile == 6:
                collapse(data, 2, 0x8001, 91, -92, 7)
            if profile == 7:
                word(data, 0x2080, 250)
                for index in range(250):
                    collapse(data, index, 0x8001 + index)
            if profile == 8:
                word(data, 0x207e, 199)
            if profile == 11:
                fragment(data, 2, 0xc001, 93, -94)
            if profile >= 13:
                word(data, 0x207e, 1600)
                for index in range(1401):
                    fragment(data, index, 0xc100 + index)
                if profile >= 14:
                    fragment(data, 0, 0xc001)
                if profile == 15:
                    fragment(data, 1400, 0xc001, 95, -96)
            word(data, 0x2074, cursor)
            cases.append((int(reverse), 1, 0xf100, data, dict(profile=profile, initial_phase=phase, kind='lookup')))
contacts = [[], [0xc001], [0xf001], [0x8001], [0x8002], [0x8003], [0x8007],
            [0xc001, 0xf001], [0x8001, 0xc003, 0xf001], [0xc001, 0xc001],
            [0x8001, 0x8002, 0xc001], [0xc001, 0x8001, 0xf001] * 10]
for profile, words in enumerate(contacts):
    for reverse in (False, True):
        for phase in (-1, 100):
            data = initial(profile + 32, phase)
            word(data, 0x2074, 0xab12)
            word(data, 0x2078, len(words))
            for index, flagged in enumerate(words, 1):
                word(data, 0x655c + 2 * index, flagged)
            data[0xf100] = (-49 if phase == -1 else 127) & 255
            cases.append((2 + int(reverse), 255 if profile == 10 else 1, 0xf100, data,
                          dict(profile=profile, initial_phase=phase, kind='impact')))
assert len(cases) == 176
raw = bytearray(struct.pack('<8sII', b'LZLB0001', len(cases), 131076))
chain = hashlib.sha256()
report = dict(passed=False, original_instructions_patched=False, original_calls_stubbed=False,
              full_ram_observer_neutrality_bytes=1024**2, observer_registers=14, cases=[])
for index, (operation, weight, caller, data, label) in enumerate(cases):
    snapshots, register_states = [], []
    events.clear()
    for executor in (observed, neutral):
        cpu = executor.cpu
        cpu.context_restore(executor.initial_context)
        cpu.mem_write(0, executor.initial_memory)
        cpu.mem_write(executor.DATA, bytes(data))
        executor.registers(0xf000, 0xff00)
        stack = struct.pack('<H', 0xff00) if operation < 2 else struct.pack('<4H', 0xff00, caller, 0x1aa2, weight)
        cpu.mem_write(0x8ff00, stack)
        enabled = executor is observed
        cpu.emu_start((0x13a7e, 0x13b18, 0x13bb2, 0x13d46)[operation], 0x1ff00, count=4000000)
        enabled = False
        executor.assert_return(0xff00, 0xf000, 0xff02 if operation < 2 else 0xff08)
        assert bytes(cpu.mem_read(0x10000, 0xaa20)) == executor.initial_memory[0x10000:0x1aa20]
        snapshots.append(bytes(cpu.mem_read(0, 1024**2)))
        register_states.append([cpu.reg_read(register) for register in registers])
    assert snapshots[0] == snapshots[1] and register_states[0] == register_states[1]
    expected = snapshots[0][observed.DATA:observed.DATA + 65536]
    raw.extend(struct.pack('<BBH', operation, weight, caller))
    raw.extend(data)
    raw.extend(expected)
    if operation >= 2 and label['profile'] == 2:
        address = 0x0a06 + (operation & 1)
        assert any(event['offset'] == address and event['ip'] == (0x3d1b if operation == 2 else 0x3eaf)
                   for event in events), events
        assert expected[0x661e] == data[0x661e]
        assert expected[address] == expected[caller]
    chain.update(hashlib.sha256(snapshots[0]).digest())
    report['cases'].append(dict(index=index, operation=operation, **label,
        final_cursor=struct.unpack_from('<H', expected, 0x2074)[0], final_phase=expected[0x661e],
        low_data_writes=[event for event in events if event['offset'] < 0x1afa]))
assert not visits['0x1370e']
packed = gzip.compress(bytes(raw), mtime=0)
assert len(packed) < 1024**2
args.out.mkdir()
(args.out / 'damage_lane_bytes_original.bin.gz').write_bytes(packed)
report.update(passed=True, cases_executed=len(cases), ds_bytes_per_case=65536,
    compared_ds_bytes=len(cases) * 65536, fixture_bytes=len(raw), fixture_gzip_bytes=len(packed),
    fixture_sha256=hashlib.sha256(raw).hexdigest(), fixture_gzip_sha256=hashlib.sha256(packed).hexdigest(),
    full_ram_hash_chain=chain.hexdigest(), original_visits=dict(visits), seeded_cases=False,
    natural_route=False, production_app_integrated=False, whole_game_claim=False)
(args.out / 'capture.json').write_text(json.dumps(report, indent=2) + '\n')
assert sum(path.stat().st_size for path in args.out.rglob('*') if path.is_file()) < 8 * 1024**2
print(json.dumps({key: value for key, value in report.items() if key != 'cases'}), flush=True)
