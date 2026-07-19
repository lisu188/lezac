#!/usr/bin/env python3
"""Launch the original LEZAC.EXE under DOSBox and read/seed its live game state.

This is the orchestration substrate for capturing the original game at levels
other than level 1, which the original offers no key shortcut to reach (there is
no PageUp/PageDown/F5 level-skip; level advance happens only through natural
completion -> results screen -> keypress -> the result routine at Ghidra
1000:1D61, which reaches the level increment at 1000:2051 and reloads geometry).

Validated behaviour (see --self-check):
  * Runs plain `dosbox` under `xvfb-run -a`, drives it to level-1 gameplay with
    `xdotool` (two menu-start taps, then a delayed neutral key for the blocking
    read after the "PREPARATI PER IL LIVELLO N" caption).
  * Finds the DOSBox process, scans /proc/<pid>/mem for the data signature
    b"larax e zaco versione" and derives the emulated-memory base as
    base = sig_addr - ((RUNTIME_DS << 4) + DATA_STRING_OFFSET) with
    RUNTIME_DS = 0x0C8F, DATA_STRING_OFFSET = 0x8B.
  * Reads DS:0x79B7 (the 1-based playable level byte, 1..7), plus the original
    destruction/bonus objective counters, targets, completion flags, and
    collapse-queue count.
  * With `--target-level N`, seeds the current objective counters to the
    level-file targets, lets `1000:3184` derive both completion flags, waits for
    the `1000:8283` empty-collapse-queue gate, advances through the native
    results routine at `1000:1D61`, dismisses the next intro, and captures the
    requested level's live gameplay frame. Value 8 is the completed-game
    sentinel and is not a playable level.
  * Retains repeatable byte-level `--seed OFFSET=VALUE` writes for focused
    experiments.

Input delivery uses real XTEST events: focus the DOSBox window, then call
`xdotool key --clearmodifiers <key>` without `--window`. SDL/DOSBox drops the
XSendEvent path produced by `xdotool key --window ...`.

Guarded: live runs require --approve-procmem and --approve-runtime-instrumentation.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

RUNTIME_DS = 0x0C8F
DATA_STRING_OFFSET = 0x8B
DATA_SIGNATURE = b"larax e zaco versione"
LEVEL_BYTE_OFFSET = 0x79B7
BONUS_TARGET_OFFSET = 0x2086
BONUS_CURRENT_OFFSET = 0x2088
BONUS_PREVIOUS_OFFSET = 0x208A
COLLAPSE_QUEUE_COUNT_OFFSET = 0x2080
DESTRUCTION_TARGET_OFFSET = 0x79B3
DESTRUCTION_CURRENT_OFFSET = 0x79B5
DESTRUCTION_PREVIOUS_OFFSET = 0x79B6
BONUS_COMPLETE_OFFSET = 0x79C5
DESTRUCTION_COMPLETE_OFFSET = 0x79C6
ACTOR_TABLE_OFFSET = 0x1BAE
ACTOR_COUNT_OFFSET = 0x208D
ACTOR_RECORD_STRIDE = 0x26
VISUAL_TABLE_OFFSET = 0xC21E
VISUAL_RECORD_STRIDE = 8
MOTION_LINK_TABLE_OFFSET = 0x79EA
MOTION_LINK_COUNT_OFFSET = 0x79F9
MOTION_LINK_RECORD_STRIDE = 0x10
VISUAL_COUNT_OFFSET = 0xC496
GLOBAL_TICK_OFFSET = 0x78C2
RANDOM_SEED_OFFSET = 0x1AFE
CAMERA_X_OFFSET = 0xC216
CAMERA_Y_OFFSET = 0xC218
CAMERA_SUB_X_OFFSET = 0xC20A
CAMERA_SUB_Y_OFFSET = 0xC20C
CAMERA_MAP_OFFSET = 0xC1F0
CAMERA_MAX_X_OFFSET = 0x2094
CAMERA_MAX_Y_OFFSET = 0x2096
VIEW_WIDTH_OFFSET = 0xC1EC
VIEW_HEIGHT_OFFSET = 0xC1EE
VIEW_ROW_DELTA_OFFSET = 0xC206
CAMERA_CENTER_X_OFFSET = 0x78BC
CAMERA_CENTER_TILE_OFFSET = 0x78BE
ACTIVE_VIEW_WIDTH_OFFSET = 0x79EE
VIEW_PRESENT_DEST_OFFSET = 0xC1F4
VIEW_BUFFER_SOURCE_OFFSET = 0xC214
VIEW_PAGE_DEST_OFFSET = 0x79F0
MIN_PLAYABLE_LEVEL = 1
MAX_PLAYABLE_LEVEL = 7


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


def write_u8(pid: int, base: int, offset: int, value: int) -> None:
    write_ds(pid, base, offset, bytes([value & 0xFF]))


def write_u16(pid: int, base: int, offset: int, value: int) -> None:
    write_ds(pid, base, offset, int(value & 0xFFFF).to_bytes(2, "little"))


def read_u8(pid: int, base: int, offset: int) -> int:
    return read_ds(pid, base, offset, 1)[0]


def read_u16(pid: int, base: int, offset: int) -> int:
    return int.from_bytes(read_ds(pid, base, offset, 2), "little")


def read_u32(pid: int, base: int, offset: int) -> int:
    return int.from_bytes(read_ds(pid, base, offset, 4), "little")


def read_i16(pid: int, base: int, offset: int) -> int:
    return int.from_bytes(
        read_ds(pid, base, offset, 2), "little", signed=True)


def read_transition_state(pid: int, base: int) -> dict[str, int]:
    return {
        "level": read_u8(pid, base, LEVEL_BYTE_OFFSET),
        "bonus_current": read_u16(pid, base, BONUS_CURRENT_OFFSET),
        "bonus_target": read_u16(pid, base, BONUS_TARGET_OFFSET),
        "bonus_previous": read_u16(pid, base, BONUS_PREVIOUS_OFFSET),
        "destruction_current": read_u8(
            pid, base, DESTRUCTION_CURRENT_OFFSET),
        "destruction_target": read_u8(
            pid, base, DESTRUCTION_TARGET_OFFSET),
        "destruction_previous": read_u8(
            pid, base, DESTRUCTION_PREVIOUS_OFFSET),
        "bonus_complete": read_u8(pid, base, BONUS_COMPLETE_OFFSET),
        "destruction_complete": read_u8(
            pid, base, DESTRUCTION_COMPLETE_OFFSET),
        "collapse_queue": read_u16(
            pid, base, COLLAPSE_QUEUE_COUNT_OFFSET),
    }


def format_transition_state(prefix: str, state: dict[str, int]) -> str:
    return " ".join(
        [f"{prefix}_level={state['level']}"]
        + [f"{prefix}_{name}={value}" for name, value in state.items()
           if name != "level"]
    )


def write_runtime_state_snapshot(
        run_dir: Path,
        pid: int,
        base: int,
        state: dict[str, int],
        phase: str) -> Path:
    actor_count = read_u8(pid, base, ACTOR_COUNT_OFFSET)
    motion_link_count = read_u8(pid, base, MOTION_LINK_COUNT_OFFSET)
    if actor_count > 64:
        raise RuntimeError(f"implausible original actor count {actor_count}")
    if motion_link_count > 64:
        raise RuntimeError(
            f"implausible original motion-link count {motion_link_count}")

    # Both original tables are 1-based: slot 0 is reserved, while the count
    # globals name the highest live slot.
    actor_slot_count = actor_count + 1
    actor_bytes = read_ds(
        pid, base, ACTOR_TABLE_OFFSET,
        actor_slot_count * ACTOR_RECORD_STRIDE)
    actors = [
        actor_bytes[index:index + ACTOR_RECORD_STRIDE]
        for index in range(0, len(actor_bytes), ACTOR_RECORD_STRIDE)
    ]
    visual_count = read_u8(pid, base, VISUAL_COUNT_OFFSET)
    if visual_count > 64:
        raise RuntimeError(f"implausible original visual count {visual_count}")
    visual_bytes = read_ds(
        pid, base, VISUAL_TABLE_OFFSET, visual_count * VISUAL_RECORD_STRIDE)
    motion_link_bytes = read_ds(
        pid, base, MOTION_LINK_TABLE_OFFSET,
        (motion_link_count + 1) * MOTION_LINK_RECORD_STRIDE)

    lines = [
        "original_level_runtime_state_v1",
        format_transition_state("state", state),
        f"actor_table=ds:{ACTOR_TABLE_OFFSET:04x}",
        f"actor_count={actor_count}",
        "actor_index_base=1",
        f"actor_stride=0x{ACTOR_RECORD_STRIDE:02x}",
        f"visual_table=ds:{VISUAL_TABLE_OFFSET:04x}",
        f"visual_allocator_count={read_u8(pid, base, VISUAL_COUNT_OFFSET)}",
        f"visual_count={visual_count}",
        f"visual_stride=0x{VISUAL_RECORD_STRIDE:02x}",
        f"motion_link_table=ds:{MOTION_LINK_TABLE_OFFSET:04x}",
        f"motion_link_count={motion_link_count}",
        "motion_link_index_base=1",
        f"motion_link_stride=0x{MOTION_LINK_RECORD_STRIDE:02x}",
        "camera"
        f" x={read_i16(pid, base, CAMERA_X_OFFSET)}"
        f" y={read_i16(pid, base, CAMERA_Y_OFFSET)}"
        f" sub_x={read_i16(pid, base, CAMERA_SUB_X_OFFSET)}"
        f" sub_y={read_i16(pid, base, CAMERA_SUB_Y_OFFSET)}"
        f" map_offset={read_u16(pid, base, CAMERA_MAP_OFFSET)}"
        f" max_x={read_i16(pid, base, CAMERA_MAX_X_OFFSET)}"
        f" max_y={read_i16(pid, base, CAMERA_MAX_Y_OFFSET)}"
        f" center_x={read_i16(pid, base, CAMERA_CENTER_X_OFFSET)}"
        f" center_tile={read_i16(pid, base, CAMERA_CENTER_TILE_OFFSET)}",
        "view"
        f" width={read_u16(pid, base, VIEW_WIDTH_OFFSET)}"
        f" height={read_u16(pid, base, VIEW_HEIGHT_OFFSET)}"
        f" row_delta={read_i16(pid, base, VIEW_ROW_DELTA_OFFSET)}"
        f" active_width={read_u16(pid, base, ACTIVE_VIEW_WIDTH_OFFSET)}"
        f" present_dest={read_u16(pid, base, VIEW_PRESENT_DEST_OFFSET)}"
        f" buffer_source={read_u16(pid, base, VIEW_BUFFER_SOURCE_OFFSET)}"
        f" page_dest={read_u16(pid, base, VIEW_PAGE_DEST_OFFSET)}",
    ]
    for index, actor in enumerate(actors):
        lines.append(
            f"actor[{index}]"
            f" kind=0x{actor[0]:02x}"
            f" visual={actor[1]}"
            f" lives={actor[2]}"
            f" anim_a={actor[3]}"
            f" anim_b={actor[4]}"
            f" behavior={actor[0x15]}"
            f" timer={actor[0x1a]}"
            f" head_link={actor[0x25]}"
            f" raw={actor.hex()}"
        )
    for index in range(visual_count):
        start = index * VISUAL_RECORD_STRIDE
        visual = visual_bytes[start:start + VISUAL_RECORD_STRIDE]
        x = int.from_bytes(visual[0:2], "little", signed=True)
        y = int.from_bytes(visual[2:4], "little", signed=True)
        lines.append(
            f"visual[{index}]"
            f" x={x} y={y}"
            f" sprite={visual[4]}"
            f" detail={visual[5]}"
            f" timer={visual[6]}"
            f" variant={visual[7]}"
            f" raw={visual.hex()}"
        )
    for index in range(motion_link_count + 1):
        start = index * MOTION_LINK_RECORD_STRIDE
        link = motion_link_bytes[start:start + MOTION_LINK_RECORD_STRIDE]
        lines.append(
            f"motion_link[{index}]"
            f" target_visual={link[0]}"
            f" self_visual={link[1]}"
            f" gain={link[2]}"
            f" mode={link[3]}"
            f" raw={link.hex()}"
        )

    target = run_dir / (
        f"original_level_{state['level']}_runtime_state_{phase}.txt")
    target.write_text("\n".join(lines) + "\n")
    return target


def read_boss_trace_sample(pid: int, base: int) -> dict[str, int | bytes]:
    for _ in range(100):
        tick_before = read_u16(pid, base, GLOBAL_TICK_OFFSET)
        level = read_u8(pid, base, LEVEL_BYTE_OFFSET)
        actor_count = read_u8(pid, base, ACTOR_COUNT_OFFSET)
        visual_count = read_u8(pid, base, VISUAL_COUNT_OFFSET)
        motion_link_count = read_u8(pid, base, MOTION_LINK_COUNT_OFFSET)
        if actor_count > 64 or visual_count > 64 or motion_link_count > 64:
            raise RuntimeError(
                "implausible original boss trace table count:"
                f" actors={actor_count} visuals={visual_count}"
                f" links={motion_link_count}")
        random_seed = read_u32(pid, base, RANDOM_SEED_OFFSET)
        actor_bytes = read_ds(
            pid, base, ACTOR_TABLE_OFFSET,
            (actor_count + 1) * ACTOR_RECORD_STRIDE)
        visual_bytes = read_ds(
            pid, base, VISUAL_TABLE_OFFSET,
            visual_count * VISUAL_RECORD_STRIDE)
        motion_link_bytes = read_ds(
            pid, base, MOTION_LINK_TABLE_OFFSET,
            (motion_link_count + 1) * MOTION_LINK_RECORD_STRIDE)
        tick_after = read_u16(pid, base, GLOBAL_TICK_OFFSET)
        if tick_before == tick_after:
            return {
                "tick": tick_before,
                "level": level,
                "random_seed": random_seed,
                "actor_count": actor_count,
                "visual_count": visual_count,
                "motion_link_count": motion_link_count,
                "actor_bytes": actor_bytes,
                "visual_bytes": visual_bytes,
                "motion_link_bytes": motion_link_bytes,
            }
    raise RuntimeError("boss trace state changed during 100 atomic-read retries")


def write_boss_runtime_trace(
        run_dir: Path,
        pid: int,
        base: int,
        sample_count: int,
        timeout: float,
        settle_seconds: float) -> Path:
    def validate_layout(sample: dict[str, int | bytes], phase: str) -> None:
        if (sample["level"] != MAX_PLAYABLE_LEVEL
                or sample["actor_count"] != 7
                or sample["visual_count"] != 9
                or sample["motion_link_count"] != 6):
            raise RuntimeError(
                f"boss trace {phase} outside the recovered level-7 layout:"
                f" level={sample['level']} actors={sample['actor_count']}"
                f" visuals={sample['visual_count']}"
                f" links={sample['motion_link_count']}")

    if (not hasattr(signal, "SIGSTOP")
            or not hasattr(signal, "SIGCONT")
            or not hasattr(os, "WUNTRACED")):
        raise RuntimeError(
            "boss tracing requires POSIX SIGSTOP/SIGCONT and waitpid")

    # DS:78C2 is interrupt-driven while the actor loop can straddle its edge.
    # Sample at a fixed delay after each transition and stop the DOSBox process
    # around the table reads so actor, visual, link, and RNG state is coherent.
    previous_tick = read_u16(pid, base, GLOBAL_TICK_OFFSET)
    samples: list[dict[str, int | bytes]] = []
    deadline = time.monotonic() + timeout
    while len(samples) < sample_count:
        if time.monotonic() >= deadline:
            raise RuntimeError(
                "timeout collecting original boss trace:"
                f" samples={len(samples)}/{sample_count}"
                f" previous_tick=0x{previous_tick:04x}")
        current_tick = read_u16(pid, base, GLOBAL_TICK_OFFSET)
        if current_tick == previous_tick:
            time.sleep(0.0005)
            continue
        tick_step = (current_tick - previous_tick) & 0xFFFF
        if tick_step != 1:
            raise RuntimeError(
                "original boss trace skipped a global tick:"
                f" previous=0x{previous_tick:04x}"
                f" current=0x{current_tick:04x}"
                f" step={tick_step}")
        time.sleep(settle_seconds)
        settled_tick = read_u16(pid, base, GLOBAL_TICK_OFFSET)
        if settled_tick != current_tick:
            raise RuntimeError(
                "original boss trace settle crossed a global tick:"
                f" expected=0x{current_tick:04x}"
                f" actual=0x{settled_tick:04x}"
                f" settle_seconds={settle_seconds}")
        os.kill(pid, signal.SIGSTOP)
        try:
            stopped_pid, stopped_status = os.waitpid(pid, os.WUNTRACED)
            if stopped_pid != pid or not os.WIFSTOPPED(stopped_status):
                raise RuntimeError(
                    "DOSBox did not enter a stopped state for boss tracing")
            sample = read_boss_trace_sample(pid, base)
        finally:
            try:
                os.kill(pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
        if int(sample["tick"]) != current_tick:
            raise RuntimeError(
                "frozen original boss sample tick changed:"
                f" expected=0x{current_tick:04x}"
                f" actual=0x{int(sample['tick']):04x}")
        validate_layout(sample, f"sample {len(samples)}")
        samples.append(sample)
        previous_tick = current_tick

    start_tick = int(samples[0]["tick"])
    lines = [
        "original_boss_runtime_trace_v1",
        "source=LEZAC.EXE via DOSBox /proc/mem tick-phase frozen reads",
        f"runtime_ds=0x{RUNTIME_DS:04x}",
        f"level={MAX_PLAYABLE_LEVEL}",
        f"sample_count={len(samples)}",
        f"tick_offset=0x{GLOBAL_TICK_OFFSET:04x}",
        f"random_seed_offset=0x{RANDOM_SEED_OFFSET:04x}",
        f"actor_table_offset=0x{ACTOR_TABLE_OFFSET:04x}",
        f"actor_entry_size={ACTOR_RECORD_STRIDE}",
        f"actor_index_base=1",
        f"visual_table_offset=0x{VISUAL_TABLE_OFFSET:04x}",
        f"visual_entry_size={VISUAL_RECORD_STRIDE}",
        f"motion_link_table_offset=0x{MOTION_LINK_TABLE_OFFSET:04x}",
        f"motion_link_entry_size={MOTION_LINK_RECORD_STRIDE}",
        f"motion_link_index_base=1",
        f"tick_start=0x{start_tick:04x}",
        f"tick_end=0x{int(samples[-1]['tick']):04x}",
        f"settle_seconds={settle_seconds:.6f}",
        "snapshot_guard=SIGSTOP/SIGCONT",
        "max_tick_step=1",
    ]
    for index, sample in enumerate(samples):
        tick = int(sample["tick"])
        lines.append(
            f"sample[{index}]"
            f" tick=0x{tick:04x}"
            f" tick_delta={(tick - start_tick) & 0xFFFF}"
            f" random_seed=0x{int(sample['random_seed']):08x}"
            f" actor_count={sample['actor_count']}"
            f" visual_count={sample['visual_count']}"
            f" motion_link_count={sample['motion_link_count']}"
            f" actor_table_hex={bytes(sample['actor_bytes']).hex()}"
            f" visual_table_hex={bytes(sample['visual_bytes']).hex()}"
            f" motion_link_table_hex="
            f"{bytes(sample['motion_link_bytes']).hex()}"
        )

    target = run_dir / "original_level_7_boss_runtime_trace.txt"
    target.write_text("\n".join(lines) + "\n")
    return target


def parse_seed(seed_args: list[str]) -> list[tuple[int, int]]:
    seeds: list[tuple[int, int]] = []
    for item in seed_args or []:
        off_text, val_text = item.split("=", 1)
        seeds.append((int(off_text, 16), int(val_text, 0) & 0xFF))
    return seeds


def wait_for_state(
        pid: int,
        base: int,
        predicate,
        timeout: float,
        label: str) -> dict[str, int]:
    deadline = time.monotonic() + timeout
    state = read_transition_state(pid, base)
    while not predicate(state):
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"timeout waiting for {label}: "
                f"{format_transition_state('state', state)}")
        time.sleep(0.1)
        state = read_transition_state(pid, base)
    return state


def run_live(args) -> int:
    run_dir = Path(args.run_dir).resolve()
    if not (run_dir / "LEZAC.EXE").is_file():
        raise RuntimeError(f"missing {run_dir / 'LEZAC.EXE'}")

    conf = run_dir / "dosbox-seed.conf"
    conf.write_text(
        "[sdl]\nfullscreen=false\noutput=surface\n"
        f"[dosbox]\ncaptures={run_dir}\n"
        "[render]\nframeskip=0\naspect=false\nscaler=none\n"
        "[cpu]\ncycles=fixed 6000\n"
    )
    dosbox = subprocess.Popen(
        ["dosbox", "-conf", str(conf), "-c", f"mount c {run_dir}",
         "-c", "c:", "-c", "LEZAC.EXE"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        def find_windows() -> list[str]:
            try:
                return subprocess.check_output(
                    ["xdotool", "search", "--name", "DOSBox"],
                    text=True, stderr=subprocess.DEVNULL).split()
            except subprocess.CalledProcessError:
                return []

        window = None
        for _ in range(80):
            time.sleep(0.1)
            found = find_windows()
            if found:
                window = found[-1]
                break
            if dosbox.poll() is not None:
                raise RuntimeError(
                    f"DOSBox exited before opening a window: {dosbox.returncode}")
        if not window:
            raise RuntimeError(
                "DOSBox window not found (run under `xvfb-run -a`)")

        def focus() -> None:
            nonlocal window
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if dosbox.poll() is not None:
                    raise RuntimeError(
                        f"DOSBox exited while acquiring focus: "
                        f"{dosbox.returncode}")
                found = find_windows()
                if found:
                    window = found[-1]
                for command in (
                        ["xdotool", "windowfocus", window],
                        ["xdotool", "windowactivate", "--sync", window]):
                    try:
                        focused = subprocess.run(
                            command,
                            stderr=subprocess.DEVNULL,
                            timeout=1.0)
                    except subprocess.TimeoutExpired:
                        continue
                    if focused.returncode == 0:
                        time.sleep(0.1)
                        return
                time.sleep(0.1)
            raise RuntimeError(
                f"DOSBox window could not be focused: last_window={window}")

        def key(name: str) -> None:
            focus()
            # Real XTEST event: SDL/DOSBox drops the --window XSendEvent path.
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", name],
                stderr=subprocess.DEVNULL, check=True)
            time.sleep(0.18)

        def capture(level: int) -> Path:
            before = {
                path.resolve()
                for pattern in ("*.png", "*.bmp")
                for path in run_dir.glob(pattern)
            }
            key("ctrl+F5")
            time.sleep(1)
            after = [
                path.resolve()
                for pattern in ("*.png", "*.bmp")
                for path in run_dir.glob(pattern)
                if path.resolve() not in before
            ]
            if not after:
                raise RuntimeError("DOSBox screenshot was not created")
            source = max(after, key=lambda path: path.stat().st_mtime_ns)
            target = run_dir / (
                f"original_level_{level}_gameplay{source.suffix.lower()}")
            if target.exists():
                target.unlink()
            source.replace(target)
            return target

        time.sleep(args.startup_seconds)
        for _ in range(args.start_taps):
            key(args.start_key)
            time.sleep(args.start_tap_gap)
        time.sleep(args.intro_seconds)
        key(args.intro_key)
        time.sleep(args.level_start_seconds)

        pid = dosbox.pid
        matches = scan_process(pid, DATA_SIGNATURE)
        if not matches:
            raise RuntimeError("data signature not found in DOSBox memory")
        base = matches[-1] - ((RUNTIME_DS << 4) + DATA_STRING_OFFSET)
        state_before = read_transition_state(pid, base)
        if not MIN_PLAYABLE_LEVEL <= state_before["level"] <= MAX_PLAYABLE_LEVEL:
            raise RuntimeError(
                "original did not reach playable state: "
                f"{format_transition_state('state', state_before)}")

        seeds = parse_seed(args.seed)
        transitions = 0
        if args.target_level is not None:
            state = state_before
            while state["level"] < args.target_level:
                from_level = state["level"]
                state = wait_for_state(
                    pid,
                    base,
                    lambda value: value["level"] == from_level
                    and value["collapse_queue"] == 0,
                    args.gate_timeout,
                    f"level {from_level} empty collapse queue",
                )
                gate_deadline = time.monotonic() + args.gate_timeout
                while True:
                    gate_state = read_transition_state(pid, base)
                    if gate_state["level"] != from_level:
                        raise RuntimeError(
                            f"level changed before completion gate: "
                            f"{from_level} -> {gate_state['level']}")
                    if (gate_state["destruction_complete"] != 0
                            and gate_state["bonus_complete"] != 0
                            and gate_state["collapse_queue"] == 0):
                        break
                    if time.monotonic() >= gate_deadline:
                        raise RuntimeError(
                            f"timeout waiting for level {from_level} "
                            "completion gate: "
                            f"{format_transition_state('state', gate_state)}")
                    if gate_state["bonus_complete"] == 0:
                        write_u16(
                            pid, base, BONUS_CURRENT_OFFSET,
                            gate_state["bonus_target"])
                    if gate_state["destruction_complete"] == 0:
                        write_u8(
                            pid, base, DESTRUCTION_CURRENT_OFFSET,
                            gate_state["destruction_target"])
                    time.sleep(0.01)
                print(
                    "seed_original_level_gate=ok"
                    f" level={from_level}"
                    f" bonus={gate_state['bonus_current']}"
                    f"/{gate_state['bonus_target']}"
                    f" destruction={gate_state['destruction_current']}"
                    f"/{gate_state['destruction_target']}"
                    " bonus_complete=1 destruction_complete=1"
                    " collapse_queue=0"
                )

                time.sleep(args.results_seconds)
                expected_level = from_level + 1
                deadline = time.monotonic() + args.advance_timeout
                while True:
                    key(args.advance_key)
                    time.sleep(0.5)
                    state = read_transition_state(pid, base)
                    if state["level"] == expected_level:
                        break
                    if state["level"] != from_level:
                        raise RuntimeError(
                            f"unexpected level transition {from_level}"
                            f" -> {state['level']}")
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            f"level {from_level} results key did not advance")

                time.sleep(args.intro_seconds)
                key(args.intro_key)
                time.sleep(args.level_start_seconds)
                state = wait_for_state(
                    pid,
                    base,
                    lambda value: value["level"] == expected_level
                    and value["destruction_previous"]
                    == value["destruction_current"]
                    and value["bonus_previous"] == value["bonus_current"]
                    and value["destruction_complete"] == 0
                    and value["bonus_complete"] == 0,
                    args.gate_timeout,
                    f"level {expected_level} gameplay",
                )
                transitions += 1
                print(
                    "seed_original_level_transition=ok"
                    f" from_level={from_level}"
                    f" to_level={expected_level}"
                    f" bonus_target={state['bonus_target']}"
                    f" destruction_target={state['destruction_target']}"
                    " gameplay_ready=1"
                )
            state_after = state
        else:
            for offset, value in seeds:
                write_u8(pid, base, offset, value)
            if seeds:
                time.sleep(args.settle)
                key("space")
                time.sleep(args.settle)
            state_after = read_transition_state(pid, base)

        runtime_state_pre = None
        runtime_state_post = None
        boss_trace = None
        if args.trace_boss_ticks:
            boss_trace = write_boss_runtime_trace(
                run_dir, pid, base, args.trace_boss_ticks,
                args.boss_trace_timeout, args.boss_trace_settle)
            print(
                "seed_original_level_boss_trace=ok"
                f" level={state_after['level']}"
                f" samples={args.trace_boss_ticks}"
                f" settle_seconds={args.boss_trace_settle:.6f}"
                " snapshot_guard=SIGSTOP/SIGCONT"
                " max_tick_step=1"
                f" file={boss_trace.name}"
            )
        if args.dump_runtime_state:
            pre_state = read_transition_state(pid, base)
            runtime_state_pre = write_runtime_state_snapshot(
                run_dir, pid, base, pre_state, "pre_capture")
        frame = capture(state_after["level"])
        if args.dump_runtime_state:
            post_state = read_transition_state(pid, base)
            runtime_state_post = write_runtime_state_snapshot(
                run_dir, pid, base, post_state, "post_capture")
            print(
                "seed_original_level_runtime_state=ok"
                f" level={post_state['level']}"
                f" actor_count={read_u8(pid, base, ACTOR_COUNT_OFFSET)}"
                f" motion_link_count={read_u8(pid, base, MOTION_LINK_COUNT_OFFSET)}"
                f" pre_file={runtime_state_pre.name}"
                f" post_file={runtime_state_post.name}"
            )
        print(
            "seed_original_level=ok"
            f" base=0x{base:x} runtime_ds=0x{RUNTIME_DS:04x}"
            f" {format_transition_state('before', state_before)}"
            f" {format_transition_state('after', state_after)}"
            f" target_level={args.target_level or 0}"
            f" transitions={transitions}"
            f" seeds={len(seeds)}"
            f" advanced={int(state_after['level'] != state_before['level'])}"
            f" reached={int(args.target_level is None or state_after['level'] == args.target_level)}"
            f" frame={frame.name}"
            f" boss_trace={boss_trace.name if boss_trace else 'none'}"
            f" runtime_state_pre={runtime_state_pre.name if runtime_state_pre else 'none'}"
            f" runtime_state_post={runtime_state_post.name if runtime_state_post else 'none'}"
        )
        return 0
    finally:
        if dosbox.poll() is None:
            dosbox.terminate()
            try:
                dosbox.wait(timeout=3)
            except subprocess.TimeoutExpired:
                dosbox.kill()
                dosbox.wait(timeout=3)


def self_check() -> int:
    # Static contract check only (no DOSBox): pin every executable window used
    # by the live transition orchestration.
    exe = Path("LEZAC.EXE").read_bytes()
    image = exe[0x770:0x770 + 50480]
    sig_at = image.find(DATA_SIGNATURE)
    if sig_at < 0:
        raise RuntimeError("data signature missing from LEZAC.EXE")
    windows = {
        "level_file_destructible_tile": (
            0x0D26, bytes.fromhex("bfb4791e57")),
        "level_file_bonus_target": (
            0x0D3B, bytes.fromhex("bf86201e57")),
        "level_file_destruction_target": (
            0x0D50, bytes.fromhex("bfb3791e57")),
        "new_game_level_one": (
            0x2F5A, bytes.fromhex("c606b77901")),
        "bonus_counter_compare": (
            0x31BC, bytes.fromhex("a186208946fea18820")),
        "bonus_complete_flag": (
            0x31D6, bytes.fromhex("837efe007f0a31c08946fec606c57901")),
        "destruction_target_compare": (
            0x3218, bytes.fromhex("a0b37930e48946fea0b57930e43b46fe")),
        "destruction_complete_flag": (
            0x323B, bytes.fromhex("31c08946fec606c67901")),
        "level_completion_gate": (
            0x8283,
            bytes.fromhex(
                "803ec579007425803ec67900741e833e8020007517")),
        "level_advance": (
            0x2051, bytes.fromhex("fe06b779")),
        "completed_game_gate": (
            0x829B, bytes.fromhex("803eb779077705")),
        "boss_tick_modulus": (
            0x5E59,
            bytes.fromhex("a1c27831d2b91d00f7f19209c07403")),
        "boss_target_selector": (
            0x6500,
            bytes.fromhex(
                "8b46f69931d029d0998bc88bda8b46f89931d029d09903c113d35250")),
    }
    for name, (offset, expected) in windows.items():
        actual = image[offset:offset + len(expected)]
        if actual != expected:
            raise RuntimeError(
                f"{name} mismatch at 1000:{offset:04x}: "
                f"expected={expected.hex()} actual={actual.hex()}")
    print(
        "seed_original_level_self_check=ok"
        f" signature=1000:{sig_at:04x} data_string_offset=0x{DATA_STRING_OFFSET:02x}"
        f" runtime_ds=0x{RUNTIME_DS:04x} level_byte=0x{LEVEL_BYTE_OFFSET:04x}"
        f" level_range={MIN_PLAYABLE_LEVEL}-{MAX_PLAYABLE_LEVEL}"
        " objective_fields=destructible:ds79b4,bonus_target:ds2086,"
        "destruction_target:ds79b3"
        " objective_counters=bonus:ds2088,destruction:ds79b5"
        " completion_flags=bonus:ds79c5,destruction:ds79c6"
        " completion_helper=1000:3184"
        " completion_gate=1000:8283 collapse_queue=ds:2080"
        " advance_routine=1000:1d61 inc_level=1000:2051"
        " completed_game_gate=1000:829b"
        " runtime_tables=ds:1bae/0x26,ds:c21e/0x08,ds:79ea/0x10"
        " runtime_counts=ds:208d,ds:79f9,ds:c496"
        " boss_trace=tick:ds78c2,seed:ds1afe,tables:actor/visual/link"
        " runtime_camera=ds:c216,ds:c218,ds:c20a,ds:c20c"
        f" pinned_windows={len(windows)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true",
                        help="static contract check against LEZAC.EXE (no DOSBox)")
    parser.add_argument("--run-dir", help="directory with LEZAC.EXE + assets")
    parser.add_argument("--start-key", default="1")
    parser.add_argument("--start-taps", type=int, default=2)
    parser.add_argument("--startup-seconds", type=float, default=6.0)
    parser.add_argument("--start-tap-gap", type=float, default=0.4)
    parser.add_argument("--intro-seconds", type=float, default=3.0)
    parser.add_argument("--intro-key", default="1")
    parser.add_argument("--level-start-seconds", type=float, default=1.5)
    parser.add_argument(
        "--target-level", "--advance-to", dest="target_level", type=int,
        help="reach and capture original playable level 1..7")
    parser.add_argument("--results-seconds", type=float, default=10.0)
    parser.add_argument("--advance-key", default="1")
    parser.add_argument("--gate-timeout", type=float, default=10.0)
    parser.add_argument("--advance-timeout", type=float, default=10.0)
    parser.add_argument("--seed", action="append",
                        help="OFFSET=VALUE (hex offset) DS byte to write, repeatable")
    parser.add_argument(
        "--dump-runtime-state", action="store_true",
        help="write live actor, visual, and motion-link tables beside the frame")
    parser.add_argument(
        "--trace-boss-ticks", type=int, default=0,
        help="atomically capture this many consecutive level-7 boss ticks")
    parser.add_argument(
        "--boss-trace-timeout", type=float, default=30.0,
        help="seconds allowed for a level-7 boss tick trace")
    parser.add_argument(
        "--boss-trace-settle", type=float, default=0.010,
        help="seconds after each tick edge before the frozen boss snapshot")
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
    if args.target_level is not None:
        if not MIN_PLAYABLE_LEVEL <= args.target_level <= MAX_PLAYABLE_LEVEL:
            parser.error("--target-level must be in the playable range 1..7")
        if args.seed:
            parser.error("--target-level cannot be combined with --seed")
    if args.trace_boss_ticks:
        if args.trace_boss_ticks < 2:
            parser.error("--trace-boss-ticks must be at least 2")
        if args.target_level != MAX_PLAYABLE_LEVEL:
            parser.error("--trace-boss-ticks requires --target-level 7")
        if args.boss_trace_timeout <= 0:
            parser.error("--boss-trace-timeout must be positive")
        if args.boss_trace_settle <= 0:
            parser.error("--boss-trace-settle must be positive")
    return run_live(args)


if __name__ == "__main__":
    raise SystemExit(main())
