"""Observe the unchanged original complete player-motion interval and helpers."""
import argparse
from collections import Counter
import gzip
import itertools
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

from actor_motion_oracle import make_case, compact_initial, SOURCES
from actor_steering_oracle import encode_trace
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA = 0x1aa20
STOPS = {0x1732c: 0, 0x192e2: 1}
FAULTS = {0x16807, 0x16874, 0x16b61, 0x16c38, 0x16ff7}


def require(yes, message):
    if not yes:
        raise ValueError(message)


def profiles():
    rows = []
    def add(family, **changes):
        row = dict(family=family, marker=1, caller=False, vx=0, vy=0, bottom=1,
            controls=(0, 0, 0, 0, 0), pickup=0, energy=100, idle=0,
            held=0, weapon=1, ammo=10, animation=1, current=1, drop=0,
            cached=(0, 0, 0, 0), cells=(0, 0, 0, 0), portal=0,
            capacity=0, score=0, flags=0x202, bp=0x3fdc, floor=0x200,
            flame_mass=1, flame_velocity=(-31, 29), seed=0x12345678,
            step_left=0, step_right=0, above=0, objective=115)
        row.update(changes)
        rows.append(row)
    for marker, bits, bottom in itertools.product((1, 2), range(32), (0, 1)):
        add('controls', marker=marker, controls=tuple((bits >> n) & 1 for n in range(5)), bottom=bottom)
    velocities = (-32768, -2048, -1025, -1024, -43, -42, -1, 0, 1, 42, 43, 1023, 1024, 32767)
    vertical = (-32768, -65, -64, -1, 0, 1, 1599, 1600, 1601, 2047, 2048, 32703, 32704, 32767)
    for vx, vy, bottom in itertools.product(velocities, vertical, (0, 1)):
        add('velocity_words', vx=vx, vy=vy, bottom=bottom, controls=(0, 1, 0, 1, 0))
    for value in range(256):
        for field in range(5):
            controls = [0] * 5
            controls[field] = value
            add('control_bytes', controls=tuple(controls), held=5)
        for pickup in range(8):
            add('pickup_energy_bytes', energy=value, pickup=pickup)
        for pickup in (5, 6):
            add('pickup_ammo_bytes', ammo=value, pickup=pickup)
        add('weapon_byte_switch', weapon=value, held=5)
        for marker, mode in itertools.product((1, 2), (0, 1)):
            add('animation_bytes', marker=marker, animation=mode, current=value, vy=1601)
        for field in range(4):
            cached = [0] * 4
            cached[field] = value
            add('cached_tile_bytes', cached=tuple(cached), controls=(0, 0, 0, 0, 1))
        add('flame_mass_bytes', cells=(117, 0, 117, 0), flame_mass=value)
    for cells, capacity in itertools.product(((0, 0, 0, 0), (1, 76, 77, 255), (103, 104, 107, 108),
            (114, 115, 103, 114), (117, 117, 117, 117)), (0, 29, 30, 255)):
        add('tile_scan_capacity', cells=cells, capacity=capacity, score=0xfffffff0)
    for marker, key, capacity in itertools.product((1, 2), (0, 1, 0x8001, 0xffff), (0, 30)):
        add('portal', marker=marker, portal=key, cached=(0, 69, 0, 0),
            controls=(0, 0, 0, 0, 1), capacity=capacity)
    for marker, bits, edges in itertools.product((1, 2), (0, 1, 2, 8, 16, 31), (0, 2)):
        add('real_caller', marker=marker, caller=True, controls=tuple((bits >> n) & 1 for n in range(5)),
            bottom=edges != 0, vx=213, vy=-1)
    for flags, bp, floor in itertools.product((0x202, 0x602), (0x700, 0x3fdc), (0x200, 65535)):
        add('stack_flags', flags=flags, bp=bp, floor=floor, pickup=6)
    for marker in (1, 2):
        add('empty_weapon_switch', marker=marker, ammo=0, held=5)
        add('down_while_airborne', marker=marker, vy=-1, controls=(0, 0, 0, 0, 1))
        add('down_existing_drop', marker=marker, drop=1, controls=(0, 0, 0, 0, 1))
        add('down_existing_pose', marker=marker, current=18 if marker == 1 else 37,
            controls=(0, 0, 0, 0, 1))
        add('down_idle_backup', marker=marker, animation=0, controls=(0, 0, 0, 0, 1))
        add('step_left', marker=marker, step_left=1, controls=(0, 1, 0, 0, 0))
        add('step_right', marker=marker, step_right=1, controls=(0, 0, 1, 0, 0))
        add('walking_inside_range', marker=marker, current=10 if marker == 1 else 29,
            controls=(0, 1, 0, 0, 0))
        add('idle_latch', marker=marker, idle=4)
        add('fire_empty', marker=marker, ammo=0, controls=(0, 0, 0, 1, 0))
        add('fire_super', marker=marker, weapon=4, controls=(0, 0, 0, 1, 0))
        add('fracture_above', marker=marker, above=0x4001, cells=(103, 0, 0, 0))
        add('objective_counter', marker=marker, objective=103, cells=(103, 0, 0, 0))
        add('backward_animation_copy', marker=marker, flags=0x602, vy=1601)
        for pickup in range(1, 7):
            add('pickup_score_carry', marker=marker, pickup=pickup, score=0xfffffff0)
    return rows


def initial_case(index, profile, image):
    row = dict(mode=5 if profile['caller'] else 0, bp=profile['bp'], floor=profile['floor'],
        flags=profile['flags'], kind=profile['marker'], behavior=profile['marker']-1,
        x=80, y=80, dx=40, dy=20, edges=2 if profile['bottom'] else 0, flag_byte=1,
        tick=49, seed=profile['seed'], ai0=0, speed=494, threshold=65535,
        left_set=1, right_set=2, vx=profile['vx'], vy=profile['vy'], width=64,
        cell=650, accumulator=0, queue=0, rectangles=0, sound_active=0,
        sound_priority=0, tiles=profile['cached'], sample_tiles=(0, 0),
        current=(0, 0), above=(0, 0), fracture=0, shape='point')
    entry, patches = make_case(index, row)
    bp = row['bp']
    marker = profile['marker']
    actor_address = DATA + 0x1b62 + marker * 38 if profile['caller'] else 0x51bd4
    def put(address, raw):
        patches.append((address, bytes(raw)))
    def data(offset, raw):
        put(DATA + offset, raw)
    def word(offset, value):
        data(offset, struct.pack('<H', value & 65535))
    def sw(offset, value):
        put(0x70000 + ((bp + offset) & 65535), struct.pack('<H', value & 65535))
    def sb(offset, value):
        put(0x70000 + ((bp + offset) & 65535), bytes((value & 255,)))
    if profile['caller']:
        actor = next(raw for address, raw in reversed(patches) if address == 0x51bd4 and len(raw) == 38)
        put(actor_address, actor)
    data(0xc22e, struct.pack('<4H', 80, 80, 0, 0))
    if not profile['caller']:
        entry = (*entry[:12], 0x6737, entry[13])
        for offset, value in ((-19, 2), (-29, marker), (-28, profile['pickup']),
                (-20, profile['current']), (-21, 18 if marker == 1 else 37),
                (-22, 19 if marker == 1 else 38), (-23, 1 if marker == 1 else 20),
                (-24, 10 if marker == 1 else 29), (-25, 17 if marker == 1 else 36),
                (-26, 2 if marker == 1 else 21), (-27, 9 if marker == 1 else 28),
                (-37, profile['step_left']), (-38, profile['step_right'])):
            sb(offset, value)
        sw(-54, 0x785a if marker == 1 else 0x7888)
        sw(-52, 0x1aa2)
    source = 0x1b78 if marker == 1 else 0x1b7d
    data(source, bytes(profile['controls']))
    data(0x1b82, bytes(profile['controls']))
    data(0x62, bytes((2, 9, 10, 17, 21, 28, 29, 36)))
    data(0x79ae, bytes((profile['pickup'] if marker == 1 else 0, profile['pickup'] if marker == 2 else 0)))
    data(0x79e6, bytes((1 if marker == 1 else 0, 1 if marker == 2 else 0)))
    data(0x79b0, bytes((profile['held'], profile['held'])))
    word(0x79bc, 0x79af + marker)
    word(0x79be, 0x1aa2)
    data(0x1b73 + marker, bytes((profile['weapon'],)))
    data(0x1b67 + marker * 4, bytes((profile['ammo'],)) * 5)
    data(0x208d, bytes((profile['capacity'],)))
    data(0xc496, bytes((2,)))
    data(0x79a5, b'\x03')
    word(0x78ba, 0)
    data(0x79a7, b'\0')
    word(0x2076, 2)
    word(0x2088, 0)
    data(0x208e, b'\0')
    data(0x79b4, bytes((profile['objective'],)))
    data(0x785a if marker == 1 else 0x7888, struct.pack('<I', profile['score']) + bytes(42))
    data(0xc322, b''.join(struct.pack('<BBH', 1, 1, 0x100 + n * 3) for n in range(256)))
    put(actor_address + 2, bytes((profile['idle'],)))
    put(actor_address + 14, struct.pack('<H', profile['drop']))
    put(actor_address + 22, bytes((profile['current'], profile['current'], profile['current'],
        1, 2, profile['animation'], 1)))
    put(actor_address + 29, bytes((20, 21, 22, 1, 2, 1, 1)))
    put(actor_address + 36, bytes((profile['energy'],)))
    cells = (715, 716, 780, 779)
    for cell, value in zip(cells, profile['cells']):
        put(0x40000 + cell, bytes((value,)))
    put(0x60000 + 2 * (cells[0] - 64), struct.pack('<H', profile['above']))
    for slot, cell in enumerate((715, 780)):
        raw = bytearray(11)
        struct.pack_into('<H', raw, 0, cell)
        raw[4:6] = bytes(v & 255 for v in profile['flame_velocity'])
        data(0x209e + slot * 11, raw)
        data(0x78d6 + slot, bytes((profile['flame_mass'],)))
    for slot, key in enumerate((1, 32767, 23), 1):
        data(0x7717 + slot * 7, struct.pack('<3HB', key, 104 + slot, 120 + slot, 0))
    put(0x60000 + 2 * (650 + 3 * 64 + 1), struct.pack('<H', profile['portal']))
    initial, seeds = compact_initial(image, patches)
    return entry, initial, seeds


def generate(root, out):
    require(unicorn.__version__ == '2.1.4' and not any(k in os.environ for k in
        ('LD_PRELOAD', 'LIBUNICORN_PATH')), 'Unsupported player oracle runtime')
    library = Path(uclib._name).resolve(strict=True)
    def mapped():
        return sha(library.read_bytes()) == LIB_SHA and any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines())
    require(mapped(), 'Actual player oracle library mapping differs')
    names = tuple(dict.fromkeys((*SOURCES, 'player_motion_oracle.py')))
    sources = {name: sha((root / 'tools' / name).read_bytes()) for name in names}
    require((root / 'tools/player_motion_oracle.py').read_bytes() == Path(__file__).read_bytes(),
        'Player producer source differs')
    exe = (root / 'LEZAC.EXE').read_bytes()
    require(sha(exe) == EXE_SHA, 'Canonical player executable differs')
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[mz[4] * 16:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + i * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
    out = out.resolve()
    require(out.is_relative_to(Path('/dev/shm')) and not out.exists(), 'Use a new RAM-only player capture')
    out.mkdir()
    rows = profiles()
    output = bytearray(b'LZPLY001' + struct.pack('<I', len(rows)))
    coverage = Counter()
    summaries = []
    try:
        for index, profile in enumerate(rows):
            entry, initial, seeds = initial_case(index, profile, image)
            endpoints, trace, writes = [], [], []
            stop = None
            fault = None
            visited = set()
            for observed in (True, False):
                engine = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_16)
                engine.mem_map(0, 1048576)
                engine.mem_write(0, bytes(initial))
                for register, value in zip(REGS, entry):
                    engine.reg_write(register, value)
                def code(uc, address, size, user):
                    nonlocal stop
                    if address in STOPS:
                        stop = address
                        uc.emu_stop()
                        return
                    r = tuple(uc.reg_read(register) for register in REGS)
                    require((r[7] == 0x1000 and r[12] < 0x83f0) or
                        (r[7] == 0x1920 and r[12] < 0x1820) or
                        (r[7] == 0x18ac and 0x517 <= r[12] < 0x5da),
                        'Player left declared original code: ' + str((r[7], r[12])))
                    visited.add(address)
                    trace.append(r)
                def write(uc, access, address, size, value, user):
                    require(size in (1, 2) and DATA <= address and address + size <= 0xb0001,
                        'Player write left declared data/stack/VGA owners')
                    writes.append((address, size, value & ((1 << (size * 8)) - 1)))
                def intr(uc, number, user):
                    nonlocal fault
                    address = uc.reg_read(REGS[7]) * 16 + uc.reg_read(REGS[12])
                    require(number == 0 and address in FAULTS, 'Unexpected original player interrupt')
                    fault = address
                    uc.emu_stop()
                def io(*unused):
                    raise ValueError('Original player attempted hardware I/O')
                engine.hook_add(unicorn.UC_HOOK_INTR, intr)
                engine.hook_add(unicorn.UC_HOOK_INSN, io, None, 1, 0, UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN, io, None, 1, 0, UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE, code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                engine.emu_start(entry[7] * 16 + entry[12], 0 if observed else (stop or 0), count=3000000)
                r = tuple(engine.reg_read(register) for register in REGS)
                final = bytes(engine.mem_read(0, 1048576))
                require((r[7] * 16 + r[12] in STOPS or fault is not None) and
                    final[0x10000:DATA] == image[:0xaa20], 'Original player endpoint/code differs')
                endpoints.append((r, final, fault))
                del engine
            require(endpoints[0] == endpoints[1], 'Player observer changed complete memory/registers')
            endpoint, final, fault = endpoints[0]
            rebuilt = bytearray(initial)
            for address, size, value in writes:
                rebuilt[address:address + size] = value.to_bytes(size, 'little')
            require(rebuilt == final, 'Player ordered writes do not reconstruct memory')
            trace.append(endpoint)
            outcome = 2 if fault is not None else STOPS[endpoint[7] * 16 + endpoint[12]]
            if profile['caller']:
                require({0x17f59, 0x16053, 0x16737}.issubset(visited),
                    'Declared player caller did not execute its actual CALL, body and motion')
            output.extend(struct.pack('<IB13HI13HI', index, outcome, *entry, *endpoint))
            output.extend(struct.pack('<I', len(seeds)))
            for address, raw in seeds:
                output.extend(struct.pack('<II', address, len(raw)) + raw)
            encode_trace(output, trace)
            output.extend(struct.pack('<I', len(writes)))
            for item in writes:
                output.extend(struct.pack('<IBH', *item))
            output.extend(struct.pack('<I', 0))
            coverage.update(cases=1, register_states=len(trace), ordered_writes=len(writes),
                actual_callers=int(0x17f59 in visited))
            coverage['outcome_' + str(outcome)] += 1
            summaries.append(dict(index=index, profile=profile, outcome=outcome, visited=sorted(visited)))
            if index % 100 == 0:
                print('player_motion_capture=' + str(index + 1) + '/' + str(len(rows)), flush=True)
        require(all(sha((root / 'tools' / name).read_bytes()) == value for name, value in sources.items()) and
            sha((root / 'LEZAC.EXE').read_bytes()) == EXE_SHA and mapped(), 'Player producer inputs changed')
        sites = {address for row in summaries for address in row['visited']}
        player_sites = {address for address in sites if 0x16737 <= address < 0x17018 or
            0x15715 <= address < 0x15740 or 0x15999 <= address < 0x15a75}
        coverage['original_player_instruction_sites'] = len(player_sites)
        require(len(player_sites) == 899, 'Original player instruction-site coverage incomplete')
        raw = bytes(output)
        packed = gzip.compress(raw, mtime=0)
        (out / 'oracle.bin.gz').write_bytes(packed)
        manifest = dict(schema='lezac-controlled-player-motion-v1', coverage=dict(coverage),
            asset_sha256={'LEZAC.EXE': EXE_SHA}, source_sha256=sources, projection_bytes=len(raw),
            projection_sha256=sha(raw), compressed_bytes=len(packed), compressed_sha256=sha(packed),
            unicorn_version=unicorn.__version__, unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True, original_code_bytes_verified=43552,
            complete_memory_observer_control=True, ordered_writes_reconstruct_memory=True,
            instruction_patches=0, calls_stubbed=0, hardware_io=0, interrupts_delivered=0,
            later_state_injected=False, production_app_comparison=False, natural_capture=False,
            full_frame_claim=False, raw_memory_published=False)
        (out / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        (out / 'checkpoints.json').write_text(json.dumps(summaries, sort_keys=True, indent=2) + '\n')
        print(json.dumps(manifest, sort_keys=True), flush=True)
    except Exception as error:
        failure = dict(index=index, profile=profile, error=str(error))
        if 'engine' in locals():
            failure['registers'] = [engine.reg_read(register) for register in REGS]
            (out / 'failed-ram.bin').write_bytes(engine.mem_read(0, 1048576))
        (out / 'failed.json').write_text(json.dumps(failure, indent=2) + '\n')
        (out / 'partial-corpus.bin').write_bytes(output)
        (out / 'producer-at-failure.py').write_bytes(Path(__file__).read_bytes())
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    generate(args.root, args.out)
