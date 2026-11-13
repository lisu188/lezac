"""Observe shipped-profile native constructors and continuous controlled motion."""
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import struct
import time
import subprocess

import capture_original_behavior4_targets as base
import capture_original_death_transients as actors
import seed_original_level as seeder

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = 'lezac-shipped-monster-profiles-v1'
HOOKS = ((0x7A6B, bytes.fromhex('803ea67900')),
         (0x7C3D, bytes.fromhex('c70682200100')),
         (0x7EEA, bytes.fromhex('803ee67901')))
WINDOWS = dict(base.WINDOWS) | dict(HOOKS)
TICKS = 64
SEEDS = (0, 0x12345678, 0xFFFFFFFF)


def profiles():
    data = (ROOT / 'LIVELS.SCH').read_bytes()
    at, level, rows = 0, 0, []
    while at < len(data):
        level += 1
        at += 8
        for _ in range(2):
            size = struct.unpack_from('<H', data, at)[0]
            at += 2 + size
        at += 4
        for stride in (30, 7, 14):
            count = data[at]
            at += 1
            for slot in range(count):
                raw = data[at:at + stride]
                if len(raw) != stride:
                    raise RuntimeError('truncated shipped level record')
                if stride == 30:
                    rows.append((level, slot, at, raw))
                at += stride
    if at != len(data) or level != 7 or len(rows) != 15:
        raise RuntimeError('shipped profile inventory differs')
    return tuple(rows)


def terrain():
    tiles = bytearray(60 * 33)
    for column in range(60):
        tiles[6 * 60 + column] = tiles[24 * 60 + column] = 1
    for row in range(7, 24):
        tiles[row * 60 + 26] = tiles[row * 60 + 56] = 1
    return bytes(tiles)


def trampoline(stage, image):
    actors.HOOKS = tuple((entry, len(raw)) for entry, raw in HOOKS)
    actors.SCRATCH = base.GATE
    plain = actors.trampoline(stage, image)
    entry, raw = HOOKS[stage - 1]
    target = base.SCRATCH_START + (stage - 1) * base.TRAMPOLINE_STRIDE
    body = plain[2:-(2 + len(raw) + 3)]
    code = base.preserve_stack(False) + b'\x9c\x60' + body
    code += b'\x61\x9d' + base.preserve_stack(True) + raw
    code += base.jump(target + len(code), entry + len(raw))
    if len(code) > base.TRAMPOLINE_STRIDE or target + len(code) > base.GATE:
        raise RuntimeError('profile trampoline exceeds verified scratch')
    return code


def self_check():
    exe = (ROOT / 'LEZAC.EXE').read_bytes()
    if hashlib.sha256(exe).hexdigest() != base.EXE_SHA:
        raise RuntimeError('original executable differs')
    image = exe[0x770:]
    for entry, raw in WINDOWS.items():
        if image[entry:entry + len(raw)] != raw:
            raise RuntimeError(f'profile instruction window differs: {entry:04x}')
    for stage in (1, 2, 3):
        trampoline(stage, image)
    profiles()
    print('shipped_monster_profiles_self_check=ok profiles=15 cases=45 ticks=64 live=0', flush=True)
    return image


def capture(pid, location, output, image, window, load_segment):
    for name in ('capture_original_shipped_monster_profiles.py',
                 'capture_original_behavior4_targets.py', 'capture_original_death_transients.py',
                 'capture_original_behavior4_lockstep.py', 'capture_original_bomb_fuses.py', 'seed_original_level.py'):
        shutil.copyfile(ROOT / 'tools' / name, output / name)
    cs, ds = location + (actors.CS << 4), location + (seeder.RUNTIME_DS << 4)
    memory_base = cs - (load_segment << 4)
    installed, pulses, sequence = [], [], 0
    with open(f'/proc/{pid}/mem', 'r+b', buffering=0) as mem:
        def read(at, size):
            raw = os.pread(mem.fileno(), size, at)
            if len(raw) != size:
                raise RuntimeError('short owned original read')
            return raw

        def write(at, raw):
            if os.pwrite(mem.fileno(), raw, at) != len(raw):
                raise RuntimeError('short owned original write')

        def stop():
            os.kill(pid, signal.SIGSTOP)
            deadline = time.monotonic() + 3
            while 'State:\tT' not in Path(f'/proc/{pid}/status').read_text():
                if time.monotonic() > deadline:
                    raise RuntimeError('owned child failed to stop')
                time.sleep(.001)

        def release(stage):
            write(cs + base.GATE + 14, struct.pack('<H', stage))

        def wait(stage, initial=False):
            nonlocal sequence
            started = time.monotonic()
            deadline, pulse = started + (60 if initial else 10), started
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack('<9H', read(cs + base.GATE, 18))
                if marker and flag == 0 and current > sequence:
                    sequence = current
                    if marker != stage or regs[0] != load_segment or regs[1] - regs[0] != seeder.RUNTIME_DS - actors.CS:
                        raise RuntimeError(f'profile stage/register mismatch: {marker}, wanted {stage}')
                    return regs
                if initial and not marker and time.monotonic() >= pulse:
                    subprocess.run(['xdotool', 'windowfocus', '--sync', window], check=True, timeout=3)
                    subprocess.run(['xdotool', 'keydown', '2'], check=True, timeout=3)
                    time.sleep(.05)
                    subprocess.run(['xdotool', 'keyup', '2'], check=True, timeout=3)
                    pulses.append({'key': '2', 'elapsed_seconds': time.monotonic() - started})
                    pulse = time.monotonic() + .75
                time.sleep(.001)
            raise RuntimeError(f'profile stage {stage} timeout')

        def snapshot(regs):
            count = read(ds + 0x208D, 1)[0]
            if count not in (0, 1):
                raise RuntimeError('controlled profile actor count differs')
            raw = read(ds + 0x1BD4, 38) if count else bytes(38)
            visual = read(ds + 0xC21E + raw[1] * 8, 8) if count else bytes(8)
            return {'frame': int.from_bytes(read(ds + 0x78C2, 2), 'little'),
                    'rng': int.from_bytes(read(ds + 0x1AFE, 4), 'little'), 'count': count,
                    'actor': raw.hex(), 'visual': visual.hex(),
                    'spawner': read(ds + 0x74C6, 30).hex(),
                    'p1': read(ds + 0xC21E, 8).hex(), 'p2': read(ds + 0xC226, 8).hex(),
                    'flags': read(ds + 0x79E6, 2).hex(), 'registers': regs}

        def screenshot(name):
            from PIL import ImageGrab
            geometry = dict(line.split('=', 1) for line in subprocess.check_output(
                ['xdotool', 'getwindowgeometry', '--shell', window], text=True).splitlines())
            x, y, width, height = (int(geometry[key]) for key in ('X', 'Y', 'WIDTH', 'HEIGHT'))
            if (width, height) != (320, 200):
                raise RuntimeError('original capture is not unscaled VGA')
            ImageGrab.grab(xdisplay=os.environ['DISPLAY']).crop((x, y, x + width, y + height)).save(output / name)

        for entry, raw in base.runtime_windows(load_segment).items():
            if read(cs + entry, len(raw)) != raw:
                raise RuntimeError('profile runtime window differs')
        scratch = read(cs + base.SCRATCH_START, base.SCRATCH_END - base.SCRATCH_START)
        if scratch != bytes(len(scratch)):
            raise RuntimeError('verified scratch is occupied')
        records = []
        try:
            stop()
            for stage, (entry, raw) in enumerate(HOOKS, 1):
                target = base.SCRATCH_START + (stage - 1) * base.TRAMPOLINE_STRIDE
                write(cs + target, trampoline(stage, image))
                installed.append((entry, raw))
                write(cs + entry, base.jump(entry, target))
            os.kill(pid, signal.SIGCONT)
            wait(1, initial=True)
            (output / 'bootstrap.json').write_text(json.dumps({'physical_key_pulses': pulses}) + '\n')
            if read(ds + 0x79B7, 1) != b'\x01' or read(ds + 0xC204, 2) != struct.pack('<H', 60):
                raise RuntimeError('probe did not enter original level 1')
            release(1)
            wait(2)
            release(2)
            wait(3)
            release(3)
            spawner_regs = wait(1)
            screenshot('original-before-control.png')
            descriptors = read(ds + 0xC322, 368)
            players = bytearray(read(ds + 0x1B88, 76))
            players[36] = players[74] = 100
            offset, segment = struct.unpack('<HH', read(ds + 0xC1E0, 4))
            tiles = memory_base + (segment << 4) + offset
            offset, segment = struct.unpack('<HH', read(ds + 0x6612, 4))
            words = memory_base + (segment << 4) + offset
            for profile, (level, slot, file_offset, shipped) in enumerate(profiles()):
                for seed_index, seed in enumerate(SEEDS):
                    index = len(records)
                    spawner = bytearray(shipped)
                    struct.pack_into('<HH', spawner, 0, 336, 105)
                    spawner[8], spawner[10], spawner[27] = 1, 1, 1
                    write(tiles, terrain())
                    write(words, bytes(3960))
                    write(ds + 0x79A6, b'\x01')
                    write(ds + 0x74C6, spawner)
                    write(ds + 0x208D, b'\x00')
                    write(ds + 0x208E, b'\x00')
                    write(ds + 0xC496, b'\x02')
                    write(ds + 0x1BD4, bytes(30 * 38))
                    write(ds + 0x1AFE, struct.pack('<I', seed))
                    write(ds + 0x78C2, struct.pack('<H', 420 + index))
                    write(ds + 0x2076, bytes(2))
                    write(ds + 0x207E, struct.pack('<H', 199))
                    write(ds + 0x2080, bytes(2))
                    write(ds + 0x79E6, bytes((1, 0)))
                    write(ds + 0x79E8, bytes(2))
                    write(ds + 0x79B9, b'\x00')
                    write(ds + 0x79EA, bytes((99, 99, 100, 100)))
                    write(ds + 0x1B88, players)
                    write(ds + 0xC21E, struct.pack('<HH', 368 if seed_index == 0 else 64, 105))
                    write(ds + 0xC226, struct.pack('<HH', 64, 105))
                    write(ds + 0x1B8E, bytes(8))
                    before = snapshot(spawner_regs)
                    release(1)
                    constructor_regs = wait(2)
                    constructed = snapshot(constructor_regs)
                    if constructed['count'] != 1 or bytes.fromhex(constructed['actor'])[0] != shipped[11]:
                        raise RuntimeError('native constructor did not create selected shipped kind')
                    case = {'index': index, 'profile': profile, 'level': level, 'slot': slot,
                            'file_offset': file_offset, 'shipped': shipped.hex(), 'seed': seed,
                            'near_start': seed_index == 0, 'before': before, 'constructor': constructed, 'ticks': []}
                    records.append(case)
                    for tick in range(TICKS):
                        pre = snapshot(constructor_regs)
                        release(2)
                        post = snapshot(wait(3))
                        if post['frame'] != pre['frame']:
                            raise RuntimeError('actor pass changed shared frame counter')
                        case['ticks'].append({'pre': pre, 'post': post})
                        release(3)
                        spawner_regs = wait(1)
                        if tick in (0, TICKS - 1) and seed_index in (0, 1):
                            screenshot(f'original-profile-{profile:02d}-seed-{seed_index}-{tick:02d}.png')
                        if tick + 1 < TICKS:
                            release(1)
                            constructor_regs = wait(2)
                    (output / 'observations.json').write_text(json.dumps(records, sort_keys=True) + '\n')
                    print(f'shipped_monster_profile={profile} seed={seed:08x} ticks={TICKS}', flush=True)
            return {'schema': SCHEMA, 'profiles': 15, 'cases': len(records), 'ticks': TICKS,
                    'sprite_descriptors': descriptors.hex(), 'terrain': terrain().hex(),
                    'continuous_actor_updates': True, 'controlled_room': True,
                    'native_constructor': True, 'natural_route': False, 'whole_game_parity': False}
        finally:
            stop()
            (output / 'observations.json').write_text(json.dumps(records, sort_keys=True) + '\n')
            (output / 'final-ds.bin').write_bytes(read(ds, 65536))
            for entry, raw in installed:
                write(cs + entry, raw)
            write(cs + base.SCRATCH_START, scratch)
            restored = all(read(cs + entry, len(raw)) == raw for entry, raw in installed)
            scratch_restored = read(cs + base.SCRATCH_START, len(scratch)) == scratch
            (output / 'restoration.json').write_text(json.dumps({'hooks_restored': restored,
                'scratch_restored': scratch_restored, 'child_retained_stopped': True}) + '\n')
            if not restored or not scratch_restored:
                raise RuntimeError('profile original restoration failed')


if __name__ == '__main__':
    base.HOOKS, base.WINDOWS = HOOKS, WINDOWS
    base.self_check, base.capture = self_check, capture
    base.__file__ = __file__
    raise SystemExit(base.main())
