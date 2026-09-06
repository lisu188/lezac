#!/usr/bin/env python3
"""Observe monster impact recovery and bomb slot ordering in a private DOSBox child."""

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
import seed_original_level as seeder


WINDOWS = actors.WINDOWS | actors.REWARD_WINDOWS | actors.CORPSE_WINDOWS | {
    0x7496: bytes.fromhex("268a450430e42d0400"),
    0x74B5: bytes.fromhex("03c209c07d44"),
}
# kind, VX, animation delay, raw HP, visual Y, damage source
PROBES = {
    "right_delay3": (1, 2048, 3, 31, 98, "flame"),
    "left_delay3": (1, -2048, 3, 31, 98, "flame"),
    "right_delay1": (1, 2048, 1, 31, 98, "flame"),
    "right_delay4": (1, 2048, 4, 31, 98, "flame"),
    "right_delay7": (1, 2048, 7, 31, 98, "flame"),
    "kind2": (2, 2048, 3, 31, 98, "flame"),
    "kind3": (3, 2048, 3, 31, 98, "flame"),
    "kind4": (4, 2048, 3, 31, 98, "flame"),
    "repeated_ground": (1, 0, 3, 9, 174, "flame"),
    "fatal_air": (1, 2048, 3, 0, 98, "flame"),
    "control_air": (1, 2048, 3, 31, 98, "none"),
}
ORDER_PROBES = {
    "bomb_first": (1, 0, 3, 31, 174, "bomb"),
    "monster_first": (1, 0, 3, 31, 174, "bomb"),
}


def initial_actor(spec):
    kind, vx, delay, hp, y, _ = spec
    start, end = {1: (46, 47) if vx > 0 else (44, 45),
                  2: (40, 42), 3: (50, 52), 4: (54, 56)}[kind]
    raw = bytearray(38)
    raw[0], raw[1], raw[0x14], raw[0x15] = kind, 2, 6 if kind == 1 else 0, 3
    raw[3], raw[4] = (1, 2) if kind == 1 else (kind + 9, kind + 9)
    struct.pack_into("<hhHHH", raw, 6, vx, 0, 0x9a, 0x4e, abs(vx))
    raw[0x16:0x1d] = bytes([start, start, end, delay, delay, 1, 1])
    raw[0x24] = hp
    return raw, start, y


def capture(pid, base, output, image, bomb_order):
    probes = ORDER_PROBES if bomb_order else PROBES
    samples = 25 if bomb_order else 13
    cs, ds = base + (actors.CS << 4), base + (seeder.RUNTIME_DS << 4)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(address, size):
            value = os.pread(mem.fileno(), size, address)
            if len(value) != size:
                raise RuntimeError("short child-memory read")
            return value

        def write(address, value):
            if os.pwrite(mem.fileno(), value, address) != len(value):
                raise RuntimeError("short child-memory write")

        def word(address):
            return struct.unpack("<H", read(address, 2))[0]

        sequence = 0

        def wait(stage):
            nonlocal sequence
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + actors.SCRATCH, 18))
                if marker == stage and flag == 0 and current > sequence:
                    sequence = current
                    if regs[1] - regs[0] != seeder.RUNTIME_DS - actors.CS:
                        raise RuntimeError("unexpected runtime segment relationship")
                    return struct.pack("<6H", *regs).hex()
                time.sleep(0.001)
            raise RuntimeError(f"actor-pass stage {stage} timeout")

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
                at = 0xF400 + (stage - 1) * 0x80
                write(cs + at, actors.trampoline(stage, image))
                write(cs + entry, jump(entry, at))
        finally:
            os.kill(pid, signal.SIGCONT)
        regs = wait(1)
        actual_cs = struct.unpack_from("<H", bytes.fromhex(regs))[0]
        memory_base = cs - (actual_cs << 4)
        objects = memory_base + (word(ds + 0xC1FE) << 4)
        words = memory_base + (word(ds + 0x6614) << 4) + word(ds + 0x6612)
        if word(ds + 0xC204) != 60:
            raise RuntimeError("unexpected level width")
        initial_objects, initial_words = read(objects, 1980), read(words, 3960)
        descriptors = read(ds + 0xC322, 92 * 4)
        mode = "bomb_actor_order" if bomb_order else "monster_damage"
        lines = ["# Seeded original actor-pass probes; no natural-route or pixel-parity claim.",
                 "# executable_sha256=" + hashlib.sha256((Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()).hexdigest(),
                 "# register_order=cs,ds,es,ss,saved-sp,bp little_endian_words=1",
                 f"capture={mode}_original_v1 seeded=1 temp_copy=1 player=240,168 spawners=0",
                 f"sprites descriptors={descriptors.hex()}"]
        for name, spec in probes.items():
            if bomb_order:
                while word(ds + 0x78C2) % 2 != 1:
                    release(1)
                    wait(2)
                    release(2)
                    regs = wait(1)
            # Restore starting terrain only at the case boundary, never between samples.
            write(objects, initial_objects)
            write(words, initial_words)
            write(ds + 0x79A6, bytes(1))
            write(ds + 0x2080, bytes(2))
            write(ds + 0x207E, struct.pack("<H", 199))
            write(ds + 0x208E, bytes(1))
            write(ds + 0xC21E, struct.pack("<HH", 240, 168))
            write(ds + 0x1AFE, struct.pack("<I", 0x12345678))
            monster, sprite, y = initial_actor(spec)
            cell = ((y - monster[0x14]) >> 3) * 60 + 42 + (spec[1] < 0)
            if spec[-1] == "flame":
                write(objects + cell, b"\x75")
            else:
                cell = -1
            write(ds + 0xC21E + 16, struct.pack("<HH", 336, y) + descriptors[sprite * 4:sprite * 4 + 4])
            seeded = [monster]
            if bomb_order:
                bomb = bytearray(38)
                bomb[0], bomb[1], bomb[0x14], bomb[0x15] = 0x0d, 3, 8, 2
                write(ds + 0xC21E + 24, struct.pack("<HH", 336, 176) + descriptors[58 * 4:59 * 4])
                seeded = [bomb, monster] if name == "bomb_first" else [monster, bomb]
            write(ds + 0x208D, bytes([len(seeded)]))
            write(ds + 0xC496, bytes([len(seeded) + 2]))
            for index, raw in enumerate(seeded, 1):
                write(ds + 0x1BAE + 38 * index, raw)
            lines.append(f"case name={name} raw={monster.hex()} x=336 y={y} cell={cell}"
                         f" frame={word(ds + 0x78C2)} rng=12345678 regs={regs}"
                         + (f" bomb={bomb.hex()} bomb_x=336 bomb_y=176" if bomb_order else ""))
            for sample in range(samples):
                frame = word(ds + 0x78C2)
                release(1)
                after_regs = wait(2)
                if word(ds + 0x78C2) != frame:
                    raise RuntimeError("actor pass crossed a frame")
                count = read(ds + 0x208D, 1)[0]
                if count > 30:
                    raise RuntimeError("invalid original actor count")
                target, others = None, []
                for index in range(1, count + 1):
                    raw = read(ds + 0x1BAE + 38 * index, 38)
                    visual = read(ds + 0xC21E + raw[1] * 8, 8)
                    row = raw.hex() + ":" + visual.hex()
                    if raw[1] == 2:
                        if target is not None:
                            raise RuntimeError("duplicate target visual slot")
                        target = row
                    else:
                        others.append(row)
                current_map = read(objects, 1980)
                delta = ",".join(f"{i}:{v:02x}" for i, v in enumerate(current_map) if v != initial_objects[i]) or "-"
                lines.append(f"tick sample={sample} frame={frame} count={count} target={target or '-'}"
                             f" others={','.join(others) or '-'} map={delta}"
                             f" rng={read(ds + 0x1AFE, 4).hex()} regs={after_regs}")
                if name in ("right_delay3", "kind2", "bomb_first", "monster_first") and sample in (1, 4, 8, 12):
                    window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
                    subprocess.run(["import", "-window", window,
                        str(output.with_name(f"{output.stem}_{name}_{sample:03d}.png"))], check=True, timeout=5)
                release(2)
                regs = wait(1)
            lines.append(f"end samples={samples}")
            output.write_text("\n".join(lines) + "\n", encoding="ascii")
            print(f"{mode}_original={name} samples={samples}", flush=True)
        lines.append(f"complete cases={len(probes)}")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        for entry, length in actors.HOOKS:
            write(cs + entry, image[entry:entry + length])
        release(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--bomb-order", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    exe = (Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()
    image = exe[0x770:]
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"instruction mismatch at 1000:{at:04x}")
    for stage in (1, 2):
        actors.trampoline(stage, image)
    print(f"monster_damage_capture_self_check=ok windows={len(WINDOWS)} live=0", flush=True)
    if args.self_check:
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("live capture requires temporary run-dir, out and both approval flags")
    if args.out.exists() or list(args.out.parent.glob(args.out.stem + "_*.png")):
        parser.error("output exists; choose a fresh path")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if (args.run_dir / "LEZAC.EXE").read_bytes() != exe:
        parser.error("temporary executable differs from guarded original")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_MONSTER_DAMAGE_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image, args.bomb_order)
        return original(run_dir, pid, base, state, phase)
    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
