#!/usr/bin/env python3
"""Capture one original collapse update for explicitly seeded local probes.

Only the temporary DOSBox child is instrumented. Guarded entry/return
trampolines preserve the original instructions and registers. These are
routine-level experiments, not natural gameplay or pixel-parity evidence.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import signal
import struct
import sys
import time

import capture_original_behavior4_lockstep as environment
from capture_original_bomb_fuses import jump
import seed_original_level as seeder


CS = 0x01ED
START, END = 0x5110, 0x567F
SCRATCH = 0xF600
WINDOWS = {
    START: bytes.fromhex("a180208946fea104c2d1e0a36620"),
    END: bytes.fromhex("837efe007403e996fa"),
    0x5571: bytes.fromhex("833e72203f7703e98700"),
}


def trampoline(stage: int, image: bytes) -> bytes:
    at = 0xF400 + 0x80 * (stage - 1)
    code = bytearray(b"\x9c\x60")
    skip = None
    if stage == 2:
        # Stop only after the final record; replay the loop condition below.
        code += bytes.fromhex("837efe007500")
        skip = len(code) - 1
    for index, op in enumerate(("8cc8", "8cd8", "8cc0", "8cd0", "89e0", "89e8")):
        code += bytes.fromhex(op) + b"\x2e\xa3" + struct.pack("<H", SCRATCH + 2 + 2 * index)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, stage)
    code += b"\x2e\x83\x3e" + struct.pack("<H", SCRATCH + 14) + bytes([stage]) + b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, 0)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH + 14, 0)
    if skip is not None:
        code[skip] = len(code) - skip - 1
    code += b"\x61\x9d"
    entry, length = (START, 3) if stage == 1 else (END, 4)
    code += image[entry:entry + length]
    code += jump(at + len(code), entry + length)
    if len(code) > 0x80:
        raise RuntimeError("trampoline exceeds scratch window")
    return bytes(code)


def record(first: int, last: int, word: int = 0x8009, vx: int = 0, vy: int = 0,
           sx: int = 0, sy: int = 0, flags: int = 0, rest: int = 0,
           magnitude: int | None = None, weight: int = 4) -> bytes:
    return struct.pack("<HHHbbbbHBBB", first * 2, last * 2, word, vx, vy, sx, sy,
                       abs(vx) + abs(vy) if magnitude is None else magnitude,
                       flags, rest, weight)


@dataclass
class Probe:
    name: str
    collapse: list[bytes]
    cells: dict[int, tuple[int, int]]
    debris: list[bytes]


def probes(width: int) -> list[Probe]:
    first = 20 * width + 23
    result = []
    variants = (
        ("rest", {}), ("rest94", {"rest": 94}), ("rest95", {"rest": 95}),
        ("rest255", {"rest": 255}), ("air", {}),
        ("air122", {"vy": 122}), ("air123", {"vy": 123}),
        ("right", {"vx": 40, "sx": 100}),
        ("left", {"vx": -40, "sx": -100}),
        ("up", {"vy": -40, "sy": -100, "flags": 0x83}),
        ("down", {"vy": 40, "sy": 100}),
        ("blocked_down63", {"vy": 63, "sy": 100}),
        ("blocked_down64", {"vy": 64, "sy": 100}),
        ("blocked_x", {"vx": 40, "sx": 100}),
        ("tip_left", {}), ("tip_right", {}),
        ("tip_left_latched", {"flags": 2}), ("tip_right_latched", {"flags": 1}),
        ("tip_left_blocked", {}), ("cascade_x", {"vx": 40, "sx": 100}),
        ("cascade_x_skip", {"vx": 40, "sx": 100, "flags": 0x80}),
        ("cascade_y", {"vy": 40, "sy": 100}),
        ("new_debris", {"vx": 40, "sx": 100}),
        ("new_collapse", {"vx": 40, "sx": 100}),
        ("live_debris", {"vx": 40, "sx": 100}),
        ("live_collapse", {"vx": 40, "sx": 100}),
        ("double_retire", {"rest": 94}),
    )
    for name, args in variants:
        cells = {y * width + x: (1 if y == 21 else 0, 0)
                 for y in range(17, 24) for x in range(19, 31)}
        cells[first] = (0x50, 0x8009)
        cells[first + 1] = (0x51, 0x8009)
        records = [record(first, first + 1, **args)]
        debris = []
        if name.startswith("air") or name in ("down", "cascade_y"):
            cells[first + width] = cells[first + width + 1] = (0, 0)
        if name.startswith("tip_left"):
            cells[first + width] = (0, 0)
        if name.startswith("tip_right"):
            cells[first + width + 1] = (0, 0)
        if name == "tip_left_blocked":
            cells[first - 1] = (1, 0)
        if name == "blocked_x":
            cells[first + 2] = (1, 0)
        if name.startswith("cascade_"):
            cells[first - width] = (0x50, 10)
        if name in ("new_debris", "new_collapse", "live_debris", "live_collapse"):
            high = name.endswith("debris")
            live = name.startswith("live")
            word = (0x4002 if high else 10) | (0x8000 if live else 0)
            cells[first + 2] = (0x60, word)
            if live and high:
                debris.append(struct.pack("<HHbbbbBBB", first + 2, word, -20, 0, 0, 0, 0, 0x60, 0))
            elif live:
                records.insert(0, record(first + 2, first + 2, word, vx=-20, weight=2))
        if name == "double_retire":
            cells[first + 4] = (0x50, 0x800a)
            records.append(record(first + 4, first + 4, 0x800a, rest=94, weight=2))
        result.append(Probe(name, records, cells, debris))
    return result


def capture(run_dir: Path, pid: int, base: int, output: Path, image: bytes) -> None:
    cs, ds = base + (CS << 4), base + (seeder.RUNTIME_DS << 4)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(address: int, count: int) -> bytes:
            data = os.pread(mem.fileno(), count, address)
            if len(data) != count:
                raise RuntimeError("short child-memory read")
            return data

        def write(address: int, data: bytes) -> None:
            if os.pwrite(mem.fileno(), data, address) != len(data):
                raise RuntimeError("short child-memory write")

        def word(address: int) -> int:
            return struct.unpack("<H", read(address, 2))[0]

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

        def wait(stage: int) -> bytes:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if word(cs + SCRATCH) == stage and word(cs + SCRATCH + 14) == 0:
                    return read(cs + SCRATCH + 2, 12)
                time.sleep(0.001)
            raise RuntimeError(f"collapse stage {stage} timeout; marker={word(cs + SCRATCH)}")

        for at, expected in WINDOWS.items():
            if read(cs + at, len(expected)) != expected:
                raise RuntimeError(f"runtime instruction mismatch at {at:04x}")
        if read(cs + 0xF400, 0x210) != bytes(0x210):
            raise RuntimeError("instrumentation scratch is not empty")

        def install() -> None:
            for stage, at in ((1, START), (2, END)):
                write(cs + 0xF400 + 0x80 * (stage - 1), trampoline(stage, image))
                write(cs + at, jump(at, 0xF400 + 0x80 * (stage - 1)))
            write(ds + 0x2080, struct.pack("<H", 1))
        stopped(install)
        regs = wait(1)
        actual_cs, actual_ds = struct.unpack_from("<HH", regs)
        if actual_ds - actual_cs != seeder.RUNTIME_DS - CS:
            raise RuntimeError("unexpected runtime segments")
        memory_base = cs - (actual_cs << 4)
        objects = memory_base + (word(ds + 0xC1FE) << 4)
        words = memory_base + (word(ds + 0x6614) << 4) + word(ds + 0x6612)
        width = word(ds + 0xC204)
        if width != 60:
            raise RuntimeError("unexpected level width")
        lines = ["# Seeded original collapse routine, not natural-route evidence.",
                 f"# executable_sha256={hashlib.sha256((run_dir / 'LEZAC.EXE').read_bytes()).hexdigest()}",
                 f"# freeze=1000:{START:04x},1000:{END:04x} runtime_cs={actual_cs:04x} runtime_ds={actual_ds:04x}",
                 "# register_order=cs,ds,es,ss,saved-sp,bp little_endian_words=1",
                 "capture=collapse_steps_original_v1 seeded=1 temp_copy=1 visual_claim=0"]
        for probe in probes(width):
            for cell, (tile, key) in probe.cells.items():
                write(objects + cell, bytes([tile]))
                write(words + 2 * cell, struct.pack("<H", key))
            write(ds + 0x2080, struct.pack("<H", len(probe.collapse)))
            write(ds + 0x6620, b"".join(probe.collapse) + bytes(60))
            write(ds + 0x207E, struct.pack("<H", 199 + len(probe.debris)))
            write(ds + 0x292B, b"".join(probe.debris) + bytes(66))
            write(ds + 0x1AFE, struct.pack("<I", 0x12345678))
            write(ds + 0x78C4, struct.pack("<H", 0x4000))
            write(ds + 0x78C8, bytes(2))
            before_actor_count = read(ds + 0x208D, 1)[0]
            before_regs = read(cs + SCRATCH + 2, 12)
            def map_state() -> str:
                return ",".join(f"{cell}:{read(objects + cell, 1).hex()}:{word(words + 2 * cell):04x}"
                                for cell in probe.cells)
            before_cells = map_state()
            write(cs + SCRATCH + 14, struct.pack("<H", 1))
            after_regs = wait(2)
            nc, nd = word(ds + 0x2080), word(ds + 0x207E) - 199
            if not 0 <= nc <= 5 or not 0 <= nd <= 6:
                raise RuntimeError("unexpected output queue count")
            encode = lambda records: ",".join(r.hex() for r in records) or "none"
            after_collapse = [read(ds + 0x6620 + 15 * i, 15) for i in range(nc)]
            after_debris = [read(ds + 0x292B + 11 * i, 11) for i in range(nd)]
            actor_count = read(ds + 0x208D, 1)[0]
            actors = [read(ds + 0x1BAE + 38 * i, 38) for i in range(before_actor_count + 1, actor_count + 1)]
            lines.append(" ".join((f"case={probe.name} width={width} tick={word(ds + 0x78C2)}",
                f"before_regs={before_regs.hex()} after_regs={after_regs.hex()}",
                f"cells={before_cells} after_cells={map_state()}",
                f"collapse={encode(probe.collapse)} debris={encode(probe.debris)}",
                f"after_collapse={encode(after_collapse)} after_debris={encode(after_debris)}",
                f"rng={read(ds + 0x1AFE, 4).hex()} destroyed={word(ds + 0x78C8)}",
                f"next_word={word(ds + 0x78C4):04x} new_actors={encode(actors)}")))
            print(f"collapse_step_original={probe.name} collapse={nc} debris={nd} destroyed={word(ds + 0x78C8)}", flush=True)
            # Avoid running the seeded actors and map through the rest of the
            # loop between probes; the next stop precedes reading the count.
            write(ds + 0x2080, struct.pack("<H", 1))
            write(ds + 0x207E, struct.pack("<H", 199))
            write(ds + 0x208D, bytes([before_actor_count]))
            write(cs + SCRATCH + 14, struct.pack("<H", 2))
            wait(1)
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        # Entry's caller was already taken with count=1, so run one valid
        # harmless record on release instead of entering the zero-count loop.
        write(ds + 0x6620, record(20 * width + 23, 20 * width + 24))
        def resume() -> None:
            write(cs + START, image[START:START + 3])
            write(cs + END, image[END:END + 3])
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
    image = (Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()[0x770:]
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"instruction mismatch at 1000:{at:04x}")
    for stage in (1, 2):
        trampoline(stage, image)
    print(f"collapse_steps_capture_self_check=ok windows={len(WINDOWS)} probes={len(probes(60))} live=0", flush=True)
    if args.self_check:
        return 0
    if not (args.approve_procmem and args.approve_runtime_instrumentation and args.run_dir and args.out):
        parser.error("live capture requires a temporary run-dir, out and both approval flags")
    if args.out.exists():
        parser.error("output already exists")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_COLLAPSE_STEPS_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot
    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(run_dir, pid, base, args.out, image)
        return original(run_dir, pid, base, state, phase)
    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
