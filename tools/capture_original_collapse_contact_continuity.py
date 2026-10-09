"""Observe eight consecutive original multi-record contact-collapse boundaries."""
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
    BANK, COLLAPSE, CPU_SHA, DEBRIS, INPUT, READER_SHA, STAGING_SHA, sha)

LANE_SHA = '2c162aedce2a54977e623e0de37fdadb7f3f73aff028fccf8e6ca5aea9821492'
HELPER_SHA = '99ee5aaa4624c6cc71cf7828d800f00e68af61df386b7de82741864933d03e2e'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path, required=True)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    assert not out.exists() and not sys.flags.optimize and os.environ['SDL_AUDIODRIVER'] == 'dummy'
    out.mkdir()
    assert sha((root / 'tools/capture_original_collapse_lane_history.py').read_bytes()) == HELPER_SHA
    source = (root / 'tools/capture_original_contact_staging.py').read_bytes()
    assert sha(source) == STAGING_SHA
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.FunctionDef) and node.name in ('module', 'restore')]
    assert len(nodes) == 2
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<pinned restoration>', 'exec'), globals())
    sys.path.insert(0, str(args.unicorn_path.resolve()))
    helper = module(root / 'tools/original_bomb_cpu.py', CPU_SHA, 'continuity_cpu')
    reader = module(root / 'tools/capture_original_fracture_retirement.py', READER_SHA, 'continuity_reader')
    import unicorn
    from unicorn import x86_const as regs
    observed, neutral, fresh = (helper['BombCPU'](root) for _ in range(3))
    caller = bytes.fromhex('833e8020007603e898d0')
    assert observed.raw[0x770 + 0x8060:0x770 + 0x806a] == caller
    tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
        ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
    enabled, visits = False, Counter()

    def code(cpu, address, size, unused):
        if enabled and address in (0x15102, 0x1370e, 0x1557b, 0x1566c):
            visits[hex(address)] += 1

    observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)

    def output(executor):
        cpu, data = executor.cpu, executor.DATA
        bound, live = struct.unpack('<HH', bytes(cpu.mem_read(data + 0x207e, 4)))
        assert 199 <= bound <= 1600 and live <= 250
        raw = bytes(cpu.mem_read(data + 0x1afe, 4)) + struct.pack('<HH', bound - 199, live)
        raw += bytes(cpu.mem_read(data + 0x78c8, 2)) + bytes(cpu.mem_read(data + 0x78c4, 2))
        raw += bytes(cpu.mem_read(0x40000, 1980)) + bytes(cpu.mem_read(0x50000, 3960))
        raw += bytes(cpu.mem_read(data + 0x292b, 1402 * 11))
        raw += bytes(cpu.mem_read(data + 0x6620, 251 * 15))
        raw += reader['bank'](executor) + reader['sound'](executor)
        raw += bytes(cpu.mem_read(data + 0x661e, 1)) + bytes(cpu.mem_read(data + 0xa06, 2))
        assert len(raw) == 26724
        return raw

    def restore_state(executor, incoming):
        assert len(incoming) == 26730
        # The reused restorer requires two records; restore the real count before execution.
        adapter = bytearray(incoming[:INPUT])
        struct.pack_into('<H', adapter, 12, 2)
        restore(executor, bytes(adapter))
        executor.cpu.mem_write(executor.DATA + 0x2080, incoming[12:14])
        executor.cpu.mem_write(executor.DATA + 0x661e, incoming[-3:-2])
        executor.cpu.mem_write(executor.DATA + 0xa06, incoming[-2:])

    packed_lane = (root / 'tests/gameplay/collapse_lane_history_original.bin.gz').read_bytes()
    assert sha(packed_lane) == LANE_SHA
    lane = gzip.decompress(packed_lane)
    assert struct.unpack_from('<8sII', lane) == (b'LZCH0001', 96, 53454)
    fixture = bytearray(b'LZCH0001' + struct.pack('<II', 768, 53454))
    incoming_stream = bytearray(b'LZCI0001' + struct.pack('<II', 768, 26730))
    expected_stream = bytearray(b'LZCO0001' + struct.pack('<II', 768, 26724))
    observations, groups, chain = [], Counter(), hashlib.sha256()
    report = dict(schema='lezac.collapse-contact-continuity.v1', passed=False, cases=768)
    try:
        for scene in range(96):
            offset = 16 + scene * 53454
            initial = lane[offset:offset + 26730]
            expected_first = lane[offset + 26730:offset + 53454]
            assert struct.unpack_from('<H', initial, 12)[0] == 2
            for executor in (observed, neutral):
                restore_state(executor, initial)
            for step in range(8):
                tick = (struct.unpack_from('<H', initial, 4)[0] + step) & 65535
                incoming = struct.pack('<3H', 60, 33, tick) + output(observed)
                active = struct.unpack_from('<H', incoming, 12)[0] != 0
                visits_before = visits.copy()
                report['current_boundary'] = dict(scene=scene, step=step, tick=tick, active=active)
                restore_state(fresh, incoming)
                assert output(fresh) == output(observed)
                snapshots, registers, outputs = [], [], []
                for executor in (observed, neutral, fresh):
                    executor.cpu.mem_write(executor.DATA + 0x78c2, struct.pack('<H', tick))
                    executor.registers(0xf000, 0xff00)
                    executor.cpu.mem_write(0x8ff00, struct.pack('<H', 0xff00))
                    if active:
                        enabled = executor is observed
                        executor.cpu.emu_start(0x15102, 0x1ff00, count=4000000)
                        enabled = False
                        executor.assert_return(0xff00, 0xf000, 0xff02)
                    snapshot = bytes(executor.cpu.mem_read(0, 1024**2))
                    assert snapshot[0x10000:0x1aa20] == executor.initial_memory[0x10000:0x1aa20]
                    snapshots.append(snapshot)
                    outputs.append(output(executor))
                    registers.append([executor.cpu.reg_read(register) for register in tracked])
                assert snapshots[0] == snapshots[1] and registers[0] == registers[1]
                assert outputs[0] == outputs[1] == outputs[2]
                if step == 0:
                    assert outputs[0] == expected_first and incoming == initial
                chain.update(hashlib.sha256(snapshots[0]).digest())
                fixture.extend(incoming + outputs[0])
                incoming_stream.extend(incoming)
                expected_stream.extend(outputs[0])
                groups['active_update' if active else 'empty_queue_skip'] += 1
                observations.append(dict(scene=scene, step=step, tick=tick, active=active,
                    input_sha256=sha(incoming), output_sha256=sha(outputs[0]),
                    reconstructed_output_sha256=sha(outputs[2]),
                    original_visits=dict(visits - visits_before),
                    debris_before=struct.unpack_from('<H', incoming, 10)[0],
                    debris_after=struct.unpack_from('<H', outputs[0], 4)[0],
                    collapse_before=struct.unpack_from('<H', incoming, 12)[0],
                    collapse_after=struct.unpack_from('<H', outputs[0], 6)[0]))
        assert len(observations) == 768 and sum(groups.values()) == 768
        packed = gzip.compress(fixture, mtime=0)
        report = dict(schema='lezac.collapse-contact-continuity.v1', passed=True, cases=768, groups=dict(groups),
            initial_scenes=96, boundaries_per_scene=8, initial_calls_match_lane_fixture=True,
            initial_live_collapse_records=2,
            initial_scene_groups={'debris': 36, 'collapse': 12, 'alternating': 36, 'collapse-group': 12},
            input_bytes=26730, state_bytes=26724, fixture_sha256=sha(packed), fixture_raw_sha256=sha(fixture),
            input_sha256=sha(incoming_stream), expected_sha256=sha(expected_stream),
            producer_sha256=sha(Path(__file__).read_bytes()), executor_sha256=CPU_SHA,
            staging_sha256=STAGING_SHA, reader_sha256=READER_SHA, lane_fixture_sha256=LANE_SHA,
            capture_helper_sha256=HELPER_SHA, original_visits=dict(visits),
            original_exe_sha256=sha(observed.raw), full_ram_hash_chain=chain.hexdigest(),
            observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
            original_calls_stubbed=False, original_instructions_patched=False, hardware_io_permitted=False,
            full_collapse_update=True, continuous_original_image=True,
            serialized_state_sufficient_for_observed_sequence=True,
            original_caller_empty_queue_gate='1000:8060-806A', original_caller_gate_hex=caller.hex(),
            first_seed_stack_history_generally_proven=False, masks=0, actual_app_executed=False,
            continuous_app_execution_proven=False, seeded=True, natural_route=False,
            original_fidelity_claim=False, whole_game_complete=False)
        (out / 'collapse_contact_continuity_original.bin.gz').write_bytes(packed)
    except BaseException as error:
        report.update(error=str(error), error_type=type(error).__name__)
        report.update(completed_boundaries=len(observations), original_visits=dict(visits))
        if 'incoming' in locals():
            (out / 'failure-input.bin.gz').write_bytes(gzip.compress(incoming, mtime=0))
        for label, executor in (('observed', observed), ('neutral', neutral), ('fresh', fresh)):
            ram = bytes(executor.cpu.mem_read(0, 1024**2))
            (out / ('failure-' + label + '-ram.bin.gz')).write_bytes(gzip.compress(ram, mtime=0))
            (out / ('failure-' + label + '-state.bin.gz')).write_bytes(gzip.compress(output(executor), mtime=0))
            (out / ('failure-' + label + '-registers.json')).write_text(json.dumps(
                [executor.cpu.reg_read(register) for register in tracked], indent=2) + '\n')
        raise
    finally:
        (out / 'collapse_contact_continuity_original.json').write_text(json.dumps(report, indent=2) + '\n')
        (out / 'observations.json').write_text(json.dumps(observations, indent=2) + '\n')
        assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < 8 * 1024**2
    print(json.dumps(dict(report, packed_bytes=len(packed))), flush=True)


if __name__ == '__main__':
    main()
