#!/usr/bin/env python3
"""Observe the original active-fire block in a silent, private DOSBox child.

These are seeded block-boundary probes, not keyboard or whole-frame replays.
The original ammo check, constructor, inventory update and latch clears run
unmodified between guarded hooks. The player identity and launch locals are
exogenous, including P2 probes made in the P1 update's stack frame.
"""

import argparse
import hashlib
import os
from pathlib import Path
import signal
import shutil
import struct
import sys
import time

import capture_original_behavior4_lockstep as environment
import capture_original_death_transients as actors
from capture_original_bomb_fuses import jump
import seed_original_level as seeder

ROOT = Path(__file__).resolve().parent.parent
EXE_SHA256 = "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec"
HOOKS = ((0x6BD5, 5), (0x6CB3, 5))
WINDOWS = {
    0x10A3: bytes.fromhex("b401"),
    0x10BD: bytes.fromhex("3c31750488267b1b"),
    0x10DD: bytes.fromhex("3c5275048826801b"),
    0x110F: bytes.fromhex("3cb1750488267b1b"),
    0x112F: bytes.fromhex("3cd275048826801b"),
    0x6BD5: bytes.fromhex("803e851b017403e9d400"),
    0x6C00: bytes.fromhex("80bd671b007703e9a900"),
    0x6CA9: bytes.fromhex("c6067b1b00c606801b00"),
    0x6CB3: bytes.fromhex("31c0a37420"),
    0x2FAD: bytes.fromhex("803e8d201e7203"),
}
CASES = []
for player in (1, 2):
    for weapon in range(1, 5):
        for name, ammo, pool, fire in (
                ("shot", 2, 0, 1), ("last", 1, 0, 1),
                ("empty", 0, 0, 1), ("full", 2, 30, 1),
                ("pool29", 2, 29, 1), ("no_fire", 2, 0, 0),
                ("same_cell", 2, 1, 1)):
            CASES.append((f"p{player}_w{weapon}_{name}", player, weapon, ammo, pool, fire, 0, 0))
    for name, vx, vy in (("left_jump", -1023, -848), ("right_fall", 1023, 2047),
                         ("clamp_up", -2047, -2000), ("clamp_right", 2047, 0)):
        CASES.append((f"p{player}_{name}", player, 1, 2, 0, 1, vx, vy))


def capture(pid, base, output, image):
    actors.HOOKS, actors.SCRATCH = HOOKS, 0xF600
    cs, ds = base + (actors.CS << 4), base + (seeder.RUNTIME_DS << 4)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(at, size):
            value = os.pread(mem.fileno(), size, at)
            if len(value) != size:
                raise RuntimeError("short active-fire read")
            return value

        def write(at, value):
            if os.pwrite(mem.fileno(), value, at) != len(value):
                raise RuntimeError("short active-fire write")

        def release(stage):
            write(cs + actors.SCRATCH + 14, struct.pack("<H", stage))

        sequence, stopped = 0, 0

        def wait(stage, initial=False):
            nonlocal sequence, stopped
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + actors.SCRATCH, 18))
                if marker and not flag and current > sequence:
                    sequence, stopped = current, marker
                    if regs[1] - regs[0] != 0xAA2:
                        raise RuntimeError("unexpected runtime segments")
                    if marker == stage:
                        return regs
                    if not initial:
                        raise RuntimeError(f"active-fire stage {marker}, wanted {stage}")
                    release(marker)
                time.sleep(0.001)
            raise RuntimeError("active-fire timeout")

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
                write(cs + target, actors.trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        finally:
            os.kill(pid, signal.SIGCONT)
        records = [f"capture schema=active_fire_v1 seeded=1 natural=0 exe_sha256={EXE_SHA256} hooks=6bd5,6cb3 cases={len(CASES)}"]
        try:
            regs = wait(1, True)
            memory_base = cs - (regs[0] << 4)
            for name, player, weapon, ammo, pool, fire, vx, vy in CASES:
                caller = memory_base + (regs[3] << 4) + regs[5]
                # Restore these ranges before the rest of the actor update runs.
                saved = [(ds + at, read(ds + at, size)) for at, size in (
                    (0x1B68, 0x208F - 0x1B68), (0xC21E, 32 * 8),
                    (0xC496, 4), (0x79A3, 1))]
                locals_saved = [(caller + at, read(caller + at, size)) for at, size in (
                    (-0x1D, 1), (-0x2C, 2), (-0x2E, 2), (-0x0C, 2), (-0x0E, 2))]
                inventory = bytearray((2, 2, 2, 2))
                inventory[weapon - 1] = ammo
                write(ds + 0x1B68 + player * 4, inventory)
                write(ds + 0x1B73 + player, bytes((weapon,)))
                keys = bytearray((1, 1))
                keys[player - 1] = fire
                write(ds + 0x1B7B, keys[:1])
                write(ds + 0x1B80, keys[1:])
                write(ds + 0x1B85, bytes((fire,)))
                write(ds + 0x208D, bytes((pool,)))
                write(ds + 0x2072, b"\x5a\x5a")
                write(ds + 0xC496, bytes((pool + 2,)))
                write(caller - 0x1D, bytes((player,)))
                for at, value in ((-0x2C, 104), (-0x2E, 168), (-0x0C, vx), (-0x0E, vy)):
                    write(caller + at, struct.pack("<h", value))
                if name.endswith("same_cell"):
                    existing = bytearray(38)
                    existing[0], existing[1], existing[2], existing[21] = weapon + 12, 2, 20, 2
                    write(ds + 0x1BD4, existing)
                    descriptor = read(ds + 0xC322 + (weapon + 57) * 4, 4)
                    write(ds + 0xC22E, struct.pack("<HH", 104, 168) + descriptor)
                release(1)
                after = wait(2)
                count = read(ds + 0x208D, 1)[0]
                raw = read(ds + 0x1BAE + count * 38, 38) if count == pool + 1 else bytes(38)
                visual = read(ds + 0xC21E + raw[1] * 8, 8) if count == pool + 1 else bytes(8)
                record = (f"case name={name} player={player} weapon={weapon} pool={pool} fire={fire} keys={keys.hex()}"
                          f" inventory={inventory.hex()} x=104 y=168 vx={vx} vy={vy} pool_after={count}"
                          f" inventory_after={read(ds + 0x1B68 + player * 4, 4).hex()}"
                          f" weapon_after={read(ds + 0x1B73 + player, 1)[0]}"
                          f" keys_after={read(ds + 0x1B7B, 1).hex()}{read(ds + 0x1B80, 1).hex()}"
                          f" result={read(ds + 0x2072, 2).hex()} raw={raw.hex()} visual={visual.hex()}"
                          f" regs={struct.pack('<6H', *after).hex()}")
                records.append(record)
                output.write_text("\n".join(records) + "\n", encoding="ascii")
                print(record, flush=True)
                for at, value in saved + locals_saved:
                    write(at, value)
                release(2)
                regs = wait(1)
        finally:
            for entry, length in HOOKS:
                write(cs + entry, image[entry:entry + length])
            if stopped:
                release(stopped)
    records.append(f"complete cases={len(CASES)} whole_game_parity=0")
    output.write_text("\n".join(records) + "\n", encoding="ascii")
    print(f"active_fire_capture=ok cases={len(CASES)} players=2 seeded=1 natural=0", flush=True)


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
    actors.HOOKS, actors.SCRATCH = HOOKS, 0xF600
    for stage in (1, 2):
        actors.trampoline(stage, image)
    if args.self_check:
        print(f"active_fire_self_check=ok cases={len(CASES)} hooks=2 players=2 live=0")
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("temporary run directory, fresh output and both instrumentation approvals required")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if (args.run_dir / "LEZAC.EXE").read_bytes() != exe or args.out.exists() or args.out.with_suffix(".png").exists():
        parser.error("fresh output and unchanged temporary EXE required")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_ACTIVE_FIRE_XVFB"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
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
    result = seeder.main()
    # The seeder captures restored gameplay after the block probes finish.
    shutil.copyfile(args.run_dir / "original_level_1_gameplay.png", args.out.with_suffix(".png"))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
