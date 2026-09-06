#!/usr/bin/env python3
"""Capture original sprite compositing at guarded render boundaries."""

import argparse
import hashlib
from itertools import combinations
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time

import capture_original_behavior4_lockstep as environment
import capture_original_death_transients as actors
from capture_original_bomb_fuses import jump
import capture_original_render_boundary as render
import seed_original_level as seeder


HOOKS = render.HOOKS
WINDOWS = render.WINDOWS | {
    0x9437 - 0x770: bytes.fromhex("8a0e96c430ed83f900"),
    0x9445 - 0x770: bytes.fromhex("31db8a8722c230e4"),
    0x94FF - 0x770: bytes.fromhex("ac3c00750347eb01aa"),
    0x9513 - 0x770: bytes.fromhex("83c30849e303e92bff"),
    0x95DC - 0x770: bytes.fromhex("ac3c00750347eb01aa"),
}
SPRITES = {"effect": 70, "bomb": 58, "monster": 44, "reward": 63, "last_sprite": 91}


def cases(pitch):
    width = pitch - 8
    x, y = 247, 135
    result = [("control", (), x + 40, y - 20, False, x, y, 0)]
    kinds = ("effect", "bomb", "monster", "reward")
    for pair in combinations(kinds, 2):
        for order in (pair, pair[::-1]):
            result.append(("_".join(order), order, x + 40, y - 20, False, x, y, 0))
    for name, order in (("mixed_forward", kinds), ("mixed_reverse", kinds[::-1])):
        result.append((name, order, x + 40, y - 20, False, x, y, 0))
    for kind in kinds:
        result.append(("player_" + kind, (kind,), x, y, False, x, y, 0))
    result.append(("two_players", (), x, y, True, x, y, 0))
    result.append(("two_players_mixed", kinds, x, y, True, x, y, 0))
    result.append(("last_sprite_control", ("last_sprite",), x, y, False, x, y, 0))
    cam_x, cam_y = x - (width // 2 - 4), y - 80
    for edge, dx, dy in (("left", -8, 45), ("right", width - 5, 45),
                         ("top", width // 2, -8), ("bottom", width // 2, 148), ("corner", -5, -5)):
        for reverse in (False, True):
            result.append((f"clip_{edge}_{int(reverse)}", kinds[::-1] if reverse else kinds,
                           cam_x + dx, cam_y + dy, False, x, y, 0))
    for phase in range(8):
        camera_x = 240 + phase
        cam_x = camera_x - (width // 2 - 4)
        result.append((f"shake_{phase}", kinds, cam_x + width - 5, cam_y + 45,
                       False, camera_x, y, 7))
    return result


def capture(pid, base, output, image, split):
    cs, ds = base + (actors.CS << 4), base + (seeder.RUNTIME_DS << 4)
    actors.HOOKS = HOOKS
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(address, count):
            value = os.pread(mem.fileno(), count, address)
            if len(value) != count:
                raise RuntimeError("short visual-order memory read")
            return value

        def write(address, value):
            if os.pwrite(mem.fileno(), value, address) != len(value):
                raise RuntimeError("short visual-order memory write")

        def word(address):
            return struct.unpack("<H", read(address, 2))[0]

        sequence = 0

        def release(stage):
            write(cs + actors.SCRATCH + 14, struct.pack("<H", stage))

        def wait(stage, initial=False):
            nonlocal sequence
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + actors.SCRATCH, 18))
                if initial and marker == 2 and not flag:
                    release(2)
                if marker == stage and not flag and current > sequence:
                    sequence = current
                    if regs[1] - regs[0] != seeder.RUNTIME_DS - actors.CS:
                        raise RuntimeError("unexpected visual-order segments")
                    return regs
                time.sleep(0.001)
            raise RuntimeError(f"visual-order stage {stage} timeout")

        for at, expected in WINDOWS.items():
            if read(cs + at, len(expected)) != expected:
                raise RuntimeError(f"runtime instruction mismatch at {at:04x}")
        if read(cs + 0xF400, 0x212) != bytes(0x212):
            raise RuntimeError("instrumentation scratch is not empty")
        os.kill(pid, signal.SIGSTOP)
        try:
            deadline = time.monotonic() + 2
            while "State:\tT" not in Path(f"/proc/{pid}/status").read_text():
                if time.monotonic() > deadline:
                    raise RuntimeError("child did not stop")
                time.sleep(0.001)
            for stage, (entry, _) in enumerate(HOOKS, 1):
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, actors.trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        finally:
            os.kill(pid, signal.SIGCONT)
        regs = wait(1, initial=True)
        memory_base = cs - (regs[0] << 4)
        objects = memory_base + (word(ds + 0xC1FE) << 4)
        pitch = 160 if split else 320
        if word(ds + 0xC204) != 60 or word(ds + 0xC1EC) != pitch or word(ds + 0xC1EE) != 160:
            raise RuntimeError("unexpected visual-order dimensions")
        tiles = read(objects, 1980)
        backdrop = read(memory_base + (word(ds + 0xC49A) << 4) + word(ds + 0xC498), 60000)
        descriptors = read(ds + 0xC322, 368)
        palette = (Path(__file__).resolve().parent.parent / "BOMPAL.PAL").read_bytes()
        lines = ["# Explicit visual seeds; no natural-route or whole-game parity claim.",
                 "# executable_sha256=" + hashlib.sha256((Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()).hexdigest(),
                 f"capture=visual_order_original_v1 level=1 seeded=1 temp_copy=1 before=7a13 after=7a57 pitch={pitch}",
                 f"map bytes={tiles.hex()}", f"backdrop bytes={render.rle(backdrop)}",
                 f"sprites descriptors={descriptors.hex()}"]
        hashes = {}
        for name, order, ax, ay, p2, x, y, shake in cases(pitch):
            write(objects, tiles)
            write(ds + 0x79E6, b"\x01\x00")
            write(ds + 0x79A6, b"\x00")
            write(ds + 0x208D, b"\x00")
            write(ds + 0x79EA, b"\x63\x63\x64\x64")
            write(ds + 0xC49C, b"\x01")
            write(ds + 0x2098, struct.pack("<h", shake))
            visuals = [struct.pack("<HH", x, y) + descriptors[4:8],
                       (struct.pack("<HH", x, y) + descriptors[84:88] if p2 else b"\xff\xff\xff\xff" + bytes(4))]
            visuals.extend(struct.pack("<HH", ax, ay) + descriptors[SPRITES[kind] * 4:SPRITES[kind] * 4 + 4] for kind in order)
            packed = b"".join(visuals)
            write(ds + 0xC21E, packed)
            write(ds + 0xC496, bytes([len(visuals)]))
            frame = word(ds + 0x78C2)
            release(1)
            after = wait(2)
            if read(objects, 1980) != tiles or read(ds + 0xC21E, len(packed)) != packed or word(ds + 0x78C2) != frame:
                raise RuntimeError("visual-order render modified seeded state")
            values = {key: word(ds + at) for key, at in (("coarse_x", 0xC216), ("coarse_y", 0xC218),
                      ("fine_x", 0xC20A), ("fine_y", 0xC20C), ("source", 0xC214), ("destination", 0xC1F4))}
            source = values["source"] + values["fine_x"] + values["fine_y"] * pitch
            buffer = memory_base + (word(ds + 0xC212) << 4)
            pixels = b"".join(read(buffer + source + row * pitch, pitch - 8) for row in range(152))
            digest = hashlib.sha256(pixels).hexdigest()
            hashes[name] = digest
            lines.append(f"view name={name} order={','.join(order) or '-'} x={x} y={y} actor_x={ax} actor_y={ay}"
                         f" p2={int(p2)} shake={shake} count={len(visuals)} frame={frame} visuals={packed.hex()}"
                         f" before_regs={struct.pack('<6H', *regs).hex()} after_regs={struct.pack('<6H', *after).hex()}"
                         + "".join(f" {key}={value}" for key, value in values.items())
                         + f" indexed_sha256={digest} pixels={render.rle(pixels)}")
            if name in ("effect_bomb", "bomb_effect", "mixed_forward", "mixed_reverse", "two_players_mixed", "clip_right_0", "shake_7", "last_sprite_control"):
                stem = output.with_name(f"{output.stem}_{name}")
                render.write_preview(stem.with_suffix(".ppm"), pixels, pitch - 8, 152, palette)
                window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
                subprocess.run(["import", "-window", window, str(stem.with_suffix(".png"))], check=True, timeout=5)
            print(f"visual_order_original case={name} frame={frame} sha256={digest}", flush=True)
            release(2)
            regs = wait(1)
        for pair in combinations(("effect", "bomb", "monster", "reward"), 2):
            if hashes["_".join(pair)] == hashes["_".join(pair[::-1])]:
                raise RuntimeError(f"non-discriminating overlap pair: {pair}")
        lines.append(f"complete views={len(cases(pitch))} discriminating_pairs=6")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        for entry, length in HOOKS:
            write(cs + entry, image[entry:entry + length])
        release(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--split-view", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    exe = (Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()
    image = exe[0x770:]
    actors.HOOKS = HOOKS
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"instruction mismatch at {at:04x}")
    for stage in (1, 2):
        actors.trampoline(stage, image)
    print(f"visual_order_capture_self_check=ok windows={len(WINDOWS)} views={len(cases(160 if args.split_view else 320))} live=0", flush=True)
    if args.self_check:
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("live capture requires temporary run-dir, out and both approval flags")
    if args.out.exists() or list(args.out.parent.glob(args.out.stem + "_*")):
        parser.error("output exists; use a fresh path")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if (args.run_dir / "LEZAC.EXE").read_bytes() != exe:
        parser.error("temporary executable differs from guarded original")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_VISUAL_ORDER_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image, args.split_view)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--start-key", "2" if args.split_view else "1", "--startup-seconds", "10", "--intro-seconds", "8",
                "--level-start-seconds", "5", "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
