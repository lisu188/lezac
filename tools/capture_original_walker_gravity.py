"""Observe bounded walker gravity locals in an owned silent original child."""
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import capture_original_behavior4_targets as base
import capture_original_death_transients as actors
import seed_original_level as seeder

HOOKS = ((0x7EC5, bytes.fromhex('c70682200100')),
         (0x716E, bytes.fromhex('807edf00')),
         (0x71A4, bytes.fromhex('807edf00')))
RAW = bytes.fromhex('807edf007406837ef2007d128346f240817ef2ff077e05c746f2ff07eb18837ef2007e1231c08946f28b46d225f8ff8946d2c646e001')
VELOCITIES = (-32768, -32767, -65, -64, -1, 0, 1, 63, 1982, 1983, 1984, 2047, 2048, 32703, 32704, 32767)
CASES = tuple((bottom, vy) for bottom in (0, 1) for vy in VELOCITIES)
WINDOWS = dict(HOOKS) | {0x716E: RAW, 0x712B: bytes.fromhex('a17420d1e0509aa8132009')}
DEPENDENCIES = {'capture_original_behavior4_targets.py': 'a99a7f81c19720f44e794807c35c2b326dd5cdedfea79d01ee63eeab3d421ed8',
                'capture_original_death_transients.py': 'a0fddeb9c3ce6426641739ac7bd558a4e7d253670df28ec1c8aead652b3e0ba9'}


def trampoline(stage, image):
    plain = actors.trampoline(stage, image)
    entry, raw = HOOKS[stage - 1]
    target = base.SCRATCH_START + (stage - 1) * base.TRAMPOLINE_STRIDE
    body = plain[2:-(2 + len(raw) + 3)]
    code = bytearray(base.preserve_stack(False) + b'\x9c\x60')
    if stage in (2, 3):
        guard = len(code)
        code += bytes.fromhex('807ef1017500807ecf037500')
        end = len(code) + len(body)
        code[guard + 5] = end - (guard + 6)
        code[guard + 11] = end - (guard + 12)
    code += body + b'\x61\x9d' + base.preserve_stack(True) + raw
    code += base.jump(target + len(code), entry + len(raw))
    if len(code) > base.TRAMPOLINE_STRIDE or target + len(code) > base.GATE:
        raise RuntimeError('gravity trampoline exceeds the previously verified scratch extent')
    return bytes(code)


def self_check():
    exe = (ROOT / 'LEZAC.EXE').read_bytes()
    if hashlib.sha256(exe).hexdigest() != base.EXE_SHA:
        raise RuntimeError('original executable changed')
    if exe[:2] != b'MZ' or struct.unpack_from('<H', exe, 8)[0] * 16 != 0x770:
        raise RuntimeError('original MZ image base differs')
    for name, digest in DEPENDENCIES.items():
        if base.sha(ROOT / 'tools' / name) != digest:
            raise RuntimeError(f'capture dependency changed: {name}')
    image = exe[0x770:]
    for offset, raw in WINDOWS.items():
        if image[offset:offset + len(raw)] != raw:
            raise RuntimeError(f'original gravity window differs: {offset:04x}')
    count, table = struct.unpack_from('<H', exe, 6)[0], struct.unpack_from('<H', exe, 24)[0]
    relocations = {segment * 16 + offset for offset, segment in
                   (struct.unpack_from('<HH', exe, table + index * 4) for index in range(count))}
    affected = {at for at in relocations for entry, raw in WINDOWS.items() if entry <= at < entry + len(raw)}
    if affected != {base.FAR_SEGMENT_WORD}:
        raise RuntimeError('gravity/support relocation set changed')
    actors.HOOKS = tuple((at, len(raw)) for at, raw in HOOKS)
    actors.SCRATCH = base.GATE
    for stage in (1, 2, 3):
        trampoline(stage, image)
    print(f'walker_gravity_self_check=ok cases={len(CASES)} hook_free_stack_preserved=1 live=0', flush=True)
    return image


def capture(pid, location, output, image, window, load_segment):
    cs, ds = location + (actors.CS << 4), location + (seeder.RUNTIME_DS << 4)
    installed, observations, pulses = [], [], []
    sequence = 0
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
                        raise RuntimeError(f'gravity stage/register mismatch: observed{marker} wanted{stage}')
                    return regs
                if initial and not marker and time.monotonic() >= next_pulse:
                    subprocess.run(['xdotool', 'windowfocus', '--sync', window], check=True, timeout=3)
                    subprocess.run(['xdotool', 'keydown', '2'], check=True, timeout=3)
                    time.sleep(.05)
                    subprocess.run(['xdotool', 'keyup', '2'], check=True, timeout=3)
                    pulses.append({'key': '2', 'elapsed_seconds': time.monotonic() - started})
                    next_pulse = time.monotonic() + .75
                time.sleep(.001)
            raise RuntimeError(f'gravity stage {stage} timeout')

        memory_base = cs - (load_segment << 4)

        def locals_at(regs):
            if regs[5] < 0x3A:
                raise RuntimeError('gravity locals cross stack segment boundary')
            raw = read(memory_base + (regs[3] << 4) + regs[5] - 0x3A, 0x3A)
            def word(relative):
                return struct.unpack_from('<h', raw, 0x3A + relative)[0]
            def byte(relative):
                return raw[0x3A + relative]
            return {'stack_hex': raw.hex(), 'vy': word(-0x0E), 'x': word(-0x2C), 'y': word(-0x2E),
                    'bottom': byte(-0x21), 'facing_dirty': byte(-0x20),
                    'kind': byte(-0x0F), 'behavior': byte(-0x31), 'registers': regs}

        for at, expected in base.runtime_windows(load_segment).items():
            if read(cs + at, len(expected)) != expected:
                raise RuntimeError(f'runtime gravity instruction differs at {at:04x}')
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
            (output / 'bootstrap.json').write_text(json.dumps({'physical_key_pulses': pulses, 'registers': initial_regs,
                'reached_gameplay_hook': True}, sort_keys=True) + '\n')
            if read(ds + 0x79B7, 1) != b'\x01' or read(ds + 0xC204, 2) != struct.pack('<H', 60):
                raise RuntimeError('gravity probe did not enter the unmodified level-1 scene')
            initial_frame = int.from_bytes(read(ds + 0x78C2, 2), 'little')
            release(1)
            wait(1)
            if int.from_bytes(read(ds + 0x78C2, 2), 'little') != (initial_frame + 1) & 0xFFFF:
                raise RuntimeError('gravity bootstrap did not advance one unseeded tick')
            from PIL import ImageGrab
            geometry = dict(row.split('=', 1) for row in subprocess.check_output(
                ['xdotool', 'getwindowgeometry', '--shell', window], text=True).splitlines())
            x, y, width, height = (int(geometry[key]) for key in ('X', 'Y', 'WIDTH', 'HEIGHT'))
            if (width, height) != (320, 200):
                raise RuntimeError('gravity original screen is not unscaled VGA')
            ImageGrab.grab(xdisplay=os.environ['DISPLAY']).crop((x, y, x + width, y + height)).save(output / 'original-before-seeding.png')
            objects = memory_base + (int.from_bytes(read(ds + 0xC1FE, 2), 'little') << 4)
            offset, segment = struct.unpack('<HH', read(ds + 0x6612, 4))
            words = memory_base + (segment << 4) + offset
            descriptors = read(ds + 0xC322, 368)
            for index, (bottom, vy) in enumerate(CASES):
                actor = bytearray.fromhex('0c0200010200000000000000000023010000000006022c2c2dff030001000000000000000101')
                actor[0], actor[2], actor[3], actor[4], actor[0x15] = 1, 11, 0, 3, 3
                struct.pack_into('<hh', actor, 6, 0, vy)
                struct.pack_into('<H', actor, 14, 208)
                terrain = bytearray(1980)
                if bottom:
                    for column in (42, 43):
                        terrain[14 * 60 + column] = 0x52
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
                write(ds + 0x78C2, struct.pack('<H', 420))
                write(ds + 0x1BD4, actor)
                write(ds + 0x208D, b'\x01')
                write(ds + 0xC496, b'\x03')
                write(ds + 0xC21E, struct.pack('<HH', 160, 80))
                write(ds + 0xC226, struct.pack('<HH', 240, 80))
                write(ds + 0xC22E, struct.pack('<HH', 336, 105) + descriptors[44 * 4:45 * 4])
                seeded_actor = read(ds + 0x1BD4, 38).hex()
                release(1)
                before = locals_at(wait(2))
                if (before['bottom'], before['vy'], before['x'], before['y'], before['kind'], before['behavior']) != (bottom, vy, 336, 99, 1, 3):
                    raise RuntimeError(f'case{index} gravity inputs differ from the declared seed: {before}')
                release(2)
                after = locals_at(wait(3))
                if read(ds + 0x78C2, 2) != struct.pack('<H', 420) or before['registers'][5] != after['registers'][5]:
                    raise RuntimeError('gravity sample did not remain within one actor call/frame')
                observations.append({'index': index, 'seed_bottom': bottom, 'seed_vy': vy,
                    'seeded_actor_hex': seeded_actor, 'before': before, 'after': after})
                (output / 'candidate.json').write_text(json.dumps({'cases': observations, 'complete': False}, sort_keys=True) + '\n')
                print(f'walker_gravity_original case={index} bottom={bottom} vy={vy}->{after["vy"]}', flush=True)
                if index + 1 < len(CASES):
                    release(3)
                    wait(1)
            return {'schema': 'lezac-walker-gravity-word-v1', 'complete': True, 'cases': observations,
                    'case_count': len(CASES), 'instruction_window': [0x716E, 0x71A4],
                    'instruction_window_hex': RAW.hex(), 'instruction_windows_sha256': hashlib.sha256(RAW).hexdigest(),
                    'hooks': [(at, raw.hex()) for at, raw in HOOKS], 'support_dependencies_sha256': DEPENDENCIES,
                    'hook_free_stack_preserved': True, 'unseeded_bootstrap_ticks': 1,
                    'seeded_case_boundaries': True, 'seeded_terrain': True, 'original_fidelity_claim': False,
                    'natural_campaign_claim': False, 'pixel_parity_claim': False,
                    'full_actor_update_parity_claim': False, 'signed_overflow_is_seeded_not_naturally_reached': True}
        finally:
            stop()
            for entry, raw in installed:
                write(cs + entry, raw)
            write(cs + base.SCRATCH_START, scratch)
            hooks_restored = all(read(cs + entry, len(raw)) == raw for entry, raw in installed)
            scratch_restored = read(cs + base.SCRATCH_START, len(scratch)) == scratch
            (output / 'restoration.json').write_text(json.dumps({'hooks_restored': hooks_restored,
                'scratch_restored': scratch_restored, 'child_retained_stopped': True,
                'installed_hooks': len(installed)}, sort_keys=True) + '\n')
            if not hooks_restored or not scratch_restored:
                raise RuntimeError('gravity instrumentation restoration failed')


if __name__ == '__main__':
    base.HOOKS = HOOKS
    base.WINDOWS = WINDOWS
    base.CASES = CASES
    base.self_check = self_check
    base.trampoline = trampoline
    base.capture = capture
    base.__file__ = __file__
    raise SystemExit(base.main())
