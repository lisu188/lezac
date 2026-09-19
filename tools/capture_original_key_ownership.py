#!/usr/bin/env python3
"""Observe real X key events through the original two-player normalization.

Only the two inventories are cleared to prevent fire probes from creating
explosions. No input, position, velocity or player identity bytes are seeded.
All game processes run silently in a temporary copy under private Xvfb.
"""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import time

import capture_original_behavior4_lockstep as environment
from capture_original_bomb_fuses import jump
import seed_original_level as seeder

ROOT = Path(__file__).resolve().parent.parent
EXE_SHA256 = "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec"
CS, SCRATCH = 0x01ED, 0xF600
HOOKS = ((0x616E, 3), (0x6245, 3))
WINDOWS = {
    0x616E: bytes.fromhex("8a46cf3c007565"),
    0x6175: bytes.fromhex("a0781ba2821ba0791ba2831ba07a1ba2841ba07b1ba2851ba07c1ba2861b"),
    0x61DE: bytes.fromhex("a07d1ba2821ba07e1ba2831ba07f1ba2841ba0801ba2851ba0811ba2861b"),
    0x6245: bytes.fromhex("8a46ed30e48bf8"),
    0x10A1: bytes.fromhex("e460b401"),
}
KEYS = ("m", "z", "x", "n", "c", "Up", "Left", "Right", "Insert", "Down")
CASES = tuple((key,) for key in KEYS) + (
    ("z", "Right"), ("x", "Left"), ("m", "Up"), ("c", "Down"),
    ("n", "Insert"), ("x", "n"), ("Right", "Insert"),
    ("m", "c"), ("Up", "Down"), ("z", "x"), ("Left", "Right"),
)


def trampoline(stage, image):
    target = 0xF400 + (stage - 1) * 0x80
    code = bytearray.fromhex("9c60807ecf017700")  # Observe only player behaviors 0/1.
    skip = len(code) - 1
    for index, op in enumerate(("8cc8", "8cd8", "8cc0", "8cd0", "89e0", "89e8")):
        code += bytes.fromhex(op) + b"\x2e\xa3" + struct.pack("<H", SCRATCH + 2 + index * 2)
    code += b"\x2e\xff\x06" + struct.pack("<H", SCRATCH + 16)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, stage)
    code += b"\x2e\x83\x3e" + struct.pack("<H", SCRATCH + 14) + bytes((stage,)) + b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, 0)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH + 14, 0)
    code[skip] = len(code) - skip - 1
    entry, length = HOOKS[stage - 1]
    code += b"\x61\x9d" + image[entry:entry + length]
    code += jump(target + len(code), entry + length)
    if len(code) > 0x80:
        raise RuntimeError("trampoline exceeds reserved window")
    return bytes(code)


def capture(pid, base, output, image):
    cs, ds = base + (CS << 4), base + (seeder.RUNTIME_DS << 4)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(at, size):
            value = os.pread(mem.fileno(), size, at)
            if len(value) != size:
                raise RuntimeError("short keyboard read")
            return value

        def write(at, value):
            if os.pwrite(mem.fileno(), value, at) != len(value):
                raise RuntimeError("short keyboard write")

        def release(stage):
            write(cs + SCRATCH + 14, struct.pack("<H", stage))

        sequence, stopped = 0, 0

        def wait(stage, initial=False):
            nonlocal sequence, stopped
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + SCRATCH, 18))
                if marker and not flag and current > sequence:
                    sequence, stopped = current, marker
                    if regs[1] - regs[0] != 0xAA2:
                        raise RuntimeError("unexpected runtime segments")
                    if marker == stage:
                        return regs
                    if not initial:
                        raise RuntimeError(f"keyboard stage {marker}, wanted {stage}")
                    release(marker)
                time.sleep(0.001)
            raise RuntimeError(f"keyboard timeout marker={read(cs + SCRATCH, 2).hex()}")

        for at, expected in WINDOWS.items():
            if read(cs + at, len(expected)) != expected:
                raise RuntimeError(f"runtime guard {at:04x}")
        if read(cs + 0xF400, 0x212) != bytes(0x212):
            raise RuntimeError("instrumentation arena occupied")
        os.kill(pid, signal.SIGSTOP)
        try:
            deadline = time.monotonic() + 2
            while "State:\tT" not in Path(f"/proc/{pid}/status").read_text():
                if time.monotonic() > deadline:
                    raise RuntimeError("owned child stop timeout")
                time.sleep(0.001)
            for stage, (entry, _) in enumerate(HOOKS, 1):
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        finally:
            os.kill(pid, signal.SIGCONT)
        saved_inventory = None
        records = [f"capture schema=key_ownership_v1 players=2 physical_keys=1 ammo_seeded=1 actor_seeded=0 exe_sha256={EXE_SHA256} hooks=616e,6245 cases={len(CASES)} samples={len(CASES) * 4}"]
        try:
            regs = wait(1, True)
            memory_base = cs - (regs[0] << 4)

            def player_at(registers):
                caller = memory_base + (registers[3] << 4) + registers[5]
                return read(caller - 0x31, 1)[0] + 1

            if player_at(regs) == 2:
                release(1); wait(2); release(2); regs = wait(1)
            if player_at(regs) != 1 or read(ds + 0x1BAE + 21, 1) != b"\x01":
                raise RuntimeError("two active original players required")
            saved_inventory = read(ds + 0x1B6C, 8)
            write(ds + 0x1B6C, bytes(8))
            window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
            subprocess.run(["xdotool", "windowfocus", "--sync", window], check=True)
            for index, held in enumerate(CASES):
                for phase in ("make", "break"):
                    subprocess.run(["xdotool", "keyup", *KEYS], check=True)
                    if phase == "make":
                        subprocess.run(["xdotool", "keydown", *held], check=True)
                    expected = bytes(int(phase == "make" and key in held) for key in KEYS)
                    deadline = time.monotonic() + 5
                    while read(ds + 0x1B78, 10) != expected:
                        if time.monotonic() > deadline:
                            raise RuntimeError(f"physical input not delivered: {held} {phase} hardware={read(ds + 0x1B78, 10).hex()}")
                        time.sleep(0.002)
                    for player in (1, 2):
                        if player_at(regs) != player:
                            raise RuntimeError("unexpected player dispatch order")
                        before = read(ds + 0x1B78, 10)
                        if before != expected:
                            raise RuntimeError("hardware state changed during sample")
                        release(1)
                        after = wait(2)
                        caller = memory_base + (after[3] << 4) + after[5]
                        actual_player = read(caller - 0x1D, 1)[0]
                        normalized = read(ds + 0x1B82, 5)
                        if actual_player != player or normalized != expected[(player - 1) * 5:player * 5]:
                            raise RuntimeError("normalization differs from original hardware bank")
                        actor = read(ds + 0x1B62 + player * 38, 38)
                        visual = read(ds + 0xC21E + actor[1] * 8, 8)
                        records.append(f"sample case={index} keys={'+'.join(held)} phase={phase} player={player}"
                                       f" frame={int.from_bytes(read(ds + 0x78C2, 2), 'little')} hardware={before.hex()}"
                                       f" normalized={normalized.hex()} actor={actor.hex()} visual={visual.hex()}"
                                       f" regs={struct.pack('<6H', *after).hex()}")
                        release(2)
                        regs = wait(1)
                    output.write_text("\n".join(records) + "\n", encoding="ascii")
                    print(f"key_ownership case={index} keys={'+'.join(held)} phase={phase} players=2", flush=True)
        finally:
            subprocess.run(["xdotool", "keyup", *KEYS], check=False)
            if saved_inventory is not None:
                write(ds + 0x1B6C, saved_inventory)
            for entry, length in HOOKS:
                write(cs + entry, image[entry:entry + length])
            if stopped:
                release(stopped)
    records.append(f"complete cases={len(CASES)} samples={len(CASES) * 4} whole_game_parity=0")
    output.write_text("\n".join(records) + "\n", encoding="ascii")
    print(f"key_ownership_capture=ok cases={len(CASES)} samples={len(CASES) * 4} physical_keys=1", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    exe = (ROOT / "LEZAC.EXE").read_bytes()
    if hashlib.sha256(exe).hexdigest() != EXE_SHA256:
        raise RuntimeError("original EXE hash")
    image = exe[0x770:]
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"static guard {at:04x}")
    for stage in (1, 2):
        trampoline(stage, image)
    if args.self_check:
        print(f"key_ownership_self_check=ok cases={len(CASES)} samples={len(CASES) * 4} hooks=2 live=0")
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("temporary run directory, fresh output and both instrumentation approvals required")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if (args.run_dir / "LEZAC.EXE").read_bytes() != exe or args.out.exists() or args.out.with_suffix(".png").exists():
        parser.error("fresh output and unchanged temporary EXE required")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_KEY_OWNERSHIP_XVFB"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--start-key", "2", "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    result = seeder.main()
    shutil.copyfile(args.run_dir / "original_level_1_gameplay.png", args.out.with_suffix(".png"))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
