"""Observe the unmodified original debris/collapse frame-dispatch region."""
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

CPU_SHA = 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c'
STAGING_SHA = 'f703d8bd4cd3e646c8b78ae98a78b85d15fb42d58a11f271ad06d9696c01c9d1'
READER_SHA = '50cd6bc4d44a9d805b2598d89b7c626a34c0eb5339b8350b8f8125ffa6c74c73'
LANE_SHA = '2c162aedce2a54977e623e0de37fdadb7f3f73aff028fccf8e6ca5aea9821492'
DEBRIS, COLLAPSE, BANK, INPUT = 5958, 21380, 25145, 26727
DISPATCH = bytes.fromhex('833e7620007708813e7e20c8007203e89ac5833e8020007603e898d0')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--unicorn-path', type=Path, required=True)
args = parser.parse_args()
ROOT = args.root.resolve()
OUT = args.out.resolve()
assert not OUT.exists() and not sys.flags.optimize and os.environ['SDL_AUDIODRIVER'] == 'dummy'
OUT.mkdir()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


source = (ROOT / 'tools/capture_original_contact_staging.py').read_bytes()
assert sha(source) == STAGING_SHA
nodes = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in ('module', 'restore')]
assert len(nodes) == 2
exec(compile(ast.Module(body=nodes, type_ignores=[]), '<pinned restoration>', 'exec'), globals())
sys.path.insert(0, str(args.unicorn_path.resolve()))
helper = module(ROOT / 'tools/original_bomb_cpu.py', CPU_SHA, 'physics_dispatch_cpu')
reader = module(ROOT / 'tools/capture_original_fracture_retirement.py', READER_SHA, 'physics_dispatch_reader')
import unicorn
from unicorn import x86_const as regs
observed, neutral, fresh, collapse_only = [helper['BombCPU'](ROOT) for _ in range(4)]
assert observed.raw[0x770 + 0x804e:0x770 + 0x806a] == DISPATCH
tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
    ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
enabled, visits = False, Counter()


def code(cpu, address, size, unused):
    if enabled and address in (0x1804e, 0x145fa, 0x15102, 0x1370e, 0x1557b, 0x1566c, 0x12f9f, 0x1165a):
        visits[hex(address)] += 1


observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)


def output(executor):
    cpu, data = executor.cpu, executor.DATA
    bound, live = struct.unpack('<HH', bytes(cpu.mem_read(data + 0x207e, 4)))
    assert 199 <= bound <= 1600 and live <= 250
    assert bytes(cpu.mem_read(data + 0x2076, 2)) == bytes(2)
    raw = bytes(cpu.mem_read(data + 0x1afe, 4)) + struct.pack('<HH', bound - 199, live)
    raw += bytes(cpu.mem_read(data + 0x78c8, 2)) + bytes(cpu.mem_read(data + 0x78c4, 2))
    raw += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
    raw += bytes(cpu.mem_read(data + 0x292b, 1402 * 11)) + bytes(cpu.mem_read(data + 0x6620, 251 * 15))
    raw += reader['bank'](executor) + reader['sound'](executor)
    raw += bytes(cpu.mem_read(data + 0x661e, 1)) + bytes(cpu.mem_read(data + 0xa06, 2))
    assert len(raw) == 26724
    return raw


def restore_state(executor, incoming):
    assert len(incoming) == 26730
    adapter = bytearray(incoming[:26727])
    struct.pack_into('<H', adapter, 12, 2)
    restore(executor, bytes(adapter))
    executor.cpu.mem_write(executor.DATA + 0x2080, incoming[12:14])
    executor.cpu.mem_write(executor.DATA + 0x661e, incoming[-3:-2])
    executor.cpu.mem_write(executor.DATA + 0xa06, incoming[-2:])


def run_dispatch(executor, tick, start=0x1804e):
    global enabled
    executor.cpu.mem_write(executor.DATA + 0x78c2, struct.pack('<H', tick))
    executor.registers(0xf000, 0xff00)
    enabled = executor is observed
    try:
        executor.cpu.emu_start(start, 0x1806a, count=4000000)
    finally:
        enabled = False
    executor.assert_return(0x806a, 0xf000, 0xff00)
    ram = bytes(executor.cpu.mem_read(0, 1024**2))
    assert ram[0x10000:0x1aa20] == executor.initial_memory[0x10000:0x1aa20]
    return output(executor), ram, [executor.cpu.reg_read(register) for register in tracked]


packed = (ROOT / 'tests/gameplay/collapse_lane_history_original.bin.gz').read_bytes()
assert sha(packed) == LANE_SHA
lane = gzip.decompress(packed)
assert struct.unpack_from('<8sII', lane) == (b'LZCH0001', 96, 53454)
indices, steps = list(range(0, 96, 3)), 16
assert len(indices) == 32
fixture = bytearray(struct.pack('<8sII', b'LZCH0001', len(indices) * steps, 53454))
inputs = bytearray(struct.pack('<8sII', b'LZCI0001', len(indices) * steps, 26730))
outputs = bytearray(struct.pack('<8sII', b'LZCO0001', len(indices) * steps, 26724))
counterfactual = bytearray(struct.pack('<8sII', b'LZCO0001', len(indices) * steps, 26724))
regions = (('rng', 0, 4), ('live_counts', 4, 8), ('destruction_fragment_counters', 8, 12),
    ('tiles', 12, 1992), ('words', 1992, 5952), ('physical_debris', 5952, 21374),
    ('physical_collapse', 21374, 25139), ('actor_bank', 25139, 26714),
    ('sound_state', 26714, 26721), ('lane_history', 26721, 26724))
observations, chain, region_changes = [], hashlib.sha256(), Counter()
report = dict(passed=False, schema='lezac.original-physics-dispatch-investigation.v1', original_lane_indices=indices,
    initial_scenes=32, steps_per_scene=steps, expected_boundaries=512, original_dispatch_hex=DISPATCH.hex(),
    original_dispatch_start='1000:804E', original_dispatch_end='1000:806A',
    original_instructions_patched=False, original_calls_stubbed=False, hardware_io_permitted=False,
    production_app_executed=False, full_game_tick_proven=False, natural_route=False, whole_game_complete=False)
try:
    for scene, original_index in enumerate(indices):
        offset = 16 + original_index * 53454
        initial = lane[offset:offset + 26730]
        first_expected = lane[offset + 26730:offset + 53454]
        assert struct.unpack_from('<HH', initial, 10) == (0, 2)
        for executor in (observed, neutral):
            restore_state(executor, initial)
        for step in range(steps):
            tick = (struct.unpack_from('<H', initial, 4)[0] + step) & 65535
            incoming = struct.pack('<3H', 60, 33, tick) + output(observed)
            report['current_boundary'] = dict(scene=scene, original_index=original_index, step=step, tick=tick)
            for executor in (fresh, collapse_only):
                restore_state(executor, incoming)
            assert output(fresh) == output(observed) == output(neutral)
            before = visits.copy()
            actual, ram, registers = run_dispatch(observed, tick)
            neutral_actual, neutral_ram, neutral_registers = run_dispatch(neutral, tick)
            reconstructed, _, _ = run_dispatch(fresh, tick)
            isolated_collapse, _, _ = run_dispatch(collapse_only, tick, start=0x18060)
            assert ram == neutral_ram and registers == neutral_registers
            assert actual == neutral_actual == reconstructed
            if step == 0:
                assert incoming == initial and actual == first_expected
            chain.update(hashlib.sha256(ram).digest())
            fixture.extend(incoming + actual)
            inputs.extend(incoming)
            outputs.extend(actual)
            counterfactual.extend(isolated_collapse)
            changed_regions = [name for name, begin, end in regions if actual[begin:end] != isolated_collapse[begin:end]]
            region_changes.update(changed_regions)
            observations.append(dict(scene=scene, original_index=original_index, step=step, tick=tick,
                input_sha256=sha(incoming), output_sha256=sha(actual), reconstructed_sha256=sha(reconstructed),
                collapse_only_sha256=sha(isolated_collapse), preceding_debris_changes_output=actual != isolated_collapse,
                changed_regions=changed_regions,
                original_visits=dict(visits - before), debris_before=struct.unpack_from('<H', incoming, 10)[0],
                debris_after=struct.unpack_from('<H', actual, 4)[0], collapse_before=struct.unpack_from('<H', incoming, 12)[0],
                collapse_after=struct.unpack_from('<H', actual, 6)[0]))
        print('scene=' + str(scene) + ' boundaries=' + str(len(observations)), flush=True)
    packed = gzip.compress(fixture, mtime=0)
    (OUT / 'physics_dispatch_original.bin.gz').write_bytes(packed)
    reference_packed = gzip.compress(counterfactual, mtime=0)
    (OUT / 'collapse_only_reference.bin.gz').write_bytes(reference_packed)
    report.update(passed=True, boundaries=len(observations), fixture_sha256=sha(packed), fixture_raw_sha256=sha(fixture),
        input_sha256=sha(inputs), expected_sha256=sha(outputs), packed_bytes=len(packed), original_visits=dict(visits),
        original_exe_sha256=sha(observed.raw), producer_sha256=sha(Path(__file__).read_bytes()), executor_sha256=CPU_SHA,
        staging_sha256=STAGING_SHA, reader_sha256=READER_SHA, lane_fixture_sha256=LANE_SHA,
        full_ram_hash_chain=chain.hexdigest(), observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
        serialized_state_sufficient_for_observed_dispatch=True, initial_calls_match_lane_fixture=True,
        collapse_only_reference_sha256=sha(reference_packed), collapse_only_reference_raw_sha256=sha(counterfactual),
        counterfactual_region_changes=dict(region_changes),
        boundaries_changed_by_preceding_debris=sum(row['preceding_debris_changes_output'] for row in observations))
except BaseException as error:
    report.update(error=str(error), error_type=type(error).__name__, completed_boundaries=len(observations), original_visits=dict(visits))
    if 'incoming' in locals():
        (OUT / 'failure-input.bin.gz').write_bytes(gzip.compress(incoming, mtime=0))
    for name, executor in (('observed', observed), ('neutral', neutral), ('fresh', fresh), ('collapse-only', collapse_only)):
        (OUT / ('failure-' + name + '-ram.bin.gz')).write_bytes(gzip.compress(bytes(executor.cpu.mem_read(0, 1024**2)), mtime=0))
        (OUT / ('failure-' + name + '-registers.json')).write_text(json.dumps(
            [executor.cpu.reg_read(register) for register in tracked], indent=2) + '\n')
    raise
finally:
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (OUT / 'observations.json').write_text(json.dumps(observations, indent=2) + '\n')
    assert sum(path.stat().st_size for path in OUT.rglob('*') if path.is_file()) < 8 * 1024**2
print(json.dumps(report), flush=True)
