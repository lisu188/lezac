"""Execute unchanged post-render spawners and waiting prepass as one window."""
import argparse
import gzip
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

from ammo_hud_oracle import ASSET_SHA, sprites
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha
from frame_spawner_oracle import inputs as spawner_inputs, profiles as spawner_profiles
from frame_waiting_oracle import profiles as waiting_profiles, seeds as waiting_seeds


def generate(root, out):
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output directory')
    out.mkdir()
    index = None
    try:
        names = ('frame_prefix_oracle.py', 'frame_spawner_oracle.py', 'frame_waiting_oracle.py',
                 'ammo_hud_oracle.py', 'frame_camera_oracle.py')
        dependencies = {name: sha((root / 'tools' / name).read_bytes()) for name in names}
        if unicorn.__version__ != '2.1.4' or any(key in os.environ for key in ('LD_PRELOAD', 'LIBUNICORN_PATH')):
            raise ValueError('Unsupported original oracle loader')
        library = Path(uclib._name).resolve(strict=True)
        if sha(library.read_bytes()) != LIB_SHA or not any(
                line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
            raise ValueError('Actual oracle library mapping differs')
        pins = dict(ASSET_SHA, **{'LEZAC.EXE': EXE_SHA})
        assets = {name: (root / name).read_bytes() for name in pins}
        if any(sha(assets[name]) != pin for name, pin in pins.items()):
            raise ValueError('Original canonical asset differs')
        exe = assets['LEZAC.EXE']
        mz = struct.unpack_from('<14H', exe)
        image = bytearray(exe[mz[4] * 16:])
        for item in range(mz[3]):
            offset, segment = struct.unpack_from('<HH', exe, mz[12] + item * 4)
            at = segment * 16 + offset
            struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
        tiles, atlas = assets['CARO.CAR'][2:], sprites(assets['BOMOMIMK.SPR'])
        waiting, spawners = waiting_profiles(), spawner_profiles()
        output = bytearray(b'LZPRFX01' + struct.pack('<I', len(waiting)))
        coverage, states, write_count = set(), 0, 0
        outcomes = [0, 0, 0]
        stops = {0x17ebb: 0, 0x11b14: 1, 0x192e2: 2}
        for index, row in enumerate(waiting):
            profile = spawners[index % len(spawners)]
            row = dict(row)
            row['floor'] = max(row['floor'], profile[4])
            patches = spawner_inputs(index, profile) + waiting_seeds(index, row, tiles, atlas)
            initial = bytearray(1048576)
            initial[0x10000:0x10000 + len(image)] = image
            for address, raw in patches:
                initial[address:address + len(raw)] = raw
            values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                      0x1000, 0x1aa2, 0x40, 0x7000, 0x3fe4, 0x7a57, row['flags'])
            endpoints, trace, writes = [], [], []
            stop = None
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for register, value in zip(REGS, values):
                    engine.reg_write(register, value)
                def external(*unused):
                    raise ValueError('Frame prefix crossed an interrupt or hardware I/O')
                def code(uc, address, size, user):
                    nonlocal stop
                    if address in stops:
                        stop = address
                        uc.emu_stop()
                        return
                    registers = tuple(uc.reg_read(register) for register in REGS)
                    trace.append(registers)
                    coverage.add((registers[7], registers[12]))
                def write(uc, access, address, size, value, user):
                    if size not in (1, 2) or not (0x1aa20 <= address < 0x2aa20 or
                            0x70000 <= address < 0x74010 or 0xa0000 <= address < 0xb0001):
                        raise ValueError('Frame prefix wrote outside data/stack/VGA')
                    writes.append((address, size, value & ((1 << (size * 8)) - 1)))
                engine.hook_add(unicorn.UC_HOOK_INTR, external)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                engine.emu_start(0x17a57, 0 if observed else stop, count=2000000)
                registers = tuple(engine.reg_read(register) for register in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                if stop not in stops or registers[7] * 16 + registers[12] != stop:
                    raise ValueError('Frame prefix missed declared endpoint')
                if final[0x10000:0x1aa20] != image[:0xaa20]:
                    raise ValueError('Original code changed during execution')
                endpoints.append((registers, final))
            if endpoints[0] != endpoints[1]:
                raise ValueError('Observation changed complete original memory/registers')
            registers, final = endpoints[0]
            expected = bytearray(initial)
            for address, size, value in writes:
                expected[address:address + size] = value.to_bytes(size, 'little')
            if expected != final:
                raise ValueError('Ordered writes do not reconstruct complete original memory')
            trace.append(registers)
            states += len(trace)
            write_count += len(writes)
            outcome = stops[stop]
            outcomes[outcome] += 1
            output.extend(struct.pack('<II13HI13HI', index, outcome, *values, *registers))
            output.extend(struct.pack('<I', len(patches)))
            for address, raw in patches:
                output.extend(struct.pack('<II', address, len(raw)) + raw)
            output.extend(struct.pack('<I', len(trace)))
            for column in range(14):
                output.extend(struct.pack('<' + ('I' if column == 13 else 'H') * len(trace),
                    *(item[column] for item in trace)))
            output.extend(struct.pack('<I', len(writes)))
            for address, size, value in writes:
                output.extend(struct.pack('<IBH', address, size, value))
        if any(sha((root / name).read_bytes()) != pin for name, pin in pins.items()) or any(
                sha((root / 'tools' / name).read_bytes()) != pin for name, pin in dependencies.items()):
            raise ValueError('Canonical sources changed before export')
        raw = bytes(output)
        compressed = gzip.compress(raw, mtime=0)
        (out / 'oracle.bin.gz').write_bytes(compressed)
        manifest = dict(schema='lezac-controlled-post-render-prefix-v1', cases=len(waiting),
            asset_sha256=pins, dependency_sha256=dependencies, spawner_profiles=len(spawners),
            entry_ip=0x7a57, endpoint_ip=0x7ebb, active_prefix_executed=False,
            completed=outcomes[0], end_run_handoffs=outcomes[1], runtime_errors=outcomes[2],
            register_states=states, ordered_writes=write_count,
            executed_instructions=[list(pair) for pair in sorted(coverage)],
            projection_bytes=len(raw), projection_sha256=sha(raw), compressed_bytes=len(compressed),
            compressed_sha256=sha(compressed), original_code_bytes_verified=43552,
            unicorn_version=unicorn.__version__, unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True, source_bytes_rechecked_before_export=True,
            full_memory_observer_control=True, ordered_writes_reconstruct_memory=True,
            controlled_initial_memory=True, raw_memory_published=False, natural_capture=False,
            end_run_ui_executed=False, trace_arithmetic_flags_compared=False,
            endpoint_all_flags_compared=True, work_clock_claim=False, full_frame_claim=False,
            whole_game_parity=False, instruction_patches=0, calls_stubbed=0,
            interrupts_delivered=0, hardware_io=0, trace_storage='register-columns-v1',
            rep_trace_policy='raw-unicorn-transfer-and-zero-count-observations')
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print(json.dumps(dict(status='passed', cases=len(waiting), states=states, outcomes=outcomes,
                              bytes=len(raw), compressed=len(compressed), sha256=sha(raw))), flush=True)
    except BaseException as error:
        (out / 'failed.json').write_text(json.dumps(dict(status='failed', case=index, error=repr(error))) + '\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.repo.resolve(), args.out)
