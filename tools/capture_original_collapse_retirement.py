"""Capture original normal retirement with initialized map-segment bindings."""
from collections import Counter
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import traceback

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--out-directory', type=Path, required=True)
parser.add_argument('--unicorn-path', type=Path)
args = parser.parse_args()
ROOT = args.out_directory.resolve()
ORACLE = args.root.resolve()
assert not ROOT.exists() and os.environ['SDL_AUDIODRIVER'] == 'dummy'
ROOT.mkdir()
if args.unicorn_path:
    sys.path.insert(0, str(args.unicorn_path.resolve()))
helper_path = ORACLE / 'tools/original_bomb_cpu.py'
helper = helper_path.read_bytes()
assert hashlib.sha256(helper).hexdigest() == 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c'
scope = {'__file__': str(helper_path), '__name__': 'original_collapse_retirement_t107'}
exec(compile(helper, str(helper_path), 'exec'), scope)
import unicorn
from unicorn import x86_const as regs

executors = [scope['BombCPU'](ORACLE), scope['BombCPU'](ORACLE)]
tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
    ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
visits = [Counter(), Counter()]
anchors = {0x1552c: 'increment_rest', 0x15602: 'normal_writeback', 0x1566c: 'timer_remove',
           0x1508b: 'remove', 0x1557b: 'fracture', 0x12f9f: 'actor_constructor'}
for executor, counter in zip(executors, visits):
    def observe(cpu, address, length, _, counter=counter):
        if address in anchors:
            counter[anchors[address]] += 1
    executor.cpu.hook_add(unicorn.UC_HOOK_CODE, observe)
report = dict(schema='lezac.original-collapse-retirement.v1', passed=False,
    recorded_utc=datetime.now(timezone.utc).isoformat(), root=str(ORACLE),
    original_exe_sha256=hashlib.sha256(executors[0].raw).hexdigest(), executor_sha256=hashlib.sha256(helper).hexdigest(),
    producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), actual_app_comparison=False,
    original_instructions_patched=False, original_calls_stubbed=False, hardware_io_permitted=False,
    independent_repeats=True, full_repeat_memory_bytes=1024**2, repeat_registers=14,
    corrected_preconditions={'DS:C1FE': '4000', 'DS:206E': '5000'}, cases=[])
chain = hashlib.sha256()
cases = [(1, timer, 0, vx, flags, sy) for timer in (0, 93, 94, 95, 254, 255)
         for vx in (0, 1, 29, 30) for flags in (0, 0x83) for sy in (0, 127)]
cases += [(count, 94, mask, vx, flags, 0) for count in (2, 3) for mask in range(1, 1 << count)
          for vx in (0, 1, 29, 30) for flags in (0, 0x83)]
assert len(cases) == 176
requests, results, total_visits = [], [], Counter()
salt = bytes((19 + index * 23) & 255 for index in range(75))
try:
    assert report['original_exe_sha256'] == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    for case_index, (count, timer, mask, vx, flags, sub_y) in enumerate(cases):
        snapshots, outputs, inputs = [], [], []
        for executor, counter in zip(executors, visits):
            cpu, base = executor.cpu, executor.DATA
            cpu.context_restore(executor.initial_context)
            cpu.mem_write(0, executor.initial_memory)
            cpu.mem_write(0x40000, bytes(65536))
            cpu.mem_write(0x50000, bytes(65536))
            for offset, value in (
                (0xc1e0, struct.pack('<HH', 0, 0x4000)), (0xc1fe, struct.pack('<H', 0x4000)),
                (0x6612, struct.pack('<HH', 0, 0x5000)), (0x206e, struct.pack('<H', 0x5000)),
                (0xc204, struct.pack('<HH', 60, 33)), (0x207a, struct.pack('<H', 0x6620)),
                (0x207e, struct.pack('<HH', 199, 0)), (0x79c8, b'\xa5'),
                (0x1afe, struct.pack('<I', 0x12345678)), (0x78c2, struct.pack('<4H', 0, 0x4000, 0, 0)),
                (0x208d, b'\x00'), (0x6620, salt)):
                cpu.mem_write(base + offset, value)
            for slot in range(count):
                cell = 762 + 4 * slot
                cpu.mem_write(0x40000 + cell, bytes((0x4d + slot,)))
                cpu.mem_write(0x50000 + 2 * cell, struct.pack('<H', slot + 1))
                cpu.mem_write(0x40000 + cell + 60, b'\x01')
                executor.registers(0xf000, 0xff00)
                cpu.mem_write(0x8ff00, struct.pack('<6H', 0xff00, 0xee00, 0x8000, 0, vx, cell))
                cpu.emu_start(0x1370e, 0x1ff00, count=100000)
                executor.assert_return(0xff00, 0xf000, 0xff0c)
                record = base + 0x6620 + 15 * slot
                cpu.mem_write(record + 9, bytes((sub_y,)))
                cpu.mem_write(record + 12, bytes((flags,)))
                rest = timer if count == 1 or mask & (1 << slot) else 93
                cpu.mem_write(record + 13, bytes((rest,)))
            glyphs = bytes(cpu.mem_read(0x40000, 1980))
            words = bytes(cpu.mem_read(0x50000, 3960))
            records = bytes(cpu.mem_read(base + 0x6620, 75))
            request = struct.pack('<HHHIHHHH', 60, 33, 0, 0x12345678, 0, count, 0, 0x4000)
            request += glyphs + words + records
            inputs.append(request)
            counter.clear()
            executor.registers(0xf000, 0xff00)
            cpu.mem_write(0x8ff00, struct.pack('<H', 0xff00))
            cpu.emu_start(0x15102, 0x1ff00, count=300000)
            executor.assert_return(0xff00, 0xf000, 0xff02)
            snapshots.append(bytes(cpu.mem_read(0, 1024**2)))
            output = bytes(cpu.mem_read(base + 0x1afe, 4))
            debris_bound, collapse_count = struct.unpack('<HH', bytes(cpu.mem_read(base + 0x207e, 4)))
            output += struct.pack('<HH', debris_bound - 199, collapse_count)
            output += bytes(cpu.mem_read(base + 0x78c8, 2)) + bytes(cpu.mem_read(base + 0x78c4, 2))
            output += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
            output += bytes(cpu.mem_read(base + 0x6620, 75))
            outputs.append(output)
        assert snapshots[0] == snapshots[1] and outputs[0] == outputs[1] and inputs[0] == inputs[1]
        assert [executors[0].cpu.reg_read(r) for r in tracked] == [executors[1].cpu.reg_read(r) for r in tracked]
        assert visits[0] == visits[1]
        requests.append(inputs[0])
        results.append(outputs[0])
        (ROOT / f'case-{case_index:03d}-input.bin').write_bytes(inputs[0])
        (ROOT / f'case-{case_index:03d}-output.bin').write_bytes(outputs[0])
        expected_removals = int(timer == 94) if count == 1 else mask.bit_count()
        assert visits[0]['timer_remove'] == visits[0]['remove'] == expected_removals
        assert visits[0]['normal_writeback'] == visits[0]['increment_rest'] == count
        assert not visits[0]['fracture'] and not visits[0]['actor_constructor']
        assert struct.unpack_from('<HH', outputs[0], 4) == (0, count - expected_removals)
        assert outputs[0][:4] == struct.pack('<I', 0x12345678)
        assert outputs[0][-30:] == salt[-30:]
        if count == 1:
            after = outputs[0][-75:-60]
            assert after[13] == (timer + 1) & 255
            expected_flags = flags & 0xfc if vx < 30 else flags
            assert after[6] == max(0, vx - 1) and after[8] == vx and after[12] == expected_flags
        chain.update(hashlib.sha256(snapshots[0]).digest())
        total_visits.update(visits[0])
        report['cases'].append(dict(index=case_index, count=count, timer=timer, retirement_mask=mask,
            vx=vx, flags=flags, sub_y=sub_y, removals=expected_removals,
            visits=dict(visits[0]), input_sha256=hashlib.sha256(inputs[0]).hexdigest(),
            output_sha256=hashlib.sha256(outputs[0]).hexdigest()))
    assert all(len(raw) == 6033 for raw in requests) and all(len(raw) == 6027 for raw in results)
    fixture = b'LZRT0001' + struct.pack('<II', len(cases), 12060)
    fixture += b''.join(request + result for request, result in zip(requests, results))
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb', filename='', mtime=0) as stream:
        stream.write(fixture)
    packed = buffer.getvalue()
    (ROOT / 'collapse_retirement_original.bin.gz').write_bytes(packed)
    expected = b'LZRO0001' + struct.pack('<II', len(cases), 6027) + b''.join(results)
    fnv = 14695981039346656037
    for byte in fixture:
        fnv = ((fnv ^ byte) * 1099511628211) & ((1 << 64) - 1)
    report.update(passed=True, original_timer_retirement_reached=True, complete_physical_records=5,
        total_cases=len(cases), state_bytes=len(expected) - 16, output_bytes=len(expected), original_visits=dict(total_visits),
        fixture_bytes=len(fixture), fixture_sha256=hashlib.sha256(fixture).hexdigest(),
        fixture_gzip_bytes=len(packed), fixture_gzip_sha256=hashlib.sha256(packed).hexdigest(),
        fixture_fnv=f'{fnv:016x}', expected_sha256=hashlib.sha256(expected).hexdigest(),
        full_memory_repeat_hash_chain=chain.hexdigest())
except BaseException:
    report['error'] = traceback.format_exc()
    raise
finally:
    raw = (json.dumps(report, indent=2) + '\n').encode()
    (ROOT / 'capture.json').write_bytes(raw)
    report['root_bytes'] = sum(path.stat().st_size for path in ROOT.rglob('*') if path.is_file())
    assert report['root_bytes'] < 8 * 1024**2
    print(json.dumps({key: value for key, value in report.items() if key != 'cases'}), flush=True)
