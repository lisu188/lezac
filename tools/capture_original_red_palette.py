#!/usr/bin/env python3
"""Capture original VGA palette updates and fixed-view pixels in a private child."""

from __future__ import annotations

import argparse
import hashlib
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


HOOKS = ((0x7A13, 5), (0x81F6, 5))
WINDOWS = {
    0x7A13: bytes.fromhex("803ee67900"),
    0x81F6: bytes.fromhex("803e582073"),
    0x079D: bytes.fromhex("b90600b3e6a0ad7930e4bac803"),
    0x07B8: bytes.fromhex("04073c3f7e02b014fec3e2e6c3"),
    0x81CD: bytes.fromhex("a1c27831d2b90500f7f19209c0751a"),
    0x81DC: bytes.fromhex("e8be85a0ad7930e4050700a2ad79803ead793f7605c606ad7914"),
}
CASES = (("continuous", 71, None, None), ("frame_wrap", 24, 65520, 62),
         ("zero_phase", 16, 0, 0), ("byte_wrap", 11, 0, 250))


def trampoline(stage, image):
    original = actors.trampoline(stage, image)
    target = 0xF400 + (stage - 1) * 0x80
    # Read all 256 DAC triples through the VGA read-index port. General
    # registers/flags are already saved by the enclosing actor trampoline.
    dac = (bytes.fromhex("bac70330c0ee83c202b90003bf")
           + struct.pack("<H", 0xF800 + (stage - 1) * 768)
           + bytes.fromhex("ec2e880547e2f9"))
    code = original[:2] + dac + original[2:-3]
    entry, length = HOOKS[stage - 1]
    code += jump(target + len(code), entry + length)
    if len(code) > 0x80:
        raise RuntimeError("palette trampoline exceeds scratch window")
    return code


def write_preview(path, pixels, dac):
    rgb = bytes(((dac[value * 3 + channel] << 2) | (dac[value * 3 + channel] >> 4)) & 255
                for value in pixels for channel in range(3))
    path.write_bytes(b"P6\n312 152\n255\n" + rgb)


def capture(pid, base, output, image, level):
    cs, ds = base + (actors.CS << 4), base + (seeder.RUNTIME_DS << 4)
    actors.HOOKS = HOOKS
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
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + actors.SCRATCH, 18))
                if initial and marker == 2 and flag == 0:
                    release(2)
                if marker == stage and flag == 0 and current > sequence:
                    sequence = current
                    if regs[1] - regs[0] != seeder.RUNTIME_DS - actors.CS:
                        raise RuntimeError("unexpected runtime segments")
                    return regs
                time.sleep(0.001)
            raise RuntimeError(f"palette stage {stage} timeout marker={marker} flag={flag} sequence={current}")

        def release(stage):
            write(cs + actors.SCRATCH + 14, struct.pack("<H", stage))

        for at, expected in WINDOWS.items():
            if read(cs + at, len(expected)) != expected:
                raise RuntimeError(f"runtime instruction mismatch at {at:04x}")
        if read(cs + 0xF400, 0xA00) != bytes(0xA00):
            raise RuntimeError("palette scratch is not empty")
        os.kill(pid, signal.SIGSTOP)
        try:
            deadline = time.monotonic() + 2
            while "State:\tT" not in Path(f"/proc/{pid}/status").read_text():
                if time.monotonic() > deadline:
                    raise RuntimeError("child did not stop")
                time.sleep(0.001)
            for stage, (entry, _) in enumerate(HOOKS, 1):
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        finally:
            os.kill(pid, signal.SIGCONT)
        regs = wait(1, initial=True)
        memory_base = cs - (regs[0] << 4)
        objects = memory_base + (word(ds + 0xC1FE) << 4)
        width = word(ds + 0xC204)
        height = word(ds + 0x2096) // 8 + 21
        if (width, height) != ((60, 33) if level == 1 else (100, 58)) or word(ds + 0xC1EC) != 320:
            raise RuntimeError("unexpected palette level/view dimensions")
        tiles = read(objects, width * height)
        backdrop = read(memory_base + (word(ds + 0xC49A) << 4) + word(ds + 0xC498), 60000)
        descriptors = read(ds + 0xC322, 368)
        x, y = (104, 168) if level == 1 else (248, 360)
        visual = struct.pack("<HH", x, y) + descriptors[4:8]
        lines = ["# Seeded fixed render state; natural palette cadence plus explicit byte/frame edge cases.",
                 f"capture=red_palette_original_v1 level={level} seeded=1 temp_copy=1 before=7a13 after=81f6 pitch=320 active_visuals=1",
                 "# executable_sha256=" + hashlib.sha256((Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()).hexdigest(),
                 f"map width={width} height={height} bytes={tiles.hex()}",
                 f"backdrop bytes={render.rle(backdrop)}", f"sprites descriptors={descriptors.hex()}"]
        indexed = None
        for name, samples, seed_frame, seed_phase in CASES:
            if seed_frame is not None:
                write(ds + 0x78C2, struct.pack("<H", seed_frame))
                write(ds + 0x79AD, bytes([seed_phase]))
            lines.append(f"case name={name} samples={samples} seeded={int(seed_frame is not None)}"
                         f" frame={word(ds + 0x78C2)} phase={read(ds + 0x79AD, 1)[0]}")
            for sample in range(samples):
                write(objects, tiles)
                write(ds + 0x79E6, b"\x01\x00")
                write(ds + 0x79A6, b"\x00")
                write(ds + 0x208D, b"\x00")
                write(ds + 0xC496, b"\x01")
                write(ds + 0xC49C, b"\x01")
                write(ds + 0x2098, b"\x00\x00")
                write(ds + 0x79EA, b"\x63\x63\x64\x64")
                write(ds + 0xC21E, visual)
                frame = word(ds + 0x78C2)
                phase = read(ds + 0x79AD, 1)[0]
                before_dac = read(cs + 0xF800, 768)
                release(1)
                after = wait(2)
                if word(ds + 0x78C2) != frame:
                    raise RuntimeError("palette boundary changed frame")
                after_dac = read(cs + 0xFB00, 768)
                after_phase = read(ds + 0x79AD, 1)[0]
                buffer = memory_base + (word(ds + 0xC212) << 4)
                source = word(ds + 0xC214) + word(ds + 0xC20A) + word(ds + 0xC20C) * 320
                pixels = b"".join(read(buffer + source + row * 320, 312) for row in range(152))
                if len(set(pixels)) < 16:
                    raise RuntimeError("palette probe did not capture a varied gameplay view")
                if indexed is None:
                    indexed = pixels
                    lines.append(f"view x={x} y={y} sprite=0 shake=0 pixels={render.rle(indexed)}")
                elif pixels != indexed:
                    raise RuntimeError(f"palette probe indexed view changed at {name}:{sample}")
                lines.append(f"sample case={name} index={sample} frame={frame} before_phase={phase} after_phase={after_phase}"
                             f" before_regs={struct.pack('<6H', *regs).hex()} after_regs={struct.pack('<6H', *after).hex()}"
                             f" before_dac={before_dac.hex()} after_dac={after_dac.hex()}"
                             f" indexed_sha256={hashlib.sha256(pixels).hexdigest()}")
                if sample in (0, samples - 1) or (name == "continuous" and sample in (4, 5, 34, 35)):
                    stem = output.with_name(f"{output.stem}_{name}_{sample:03d}")
                    write_preview(stem.with_suffix(".ppm"), pixels, after_dac)
                    window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
                    subprocess.run(["import", "-window", window, str(stem.with_suffix(".png"))], check=True, timeout=5)
                print(f"original_palette={name} sample={sample} frame={frame} phase={phase}->{after_phase}"
                      f" red_dac={after_dac[690:708].hex()}", flush=True)
                release(2)
                regs = wait(1)
        lines.append(f"complete cases={len(CASES)} samples={sum(case[1] for case in CASES)}")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        for entry, length in HOOKS:
            write(cs + entry, image[entry:entry + length])
        release(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--level", type=int, choices=(1, 4), default=4)
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
        trampoline(stage, image)
    print(f"palette_capture_self_check=ok windows={len(WINDOWS)} cases={len(CASES)} samples={sum(case[1] for case in CASES)} live=0", flush=True)
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
    environment.XVFB_MARKER = "LEZAC_RED_PALETTE_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image, args.level)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", str(args.level),
                "--start-key", "1", "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--results-seconds", "10", "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
