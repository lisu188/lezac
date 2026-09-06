#!/usr/bin/env python3
"""Capture continuous level-7 boss, link and player updates in original DOSBox."""

import argparse
import hashlib
import os
from pathlib import Path
import signal
import struct
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
WINDOWS = player.WINDOWS | render.WINDOWS | {
    0x7EBB: bytes.fromhex("803ef97900"),
    0x7EC5: bytes.fromhex("c70682200100"),
}
CASES = (("idle_phase", 100), ("approach", 101), ("clock_wrap", 65520))
SAMPLES = 200
VIEWS = (0, 1, 15, 16, 28, 57, 99, 139, 179, 199)


def controls(name, sample):
    return "left" if name == "approach" and sample < 100 else (
        "right" if name == "approach" and sample < 140 else "idle")


def capture(pid, base, output, image, near_encounter=False):
    actors.HOOKS = HOOKS
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

        def wait(stage, initial=False, allow_view=False):
            nonlocal sequence, stopped_stage
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + actors.SCRATCH, 18))
                if marker and not flag and current > sequence:
                    sequence = current
                    if marker == stage or (allow_view and marker == 3):
                        if regs[1] - regs[0] != 0xAA2:
                            raise RuntimeError("unexpected original boss segments")
                        stopped_stage = marker
                        return regs
                    if not initial:
                        raise RuntimeError(f"boss stage {marker}, wanted {stage}")
                    release(marker)
                time.sleep(0.001)
            raise RuntimeError(f"boss stage {stage} timeout")

        for at, expected in WINDOWS.items():
            if read(cs + at, len(expected)) != expected:
                raise RuntimeError(f"original boss instruction mismatch at {at:04x}")
        if read(cs + 0xF400, 0x212) != bytes(0x212):
            raise RuntimeError("boss instrumentation scratch not empty")
        os.kill(pid, signal.SIGSTOP)
        try:
            deadline = time.monotonic() + 2
            while "State:\tT" not in Path(f"/proc/{pid}/status").read_text():
                if time.monotonic() > deadline:
                    raise RuntimeError("boss child stop timeout")
                time.sleep(0.001)
            for stage, (entry, _) in enumerate(HOOKS, 1):
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, actors.trampoline(stage, image))
                write(cs + entry, jump(entry, target))
        finally:
            os.kill(pid, signal.SIGCONT)
        regs = wait(1, initial=True)
        memory_base = cs - (regs[0] << 4)
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
                 "capture=boss_continuous_original_v1 level=7 temp_copy=1 seeded_case_boundary=1 per_tick_actor_seed=0 observed_backdrop=1 natural_campaign=0",
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
            return (f"count={count} visuals={read(ds + 0xC496, 1)[0]} link_count={link_count}"
                    f" links={read(ds + 0x79FA, link_count * 16).hex()} rng={read(ds + 0x1AFE, 4).hex()}"
                    f" p1={read(ds + 0x1B88, 38).hex()} player={read(ds + 0xC21E, 8).hex()}"
                    f" player_state={read(ds + 0x79E6, 1)[0]} energy={read(ds + 0x79EC, 1)[0]} lives={read(ds + 0x79EA, 1)[0]}"
                    f" actors={','.join(rows) or '-'}")

        for name, frame in CASES:
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
            write(ds + 0x79EA, b"\x63\x63\x64\x64")
            write(ds + 0x79A6, bytes(1))
            write(ds + 0x2080, bytes(2))
            write(ds + 0x207E, struct.pack("<H", 199))
            write(ds + 0x2076, bytes(2))
            write(ds + 0x208E, bytes(1))
            write(ds + 0x2098, bytes(6))
            write(ds + 0xC49C, b"\x01")
            write(ds + 0x1AFE, struct.pack("<I", 0x12345678))
            write(ds + 0x78C2, struct.pack("<H", frame))
            lines.append(f"case name={name} frame={frame} regs={struct.pack('<6H', *regs).hex()} " + state())
            output.write_text("\n".join(lines) + "\n", encoding="ascii")
            for sample in range(SAMPLES):
                if word(ds + 0x78C2) != (frame + sample) % 65536:
                    raise RuntimeError("nonconsecutive original boss pass")
                release(1)
                before = wait(2, allow_view=True)
                control = controls(name, sample)
                if stopped_stage == 2:
                    write(ds + 0x1B82, bytes(player.CONTROLS[control]))
                    input_regs = struct.pack('<6H', *before).hex()
                    release(2)
                    view = wait(3)
                else:
                    input_regs = "-"
                    view = before
                delta = ",".join(f"{i}:{value:02x}" for i, value in enumerate(read(objects, len(tiles))) if value != tiles[i]) or "-"
                lines.append(f"tick sample={sample} frame={word(ds + 0x78C2)} control={control} input_regs={input_regs}"
                             f" regs={struct.pack('<6H', *view).hex()} map={delta} " + state())
                if sample in VIEWS:
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
            lines.append(f"end samples={SAMPLES}")
            output.write_text("\n".join(lines) + "\n", encoding="ascii")
            print(f"boss_continuous_original case={name} samples={SAMPLES} views={len(VIEWS)}", flush=True)
        lines.append(f"complete cases={len(CASES)} samples={len(CASES) * SAMPLES} views={len(CASES) * len(VIEWS)}")
        output.write_text("\n".join(lines) + "\n", encoding="ascii")
        for at, length in HOOKS:
            write(cs + at, image[at:at + length])
        release(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--near-encounter", action="store_true")
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    exe = (ROOT / "LEZAC.EXE").read_bytes()
    if hashlib.sha256(exe).hexdigest() != "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec":
        raise RuntimeError("original executable hash mismatch")
    image = exe[0x770:]
    actors.HOOKS = HOOKS
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"boss instruction mismatch at {at:04x}")
    for stage in range(1, len(HOOKS) + 1):
        actors.trampoline(stage, image)
    print(f"boss_continuous_capture_self_check=ok windows={len(WINDOWS)} cases={len(CASES)} samples={SAMPLES} live=0", flush=True)
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
    environment.XVFB_MARKER = "LEZAC_BOSS_CONTINUOUS_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def hook(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, args.out, image, args.near_encounter)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = hook
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "7",
                "--startup-seconds", "10", "--intro-seconds", "8", "--level-start-seconds", "5",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
