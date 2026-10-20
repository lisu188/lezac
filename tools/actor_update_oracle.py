"""Observe complete original player/nonplayer calls through their real RET 4."""
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

import actor_motion_oracle as motion
import nonplayer_loop_oracle as loop
import player_motion_oracle as player
from actor_steering_oracle import encode_trace
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA = 0x1aa20
STOPS = {0x17ee4: 0, 0x17f5c: 0, 0x192e2: 1}
FAULTS = motion.FAULTS | player.FAULTS
SOURCES = tuple(dict.fromkeys((*motion.SOURCES, 'player_motion_oracle.py',
    'nonplayer_loop_oracle.py', 'actor_update_oracle.py')))


def require(yes, message):
    if not yes:
        raise ValueError(message)


def profiles():
    rows = [('player_direct', row) for row in player.profiles()]
    rows += [('player_caller', row) for row in player.profiles() if row['caller']]
    rows += [('nonplayer', row) for row in motion.profiles() if row['mode'] >= 4]
    base = dict(count=1, states=(1, 1), behavior=5, expiry='none', dx=40, dy=20,
        dx2=-30, dy2=-30, sp=0x3fe4, flags=0x202, floor=0x200, period=24)
    for behavior, expiry, flags, sp in itertools.product((5, 6), ('none', 'first'),
            (0x202, 0x602), (0x1fe4, 0x3fe4)):
        rows.append(('expiry', dict(base, behavior=behavior, expiry=expiry, flags=flags, sp=sp)))
    for flags in (0x202, 0x602):
        rows.append(('stack_error', dict(base, floor=65535, flags=flags)))
        rows.append(('divide_error', dict(base, behavior=4, period=0, flags=flags)))
    for marker, flags, family in itertools.product((1, 2), (0x202, 0x602),
            ('player_direct', 'player_caller')):
        rows.append((family, dict(player.profiles()[0], marker=marker, flags=flags,
            animation=3, current=2, initial_animation_copy=True)))
    return rows


def initial_case(index, family, profile, image):
    if family.startswith('player'):
        entry, initial, seeds = player.initial_case(index, dict(profile, caller=True), image)
        if profile.get('initial_animation_copy'):
            # Expire the mode-3 frame timer before entry, triggering the real Move.
            timer = DATA + 0x1b62 + profile['marker'] * 38 + 25
            initial, seeds = motion.compact_initial(image, [*seeds, (timer, b'\x02')])
        if family == 'player_direct':
            sp = (entry[11] - 6) & 65535
            arguments = struct.pack('<3H', 0x7f5c, 0x1b62 + profile['marker'] * 38, 0x1aa2)
            initial, seeds = motion.compact_initial(image, [*seeds, (0x70000 + sp, arguments)])
            entry = (*entry[:11], sp, 0x6053, entry[13])
        return entry, initial, seeds
    if family == 'nonplayer':
        entry, patches = motion.make_case(index, profile)
        initial, seeds = motion.compact_initial(image, patches)
        return entry, initial, seeds
    return loop.initial_case(index, profile, image)


def generate(root, out):
    require(unicorn.__version__ == '2.1.4' and not any(key in os.environ for key in
        ('LD_PRELOAD', 'LIBUNICORN_PATH')), 'Unsupported complete actor oracle runtime')
    library = Path(uclib._name).resolve(strict=True)
    def mapped():
        return sha(library.read_bytes()) == LIB_SHA and any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines())
    require(mapped(), 'Actual complete actor library mapping differs')
    sources = {name: sha((root / 'tools' / name).read_bytes()) for name in SOURCES}
    require((root / 'tools/actor_update_oracle.py').read_bytes() == Path(__file__).read_bytes(),
        'Complete actor producer differs')
    exe = (root / 'LEZAC.EXE').read_bytes()
    require(sha(exe) == EXE_SHA, 'Canonical complete actor executable differs')
    mz = struct.unpack_from('<14H', exe)
    image = bytearray(exe[mz[4] * 16:])
    for i in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + i * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + 0x1000) & 65535)
    out = out.resolve()
    require(out.is_relative_to(Path('/dev/shm')) and not out.exists(), 'Use a new RAM-only actor capture')
    out.mkdir()
    rows = profiles()
    output = bytearray(b'LZACT001' + struct.pack('<I', len(rows)))
    coverage, summaries = Counter(), []
    try:
        for index, (family, profile) in enumerate(rows):
            entry, initial, seeds = initial_case(index, family, profile, image)
            trace, writes, visited, endpoints = [], [], set(), []
            stop, fault = None, None
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
                        'Complete actor left declared code: ' + str((r[7], r[12])))
                    visited.add(address)
                    trace.append(r)
                def write(uc, access, address, size, value, user):
                    require(size in (1, 2) and DATA <= address and address + size <= 0xb0001,
                        'Complete actor write left declared owners')
                    writes.append((address, size, value & ((1 << (size * 8)) - 1)))
                def intr(uc, number, user):
                    nonlocal fault
                    address = uc.reg_read(REGS[7]) * 16 + uc.reg_read(REGS[12])
                    require(number == 0 and address in FAULTS, 'Unexpected complete actor interrupt')
                    fault = address
                    uc.emu_stop()
                def io(*unused):
                    raise ValueError('Complete actor attempted hardware I/O')
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
                    final[0x10000:DATA] == image[:0xaa20], 'Complete actor endpoint/code differs')
                endpoints.append((r, final, fault))
                del engine
            require(endpoints[0] == endpoints[1], 'Complete actor observer changed memory/registers')
            endpoint, final, fault = endpoints[0]
            outcome = 2 if fault is not None else STOPS[endpoint[7] * 16 + endpoint[12]]
            if outcome == 0:
                require(trace[-1][7] == 0x1000 and trace[-1][12] == 0x7780,
                    'Complete actor endpoint omitted actual RET 4')
                caller_sp = entry[11] if entry[12] == 0x7ebb else (entry[11] + 6) & 65535
                require(endpoint[10] == entry[10] and endpoint[11] == caller_sp and endpoint[6] == entry[6],
                    'Complete actor failed to restore SS/SP/BP')
            if entry[12] == 0x7ebb and outcome == 0:
                call = 0x17f59 if family == 'player_caller' else 0x17ee1
                require({call, 0x16053, 0x17780}.issubset(visited), 'Actual actor CALL/RET missing')
            rebuilt = bytearray(initial)
            for address, size, value in writes:
                rebuilt[address:address + size] = value.to_bytes(size, 'little')
            require(rebuilt == final, 'Complete actor writes do not reconstruct memory')
            trace.append(endpoint)
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
                actual_player_calls=int(0x17f59 in visited), actual_nonplayer_calls=int(0x17ee1 in visited),
                player_paths=int(0x16737 in visited), expiry_paths=int(0x165a8 in visited),
                animation_copy_paths=int(0x19b1f in visited),
                actual_returns=int(outcome == 0))
            coverage['outcome_' + str(outcome)] += 1
            summaries.append(dict(index=index, family=family, profile=profile, outcome=outcome, visited=sorted(visited)))
            if index % 100 == 0:
                print('actor_update_capture=' + str(index + 1) + '/' + str(len(rows)), flush=True)
        require(mapped() and sha((root / 'LEZAC.EXE').read_bytes()) == EXE_SHA and
            all(sha((root / 'tools' / name).read_bytes()) == value for name, value in sources.items()),
            'Complete actor capture inputs changed')
        require(coverage['animation_copy_paths'] == 8, 'Original animation-copy path coverage incomplete')
        raw = bytes(output)
        packed = gzip.compress(raw, mtime=0)
        (out / 'oracle.bin.gz').write_bytes(packed)
        manifest = dict(schema='lezac-controlled-actor-update-v1', coverage=dict(coverage),
            asset_sha256={'LEZAC.EXE': EXE_SHA}, source_sha256=sources,
            projection_bytes=len(raw), projection_sha256=sha(raw), compressed_bytes=len(packed),
            compressed_sha256=sha(packed), unicorn_version=unicorn.__version__,
            unicorn_library_sha256=LIB_SHA, actual_library_mapping_verified=True,
            original_code_bytes_verified=43552, complete_memory_observer_control=True,
            ordered_writes_reconstruct_memory=True, instruction_patches=0, calls_stubbed=0,
            hardware_io=0, interrupts_delivered=0, later_state_injected=False,
            production_app_comparison=False, natural_capture=False, full_frame_claim=False, raw_memory_published=False)
        (out / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        (out / 'checkpoints.json').write_text(json.dumps(summaries, sort_keys=True, indent=2) + '\n')
        print(json.dumps(manifest, sort_keys=True), flush=True)
    except Exception as error:
        failure = dict(index=index, family=family, profile=profile, error=str(error))
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
