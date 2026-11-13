"""Observe complete original collapse updates with one through six contacts."""
import argparse
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
PRIOR = ROOT / 'tests/fixtures/collapse_contact_pools_original.bin.gz'
INPUT, STATE, STRIDE = 26727, 26721, 53448
DEBRIS, COLLAPSE, BANK = 5958, 21380, 25145
HELPER_SHA = 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c'
READER_SHA = '50cd6bc4d44a9d805b2598d89b7c626a34c0eb5339b8350b8f8125ffa6c74c73'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def module(path, pin, name):
    raw = path.read_bytes()
    assert sha(raw) == pin
    scope = {'__file__': str(path), '__name__': name}
    exec(compile(raw, str(path), 'exec'), scope)
    return scope


def request(base, direction, count, pattern, index):
    raw = bytearray(base)
    raw[18:DEBRIS] = bytes(DEBRIS - 18)
    dx, dy = {'right': (96, 0), 'left': (-96, 0),
              'down': (0, 96), 'up': (0, -96)}[direction]
    stationary = pattern == 'support-only'
    if stationary:
        dx = dy = 0
    width, height = ((count, 2) if direction in ('down', 'up') or stationary
                     else (2, count))
    first = 20 * 60 + 20
    last = first + (height - 1) * 60 + width - 1

    def tile(cell, byte, word=0):
        raw[18 + cell] = byte
        struct.pack_into('<H', raw, 18 + 1980 + cell * 2, word)

    for cell in (122, 123):
        tile(cell, 0x60, 0x8001)
        tile(cell + 60, 1)
    for y in range(height):
        for x in range(width):
            tile(first + y * 60 + x, 0x60, 0x8002)
    for x in range(width):
        tile(first + height * 60 + x, 1)
    if stationary or direction == 'down':
        targets = [first + height * 60 + x for x in range(count)]
    elif direction == 'up':
        targets = [first - 60 + x for x in range(count)]
    elif direction == 'right':
        targets = [first + y * 60 + width for y in range(count)]
    else:
        targets = [first + y * 60 - 1 for y in range(count)]
    for slot, cell in enumerate(targets):
        word = 0 if pattern == 'hard' else 0xc001 + (0 if pattern == 'repeated' else slot)
        tile(cell, 1 if word == 0 else 0x47, word)
        raw[DEBRIS + slot * 11:DEBRIS + (slot + 1) * 11] = struct.pack(
            '<HHbbbbBBB', cell, word or 0xc001 + slot, -dx,
            0 if direction == 'down' else -dy, 0, 0, 0, 0x47, 0x9a)
    struct.pack_into('<HHHbbbbHBBB', raw, COLLAPSE,
                     244, 246, 0x8001, 0, 0, 0, 0, 0, 0x83, 0, 2)
    struct.pack_into('<HHHbbbbHBBB', raw, COLLAPSE + 15,
                     first * 2, last * 2, 0x8002, dx, dy,
                     100 if dx > 0 else -100 if dx < 0 else 0,
                     100 if dy > 0 else -100 if dy < 0 else 0,
                     abs(dx) + abs(dy), 0x83, (0, 94, 255)[index % 3], width * height)
    struct.pack_into('<HH', raw, 10, count, 2)
    return bytes(raw), targets, width, height


def restore(executor, incoming):
    cpu, base = executor.cpu, executor.DATA
    cpu.context_restore(executor.initial_context)
    cpu.mem_write(0, executor.initial_memory)
    cpu.mem_write(0x40000, bytes(65536))
    cpu.mem_write(0x50000, bytes(65536))
    width, height, tick, rng, debris, collapse, destroyed, next_word = struct.unpack_from('<HHHIHHHH', incoming)
    assert (width, height, collapse) == (60, 33, 2)
    for offset, raw in ((0xc1e0, struct.pack('<HH', 0, 0x4000)),
                       (0xc1fe, struct.pack('<H', 0x4000)),
                       (0x6612, struct.pack('<HH', 0, 0x5000)),
                       (0x206e, struct.pack('<H', 0x5000)),
                       (0xc204, struct.pack('<HH', width, height)),
                       (0x207a, struct.pack('<4H', 0x6620, 0x209e, 199 + debris, collapse)),
                       (0x1afa, bytes(2)), (0x1afe, struct.pack('<I', rng)),
                       (0x78c2, struct.pack('<4H', tick, next_word, 0, destroyed)),
                       (0x292b, incoming[DEBRIS:COLLAPSE]),
                       (0x6620, incoming[COLLAPSE:BANK])):
        cpu.mem_write(base + offset, raw)
    cpu.mem_write(0x40000, incoming[18:18 + 1980])
    cpu.mem_write(0x50000, incoming[18 + 1980:DEBRIS])
    cursor = BANK
    for offset, length in ((0x1bae, 1178), (0xc21e, 264), (0x79ea, 128),
                           (0x208d, 1), (0xc496, 1), (0x79f9, 1), (0x2072, 2),
                           (0x2074, 2), (0x799f, 1), (0x799e, 1),
                           (0x78c0, 2), (0x79c4, 1)):
        cpu.mem_write(base + offset, incoming[cursor:cursor + length])
        cursor += length
    assert cursor == INPUT
    cpu.mem_write(base + 0xc322, executor.descriptors)
    executor.registers(0xf000, 0xff00)
    cpu.mem_write(0x8ff00, struct.pack('<H', 0xff00))


assert not OUT.exists() and os.environ['SDL_AUDIODRIVER'] == 'dummy' and not sys.flags.optimize
OUT.mkdir()
sys.path.insert(0, str(args.unicorn_path.resolve()))
helper = module(ROOT / 'tools/original_bomb_cpu.py', HELPER_SHA, 'contact_staging_cpu')
reader = module(ROOT / 'tools/capture_original_fracture_retirement.py', READER_SHA, 'contact_staging_reader')
import unicorn
from unicorn import x86_const as regs
observed, neutral = helper['BombCPU'](ROOT), helper['BombCPU'](ROOT)
tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
           ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
packed_prior = PRIOR.read_bytes()
assert sha(packed_prior) == '9075ffca72bcdaa17392fee1f2626ae40368c6f3c59a20f0f35fee47eb6ad507'
prior = gzip.decompress(packed_prior)
assert sha(prior) == '1955f2e3eec9bcc5fe2e943105fcc9cdaca103ba115e3bb4c8f09719b0444ea3'
bases = [prior[16 + slot * STRIDE:16 + slot * STRIDE + INPUT] for slot in (0, 1)]
assert bases[0][BANK + 1570] == 0 and bases[1][BANK + 1570] == 30
enabled = False
visits, totals, writes, guard_writes = Counter(), Counter(), Counter(), []
collector_calls = []
anchors = {0x14d3c: 'support_scan', 0x14dd3: 'balance_scan', 0x14e48: 'contact_scan',
           0x1552c: 'increment_rest', 0x15602: 'normal_writeback', 0x1566c: 'timer_remove',
           0x1508b: 'remove', 0x1557b: 'fracture', 0x12f9f: 'actor_constructor', 0x1370e: 'seed'}


def code(cpu, address, size, _):
    if enabled:
        if address in anchors:
            visits[anchors[address]] += 1
        if address == 0x14e48:
            collector_calls.append(dict(delta=struct.unpack('<h', bytes(cpu.mem_read(observed.DATA + 0x2090, 2)))[0],
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
cases = [(direction, count, pattern) for direction in ('right', 'left', 'down', 'up')
         for count in range(1, 7) for pattern in ('unique', 'repeated', 'hard', 'support-only')]
assert len(cases) == 96
requests, results, chain = [], [], hashlib.sha256()
report = dict(schema='lezac.original-contact-staging.v1', passed=False,
    recorded_utc=datetime.now(timezone.utc).isoformat(), producer_sha256=sha(Path(__file__).read_bytes()),
    executor_sha256=HELPER_SHA, bank_reader_sha256=READER_SHA,
    original_exe_sha256=sha(observed.raw), original_instructions_patched=False,
    original_calls_stubbed=False, hardware_io_permitted=False,
    observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
    physical_debris_records=1402, physical_collapse_records=251,
    complete_actor_bank_bytes=1575, complete_sound_bytes=7,
    existing_fragments_not_advanced=True, initial_fragment_terrain_ownership_claim=False,
    actual_app_comparison=False, seeded=True, natural_route=False, whole_game_claim=False, cases=[])
try:
    for index, (direction, count, pattern) in enumerate(cases):
        incoming, target_cells, width, height = request(bases[index % 2], direction, count, pattern, index)
        report['current_case'] = dict(index=index, direction=direction, contacts=count, pattern=pattern)
        outputs, snapshots = [], []
        visits.clear()
        guard_writes.clear()
        collector_calls.clear()
        for executor in (observed, neutral):
            restore(executor, incoming)
            enabled = executor is observed
            executor.cpu.emu_start(0x15102, 0x1ff00, count=4000000)
            enabled = False
            executor.assert_return(0xff00, 0xf000, 0xff02)
            cpu, base = executor.cpu, executor.DATA
            snapshots.append(bytes(cpu.mem_read(0, 1024**2)))
            bound, live = struct.unpack('<HH', bytes(cpu.mem_read(base + 0x207e, 4)))
            result = bytes(cpu.mem_read(base + 0x1afe, 4)) + struct.pack('<HH', bound - 199, live)
            result += bytes(cpu.mem_read(base + 0x78c8, 2)) + bytes(cpu.mem_read(base + 0x78c4, 2))
            result += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
            result += bytes(cpu.mem_read(base + 0x292b, 1402 * 11)) + bytes(cpu.mem_read(base + 0x6620, 251 * 15))
            result += reader['bank'](executor) + reader['sound'](executor)
            outputs.append(result)
        assert outputs[0] == outputs[1] and snapshots[0] == snapshots[1]
        assert [observed.cpu.reg_read(r) for r in tracked] == [neutral.cpu.reg_read(r) for r in tracked]
        assert len(incoming) == INPUT and len(outputs[0]) == STATE
        assert visits['increment_rest'] == 2 and visits['fracture'] == visits['actor_constructor']
        assert all(write['ip'] == 0x4ecd for write in guard_writes)
        if pattern in ('hard', 'support-only'):
            assert not guard_writes
            assert incoming[21369:21380] == outputs[0][21363:21374]
        else:
            expected_count = count if pattern == 'unique' else 1
            assert len(guard_writes) == expected_count
            assert [write['offset'] for write in guard_writes] == [0x655e + 2 * slot for slot in range(expected_count)]
        chain.update(hashlib.sha256(snapshots[0]).digest())
        requests.append(incoming)
        results.append(outputs[0])
        totals.update(visits)
        report['cases'].append(dict(index=index, direction=direction, contacts=count, pattern=pattern,
            actor_count=incoming[BANK + 1570], subject_width=width, subject_height=height,
            target_cells=target_cells, guard_input=incoming[21369:21380].hex(),
            guard_output=outputs[0][21363:21374].hex(), guard_writes=list(guard_writes),
            collector_calls=list(collector_calls), visits=dict(visits),
            input_sha256=sha(incoming), output_sha256=sha(outputs[0])))
    fixture = b'LZFC0001' + struct.pack('<II', 96, STRIDE)
    fixture += b''.join(incoming + result for incoming, result in zip(requests, results))
    packed = gzip.compress(fixture, mtime=0)
    expected = b'LZFP0001' + struct.pack('<II', 96, STATE) + b''.join(results)
    (OUT / 'contact_staging_original.bin.gz').write_bytes(packed)
    (OUT / 'expected.bin').write_bytes(expected)
    report.update(passed=True, total_cases=96, state_bytes=96 * STATE,
        original_visits=dict(totals), guard_write_offsets=dict(writes),
        fixture_bytes=len(fixture), fixture_sha256=sha(fixture),
        fixture_gzip_bytes=len(packed), fixture_gzip_sha256=sha(packed),
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
