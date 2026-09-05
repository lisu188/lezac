#!/usr/bin/env python3
"""Capture one original loop-2 tick per explicitly seeded collision.

The temporary DOSBox child is stopped at 1000:492F and 1000:4D3A by
guarded CS trampolines. No helper or physics instruction is changed. Inputs
are artificial, not a natural bomb route or a visual-parity claim.
"""

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
import seed_original_level as seeder


CS = 0x01ED
START, END = 0x492F, 0x4D3A
START_BODY, END_BODY, SCRATCH = 0xF400, 0xF480, 0xF500
WINDOWS = {
    START: bytes.fromhex("c746fec700813e7e20c8007303e9fb03"),
    END: bytes.fromhex("c9c3c70674201027"),
    0x3BB2: bytes.fromhex("5589e5b810009adf04"),
    0x3D46: bytes.fromhex("5589e5b810009adf04"),
}


def jump(at: int, target: int) -> bytes:
    return b"\xe9" + struct.pack("<H", (target - at - 3) & 0xFFFF)


def trampoline(stage: int, at: int) -> bytes:
    code = bytearray()
    # Record actual CS/DS/ES/SS/SP/BP before publishing the stage marker.
    for index, op in enumerate(("8cc8", "8cd8", "8cc0", "8cd0", "89e0", "89e8")):
        code += bytes.fromhex(op) + b"\x2e\xa3" + struct.pack("<H", SCRATCH + 2 + 2 * index)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, stage)
    # Immutable polling code: release by changing data, never the instruction
    # currently being fetched by the emulator.
    code += b"\x2e\x83\x3e" + struct.pack("<H", SCRATCH + 14) + bytes([stage])
    code += b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH + 14, 0)
    if stage == 1:
        code += WINDOWS[START][:5]
    code += jump(at + len(code), START + 5 if stage == 1 else END)
    return bytes(code)


def check_image(exe: Path) -> bytes:
    image = exe.read_bytes()[0x770:]
    for offset, expected in WINDOWS.items():
        if image[offset:offset + len(expected)] != expected:
            raise RuntimeError(f"original instruction mismatch: 1000:{offset:04x}")
    print("debris_impacts_capture_self_check=ok windows=4 seeded=1 live=0", flush=True)
    return image


def record(tile: int, word: int, vx: int, vy: int, sx: int = 0) -> bytes:
    return struct.pack("<HHbbbbBBB", tile, word, vx, vy, sx, 0, 0, 0x60, 0)


def capture(run_dir: Path, pid: int, base: int, output: Path, image: bytes) -> None:
    ds = base + (seeder.RUNTIME_DS << 4)
    cs = base + (CS << 4)
    start_body = trampoline(1, START_BODY)
    end_body = trampoline(2, END_BODY)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(address: int, count: int) -> bytes:
            mem.seek(address)
            value = mem.read(count)
            if len(value) != count:
                raise RuntimeError("short child-memory read")
            return value

        def write(address: int, value: bytes) -> None:
            mem.seek(address)
            if mem.write(value) != len(value):
                raise RuntimeError("short child-memory write")

        def u16(address: int) -> int:
            return struct.unpack("<H", read(address, 2))[0]

        def wait_stage(stage: int) -> bytes:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if u16(cs + SCRATCH) == stage:
                    time.sleep(0.02)
                    registers = read(cs + SCRATCH + 2, 12)
                    actual_cs, actual_ds = struct.unpack_from("<HH", registers)
                    if actual_ds - actual_cs != seeder.RUNTIME_DS - CS:
                        raise RuntimeError(f"trampoline runtime segment mismatch: {registers.hex()}")
                    return registers
                time.sleep(0.001)
            subprocess.run(["xdotool", "key", "ctrl+F5"], check=True)
            time.sleep(1)
            raise RuntimeError(
                f"original did not reach stage {stage}: marker={u16(cs + SCRATCH)} "
                f"frame={u16(ds + 0x78C2)} entry={read(cs + START, 8).hex()} "
                f"body={read(cs + START_BODY, len(start_body)).hex()}")

        def stopped(action) -> None:
            os.kill(pid, signal.SIGSTOP)
            try:
                deadline = time.monotonic() + 2
                while "State:\tT" not in Path(f"/proc/{pid}/status").read_text():
                    if time.monotonic() > deadline:
                        raise RuntimeError("child did not stop")
                    time.sleep(0.001)
                action()
            finally:
                os.kill(pid, signal.SIGCONT)

        for offset, expected in WINDOWS.items():
            if read(cs + offset, len(expected)) != expected:
                raise RuntimeError(f"runtime instruction mismatch: {CS:04x}:{offset:04x}")
        if read(cs + START_BODY, 0x120) != bytes(0x120):
            raise RuntimeError("trampoline scratch is not empty")

        def install() -> None:
            write(cs + START_BODY, start_body)
            write(cs + END_BODY, end_body)
            write(cs + SCRATCH, bytes(16))
            write(cs + START, jump(START, START_BODY))
            # Make the update eligible even if the caller gates empty queues.
            write(ds + 0x207E, struct.pack("<H", 200))
            write(ds + 0x292B, record(20 * 60 + 23, 0xC001, 0, 0))
        stopped(install)
        initial_registers = wait_stage(1)
        stopped(lambda: write(cs + END, jump(END, END_BODY)))
        actual_cs, actual_ds = struct.unpack_from("<HH", initial_registers)
        memory_base = cs - (actual_cs << 4)
        print(f"debris_impact_segments cs={actual_cs:04x} ds={actual_ds:04x} regs={initial_registers.hex()}", flush=True)
        width = u16(ds + 0xC204)
        if width != 60:
            raise RuntimeError(f"unexpected level-1 width {width}")
        objects = memory_base + (u16(ds + 0xC1FE) << 4)
        words = memory_base + (u16(ds + 0x6614) << 4) + u16(ds + 0x6612)
        cells = [y * width + x for y in range(18, 23) for x in range(20, 29)]
        caller = 20 * width + 23
        cases = (
            ("debris_positive", 1, 50, -40, "debris", -20, 20, 1),
            ("debris_negative", -1, -50, -41, "debris", 20, 20, 1),
            ("debris_zero_round", 1, 2, -1, "debris", 0, 0, 1),
            ("debris_bounce_before_blend", 1, 50, 60, "debris", -20, 20, 1),
            ("collapse_unsigned_weight", 1, 50, -40, "collapse", -20, 20, 255),
            ("collapse_negative_round", -1, -50, -41, "collapse", 3, 2, 14),
            ("new_debris", 1, 50, -40, "new_debris", 0, 0, 1),
            ("new_collapse", 1, 50, -40, "new_collapse", 0, 0, 2),
            ("newest_debris_match", 1, 50, -40, "duplicate", -20, 20, 1),
        )
        lines = [
            "# Seeded original DOSBox loop-2 collisions; not natural-route evidence.",
            f"# executable_sha256={hashlib.sha256((run_dir / 'LEZAC.EXE').read_bytes()).hexdigest()}",
            f"# freeze=1000:492f,1000:4d3a runtime_cs={actual_cs:04x} runtime_ds={actual_ds:04x}",
            "# register_order=cs,ds,es,ss,sp,bp little_endian_words=1",
            "capture=debris_impacts_original_v1 seeded=1 temp_copy=1 visual_claim=0",
        ]

        def snapshot_cells() -> str:
            return ",".join(f"{cell}:{read(objects + cell, 1).hex()}:{u16(words + 2 * cell):04x}" for cell in cells)

        for name, direction, vx, vy, kind, other_x, other_y, weight in cases:
            target = caller + direction
            high = kind not in ("collapse", "new_collapse")
            word = 0x4002 if high else 9
            seeded = kind.startswith("new_")
            debris = [record(caller, 0xC001, vx, vy, 127 if direction > 0 else -128)]
            collapse = []
            if not seeded:
                if high:
                    debris.append(record(target, word | 0x8000, 99 if kind == "duplicate" else other_x, 0 if kind == "duplicate" else other_y))
                    if kind == "duplicate":
                        debris.append(record(caller + 4, word | 0x8000, other_x, other_y))
                else:
                    collapse.append(struct.pack("<HHHbbHHBBB", target * 2, target * 2, word | 0x8000, other_x, other_y, 0, 0, 0, 0, weight))
            for cell in cells:
                write(objects + cell, b"\x01" if cell // width == 21 else b"\x00")
                write(words + 2 * cell, bytes(2))
            write(objects + caller, b"\x60")
            write(words + 2 * caller, struct.pack("<H", 0xC001))
            write(objects + target, b"\x60")
            write(words + 2 * target, struct.pack("<H", word if seeded else word | 0x8000))
            if kind == "duplicate":
                write(objects + caller + 4, b"\x60")
                write(words + 2 * (caller + 4), struct.pack("<H", word | 0x8000))
            write(ds + 0x207E, struct.pack("<H", 199 + len(debris)))
            write(ds + 0x2080, struct.pack("<H", len(collapse)))
            write(ds + 0x292B, b"".join(debris) + bytes(44))
            write(ds + 0x6620, b"".join(collapse) + bytes(30))
            write(ds + 0x1AFE, struct.pack("<I", 0x12345678))
            before_cells = snapshot_cells()
            before_registers = read(cs + SCRATCH + 2, 12)
            write(cs + SCRATCH + 14, struct.pack("<H", 1))
            after_registers = wait_stage(2)
            count = u16(ds + 0x207E) - 199
            collapse_count = u16(ds + 0x2080)
            if not 1 <= count <= 4 or not 0 <= collapse_count <= 1:
                raise RuntimeError("unexpected output queue count")
            after_debris = [read(ds + 0x292B + 11 * i, 11).hex() for i in range(count)]
            if after_debris[0] == debris[0].hex():
                raise RuntimeError(f"{name}: no mover progress; capture rejected")
            after_collapse = [read(ds + 0x6620 + 15 * i, 15).hex() for i in range(collapse_count)]
            lines.append(" ".join((
                f"case={name}", f"width={width}", "tick=" + str(u16(ds + 0x78C2)),
                "before_regs=" + before_registers.hex(), "after_regs=" + after_registers.hex(),
                "cells=" + before_cells, "after_cells=" + snapshot_cells(),
                "debris=" + ",".join(r.hex() for r in debris),
                "collapse=" + (",".join(r.hex() for r in collapse) or "none"),
                "after_debris=" + ",".join(after_debris),
                "after_collapse=" + (",".join(after_collapse) or "none"),
                "rng=" + read(ds + 0x1AFE, 4).hex(),
            )))
            print(f"debris_impact_original={name} after={','.join(after_debris)} regs={after_registers.hex()}", flush=True)
            write(ds + 0x207E, struct.pack("<H", 200))
            write(ds + 0x2080, bytes(2))
            def release_end() -> None:
                write(cs + END, image[END:END + 3])
                write(cs + SCRATCH + 14, struct.pack("<H", 2))
            stopped(release_end)
            wait_stage(1)
            stopped(lambda: write(cs + END, jump(END, END_BODY)))
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        # Resume the untouched game so the outer capture gets a real frame.
        def resume() -> None:
            write(cs + END, image[END:END + 3])
            write(cs + START, image[START:START + 3])
            write(cs + SCRATCH + 14, struct.pack("<H", 1))
        stopped(resume)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    image = check_image(Path(__file__).resolve().parent.parent / "LEZAC.EXE")
    if args.self_check:
        return 0
    if not (args.approve_procmem and args.approve_runtime_instrumentation and args.run_dir and args.out):
        parser.error("live capture requires a temporary run-dir, out and both approval flags")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    # The shared Xvfb wrapper re-executes this script, not the behavior-4 tool.
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_DEBRIS_IMPACTS_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(run_dir, pid, base, args.out, image)
        return original(run_dir, pid, base, state, phase)
    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
