#!/usr/bin/env python3
"""Probe original bomb/spawner allocation with a seeded pool in a private child."""

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


WINDOWS = {
    0x6C0A: bytes.fromhex("807eee04"),
    0x6CA9: bytes.fromhex("c6067b1b00"),
    0x7A6B: bytes.fromhex("803ea67900"),
    0x7C3D: bytes.fromhex("c70682200100"),
    0x7A57: bytes.fromhex("c606e87900"),
    0x2FAD: bytes.fromhex("803e8d201e7203"),
    0x6C5E: bytes.fromhex("833e7220017544"),
    0x7B2B: bytes.fromhex("833e7220017403"),
}


def capture(pid, base, output, image, mode):
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

        def release(stage):
            write(cs + actors.SCRATCH + 14, struct.pack("<H", stage))

        def wait(stage):
            nonlocal sequence
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + actors.SCRATCH, 18))
                if marker and not flag and current > sequence:
                    sequence = current
                    if marker == stage:
                        if regs[1] - regs[0] != seeder.RUNTIME_DS - actors.CS:
                            raise RuntimeError(f"unexpected runtime segments: {regs}")
                        return regs
                    if marker == 3:
                        release(3)
                    else:
                        raise RuntimeError(f"unexpected hook {marker}, wanted {stage}")
                time.sleep(0.001)
            raise RuntimeError(f"capacity stage {stage} timeout: marker={marker} frame={word(ds + 0x78C2)}")

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
        window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
        subprocess.run(["xdotool", "windowfocus", "--sync", window], check=True)
        descriptors = read(ds + 0xC322, 368)
        spawner = bytearray(read(ds + 0x74C6, 30))
        lines = ["# Seeded allocation-boundary probes, not a natural route or pixel-parity claim.",
                 "# register_order=cs,ds,es,ss,saved-sp,bp little_endian_words=1",
                 "# executable_sha256=" + hashlib.sha256((Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()).hexdigest(),
                 f"capture=shared_capacity_original_v1 mode={mode} seeded=1 temp_copy=1 level=1",
                 f"sprites descriptors={descriptors.hex()}"]

        def snapshot(label, regs):
            count = read(ds + 0x208D, 1)[0]
            if count > 30:
                raise RuntimeError("invalid original actor count")
            rows = []
            for slot in range(1, count + 1):
                raw = read(ds + 0x1BAE + slot * 38, 38)
                visual = read(ds + 0xC21E + raw[1] * 8, 8)
                rows.append(raw.hex() + ":" + visual.hex())
            return (f"{label} frame={word(ds + 0x78C2)} count={count} visuals={read(ds + 0xC496, 1)[0]}"
                    f" result={word(ds + 0x2072)} rng={read(ds + 0x1AFE, 4).hex()}"
                    f" inventory={read(ds + 0x1B6C, 4).hex()} selected={read(ds + 0x1B74, 1)[0]}"
                    f" fire={read(ds + 0x1B76, 1)[0]} spawner={read(ds + 0x74C6, 30).hex()}"
                    f" regs={struct.pack('<6H', *regs).hex()} actors={','.join(rows) or '-'}")

        cases = [(f"weapon{weapon}_pool{count}", weapon, count) for weapon in range(1, 5) for count in (0, 29, 30)] if mode == "bomb" else [
            (f"spawner_pool{count}", 0, count) for count in (0, 29, 30)] + [("spawner_pool30_expiring", 0, 30)]
        for name, weapon, count in cases:
            if mode == "bomb":
                subprocess.run(["xdotool", "keydown", "n"], check=True)
            regs = wait(1)
            if mode == "bomb":
                subprocess.run(["xdotool", "keyup", "n"], check=True)
                caller = cs - (regs[0] << 4) + (regs[3] << 4) + regs[5]
                owner = read(caller - 0x1D, 1)[0]
                if owner != 1:
                    raise RuntimeError(f"unexpected bomb owner {owner}")
                write(caller - 0x12, bytes([weapon]))
                launch = [struct.unpack("<h", read(caller + offset, 2))[0] for offset in (-0x2C, -0x2E, -0x0C, -0x0E)]
                write(ds + 0x1B74, bytes([weapon]))
            else:
                launch = [0, 0, 0, 0]
            write(ds + 0x79E6, b"\x01\x00")
            write(ds + 0x79EA, b"\x63\x63\x64\x64")
            write(ds + 0x79A6, bytes([mode == "spawner"]))
            write(ds + 0x208D, bytes([count]))
            write(ds + 0x208E, bytes(1))
            write(ds + 0xC496, bytes([count + 2]))
            write(ds + 0x1BAE + 38, bytes(30 * 38))
            if name.endswith("_expiring"):
                write(ds + 0x78C2, struct.pack("<H", 91))
            for slot in range(1, count + 1):
                filler = bytearray(38)
                filler[1], filler[2], filler[0x15] = slot + 1, 240, 5
                if name.endswith("_expiring") and slot == 1:
                    filler[2] = 1
                write(ds + 0x1BAE + slot * 38, filler)
                write(ds + 0xC21E + (slot + 1) * 8,
                      struct.pack("<HH", 160 + ((slot - 1) % 10) * 12, 88 + ((slot - 1) // 10) * 16) + descriptors[80 * 4:81 * 4])
            write(ds + 0x1AFE, struct.pack("<I", 0x12345678))
            write(ds + 0x2072, bytes(2))
            write(ds + 0x1B6C, bytes([9] * 4))
            write(ds + 0x1B76, bytes(1))
            spawner[8], spawner[9], spawner[10], spawner[27] = 1, 7, 2, 1
            write(ds + 0x74C6, spawner)
            lines.append(f"case name={name} weapon={weapon} count={count} launch={','.join(map(str, launch))}")
            lines.append(snapshot("before", regs))
            release(1)
            after = wait(2)
            lines.append(snapshot("after", after))
            release(2)
            wait(3)
            subprocess.run(["import", "-window", window, str(output.with_name(output.stem + "_" + name + ".png"))], check=True, timeout=5)
            lines.append(f"frame name={name} frame={word(ds + 0x78C2)} count={read(ds + 0x208D, 1)[0]} phase=next_render")
            print(f"shared_capacity_original case={name} captured=1", flush=True)
            if name != cases[-1][0]:
                release(3)
        lines.append(f"complete cases={len(cases)} seeded=1 natural_route=0")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        for entry, _ in actors.HOOKS:
            write(cs + entry, image[entry:entry + 3])
        release(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--mode", choices=("bomb", "spawner"), default="bomb")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    exe = (Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()
    image = exe[0x770:]
    actors.HOOKS = ((0x6C0A, 4), (0x6CA9, 5), (0x7A57, 5)) if args.mode == "bomb" else ((0x7A6B, 5), (0x7C3D, 6), (0x7A57, 5))
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"instruction mismatch at {at:04x}")
    for stage in (1, 2, 3):
        actors.trampoline(stage, image)
    print(f"shared_capacity_capture_self_check=ok windows={len(WINDOWS)} live=0", flush=True)
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
    environment.XVFB_MARKER = "LEZAC_SHARED_CAPACITY_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image, args.mode)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--start-key", "1", "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--results-seconds", "10", "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
