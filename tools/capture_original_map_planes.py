"""Capture unmodified original debris map accesses with separated and shared planes."""
import argparse
import ast
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
DEBRIS, COLLAPSE, BANK, INPUT = 5958, 21380, 25145, 26727
PINS = dict(capture_original_contact_staging='f703d8bd4cd3e646c8b78ae98a78b85d15fb42d58a11f271ad06d9696c01c9d1',
    original_bomb_cpu='fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c',
    capture_original_fracture_retirement='50cd6bc4d44a9d805b2598d89b7c626a34c0eb5339b8350b8f8125ffa6c74c73',
    capture_original_physics_dispatch='927dce949bafdf712cc953a778599a52357df6a2451eff90f93857601ff563ef')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def functions(name, names):
    path = ROOT / 'tools' / (name + '.py')
    raw = path.read_bytes()
    assert sha(raw) == PINS[name]
    nodes = [n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), globals())


assert not OUT.exists() and os.environ['SDL_AUDIODRIVER'] == 'dummy' and not sys.flags.optimize
OUT.mkdir()
functions('capture_original_contact_staging', ('module', 'restore'))
sys.path.insert(0, str(args.unicorn_path.resolve()))
helper = module(ROOT / 'tools/original_bomb_cpu.py', PINS['original_bomb_cpu'], 'map_planes_cpu')
reader = module(ROOT / 'tools/capture_original_fracture_retirement.py', PINS['capture_original_fracture_retirement'], 'map_planes_reader')
import unicorn
from unicorn import x86_const as regs
functions('capture_original_physics_dispatch', ('output', 'restore_state', 'run_dispatch'))
observed, neutral = helper['BombCPU'](ROOT), helper['BombCPU'](ROOT)
tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
    ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
enabled, case_index, step, word_base = False, -1, -1, 0x50000
events = []


def memory(cpu, access, address, size, value, _):
    if not enabled:
        return
    assert size in (1, 2)
    plane = 0 if size == 1 else 1
    offset = address - (0x40000 if plane == 0 else word_base)
    assert 0 <= offset <= 65536 - size and (plane == 0 or offset % 2 == 0)
    actual = int.from_bytes(bytes(cpu.mem_read(address, size)), 'little') if access == unicorn.UC_MEM_READ else value
    events.append(dict(case=case_index, step=step, plane=plane,
        write=access == unicorn.UC_MEM_WRITE, offset=offset, value=actual,
        instruction=hex(cpu.reg_read(regs.UC_X86_REG_CS) * 16 + cpu.reg_read(regs.UC_X86_REG_IP))))


observed.cpu.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, memory, None, 0x40000, 0x5ffff)
packed_prior = (ROOT / 'tests/gameplay/physics_dispatch_original.bin.gz').read_bytes()
assert sha(packed_prior) == 'e6552d851b95d4b30d931887eee00d75beafede7a173dabf3add77504c83b1cf'
prior = gzip.decompress(packed_prior)
base = prior[16:16 + 26730]
cases = [
    ('logical-bottom', 1953, 103, 117, 8, 66, 2013, 0),
    ('retained-tail', 2013, 103, 121, 111, 55, 2074, 0),
    ('object-underflow', 0, -96, 0, -96, 0, 65535, 0),
    ('object-overflow', 65535, 96, 0, 96, 0, 0, 0),
    ('word-forward-alias', 32767, 96, 0, 96, 0, 32768, 0),
    ('word-backward-alias', 32768, -96, 0, -96, 0, 32767, 0),
    ('word-upper-alias', 32768, 96, 0, 96, 0, 32769, 0),
    ('vertical-overflow', 65500, 0, 96, 0, 96, 24, 0),
    ('vertical-underflow', 40, 0, -96, 0, -96, 65516, 0),
    ('stationary-tail', 2013, 0, 0, 0, 0, 2013, 0),
    ('shared-tail-write-alias', 1953, 103, 117, 8, 66, 2013, 1),
    ('shared-live-word-alias', 1953, 103, 117, 8, 66, 1953, 1),
]
requests = bytearray(struct.pack('<8sI', b'LZMP0001', len(cases)))
expected = bytearray(struct.pack('<8sI', b'LZMR0001', len(cases)))
chain = hashlib.sha256()
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(), cases=[],
    generator_sha256=sha(Path(__file__).read_bytes()), dependency_sha256=PINS,
    original_exe_sha256=sha(observed.raw), prior_fixture_sha256=sha(packed_prior),
    original_instructions_patched=False, original_calls_stubbed=False, hardware_io_permitted=False,
    seeded=True, natural_route=False, natural_heap_initialization_proven=False, production_app=False,
    actual_cpp_comparison=False, whole_game_complete=False, all_execution_silent=True,
    observer_neutrality_memory_bytes=1048576, observer_neutrality_registers=14)
try:
    for case_index, (name, cell, vx, vy, sx, sy, destination, layout) in enumerate(cases):
        word_base = 0x50000 if layout == 0 else 0x40000 + 2000
        incoming = bytearray(base)
        incoming[18:BANK] = bytes(BANK - 18)
        struct.pack_into('<HHHIHHHH', incoming, 0, 60, 33, 13, 0x12345678, 1, 0, 0, 0xc100)
        incoming[DEBRIS:DEBRIS + 11] = struct.pack('<HHbbbbBBB', cell, 0xc001, vx, vy, sx, sy, 0, 0x49, 0)
        incoming[-3:] = bytes(3)
        for executor in (observed, neutral):
            restore_state(executor, bytes(incoming))
            executor.cpu.mem_write(executor.DATA + 0x6612, struct.pack('<HH', 0, word_base >> 4))
            executor.cpu.mem_write(executor.DATA + 0x206e, struct.pack('<H', word_base >> 4))
            executor.cpu.mem_write(0x40000 + cell, bytes([0x49]))
            executor.cpu.mem_write(word_base + ((cell * 2) & 65535), struct.pack('<H', 0xc001))
            if name == 'shared-live-word-alias':
                executor.cpu.mem_write(word_base + 12, struct.pack('<H', 0x1200))
        planes = bytes(observed.cpu.mem_read(0x40000, 65536)) + bytes(observed.cpu.mem_read(word_base, 65536))
        first_event = len(events)
        row = dict(name=name, layout=layout, object_segment=0x4000, word_segment=word_base >> 4,
            first_cell=cell, first_expected_destination=destination, input_planes_sha256=sha(planes), observations=[])
        report['cases'].append(row)
        for step in range(2):
            actual, ram, registers = run_dispatch(observed, 13 + step)
            duplicate, neutral_ram, neutral_registers = run_dispatch(neutral, 13 + step)
            actual = actual[:1992] + bytes(observed.cpu.mem_read(word_base, 3960)) + actual[5952:]
            duplicate = duplicate[:1992] + bytes(neutral.cpu.mem_read(word_base, 3960)) + duplicate[5952:]
            assert actual == duplicate and ram == neutral_ram and registers == neutral_registers
            position = struct.unpack_from('<H', actual, 5952)[0]
            if step == 0:
                assert position == destination and struct.unpack_from('<H', actual, 4)[0] == 1, (name, position)
            chain.update(hashlib.sha256(ram).digest())
            row['observations'].append(dict(step=step, tile=position, state_sha256=sha(actual), full_memory_sha256=sha(ram)))
        case_events = events[first_event:]
        reads = [event['value'] for event in case_events if not event['write']]
        final_planes = bytes(observed.cpu.mem_read(0x40000, 65536)) + bytes(observed.cpu.mem_read(word_base, 65536))
        requests.extend(struct.pack('<IHHI', layout, 60, 33, len(case_events)) + planes)
        for event in case_events:
            requests.extend(struct.pack('<BBHH', event['plane'], event['write'], event['offset'], event['value'] if event['write'] else 0))
        expected.extend(struct.pack('<I', len(reads)))
        expected.extend(struct.pack('<' + 'H' * len(reads), *reads))
        expected.extend(final_planes)
        row.update(events=len(case_events), reads=len(reads), writes=len(case_events) - len(reads),
            final_planes_sha256=sha(final_planes))
    packed = gzip.compress(bytes(requests), mtime=0)
    packed_expected = gzip.compress(bytes(expected), mtime=0)
    (OUT / 'map_planes_original.bin.gz').write_bytes(packed)
    (OUT / 'map_planes_expected.bin.gz').write_bytes(packed_expected)
    report.update(passed=True, scenes=len(cases), updates_per_scene=2, boundaries=24,
        input_bytes=len(requests), input_sha256=sha(requests), fixture_sha256=sha(packed),
        expected_bytes=len(expected), expected_sha256=sha(expected), expected_fixture_sha256=sha(packed_expected),
        events=len(events), reads=sum(not e['write'] for e in events), writes=sum(e['write'] for e in events),
        full_memory_neutrality_hash_chain=chain.hexdigest())
except BaseException:
    report['error'] = traceback.format_exc()
    raise
finally:
    (OUT / 'events.json').write_text(json.dumps(events, indent=2) + '\n')
    (OUT / 'map_planes_original.json').write_text(json.dumps(report, indent=2) + '\n')
    assert sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()) < 8 * 1024**2
print(json.dumps({k: v for k, v in report.items() if k != 'cases'}), flush=True)
