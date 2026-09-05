#!/usr/bin/env python3
"""Observe seeded corpse expiry and its effects in a private DOSBox child."""

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
from capture_original_bomb_fuses import jump
import seed_original_level as seeder


CS = 0x01ED
SCRATCH = 0xF600
HOOKS = ((0x7EC5, 6), (0x7EEA, 5))
WINDOWS = {
    0x7EC5: bytes.fromhex("c70682200100"),
    0x7EEA: bytes.fromhex("803ee67901"),
    0x766D: bytes.fromhex("6a649aa813"),
    0x772A: bytes.fromhex("ff76d4ff76d2685802"),
    0x65A2: bytes.fromhex("807ecf057532a1c278250100"),
    0x2FAD: bytes.fromhex("803e8d201e7203"),
    0x7A6B: bytes.fromhex("803ea67900"),
}
PROBES = (
    ("reward_even", 0x90E25B93, 1, 0),
    ("reward_odd", 0x90E25B93, 1, 1),
    ("no_reward_even", 0, 1, 0),
    ("no_reward_odd", 0, 1, 1),
    ("reward_pool29", 0x90E25B93, 29, 1),
    ("reward_pool30", 0x90E25B93, 30, 1),
    ("no_reward_pool30", 0, 30, 1),
    ("no_reward_fraction", 0, 1, 1),
)


def trampoline(stage: int, image: bytes) -> bytes:
    target = 0xF400 + (stage - 1) * 0x80
    code = bytearray(b"\x9c\x60")
    for i, op in enumerate(("8cc8", "8cd8", "8cc0", "8cd0", "89e0", "89e8")):
        code += bytes.fromhex(op) + b"\x2e\xa3" + struct.pack("<H", SCRATCH + 2 + i * 2)
    code += b"\x2e\xff\x06" + struct.pack("<H", SCRATCH + 16)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, stage)
    code += b"\x2e\x83\x3e" + struct.pack("<H", SCRATCH + 14) + bytes([stage]) + b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, 0)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH + 14, 0)
    entry, length = HOOKS[stage - 1]
    code += b"\x61\x9d" + image[entry:entry + length]
    code += jump(target + len(code), entry + length)
    if len(code) > 0x80:
        raise RuntimeError("trampoline exceeds scratch window")
    return bytes(code)


def capture(pid: int, base: int, output: Path, image: bytes) -> None:
    cs, ds = base + (CS << 4), base + (seeder.RUNTIME_DS << 4)
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
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + SCRATCH, 18))
                if marker == stage and flag == 0 and current > sequence:
                    sequence = current
                    if regs[1] - regs[0] != seeder.RUNTIME_DS - CS:
                        raise RuntimeError("unexpected runtime segments")
                    return struct.pack("<6H", *regs).hex()
                time.sleep(0.001)
            raise RuntimeError(f"actor-pass stage {stage} timeout")

        def release(stage):
            write(cs + SCRATCH + 14, struct.pack("<H", stage))

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
                write(cs + target, trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        finally:
            os.kill(pid, signal.SIGCONT)
        regs = wait(1)
        write(ds + 0x79A6, bytes(1))
        lines = ["# Seeded original actor-pass probes; no natural-route or pixel-parity claim.",
                 "# executable_sha256=" + hashlib.sha256((Path(__file__).resolve().parent.parent / "LEZAC.EXE").read_bytes()).hexdigest(),
                 "# register_order=cs,ds,es,ss,saved-sp,bp little_endian_words=1",
                 "capture=death_transients_original_v1 seeded=1 temp_copy=1 spawners=0 player=240,168",
                 f"sprites descriptors={read(ds + 0xC322, 92 * 4).hex()}"]
        for name, seed, count, parity in PROBES:
            while word(ds + 0x78C2) % 2 != parity:
                release(1)
                wait(2)
                release(2)
                regs = wait(1)
            corpse = bytearray.fromhex("0c0200010200000000000000000023010000000006022c2c2dff030001000000000000000101")
            if name == "no_reward_fraction":
                corpse[10], corpse[12] = 0x9a, 0x4e
            filler = bytearray(38)
            filler[2] = 240
            filler[0x15] = 5
            write(ds + 0x208D, bytes([count]))
            write(ds + 0x208E, bytes(1))
            write(ds + 0xC496, bytes([count + 2]))
            write(ds + 0x1BAE + 38, corpse)
            write(ds + 0xC21E + 16, struct.pack("<HH", 336, 174) + read(ds + 0xC322 + 48 * 4, 4))
            for slot in range(2, count + 1):
                filler[1] = slot + 1
                write(ds + 0x1BAE + slot * 38, filler)
                write(ds + 0xC21E + (slot + 1) * 8,
                      struct.pack("<HH", 440, 240) + read(ds + 0xC322 + 80 * 4, 4))
            write(ds + 0x1AFE, struct.pack("<I", seed))
            write(ds + 0x2080, bytes(2))
            write(ds + 0x207E, struct.pack("<H", 199))
            write(ds + 0xC21E, struct.pack("<HH", 240, 168))
            lines.append(f"case name={name} rng={seed:08x} count={count} parity={parity}"
                         f" corpse={corpse.hex()} x=336 y=174 regs={regs}")
            for sample in range(41):
                frame = word(ds + 0x78C2)
                release(1)
                after_regs = wait(2)
                if word(ds + 0x78C2) != frame:
                    raise RuntimeError("actor pass crossed a frame")
                actor_count = read(ds + 0x208D, 1)[0]
                if actor_count > 30:
                    raise RuntimeError("actor count exceeds original pool")
                effects, rewards = [], []
                for slot in range(1, actor_count + 1):
                    actor = read(ds + 0x1BAE + slot * 38, 38)
                    visual = read(ds + 0xC21E + actor[1] * 8, 8)
                    if struct.unpack_from("<H", visual)[0] == 440:
                        continue
                    row = f"{actor.hex()}:{visual.hex()}"
                    if actor[0x15] == 5:
                        effects.append(row)
                    elif 0x13 <= actor[0] <= 0x19:
                        rewards.append(row)
                    else:
                        raise RuntimeError(f"unexpected post-expiry actor {actor.hex()}")
                lines.append(f"tick sample={sample} frame={frame} count={actor_count}"
                             f" rng={read(ds + 0x1AFE, 4).hex()} effects={','.join(effects) or '-'}"
                             f" rewards={','.join(rewards) or '-'} regs={after_regs}")
                if name == "reward_odd" and sample in (1, 5, 10, 20, 30):
                    window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
                    subprocess.run(["import", "-window", window,
                        str(output.with_name(f"{output.stem}_{name}_{sample:03d}.png"))], check=True, timeout=5)
                release(2)
                regs = wait(1)
            lines.append("end samples=41")
            output.write_text("\n".join(lines) + "\n", encoding="ascii")
            print(f"death_transients_original={name} samples=41", flush=True)
        lines.append(f"complete cases={len(PROBES)}")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        for entry, length in HOOKS:
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
            raise RuntimeError(f"instruction mismatch at 1000:{at:04x}")
    for stage in (1, 2):
        trampoline(stage, image)
    print(f"death_transients_capture_self_check=ok windows={len(WINDOWS)} cases={len(PROBES)} live=0"
          f" executable_sha256={hashlib.sha256(exe).hexdigest()}", flush=True)
    if args.self_check:
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("live capture requires temporary run-dir, out and both approval flags")
    if args.out.exists() or list(args.out.parent.glob(args.out.stem + "_*.png")):
        parser.error("output already exists; use a fresh path")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if (args.run_dir / "LEZAC.EXE").read_bytes() != exe:
        parser.error("temporary executable differs from the guarded original")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_DEATH_TRANSIENTS_INSIDE_XVFB"
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
