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
    0x13FF - 0x770: bytes.fromhex("a116660b061866741e"),
    0x1437 - 0x770: bytes.fromhex("a1ba7805100050"),
    0x14D0 - 0x770: bytes.fromhex("a1ba7805100050"),
    0x1506 - 0x770: bytes.fromhex("c43ee0c18cc0408bd031c0"),
    0x9D70 - 0x770: bytes.fromhex("2689450426895506"),
    0x9E01 - 0x770: bytes.fromhex("0507008bd0d1dad1ead1ead1ea250800c3"),
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


def tall_cases(width, height, spawn):
    right, bottom = width * 8 - 32, height * 8 - 24
    return (
        ("upper", 104, 64, 0, 1),
        ("spawn", *spawn, 0, 1),
        ("center", width * 4, height * 4, 0, 1),
        ("lower_left", 104, bottom, 0, 1),
        ("lower_right", right, bottom, 0, 1),
        ("clear_upper", 104, 64, 0, 1),
        *((f"clear_threshold_{i}", right, 80 + i * 8, 0, 1) for i in (35, 36, 37)),
        ("clear_bottom_left", 104, bottom, 0, 1),
        ("clear_bottom_right", right, bottom, 0, 1),
        ("clear_bottom_shake", right, bottom, 7, 1),
        ("clear_bottom_off", right, bottom, 0, 0),
        ("alias_bottom_left", 104, bottom, 0, 1),
        ("alias_bottom_right", right, bottom, 0, 1),
    )


def capture(pid, base, output, image, split_view, level):
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
        backdrop_segment, backdrop_offset = word(ds + 0xC49A), word(ds + 0xC498)
        backdrop = memory_base + (backdrop_segment << 4) + backdrop_offset

        def read_backdrop(start, count):
            offset = (backdrop_offset + start) & 0xffff
            first = min(count, 65536 - offset)
            segment = memory_base + (backdrop_segment << 4)
            return read(segment + offset, first) + (read(segment, count - first) if first < count else b"")

        width = word(ds + 0xC204)
        height = word(ds + 0x2096) // 8 + 21
        pitch = 160 if split_view else 320
        view_width = pitch - 8
        dimensions = ((60, 33), (100, 53), (150, 60), (100, 58), (110, 62), (180, 64), (140, 52))
        if (width, height) != dimensions[level - 1] or word(ds + 0xC1EC) != pitch or word(ds + 0xC1EE) != 160:
            raise RuntimeError("unexpected level/view dimensions")
        cases = CASES if level == 1 else tall_cases(width, height, struct.unpack("<HH", read(ds + 0xC21E, 4)))
        tiles = read(objects, width * height)
        background = read(backdrop, 60000)
        descriptors = read(ds + 0xC322, 368)
        lines = [
            "# Seeded rendering probes, not a natural gameplay route or whole-game parity claim.",
            f"capture={'render_boundary_tall_original_v2' if level != 1 else 'render_boundary_original_v1'} level={level} seeded=1 temp_copy=1 before=7a13 after=7a57"
            f" pitch={pitch} active_visuals=1",
            "# executable_sha256=" + hashlib.sha256((Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()).hexdigest(),
            f"map width={width} height={height} bytes={tiles.hex()}",
            f"backdrop bytes={rle(background)}",
            f"sprites descriptors={descriptors.hex()}",
        ]
        if level != 1:
            pointers = {key: read(ds + at, 4).hex() for key, at in (
                ("backdrop", 0xC498), ("tile_bytes", 0xC1E0), ("tile_words", 0x6612),
                ("tile_allocation", 0x661A), ("word_allocation", 0x6616))}
            lines.append(f"heap segment={backdrop_segment} offset={backdrop_offset}"
                         f" tail={rle(read_backdrop(60000, 5536))}"
                         f" draw_segment={word(ds + 0xC212)} map_segment={word(ds + 0xC1FE)}"
                         f" sprite_segment={word(ds + 0xC1FA)}"
                         + "".join(f" {key}={value}" for key, value in pointers.items()))
        for name, x, y, shake, enabled in cases:
            mode = "alias" if name.startswith("alias_") else "clear" if name.startswith("clear_") else "level"
            rendered_tiles = tiles if mode == "level" else bytes(len(tiles))
            if mode == "alias":
                rendered_tiles = bytes(1 + i % 174 for i in range(512)) + rendered_tiles[512:]
            write(objects, rendered_tiles)
            write(ds + 0x79E6, b"\x01\x00")
            write(ds + 0x79A6, b"\x00")
            write(ds + 0x208D, b"\x00")
            write(ds + 0xC496, b"\x01")
            write(ds + 0xC49C, bytes([enabled]))
            write(ds + 0x2098, struct.pack("<h", shake))
            if level != 1:
                write(ds + 0x79EA, b"\x63\x63\x64\x64")
            visual = struct.pack("<HH", x, y) + descriptors[4:8]
            write(ds + 0xC21E, visual)
            frame = word(ds + 0x78C2)
            tail_before = read_backdrop(60000, 5536) if level != 1 else b""
            release(1)
            after = wait(2)
            if word(ds + 0x78C2) != frame or read(objects, len(tiles)) != rendered_tiles or read(ds + 0xC21E, 8) != visual:
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
                         + (f" map_mode={mode}"
                            f" tail_before={rle(tail_before)} tail_after={rle(read_backdrop(60000, 5536))}" if level != 1 else "")
                         + f" pixels={rle(pixels)}")
            if name in ("spawn", "fine_x_3", "maximum", "background_off", "lower_right", "clear_bottom_right", "clear_threshold_36", "alias_bottom_right"):
                write_preview(output.with_name(f"{output.stem}_{name}.ppm"), pixels, view_width, 152, palette)
                window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
                subprocess.run(["import", "-window", window,
                                str(output.with_name(f"{output.stem}_{name}.png"))], check=True, timeout=5)
            print(f"original_render={name} frame={frame} camera="
                  f"{globals_['coarse_x'] + globals_['fine_x']},{globals_['coarse_y'] + globals_['fine_y']}"
                  f" indexed_sha256={hashlib.sha256(pixels).hexdigest()}", flush=True)
            release(2)
            regs = wait(1)
        lines.append(f"complete views={len(cases)}")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        for entry, length in HOOKS:
            write(cs + entry, image[entry:entry + length])
        release(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--split-view", action="store_true", help="initialize two-player mode, then isolate its left view")
    parser.add_argument("--level", type=int, choices=(1, 3, 4, 5, 6), default=1)
    parser.add_argument("--intro-seconds", type=float, default=8)
    parser.add_argument("--level-start-seconds", type=float, default=5)
    parser.add_argument("--results-seconds", type=float, default=10)
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
    case_count = len(CASES) if args.level == 1 else len(tall_cases(180, 64, (104, 168)))
    print(f"render_capture_self_check=ok windows={len(WINDOWS)} cases={case_count} live=0"
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
            capture(pid, base, args.out, image, args.split_view, args.level)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", str(args.level),
                "--start-key", "2" if args.split_view else "1",
                "--startup-seconds", "10", "--intro-seconds", str(args.intro_seconds),
                "--level-start-seconds", str(args.level_start_seconds), "--results-seconds", str(args.results_seconds),
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
