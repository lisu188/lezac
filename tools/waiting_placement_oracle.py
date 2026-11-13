"""Observe the unchanged complete no-expiry waiting prepass on controlled map views."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT


def cell(x, y):
    return ((((y + 7) & 65535) >> 3) + 1) * 60 + (x >> 3) & 65535


def profiles():
    result = []
    pairs = [(0, 0), (1, 0), (76, 0), (77, 1), (0, 1), (0, 76), (0, 77), (255, 76)]
    for x in (0, 24, 65535):
        for y in (0, 24, 25, 40, 65535, 3000, 8703):
            for left, right in pairs:
                result.append((0, 1 + len(result) % 2, x, y, left, right))
    for mode, targets in ((1, (1980, 1994)), (2, (2000, 2001)), (3, (1997, 1998))):
        for target in targets:
            x, y = target % 60 * 8, (target // 60 - 1) * 8
            assert cell(x, y) == target
            for mask in (1, 2, 3):
                for left, right in pairs:
                    result.append((mode, mask, x, y, left, right))
    result.extend((0, 0, 24, 40, left, right) for left, right in pairs)
    return result


def generate(root, out):
    if unicorn.__version__ != '2.1.4' or any(k in os.environ for k in ('LD_PRELOAD', 'LIBUNICORN_PATH')):
        raise ValueError('Unsupported original oracle loader')
    library = Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes()) != LIB_SHA or not any(
            line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual oracle library mapping differs')
    exe = (root / 'LEZAC.EXE').read_bytes()
    if sha(exe) != EXE_SHA:
        raise ValueError('Original executable differs')
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[mz[4] * 16:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + i * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output directory')
    out.mkdir()
    cases, coverage, reads = profiles(), set(), 0
    output = bytearray(b'LZWMAP01' + struct.pack('<I', len(cases)))
    try:
        for index, (mode, mask, x, y, left, right) in enumerate(cases):
            encoding, gate = index // 2 % 2, index % 2
            positions = [(x, y) if mask == 1 else (24, 40), (x, y) if mask & 2 else (80, 40)]
            initial = bytearray(1048576)
            initial[0x10000:0x10000 + len(image)] = image
            initial[0x40000:0x50000] = bytes(65536)
            for player, (px, py) in enumerate(positions):
                actor = 0x1aa20 + 0x1b88 + player * 38
                initial[actor:actor + 38] = bytes(38)
                initial[actor + 1] = player
                initial[actor + 21] = 2 if mask & (1 << player) else 0
                struct.pack_into('<H', initial, actor + 16, 65535 if mask & (1 << player) else 0)
                struct.pack_into('<HH', initial, 0x1aa20 + 0xc21e + player * 8, px, py)
                initial[0x1aa20 + 0x79e6 + player] = 2 if mask & (1 << player) else 0
                if mask & (1 << player):
                    at = cell(px, py)
                    initial[0x40000 + at] = left
                    initial[0x40000 + ((at + 1) & 65535)] = right
            initial[0x1aa20 + 0x1b76:0x1aa20 + 0x1b78] = bytes(2)
            initial[0x1aa20 + 0x1b7b] = initial[0x1aa20 + 0x1b80] = 0
            initial[0x1aa20 + 0x79ca] = gate
            initial[0x1aa20 + 0x79b9] = 0
            struct.pack_into('<H', initial, 0x1aa20 + 0xc204, 60)
            struct.pack_into('<HH', initial, 0x1aa20 + 0xc1e0, 0, 0x4000)
            struct.pack_into('<H', initial, 0x1aa20 + 0x2074, 0x5aa5)
            values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                      0x1000, 0x1aa2, 0x40, 0x7000, 0x3fe4, 0x7c3d, 0x202)
            endpoints = []
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for reg, value in zip(REGS, values):
                    engine.reg_write(reg, value)
                def external(*unused):
                    raise ValueError('Waiting prepass crossed an interrupt or hardware I/O')
                def code(uc, address, size, user):
                    if not 0x17c3d <= address < 0x17ebb:
                        raise ValueError('Controlled prepass unexpectedly called another routine')
                    coverage.add(address - 0x10000)
                def read(uc, access, address, size, value, user):
                    nonlocal reads
                    if size != 1 or uc.reg_read(REGS[12]) not in (0x7e2e, 0x7e3d, 0x7e4d, 0x7e5d):
                        raise ValueError('Unexpected physical object-plane read')
                    reads += 1
                engine.hook_add(unicorn.UC_HOOK_INTR, external)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_READ, read, None, 0x40000, 0x4ffff)
                engine.emu_start(0x17c3d, 0x17ebb, count=20000)
                registers = tuple(engine.reg_read(reg) for reg in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                if registers[7] != 0x1000 or registers[12] != 0x7ebb or final[0x10000:0x1aa20] != image[:0xaa20]:
                    raise ValueError('Original endpoint/code identity differs')
                if final[0x40000:0x50000] != initial[0x40000:0x50000]:
                    raise ValueError('Waiting prepass unexpectedly changed its map')
                endpoints.append((registers, final))
            if endpoints[0] != endpoints[1]:
                raise ValueError('Observation changed complete original memory/registers')
            final = endpoints[0][1]
            ys = [struct.unpack_from('<H', final, 0x1aa20 + 0xc220 + p * 8)[0] for p in range(2)]
            timers = [struct.unpack_from('<H', final, 0x1aa20 + 0x1b98 + p * 38)[0] for p in range(2)]
            cursor = struct.unpack_from('<H', final, 0x1aa20 + 0x2074)[0]
            states = struct.unpack_from('<H', final, 0x1aa20 + 0x79e6)[0]
            fallback = final[0x1aa20 + 0x79b9]
            output.extend(struct.pack('<18H', index, mode, mask, encoding, gate, *positions[0], *positions[1],
                                      left, right, *ys, cursor, *timers, states, fallback))
        raw = bytes(output)
        (out / 'oracle.bin').write_bytes(raw)
        manifest = dict(schema='lezac-controlled-waiting-map-v1', cases=len(cases),
            executable_sha256=EXE_SHA, producer_sha256=sha(Path(__file__).read_bytes()),
            shared_oracle_sha256=sha(Path(__file__).with_name('frame_camera_oracle.py').read_bytes()),
            unicorn_version=unicorn.__version__, unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True, complete_memory_observer_control=True,
            original_code_bytes_verified=43552, original_instruction_offsets=sorted(coverage), map_reads=reads,
            projection_bytes=len(raw), projection_sha256=sha(raw), controlled_input=True,
            map_pointer='normalized 4000:0000 object view', natural_heap_initialization_proven=False,
            instruction_patches=0, calls_stubbed=0, interrupts_delivered=0, hardware_io=0,
            raw_memory_published=False, no_expiry_path_only=True, full_frame_claim=False,
            production_app_comparison=False, whole_game_parity=False)
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print(json.dumps(dict(status='passed', cases=len(cases), bytes=len(raw), map_reads=reads, sha256=sha(raw))), flush=True)
    except Exception as error:
        (out / 'failed.json').write_text(json.dumps(dict(status='failed', case=index, error=str(error))) + '\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.repo.resolve(), args.out)
