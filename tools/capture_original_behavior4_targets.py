#!/usr/bin/env python3
"""Capture seeded active/inactive behavior-4 target decisions in private DOSBox."""
from __future__ import annotations

import argparse
import hashlib
import json
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

ROOT = Path(__file__).resolve().parent.parent
EXE_SHA = "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec"
SCHEMA = "lezac-behavior4-target-decisions-v1"
HOOKS = ((0x7EC5, bytes.fromhex("c70682200100")),
         (0x7EEA, bytes.fromhex("803ee67901")),
         (0x654E, bytes.fromhex("807ecf06")))
WINDOWS = dict(HOOKS) | {
    0x62DA: bytes.fromhex("803ee67901752f"),
    0x6315: bytes.fromhex("803ee77901752f"),
    0x6500: bytes.fromhex("8b46f69931d029d099"),
    0x6538: bytes.fromhex("3bd37f067c103bc1760c"),
    0x70D7: bytes.fromhex("a1c27831d2f736e8c19209c0756a"),
    0x710D: bytes.fromhex("8d7efc16578d7efa1657"),
    0x712B: bytes.fromhex("a17420d1e0509aa8132009"),
}
# Only flag value 1 participates in the original target-coordinate reads.
# The both-out case is last: the native outer loop may then leave gameplay.
CASES = (
    ("p1_nearer", 1, 1, (346, 96), (296, 96)),
    ("p2_nearer", 1, 1, (376, 96), (326, 96)),
    ("tie_horizontal", 1, 1, (356, 96), (316, 96)),
    ("tie_diagonal", 1, 1, (356, 106), (326, 116)),
    ("p1_state2_p2_active", 2, 1, (346, 96), (316, 96)),
    ("p1_out_p2_alive", 0, 1, (346, 96), (316, 96)),
    ("p2_state2_p1_active", 1, 2, (346, 96), (316, 96)),
    ("p2_out_p1_alive", 1, 0, (346, 96), (316, 96)),
    ("threshold_equality", 1, 1, (411, 96), (456, 96)),
    ("negative_diagonal", 1, 1, (296, 76), (456, 96)),
    ("both_state2", 2, 2, (346, 96), (316, 96)),
    ("p1_state2_p2_out", 2, 0, (346, 96), (316, 96)),
    ("both_out", 0, 0, (346, 96), (316, 96)),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lcg(seed: int) -> int:
    return (seed * 0x08088405 + 1) & 0xFFFFFFFF


def trampoline(stage: int, image: bytes) -> bytes:
    plain = actors.trampoline(stage, image)
    if stage != 3:
        return plain
    entry, raw = HOOKS[stage - 1]
    target = 0xF400 + (stage - 1) * 0x80
    body = plain[2:-(2 + len(raw) + 3)]
    # Players join at 654e too; only behavior-4 monsters selected a target.
    code = bytearray(bytes.fromhex("9c60807ef1027500807ecf047500"))
    epilogue = len(code) + len(body)
    code[7] = epilogue - 8
    code[13] = epilogue - 14
    code += body + b"\x61\x9d" + raw
    code += jump(target + len(code), entry + len(raw))
    if len(code) > 0x80:
        raise RuntimeError("filtered target trampoline exceeds scratch window")
    return bytes(code)


def self_check() -> bytes:
    exe = (ROOT / "LEZAC.EXE").read_bytes()
    if hashlib.sha256(exe).hexdigest() != EXE_SHA:
        raise RuntimeError("original executable hash mismatch")
    image = exe[0x770:]
    for at, expected in WINDOWS.items():
        if image[at:at + len(expected)] != expected:
            raise RuntimeError(f"original target window mismatch at {at:04x}")
    actors.HOOKS = tuple((at, len(raw)) for at, raw in HOOKS)
    for stage in range(1, len(HOOKS) + 1):
        trampoline(stage, image)
    print(f"behavior4_targets_self_check=ok windows={len(WINDOWS)} cases={len(CASES)} live=0", flush=True)
    return image


def capture(pid: int, base: int, output: Path, image: bytes, window: str) -> dict:
    cs, ds = base + (actors.CS << 4), base + (seeder.RUNTIME_DS << 4)
    installed = []
    observations = []
    sequence = 0
    pulses = []
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(at, size):
            data = os.pread(mem.fileno(), size, at)
            if len(data) != size:
                raise RuntimeError("short owned-child memory read")
            return data

        def write(at, data):
            if os.pwrite(mem.fileno(), data, at) != len(data):
                raise RuntimeError("short owned-child memory write")

        def stop():
            os.kill(pid, signal.SIGSTOP)
            deadline = time.monotonic() + 3
            while "State:\tT" not in Path(f"/proc/{pid}/status").read_text():
                if time.monotonic() >= deadline:
                    raise RuntimeError("owned child did not stop")
                time.sleep(.001)

        def wait(stage, initial=False):
            nonlocal sequence
            started = time.monotonic()
            deadline = started + (60 if initial else 10)
            next_pulse = started
            while time.monotonic() < deadline:
                marker, *regs, flag, current = struct.unpack("<9H", read(cs + actors.SCRATCH, 18))
                if marker and flag == 0 and current > sequence:
                    sequence = current
                    if regs[1] - regs[0] != seeder.RUNTIME_DS - actors.CS:
                        raise RuntimeError("runtime code/data segment relationship changed")
                    if marker == stage:
                        return regs
                    if not initial:
                        raise RuntimeError(f"actor-pass stage {marker}, wanted {stage}")
                    release(marker)
                if initial and not marker and time.monotonic() >= next_pulse:
                    subprocess.run(["xdotool", "windowfocus", "--sync", window], check=True, timeout=3)
                    subprocess.run(["xdotool", "keydown", "2"], check=True, timeout=3)
                    time.sleep(.05)
                    subprocess.run(["xdotool", "keyup", "2"], check=True, timeout=3)
                    pulses.append({"key": "2", "elapsed_seconds": time.monotonic() - started})
                    (output / "bootstrap.json").write_text(json.dumps({"physical_key_pulses": pulses,
                        "reached_gameplay_hook": False}, sort_keys=True) + "\n")
                    next_pulse = time.monotonic() + .75
                time.sleep(.001)
            raise RuntimeError(f"actor-pass stage {stage} timeout")

        def release(stage):
            write(cs + actors.SCRATCH + 14, struct.pack("<H", stage))

        def state():
            return {"frame": int.from_bytes(read(ds + 0x78C2, 2), "little"),
                    "rng": int.from_bytes(read(ds + 0x1AFE, 4), "little"),
                    "actor_count": read(ds + 0x208D, 1)[0],
                    "actor": read(ds + 0x1BD4, 38).hex(),
                    "visual": read(ds + 0xC22E, 8).hex(),
                    "p1": read(ds + 0x1B88, 38).hex(),
                    "p2": read(ds + 0x1BAE, 38).hex(),
                    "p1_visual": read(ds + 0xC21E, 8).hex(),
                    "p2_visual": read(ds + 0xC226, 8).hex(),
                    "player_flags": read(ds + 0x79E5, 14).hex()}

        for at, expected in WINDOWS.items():
            if read(cs + at, len(expected)) != expected:
                raise RuntimeError(f"runtime instruction mismatch at {at:04x}")
        scratch = read(cs + 0xF400, 0x212)
        if scratch != bytes(0x212):
            raise RuntimeError("instrumentation scratch is not empty")
        try:
            stop()
            for stage, (entry, raw) in enumerate(HOOKS, 1):
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, trampoline(stage, image))
                installed.append((entry, raw))
                write(cs + entry, jump(entry, target))
            os.kill(pid, signal.SIGCONT)
            before_regs = wait(1, initial=True)
            (output / "bootstrap.json").write_text(json.dumps({"physical_key_pulses": pulses,
                "reached_gameplay_hook": True, "registers": before_regs}, sort_keys=True) + "\n")
            memory_base = cs - (before_regs[0] << 4)
            width = int.from_bytes(read(ds + 0xC204, 2), "little")
            if width != 60 or read(ds + 0x79B7, 1) != b"\x01":
                raise RuntimeError("probe is not at the level-1 scene")
            if read(ds + 0x1B89, 1) != b"\x00" or read(ds + 0x1BAF, 1) != b"\x01":
                raise RuntimeError("native player visual slots differ")
            initial = state()
            if bytes.fromhex(initial["player_flags"])[1:3] != b"\x01\x01":
                raise RuntimeError("probe did not enter active two-player gameplay")
            from PIL import ImageGrab
            geometry = dict(row.split("=", 1) for row in subprocess.check_output(
                ["xdotool", "getwindowgeometry", "--shell", window], text=True).splitlines())
            x, y, w, h = (int(geometry[key]) for key in ("X", "Y", "WIDTH", "HEIGHT"))
            if (w, h) != (320, 200):
                raise RuntimeError("original scene is not an unscaled VGA frame")
            ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).crop((x, y, x + w, y + h)).save(output / "original-before-seeding.png")
            objects = memory_base + (int.from_bytes(read(ds + 0xC1FE, 2), "little") << 4)
            word_offset, word_segment = struct.unpack("<HH", read(ds + 0x6612, 4))
            words = memory_base + (word_segment << 4) + word_offset
            descriptors = read(ds + 0xC322, 368)
            actor = bytearray(38)
            actor[0], actor[1], actor[3], actor[4], actor[0x15], actor[0x24] = 2, 2, 11, 11, 4, 255
            struct.pack_into("<HHH", actor, 14, 14, 271, 75)
            actor[0x16:0x1D] = bytes((40, 40, 42, 0, 3, 1, 1))
            for index, (name, state1, state2, p1, p2) in enumerate(CASES):
                # Every write is an explicit case-boundary seed, never an observed result.
                write(objects, bytes(1980))
                write(words, bytes(3960))
                write(ds + 0x79A6, b"\x00")
                write(ds + 0x2076, bytes(2))
                write(ds + 0x207E, struct.pack("<H", 199))
                write(ds + 0x2080, bytes(2))
                write(ds + 0x208E, b"\x00")
                write(ds + 0x79E6, bytes((state1, state2)))
                write(ds + 0x79E8, bytes(2))
                write(ds + 0x1AFE, struct.pack("<I", 0x12345678))
                write(ds + 0x78C2, struct.pack("<H", 420))
                write(ds + 0x1BD4, actor)
                write(ds + 0x208D, b"\x01")
                write(ds + 0xC496, b"\x03")
                write(ds + 0xC21E, struct.pack("<HH", *p1))
                write(ds + 0xC226, struct.pack("<HH", *p2))
                write(ds + 0xC22E, struct.pack("<HH", 336, 96) + descriptors[160:164])
                before = state()
                release(1)
                target_regs = wait(3)
                if target_regs[5] < 0x3A:
                    raise RuntimeError("target stack locals wrap the segment")
                locals_at = memory_base + (target_regs[3] << 4) + target_regs[5] - 0x3A
                target_stack = read(locals_at, 0x3A)
                selected_delta = list(struct.unpack_from("<hh", target_stack, 0x34))[::-1]
                release(3)
                after_regs = wait(2)
                after = state()
                if before["frame"] != 420 or after["frame"] != 420 or after["actor_count"] != 1:
                    raise RuntimeError("probe did not retain a single same-frame actor pass")
                steps = next((i for i, seed in enumerate((0x12345678, lcg(0x12345678), lcg(lcg(0x12345678))))
                              if seed == after["rng"]), None)
                if steps not in (0, 2):
                    raise RuntimeError("actor-pass RNG does not identify zero or two draws")
                row = {"name": name, "seeded_p1_state": state1, "seeded_p2_state": state2,
                       "before": before, "after": after, "before_registers": before_regs,
                       "after_registers": after_regs, "rng_steps": steps,
                       "target_registers": target_regs, "target_stack_hex": target_stack.hex(),
                       "selected_delta": selected_delta,
                       "observed_branch": "random" if steps == 2 else "homing"}
                observations.append(row)
                (output / "candidate.json").write_text(json.dumps({"schema": SCHEMA, "initial": initial,
                    "cases": observations, "complete": False}, sort_keys=True) + "\n")
                print(f"behavior4_targets_original case={name} rng_steps={steps}", flush=True)
                if index + 1 < len(CASES):
                    release(2)
                    before_regs = wait(1)
            return {"schema": SCHEMA, "initial": initial, "cases": observations, "complete": True,
                    "executable_sha256": EXE_SHA, "seeded_case_boundaries": True,
                    "seeded_empty_terrain": True, "per_tick_actor_seed": False,
                    "natural_campaign_claim": False, "pixel_parity_claim": False,
                    "original_fidelity_claim": False}
        finally:
            # Never resume an IP inside cleared scratch: the owner kills this child.
            stop()
            for entry, raw in installed:
                write(cs + entry, raw)
            write(cs + 0xF400, scratch)
            restored = all(read(cs + entry, len(raw)) == raw for entry, raw in installed)
            scratch_restored = read(cs + 0xF400, len(scratch)) == scratch
            (output / "restoration.json").write_text(json.dumps({"hooks_restored": restored,
                "scratch_restored": scratch_restored, "child_retained_stopped": True,
                "installed_hooks": len(installed)}, sort_keys=True) + "\n")
            if not restored or not scratch_restored:
                raise RuntimeError("original instrumentation restoration failed")


def locate_runtime(child: subprocess.Popen) -> tuple[int, str]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("owned original exited during bootstrap")
        candidates = []
        with open(f"/proc/{child.pid}/mem", "rb", buffering=0) as mem:
            for at in seeder.scan_process(child.pid, seeder.DATA_SIGNATURE):
                base = at - ((seeder.RUNTIME_DS << 4) + seeder.DATA_STRING_OFFSET)
                cs = base + (actors.CS << 4)
                try:
                    if all(os.pread(mem.fileno(), len(raw), cs + entry) == raw
                           for entry, raw in WINDOWS.items()):
                        candidates.append(base)
                except OSError:
                    continue
        if len(candidates) > 1:
            raise RuntimeError("original runtime signature is ambiguous")
        windows = subprocess.run(["xdotool", "search", "--pid", str(child.pid), "--name", "DOSBox"],
                                 capture_output=True, text=True, timeout=3).stdout.splitlines()
        if len(candidates) == 1 and len(windows) == 1:
            return candidates[0], windows[0]
        time.sleep(.1)
    raise RuntimeError("owned original code and window did not become ready")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    image = self_check()
    if args.self_check:
        return 0
    if not (args.run_dir and args.out_dir and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("live capture requires a temporary run-dir, fresh out-dir and both approval flags")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    if sha(args.run_dir / "LEZAC.EXE") != EXE_SHA or args.out_dir.exists():
        parser.error("temporary original differs or output already exists")
    assets = {name: sha(ROOT / name) for name in environment.REQUIRED_ASSETS}
    if {name: sha(args.run_dir / name) for name in assets} != assets:
        parser.error("temporary assets differ from the guarded checkout")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_BEHAVIOR4_TARGETS_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    args.out_dir.mkdir(parents=True)
    output = args.out_dir.resolve()
    config = output / "dosbox.conf"
    config.write_text("[sdl]\nfullscreen=false\noutput=surface\n"
                      f"[dosbox]\nmemsize=16\ncaptures={output}\n"
                      "[render]\nframeskip=0\naspect=false\nscaler=none\n"
                      "[cpu]\ncore=normal\ncycles=fixed 6000\n")
    command = ["dosbox", "-conf", str(config), "-c", f'mount c "{args.run_dir.resolve()}"',
               "-c", "c:", "-c", "LEZAC.EXE"]
    child = None
    try:
        with (output / "dosbox.log").open("wb") as log:
            child = subprocess.Popen(command, env=dict(os.environ, SDL_AUDIODRIVER="dummy"),
                                     stdout=log, stderr=subprocess.STDOUT)
            try:
                base, window = locate_runtime(child)
                report = capture(child.pid, base, output, image, window)
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
        report["owned_child_returncode"] = child.returncode
        report["launch_command"] = command
        report["audio_driver"] = "dummy"
        report["producer_sha256"] = sha(Path(__file__))
        report["assets_sha256"] = assets
        report["dependency_sha256"] = {name: sha(ROOT / "tools" / name) for name in (
            "capture_original_behavior4_lockstep.py", "capture_original_death_transients.py",
            "capture_original_bomb_fuses.py", "seed_original_level.py")}
        report["files"] = {path.name: sha(path) for path in output.iterdir() if path.is_file()}
        (output / "capture.json").write_text(json.dumps(report, sort_keys=True) + "\n")
        return 0
    except BaseException as error:
        (output / "failure.json").write_text(json.dumps({"error": repr(error),
            "owned_child_returncode": None if child is None else child.poll(),
            "original_fidelity_claim": False}, sort_keys=True) + "\n")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
