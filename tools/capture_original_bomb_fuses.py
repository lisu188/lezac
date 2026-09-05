#!/usr/bin/env python3
"""Trace one original bomb constructor and every countdown update in DOSBox.

Runs only in a temporary asset copy under private Xvfb. A real N key reaches
the placement path; weapon choice and placement-frame parity are exogenous.
Four guarded CS polling trampolines preserve registers/flags and replay the
displaced instructions. Constructor, countdown and blast code remain original.
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
SCRATCH = 0xF700
HOOKS = ((0x6C0A, 4), (0x6C5E, 5), (0x75B4, 3), (0x75CB, 4))
WINDOWS = {
    0x6C0A: bytes.fromhex("807eee0474108a46ee30e46bc00a050a00a2a379eb05c606a379c8"),
    0x6C5E: bytes.fromhex("833e7220017544"),
    0x75A7: bytes.fromhex("a1c278250100c47e0426284502"),
    0x75B4: bytes.fromhex("c47e0426807d0200740dc47e0426807d02ff7403e9b401"),
    0x75CB: bytes.fromhex("807ef10c762d"),
    0x3052: bytes.fromhex("26884502"),
}


def jump(at: int, target: int) -> bytes:
    return b"\xe9" + struct.pack("<H", (target - at - 3) & 0xFFFF)


def trampoline(stage: int, image: bytes) -> bytes:
    entry, length = HOOKS[stage - 1]
    at = 0xF400 + (stage - 1) * 0x80
    code = bytearray(b"\x9c\x60")  # Save FLAGS and every general register.
    skips = []
    if stage >= 3:
        for comparison, branch in ((b"\x80\x7e\xf1\x0d", 0x72),
                                   (b"\x80\x7e\xf1\x10", 0x77)):
            code += comparison + bytes([branch, 0])
            skips.append(len(code) - 1)
    for index, op in enumerate(("8cc8", "8cd8", "8cc0", "8cd0", "89e0", "89e8")):
        code += bytes.fromhex(op) + b"\x2e\xa3" + struct.pack("<H", SCRATCH + 2 + 2 * index)
    code += b"\x2e\xff\x06" + struct.pack("<H", SCRATCH + 16)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, stage)
    code += b"\x2e\x83\x3e" + struct.pack("<H", SCRATCH + 14) + bytes([stage]) + b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, 0)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH + 14, 0)
    for skip in skips:
        code[skip] = len(code) - skip - 1
    code += b"\x61\x9d" + image[entry:entry + length]
    code += jump(at + len(code), entry + length)
    if len(code) > 0x80:
        raise RuntimeError("trampoline exceeds its reserved window")
    return bytes(code)


def check_image(exe: Path) -> bytes:
    image = exe.read_bytes()[0x770:]
    for offset, expected in WINDOWS.items():
        if image[offset:offset + len(expected)] != expected:
            raise RuntimeError(f"instruction mismatch at 1000:{offset:04x}")
    for stage in range(1, 5):
        trampoline(stage, image)
    print(f"bomb_fuse_capture_self_check=ok windows={len(WINDOWS)} live=0", flush=True)
    return image


def capture(pid: int, base: int, output: Path, image: bytes, weapon: int, parity: int) -> None:
    ds, cs = base + (seeder.RUNTIME_DS << 4), base + (CS << 4)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(address: int, count: int) -> bytes:
            value = os.pread(mem.fileno(), count, address)
            if len(value) != count:
                raise RuntimeError("short child-memory read")
            return value

        def write(address: int, value: bytes) -> None:
            if os.pwrite(mem.fileno(), value, address) != len(value):
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

        last_sequence = 0

        def wait(stage: int) -> tuple[int, ...]:
            nonlocal last_sequence
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                snapshot = read(cs + SCRATCH, 18)
                marker, *registers, flag, sequence = struct.unpack("<9H", snapshot)
                if marker == stage and flag == 0 and sequence > last_sequence:
                    last_sequence = sequence
                    if registers[1] - registers[0] != seeder.RUNTIME_DS - CS:
                        raise RuntimeError("unexpected runtime segment relationship")
                    return tuple(registers)
                time.sleep(0.001)
            raise RuntimeError(f"stage {stage} timeout: marker={word(cs + SCRATCH)} "
                               f"frame={word(ds + 0x78C2)} player={read(ds + 0x79E5, 7).hex()} "
                               f"controls={read(ds + 0x1B78, 10).hex()}")

        def release(stage: int) -> None:
            write(cs + SCRATCH + 14, struct.pack("<H", stage))

        for offset, expected in WINDOWS.items():
            if read(cs + offset, len(expected)) != expected:
                raise RuntimeError(f"runtime window mismatch at {offset:04x}")
        if read(cs + 0xF400, 0x312) != bytes(0x312):
            raise RuntimeError("CS instrumentation area is not empty")

        def install() -> None:
            for stage, (entry, _) in enumerate(HOOKS, 1):
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        stopped(install)
        window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
        subprocess.run(["xdotool", "windowfocus", "--sync", window], check=True)
        subprocess.run(["xdotool", "keydown", "n"], check=True)
        registers = wait(1)
        subprocess.run(["xdotool", "keyup", "n"], check=True)
        memory_base = cs - (registers[0] << 4)
        write(memory_base + (registers[3] << 4) + registers[5] - 0x12, bytes([weapon]))
        release(1)
        registers = wait(2)
        placement_frame = word(ds + 0x78C2)
        frame = placement_frame + ((placement_frame & 1) != parity)
        write(ds + 0x78C2, struct.pack("<H", frame & 0xFFFF))
        slot = read(ds + 0x208D, 1)[0]
        actor_address = ds + 0x1BAE + slot * 0x26
        initial = read(actor_address, 0x26)
        if initial[0] != 12 + weapon or initial[0x15] != 2:
            raise RuntimeError(f"constructor did not create selected bomb: {initial.hex()}")
        print(f"bomb_constructor weapon={weapon} frame={frame} raw={initial.hex()}", flush=True)
        lines = [
            "# Original DOSBox bomb trace; weapon choice and frame parity are exogenous.",
            "# register_order=cs,ds,es,ss,sp_after_pushf_pusha,bp; little-endian words",
            f"capture=bomb_fuse_original_v1 weapon={weapon} parity={parity} temp_copy=1",
            f"seed frame={frame} natural_frame={placement_frame} slot={slot} raw={initial.hex()} "
            f"regs={struct.pack('<6H', *registers).hex()}",
        ]
        release(2)
        samples = 0
        first_frame = None
        while True:
            registers = wait(3)
            pointer = memory_base + (registers[3] << 4) + registers[5] + 4
            offset, segment = struct.unpack("<HH", read(pointer, 4))
            raw = read(memory_base + (segment << 4) + offset, 0x26)
            tick = word(ds + 0x78C2)
            if first_frame is None:
                first_frame = tick
                if (tick - frame) & 0xFFFF not in (0, 1):
                    raise RuntimeError(f"first update delayed: placement={frame} first={tick}")
            if tick != (first_frame + samples) & 0xFFFF:
                raise RuntimeError(f"non-consecutive bomb update {samples}: frame={tick}")
            visual = read(ds + 0xC21E + raw[1] * 8, 8)
            lines.append(f"tick frame={tick} raw={raw.hex()} visual={visual.hex()}")
            samples += 1
            if samples == 2:
                window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
                subprocess.run(["import", "-window", window, str(output.with_suffix('.png'))], check=True, timeout=5)
            release(3)
            if raw[2] in (0, 255):
                break
            if samples > 510:
                raise RuntimeError("bomb did not expire within byte-countdown bound")
        registers = wait(4)
        lines.append(f"expiry frame={word(ds + 0x78C2)} updates={samples} "
                     f"regs={struct.pack('<6H', *registers).hex()}")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        print(f"bomb_fuse_original weapon={weapon} parity={parity} seed={initial[2]} updates={samples}", flush=True)

        def resume() -> None:
            for entry, _ in HOOKS:
                write(cs + entry, image[entry:entry + 3])
            release(4)
        stopped(resume)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--weapon", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--parity", type=int, choices=(0, 1), default=0)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    exe = Path(__file__).resolve().parent.parent / "LEZAC.EXE"
    image = check_image(exe)
    if args.self_check:
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("live capture requires temporary run-dir, out and both approval flags")
    if args.out.exists() or args.out.with_suffix(".png").exists():
        parser.error("output already exists; choose a fresh path for each capture attempt")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if hashlib.sha256((args.run_dir / "LEZAC.EXE").read_bytes()).digest() != hashlib.sha256(exe.read_bytes()).digest():
        raise RuntimeError("temporary executable differs from checked image")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_BOMB_FUSE_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image, args.weapon, args.parity)
        return original(run_dir, pid, base, state, phase)
    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
