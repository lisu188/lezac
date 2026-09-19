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
import capture_original_death_transients as hooks
from capture_original_bomb_fuses import jump
import seed_original_level as seeder

ROOT = Path(__file__).resolve().parents[1]
EXE_HASH = "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec"
HOOKS = ((0x8283, 5), (0x82AF, 5), (0x1D61, 3), (0x829B, 5))
WINDOWS = {
    0x8283: bytes.fromhex("803ec579007425803ec67900741e833e8020007517e8c69a"),
    0x82AF: bytes.fromhex("803e58201b7403e94af6"),
    0x1D61: bytes.fromhex("5589e5"),
    0x829B: bytes.fromhex("803eb779077705e937f5"),
}
CASES = [(bonus, destruction, count) for bonus in (0, 1) for destruction in (0, 1)
         for count in (0, 1) if (bonus, destruction, count) != (1, 1, 0)]
CASES += [(1, 1, 256), (1, 1, 65535), (1, 1, 0)]


def check_image(path: Path) -> bytes:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXE_HASH:
        raise RuntimeError("original executable hash differs")
    image = data[0x770:]
    hooks.HOOKS, hooks.SCRATCH = HOOKS, 0xF600
    for address, expected in WINDOWS.items():
        if image[address:address + len(expected)] != expected:
            raise RuntimeError(f"original instruction mismatch at {address:04x}")
    for stage in range(1, 5):
        hooks.trampoline(stage, image)
    return image


def capture(pid: int, base: int, image: bytes, output: Path) -> None:
    cs, ds = base + (hooks.CS << 4), base + (seeder.RUNTIME_DS << 4)
    records = {"schema": "lezac.original.level1-completion-gate.v1", "exe_sha256": EXE_HASH,
               "seeded": True, "natural_route": False, "original_fidelity_claim": False,
               "hooks": [f"{address:04x}" for address, _ in HOOKS], "cases": [], "freeze": []}
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def read(address: int, size: int) -> bytes:
            data = os.pread(mem.fileno(), size, address)
            if len(data) != size:
                raise RuntimeError("short completion read")
            return data

        def write(address: int, data: bytes) -> None:
            if os.pwrite(mem.fileno(), data, address) != len(data):
                raise RuntimeError("short completion write")

        def stop(action) -> None:
            os.kill(pid, signal.SIGSTOP)
            try:
                deadline = time.monotonic() + 2
                while "State:\tT" not in Path(f"/proc/{pid}/status").read_text():
                    if time.monotonic() > deadline:
                        raise RuntimeError("owned child did not stop")
                    time.sleep(0.001)
                action()
            finally:
                os.kill(pid, signal.SIGCONT)

        sequence, stopped = 0, 0

        def poll():
            nonlocal sequence, stopped
            stage, *registers, flag, current = struct.unpack("<9H", read(cs + hooks.SCRATCH, 18))
            if stage and not flag and current > sequence:
                sequence, stopped = current, stage
                if registers[1] - registers[0] != seeder.RUNTIME_DS - hooks.CS:
                    raise RuntimeError("unexpected original runtime segments")
                return stage, registers
            return None

        def wait(expected: int, initial: bool = False):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                result = poll()
                if result:
                    stage, registers = result
                    if stage == expected:
                        return registers
                    if not initial:
                        raise RuntimeError(f"original branch {stage}, expected {expected}")
                    release(stage)
                time.sleep(0.001)
            raise RuntimeError(f"original completion stage {expected} timed out")

        def release(stage: int) -> None:
            nonlocal stopped
            write(cs + hooks.SCRATCH + 14, struct.pack("<H", stage))
            stopped = 0

        def world(registers) -> dict:
            memory_base = cs - (registers[0] << 4)
            planes = []
            for pointer, stride in ((0xC1E0, 1), (0x6612, 2)):
                offset, segment = struct.unpack("<HH", read(ds + pointer, 4))
                planes.append(hashlib.sha256(read(memory_base + (segment << 4) + offset, 60 * 33 * stride)).hexdigest())
            return {"frame": int.from_bytes(read(ds + 0x78C2, 2), "little"),
                    "level": read(ds + 0x79B7, 1)[0], "map_sha256": planes,
                    "actors_hex": read(ds + 0x1B88, 32 * 38).hex(),
                    "life_state_hex": read(ds + 0x79E5, 8).hex()}

        for address, expected in WINDOWS.items():
            if read(cs + address, len(expected)) != expected:
                raise RuntimeError(f"runtime completion guard {address:04x}")
        if read(cs + 0xF400, 0x212) != bytes(0x212):
            raise RuntimeError("completion instrumentation arena occupied")

        def install() -> None:
            for stage, (address, _) in enumerate(HOOKS, 1):
                target = 0xF400 + (stage - 1) * 0x80
                write(cs + target, hooks.trampoline(stage, image))
                write(cs + address, jump(address, target))

        saved_gate = None
        stop(install)
        try:
            registers = wait(1, True)
            for bonus, destruction, count in CASES:
                saved_gate = (read(ds + 0x79C5, 2), read(ds + 0x2080, 2))
                if saved_gate[1] != bytes(2):
                    raise RuntimeError("completion probes require a naturally empty collapse queue")
                write(ds + 0x79C5, bytes((bonus, destruction)))
                write(ds + 0x2080, struct.pack("<H", count))
                frame = int.from_bytes(read(ds + 0x78C2, 2), "little")
                release(1)
                accepted = bool(bonus and destruction and count == 0)
                branch = 3 if accepted else 2
                registers = wait(branch)
                if int.from_bytes(read(ds + 0x78C2, 2), "little") != frame:
                    raise RuntimeError("completion gate crossed an update")
                records["cases"].append({"bonus_flag": bonus, "destruction_flag": destruction,
                                         "collapse_count": count, "accepted": accepted,
                                         "frame": frame, "registers": registers, "stage": branch})
                if not accepted:
                    write(ds + 0x79C5, saved_gate[0])
                    write(ds + 0x2080, saved_gate[1])
                    saved_gate = None
                    release(2)
                    registers = wait(1)
            frozen = world(registers)
            records["freeze"].append(frozen)
            saved_gate = None
            release(3)
            for _ in range(8):
                time.sleep(0.25)
                if read(cs + hooks.SCRATCH, 2) != bytes(2):
                    raise RuntimeError("result routine is still stopped at an instrumentation hook")
                snapshot = world(registers)
                records["freeze"].append(snapshot)
                if snapshot != frozen:
                    raise RuntimeError("original gameplay changed inside result subroutine")
            window = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
            subprocess.run(["import", "-window", window, str(output.with_suffix(".png"))], check=True, timeout=10)
            deadline = time.monotonic() + 40
            keypresses = 0
            while time.monotonic() < deadline:
                result = poll()
                if result:
                    stage, registers = result
                    if stage != 4:
                        raise RuntimeError("unexpected return from original result flow")
                    break
                subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], check=True, timeout=5)
                keypresses += 1
                time.sleep(0.5)
            else:
                raise RuntimeError("original result flow did not return")
            records["returned_level"] = read(ds + 0x79B7, 1)[0]
            records["return_registers"] = registers
            records["acknowledgement_attempts"] = keypresses
            if records["returned_level"] != 2:
                raise RuntimeError("original result flow did not increment to level 2")
            records["complete"] = True
            output.write_text(json.dumps(records, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            print(f"original_completion_gate=ok cases={len(CASES)} frozen_samples=9 returned_level=2 seeded=1 natural=0", flush=True)
        except BaseException as error:
            records["complete"] = False
            records["error"] = str(error)
            output.with_suffix(".partial.json").write_text(json.dumps(records, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            raise
        finally:
            def restore() -> None:
                if saved_gate is not None:
                    write(ds + 0x79C5, saved_gate[0])
                    write(ds + 0x2080, saved_gate[1])
                for address, _ in HOOKS:
                    write(cs + address, image[address:address + 3])
                marker = int.from_bytes(read(cs + hooks.SCRATCH, 2), "little")
                if marker:
                    release(marker)
            stop(restore)


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe seeded original completion gates and result-flow freezing")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    image = check_image(ROOT / "LEZAC.EXE")
    if args.self_check:
        print(f"completion_capture_self_check=ok hooks=4 cases={len(CASES)} live=0")
        return 0
    if not (args.run_dir and args.out and args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("temporary run-dir, out and both approval flags are required")
    if args.out.exists() or args.out.with_suffix(".png").exists():
        parser.error("output exists; use a fresh path")
    environment.validate_temp_run_dir(args.run_dir.resolve())
    check_image(args.run_dir / "LEZAC.EXE")
    environment.SCRIPT_PATH = Path(__file__).resolve()
    environment.XVFB_MARKER = "LEZAC_COMPLETION_INSIDE_XVFB"
    environment.enter_private_xvfb(sys.argv[1:])
    original = seeder.write_runtime_state_snapshot

    def observe(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            capture(pid, base, image, args.out)
            state = seeder.read_transition_state(pid, base)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = observe
    sys.argv = ["seed_original_level.py", "--run-dir", str(args.run_dir), "--target-level", "1",
                "--approve-procmem", "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
