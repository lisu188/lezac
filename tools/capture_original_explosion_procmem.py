#!/usr/bin/env python3
"""Capture original LEZAC explosion bytes from a temporary DOSBox process.

This helper is intentionally guarded because it reads /proc/<pid>/mem from the
DOSBox child process it starts. Keep output directories outside the repository.
Candidate fixtures still need frame inspection before promotion.
"""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


ASSETS = [
    "LEZAC.EXE",
    "BOMPAL.PAL",
    "CARO.CAR",
    "FONTS.SPR",
    "GRAN.MST",
    "LIVELS.SCH",
    "PROEFS.SON",
    "PROVA.SPR",
    "RECS.DAT",
    "SFONLEF.ZBG",
    "BOMOMIMK.SPR",
    "ENGLISH.DOC",
    "ITALIANO.DOC",
]

ENTRY_SIGNATURE = bytes.fromhex(
    "9a00000d0b9a2d07990a9a0000370a9a11011a0a5589e5"
)
DATA_SIGNATURE = b"larax e zaco versione"
RUNTIME_CS = 0x01ED
RUNTIME_DS = 0x0C8F
ENTRY_IP = 0x7783
DATA_STRING_OFFSET = 0x008B


def run(args: list[str], env: dict[str, str], check: bool = True) -> str:
    completed = subprocess.run(
        args,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"{completed.stdout}"
        )
    return completed.stdout


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"missing required command: {name}")


def copy_assets(asset_dir: Path, run_dir: Path) -> None:
    for name in ASSETS:
        src = asset_dir / name
        if src.exists():
            shutil.copy2(src, run_dir / name)
    if not (run_dir / "LEZAC.EXE").exists():
        raise RuntimeError(f"missing {asset_dir / 'LEZAC.EXE'}")


def write_conf(path: Path, capture_dir: Path) -> None:
    path.write_text(
        "[sdl]\n"
        "fullscreen=false\n"
        "fulldouble=false\n"
        "output=surface\n\n"
        "[dosbox]\n"
        f"captures={capture_dir}\n\n"
        "[render]\n"
        "frameskip=0\n"
        "aspect=false\n"
        "scaler=none\n\n"
        "[cpu]\n"
        "cycles=fixed 6000\n",
        encoding="ascii",
    )


def scan_process(pid: int, pattern: bytes) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    maps = Path(f"/proc/{pid}/maps").read_text(encoding="utf-8").splitlines()
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        for line in maps:
            parts = line.split()
            if len(parts) < 2 or "r" not in parts[1]:
                continue
            start_text, end_text = parts[0].split("-")
            start = int(start_text, 16)
            end = int(end_text, 16)
            size = end - start
            if size <= 0 or size > 64 * 1024 * 1024:
                continue
            try:
                mem.seek(start)
                data = mem.read(size)
            except OSError:
                continue
            index = data.find(pattern)
            while index >= 0:
                found.append((start + index, line))
                index = data.find(pattern, index + 1)
    return found


def find_debug_pid(run_dir: Path) -> int:
    output = subprocess.check_output(["pgrep", "-a", "dosbox-debug"], text=True)
    candidates = [
        int(line.split()[0])
        for line in output.splitlines()
        if str(run_dir) in line
    ]
    if not candidates:
        raise RuntimeError("could not find dosbox-debug child for run directory")
    return candidates[-1]


def format_dump(segment: int, offset: int, data: bytes) -> str:
    lines = []
    for index in range(0, len(data), 16):
        chunk = data[index : index + 16]
        bytes_text = " ".join(f"{value:02x}" for value in chunk)
        lines.append(f"{segment:04X}:{offset + index:04X}  {bytes_text}")
    return "\n".join(lines)


def activate_window(env: dict[str, str], window: str) -> None:
    run(["xdotool", "windowactivate", "--sync", window], env, check=False)
    time.sleep(0.12)


def key(env: dict[str, str], window: str, name: str) -> None:
    activate_window(env, window)
    run(["xdotool", "key", "--clearmodifiers", name], env, check=False)
    time.sleep(0.2)


def hold_key(env: dict[str, str], window: str, name: str, seconds: float) -> None:
    activate_window(env, window)
    run(["xdotool", "keydown", name], env, check=False)
    time.sleep(seconds)
    run(["xdotool", "keyup", name], env, check=False)
    time.sleep(0.15)


def held_tap(env: dict[str, str], window: str, name: str, seconds: float) -> None:
    activate_window(env, window)
    run(["xdotool", "keydown", name], env, check=False)
    time.sleep(seconds)
    run(["xdotool", "keyup", name], env, check=False)
    time.sleep(0.2)


def snapshot(env: dict[str, str], out_dir: Path, window: str, label: str) -> None:
    before = set(glob.glob(str(out_dir / "*.png")))
    activate_window(env, window)
    run(["xdotool", "key", "--clearmodifiers", "ctrl+F5"], env, check=False)
    time.sleep(0.3)
    new_files = sorted(set(glob.glob(str(out_dir / "*.png"))) - before)
    if new_files:
        Path(new_files[-1]).rename(out_dir / f"{label}.png")


def read_emulated(pid: int, base: int, segment: int, offset: int, length: int) -> bytes:
    host = base + ((segment << 4) + offset)
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        mem.seek(host)
        return mem.read(length)


def choose_sample(records: list[tuple[float, bytes, bytes, bytes, bytes, bytes]]):
    for record in records:
        _, _, debris, _, lookup, effect = record
        del lookup
        if any(debris[3:14]) or any(effect[:16]):
            return record
    return max(records, key=lambda item: sum(1 for value in item[3] if value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("asset_dir", nargs="?", default=".")
    parser.add_argument(
        "--approve-procmem",
        action="store_true",
        help="required: approve reading /proc/<pid>/mem from the child DOSBox process",
    )
    parser.add_argument("--mode", choices=["debug", "regular"], default="debug")
    parser.add_argument("--start-key", default="1")
    parser.add_argument("--start-taps", type=int, default=2)
    parser.add_argument("--level-start-seconds", type=float, default=3.0)
    parser.add_argument("--right-key", default="x")
    parser.add_argument(
        "--x-hold-seconds",
        "--right-hold-seconds",
        dest="right_hold_seconds",
        type=float,
        default=2.0,
    )
    parser.add_argument("--sample-seconds", type=float, default=8.0)
    parser.add_argument("--sample-interval", type=float, default=0.08)
    parser.add_argument("--bomb-key", default="n")
    parser.add_argument("--bomb-hold-seconds", type=float, default=0.25)
    args = parser.parse_args()

    if not args.approve_procmem:
        print("refusing to read /proc/<pid>/mem without --approve-procmem", file=sys.stderr)
        return 64

    for tool in ["Xvfb", "xdotool", "dosbox", "python3"]:
        require_tool(tool)
    if args.mode == "debug":
        for tool in ["dosbox-debug", "zutty", "script", "pgrep"]:
            require_tool(tool)

    out_dir = Path(args.out_dir).resolve()
    asset_dir = Path(args.asset_dir).resolve()
    repo_dir = Path.cwd().resolve()
    if repo_dir in out_dir.parents or out_dir == repo_dir:
        raise RuntimeError("choose an output directory outside the repository")
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = out_dir / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    copy_assets(asset_dir, run_dir)
    conf = run_dir / "dosbox.conf"
    write_conf(conf, out_dir)

    display = ":137"
    xvfb = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1024x768x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    env = os.environ.copy()
    env.update({"DISPLAY": display, "TERM": "xterm-256color", "SDL_AUDIODRIVER": "dummy"})
    proc: subprocess.Popen[str] | None = None
    zutty: subprocess.Popen[str] | None = None

    try:
        time.sleep(0.5)
        if args.mode == "debug":
            command = (
                f'env TERM=xterm-256color SDL_AUDIODRIVER=dummy dosbox-debug '
                f'-conf "{conf}" -c "mount c {run_dir}" -c "c:" '
                f'-c "DEBUG LEZAC.EXE"'
            )
            zutty = subprocess.Popen(
                [
                    "zutty",
                    "-title",
                    "LEZACPROCMEMCAP",
                    "-geometry",
                    "100x50",
                    "-e",
                    "script",
                    "-q",
                    "-f",
                    str(out_dir / "dosbox_debug_terminal.log"),
                    "-c",
                    command,
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            time.sleep(5.0)
            pid = find_debug_pid(run_dir)
            entries = scan_process(pid, ENTRY_SIGNATURE)
            if len(entries) != 1:
                raise RuntimeError(f"expected one entry signature, found {len(entries)}")
            base = entries[0][0] - ((RUNTIME_CS << 4) + ENTRY_IP)
            terminal = run(["xdotool", "search", "--name", "LEZACPROCMEMCAP"], env).split()[0]
            activate_window(env, terminal)
            run(["xdotool", "key", "--window", terminal, "F5"], env, check=False)
            time.sleep(6.0)
        else:
            command = (
                f'dosbox -conf "{conf}" -c "mount c {run_dir}" -c "c:" '
                f'-c "LEZAC.EXE"'
            )
            proc = subprocess.Popen(
                ["dosbox", "-conf", str(conf), "-c", f"mount c {run_dir}", "-c", "c:", "-c", "LEZAC.EXE"],
                cwd=run_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            time.sleep(6.0)
            pid = proc.pid
            data_matches = scan_process(pid, DATA_SIGNATURE)
            if not data_matches:
                raise RuntimeError("runtime data signature not found")
            base = data_matches[-1][0] - ((RUNTIME_DS << 4) + DATA_STRING_OFFSET)

        data_matches = scan_process(pid, DATA_SIGNATURE)
        if data_matches:
            inferred_ds = ((data_matches[-1][0] - base) - DATA_STRING_OFFSET) // 16
        else:
            inferred_ds = RUNTIME_DS
        if inferred_ds != RUNTIME_DS:
            raise RuntimeError(f"unexpected runtime DS 0x{inferred_ds:04x}")

        game = run(["xdotool", "search", "--name", "DOSBox"], env).split()[0]
        snapshot(env, out_dir, game, "000_menu")
        for _ in range(max(args.start_taps, 1)):
            key(env, game, args.start_key)
            time.sleep(0.4)
        time.sleep(args.level_start_seconds)
        snapshot(env, out_dir, game, "010_level_start")
        hold_key(env, game, args.right_key, args.right_hold_seconds)
        snapshot(env, out_dir, game, "020_route_position")
        held_tap(env, game, args.bomb_key, args.bomb_hold_seconds)
        time.sleep(0.3)
        snapshot(env, out_dir, game, "030_bomb_key")

        records = []
        started = time.time()
        while time.time() - started < args.sample_seconds:
            elapsed = time.time() - started
            records.append(
                (
                    elapsed,
                    read_emulated(pid, base, RUNTIME_DS, 0x2070, 0x60),
                    read_emulated(pid, base, RUNTIME_DS, 0x2090, 0x30),
                    read_emulated(pid, base, RUNTIME_DS, 0x6610, 0x30),
                    read_emulated(pid, base, RUNTIME_DS, 0xC1E0, 0x20),
                    read_emulated(pid, base, RUNTIME_DS, 0xC21E, 0x40),
                )
            )
            time.sleep(args.sample_interval)
        snapshot(env, out_dir, game, "090_after_sampling")

        chosen = choose_sample(records)
        elapsed, dump2070, dump2090, dump6610, dumpc1e0, dumpc21e = chosen
        fixture = out_dir / "explosion_playback_oracle_original_candidate.txt"
        with fixture.open("w", encoding="ascii") as out:
            out.write("# LEZAC original explosion playback oracle candidate.\n")
            out.write("# Candidate only: inspect frames before promoting to tests/fixtures.\n")
            out.write(f"# chosen_sample_seconds_after_bomb={elapsed:.2f}\n")
            out.write("capture=explosion_playback\n")
            out.write(f"source=dosbox-{args.mode}-process-memory\n")
            out.write("temp_copy=1\nvisual_claim=0\n")
            out.write(f"command={command}\n")
            out.write("route=focused_no_window_original_controls_process_memory\n")
            out.write(f"input_start_key={args.start_key}\n")
            out.write(f"input_start_taps={max(args.start_taps, 1)}\n")
            out.write(f"input_right_key={args.right_key}\n")
            out.write(f"input_right_hold_seconds={args.right_hold_seconds:.2f}\n")
            out.write(f"input_bomb_key={args.bomb_key}\n")
            out.write(f"input_bomb_hold_seconds={args.bomb_hold_seconds:.2f}\n")
            out.write(f"runtime_cs={RUNTIME_CS:04X}\n")
            out.write(f"runtime_ds={RUNTIME_DS:04X}\n")
            for ghidra, offset, label in [
                ("1000:75F1", 0x75F1, "bomb_expire_dispatch_call"),
                ("1000:414A", 0x414A, "explosion_dispatcher"),
                ("1000:370E", 0x370E, "tile_damage_queue"),
                ("1000:3A7E", 0x3A7E, "damage_forward_lookup"),
                ("1000:3B18", 0x3B18, "damage_reverse_lookup"),
                ("1000:3BB2", 0x3BB2, "collapse_forward_pass"),
                ("1000:3D46", 0x3D46, "collapse_reverse_pass"),
            ]:
                out.write(
                    f"break ghidra={ghidra} runtime={RUNTIME_CS:04X}:{offset:04X} "
                    f"label={label} observed=process_memory_sampling_no_debugger_break\n"
                )
            for label, offset, data in [
                ("DS:2070", 0x2070, dump2070),
                ("DS:2090", 0x2090, dump2090),
                ("DS:6610", 0x6610, dump6610),
                ("DS:C1E0", 0xC1E0, dumpc1e0),
                ("DS:C21E", 0xC21E, dumpc21e),
            ]:
                out.write(f"\ndump {label}\n")
                out.write(format_dump(RUNTIME_DS, offset, data) + "\n")

        manifest = out_dir / "manifest.txt"
        manifest.write_text(
            f"capture=original_explosion_process_memory\n"
            f"mode={args.mode}\n"
            f"method=approved_process_memory_scan_limited_to_child_dosbox_process\n"
            f"run_dir={run_dir}\n"
            f"fixture_candidate={fixture}\n"
            f"runtime_cs={RUNTIME_CS:04X}\n"
            f"runtime_ds={RUNTIME_DS:04X}\n"
            f"input_start_key={args.start_key}\n"
            f"input_start_taps={max(args.start_taps, 1)}\n"
            f"input_level_start_seconds={args.level_start_seconds:.2f}\n"
            f"input_right_key={args.right_key}\n"
            f"input_right_hold_seconds={args.right_hold_seconds:.2f}\n"
            f"input_bomb_key={args.bomb_key}\n"
            f"input_bomb_hold_seconds={args.bomb_hold_seconds:.2f}\n"
            f"visual_claim=0\n",
            encoding="ascii",
        )
        print(f"candidate={fixture}")
        return 0
    finally:
        if zutty is not None:
            zutty.terminate()
            try:
                zutty.wait(timeout=3)
            except subprocess.TimeoutExpired:
                zutty.kill()
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        xvfb.terminate()
        try:
            xvfb.wait(timeout=3)
        except subprocess.TimeoutExpired:
            xvfb.kill()


if __name__ == "__main__":
    raise SystemExit(main())
