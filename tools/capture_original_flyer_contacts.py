"""Observe seeded behavior-4 terrain, steering and 8.8 motion in silent DOSBox."""
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import time

import capture_original_behavior4_targets as base
import capture_original_death_transients as actors
import seed_original_level as seeder

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ((0x7EC5, bytes.fromhex('c70682200100')),
         (0x7062, bytes.fromhex('803e552001')),
         (0x741E, bytes.fromhex('807ef101')))
FLOOR = bytes.fromhex('803e552001720d803e55204c7706c646e201eb18803e562001720d803e56204c7706c646e201eb04c646e200807ee200740b807ede00740531c08946f2807ee2007414837ef2007e0e8b46f2f7d899b90200f7f98946f2')
COMMON = bytes.fromhex('807ede00740b837ef2007d05c746f20100807edd00740b807edc00740531c08946f4807edd007406837ef4007c0c807edc007422837ef4007e1c8b46f4f7d899b90200f7f98946f4837ef4007d05ff4ed4eb03ff46d48b46f230ff3d00007d02b7ff8a5eef00c3885eef88e088fc1146d28b46f430ff3d00007d02b7ff8a5eef8a5ef000c3885ef088e088fc1146d4')
WINDOWS = dict(HOOKS) | {
    0x7062: FLOOR, 0x738F: COMMON,
    0x70D7: bytes.fromhex('a1c27831d2f736e8c19209c0756a'),
    0x712B: bytes.fromhex('a17420d1e0509aa8132009'),
    0x713D: bytes.fromhex('a17420d1e0509aa8132009'),
}
RELOCATIONS = {0x7134, 0x7146}
DEPENDENCIES = {
    'capture_original_behavior4_targets.py': 'a99a7f81c19720f44e794807c35c2b326dd5cdedfea79d01ee63eeab3d421ed8',
    'capture_original_death_transients.py': 'a0fddeb9c3ce6426641739ac7bd558a4e7d253670df28ec1c8aead652b3e0ba9',
}


def cases():
    rows = []
    def add(kind, mask, glyph, vx, vy, mode=0):
        rows.append({'index': len(rows), 'kind': kind, 'mask': mask, 'glyph': glyph,
                     'vx': vx, 'vy': vy, 'frac_x': 165, 'frac_y': 90,
                     'mode': mode, 'frame': 421 if mode == 0 else 420,
                     'ai0': 14, 'ai1': 271, 'ai2': 75})
    for kind in range(1, 9):
        for mask in (0, 1, 2, 3, 4, 8, 12, 15):
            add(kind, mask, 1, -513 if mask & 1 else 513, -513 if mask & 4 else 513)
    for glyph in (0, 1, 0x4C, 0x4D, 0x52, 0x53, 0x75, 0xFF):
        for mask in (1, 2, 4, 8, 12, 15):
            add(2, mask, glyph, -513 if mask & 1 else 513, -513 if mask & 4 else 513)
    for kind in range(1, 9):
        for vx in (-32768, -32767, -1, 32767):
            add(kind, 1 if vx < 0 else 2, 1, vx, 257)
    for mode in (1, 2):
        for mask in range(16):
            add(2, mask, 1, -513, 513, mode)
    return tuple(rows)


CASES = cases()


def trampoline(stage, image):
    plain = actors.trampoline(stage, image)
    entry, raw = HOOKS[stage - 1]
    target = base.SCRATCH_START + (stage - 1) * base.TRAMPOLINE_STRIDE
    body = plain[2:-(2 + len(raw) + 3)]
    code = bytearray(base.preserve_stack(False) + b'\x9c\x60')
    if stage in (2, 3):
        guard = len(code)
        code += bytes.fromhex('817e04d41b7500807ecf047500')
        end = len(code) + len(body)
        code[guard + 6] = end - (guard + 7)
        code[guard + 12] = end - (guard + 13)
    code += body + b'\x61\x9d' + base.preserve_stack(True) + raw
    code += base.jump(target + len(code), entry + len(raw))
    if len(code) > base.TRAMPOLINE_STRIDE or target + len(code) > base.GATE:
        raise RuntimeError('flyer trampoline exceeds verified scratch extent')
    return bytes(code)


def runtime_windows(load_segment):
    windows = dict(WINDOWS)
    for entry in (0x712B, 0x713D):
        raw = bytearray(windows[entry])
        segment = struct.unpack_from('<H', raw, 9)[0]
        struct.pack_into('<H', raw, 9, (segment + load_segment) & 0xFFFF)
        windows[entry] = bytes(raw)
    return windows


def self_check():
    exe = (ROOT / 'LEZAC.EXE').read_bytes()
    if hashlib.sha256(exe).hexdigest() != base.EXE_SHA:
        raise RuntimeError('original executable differs')
    if exe[:2] != b'MZ' or struct.unpack_from('<H', exe, 8)[0] * 16 != 0x770:
        raise RuntimeError('original MZ extent differs')
    image = exe[0x770:]
    for name, digest in DEPENDENCIES.items():
        if base.sha(ROOT / 'tools' / name) != digest:
            raise RuntimeError(f'capture dependency differs: {name}')
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f'original flyer window differs at {at:04x}')
    count, table = struct.unpack_from('<H', exe, 6)[0], struct.unpack_from('<H', exe, 24)[0]
    relocations = {segment * 16 + offset for offset, segment in
                   (struct.unpack_from('<HH', exe, table + index * 4) for index in range(count))}
    affected = {at for at in relocations for entry, raw in WINDOWS.items() if entry <= at < entry + len(raw)}
    if affected != RELOCATIONS:
        raise RuntimeError('flyer relocation set differs')
    actors.HOOKS = tuple((at, len(raw)) for at, raw in HOOKS)
    actors.SCRATCH = base.GATE
    for stage in (1, 2, 3):
        trampoline(stage, image)
    print(f'flyer_contacts_self_check=ok cases={len(CASES)} kinds=1..8 live=0', flush=True)
    return image


def capture(pid, location, output, image, window, load_segment, retain_writeback=False):
    cs, ds = location + (actors.CS << 4), location + (seeder.RUNTIME_DS << 4)
    installed, observations, pulses = [], [], []
    sequence = 0
    memory_base = cs - (load_segment << 4)
    with open(f'/proc/{pid}/mem', 'r+b', buffering=0) as mem:
        def read(at, size):
            data = os.pread(mem.fileno(), size, at)
            if len(data) != size:
                raise RuntimeError('short owned-child read')
            return data

        def write(at, data):
            if os.pwrite(mem.fileno(), data, at) != len(data):
                raise RuntimeError('short owned-child write')

        def stop():
            os.kill(pid, signal.SIGSTOP)
            deadline = time.monotonic() + 3
            while 'State:\tT' not in Path(f'/proc/{pid}/status').read_text():
                if time.monotonic() >= deadline:
                    raise RuntimeError('owned original did not stop')
                time.sleep(.001)

        def release(stage):
            write(cs + base.GATE + 14, struct.pack('<H', stage))

        def wait(stage, initial=False):
            nonlocal sequence
            started = time.monotonic()
            deadline, next_pulse = started + (60 if initial else 10), started
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack('<9H', read(cs + base.GATE, 18))
                if marker and flag == 0 and current > sequence:
                    sequence = current
                    if marker != stage or regs[0] != load_segment or regs[1] - regs[0] != seeder.RUNTIME_DS - actors.CS:
                        raise RuntimeError(f'flyer stage/register mismatch: observed {marker}, wanted {stage}')
                    return regs
                if initial and not marker and time.monotonic() >= next_pulse:
                    subprocess.run(['xdotool', 'windowfocus', '--sync', window], check=True, timeout=3)
                    subprocess.run(['xdotool', 'keydown', '2'], check=True, timeout=3)
                    time.sleep(.05)
                    subprocess.run(['xdotool', 'keyup', '2'], check=True, timeout=3)
                    pulses.append({'key': '2', 'elapsed_seconds': time.monotonic() - started})
                    next_pulse = time.monotonic() + .75
                time.sleep(.001)
            raise RuntimeError(f'flyer stage {stage} timeout')

        def locals_at(regs):
            if regs[5] < 0x3A or regs[5] > 0xFFF8:
                raise RuntimeError('flyer locals/parameter cross stack boundary')
            stack = memory_base + (regs[3] << 4) + regs[5]
            raw = read(stack - 0x3A, 0x3A)
            def word(relative):
                return struct.unpack_from('<h', raw, 0x3A + relative)[0]
            def byte(relative):
                return raw[0x3A + relative]
            return {'stack_hex': raw.hex(), 'vx': word(-12), 'vy': word(-14),
                    'x': word(-44), 'y': word(-46), 'frac_x': byte(-16), 'frac_y': byte(-17),
                    'edges': [byte(-35), byte(-36), byte(-34), byte(-33)],
                    'kind': byte(-15), 'behavior': byte(-49), 'registers': regs,
                    'actor_pointer': list(struct.unpack('<HH', read(stack + 4, 4))),
                    'rng': int.from_bytes(read(ds + 0x1AFE, 4), 'little'),
                    'frame': int.from_bytes(read(ds + 0x78C2, 2), 'little')}

        for at, expected in runtime_windows(load_segment).items():
            if read(cs + at, len(expected)) != expected:
                raise RuntimeError(f'runtime flyer instruction differs at {at:04x}')
        scratch = read(cs + base.SCRATCH_START, base.SCRATCH_END - base.SCRATCH_START)
        if scratch != bytes(len(scratch)):
            raise RuntimeError('verified scratch extent is not empty')
        try:
            stop()
            for stage, (entry, raw) in enumerate(HOOKS, 1):
                target = base.SCRATCH_START + (stage - 1) * base.TRAMPOLINE_STRIDE
                write(cs + target, trampoline(stage, image))
                installed.append((entry, raw))
                write(cs + entry, base.jump(entry, target))
            os.kill(pid, signal.SIGCONT)
            initial_regs = wait(1, initial=True)
            (output / 'bootstrap.json').write_text(json.dumps({'physical_key_pulses': pulses,
                'registers': initial_regs, 'reached_gameplay_hook': True}, sort_keys=True) + '\n')
            if read(ds + 0x79B7, 1) != b'\x01' or read(ds + 0xC204, 2) != struct.pack('<H', 60):
                raise RuntimeError('flyer probe did not enter the unmodified level-1 scene')
            frame = int.from_bytes(read(ds + 0x78C2, 2), 'little')
            release(1)
            wait(1)
            if int.from_bytes(read(ds + 0x78C2, 2), 'little') != (frame + 1) & 0xFFFF:
                raise RuntimeError('bootstrap did not advance one unseeded tick')
            from PIL import ImageGrab
            geometry = dict(row.split('=', 1) for row in subprocess.check_output(
                ['xdotool', 'getwindowgeometry', '--shell', window], text=True).splitlines())
            x, y, width, height = (int(geometry[key]) for key in ('X', 'Y', 'WIDTH', 'HEIGHT'))
            if (width, height) != (320, 200):
                raise RuntimeError('original screen is not unscaled VGA')
            ImageGrab.grab(xdisplay=os.environ['DISPLAY']).crop((x, y, x + width, y + height)).save(output / 'original-before-seeding.png')
            objects = memory_base + (int.from_bytes(read(ds + 0xC1FE, 2), 'little') << 4)
            offset, segment = struct.unpack('<HH', read(ds + 0x6612, 4))
            words = memory_base + (segment << 4) + offset
            descriptors = read(ds + 0xC322, 368)
            for case in CASES:
                initial_x, initial_y = case.get('x', 336), case.get('y', 99)
                actor = bytearray(38)
                actor[0], actor[1], actor[3], actor[4], actor[0x15], actor[0x24] = case['kind'], 2, 11, 11, 4, 255
                struct.pack_into('<hhHHHHH', actor, 6, case['vx'], case['vy'], case['frac_x'], case['frac_y'], case['ai0'], case['ai1'], case['ai2'])
                actor[0x16:0x1D] = bytes((40, 40, 42, 0, 3, 1, 1))
                terrain = bytearray(1980)
                for bit, cells in ((1, ((41, 12), (41, 13))), (2, ((44, 12), (44, 13))),
                                   (4, ((42, 11), (43, 11))), (8, ((42, 14), (43, 14)))):
                    if case['mask'] & bit:
                        for column, row in cells:
                            terrain[row * 60 + column] = case['glyph']
                write(objects, terrain)
                write(words, bytes(3960))
                write(ds + 0x79A6, b'\x00')
                write(ds + 0x2076, bytes(2))
                write(ds + 0x207E, struct.pack('<H', 199))
                write(ds + 0x2080, bytes(2))
                write(ds + 0x208E, b'\x00')
                write(ds + 0x79E6, bytes((1, 1)))
                write(ds + 0x79E8, bytes(2))
                write(ds + 0x1AFE, struct.pack('<I', 0x12345678))
                write(ds + 0x78C2, struct.pack('<H', case['frame']))
                write(ds + 0x1BD4, actor)
                write(ds + 0x208D, b'\x01')
                write(ds + 0xC496, b'\x03')
                write(ds + 0xC21E, struct.pack('<HH', 296 if case['mode'] == 2 else 160,
                                             79 if case['mode'] == 2 else 80))
                write(ds + 0xC226, struct.pack('<HH', 240, 80))
                write(ds + 0xC22E, struct.pack('<hh', initial_x, initial_y) + descriptors[40 * 4:41 * 4])
                seeded_actor = read(ds + 0x1BD4, 38).hex()
                release(1)
                before = locals_at(wait(2))
                if (before['vx'], before['vy'], before['x'], before['y'], before['frac_x'], before['frac_y'], before['kind'], before['behavior']) != (case['vx'], case['vy'], initial_x, initial_y, case['frac_x'], case['frac_y'], case['kind'], 4):
                    raise RuntimeError(f'case {case["index"]} native inputs differ: {before}')
                release(2)
                after = locals_at(wait(3))
                if before['frame'] != after['frame'] or before['registers'][3:] != after['registers'][3:] or before['actor_pointer'] != after['actor_pointer'] or before['actor_pointer'] != [0x1BD4, before['registers'][1]]:
                    raise RuntimeError('motion pair did not remain in one actor/frame/stack')
                observation = {'seed': case, 'seeded_actor_hex': seeded_actor,
                               'terrain_sha256': hashlib.sha256(terrain).hexdigest(), 'before': before, 'after': after}
                if retain_writeback:
                    observation['writeback_actor_hex'] = read(ds + 0x1BD4, 38).hex()
                    observation['writeback_visual_hex'] = read(ds + 0xC22E, 8).hex()
                observations.append(observation)
                (output / 'candidate.json').write_text(json.dumps({'cases': observations, 'complete': False}, sort_keys=True) + '\n')
                print(f'flyer_contacts_original case={case["index"]} kind={case["kind"]} mask={case["mask"]} motion={after["x"]},{after["y"]},{after["vx"]},{after["vy"]}', flush=True)
                if case['index'] + 1 < len(CASES):
                    release(3)
                    wait(1)
            return {'schema': 'lezac-flyer-contact-motion-v1', 'complete': True, 'cases': observations,
                    'case_count': len(CASES), 'kind_coverage': list(range(1, 9)),
                    'observed_entry_exit': [HOOKS[1][0], HOOKS[2][0]],
                    'instruction_windows': {str(at): raw.hex() for at, raw in WINDOWS.items()},
                    'hooks': [(at, raw.hex()) for at, raw in HOOKS], 'support_dependencies_sha256': DEPENDENCIES,
                    'hook_free_stack_preserved': True, 'selected_actor_parameter_guard': True,
                    'unseeded_bootstrap_ticks': 1, 'seeded_case_boundaries': True, 'seeded_terrain': True,
                    'original_fidelity_claim': False, 'natural_campaign_claim': False,
                    'pixel_parity_claim': False, 'full_actor_update_parity_claim': False}
        finally:
            stop()
            for entry, raw in installed:
                write(cs + entry, raw)
            write(cs + base.SCRATCH_START, scratch)
            restored = all(read(cs + entry, len(raw)) == raw for entry, raw in installed)
            scratch_restored = read(cs + base.SCRATCH_START, len(scratch)) == scratch
            (output / 'restoration.json').write_text(json.dumps({'hooks_restored': restored,
                'scratch_restored': scratch_restored, 'child_retained_stopped': True,
                'installed_hooks': len(installed)}, sort_keys=True) + '\n')
            if not restored or not scratch_restored:
                raise RuntimeError('flyer instrumentation restoration failed')


if __name__ == '__main__':
    base.HOOKS, base.WINDOWS, base.CASES = HOOKS, WINDOWS, CASES
    base.self_check, base.trampoline, base.capture = self_check, trampoline, capture
    base.runtime_windows = runtime_windows
    base.__file__ = __file__
    raise SystemExit(base.main())
