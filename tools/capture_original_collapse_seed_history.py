"""Capture original SS-caller contact blends with repeated staged targets."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

CPU_SHA = 'fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c'
ENCODER_SHA = '29539957662f4e86a0fc521e9509aba6059316f6d25c1a6eac83a1c3b7412504'
PROFILES = ('debris_twice', 'debris_six', 'debris_thirty', 'collapse_twice',
            'collapse_six', 'debris_collapse_debris', 'collapse_debris_collapse',
            'debris_flagged_debris')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def module(path, pin, name):
    raw = path.read_bytes()
    assert sha(raw) == pin
    scope = {'__file__': str(path), '__name__': name}
    exec(compile(raw, str(path), 'exec'), scope)
    return scope


def cases():
    for profile in PROFILES:
        for bound in (200, 1599, 1600):
            debris = [struct.pack('<HHbbbbBBB', 3, 0xc000 + slot,
                       -49, 49, 0, 0, 0, 0x55, 0) for slot in range(200, bound + 1)]
            collapse = [struct.pack('<HHHbbbbHBBB', 4, 4, 0x8001,
                         127, -128, 0, 0, 0, 0, 0, 254)]
            words, tiles = bytearray(256), bytearray(128)
            for cell, word, tile in ((2, 0x8001, 0x55), (3, 0xc0c8, 0x55),
                                     (32, 0x4001, 0x31), (40, 0x0011, 0x41)):
                struct.pack_into('<H', words, 2 * cell, word)
                tiles[cell] = tile
            d, c, flagged = (32, 0x4001), (40, 0x0011), (2, 0x8001)
            contacts = {'debris_twice': [d, d], 'debris_six': [d] * 6,
                'debris_thirty': [d] * 30, 'collapse_twice': [c, c],
                'collapse_six': [c] * 6, 'debris_collapse_debris': [d, c, d],
                'collapse_debris_collapse': [c, d, c],
                'debris_flagged_debris': [d, flagged, d]}[profile]
            for own in (-128, -49, 49, 127):
                for weight in (1, 18, 255):
                    for reverse in (0, 1):
                        yield profile, own, weight, reverse, debris, collapse, bytes(words), bytes(tiles), contacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path, required=True)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    assert not out.exists() and not sys.flags.optimize
    assert os.environ['SDL_AUDIODRIVER'] == 'dummy'
    sys.path.insert(0, str(args.unicorn_path.resolve()))
    helper = module(root / 'tools/original_bomb_cpu.py', CPU_SHA, 'collapse_seed_history_cpu')
    encoder = module(root / 'tools/capture_original_collapse_contacts.py', ENCODER_SHA,
                     'collapse_seed_history_encoder')
    import unicorn
    from unicorn import x86_const as regs
    observed, neutral = helper['BombCPU'](root), helper['BombCPU'](root)
    tracked = [getattr(regs, 'UC_X86_REG_' + name) for name in
        ('AX', 'BX', 'CX', 'DX', 'SI', 'DI', 'BP', 'SP', 'CS', 'DS', 'ES', 'SS', 'IP', 'EFLAGS')]
    enabled, trace, visits = False, [], Counter()

    def code(cpu, address, size, _):
        if not enabled:
            return
        if address in (0x1370e, 0x13a7e, 0x13b18):
            visits[hex(address)] += 1
        if address in (0x13c23, 0x13c26, 0x13db7, 0x13dba):
            trace.append(dict(ip=cpu.reg_read(regs.UC_X86_REG_IP),
                seed_class=cpu.mem_read(0x8fef2, 1)[0],
                result=cpu.mem_read(observed.DATA + 0x79c8, 1)[0]))

    observed.cpu.hook_add(unicorn.UC_HOOK_CODE, code)
    matrix = list(cases())
    assert len(matrix) == 576
    fixture = bytearray(b'LZCF0001' + struct.pack('<I', len(matrix)))
    inputs, outputs, ram_chain = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()
    groups, observations, early_returns = Counter(), [], 0
    for index, case in enumerate(matrix):
        profile, own, weight, reverse, debris, collapse, words, tiles, contacts = case
        results, snapshots, registers = [], [], []
        trace.clear(); visits.clear()
        for executor in (observed, neutral):
            cpu, data = executor.cpu, executor.DATA
            cpu.context_restore(executor.initial_context)
            cpu.mem_write(0, executor.initial_memory)
            for offset, raw in ((0x1afa, bytes(2)), (0x6612, struct.pack('<HH', 0, 0x5000)),
                               (0xc1e0, struct.pack('<HH', 0, 0x4000)),
                               (0xc204, struct.pack('<HH', 64, 2)),
                               (0x2076, struct.pack('<HH', 0, len(contacts))),
                               (0x207e, struct.pack('<HH', 199 + len(debris), len(collapse))),
                               (0x292b, b''.join(debris)), (0x6620, b''.join(collapse)),
                               (0x78d2, b'\x6d'), (0x79c8, b'\x7f')):
                cpu.mem_write(data + offset, raw)
            cpu.mem_write(0x50000, words)
            cpu.mem_write(0x40000, tiles)
            for slot, (cell, word) in enumerate(contacts, 1):
                cpu.mem_write(data + 0x655c + 2 * slot, struct.pack('<H', word))
                cpu.mem_write(data + 0x6598 + 2 * slot, struct.pack('<H', 2 * cell))
                cpu.mem_write(data + 0x65d4 + 2 * slot, b'\xcc\xcc')
            executor.registers(0xf000, 0xff00)
            cpu.mem_write(0x8ff00, struct.pack('<HHHH', 0xff00, 0xef00, 0x8000, weight))
            cpu.mem_write(0x8ef00, bytes((own & 255,)))
            cpu.mem_write(0x8fef2, b'\xa5')
            enabled = executor is observed
            cpu.emu_start(0x13d46 if reverse else 0x13bb2, 0x1ff00, count=200000)
            enabled = False
            executor.assert_return(0xff00, 0xf000, 0xff08)
            snapshot = bytes(cpu.mem_read(0, 1024**2))
            assert snapshot[0x10000:0x1aa20] == executor.initial_memory[0x10000:0x1aa20]
            assert cpu.mem_read(data + 0x78d2, 1) == b'\x6d'
            bound, live = struct.unpack('<HH', bytes(cpu.mem_read(data + 0x207e, 4)))
            assert 199 <= bound <= 1600 and live <= 30
            result = bytes(cpu.mem_read(0x8ef00, 1)) + struct.pack('<HH', bound - 199, live)
            result += bytes(cpu.mem_read(data + 0x292b, 11 * (bound - 199)))
            result += bytes(cpu.mem_read(data + 0x6620, 15 * live))
            result += bytes(cpu.mem_read(0x50000, 256)) + bytes(cpu.mem_read(0x40000, 128))
            results.append(result); snapshots.append(snapshot)
            registers.append([cpu.reg_read(register) for register in tracked])
        assert snapshots[0] == snapshots[1] and results[0] == results[1] and registers[0] == registers[1]
        assert trace and len(trace) % 2 == 0 and trace[0]['seed_class'] == 0xa5
        # The first real seed defines the local; no output depends on its poison input.
        assert trace[1]['seed_class'] in (0, 1)
        early_returns += sum(before['seed_class'] == after['seed_class'] and after['result'] == 1
                             for before, after in zip(trace[2::2], trace[3::2]))
        incoming = encoder['request'](case)
        fixture.extend(struct.pack('<II', len(incoming), len(results[0])) + incoming + results[0])
        inputs.update(incoming); outputs.update(results[0])
        ram_chain.update(hashlib.sha256(snapshots[0]).digest())
        groups[profile] += 1
        observations.append(dict(index=index, profile=profile, bound=199 + len(debris),
            reverse=reverse, initial_velocity=own, weight=weight, trace=list(trace), visits=dict(visits),
            result_sha256=sha(results[0])))
    packed = gzip.compress(fixture, mtime=0)
    metadata = dict(schema='lezac.collapse-seed-history.v1', cases=len(matrix), groups=dict(groups),
        input_sha256=inputs.hexdigest(), output_sha256=outputs.hexdigest(), fixture_sha256=sha(packed),
        producer_sha256=sha(Path(__file__).read_bytes()), executor_sha256=CPU_SHA, encoder_sha256=ENCODER_SHA,
        original_exe_sha256=sha(observed.raw), full_ram_hash_chain=ram_chain.hexdigest(),
        observer_neutrality_memory_bytes=1024**2, observer_neutrality_registers=14,
        ss_caller_offset=0xef00, ss_seed_class_offset=0xfef2, first_seed_defines_class=True,
        repeated_seed_class_retained_calls=early_returns, original_calls_stubbed=False,
        original_instructions_patched=False, hardware_io_permitted=False,
        actual_app_executed=False, full_collapse_update=False, natural_gameplay=False,
        original_fidelity_claim=False, whole_game_complete=False)
    out.mkdir()
    (out / 'collapse_seed_history_original.bin.gz').write_bytes(packed)
    (out / 'collapse_seed_history_original.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (out / 'observations.json').write_text(json.dumps(observations, indent=2) + '\n')
    assert sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) < 8 * 1024**2
    print(json.dumps(dict(passed=True, **metadata, packed_bytes=len(packed))), flush=True)


if __name__ == '__main__':
    main()
