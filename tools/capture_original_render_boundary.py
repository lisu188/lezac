#!/usr/bin/env python3
"""Capture original indexed view pixels between the camera and actor passes."""

from __future__ import annotations

import argparse
import hashlib
from itertools import groupby
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
import seed_original_level as seeder


HOOKS = ((0x7A13, 5), (0x7A57, 5))
WINDOWS = {
    0x7A13: bytes.fromhex("803ee67900"),
    0x7A57: bytes.fromhex("c606e87900"),
    0x3587: bytes.fromhex("5589e531c0"),
    0x36F6: bytes.fromhex("a1982099"),
    0x8AC0 + 0x00F4: bytes.fromhex("a09cc43c01"),
    0x8AC0 + 0x03C8: bytes.fromhex("bada031eb800a0"),
}
CASES = (
    ("minimum", 104, 64, 0, 1),
    ("spawn", 104, 168, 0, 1),
    ("center", 240, 128, 0, 1),
    *((f"fine_x_{i}", 240 + i, 128, 0, 1) for i in range(1, 8)),
    *((f"fine_y_{i}", 240, 128 + i, 0, 1) for i in range(1, 8)),
    ("maximum", 440, 240, 0, 1),
    ("shake_positive", 243, 131, 3, 1),
    ("shake_fine_carry", 247, 131, 7, 1),
    *((f"shake_phase_{i}", 240 + i, 135, 7, 1) for i in range(8)),
    ("background_off", 243, 131, 0, 0),
    ("background_off_carry", 247, 135, 7, 0),
)


def rle(data):
    return ",".join(f"{sum(1 for _ in run)}:{value:02x}" for value, run in groupby(data))


def write_preview(path, pixels, width, height, palette):
    rgb = bytearray()
    for value in pixels:
        if 176 <= value <= 214:
            j = value - 176
            components = (j * 43 // 38, j * 23 // 38, 14 - j * 12 // 38)
        else:
            components = palette[value * 3:value * 3 + 3]
        rgb.extend(((v << 2) | (v >> 4)) & 255 for v in components)
    path.write_bytes(f"P6\n{width} {height}\n255\n".encode("ascii") + rgb)


def capture(pid, base, output, image, split_view):
    cs = base + (actors.CS << 4)
    ds = base + (seeder.RUNTIME_DS << 4)
    actors.HOOKS = HOOKS
    palette = (Path(__file__).resolve().parent.parent / "BOMPAL.PAL").read_bytes()
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(address, count):
            data = os.pread(mem.fileno(), count, address)
            if len(data) != count:
                raise RuntimeError("short child-memory read")
            return data

        def write(address, data):
            if os.pwrite(mem.fileno(), data, address) != len(data):
                raise RuntimeError("short child-memory write")

        def word(address):
            return struct.unpack("<H", read(address, 2))[0]

        sequence = 0

        def wait(stage, initial=False):
            nonlocal sequence
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + actors.SCRATCH, 18))
                if initial and marker == 2 and flag == 0:
                    write(cs + actors.SCRATCH + 14, struct.pack("<H", 2))
                if marker == stage and flag == 0 and current > sequence:
                    sequence = current
                    if regs[1] - regs[0] != seeder.RUNTIME_DS - actors.CS:
                        raise RuntimeError("unexpected runtime segments")
                    return regs
                time.sleep(0.001)
            raise RuntimeError(f"render stage {stage} timeout marker={marker} flag={flag} sequence={current}")

        def release(stage):
            write(cs + actors.SCRATCH + 14, struct.pack("<H", stage))

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
        backdrop = memory_base + (word(ds + 0xC49A) << 4) + word(ds + 0xC498)
        width, height = word(ds + 0xC204), 33
        pitch = 160 if split_view else 320
        view_width = pitch - 8
        if width != 60 or word(ds + 0xC1EC) != pitch or word(ds + 0xC1EE) != 160:
            raise RuntimeError("unexpected level/view dimensions")
        tiles = read(objects, width * height)
        background = read(backdrop, 60000)
        descriptors = read(ds + 0xC322, 368)
        lines = [
            "# Seeded rendering probes, not a natural gameplay route or whole-game parity claim.",
            "capture=render_boundary_original_v1 level=1 seeded=1 temp_copy=1 before=7a13 after=7a57"
            f" pitch={pitch} active_visuals=1",
            "# executable_sha256=" + hashlib.sha256((Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()).hexdigest(),
            f"map width={width} height={height} bytes={tiles.hex()}",
            f"backdrop bytes={rle(background)}",
            f"sprites descriptors={descriptors.hex()}",
        ]
        for name, x, y, shake, enabled in CASES:
            write(objects, tiles)
            write(ds + 0x79E6, b"\x01\x00")
            write(ds + 0x79A6, b"\x00")
            write(ds + 0x208D, b"\x00")
            write(ds + 0xC496, b"\x01")
            write(ds + 0xC49C, bytes([enabled]))
            write(ds + 0x2098, struct.pack("<h", shake))
            visual = struct.pack("<HH", x, y) + descriptors[4:8]
            write(ds + 0xC21E, visual)
            frame = word(ds + 0x78C2)
            release(1)
            after = wait(2)
            if word(ds + 0x78C2) != frame or read(objects, len(tiles)) != tiles or read(ds + 0xC21E, 8) != visual:
                raise RuntimeError("render boundary changed input state")
            globals_ = {key: word(ds + offset) for key, offset in (
                ("coarse_x", 0xC216), ("coarse_y", 0xC218),
                ("fine_x", 0xC20A), ("fine_y", 0xC20C),
                ("source", 0xC214), ("destination", 0xC1F4),
                ("map_offset", 0xC1F0), ("glyph_base", 0xC208),
                ("backdrop_stride", 0xC1F8), ("backdrop_delta", 0xC1F6),
            )}
            source = globals_["source"] + globals_["fine_x"] + globals_["fine_y"] * pitch
            buffer = memory_base + (word(ds + 0xC212) << 4)
            pixels = b"".join(read(buffer + source + row * pitch, view_width) for row in range(152))
            if globals_["destination"] != 1284:
                raise RuntimeError("unexpected presentation destination")
            lines.append(f"view name={name} x={x} y={y} shake={shake} background={enabled}"
                         f" sprite=0 frame={frame} before_regs={struct.pack('<6H', *regs).hex()}"
                         f" after_regs={struct.pack('<6H', *after).hex()}"
                         + "".join(f" {key}={value}" for key, value in globals_.items())
                         + f" pixels={rle(pixels)}")
            if name in ("spawn", "fine_x_3", "maximum", "background_off"):
                write_preview(output.with_name(f"{output.stem}_{name}.ppm"), pixels, view_width, 152, palette)
                window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
                subprocess.run(["import", "-window", window,
                                str(output.with_name(f"{output.stem}_{name}.png"))], check=True, timeout=5)
            print(f"original_render={name} frame={frame} camera="
                  f"{globals_['coarse_x'] + globals_['fine_x']},{globals_['coarse_y'] + globals_['fine_y']}"
                  f" indexed_sha256={hashlib.sha256(pixels).hexdigest()}", flush=True)
            release(2)
            regs = wait(1)
        lines.append(f"complete views={len(CASES)}")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        for entry, length in HOOKS:
            write(cs + entry, image[entry:entry + length])
        release(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--split-view", action="store_true", help="initialize two-player mode, then isolate its left view")
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
            raise RuntimeError(f"instruction mismatch at image offset {at:04x}")
    for stage in (1, 2):
        actors.trampoline(stage, image)
    print(f"render_capture_self_check=ok windows={len(WINDOWS)} cases={len(CASES)} live=0"
          f" executable_sha256={hashlib.sha256(exe).hexdigest()}", flush=True)
    if args.self_check:
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("live capture requires temporary run-dir, out and both approval flags")
    if args.out.exists() or list(args.out.parent.glob(args.out.stem + "_*")):
        parser.error("output already exists; use a fresh path")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if (args.run_dir / "LEZAC.EXE").read_bytes() != exe:
        parser.error("temporary executable differs from the guarded original")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_RENDER_BOUNDARY_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image, args.split_view)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--start-key", "2" if args.split_view else "1",
                "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
