"""Execute original above-cell contact staging, constructors and gating controls."""
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


def request(base, direction, count, pattern, gated, index):
    raw = bytearray(base)
    raw[18:DEBRIS] = bytes(DEBRIS - 18)
    first, last = 20 * 60 + 20, 21 * 60 + 20 + count - 1
    dx, dy = {'right': (96, 0), 'left': (-96, 0), 'down': (0, 96),
              'stationary': (0, 0)}[direction]

    def tile(cell, byte, word=0):
        raw[18 + cell] = byte
        struct.pack_into('<H', raw, 18 + 1980 + cell * 2, word)

    for cell in (122, 123):
        tile(cell, 0x60, 0x8001)
        tile(cell + 60, 1)
    for y in range(2):
        for x in range(count):
            tile(first + y * 60 + x, 0x60, 0x8002)
    for x in range(count):
        tile(first + 2 * 60 + x, 1)
    words = []
    for slot in range(count):
        word = ((0x4001 + slot) if pattern == 'fragment' else
                (0x9001 + slot) if pattern == 'flagged' else
                0x1001 + (0 if pattern == 'repeated' else slot))
        words.append(word)
        tile(first - 60 + slot, 0x47 if pattern == 'fragment' else 0x60, word)
    struct.pack_into('<HHHbbbbHBBB', raw, COLLAPSE,
                     244, 246, 0x8001, 0, 0, 0, 0, 0, 0x83, 0, 4)
    struct.pack_into('<HHHbbbbHBBB', raw, COLLAPSE + 15,
                     first * 2, last * 2, 0x8002, dx, dy,
                     100 if dx > 0 else -100 if dx < 0 else 0,
                     100 if dy > 0 else 0, abs(dx) + abs(dy),
                     0x83 if gated else 3, (0, 94, 255)[index % 3], 4 * count)
    struct.pack_into('<HH', raw, 10, 0, 2)
    return bytes(raw), words


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
helper = module(ROOT / 'tools/original_bomb_cpu.py', HELPER_SHA, 'above_contact_cpu')
reader = module(ROOT / 'tools/capture_original_fracture_retirement.py', READER_SHA, 'above_contact_reader')
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
visits, totals, writes, guard_writes, calls = Counter(), Counter(), Counter(), [], []
anchors = {0x14e48: 'contact_scan', 0x1552c: 'increment_rest', 0x15602: 'normal_writeback',
           0x1566c: 'timer_remove', 0x1508b: 'remove', 0x1557b: 'fracture',
           0x12f9f: 'actor_constructor', 0x1370e: 'seed'}


def code(cpu, address, size, _):
    if enabled:
        if address in anchors:
            visits[anchors[address]] += 1
        if address == 0x14e48:
            calls.append(dict(delta=struct.unpack('<h', bytes(cpu.mem_read(observed.DATA + 0x2090, 2)))[0],
                              contacts_before=struct.unpack('<H', bytes(cpu.mem_read(observed.DATA + 0x2078, 2)))[0]))


def memory(cpu, access, address, size, value, _):
    if enabled and address < observed.DATA + 0x656a and address + size > observed.DATA + 0x655e:
        guard_writes.append(dict(ip=cpu.reg_read(regs.UC_X86_REG_IP),
                                 offset=address - observed.DATA, bytes=size, value=value))
        for byte in range(size):
            offset = address + byte - observed.DATA - 0x655e
            if 0 <= offset < 11:
                writes[offset] += 1


observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)
observed.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory)
cases = [(direction, count, pattern, False) for direction in ('right', 'left', 'down')
         for count in range(1, 7) for pattern in ('unique', 'repeated', 'fragment', 'flagged')]
cases += [(direction, count, 'unique', True) for direction in ('right', 'left', 'down') for count in range(1, 7)]
cases += [('stationary', count, 'unique', False) for count in range(1, 7)]
assert len(cases) == 96
requests, results, chain = [], [], hashlib.sha256()
report = dict(schema='lezac.original-above-contact-staging.v1', passed=False,
    recorded_utc=datetime.now(timezone.utc).isoformat(), producer_sha256=sha(Path(__file__).read_bytes()),
    executor_sha256=HELPER_SHA, bank_reader_sha256=READER_SHA, restoration_source_sha256=RESTORE_SHA,
    original_exe_sha256=sha(observed.raw), original_instructions_patched=False,
    original_calls_stubbed=False, hardware_io_permitted=False, observer_neutrality_memory_bytes=1024**2,
    observer_neutrality_registers=14, physical_debris_records=1402, physical_collapse_records=251,
    complete_actor_bank_bytes=1575, complete_sound_bytes=7, initial_fragment_count=0,
    existing_fragments_not_advanced=True, actual_app_comparison=False, seeded=True,
    natural_route=False, whole_game_claim=False, cases=[])
try:
    for index, (direction, count, pattern, gated) in enumerate(cases):
        incoming, target_words = request(bases[index % 2], direction, count, pattern, gated, index)
        report['current_case'] = dict(index=index, direction=direction, count=count, pattern=pattern, gated=gated)
        outputs, snapshots = [], []
        visits.clear(); guard_writes.clear(); calls.clear()
        for executor in (observed, neutral):
            restore(executor, incoming)
            enabled = executor is observed
            executor.cpu.emu_start(0x15102, 0x1ff00, count=4000000)
            enabled = False
            executor.assert_return(0xff00, 0xf000, 0xff02)
            cpu, data = executor.cpu, executor.DATA
            snapshots.append(bytes(cpu.mem_read(0, 1024**2)))
            bound, live = struct.unpack('<HH', bytes(cpu.mem_read(data + 0x207e, 4)))
            output = bytes(cpu.mem_read(data + 0x1afe, 4)) + struct.pack('<HH', bound - 199, live)
            output += bytes(cpu.mem_read(data + 0x78c8, 2)) + bytes(cpu.mem_read(data + 0x78c4, 2))
            output += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
            output += bytes(cpu.mem_read(data + 0x292b, 1402 * 11)) + bytes(cpu.mem_read(data + 0x6620, 251 * 15))
            output += reader['bank'](executor) + reader['sound'](executor)
            outputs.append(output)
        assert outputs[0] == outputs[1] and snapshots[0] == snapshots[1]
        assert [observed.cpu.reg_read(r) for r in tracked] == [neutral.cpu.reg_read(r) for r in tracked]
        assert len(incoming) == INPUT and len(outputs[0]) == STATE
        assert visits['increment_rest'] == 2
        assert all(write['ip'] == 0x4ecd for write in guard_writes)
        if gated or direction == 'stationary':
            assert not guard_writes
        else:
            expected_count = 1 if pattern == 'repeated' else count
            assert len(guard_writes) == expected_count
            assert [write['value'] for write in guard_writes] == list(dict.fromkeys(target_words))
        chain.update(hashlib.sha256(snapshots[0]).digest())
        requests.append(incoming); results.append(outputs[0]); totals.update(visits)
        report['cases'].append(dict(index=index, direction=direction, count=count, pattern=pattern,
            gated=gated, actor_count=incoming[BANK + 1570], target_words=target_words,
            guard_input=incoming[21369:21380].hex(), guard_output=outputs[0][21363:21374].hex(),
            guard_writes=list(guard_writes), collector_calls=list(calls), visits=dict(visits),
            input_sha256=sha(incoming), output_sha256=sha(outputs[0])))
    fixture = b'LZFC0001' + struct.pack('<II', 96, STRIDE)
    fixture += b''.join(incoming + result for incoming, result in zip(requests, results))
    packed = gzip.compress(fixture, mtime=0)
    expected = b'LZFP0001' + struct.pack('<II', 96, STATE) + b''.join(results)
    (OUT / 'above_contact_staging_original.bin.gz').write_bytes(packed)
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
