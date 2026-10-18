"""Execute unchanged 7C3D..7EBB and real HUD/clear/player-start callees."""
import argparse
import gzip
import itertools
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

from ammo_hud_oracle import ASSET_SHA, sprites
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha


def profiles():
    rows = []
    def add(**changes):
        i = len(rows)
        row = dict(states=(2, 2), actors=(2, 2), timers=(2, 2), reserves=(2, 2),
            fire=(0, 0), gate=1, dirty=(0, 0), selected=(i % 4 + 1, (i + 1) % 4 + 1),
            ammo=(i & 255, (i * 13) & 255), positions=((24, 40), (80, 40)),
            tiles=((0, 1), (76, 0)), active=2, floor=0x200,
            flags=0x602 if i % 7 == 0 else 0x202)
        row.update(changes)
        rows.append(row)
    for first, second, actors, gate in itertools.product(range(4), range(4), range(4), range(2)):
        i = len(rows)
        add(states=(first, second), actors=tuple(2 if actors & (1 << p) else 0 for p in range(2)),
            gate=gate, timers=tuple((0, 1, 2, 65535)[(i + p) % 4] for p in range(2)),
            reserves=tuple((0, 1, 2, 255)[(i // 2 + p) % 4] for p in range(2)),
            fire=tuple((0, 1, 2, 255)[(i + p * 3) % 4] for p in range(2)),
            dirty=tuple((0, 1, 2, 255)[(i // 3 + p) % 4] for p in range(2)),
            positions=(((0, 24, 65535)[i % 3], (0, 24, 25, 40, 65535)[i % 5]), (80, 40)))
    for first, second, gate in itertools.product((0, 1, 2, 255), (0, 1, 2, 255), range(2)):
        add(fire=(first, second), gate=gate, timers=(1, 2))
    for gate, direction in itertools.product(range(2), (0x202, 0x602)):
        add(fire=(1, 1), timers=(1, 1), gate=gate, flags=direction)
    for selected, ammo, dirty in itertools.product(range(4), (0, 1, 99, 100, 255), (1, 2)):
        add(states=(1, 1), actors=(0, 0), selected=(selected + 1, (selected + 1) % 4 + 1),
            ammo=(ammo, ammo), dirty=(dirty, dirty))
    for player, reserve, active in itertools.product(range(2), (0, 1, 255), (1, 2)):
        add(states=tuple(2 if p == player else 0 for p in range(2)),
            actors=tuple(2 if p == player else 0 for p in range(2)),
            timers=(1, 1), reserves=(reserve, reserve), active=active)
    for mode, direction in itertools.product(range(3), (0x202, 0x602)):
        add(states=(1, 0) if mode == 0 else (2, 0), actors=(0, 0) if mode == 0 else (2, 0),
            timers=(1, 2), reserves=(0, 2) if mode == 1 else (2, 2),
            dirty=(2, 0) if mode == 0 else (0, 0), floor=65535, flags=direction)
    for ammo, direction in itertools.product((0, 1, 2, 9, 10, 99, 100, 255), (0x202, 0x602)):
        add(timers=(1, 1), ammo=(ammo, ammo), reserves=(1, 1), flags=direction)
    return rows


def seeds(index, row, tiles, atlas):
    result = []
    def put(address, raw):
        result.append((address, raw))
    def data(offset, raw):
        put(0x1aa20 + offset, raw)
    def word(offset, value):
        data(offset, struct.pack('<H', value))
    put(0x73f00, bytes((i * 29 + index * 7 + 11) & 255 for i in range(256)))
    put(0x40000, bytes(65536))
    word(0xc1e0, 0)
    word(0xc1e2, 0x4000)
    word(0xc204, 60)
    word(0x1afa, row['floor'])
    word(0xc208, 0x4000)
    data(0x4000, tiles[:116 * 64])
    word(0x2070, 0x9000)
    data(0x9000, tiles[121 * 64:131 * 64])
    word(0xc1fa, 0x5000)
    word(0xc3c0, 0x5aa5)
    word(0x2072, 0xa55a)
    word(0x2074, 0x5aa5)
    word(0x2082, 0x7f3d)
    word(0x78cc, 65532)
    data(0x661e, bytes(((index * 13) & 255,)))
    data(0x79a3, bytes(((index * 31 + 18) & 255,)))
    data(0x79b8, bytes((row['active'], 13)))
    data(0x79ca, bytes((row['gate'],)))
    data(0x79a5, bytes((0 if index % 5 == 0 else 3,)))
    for p, marker in enumerate((3 if index % 3 else 0, 1, 2), 1):
        data(0x7717 + p * 7, struct.pack('<HHHB', p * 9, 32 * p, 41 + p, marker))
    for player in range(2):
        actor = bytearray((index + i * 17 + player) & 255 for i in range(38))
        actor[1] = player
        actor[21] = row['actors'][player]
        struct.pack_into('<H', actor, 16, row['timers'][player])
        data(0x1b88 + player * 38, actor)
        x, y = row['positions'][player]
        data(0xc21e + player * 8, struct.pack('<HHBBH', x, y, 128 + player, 64 + player, 0xa55a))
        data(0x79e6 + player, bytes((row['states'][player],)))
        data(0x79ea + player, bytes((row['reserves'][player],)))
        word(0x79f4 + player * 2, player * 180)
        data(0x1b7b + player * 5, bytes((row['fire'][player],)))
        data(0x1b76 + player, bytes((row['dirty'][player],)))
        data(0x1b74 + player, bytes((row['selected'][player],)))
        data(0x1b6c + player * 4, bytes((row['ammo'][player],) * 4))
        cell = (((((y + 7) & 65535) >> 3) + 1) * 60 + (x >> 3)) & 65535
        for offset, value in enumerate(row['tiles'][player]):
            put(0x40000 + ((cell + offset) & 65535), bytes((value,)))
    for selected in range(4):
        width, height, pixels = atlas[57 + selected]
        source = 0x2000 + selected * 1024
        data(0xc322 + (58 + selected) * 4, struct.pack('<BBH', width, height, source))
        put(0x50000 + source, pixels)
    return result


def generate(root, out):
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only output directory')
    out.mkdir()
    index = None
    try:
        dependencies = {name: sha((root / 'tools' / name).read_bytes()) for name in
            ('frame_waiting_oracle.py', 'ammo_hud_oracle.py', 'frame_camera_oracle.py')}
        if unicorn.__version__ != '2.1.4' or any(k in os.environ for k in ('LD_PRELOAD', 'LIBUNICORN_PATH')):
            raise ValueError('Unsupported original oracle loader')
        library = Path(uclib._name).resolve(strict=True)
        if sha(library.read_bytes()) != LIB_SHA or not any(
                line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
            raise ValueError('Actual oracle library mapping differs')
        pins = dict(ASSET_SHA, **{'LEZAC.EXE': EXE_SHA})
        raw_assets = {name: (root / name).read_bytes() for name in pins}
        if any(sha(raw_assets[name]) != pin for name, pin in pins.items()):
            raise ValueError('Original canonical asset differs')
        exe = raw_assets['LEZAC.EXE']
        tiles = raw_assets['CARO.CAR'][2:]
        atlas = sprites(raw_assets['BOMOMIMK.SPR'])
        mz = struct.unpack_from('<14H', exe)
        image = bytearray(exe[mz[4] * 16:])
        for i in range(mz[3]):
            offset, segment = struct.unpack_from('<HH', exe, mz[12] + i * 4)
            at = segment * 16 + offset
            struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
        cases = profiles()
        output = bytearray(b'LZWAIT01' + struct.pack('<I', len(cases)))
        stops = {0x17ebb: 0, 0x11b14: 1, 0x192e2: 2}
        coverage, states, write_total = set(), 0, 0
        outcomes = [0, 0, 0]
        for index, row in enumerate(cases):
            initial = bytearray(1048576)
            initial[0x10000:0x10000 + len(image)] = image
            patches = seeds(index, row, tiles, atlas)
            for address, raw in patches:
                initial[address:address + len(raw)] = raw
            values = (0xa55a, 0x1234, 0x5678, 0xabcd, 0x1357, 0x2468, 0x3ffe,
                      0x1000, 0x1aa2, 0x40, 0x7000, 0x3fe4, 0x7c3d, row['flags'])
            endpoints, trace, writes = [], [], []
            stop = None
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for register, value in zip(REGS, values):
                    engine.reg_write(register, value)
                def external(*unused):
                    raise ValueError('Waiting prepass crossed an interrupt or hardware I/O')
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
                        raise ValueError('Waiting prepass wrote outside data/stack/VGA')
                    writes.append((address, size, value & ((1 << (size * 8)) - 1)))
                engine.hook_add(unicorn.UC_HOOK_INTR, external)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, external, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                engine.emu_start(0x17c3d, 0 if observed else stop, count=2000000)
                registers = tuple(engine.reg_read(register) for register in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                if stop not in stops or registers[7] * 16 + registers[12] != stop:
                    raise ValueError('Waiting prepass missed declared endpoint')
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
            write_total += len(writes)
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
        manifest = dict(schema='lezac-controlled-waiting-frame-v1', cases=len(cases),
            weapon_selection_values=[1, 2, 3, 4], descriptor_indexing='one-based', inventory_bases=[0x1b6c, 0x1b70],
            completed=outcomes[0], end_run_handoffs=outcomes[1], runtime_errors=outcomes[2],
            asset_sha256=pins, dependency_sha256=dependencies,
            unicorn_version=unicorn.__version__, unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True, full_memory_observer_control=True,
            ordered_writes_reconstruct_memory=True, original_code_bytes_verified=43552,
            register_states=states, ordered_writes=write_total,
            executed_instructions=[list(pair) for pair in sorted(coverage)],
            projection_bytes=len(raw), projection_sha256=sha(raw), compressed_bytes=len(compressed),
            compressed_sha256=sha(compressed), trace_storage='register-columns-v1',
            rep_trace_policy='raw-unicorn-transfer-and-zero-count-observations',
            trace_arithmetic_flags_compared=False, endpoint_all_flags_compared=True,
            raw_memory_published=False, controlled_initial_memory=True, natural_capture=False,
            source_bytes_rechecked_before_export=True, end_run_ui_executed=False,
            instruction_patches=0, calls_stubbed=0, interrupts_delivered=0, hardware_io=0,
            work_clock_claim=False, full_frame_claim=False, whole_game_parity=False)
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print(json.dumps(dict(status='passed', cases=len(cases), states=states, writes=write_total,
            outcomes=outcomes, bytes=len(raw), compressed=len(compressed), sha256=sha(raw))), flush=True)
    except Exception as error:
        (out / 'failed.json').write_text(json.dumps(dict(status='failed', case=index, error=str(error))) + '\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    generate(arguments.repo.resolve(), arguments.out)
