#!/usr/bin/env python3
"""Capture original LEZAC explosion bytes from a temporary DOSBox process.

This helper is intentionally guarded because it reads /proc/<pid>/mem from the
DOSBox child process it starts. Keep output directories outside the repository.
Candidate fixtures still need frame inspection before promotion.

When --freeze-ghidra-offset is used, the helper also patches only the temporary
copied executable with an infinite loop. That mode is instrumentation evidence,
not pristine original evidence.
"""

from __future__ import annotations

import argparse
import hashlib
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
DEBRIS_BASE = 0x2093
DEBRIS_STRIDE = 0x0B
COLLAPSE_BASE = 0x6611
COLLAPSE_STRIDE = 0x0F
EFFECT_BASE = 0xC21E
EFFECT_STRIDE = 0x08
FREEZE_PATCH = bytes.fromhex("ebfe")


SampleRecord = tuple[float, bytes, bytes, bytes, bytes, bytes]


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


def parse_ghidra_offset(value: str) -> int:
    text = value.strip().lower()
    if ":" in text:
        segment, text = text.split(":", 1)
        if segment not in {"1000", "0x1000"}:
            raise ValueError(f"freeze offset must use Ghidra segment 1000, got {segment}")
    if text.startswith("0x"):
        text = text[2:]
    if not text or len(text) > 4:
        raise ValueError(f"bad Ghidra offset: {value}")
    return int(text, 16)


def patch_freeze(run_dir: Path, ghidra_offset: int) -> dict[str, int | str]:
    exe = run_dir / "LEZAC.EXE"
    data = bytearray(exe.read_bytes())
    if data[:2] != b"MZ":
        raise RuntimeError(f"{exe} is not an MZ executable")
    header_paragraphs = data[8] | (data[9] << 8)
    image_base = header_paragraphs * 16
    file_offset = image_base + ghidra_offset
    if file_offset < image_base or file_offset + len(FREEZE_PATCH) > len(data):
        raise RuntimeError(
            f"freeze offset 1000:{ghidra_offset:04X} maps outside {exe}"
        )
    original = bytes(data[file_offset : file_offset + len(FREEZE_PATCH)])
    data[file_offset : file_offset + len(FREEZE_PATCH)] = FREEZE_PATCH
    exe.write_bytes(data)
    return {
        "ghidra_offset": ghidra_offset,
        "image_base": image_base,
        "file_offset": file_offset,
        "original_bytes": original.hex(),
        "patch_bytes": FREEZE_PATCH.hex(),
    }


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_emulated(pid: int, base: int, segment: int, offset: int, length: int) -> bytes:
    host = base + ((segment << 4) + offset)
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        mem.seek(host)
        return mem.read(length)


def parse_time_list(value: str) -> list[float]:
    if not value:
        return []
    times: list[float] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        parsed = float(item)
        if parsed < 0:
            raise ValueError("sample screenshot times must be non-negative")
        times.append(parsed)
    return sorted(set(times))


def le16(data: bytes, index: int) -> int:
    if index + 1 >= len(data):
        return 0
    return data[index] | (data[index + 1] << 8)


def nonzero_count(data: bytes) -> int:
    return sum(1 for value in data if value != 0)


def debris_slot_fields(dump2090: bytes, slot: int) -> dict[str, int]:
    index = (DEBRIS_BASE - 0x2090) + slot * DEBRIS_STRIDE
    return {
        "slot": slot,
        "addr": DEBRIS_BASE + slot * DEBRIS_STRIDE,
        "tile_index": le16(dump2090, index),
        "flagged": le16(dump2090, index + 2),
        "forward": dump2090[index + 4] if index + 4 < len(dump2090) else 0,
        "reverse": dump2090[index + 5] if index + 5 < len(dump2090) else 0,
        "lookup": dump2090[index + 9] if index + 9 < len(dump2090) else 0,
    }


def collapse_slot_fields(dump6610: bytes, slot: int) -> dict[str, int]:
    index = (COLLAPSE_BASE - 0x6610) + slot * COLLAPSE_STRIDE
    return {
        "slot": slot,
        "addr": COLLAPSE_BASE + slot * COLLAPSE_STRIDE,
        "start": le16(dump6610, index),
        "end": le16(dump6610, index + 2),
        "word": le16(dump6610, index + 4),
        "forward": dump6610[index + 6] if index + 6 < len(dump6610) else 0,
        "reverse": dump6610[index + 7] if index + 7 < len(dump6610) else 0,
        "magnitude": le16(dump6610, index + 8),
        "affected": dump6610[index + 10] if index + 10 < len(dump6610) else 0,
        "count": dump6610[index + 11] if index + 11 < len(dump6610) else 0,
    }


def effect_slot_fields(dumpc21e: bytes, slot: int) -> dict[str, int]:
    index = slot * EFFECT_STRIDE
    return {
        "slot": slot,
        "addr": EFFECT_BASE + slot * EFFECT_STRIDE,
        "x": le16(dumpc21e, index),
        "y": le16(dumpc21e, index + 2),
        "sprite": dumpc21e[index + 4] if index + 4 < len(dumpc21e) else 0,
        "detail": dumpc21e[index + 5] if index + 5 < len(dumpc21e) else 0,
        "timer": dumpc21e[index + 6] if index + 6 < len(dumpc21e) else 0,
        "variant": dumpc21e[index + 7] if index + 7 < len(dumpc21e) else 0,
    }


def debris_slot_score(fields: dict[str, int]) -> int:
    score = 0
    if 0 < fields["tile_index"] < 0x4000 and (fields["flagged"] & 0x8000):
        score += 30
    if fields["forward"] or fields["reverse"]:
        score += 10
    if fields["lookup"]:
        score += 10
    return score


def collapse_slot_score(fields: dict[str, int]) -> int:
    score = 0
    if 0 < fields["start"] <= fields["end"] < 0x4000:
        score += 35
    if 0 < fields["count"] <= 16:
        score += 20
    if 0 < (fields["word"] & 0x7FFF) < 0x4000:
        score += 20
    if (fields["word"] & 0x7FFF) == 0x0009:
        score += 40
    if fields["word"] & 0x8000:
        score += 15
    if fields["forward"] or fields["reverse"]:
        score += 10
    return score


def effect_slot_score(fields: dict[str, int]) -> int:
    score = 0
    if 0x84 <= fields["sprite"] <= 0x89:
        score += 50
    if fields["detail"] == 0x75:
        score += 30
    if fields["timer"] or fields["variant"]:
        score += 10
    return score


def best_scored_slot(
    values: list[dict[str, int]], scorer
) -> tuple[dict[str, int], int]:
    best = max(values, key=scorer)
    return best, scorer(best)


def decode_sample(record: SampleRecord) -> dict[str, int | float]:
    elapsed, dump2070, dump2090, dump6610, dumpc1e0, dumpc21e = record
    del dump2070
    debris, debris_score = best_scored_slot(
        [debris_slot_fields(dump2090, slot) for slot in range(4)], debris_slot_score
    )
    collapse, collapse_score = best_scored_slot(
        [collapse_slot_fields(dump6610, slot) for slot in range(4)],
        collapse_slot_score,
    )
    effect, effect_score = best_scored_slot(
        [effect_slot_fields(dumpc21e, slot) for slot in range(8)], effect_slot_score
    )
    return {
        "elapsed": elapsed,
        "selected_debris_base": debris["addr"],
        "selected_collapse_base": collapse["addr"],
        "selected_effect_base": effect["addr"],
        "selected_debris_slot": debris["slot"],
        "selected_collapse_slot": collapse["slot"],
        "selected_effect_slot": effect["slot"],
        "debris_score": debris_score,
        "collapse_score": collapse_score,
        "effect_score": effect_score,
        "debris_nonzero": nonzero_count(dump2090),
        "collapse_nonzero": nonzero_count(dump6610),
        "lookup_nonzero": nonzero_count(dumpc1e0),
        "effect_nonzero": nonzero_count(dumpc21e),
        "debris_tile_index": debris["tile_index"],
        "debris_flagged": debris["flagged"],
        "debris_forward": debris["forward"],
        "debris_reverse": debris["reverse"],
        "debris_lookup": debris["lookup"],
        "collapse_start": collapse["start"],
        "collapse_end": collapse["end"],
        "collapse_word": collapse["word"],
        "collapse_forward": collapse["forward"],
        "collapse_reverse": collapse["reverse"],
        "collapse_magnitude": collapse["magnitude"],
        "collapse_affected": collapse["affected"],
        "collapse_count": collapse["count"],
        "effect_x": effect["x"],
        "effect_y": effect["y"],
        "effect_sprite": effect["sprite"],
        "effect_detail": effect["detail"],
        "effect_timer": effect["timer"],
        "effect_variant": effect["variant"],
    }


def sample_score(record: SampleRecord) -> int:
    fields = decode_sample(record)
    score = 0
    score += int(fields["debris_score"])
    score += int(fields["collapse_score"])
    score += int(fields["effect_score"])
    return score


def choose_sample(records: list[SampleRecord]) -> SampleRecord:
    scored = [(sample_score(record), record) for record in records]
    best_score, best_record = max(scored, key=lambda item: item[0])
    if best_score > 0:
        return best_record
    for record in records:
        _, _, debris, _, lookup, effect = record
        del lookup
        if any(debris[3:14]) or any(effect[:16]):
            return record
    return max(records, key=lambda item: sum(1 for value in item[3] if value))


def write_sample_summary(path: Path, records: list[SampleRecord]) -> None:
    fields = [
        "elapsed",
        "score",
        "selected_debris_base",
        "selected_collapse_base",
        "selected_effect_base",
        "selected_debris_slot",
        "selected_collapse_slot",
        "selected_effect_slot",
        "debris_score",
        "collapse_score",
        "effect_score",
        "debris_nonzero",
        "collapse_nonzero",
        "lookup_nonzero",
        "effect_nonzero",
        "debris_tile_index",
        "debris_flagged",
        "debris_forward",
        "debris_reverse",
        "debris_lookup",
        "collapse_start",
        "collapse_end",
        "collapse_word",
        "collapse_forward",
        "collapse_reverse",
        "collapse_magnitude",
        "collapse_affected",
        "collapse_count",
        "effect_x",
        "effect_y",
        "effect_sprite",
        "effect_detail",
        "effect_timer",
        "effect_variant",
    ]
    with path.open("w", encoding="ascii") as out:
        out.write("\t".join(fields) + "\n")
        for record in records:
            decoded = decode_sample(record)
            values: list[str] = []
            for field in fields:
                if field == "score":
                    values.append(str(sample_score(record)))
                elif field == "elapsed":
                    values.append(f"{float(decoded[field]):.3f}")
                else:
                    values.append(f"0x{int(decoded[field]):04x}")
            out.write("\t".join(values) + "\n")


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
    parser.add_argument(
        "--sample-screenshot-seconds",
        default="0.5,1.0,1.5,2.0,3.0",
        help="comma-separated seconds after bomb input for visual checkpoints",
    )
    parser.add_argument("--bomb-key", default="n")
    parser.add_argument("--bomb-hold-seconds", type=float, default=0.25)
    parser.add_argument(
        "--approve-instrumentation",
        action="store_true",
        help="required with --freeze-ghidra-offset: approve patching the temp copy",
    )
    parser.add_argument(
        "--freeze-ghidra-offset",
        help="patch temp-copy LEZAC.EXE at Ghidra offset, e.g. 1000:3BB2, to EB FE",
    )
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
    sample_screenshot_seconds = parse_time_list(args.sample_screenshot_seconds)
    freeze_patch: dict[str, int | str] | None = None
    if args.freeze_ghidra_offset:
        if not args.approve_instrumentation:
            print(
                "refusing to patch the temp copy without --approve-instrumentation",
                file=sys.stderr,
            )
            return 64
        freeze_patch = {
            "ghidra_offset": parse_ghidra_offset(args.freeze_ghidra_offset)
        }
    run_dir = out_dir / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    copy_assets(asset_dir, run_dir)
    if freeze_patch is not None:
        freeze_patch = patch_freeze(run_dir, int(freeze_patch["ghidra_offset"]))
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
        freeze_loaded_bytes = b""
        if freeze_patch is not None:
            freeze_loaded_bytes = read_emulated(
                pid, base, RUNTIME_CS, int(freeze_patch["ghidra_offset"]), 8
            )

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

        records: list[SampleRecord] = []
        captured_sample_screenshots: list[str] = []
        pending_screenshots = list(sample_screenshot_seconds)
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
            while pending_screenshots and elapsed >= pending_screenshots[0]:
                target_seconds = pending_screenshots.pop(0)
                label_seconds = f"{target_seconds:.2f}".replace(".", "p")
                label = f"{40 + len(captured_sample_screenshots):03d}_sample_{label_seconds}s"
                snapshot(env, out_dir, game, label)
                captured_sample_screenshots.append(label)
            time.sleep(args.sample_interval)
        snapshot(env, out_dir, game, "090_after_sampling")

        chosen = choose_sample(records)
        sample_summary = out_dir / "sample_summary.tsv"
        write_sample_summary(sample_summary, records)
        screenshot_hashes: list[tuple[str, str]] = []
        for image_path in sorted(out_dir.glob("*.png")):
            screenshot_hashes.append((image_path.name, sha256_file(image_path)))
        after_hash = next(
            (digest for name, digest in screenshot_hashes if name == "090_after_sampling.png"),
            "",
        )
        tail_match_frame = ""
        if after_hash:
            for name, digest in reversed(screenshot_hashes):
                if name != "090_after_sampling.png" and digest == after_hash:
                    tail_match_frame = name
                    break
        freeze_observed = freeze_patch is not None and bool(tail_match_frame)
        chosen_score = sample_score(chosen)
        chosen_fields = decode_sample(chosen)
        elapsed, dump2070, dump2090, dump6610, dumpc1e0, dumpc21e = chosen
        fixture = out_dir / "explosion_playback_oracle_original_candidate.txt"
        with fixture.open("w", encoding="ascii") as out:
            out.write("# LEZAC original explosion playback oracle candidate.\n")
            out.write("# Candidate only: inspect frames before promoting to tests/fixtures.\n")
            out.write(f"# chosen_sample_seconds_after_bomb={elapsed:.2f}\n")
            out.write(f"# chosen_sample_score={chosen_score}\n")
            out.write(
                "# chosen_selected_bases="
                f"debris:{int(chosen_fields['selected_debris_base']):04X},"
                f"collapse:{int(chosen_fields['selected_collapse_base']):04X},"
                f"effect:{int(chosen_fields['selected_effect_base']):04X}\n"
            )
            out.write(f"# sample_summary={sample_summary.name}\n")
            if captured_sample_screenshots:
                out.write(
                    "# sample_screenshots="
                    + ",".join(f"{label}.png" for label in captured_sample_screenshots)
                    + "\n"
                )
            out.write("capture=explosion_playback\n")
            out.write(f"source=dosbox-{args.mode}-process-memory\n")
            out.write("temp_copy=1\nvisual_claim=0\n")
            if freeze_patch is not None:
                out.write("instrumented_temp_copy=1\n")
                out.write(
                    f"instrumented_freeze_observed={1 if freeze_observed else 0}\n"
                )
                if tail_match_frame:
                    out.write(f"instrumented_freeze_tail_frame={tail_match_frame}\n")
                out.write(
                    f"instrumentation=freeze_loop_patch "
                    f"ghidra=1000:{int(freeze_patch['ghidra_offset']):04X} "
                    f"runtime={RUNTIME_CS:04X}:{int(freeze_patch['ghidra_offset']):04X} "
                    f"file_offset=0x{int(freeze_patch['file_offset']):x} "
                    f"old_bytes={freeze_patch['original_bytes']} "
                    f"patch_bytes={freeze_patch['patch_bytes']} "
                    f"loaded_bytes={freeze_loaded_bytes.hex()}\n"
                )
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
            out.write(f"selected_debris_base={int(chosen_fields['selected_debris_base']):04X}\n")
            out.write(f"selected_collapse_base={int(chosen_fields['selected_collapse_base']):04X}\n")
            out.write(f"selected_effect_base={int(chosen_fields['selected_effect_base']):04X}\n")
            for ghidra, offset, label in [
                ("1000:75F1", 0x75F1, "bomb_expire_dispatch_call"),
                ("1000:414A", 0x414A, "explosion_dispatcher"),
                ("1000:370E", 0x370E, "tile_damage_queue"),
                ("1000:3A7E", 0x3A7E, "damage_forward_lookup"),
                ("1000:3B18", 0x3B18, "damage_reverse_lookup"),
                ("1000:3BB2", 0x3BB2, "collapse_forward_pass"),
                ("1000:3D46", 0x3D46, "collapse_reverse_pass"),
            ]:
                observed = "process_memory_sampling_no_debugger_break"
                if freeze_patch is not None and offset == int(freeze_patch["ghidra_offset"]):
                    observed = (
                        "instrumented_temp_copy_freeze_observed"
                        if freeze_observed
                        else "instrumented_temp_copy_patch_loaded_no_freeze_observed"
                    )
                out.write(
                    f"break ghidra={ghidra} runtime={RUNTIME_CS:04X}:{offset:04X} "
                    f"label={label} observed={observed}\n"
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

        instrumentation_manifest = ""
        if freeze_patch is not None:
            instrumentation_manifest = (
                f"freeze_ghidra=1000:{int(freeze_patch['ghidra_offset']):04X}\n"
                f"freeze_runtime={RUNTIME_CS:04X}:{int(freeze_patch['ghidra_offset']):04X}\n"
                f"freeze_file_offset=0x{int(freeze_patch['file_offset']):x}\n"
                f"freeze_old_bytes={freeze_patch['original_bytes']}\n"
                f"freeze_patch_bytes={freeze_patch['patch_bytes']}\n"
                f"freeze_loaded_bytes={freeze_loaded_bytes.hex()}\n"
            )
        manifest = out_dir / "manifest.txt"
        manifest.write_text(
            f"capture=original_explosion_process_memory\n"
            f"mode={args.mode}\n"
            f"method=approved_process_memory_scan_limited_to_child_dosbox_process\n"
            f"run_dir={run_dir}\n"
            f"fixture_candidate={fixture}\n"
            f"runtime_cs={RUNTIME_CS:04X}\n"
            f"runtime_ds={RUNTIME_DS:04X}\n"
            f"instrumented_temp_copy={1 if freeze_patch is not None else 0}\n"
            f"{instrumentation_manifest}"
            f"instrumented_freeze_observed={1 if freeze_observed else 0}\n"
            f"instrumented_freeze_tail_frame={tail_match_frame}\n"
            f"input_start_key={args.start_key}\n"
            f"input_start_taps={max(args.start_taps, 1)}\n"
            f"input_level_start_seconds={args.level_start_seconds:.2f}\n"
            f"input_right_key={args.right_key}\n"
            f"input_right_hold_seconds={args.right_hold_seconds:.2f}\n"
            f"input_bomb_key={args.bomb_key}\n"
            f"input_bomb_hold_seconds={args.bomb_hold_seconds:.2f}\n"
            f"sample_seconds={args.sample_seconds:.2f}\n"
            f"sample_interval={args.sample_interval:.3f}\n"
            f"sample_summary={sample_summary}\n"
            f"sample_screenshots="
            f"{','.join(label + '.png' for label in captured_sample_screenshots)}\n"
            f"chosen_sample_seconds_after_bomb={elapsed:.2f}\n"
            f"chosen_sample_score={chosen_score}\n"
            f"selected_debris_base={int(chosen_fields['selected_debris_base']):04X}\n"
            f"selected_collapse_base={int(chosen_fields['selected_collapse_base']):04X}\n"
            f"selected_effect_base={int(chosen_fields['selected_effect_base']):04X}\n"
            f"screenshot_sha256="
            f"{','.join(name + ':' + digest for name, digest in screenshot_hashes)}\n"
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
