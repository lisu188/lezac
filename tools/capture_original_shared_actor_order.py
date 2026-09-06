#!/usr/bin/env python3
"""Capture continuous mixed actor passes, including stable deletion and appends."""

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
import seed_original_level as seeder


WINDOWS = actors.WINDOWS | actors.REWARD_WINDOWS | {
    0x3358: bytes.fromhex("5589e5b80a00"),
    0x65BF: bytes.fromhex("ff368220e892cdff0e8220"),
    0x33A2: bytes.fromhex("8b46fe406bf826"),
}
CASES = {
    "retire_front": ("expire", "expire2", "bomb", "reward"),
    "retire_back": ("bomb", "reward", "expire", "expire2"),
    "corpse_front_full": ("corpse", "expire", "bomb") + ("filler",) * 27,
    "effect_front_full": ("expire", "corpse", "bomb") + ("filler",) * 27,
    "corpse_bomb_full": ("corpse", "blast", "expire") + ("filler",) * 27,
    "bomb_corpse_full": ("blast", "corpse", "expire") + ("filler",) * 27,
    "two_bombs_full": ("blast", "blast2") + ("filler",) * 28,
    "two_corpses_full": ("corpse", "corpse2") + ("filler",) * 28,
    "mixed_forward": ("effect", "bomb", "reward", "moving_corpse"),
    "mixed_reverse": ("moving_corpse", "reward", "bomb", "effect"),
}
SAMPLES = 41


def seed_actor(kind, slot, descriptors):
    raw = bytearray(38)
    raw[1] = slot + 1
    x, y, sprite = 180 + (slot % 10) * 12, 88 + (slot // 10) * 16, 80
    raw[2], raw[0x15] = 240, 5
    if kind.startswith("expire"):
        raw[2] = 1
    elif kind == "effect":
        x, y, sprite = 300, 100, 70
        raw[0], raw[2] = 11, 15
        struct.pack_into("<hh", raw, 6, 300, -100)
        raw[0x16:0x1d] = bytes([69, 69, 79, 2, 2, 2, 1])
    elif kind in ("bomb", "blast", "blast2"):
        x, y, sprite = 400 if kind != "blast2" else 432, 140, 58
        raw[0], raw[2], raw[0x15] = 13, 1 if kind.startswith("blast") else 100, 2
        if kind == "bomb":
            struct.pack_into("<hh", raw, 6, -190, -300)
        raw[0x1c] = 1
        raw[0x14] = 16 - descriptors[sprite * 4 + 1]
    elif kind == "reward":
        x, y, sprite = 350, 120, 63
        raw[0], raw[2], raw[0x15] = 20, 100, 2
        raw[0x14] = 16 - descriptors[sprite * 4 + 1]
        struct.pack_into("<hh", raw, 6, -90, -200)
    elif "corpse" in kind:
        x, y, sprite = 336 if kind != "corpse2" else 368, 130, 48
        raw[0], raw[2], raw[0x15], raw[0x14] = 12, 25 if kind == "moving_corpse" else 0, 2, 6
        struct.pack_into("<hh", raw, 6, 189, -300)
        raw[0x16:0x1d] = bytes([44, 44, 45, 0, 3, 0, 1])
    if kind not in ("expire", "expire2", "filler"):
        raw[10], raw[12] = 0x9a, 0x4e
    return bytes(raw), struct.pack("<HH", x, y) + descriptors[sprite * 4:sprite * 4 + 4]


def capture(pid, base, output, image):
    cs, ds = base + (actors.CS << 4), base + (seeder.RUNTIME_DS << 4)
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

        def wait(stage):
            nonlocal sequence
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + actors.SCRATCH, 18))
                if marker == stage and not flag and current > sequence:
                    sequence = current
                    if regs[1] - regs[0] != seeder.RUNTIME_DS - actors.CS:
                        raise RuntimeError("unexpected runtime segments")
                    return regs
                time.sleep(0.001)
            raise RuntimeError(f"shared actor stage {stage} timeout")

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
            for stage, (entry, _) in enumerate(actors.HOOKS, 1):
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, actors.trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        finally:
            os.kill(pid, signal.SIGCONT)
        regs = wait(1)
        memory_base = cs - (regs[0] << 4)
        objects = memory_base + (word(ds + 0xC1FE) << 4)
        words = memory_base + (word(ds + 0x6614) << 4) + word(ds + 0x6612)
        if word(ds + 0xC204) != 60:
            raise RuntimeError("unexpected level width")
        initial_map, initial_words = read(objects, 1980), read(words, 3960)
        descriptors = read(ds + 0xC322, 368)
        lines = ["# Seeded case boundaries followed by continuous unseeded original actor passes.",
                 "# register_order=cs,ds,es,ss,saved-sp,bp little_endian_words=1",
                 "# executable_sha256=" + hashlib.sha256((Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()).hexdigest(),
                 "capture=shared_actor_order_original_v1 seeded=1 temp_copy=1 level=1 player=240,168 spawners=0",
                 f"map bytes={initial_map.hex()} words={initial_words.hex()}",
                 f"sprites descriptors={descriptors.hex()}"]

        def actor_rows():
            count = read(ds + 0x208D, 1)[0]
            if count > 30:
                raise RuntimeError("invalid actor count")
            rows = []
            for slot in range(1, count + 1):
                raw = read(ds + 0x1BAE + slot * 38, 38)
                visual = read(ds + 0xC21E + raw[1] * 8, 8)
                rows.append(raw.hex() + ":" + visual.hex())
            return ",".join(rows) or "-"

        for name, kinds in CASES.items():
            write(objects, initial_map)
            write(words, initial_words)
            write(ds + 0x79A6, bytes(1))
            write(ds + 0x79EA, b"\x63\x63\x64\x64")
            write(ds + 0x79E6, b"\x01\x00")
            write(ds + 0x2080, bytes(2))
            write(ds + 0x207E, struct.pack("<H", 199))
            write(ds + 0x2076, bytes(2))
            write(ds + 0x208E, bytes(1))
            write(ds + 0x79F9, bytes(1))
            write(ds + 0x1AFE, struct.pack("<I", 0x12345678))
            write(ds + 0x78C2, struct.pack("<H", 101))
            write(ds + 0xC21E, struct.pack("<HH", 240, 168))
            write(ds + 0x208D, bytes([len(kinds)]))
            write(ds + 0xC496, bytes([len(kinds) + 2]))
            for slot, kind in enumerate(kinds, 1):
                raw, visual = seed_actor(kind, slot, descriptors)
                write(ds + 0x1BAE + slot * 38, raw)
                write(ds + 0xC21E + (slot + 1) * 8, visual)
            lines.append(f"case name={name} frame=101 rng=12345678 samples={SAMPLES} actors={actor_rows()} regs={struct.pack('<6H', *regs).hex()}")
            for sample in range(SAMPLES):
                frame = word(ds + 0x78C2)
                if frame != 101 + sample:
                    raise RuntimeError("nonconsecutive actor pass")
                release(1)
                after = wait(2)
                current_map = read(objects, 1980)
                delta = ",".join(f"{i}:{value:02x}" for i, value in enumerate(current_map) if value != initial_map[i]) or "-"
                lines.append(f"tick sample={sample} frame={frame} count={read(ds + 0x208D, 1)[0]} visuals={read(ds + 0xC496, 1)[0]}"
                             f" rng={read(ds + 0x1AFE, 4).hex()} actors={actor_rows()} map={delta} regs={struct.pack('<6H', *after).hex()}")
                if sample in (1, 10, 30, 40):
                    window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
                    subprocess.run(["import", "-window", window, str(output.with_name(f"{output.stem}_{name}_{sample:03d}.png"))], check=True, timeout=5)
                release(2)
                regs = wait(1)
            lines.append(f"end samples={SAMPLES}")
            output.write_text("\n".join(lines) + "\n", encoding="ascii")
            print(f"shared_actor_order_original case={name} samples={SAMPLES}", flush=True)
        lines.append(f"complete cases={len(CASES)} samples={len(CASES) * SAMPLES}")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        for entry, length in actors.HOOKS:
            write(cs + entry, image[entry:entry + length])
        release(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    exe = (Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()
    image = exe[0x770:]
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"instruction mismatch at {at:04x}")
    for stage in (1, 2):
        actors.trampoline(stage, image)
    print(f"shared_actor_order_capture_self_check=ok windows={len(WINDOWS)} cases={len(CASES)} live=0", flush=True)
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
    environment.XVFB_MARKER = "LEZAC_SHARED_ACTOR_ORDER_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
