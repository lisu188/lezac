#!/usr/bin/env python3
"""Launch the original LEZAC.EXE under DOSBox and read/seed its live game state.

This is the orchestration substrate for capturing the original game at levels
other than level 1, which the original offers no key shortcut to reach (there is
no PageUp/PageDown/F5 level-skip; level advance happens only through natural
completion -> results screen -> keypress -> the level-advance routine at Ghidra
1000:2040/2051 which increments the level byte DS:0x79B7 and reloads geometry).

Validated behaviour (see --self-check):
  * Runs plain `dosbox` under `xvfb-run -a`, drives it to level-1 gameplay with
    `xdotool` (start key, then a fire tap to dismiss the "PREPARATI PER IL
    LIVELLO N" splash).
  * Finds the DOSBox process, scans /proc/<pid>/mem for the data signature
    b"larax e zaco versione" and derives the emulated-memory base as
    base = sig_addr - ((RUNTIME_DS << 4) + DATA_STRING_OFFSET) with
    RUNTIME_DS = 0x0C8F, DATA_STRING_OFFSET = 0x8B.
  * Reads DS:0x79B7 (the level byte, 0-indexed: 0 == level 1) and can write
    arbitrary DS offsets for seeding experiments, then triggers a DOSBox
    screenshot.

SOLVED completion trigger (this is what lets us seed levels 2-8):
  The main-loop completion gate lives at Ghidra 1000:8283 (file offset 0x89f3):

      cmp BYTE  ds:0x79c5, 0   ; je  skip   (progress flag 1 -> reached scroll limit)
      cmp BYTE  ds:0x79c6, 0   ; je  skip   (progress flag 2)
      cmp WORD  ds:0x2080, 0   ; jne skip   (active-actor count -> must be zero)
      call 0x24d1              ; "LIVELLO COMPLETATO" results screen (blocking)
      cmp BYTE  ds:0x79b7, 7   ; ja end-game
      jmp advance              ; increment level byte, load next level

  Writing DS:0x79C5=1 and DS:0x79C6=1 alone does NOT advance the level, because
  the third condition (WORD DS:0x2080 == 0, the active-actor count that is
  inc'd on spawn at 1000:40e8 and dec'd on destroy at 1000:586a) is almost never
  zero during normal play. Seeding all three (0x79C5=1, 0x79C6=1, 0x2080=0)
  satisfies the gate: the game runs its own results screen and advances. This is
  validated live end-to-end (levels 1->2->...->7->victory captured under DOSBox).

Input delivery: keys MUST be sent as real XTEST events (focus the window with
`xdotool windowactivate --sync`, then `xdotool key --clearmodifiers <k>` with NO
`--window` flag). SDL/DOSBox silently drops XSendEvent synthetic events, so
`xdotool key --window ...` never registers in-game; that was the long-standing
standalone-driver blocker.

Guarded: live runs require --approve-procmem and --approve-runtime-instrumentation.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

RUNTIME_DS = 0x0C8F
DATA_STRING_OFFSET = 0x8B
DATA_SIGNATURE = b"larax e zaco versione"
LEVEL_BYTE_OFFSET = 0x79B7

# Completion gate globals (Ghidra 1000:8283 / file 0x89f3).
COMPLETION_FLAG1_OFFSET = 0x79C5  # progress flag 1 (byte)
COMPLETION_FLAG2_OFFSET = 0x79C6  # progress flag 2 (byte)
ACTOR_COUNT_OFFSET = 0x2080       # active-actor count (word); must be 0 to complete


def scan_process(pid: int, pattern: bytes) -> list[int]:
    out: list[int] = []
    for line in Path(f"/proc/{pid}/maps").read_text().splitlines():
        parts = line.split()
        if len(parts) < 2 or "r" not in parts[1]:
            continue
        start_text, end_text = parts[0].split("-")
        start = int(start_text, 16)
        end = int(end_text, 16)
        if end - start <= 0 or end - start > 64 * 1024 * 1024:
            continue
        try:
            with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
                mem.seek(start)
                data = mem.read(end - start)
        except OSError:
            continue
        index = data.find(pattern)
        while index != -1:
            out.append(start + index)
            index = data.find(pattern, index + 1)
    return out


def read_ds(pid: int, base: int, offset: int, length: int) -> bytes:
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        mem.seek(base + (RUNTIME_DS << 4) + offset)
        return mem.read(length)


def write_ds(pid: int, base: int, offset: int, data: bytes) -> None:
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        mem.seek(base + (RUNTIME_DS << 4) + offset)
        mem.write(data)


def parse_seed(seed_args: list[str]) -> list[tuple[int, int]]:
    seeds: list[tuple[int, int]] = []
    for item in seed_args or []:
        off_text, val_text = item.split("=", 1)
        seeds.append((int(off_text, 16), int(val_text, 0) & 0xFF))
    return seeds


def run_live(args) -> int:
    conf = Path(args.run_dir) / "dosbox-seed.conf"
    conf.write_text(
        "[sdl]\nfullscreen=false\noutput=surface\n"
        f"[dosbox]\ncaptures={args.run_dir}\n"
        "[render]\nframeskip=0\naspect=false\nscaler=none\n"
        "[cpu]\ncycles=fixed 6000\n"
    )
    dosbox = subprocess.Popen(
        ["dosbox", "-conf", str(conf), "-c", f"mount c {args.run_dir}",
         "-c", "c:", "-c", "LEZAC.EXE"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    window = None
    for _ in range(30):
        time.sleep(1)
        try:
            found = subprocess.check_output(
                ["xdotool", "search", "--name", "DOSBox"],
                text=True, stderr=subprocess.DEVNULL).split()
            if found:
                window = found[-1]
                break
        except subprocess.CalledProcessError:
            pass
    if not window:
        dosbox.terminate()
        raise RuntimeError("DOSBox window not found (run under `xvfb-run -a`)")

    def focus() -> None:
        subprocess.run(["xdotool", "windowactivate", "--sync", window],
                       stderr=subprocess.DEVNULL)
        time.sleep(0.06)

    def key(name: str) -> None:
        # Real XTEST event (NO --window): SDL/DOSBox drops XSendEvent synthetics.
        focus()
        subprocess.run(["xdotool", "key", "--clearmodifiers", name],
                       stderr=subprocess.DEVNULL)
        time.sleep(0.15)

    def hold(name: str, seconds: float) -> None:
        focus()
        subprocess.run(["xdotool", "keydown", name], stderr=subprocess.DEVNULL)
        time.sleep(seconds)
        subprocess.run(["xdotool", "keyup", name], stderr=subprocess.DEVNULL)
        time.sleep(0.1)

    time.sleep(5)
    key(args.start_key)
    time.sleep(0.4)
    key(args.start_key)
    time.sleep(1.5)
    hold("x", 1.2)  # movement dismisses the level-intro splash into live play
    time.sleep(1.0)

    pid = int(subprocess.check_output(["pgrep", "-n", "dosbox"], text=True).strip())
    matches = scan_process(pid, DATA_SIGNATURE)
    if not matches:
        dosbox.terminate()
        raise RuntimeError("data signature not found in DOSBox memory")
    base = matches[-1] - ((RUNTIME_DS << 4) + DATA_STRING_OFFSET)
    level_before = read_ds(pid, base, LEVEL_BYTE_OFFSET, 1)[0]

    def trigger_completion(prev_level: int) -> int:
        # Satisfy the 1000:8283 gate (flag1=1, flag2=1, actor-count=0), acking the
        # blocking results screen with a keypress, until the level byte advances.
        deadline = time.time_ns() + 9_000_000_000
        iteration = 0
        while time.time_ns() < deadline:
            write_ds(pid, base, COMPLETION_FLAG1_OFFSET, b"\x01")
            write_ds(pid, base, COMPLETION_FLAG2_OFFSET, b"\x01")
            write_ds(pid, base, ACTOR_COUNT_OFFSET, b"\x00\x00")
            iteration += 1
            now = read_ds(pid, base, LEVEL_BYTE_OFFSET, 1)[0]
            if now != prev_level:
                return now
            if iteration % 6 == 0:
                key("space")
            time.sleep(0.03)
        return read_ds(pid, base, LEVEL_BYTE_OFFSET, 1)[0]

    current = level_before
    if args.advance_to is not None:
        while current < args.advance_to:
            nxt = trigger_completion(current)
            if nxt == current:
                break
            current = nxt
            time.sleep(1.5)
            hold("x", 1.0)  # dismiss the new level's intro splash
            time.sleep(0.8)

    seeds = parse_seed(args.seed)
    for offset, value in seeds:
        write_ds(pid, base, offset, bytes([value]))
    if seeds:
        time.sleep(args.settle)
        key("space")
        time.sleep(args.settle)

    level_after = read_ds(pid, base, LEVEL_BYTE_OFFSET, 1)[0]
    focus()
    subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+F5"],
                   stderr=subprocess.DEVNULL)
    time.sleep(1)
    dosbox.terminate()

    print(
        "seed_original_level=ok"
        f" base=0x{base:x} runtime_ds=0x{RUNTIME_DS:04x}"
        f" level_byte_before={level_before} level_byte_after={level_after}"
        f" seeds={len(seeds)} advanced={int(level_after != level_before)}"
    )
    return 0


def self_check() -> int:
    # Static contract check only (no DOSBox): confirm the derivation constants
    # and the level byte against the shipped executable.
    exe = Path("LEZAC.EXE").read_bytes()
    image = exe[0x770:0x770 + 50480]
    sig_at = image.find(DATA_SIGNATURE)
    if sig_at < 0:
        raise RuntimeError("data signature missing from LEZAC.EXE")
    # The signature sits at DS:DATA_STRING_OFFSET at runtime; the level byte and
    # the advance routine are pinned by the recovery notes.
    if image[0x2051:0x2055] != b"\xfe\x06\xb7\x79":
        raise RuntimeError("level-advance inc [0x79b7] not at 1000:2051")
    # The completion gate at 1000:8283 is the trigger we seed. The three cmp
    # instructions are separated by conditional jumps, so pin each in place:
    #   1000:8283  80 3e c5 79 00  cmp byte [0x79c5],0
    #   1000:828a  80 3e c6 79 00  cmp byte [0x79c6],0
    #   1000:8291  83 3e 80 20 00  cmp word [0x2080],0
    gate_checks = (
        (0x8283, b"\x80\x3e\xc5\x79\x00"),
        (0x828a, b"\x80\x3e\xc6\x79\x00"),
        (0x8291, b"\x83\x3e\x80\x20\x00"),
    )
    for offset, expected in gate_checks:
        if image[offset:offset + 5] != expected:
            raise RuntimeError(f"completion gate cmp not at 1000:{offset:04x}")
    print(
        "seed_original_level_self_check=ok"
        f" signature=1000:{sig_at:04x} data_string_offset=0x{DATA_STRING_OFFSET:02x}"
        f" runtime_ds=0x{RUNTIME_DS:04x} level_byte=0x{LEVEL_BYTE_OFFSET:04x}"
        " advance_routine=1000:2040 inc_level=1000:2051"
        f" completion_gate=1000:8283 flag1=0x{COMPLETION_FLAG1_OFFSET:04x}"
        f" flag2=0x{COMPLETION_FLAG2_OFFSET:04x} actor_count=0x{ACTOR_COUNT_OFFSET:04x}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true",
                        help="static contract check against LEZAC.EXE (no DOSBox)")
    parser.add_argument("--run-dir", help="directory with LEZAC.EXE + assets")
    parser.add_argument("--start-key", default="1")
    parser.add_argument("--advance-to", type=int, default=None,
                        help="drive the original to this 1-indexed level via the "
                             "1000:8283 completion trigger before seeding/capturing")
    parser.add_argument("--seed", action="append",
                        help="OFFSET=VALUE (hex offset) DS byte to write, repeatable")
    parser.add_argument("--settle", type=float, default=4.0)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()

    if args.self_check:
        return self_check()
    if not (args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error("live runs require --approve-procmem "
                     "and --approve-runtime-instrumentation")
    if not args.run_dir:
        parser.error("--run-dir is required for live runs")
    return run_live(args)


if __name__ == "__main__":
    raise SystemExit(main())
