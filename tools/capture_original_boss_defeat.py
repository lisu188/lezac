#!/usr/bin/env python3
"""Capture original level-7 fatal/nonfatal boss hits from a boundary-seeded bomb."""

import argparse
import hashlib
import os
from pathlib import Path
import signal
import shutil
import struct
import subprocess
import sys
import time

import capture_original_behavior4_lockstep as environment
import capture_original_death_transients as actors
from capture_original_bomb_fuses import jump
import capture_original_player_walk as player
import capture_original_render_boundary as render
import seed_original_level as seeder


ROOT = Path(__file__).resolve().parent.parent
HOOKS = ((0x7EBB, 5), (0x6813, 3), (0x7A57, 5))
REENTRY_HOOKS = HOOKS + ((0x7EF8, 4), (0x7F03, 6), (0x2ADC, 3), (0x2C72, 5), (0x2C77, 3))
REENTRY_WINDOWS = {
    0x7EF8: bytes.fromhex("fe06b979803eb979e6"),
    0x7F03: bytes.fromhex("c70682200100"),
    0x2ADC: bytes.fromhex("5589e5"),
    0x2C77: bytes.fromhex("a25820"),
}
INTRO_CALL = bytes.fromhex("9a0f034a08")
WINDOWS = player.WINDOWS | render.WINDOWS | {
    0x7EBB: bytes.fromhex("803ef97900"),
    0x7EC5: bytes.fromhex("c70682200100"),
}
CASES = (("defeat_even", 100), ("defeat_odd", 101))
IMPACT_CASES = (("hit_even", 100), ("hit_odd", 101))
MASS_CASES = (("massive_even", 100), ("massive_odd", 101))
IMPACT_WINDOWS = {
    0x43E8: bytes.fromhex("8b9520c2c47ef4268b45022bc2"),
    0x4503: bytes.fromhex("c47ef4268b450231d203c113d3"),
    0x5AE9: bytes.fromhex("b810002bc28b7e0436c47d0426884514"),
}
MASS_WINDOWS = {
    0x3A56: bytes.fromhex("a1762048bb0b00f7e389c38b879e203b067220"),
    0x5F5F: bytes.fromhex("803e1e66007e4de8edda8b3e742080bdd578017609a01e6698d1e0a21e66"),
    0x3108: bytes.fromhex("c47efc81c716000657a06c0050a06d00506a036a01"),
    0x7C93: bytes.fromhex("c47efc26ff4d10c47efc26837d1000"),
    0x7D11: bytes.fromhex("6b3e82202681c7621b1e57a0822050e84888"),
    0x7D78: bytes.fromhex("8b3e8220c685e57902"),
    0x7D94: bytes.fromhex("a1c0c3c47ef826894506"),
    0x7F40: bytes.fromhex("8b3e822080bde579017403e9f600"),
}
SAMPLES = 180
VIEWS = (0, 1, 2, 3, 5, 10, 20, 39, 59, 79, 99, 119, 139, 159, 179)
REENTRY_VIEWS = VIEWS + (199, 239, 259, 279, 319, 379, 419)
FIRE_REENTRY_VIEWS = (0, 1, 2, 3, 5, 10, 20, 39, 59, 79, 99, 100, 101, 102, 119, 139)


def capture(pid, base, output, image, near_encounter=False, nonfatal=False, massive=False,
            reentry_wait=False, run_dir=None, zero_reserve=False, fire_reentry=False):
    hooks = REENTRY_HOOKS if reentry_wait else HOOKS
    actors.HOOKS = hooks
    actors.SCRATCH = 0xF800 if reentry_wait else 0xF600
    massive = massive or reentry_wait
    nonfatal = nonfatal or massive
    weapon = 3 if massive else 0
    cases = MASS_CASES[:1] if reentry_wait else MASS_CASES if massive else (IMPACT_CASES if nonfatal else CASES)
    samples = 420 if reentry_wait else SAMPLES
    views = REENTRY_VIEWS if reentry_wait else VIEWS
    if zero_reserve:
        cases = (("zero_reserve_even", 100),)
    if fire_reentry:
        cases, samples, views = (("fire_reentry_even", 100),), 140, FIRE_REENTRY_VIEWS
    prefix = "boss_mass" if massive else ("boss_impact" if nonfatal else "boss_defeat")
    windows = WINDOWS | (IMPACT_WINDOWS if nonfatal else {}) | (MASS_WINDOWS if massive else {})
    windows |= REENTRY_WINDOWS if reentry_wait else {}
    cs, ds = base + (actors.CS << 4), base + (seeder.RUNTIME_DS << 4)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(at, size):
            data = os.pread(mem.fileno(), size, at)
            if len(data) != size:
                raise RuntimeError("short boss memory read")
            return data

        def write(at, data):
            if os.pwrite(mem.fileno(), data, at) != len(data):
                raise RuntimeError("short boss memory write")

        def word(at):
            return struct.unpack("<H", read(at, 2))[0]

        def release(stage):
            write(cs + actors.SCRATCH + 14, struct.pack("<H", stage))

        sequence = 0

        stopped_stage = 0
        lines = []
        sample = -1
        resets = 0
        boundary_counts = {stage: 0 for stage in range(4, 9)}

        def key(name):
            windows = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True, timeout=5).split()
            if len(windows) != 1:
                raise RuntimeError("expected one DOSBox window on private display")
            subprocess.run(["xdotool", "windowfocus", windows[0]], check=True, timeout=5)
            subprocess.run(["xdotool", "key", "--clearmodifiers", name], check=True, timeout=5)

        def boundary(stage, regs):
            nonlocal resets
            labels = {4: "fallback_increment", 5: "fallback_promote", 6: "level_init", 7: "intro_wait", 8: "intro_ack"}
            if stage not in labels or sample < 0:
                raise RuntimeError("unexpected reentry boundary")
            boundary_counts[stage] += 1
            fields = (f"boundary sample={sample} stage={labels[stage]} frame={word(ds + 0x78C2)}"
                      f" regs={struct.pack('<6H', *regs).hex()} counter={read(ds + 0x79B9, 1)[0]}"
                      f" flags={read(ds + 0x79E5, 9).hex()} gate={read(ds + 0x79CA, 1)[0]}"
                      f" p1={read(ds + 0x1B88, 38).hex()} p2={read(ds + 0x1BAE, 38).hex()}"
                      f" visuals={read(ds + 0xC21E, 16).hex()} rng={read(ds + 0x1AFE, 4).hex()}")
            if zero_reserve or fire_reentry:
                fields += f" active_players={read(ds + 0x79B8, 1)[0]}"
            lines.append(fields)
            if stage != 4:
                print(fields, flush=True)
            if stage == 7:
                before = set(run_dir.glob("*.png")) | set(run_dir.glob("*.bmp"))
                key("ctrl+F5")
                deadline = time.monotonic() + 5
                fresh = set()
                while time.monotonic() < deadline and not fresh:
                    time.sleep(0.1)
                    fresh = (set(run_dir.glob("*.png")) | set(run_dir.glob("*.bmp"))) - before
                if len(fresh) != 1:
                    raise RuntimeError("restart intro screenshot not created")
                source = fresh.pop()
                destination = output.with_name(f"{output.stem}_intro_{resets}{source.suffix}")
                shutil.copyfile(source, destination)
                lines.append(f"intro sample={sample} file={destination.name} sha256={hashlib.sha256(destination.read_bytes()).hexdigest()}")
                release(stage)
                key("Return")
            else:
                release(stage)
            if stage == 8:
                resets += 1
            if stage != 4:
                output.write_text("\n".join(lines) + "\n", encoding="ascii")

        def wait(stage, initial=False, allow_view=False):
            nonlocal sequence, stopped_stage
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + actors.SCRATCH, 18))
                if marker and not flag and current > sequence:
                    sequence = current
                    if reentry_wait and marker >= 4:
                        if regs[1] - regs[0] != 0xAA2:
                            raise RuntimeError("unexpected reentry boundary segments")
                        boundary(marker, regs)
                        deadline = time.monotonic() + 60
                        continue
                    if marker == stage or (allow_view and marker == 3):
                        if regs[1] - regs[0] != 0xAA2:
                            raise RuntimeError("unexpected original boss segments")
                        stopped_stage = marker
                        return regs
                    if not initial:
                        raise RuntimeError(f"boss stage {marker}, wanted {stage}")
                    release(marker)
                time.sleep(0.001)
            if lines:
                output.write_text("\n".join(lines) + "\n", encoding="ascii")
            raise RuntimeError(f"boss stage {stage} timeout marker={marker} flag={flag} sequence={sequence}/{current}"
                               f" frame={word(ds + 0x78C2)} flags={read(ds + 0x79E5, 9).hex()} registers={regs}")

        for at, expected in windows.items():
            if read(cs + at, len(expected)) != expected:
                raise RuntimeError(f"original boss instruction mismatch at {at:04x}")
        arena_size = actors.SCRATCH + 18 - 0xF400
        if read(cs + 0xF400, arena_size) != bytes(arena_size):
            raise RuntimeError("boss instrumentation scratch not empty")
        os.kill(pid, signal.SIGSTOP)
        try:
            deadline = time.monotonic() + 2
            while "State:\tT" not in Path(f"/proc/{pid}/status").read_text():
                if time.monotonic() > deadline:
                    raise RuntimeError("boss child stop timeout")
                time.sleep(0.001)
            for stage, (entry, _) in enumerate(hooks, 1):
                if stage == 7:
                    continue
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, actors.trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        finally:
            os.kill(pid, signal.SIGCONT)
        regs = wait(1, initial=True)
        memory_base = cs - (regs[0] << 4)
        runtime_image = bytearray(image)
        if reentry_wait:
            # Install the far-call hook only after measuring the actual load segment.
            expected_far = INTRO_CALL[:3] + struct.pack("<H", 0x084A + regs[0])
            if image[0x2C72:0x2C77] != INTRO_CALL or read(cs + 0x2C72, 5) != expected_far:
                raise RuntimeError("unexpected relocated intro keyboard call")
            runtime_image[0x2C72:0x2C77] = expected_far
            write(cs + 0xF700, actors.trampoline(7, runtime_image))
            write(cs + 0x2C72, jump(0x2C72, 0xF700))
        warmup = 0
        while near_encounter and warmup < 600:
            head_visual = read(ds + 0x1BD5, 1)[0]
            x, y = struct.unpack("<HH", read(ds + 0xC21E + head_visual * 8, 4))
            if x >= 720 and y >= 275:
                break
            release(1)
            wait(2)
            write(ds + 0x1B82, bytes(player.CONTROLS["idle"]))
            release(2)
            wait(3)
            release(3)
            regs = wait(1)
            warmup += 1
        if warmup == 600:
            raise RuntimeError("boss did not naturally approach the player's viewport")
        width, height = word(ds + 0xC204), word(ds + 0x2096) // 8 + 21
        if (width, height) != (140, 52) or read(ds + 0x208D, 1) != b"\x07" or read(ds + 0x79F9, 1) != b"\x06":
            raise RuntimeError("unexpected original boss scene")
        objects = memory_base + (word(ds + 0xC1FE) << 4)
        words = memory_base + (word(ds + 0x6614) << 4) + word(ds + 0x6612)
        tiles, map_words = read(objects, width * height), read(words, width * height * 2)
        background = read(memory_base + (word(ds + 0xC49A) << 4) + word(ds + 0xC498), 60000)
        descriptors = read(ds + 0xC322, 368)
        initial_actors = read(ds + 0x1BD4, 7 * 38)
        initial_links = read(ds + 0x79FA, 6 * 16)
        initial_player = read(ds + 0x1B88, 38)
        initial_visuals = read(ds + 0xC21E, 9 * 8)
        lines = ["# Original continuous gameplay; observed entry state restored only at case boundaries.",
                 f"# natural_idle_warmup_updates={warmup} near_encounter={int(near_encounter)} forced_boss_position=0",
                 "# register_order=cs,ds,es,ss,saved-sp,bp little_endian_words=1",
                 "# executable_sha256=" + hashlib.sha256((ROOT / "LEZAC.EXE").read_bytes()).hexdigest(),
                 f"capture={prefix}_probe_v1 level=7 temp_copy=1 seeded_case_boundary=1 seeded_head_hp=0 seeded_head_lives={int(nonfatal)} seeded_bomb=1"
                 + (f" seeded_weapon={weapon}" if massive else "") + " per_tick_actor_seed=0 natural_campaign=0",
                 f"map width={width} height={height} bytes={tiles.hex()} words={map_words.hex()}",
                 f"backdrop bytes={render.rle(background)}",
                 f"sprites descriptors={descriptors.hex()}"]

        def state():
            count = read(ds + 0x208D, 1)[0]
            link_count = read(ds + 0x79F9, 1)[0]
            if count > 30 or link_count > 6:
                raise RuntimeError("invalid original boss actor/link count")
            rows = []
            for slot in range(1, count + 1):
                raw = read(ds + 0x1BAE + slot * 38, 38)
                visual = read(ds + 0xC21E + raw[1] * 8, 8)
                rows.append(raw.hex() + ":" + visual.hex())
            flame_count = word(ds + 0x2076)
            if flame_count > 199:
                raise RuntimeError("invalid original flame count")
            flames = ",".join(read(ds + 0x2093 + slot * 11, 11).hex() + ":" + read(ds + 0x78D5 + slot, 1).hex()
                              for slot in range(1, flame_count + 1)) or "-"
            return (f"count={count} visuals={read(ds + 0xC496, 1)[0]} link_count={link_count}"
                    f" links={read(ds + 0x79FA, link_count * 16).hex()} rng={read(ds + 0x1AFE, 4).hex()}"
                    f" p1={read(ds + 0x1B88, 38).hex()} player={read(ds + 0xC21E, 8).hex()}"
                    f" player_state={read(ds + 0x79E6, 1)[0]} energy={read(ds + 0x79EC, 1)[0]} lives={read(ds + 0x79EA, 1)[0]}"
                    f" actors={','.join(rows) or '-'} flames={flames} globals={read(ds + 0x79C0, 58).hex()}"
                    + (f" fallback={read(ds + 0x79B9, 1)[0]} resets={resets}" if reentry_wait else "")
                    + (f" active_players={read(ds + 0x79B8, 1)[0]}" if zero_reserve or fire_reentry else ""))

        for name, frame in cases:
            write(objects, tiles)
            write(words, map_words)
            write(ds + 0x1BD4, initial_actors)
            write(ds + 0x79FA, initial_links)
            write(ds + 0x1B88, initial_player)
            write(ds + 0xC21E, initial_visuals)
            write(ds + 0x208D, b"\x07")
            write(ds + 0xC496, b"\x09")
            write(ds + 0x79F9, b"\x06")
            write(ds + 0x79E6, b"\x01\x00")
            write(ds + 0x79EA, bytes([1 if zero_reserve else 99, 99, 100, 100]))
            write(ds + 0x79A6, bytes(1))
            write(ds + 0x2080, bytes(2))
            write(ds + 0x207E, struct.pack("<H", 199))
            write(ds + 0x2076, bytes(2))
            write(ds + 0x208E, bytes(1))
            write(ds + 0x2098, bytes(6))
            write(ds + 0xC49C, b"\x01")
            write(ds + 0x1AFE, struct.pack("<I", 0x12345678))
            write(ds + 0x78C2, struct.pack("<H", frame))
            write(ds + 0x1BD4 + 2, bytes([int(nonfatal)]))
            write(ds + 0x1BD4 + 36, bytes(1))
            head_visual = initial_actors[1]
            head_x, head_y = struct.unpack_from("<HH", initial_visuals, head_visual * 8)
            bomb = bytearray(38)
            bomb[0], bomb[1], bomb[20], bomb[21] = 13 + weapon, 9, 8, 2
            write(ds + 0x1BAE + 8 * 38, bomb)
            write(ds + 0xC21E + 9 * 8, struct.pack("<HH", head_x + 16, head_y + 8) + descriptors[(58 + weapon) * 4:(59 + weapon) * 4])
            write(ds + 0x208D, b"\x08")
            write(ds + 0xC496, b"\x0a")
            lines.append(f"case name={name} frame={frame} regs={struct.pack('<6H', *regs).hex()} " + state())
            output.write_text("\n".join(lines) + "\n", encoding="ascii")
            for sample in range(samples):
                if fire_reentry and sample == 100:
                    lines.append("key sample=100 address=1b7b value=01 after_state_prepass=1")
                    write(ds + 0x1B7B, b"\x01")
                if word(ds + 0x78C2) != (frame + sample) % 65536:
                    raise RuntimeError("nonconsecutive original boss pass")
                release(1)
                before = wait(2, allow_view=True)
                control = "idle"
                if stopped_stage == 2:
                    write(ds + 0x1B82, bytes(player.CONTROLS[control]))
                    input_regs = struct.pack('<6H', *before).hex()
                    release(2)
                    view = wait(3)
                else:
                    input_regs = "-"
                    view = before
                if reentry_wait:
                    objects = memory_base + (word(ds + 0xC1FE) << 4)
                    words = memory_base + (word(ds + 0x6614) << 4) + word(ds + 0x6612)
                delta = ",".join(f"{i}:{value:02x}" for i, value in enumerate(read(objects, len(tiles))) if value != tiles[i]) or "-"
                lines.append(f"tick sample={sample} frame={word(ds + 0x78C2)} control={control} input_regs={input_regs}"
                             f" regs={struct.pack('<6H', *view).hex()} map={delta} " + state())
                if sample in views:
                    values = {key: word(ds + at) for key, at in (("coarse_x", 0xC216), ("coarse_y", 0xC218), ("fine_x", 0xC20A),
                              ("fine_y", 0xC20C), ("source", 0xC214), ("destination", 0xC1F4))}
                    source = values["source"] + values["fine_x"] + values["fine_y"] * 320
                    buffer = memory_base + (word(ds + 0xC212) << 4)
                    pixels = b"".join(read(buffer + source + row * 320, 312) for row in range(152))
                    lines.append(f"view sample={sample}" + "".join(f" {key}={value}" for key, value in values.items())
                                 + f" indexed_sha256={hashlib.sha256(pixels).hexdigest()} pixels={render.rle(pixels)}")
                    render.write_preview(output.with_name(f"{output.stem}_{name}_{sample:03d}.ppm"), pixels, 312, 152, (ROOT / "BOMPAL.PAL").read_bytes())
                release(3)
                regs = wait(1)
                if sample % 20 == 19:
                    output.write_text("\n".join(lines) + "\n", encoding="ascii")
            if reentry_wait and not fire_reentry and (boundary_counts != {4: 230, 5: 1, 6: 1, 7: 1, 8: 1} or resets != 1):
                raise RuntimeError(f"incomplete reentry boundary coverage: {boundary_counts}")
            if fire_reentry and (resets or boundary_counts[4] == 0 or read(ds + 0x79E6, 1) != b"\x01"):
                raise RuntimeError("input reentry did not resume the player")
            lines.append(f"end samples={samples}")
            output.write_text("\n".join(lines) + "\n", encoding="ascii")
            print(f"{prefix}_original case={name} samples={samples} views={len(views)}", flush=True)
        lines.append(f"complete cases={len(cases)} samples={len(cases) * samples} views={len(cases) * len(views)}")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        for at, length in hooks:
            write(cs + at, runtime_image[at:at + length])
        release(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--near-encounter", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--nonfatal", action="store_true")
    mode.add_argument("--mass", action="store_true", help="nonfatal head hit with the largest bomb; player damage remains enabled")
    mode.add_argument("--reentry-wait", action="store_true", help="one near largest-bomb case through the shared fallback, intro acknowledgement, and 420 rendered frames")
    mode.add_argument("--zero-reserve", action="store_true", help="shared fallback from one reserve life to zero, without eliminating the player")
    mode.add_argument("--fire-reentry", action="store_true", help="seed the fire latch after sample 100's state prepass and capture 140 frames")
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    args.reentry_wait = args.reentry_wait or args.zero_reserve or args.fire_reentry
    if args.reentry_wait:
        args.mass = True
        args.near_encounter = True
    prefix = "boss_mass" if args.mass else ("boss_impact" if args.nonfatal else "boss_defeat")
    windows = WINDOWS | (IMPACT_WINDOWS if args.nonfatal or args.mass else {}) | (MASS_WINDOWS if args.mass else {})
    windows |= REENTRY_WINDOWS | {0x2C72: INTRO_CALL} if args.reentry_wait else {}
    exe = (ROOT / "LEZAC.EXE").read_bytes()
    if hashlib.sha256(exe).hexdigest() != "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec":
        raise RuntimeError("original executable hash mismatch")
    image = exe[0x770:]
    actors.HOOKS = REENTRY_HOOKS if args.reentry_wait else HOOKS
    actors.SCRATCH = 0xF800 if args.reentry_wait else 0xF600
    if args.reentry_wait:
        relocation_count, relocation_table = struct.unpack_from("<H", exe, 6)[0], struct.unpack_from("<H", exe, 24)[0]
        relocations = [struct.unpack_from("<HH", exe, relocation_table + i * 4) for i in range(relocation_count)]
        if struct.unpack_from("<H", exe, 22)[0] != 0 or (0x2C75, 0) not in relocations:
            raise RuntimeError("unexpected intro far-call MZ relocation")
    for at, expected in windows.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"boss instruction mismatch at {at:04x}")
    for stage in range(1, len(actors.HOOKS) + 1):
        actors.trampoline(stage, image)
    print(f"{prefix}_capture_self_check=ok windows={len(windows)} cases={1 if args.reentry_wait else len(CASES)} samples={140 if args.fire_reentry else 420 if args.reentry_wait else SAMPLES} live=0", flush=True)
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
    environment.XVFB_MARKER = "LEZAC_BOSS_DEFEAT_XVFB"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image, args.near_encounter, args.nonfatal, args.mass, args.reentry_wait, run_dir,
                    args.zero_reserve, args.fire_reentry)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "7",
                "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
