#!/usr/bin/env python3
"""Capture original player input response and integration under private DOSBox.

Normalized control bytes are injected at a guarded player-update stop. The
explicit cursor_restore probe additionally seeds only the two animation cursors.
Positions, velocities, collision flags and fractions are not seeded. Guarded
checkpoint trampolines replay displaced instructions without changing motion.
All live runs use a temporary asset copy and require both approval flags.
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
from capture_original_bomb_fuses import jump
import seed_original_level as seeder


CS = 0x01ED
SCRATCH = 0xF700
HOOKS = ((0x6813, 3), (0x6B55, 3), (0x741E, 4), (0x6064, 4))
WINDOWS = {
    0x6813: bytes.fromhex("a0841b30e48bd0a0831b30e403c23d0200"),
    0x6B55: bytes.fromhex("8b46f49931d029d099b90001f7f9"),
    0x741E: bytes.fromhex("807ef1017303e9f000"),
    0x6AC6: bytes.fromhex("817ef400fc7e04836ef440"),
    0x6B1C: bytes.fromhex("817ef400047d048346f440"),
    0x6B27: bytes.fromhex("807edf007428803e821b01750b"),
    0x5B9C: bytes.fromhex("3d2b007d0b8b7e0431c0368945f4eb1c"),
    0x66F3: bytes.fromhex("8a46cf3c007403e91b09"),
    0x6743: bytes.fromhex("8346f240817ef2ff077e05c746f2ff07"),
    0x6064: bytes.fromhex("268a45018846edc47e0481c71600"),
    0x6085: bytes.fromhex("c47ec626fe4503c47ec6268a4503"),
    0x6B93: bytes.fromhex("c47e0426807d02057538"),
    0x60F1: bytes.fromhex("c47e0481c71d000657c47e0481c7160006576a079a0e09"),
    0x6768: bytes.fromhex("817ef240067f03e99c00"),
    0x6A47: bytes.fromhex("c47e0426c7450e0400"),
    0x6A5E: bytes.fromhex("c47e0426837d0e0076138346d202"),
    0x65A2: bytes.fromhex("807ecf057532a1c278250100"),
    0x2FAD: bytes.fromhex("803e8d201e7203"),
    0x6D88: bytes.fromhex("803e8e200e7372"),
    0x806A: bytes.fromhex("833e9c20007423"),
}
ROUTES = {
    "braking": [("right", 20), ("idle", 28), ("left", 20), ("idle", 28)],
    "reversal": [("right", 20), ("left", 36), ("right", 36), ("idle", 28)],
    "reaccelerate": [("right", 20), ("idle", 7), ("right", 12), ("idle", 28),
                     ("left", 20), ("idle", 7), ("left", 12), ("idle", 28)],
    "air_coast": [("right", 10), ("jump_right", 1), ("idle", 28)],
    "switch_coast": [("right", 20), ("both", 8), ("idle", 28)],
    "idle_resume": [("idle", 260), ("right", 20), ("idle", 28)],
    "cursor_restore": [("idle", 6)],
    "short_idle": [("right", 20), ("idle", 3), ("right", 4), ("idle", 28)],
    "down_floor": [("down", 12), ("jump_down", 12), ("idle", 4)],
    "platform_drop": [("right", 16), ("idle", 28), ("jump", 1), ("idle", 30),
                      ("down", 1), ("idle", 15)],
    "platform_collapse": [("right", 16), ("idle", 128)],
    "hill_fall": [("left", 80), ("jump_right", 1), ("right", 45), ("idle", 28)],
    "hill_jump_fall": [("jump_left", 100), ("idle", 28), ("jump_right", 1),
                       ("right", 35), ("idle", 28)],
}
CONTROLS = {"idle": (0, 0, 0, 0, 0), "left": (0, 1, 0, 0, 0),
            "right": (0, 0, 1, 0, 0), "jump_right": (1, 0, 1, 0, 0),
            "both": (0, 1, 1, 0, 0), "down": (0, 0, 0, 0, 1),
            "jump": (1, 0, 0, 0, 0), "jump_down": (1, 0, 0, 0, 1),
            "jump_left": (1, 1, 0, 0, 0)}


def trampoline(stage: int, image: bytes) -> bytes:
    entry, length = HOOKS[stage - 1]
    at = 0xF400 + (stage - 1) * 0x80
    code = bytearray(b"\x9c\x60")
    skip = None
    if stage == 3:
        code += bytes.fromhex("807ecf007500")  # Only normalized player behavior 0.
        skip = len(code) - 1
    elif stage == 4:
        code += bytes.fromhex("26807d15007500")  # ES:DI already selects the actor.
        skip = len(code) - 1
    for index, op in enumerate(("8cc8", "8cd8", "8cc0", "8cd0", "89e0", "89e8")):
        code += bytes.fromhex(op) + b"\x2e\xa3" + struct.pack("<H", SCRATCH + 2 + 2 * index)
    code += b"\x2e\xff\x06" + struct.pack("<H", SCRATCH + 16)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, stage)
    code += b"\x2e\x83\x3e" + struct.pack("<H", SCRATCH + 14) + bytes([stage]) + b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, 0)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH + 14, 0)
    if skip is not None:
        code[skip] = len(code) - skip - 1
    code += b"\x61\x9d" + image[entry:entry + length]
    code += jump(at + len(code), entry + length)
    if len(code) > 0x80:
        raise RuntimeError("trampoline exceeds reserved window")
    return bytes(code)


def check_image(exe: Path) -> bytes:
    image = exe.read_bytes()[0x770:]
    for offset, expected in WINDOWS.items():
        if image[offset:offset + len(expected)] != expected:
            raise RuntimeError(f"instruction mismatch at 1000:{offset:04x}")
    for stage in range(1, 5):
        trampoline(stage, image)
    print(f"player_walk_capture_self_check=ok windows={len(WINDOWS)} live=0", flush=True)
    return image


def capture(pid: int, base: int, output: Path, image: bytes, route: str,
            animation: bool = False, world: bool = False, transients: bool = False) -> None:
    ds, cs = base + (seeder.RUNTIME_DS << 4), base + (CS << 4)
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

        sequence_seen = 0

        def wait(stage: int) -> tuple[int, ...]:
            nonlocal sequence_seen
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                marker, *registers, flag, sequence = struct.unpack("<9H", read(cs + SCRATCH, 18))
                if marker == stage and flag == 0 and sequence > sequence_seen:
                    sequence_seen = sequence
                    if registers[1] - registers[0] != seeder.RUNTIME_DS - CS:
                        raise RuntimeError("unexpected runtime segments")
                    return tuple(registers)
                time.sleep(0.001)
            try:
                windows = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()
                if windows:
                    subprocess.run(["import", "-window", windows[-1],
                                    str(output.with_suffix(".failure.png"))], check=True, timeout=5)
            except (subprocess.SubprocessError, OSError) as error:
                print(f"failure screenshot unavailable: {error}", file=sys.stderr)
            raise RuntimeError(f"stage {stage} timeout: marker={word(cs + SCRATCH)} "
                               f"frame={word(ds + 0x78C2)}")

        def release(stage: int) -> None:
            write(cs + SCRATCH + 14, struct.pack("<H", stage))

        def locals_at(registers: tuple[int, ...]) -> tuple[int, bytes]:
            actual_base = cs - (registers[0] << 4)
            caller = actual_base + (registers[3] << 4) + registers[5]
            return caller, read(caller - 0x3A, 0x3A)

        for offset, expected in WINDOWS.items():
            if read(cs + offset, len(expected)) != expected:
                raise RuntimeError(f"runtime instruction mismatch at {offset:04x}")
        if read(cs + 0xF400, 0x312) != bytes(0x312):
            raise RuntimeError("instrumentation area is not empty")

        def install(stages) -> None:
            for stage in stages:
                entry, _ = HOOKS[stage - 1]
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        stopped(lambda: install([4] if animation else [1, 2, 3]))
        entry_regs = wait(4) if animation else None
        if animation:
            stopped(lambda: install([1, 2, 3]))
        capture_kind = "player_animation_original_v1" if animation else "player_walk_original_v1"
        rows = ["# Original player trace; normalized controls and any declared cursor probe are exogenous.",
                "# pre/response/post = SS:BP-3A..BP-1; regs=CS,DS,ES,SS,saved-SP,BP.",
                f"capture={capture_kind} route={route} temp_copy=1 cursor_seeded={int(route == 'cursor_restore')}"]
        descriptors = read(ds + 0xC322, 92 * 4)
        if animation:
            rows.append(f"sprites descriptors={descriptors.hex()}")
            if word(ds + 0xC204) != 60:
                raise RuntimeError("player capture requires the level-1 tile stride")
            offset, segment = struct.unpack("<HH", read(ds + 0xC1E0, 4))
            actual_base = cs - (entry_regs[0] << 4)
            output.with_suffix(".tiles.bin").write_bytes(
                read(actual_base + (segment << 4) + offset, 60 * 33))

        def map_planes():
            planes = []
            for pointer, stride in ((0xC1E0, 1), (0x6612, 2)):
                offset, segment = struct.unpack("<HH", read(ds + pointer, 4))
                planes.append(read(actual_base + (segment << 4) + offset, 60 * 33 * stride))
            return planes

        if world:
            initial_tiles, initial_words = map_planes()
            output.with_suffix(".words.bin").write_bytes(initial_words)
            rows.append(f"world width=60 height=33 pickup_tables={read(ds + 2, 48).hex()}")

        if transients:
            rows.append("transients behavior=5 actor_capacity=30 pickup_capacity=14 seeded=0")

        def transient_state(prefix):
            count = read(ds + 0x208D, 1)[0]
            if count > 30:
                raise RuntimeError("original shared actor count exceeds capacity")
            entries = []
            for slot in range(1, count + 1):
                actor = read(ds + 0x1BAE + slot * 38, 38)
                if actor[0x15] == 5:
                    visual = read(ds + 0xC21E + actor[1] * 8, 8)
                    entries.append(f"{slot}:{actor.hex()}:{visual.hex()}")
            return (f" {prefix}_transients={','.join(entries) or '-'}"
                    f" {prefix}_actor_count={count} {prefix}_pickup_count={read(ds + 0x208E, 1)[0]}"
                    f" {prefix}_shake={read(ds + 0x2098, 6).hex()}"
                    f" {prefix}_rng={read(ds + 0x1AFE, 4).hex()}")

        world_changed = False
        last_world_key = None

        def world_state(prefix):
            nonlocal world_changed, last_world_key
            tiles, words = map_planes()
            changes = bytearray()
            for index, tile in enumerate(tiles):
                at = index * 2
                if tile != initial_tiles[index] or words[at:at + 2] != initial_words[at:at + 2]:
                    changes += struct.pack("<HB", index, tile) + words[at:at + 2]
            count = word(ds + 0x2080)
            if count > 250:
                raise RuntimeError("collapse count exceeds original capacity")
            records = read(ds + 0x6620, count * 15)
            key = (tiles, words, count)
            world_changed = world_changed or key != last_world_key
            last_world_key = key
            return (f" {prefix}_map={changes.hex() or '-'}"
                    f" {prefix}_collapse={records.hex() or '-'}")

        def actor_at(regs):
            caller, _ = locals_at(regs)
            actual_base = cs - (regs[0] << 4)
            offset, segment = struct.unpack("<HH", read(caller + 4, 4))
            address = actual_base + (segment << 4) + offset
            actor = read(address, 0x26)
            return address, actor, read(ds + 0xC21E + actor[1] * 8, 8)

        previous = None
        samples = 0
        for phase, ticks in ROUTES[route]:
            for _ in range(ticks):
                extra = ""
                world_changed = False
                if animation:
                    if samples:
                        entry_regs = wait(4)
                    elif route == "cursor_restore":
                        address, _, _ = actor_at(entry_regs)
                        write(address + 0x16, bytes([6, 5, 6, 1, 1, 3, 1,
                                                    8, 8, 9, 2, 2, 1, 1]))
                    _, entry_actor, entry_visual = actor_at(entry_regs)
                    extra = f" entry={entry_actor.hex()} entry_visual={entry_visual.hex()}"
                    if world:
                        extra += world_state("entry")
                    if transients:
                        extra += transient_state("entry")
                    release(4)
                regs = wait(1)
                frame = word(ds + 0x78C2)
                if previous is not None and frame != (previous + 1) & 0xFFFF:
                    raise RuntimeError("non-consecutive player update")
                previous = frame
                caller, before = locals_at(regs)
                actual_base = cs - (regs[0] << 4)
                offset, segment = struct.unpack("<HH", read(caller + 4, 4))
                actor = read(actual_base + (segment << 4) + offset, 0x26)
                if actor[0x15] != 0 or before[0x3A - 0x1D] != 1:
                    raise RuntimeError("checkpoint is not active player 1")
                visual = read(ds + 0xC21E + actor[1] * 8, 8)
                if animation:
                    extra += f" edge_tiles={read(ds + 0x2048, 16).hex()}"
                write(ds + 0x1B82, bytes(CONTROLS[phase]))
                release(1)
                response_regs = wait(2)
                _, response = locals_at(response_regs)
                release(2)
                after_regs = wait(3)
                _, after = locals_at(after_regs)
                if animation:
                    _, final_actor, final_visual = actor_at(after_regs)
                    sprite = next((i - 1 for i in range(1, 92)
                                   if descriptors[i * 4:i * 4 + 4] == final_visual[4:]), None)
                    if sprite is None:
                        raise RuntimeError("player visual has no original sprite descriptor")
                    extra += (f" final_actor={final_actor.hex()} final_visual={final_visual.hex()} sprite={sprite}"
                              f" normalized={read(ds + 0x1B82, 5).hex()}")
                    if world:
                        extra += world_state("final")
                    if transients:
                        extra += transient_state("final")
                if word(ds + 0x78C2) != frame:
                    raise RuntimeError("player checkpoints crossed a frame")
                rows.append(f"tick frame={frame} phase={phase} raw={actor.hex()} visual={visual.hex()} "
                            f"pre={before.hex()} response={response.hex()} post={after.hex()} "
                            f"regs={struct.pack('<6H', *regs).hex()}{extra}")
                samples += 1
                if samples in (8, 20, 32) or (transients and 32 <= samples <= 60) or (world and world_changed) or (animation and
                    (entry_actor[0x16:0x24] != final_actor[0x16:0x24] or
                     entry_actor[0x0E:0x10] != final_actor[0x0E:0x10])):
                    window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
                    screenshot = output.with_name(f"{output.stem}_{samples:03d}.png")
                    subprocess.run(["import", "-window", window, str(screenshot)], check=True, timeout=5)
                if samples < sum(n for _, n in ROUTES[route]):
                    release(3)
        rows.append(f"complete samples={samples}")
        output.write_text("\n".join(rows) + "\n", encoding="ascii")

        def resume() -> None:
            for entry, _ in HOOKS[:4 if animation else 3]:
                write(cs + entry, image[entry:entry + 3])
            release(3)
        stopped(resume)
        print(f"player_walk_original=ok route={route} samples={samples}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--route", choices=ROUTES, default="braking")
    parser.add_argument("--animation", action="store_true",
                        help="also capture pre-advance and post-input animation/visual state")
    parser.add_argument("--world", action="store_true",
                        help="with --animation, capture collapse records and sparse map changes")
    parser.add_argument("--transients", action="store_true",
                        help="with --animation, capture shared behavior-5 actors, visuals and RNG")
    parser.add_argument("--approve-animation-seed", action="store_true",
                        help="allow the cursor_restore probe to seed only actor +16..+23")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--startup-seconds", type=float, default=6.0)
    parser.add_argument("--intro-seconds", type=float, default=3.0)
    parser.add_argument("--level-start-seconds", type=float, default=1.5)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    exe = Path(__file__).resolve().parent.parent / "LEZAC.EXE"
    image = check_image(exe)
    if args.self_check:
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("live capture requires temporary run-dir, out and both approval flags")
    if args.route == "cursor_restore" and not (args.animation and args.approve_animation_seed):
        parser.error("cursor_restore requires --animation and --approve-animation-seed")
    if args.world and not args.animation:
        parser.error("--world requires --animation")
    if args.transients and not args.animation:
        parser.error("--transients requires --animation")
    if (args.out.exists() or args.out.with_suffix(".tiles.bin").exists() or
        args.out.with_suffix(".words.bin").exists() or list(args.out.parent.glob(args.out.stem + "_*.png"))):
        parser.error("output already exists; use a fresh path")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if hashlib.sha256((args.run_dir / "LEZAC.EXE").read_bytes()).digest() != hashlib.sha256(exe.read_bytes()).digest():
        raise RuntimeError("temporary executable differs from checked image")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_PLAYER_WALK_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image, args.route, args.animation, args.world, args.transients)
        return original(run_dir, pid, base, state, phase)
    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--startup-seconds", str(args.startup_seconds),
                "--intro-seconds", str(args.intro_seconds),
                "--level-start-seconds", str(args.level_start_seconds),
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
