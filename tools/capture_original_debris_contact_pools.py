"""Observe direct fragment impacts across complete low/full physical pools."""
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import traceback

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--out-directory', type=Path, required=True)
parser.add_argument('--unicorn-path', type=Path, required=True)
args = parser.parse_args()
ROOT, OUT = args.root.resolve(), args.out_directory.resolve()
INPUT, STATE, STRIDE = 26727, 26721, 53448
DEBRIS, COLLAPSE, BANK = 5958, 21380, 25145
HELPER_SHA = 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c'
READER_SHA = '50cd6bc4d44a9d805b2598d89b7c626a34c0eb5339b8350b8f8125ffa6c74c73'
RESTORE_SHA = 'f703d8bd4cd3e646c8b78ae98a78b85d15fb42d58a11f271ad06d9696c01c9d1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def request(base, direction, target_type, capacity_index, actor_index):
    raw = bytearray(base)
    raw[18:DEBRIS] = bytes(DEBRIS - 18)
    count = (2, 1400, 1401)[capacity_index]
    own = 29 * 60 + 20
    delta = {'right': 1, 'left': -1, 'down': 60, 'up': -60}[direction]
    target = own + delta
    dx, dy = {'right': (96, -49), 'left': (-96, -49), 'down': (0, 96), 'up': (0, -96)}[direction]

    def tile(cell, byte, word=0):
        raw[18 + cell] = byte
        struct.pack_into('<H', raw, 18 + 1980 + cell * 2, word)

    for y in range(33):
        tile(y * 60, 1); tile(y * 60 + 59, 1)
    for x in range(60):
        tile(x, 1); tile(32 * 60 + x, 1); tile(26 * 60 + x, 1)
    positions = [y * 60 + x for y in range(1, 26) for x in range(1, 59)]
    for slot in range(count - 1):
        cell = target if slot == 0 and target_type == 'fragment' else positions[slot]
        word = 0xc001 + slot
        tile(cell, 0x60, word)
        raw[DEBRIS + 11 * slot:DEBRIS + 11 * (slot + 1)] = struct.pack(
            '<HHbbbbBBB', cell, word, 20 if slot == 0 else 0,
            -10 if slot == 0 else 0, 0, 0, 0, 0x60, 0x9a)
    tile(own, 0x60, 0xc000 + count)
    tile(own + 60, 1)
    word = {'fragment': 0xc001, 'collapse': 0x8001, 'new-fragment': 0x7001, 'hard': 0}[target_type]
    tile(target, 1 if target_type == 'hard' else 0x47 if target_type == 'new-fragment' else 0x60, word)
    raw[DEBRIS + 11 * (count - 1):DEBRIS + 11 * count] = struct.pack(
        '<HHbbbbBBB', own, 0xc000 + count, dx, dy,
        100 if dx > 0 else -100 if dx < 0 else 0,
        100 if direction == 'down' else -100 if direction == 'up' else 0,
        (0, 98, 99)[capacity_index], 0x60, 0x8d)
    struct.pack_into('<HHHbbbbHBBB', raw, COLLAPSE,
                     target * 2, target * 2, 0x8001, 80, -64, 0, 0, 144,
                     0x83, 0, (0, 2, 254)[capacity_index])
    struct.pack_into('<HHHbbbbHBBB', raw, COLLAPSE + 15,
                     244, 246, 0x8002, 0, 0, 0, 0, 0, 0x83, 0, 4)
    struct.pack_into('<HH', raw, 10, count, 2)
    return bytes(raw), word


assert not OUT.exists() and os.environ['SDL_AUDIODRIVER'] == 'dummy' and not sys.flags.optimize
OUT.mkdir()
source_path = ROOT / 'tools/capture_original_contact_staging.py'
source = source_path.read_bytes()
assert sha(source) == RESTORE_SHA
tree = ast.parse(source, filename=str(source_path))
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ('module', 'restore')]
assert {node.name for node in functions} == {'module', 'restore'}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(source_path), 'exec'), globals())
sys.path.insert(0, str(args.unicorn_path.resolve()))
helper = module(ROOT / 'tools/original_bomb_cpu.py', HELPER_SHA, 'debris_contact_cpu')
reader = module(ROOT / 'tools/capture_original_fracture_retirement.py', READER_SHA, 'debris_contact_reader')
import unicorn
from unicorn import x86_const as regs
assert unicorn.__version__ == '2.1.4'
observed, neutral = helper['BombCPU'](ROOT), helper['BombCPU'](ROOT)
tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
           ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
packed_base = (ROOT / 'tests/fixtures/collapse_contact_pools_original.bin.gz').read_bytes()
assert sha(packed_base) == '9075ffca72bcdaa17392fee1f2626ae40368c6f3c59a20f0f35fee47eb6ad507'
base = gzip.decompress(packed_base)
assert sha(base) == '1955f2e3eec9bcc5fe2e943105fcc9cdaca103ba115e3bb4c8f09719b0444ea3'
bases = [base[16 + index * STRIDE:16 + index * STRIDE + INPUT] for index in (0, 1)]
enabled = False
visits, totals, writes, guard_writes = Counter(), Counter(), Counter(), []
anchors = {0x145fa: 'updater', 0x1458d: 'remove', 0x1370e: 'seed',
           0x13bb2: 'forward_blend', 0x13d46: 'reverse_blend',
           0x14c8c: 'forward_stage', 0x14c9f: 'reverse_stage',
           0x13d2d: 'forward_debris_write', 0x13ec1: 'reverse_debris_write',
           0x12f9f: 'actor_constructor', 0x1a5a8: 'random', 0x1165a: 'sound_latch'}


def code(cpu, address, size, _):
    if enabled and address in anchors:
        visits[anchors[address]] += 1


def memory(cpu, access, address, size, value, _):
    if enabled and address < observed.DATA + 0x6569 and address + size > observed.DATA + 0x655e:
        guard_writes.append(dict(ip=cpu.reg_read(regs.UC_X86_REG_IP),
                                 offset=address - observed.DATA, bytes=size, value=value))
        for byte in range(size):
            offset = address + byte - observed.DATA - 0x655e
            if 0 <= offset < 11:
                writes[offset] += 1


observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)
observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory)
cases = [(direction, target, capacity, actor) for direction in ('right', 'left', 'down', 'up')
         for target in ('fragment', 'collapse', 'new-fragment', 'hard')
         for capacity in range(3) for actor in range(2)]
assert len(cases) == 96
requests, results, chain = [], [], hashlib.sha256()
report = dict(schema='lezac.original-debris-contact-pools.v1', passed=False,
    recorded_utc=datetime.now(timezone.utc).isoformat(), producer_sha256=sha(Path(__file__).read_bytes()),
    executor_sha256=HELPER_SHA, bank_reader_sha256=READER_SHA, restoration_source_sha256=RESTORE_SHA,
    original_exe_sha256=sha(observed.raw), original_instructions_patched=False, original_calls_stubbed=False,
    hardware_io_permitted=False, observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
    physical_debris_records=1402, physical_collapse_records=251, complete_actor_bank_bytes=1575,
    complete_sound_bytes=7, fragments_advanced=True, collapse_records_not_advanced=True,
    actual_app_comparison=False, seeded=True, natural_route=False, whole_game_claim=False, cases=[])
try:
    for index, (direction, target, capacity, actor) in enumerate(cases):
        incoming, target_word = request(bases[actor], direction, target, capacity, actor)
        report['current_case'] = dict(index=index, direction=direction, target=target, capacity=capacity, actor=actor)
        outputs, snapshots = [], []
        visits.clear(); guard_writes.clear()
        for executor in (observed, neutral):
            restore(executor, incoming)
            enabled = executor is observed
            executor.cpu.emu_start(0x145fa, 0x1ff00, count=4000000)
            enabled = False
            executor.assert_return(0xff00, 0xf000, 0xff02)
            cpu, data = executor.cpu, executor.DATA
            snapshots.append(bytes(cpu.mem_read(0, 1024**2)))
            bound, live = struct.unpack('<HH', bytes(cpu.mem_read(data + 0x207e, 4)))
            assert 199 <= bound <= 1600 and live <= 250
            output = bytes(cpu.mem_read(data + 0x1afe, 4)) + struct.pack('<HH', bound - 199, live)
            output += bytes(cpu.mem_read(data + 0x78c8, 2)) + bytes(cpu.mem_read(data + 0x78c4, 2))
            output += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
            output += bytes(cpu.mem_read(data + 0x292b, 1402 * 11)) + bytes(cpu.mem_read(data + 0x6620, 251 * 15))
            output += reader['bank'](executor) + reader['sound'](executor)
            outputs.append(output)
        assert outputs[0] == outputs[1] and snapshots[0] == snapshots[1]
        assert [observed.cpu.reg_read(r) for r in tracked] == [neutral.cpu.reg_read(r) for r in tracked]
        assert len(incoming) == INPUT and len(outputs[0]) == STATE and visits['updater'] == 1
        assert all(write['ip'] in (0x4c8c, 0x4c9f) for write in guard_writes)
        assert incoming[21371:21380] == outputs[0][21365:21374]
        if target == 'hard':
            assert not guard_writes
        else:
            assert [write['ip'] for write in guard_writes] == [0x4c8c, 0x4c9f]
            assert [write['value'] for write in guard_writes] == [target_word, target_word | 0x8000]
        chain.update(hashlib.sha256(snapshots[0]).digest())
        requests.append(incoming); results.append(outputs[0]); totals.update(visits)
        report['cases'].append(dict(index=index, direction=direction, target=target,
            initial_debris_count=(2, 1400, 1401)[capacity], actor_count=incoming[BANK + 1570],
            target_word=target_word, guard_input=incoming[21369:21380].hex(),
            guard_output=outputs[0][21363:21374].hex(), guard_writes=list(guard_writes), visits=dict(visits),
            input_sha256=sha(incoming), output_sha256=sha(outputs[0])))
    fixture = b'LZFC0001' + struct.pack('<II', 96, STRIDE)
    fixture += b''.join(incoming + result for incoming, result in zip(requests, results))
    packed = gzip.compress(fixture, mtime=0)
    expected = b'LZFP0001' + struct.pack('<II', 96, STATE) + b''.join(results)
    (OUT / 'debris_contact_pools_original.bin.gz').write_bytes(packed)
    (OUT / 'expected.bin').write_bytes(expected)
    report.update(passed=True, total_cases=96, state_bytes=96 * STATE,
        original_visits=dict(totals), guard_write_offsets=dict(writes), fixture_bytes=len(fixture),
        fixture_sha256=sha(fixture), fixture_gzip_bytes=len(packed), fixture_gzip_sha256=sha(packed),
        expected_sha256=sha(expected), full_memory_repeat_hash_chain=chain.hexdigest())
except BaseException:
    report['error'] = traceback.format_exc()
    (OUT / 'failure-input.bin').write_bytes(incoming)
    for position, raw in enumerate(outputs):
        (OUT / ('failure-output-' + str(position) + '.bin')).write_bytes(raw)
    for position, raw in enumerate(snapshots):
        (OUT / ('failure-ram-' + str(position) + '.bin.gz')).write_bytes(gzip.compress(raw, mtime=0))
    raise
finally:
    (OUT / 'capture.json').write_text(json.dumps(report, indent=2) + '\n')
    assert sum(path.stat().st_size for path in OUT.rglob('*') if path.is_file()) < 8 * 1024**2
    print(json.dumps({key: value for key, value in report.items() if key != 'cases'}), flush=True)
