"""Observe complete original fragment updates with prior phase and low DS bytes."""
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
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--unicorn-path', type=Path, required=True)
args = parser.parse_args()
ROOT, OUT = args.root.resolve(), args.out.resolve()
INPUT, STATE, STRIDE = 26727, 26721, 53448
DEBRIS, COLLAPSE, BANK = 5958, 21380, 25145


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


assert not OUT.exists() and os.environ['SDL_AUDIODRIVER'] == 'dummy' and not sys.flags.optimize
source = (ROOT / 'tools/capture_original_contact_staging.py').read_bytes()
assert sha(source) == 'f703d8bd4cd3e646c8b78ae98a78b85d15fb42d58a11f271ad06d9696c01c9d1'
nodes = [node for node in ast.parse(source).body
    if isinstance(node, ast.FunctionDef) and node.name in ('module', 'restore')]
assert len(nodes) == 2
exec(compile(ast.Module(body=nodes, type_ignores=[]), '<pinned original restoration>', 'exec'), globals())
sys.path.insert(0, str(args.unicorn_path.resolve()))
helper = module(ROOT / 'tools/original_bomb_cpu.py',
    'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c', 'damage_history_cpu')
reader = module(ROOT / 'tools/capture_original_fracture_retirement.py',
    '50cd6bc4d44a9d805b2598d89b7c626a34c0eb5339b8350b8f8125ffa6c74c73', 'damage_history_reader')
import unicorn
from unicorn import x86_const as regs
assert unicorn.__version__ == '2.1.4'
observed, neutral = helper['BombCPU'](ROOT), helper['BombCPU'](ROOT)
packed = (ROOT / 'tests/fixtures/debris_contact_pools_original.bin.gz').read_bytes()
assert sha(packed) == '395aaa29cac7912735f2bd258638c52fd18eb765d4b2733bda8d593fa63db6e5'
raw = gzip.decompress(packed)
assert sha(raw) == 'cfff186bced8419ebbb8cd5951b91e9503764e6836a44775ab9e9e733732f073'
tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
    ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
enabled, events = False, []
visits = Counter()


def code(cpu, address, count, _):
    if enabled and address in (0x145fa, 0x13a7e, 0x13b18, 0x13bb2, 0x13d46, 0x1370e):
        visits[hex(address)] += 1


def memory(cpu, access, address, count, value, _):
    if enabled and any(address < observed.DATA + offset + 1 and address + count > observed.DATA + offset
                       for offset in (0xa06, 0xa07, 0x2074, 0x2075, 0x661e)):
        events.append(dict(ip=cpu.reg_read(regs.UC_X86_REG_IP), offset=address - observed.DATA,
                           bytes=count, value=value))


observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)
observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory)
cases = [(index, 0) for index in range(96)]
cases += [(index, phase) for index in (16, 40, 64, 88) for phase in (-100, -1, 1, 100)]
fixture = bytearray(struct.pack('<8sII', b'LZDH0001', len(cases), 53454))
expected = bytearray(struct.pack('<8sII', b'LZDO0001', len(cases), 26724))
chain = hashlib.sha256()
report = dict(passed=False, cases=[], original_instructions_patched=False, original_calls_stubbed=False,
    full_ram_observer_neutrality_bytes=1024**2, observer_registers=14, production_app_executed=False,
    natural_route=False, whole_game_claim=False, producer_sha256=sha(Path(__file__).read_bytes()))
for index, phase in cases:
    incoming = raw[16 + index * STRIDE:16 + index * STRIDE + INPUT]
    history = bytes((phase & 255, 0x5a, 0xa5))
    snapshots, outputs, registers = [], [], []
    events.clear(); visits.clear()
    for executor in (observed, neutral):
        restore(executor, incoming)
        cpu, data = executor.cpu, executor.DATA
        cpu.mem_write(data + 0x661e, history[:1])
        cpu.mem_write(data + 0xa06, history[1:])
        enabled = executor is observed
        cpu.emu_start(0x145fa, 0x1ff00, count=4000000)
        enabled = False
        executor.assert_return(0xff00, 0xf000, 0xff02)
        snapshot = bytes(cpu.mem_read(0, 1024**2))
        assert snapshot[0x10000:0x1aa20] == executor.initial_memory[0x10000:0x1aa20]
        snapshots.append(snapshot)
        registers.append([cpu.reg_read(register) for register in tracked])
        bound, live = struct.unpack('<HH', bytes(cpu.mem_read(data + 0x207e, 4)))
        assert 199 <= bound <= 1600 and live <= 250
        output = bytes(cpu.mem_read(data + 0x1afe, 4)) + struct.pack('<HH', bound - 199, live)
        output += bytes(cpu.mem_read(data + 0x78c8, 2)) + bytes(cpu.mem_read(data + 0x78c4, 2))
        output += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
        output += bytes(cpu.mem_read(data + 0x292b, 1402 * 11)) + bytes(cpu.mem_read(data + 0x6620, 251 * 15))
        output += reader['bank'](executor) + reader['sound'](executor)
        if phase == 0:
            assert output == raw[16 + index * STRIDE + INPUT:16 + (index + 1) * STRIDE]
        output += bytes(cpu.mem_read(data + 0x661e, 1)) + bytes(cpu.mem_read(data + 0xa06, 2))
        assert len(output) == 26724
        outputs.append(output)
    assert snapshots[0] == snapshots[1] and outputs[0] == outputs[1] and registers[0] == registers[1]
    chain.update(hashlib.sha256(snapshots[0]).digest())
    fixture.extend(incoming + history + outputs[0]); expected.extend(outputs[0])
    report['cases'].append(dict(fixture_case=index, initial_phase=phase, initial_history=history.hex(),
        final_history=outputs[0][-3:].hex(), output_sha256=sha(outputs[0]), events=list(events), visits=dict(visits)))
packed = gzip.compress(fixture, mtime=0)
report.update(passed=True, cases_executed=len(cases), full_ram_hash_chain=chain.hexdigest(),
    fixture_packed_sha256=sha(packed), fixture_raw_sha256=sha(fixture), expected_sha256=sha(expected),
    packed_bytes=len(packed), input_bytes=26730, state_bytes=26724)
OUT.mkdir()
(OUT / 'damage_lane_history_original.bin.gz').write_bytes(packed)
(OUT / 'capture.json').write_text(json.dumps(report, indent=2) + '\n')
assert sum(path.stat().st_size for path in OUT.rglob('*') if path.is_file()) < 8 * 1024**2
print(json.dumps({key: value for key, value in report.items() if key != 'cases'}), flush=True)
