#!/usr/bin/env python3
"""Observe seeded player waiting prepasses in a silent, private DOSBox child."""

import argparse
import hashlib
import os
from pathlib import Path
import signal
import struct
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
import capture_original_behavior4_lockstep as environment
import capture_original_death_transients as actors
from capture_original_bomb_fuses import jump
import seed_original_level as seeder

HOOKS = ((0x7C3D, 6), (0x7EBB, 5))
EXE_SHA256 = "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec"
WINDOWS = {0x7C3D: bytes.fromhex("c70682200100"),
           0x7EBB: bytes.fromhex("803ef97900"),
           0x7E6D: bytes.fromhex("c47ef826ff4d02"),
           0x7E9D: bytes.fromhex("c6067b1b00c606801b00")}
CASES = [
    ("open", 0, 0, 40, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("left_1", 1, 0, 40, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("left_76", 76, 0, 40, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("left_77", 77, 0, 40, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("right_1", 0, 1, 40, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("right_76", 0, 76, 40, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("right_77", 0, 77, 40, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("left_at_24", 1, 0, 24, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("right_at_24", 0, 1, 24, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("solid_fire", 1, 0, 40, 1, 1, 0xfff0, [0, 0, 0, 0]),
    ("gate0_fire", 1, 0, 40, 1, 0, 0xfff0, [0, 0, 0, 0]),
    ("expiry_empty", 0, 0, 40, 0, 1, 1, [0, 0, 0, 0]),
    ("expiry_above", 0, 0, 40, 0, 1, 1, [200, 20, 6, 3]),
    ("expiry_below", 0, 0, 40, 0, 1, 1, [99, 9, 1, 7]),
    ("left_2", 2, 0, 40, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("left_38", 38, 0, 40, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("right_75", 0, 75, 40, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("left_at_0", 1, 0, 0, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("right_at_0", 0, 1, 0, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("right_at_25", 0, 1, 25, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("left_at_65535", 1, 0, 65535, 0, 1, 0xfff0, [0, 0, 0, 0]),
    ("expiry_gate0", 0, 0, 40, 0, 0, 1, [0, 0, 0, 0]),
    ("expiry_fire", 0, 0, 40, 1, 1, 1, [0, 0, 0, 0]),
    ("expiry_gate0_fire", 0, 0, 40, 1, 0, 1, [0, 0, 0, 0]),
    ("expiry_equal", 0, 0, 40, 0, 1, 1, [100, 10, 2, 255]),
    ("before_expiry", 1, 0, 40, 1, 1, 2, [0, 0, 0, 0]),
    ("word_wrap", 1, 0, 40, 0, 1, 0, [0, 0, 0, 0]),
]


def capture(pid, base, output, image):
    actors.HOOKS, actors.SCRATCH = HOOKS, 0xF600
    cs, ds = base + (actors.CS << 4), base + (seeder.RUNTIME_DS << 4)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(at, size):
            value = os.pread(mem.fileno(), size, at)
            if len(value) != size:
                raise RuntimeError("short prepass read")
            return value

        def write(at, value):
            if os.pwrite(mem.fileno(), value, at) != len(value):
                raise RuntimeError("short prepass write")

        def word(at):
            return struct.unpack("<H", read(at, 2))[0]

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
                        raise RuntimeError(f"prepass stage {marker}, wanted {stage}")
                    release(marker)
                time.sleep(0.001)
            raise RuntimeError("prepass timeout")

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
        try:
            regs = wait(1, True)
            memory_base = cs - (regs[0] << 4)
            width = word(ds + 0xC204)
            height = word(ds + 0x2096) // 8 + 21
            objects = memory_base + (word(ds + 0xC1FE) << 4)
            original_map = read(objects, width * height)
            original_actors = read(ds + 0x1B88, 76)
            original_visuals = read(ds + 0xC21E, 16)
            scan_map = memory_base + (word(ds + 0xC1E2) << 4) + word(ds + 0xC1E0)
            if scan_map != objects:
                raise RuntimeError("waiting scan does not alias the object plane")
            records = [f"capture schema=state2_prepass_v1 level=1 seeded=1 natural=0 exe_sha256={EXE_SHA256} hooks=7c3d,7ebb cases={len(CASES) * 2}",
                       f"layout width={width} height={height} descriptors={read(ds + 0xC322, 92 * 4).hex()}"]
            for player, spec in ((p, case) for p in (1, 2) for case in CASES):
                name, left, right, y, key, gate, timer, inventory = spec
                name = f"p{player}_{name}"
                actor_at = ds + 0x1B62 + player * 38
                visual_at = ds + 0xC21E + (player - 1) * 8
                inventory_at = ds + 0x1B68 + player * 4
                tiles = bytearray(len(original_map))
                at = (((((y + 7) & 65535) >> 3) + 1) * width + 3) & 65535
                if at + 1 >= len(tiles):
                    raise RuntimeError("probe cells outside object plane")
                tiles[at:at + 2] = bytes((left, right))
                actor = bytearray(original_actors[:38])
                actor[1], actor[21], actor[36] = player - 1, 2, 77
                struct.pack_into("<H", actor, 16, timer)
                visual = bytearray(original_visuals[:8])
                struct.pack_into("<HH", visual, 0, 24, y)
                write(objects, tiles)
                write(ds + 0x1B88, original_actors)
                write(ds + 0xC21E, original_visuals)
                write(actor_at, actor)
                write(visual_at, visual)
                states = bytearray(2)
                states[player - 1] = 1 if timer in (1, 2) else 2
                write(ds + 0x79E6, states)
                write(ds + 0x79EA, b"\x63\x63")
                write(ds + 0x79E9 + player, b"\x01")
                write(ds + 0x79B8, b"\x01\x00")
                write(ds + 0x79CA, bytes((gate,)))
                write(inventory_at, bytes(inventory))
                write(ds + 0x1B7B, bytes((key,)))
                write(ds + 0x1B80, bytes((key,)))
                write(ds + 0x208D, b"\x00")
                write(ds + 0x79F9, b"\x00")
                write(ds + 0x79A6, b"\x00")
                release(1)
                after_regs = wait(2)
                after_actor = read(actor_at, 38)
                after_visual = read(visual_at, 8)
                record = (f"case name={name} player={player} left={left} right={right} y={y} fire={key} gate={gate} timer={timer}"
                          f" inventory={bytes(inventory).hex()} before={actor.hex()} visual={visual.hex()}"
                          f" after={after_actor.hex()} visual_after={after_visual.hex()} inventory_after={read(inventory_at, 4).hex()}"
                          f" states={read(ds + 0x79E6, 2).hex()} lives={read(ds + 0x79E9 + player, 1)[0]}"
                          f" gate_after={read(ds + 0x79CA, 1)[0]} counter={read(ds + 0x79B9, 1)[0]}"
                          f" keys={read(ds + 0x1B7B, 1).hex()}{read(ds + 0x1B80, 1).hex()} regs={struct.pack('<6H', *after_regs).hex()}")
                records.append(record)
                output.write_text("\n".join(records) + "\n", encoding="ascii")
                print(record, flush=True)
                write(objects, original_map)
                write(ds + 0x1B88, original_actors)
                write(ds + 0xC21E, original_visuals)
                write(ds + 0x79E6, b"\x01\x00")
                write(ds + 0x79EA, b"\x63\x63")
                write(ds + 0x79B9, b"\x00")
                write(ds + 0x79CA, b"\x01")
                write(ds + 0x1B7B, b"\x00")
                write(ds + 0x1B80, b"\x00")
                release(2)
                wait(1)
        finally:
            for entry, length in HOOKS:
                write(cs + entry, image[entry:entry + length])
            if stopped:
                release(stopped)
    records.append(f"complete cases={len(CASES) * 2} whole_game_parity=0")
    output.write_text("\n".join(records) + "\n", encoding="ascii")
    print(f"state2_prepass_capture=ok cases={len(CASES) * 2} players=2 seeded=1 natural=0", flush=True)


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
    if args.self_check:
        print(f"state2_prepass_self_check=ok cases={len(CASES) * 2} hooks=2 players=2 live=0")
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("temporary run directory, fresh output and both instrumentation approvals required")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if (args.run_dir / "LEZAC.EXE").read_bytes() != exe or args.out.exists():
        parser.error("fresh output and unchanged temporary EXE required")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_STATE2_PREPASS_XVFB"
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
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
