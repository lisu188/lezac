#!/usr/bin/env python3
"""Capture original level-3 behavior-4 motion as consecutive game ticks.

The live path is Linux/WSL-only and always re-executes under a private Xvfb
display.  It reaches level 3 through the original results flow, waits for the
shipped behavior-4 spawner, and snapshots the complete 64 KiB data segment
once per DS:78C2 tick.  The first phase leaves player 1 at the natural level
start.  The second phase explicitly writes player 1 near the selected actor so
the original homing branch is exercised; those coordinates are labeled as
exogenous in every row.

Live observation and the seeded player phase require both approval flags.  A
temporary game copy is mandatory.  The repository checkout is never launched
or modified.

A single pread reduces cross-table skew but is not an atomic emulator stop.
Captured candidates require independent transition replay and frame review;
completion of sampling alone never promotes a runtime-fidelity claim.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
import seed_original_level as seeder  # noqa: E402


SCHEMA = "lezac_original_behavior4_lockstep_v1"
XVFB_MARKER = "LEZAC_BEHAVIOR4_LOCKSTEP_INSIDE_XVFB"

FRAME_OFFSET = 0x78C2
LEVEL_OFFSET = 0x79B7
RNG_OFFSET = 0x1AFE
ACTOR_TABLE_OFFSET = 0x1BAE
ACTOR_COUNT_OFFSET = 0x208D
ACTOR_STRIDE = 0x26
VISUAL_TABLE_OFFSET = 0xC21E
VISUAL_COUNT_OFFSET = 0xC496
VISUAL_STRIDE = 8
MAX_ACTORS = 64
MAX_VISUALS = 96

TARGET_LEVEL = 3
TARGET_BEHAVIOR = 4
TARGET_KIND = 2
TARGET_SOURCE_SPAWNER = 2
REQUIRED_ASSETS = (
    "LEZAC.EXE",
    "BOMOMIMK.SPR",
    "BOMPAL.PAL",
    "LIVELS.SCH",
    "PROEFS.SON",
    "CARO.CAR",
    "SFONLEF.ZBG",
)


class CaptureIncomplete(RuntimeError):
    """Expected live-capture failure that must not promote a fixture."""


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def i16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def validate_temp_run_dir(run_dir: Path) -> None:
    if not run_dir.is_dir():
        raise RuntimeError(f"run directory does not exist: {run_dir}")
    if run_dir == REPO_ROOT.resolve() or (run_dir / ".git").exists() or (
        run_dir / ".codex-git"
    ).exists():
        raise RuntimeError("--run-dir must be a temporary game copy")
    missing = [name for name in REQUIRED_ASSETS if not (run_dir / name).is_file()]
    if missing:
        raise RuntimeError("temporary game copy is missing: " + ",".join(missing))


def enter_private_xvfb(argv: list[str]) -> None:
    if not sys.platform.startswith("linux") or not Path("/proc").is_dir():
        raise RuntimeError("live capture is Linux/WSL-only")
    if os.environ.get(XVFB_MARKER) == "1":
        if not os.environ.get("DISPLAY"):
            raise RuntimeError("xvfb child has no DISPLAY")
        return
    if not command_exists("xvfb-run"):
        raise RuntimeError("missing xvfb-run")
    environment = os.environ.copy()
    environment[XVFB_MARKER] = "1"
    command = ["xvfb-run", "-a", sys.executable, str(SCRIPT_PATH), *argv]
    os.execvpe(command[0], command, environment)


def self_check(exe_path: Path) -> int:
    exe = exe_path.read_bytes()
    if len(exe) < 0x0770 or exe[:2] != b"MZ":
        raise RuntimeError(f"{exe_path} is not the shipped MZ executable")
    image_base = int.from_bytes(exe[8:10], "little") * 16
    if image_base != 0x0770:
        raise RuntimeError(f"unexpected MZ image base 0x{image_base:04x}")
    image = exe[image_base:]
    windows = {
        "behavior4_dispatch": (
            0x705B,
            bytes.fromhex("3c047403e9f000803e552001720d803e55204c7706"),
        ),
        "behavior4_parameters_and_modulo": (
            0x70BC,
            bytes.fromhex(
                "268b450ea3e8c1c47e04268b4510a37420c47e04268b4512"
                "a37220a1c27831d2f736e8c19209c0756a"
            ),
        ),
        "behavior4_homing_call": (
            0x710D,
            bytes.fromhex(
                "8d7efc16578d7efa1657bf74201e578d7ef416578d7ef21657e842c3"
            ),
        ),
        "behavior4_random_pair": (
            0x712B,
            bytes.fromhex(
                "a17420d1e0509aa81320092b0674208946f4a17420d1e050"
                "9aa81320092b0674208946f2e9da01"
            ),
        ),
        "behavior4_common_collision": (
            0x738F,
            bytes.fromhex(
                "807ede00740b837ef2007d05c746f20100807edd00740b"
                "807edc00740531c08946f4"
            ),
        ),
        "integration_8_8": (
            0x73E5,
            bytes.fromhex(
                "8b46f230ff3d00007d02b7ff8a5eef00c3885eef88e088fc"
                "1146d28b46f430ff3d00007d02b7ff8a5eef8a5ef000c3"
                "885ef088e088fc1146d4"
            ),
        ),
    }
    for label, (offset, expected) in windows.items():
        actual = image[offset:offset + len(expected)]
        if actual != expected:
            raise RuntimeError(
                f"{label} mismatch at 1000:{offset:04x}: "
                f"expected={expected.hex()} actual={actual.hex()}"
            )
    signature_at = image.find(seeder.DATA_SIGNATURE)
    if signature_at < 0:
        raise RuntimeError("DOSBox data-segment locator signature is missing")
    print(
        "behavior4_lockstep_self_check=ok"
        f" schema={SCHEMA}"
        " image_base=0x0770"
        f" data_signature=1000:{signature_at:04x}"
        f" frame=ds:{FRAME_OFFSET:04x}"
        f" actors=ds:{ACTOR_TABLE_OFFSET:04x}/0x{ACTOR_STRIDE:02x}"
        f" visuals=ds:{VISUAL_TABLE_OFFSET:04x}/0x{VISUAL_STRIDE:02x}"
        f" pinned_windows={len(windows)}"
        " live=0 visual_claim=0"
    )
    return 0


def decode_visual(segment: bytes, slot: int) -> dict[str, Any]:
    offset = VISUAL_TABLE_OFFSET + slot * VISUAL_STRIDE
    raw = segment[offset:offset + VISUAL_STRIDE]
    if len(raw) != VISUAL_STRIDE:
        raise CaptureIncomplete(f"visual_row_truncated:{slot}")
    return {
        "slot": slot,
        "x": i16(raw, 0),
        "y": i16(raw, 2),
        "raw": raw.hex(),
    }


def decode_actor(segment: bytes, slot: int) -> dict[str, Any]:
    offset = ACTOR_TABLE_OFFSET + slot * ACTOR_STRIDE
    raw = segment[offset:offset + ACTOR_STRIDE]
    if len(raw) != ACTOR_STRIDE:
        raise CaptureIncomplete(f"actor_row_truncated:{slot}")
    visual_slot = raw[1]
    visual = decode_visual(segment, visual_slot)
    return {
        "slot": slot,
        "kind": raw[0],
        "visual_slot": visual_slot,
        "behavior": raw[0x15],
        "vx": i16(raw, 0x06),
        "vy": i16(raw, 0x08),
        "fx": raw[0x0A],
        "fy": raw[0x0C],
        "ai0": u16(raw, 0x0E),
        "ai1": u16(raw, 0x10),
        "ai2": u16(raw, 0x12),
        "hotspot_y": raw[0x14],
        "hp": raw[0x24],
        "source_spawner": raw[0x25],
        "x": visual["x"],
        "y": visual["y"],
        "visual_raw": visual["raw"],
        "raw": raw.hex(),
    }


def decode_segment(
    segment: bytes,
    target_slot: int | None,
    previous_frame: int | None,
) -> dict[str, Any]:
    frame = u16(segment, FRAME_OFFSET)
    actor_count = segment[ACTOR_COUNT_OFFSET]
    visual_count = segment[VISUAL_COUNT_OFFSET]
    if actor_count > MAX_ACTORS:
        raise CaptureIncomplete(f"implausible_actor_count:{actor_count}")
    if visual_count > MAX_VISUALS:
        raise CaptureIncomplete(f"implausible_visual_count:{visual_count}")
    actors = [decode_actor(segment, slot) for slot in range(actor_count + 1)]
    if target_slot is None:
        target = next(
            (
                actor
                for actor in actors
                if actor["kind"] == TARGET_KIND
                and actor["behavior"] == TARGET_BEHAVIOR
                and actor["source_spawner"] == TARGET_SOURCE_SPAWNER
            ),
            None,
        )
    else:
        target = next((actor for actor in actors if actor["slot"] == target_slot), None)
    player = decode_visual(segment, 0)
    return {
        "type": "tick",
        "schema": SCHEMA,
        "frame": frame,
        "frame_delta": (
            None if previous_frame is None else (frame - previous_frame) & 0xFFFF
        ),
        "level": segment[LEVEL_OFFSET],
        "rng": u32(segment, RNG_OFFSET),
        "actor_count": actor_count,
        "visual_count": visual_count,
        "player": player,
        "target": target,
    }


def fixture_row(sample: dict[str, Any]) -> str:
    actor = sample["target"]
    player = sample["player"]
    assert actor is not None
    return (
        f"tick {sample['frame']}"
        f" phase={sample['phase']}"
        f" seeded={int(sample['player_position_exogenous'])}"
        f" slot={actor['slot']} kind={actor['kind']} behavior={actor['behavior']}"
        f" visual={actor['visual_slot']}"
        f" x={actor['x']} y={actor['y']} fx={actor['fx']} fy={actor['fy']}"
        f" vx={actor['vx']} vy={actor['vy']}"
        f" ai0={actor['ai0']} ai1={actor['ai1']} ai2={actor['ai2']}"
        f" hotspot_y={actor['hotspot_y']} hp={actor['hp']}"
        f" source={actor['source_spawner']}"
        f" p1x={player['x']} p1y={player['y']}"
        f" seed=0x{sample['rng']:08x}"
        f" raw={actor['raw']}"
    )


class CaptureSession:
    def __init__(
        self,
        args: argparse.Namespace,
        out_dir: Path,
        pid: int,
        emulator_base: int,
    ) -> None:
        self.args = args
        self.out_dir = out_dir
        self.pid = pid
        self.ds_base = emulator_base + (seeder.RUNTIME_DS << 4)
        self.target_slot: int | None = None
        self.previous_frame: int | None = None
        self.all_rows = 0
        self.tick_gaps = 0
        self.natural_rows: list[dict[str, Any]] = []
        self.seeded_rows: list[dict[str, Any]] = []
        self.jsonl_path = out_dir / "behavior4_lockstep_ticks.jsonl"
        self.fixture_path = out_dir / "behavior4_lockstep_original_level3.txt"
        self.manifest_path = out_dir / "behavior4_lockstep_manifest.json"
        self.jsonl = self.jsonl_path.open("w", encoding="utf-8")

    def write_jsonl(self, row: dict[str, Any]) -> None:
        self.jsonl.write(json.dumps(row, sort_keys=True) + "\n")
        self.jsonl.flush()

    def write_player_near_target(self, mem_fd: int, actor: dict[str, Any]) -> None:
        x = max(-32768, min(32767, actor["x"] + self.args.near_dx))
        y = max(-32768, min(32767, actor["y"] + self.args.near_dy))
        written = os.pwrite(
            mem_fd,
            struct.pack("<hh", x, y),
            self.ds_base + VISUAL_TABLE_OFFSET,
        )
        if written != 4:
            raise CaptureIncomplete(f"player_seed_write_truncated:{written}")

    def finalize(self, reasons: list[str]) -> bool:
        rows = self.natural_rows + self.seeded_rows
        rng_changes_natural = sum(
            1
            for before, after in zip(self.natural_rows, self.natural_rows[1:])
            if before["rng"] != after["rng"]
        )
        rng_changes_seeded = sum(
            1
            for before, after in zip(self.seeded_rows, self.seeded_rows[1:])
            if before["rng"] != after["rng"]
        )
        if len(self.natural_rows) < self.args.natural_ticks:
            reasons.append("natural_phase_short")
        if len(self.seeded_rows) < self.args.seeded_ticks:
            reasons.append("seeded_phase_short")
        if self.tick_gaps:
            reasons.append(f"tick_gaps:{self.tick_gaps}")
        natural_gate_changes = sum(
            1 for before, after in zip(self.natural_rows, self.natural_rows[1:])
            if before["target"]["ai0"] > 0
            and before["frame"] % before["target"]["ai0"] == 0
            and (before["target"]["vx"], before["target"]["vy"]) !=
                (after["target"]["vx"], after["target"]["vy"])
        )
        if natural_gate_changes < self.args.minimum_natural_retargets:
            reasons.append(f"natural_gate_changes_short:{natural_gate_changes}")
        if rows and any(
            row["target"] is None
            or row["target"]["behavior"] != TARGET_BEHAVIOR
            or row["target"]["source_spawner"] != TARGET_SOURCE_SPAWNER
            for row in rows
        ):
            reasons.append("target_identity_changed")
        complete = not reasons
        manifest = {
            "schema": SCHEMA,
            "status": "complete" if complete else "incomplete",
            "complete": complete,
            "promotion_ready": False,
            "original_runtime_claim": 0,
            "review_required": "transition_replay_and_frame_inspection",
            "visual_claim": 0,
            "temp_copy": True,
            "runtime_ds": f"0x{seeder.RUNTIME_DS:04x}",
            "target_level": TARGET_LEVEL,
            "target_slot": self.target_slot,
            "natural_rows": len(self.natural_rows),
            "seeded_rows": len(self.seeded_rows),
            "tick_rows": len(rows),
            "sampled_rows_total": self.all_rows,
            "tick_gaps": self.tick_gaps,
            "natural_rng_changes": rng_changes_natural,
            "natural_gate_velocity_changes": natural_gate_changes,
            "seeded_rng_changes": rng_changes_seeded,
            "incomplete_reasons": reasons,
            "jsonl": str(self.jsonl_path),
            "fixture": str(self.fixture_path),
        }
        if complete:
            lines = [
                "# Original LEZAC.EXE level-3 behavior-4 motion evidence.",
                "# Whole-DS, tick-locked /proc/mem snapshots; phase=seeded_near",
                "# labels the explicitly exogenous player-position writes.",
                "behavior4_lockstep_original=level3",
                "source=LEZAC.EXE via DOSBox /proc/mem tick-locked read",
                f"schema={SCHEMA}",
                f"runtime_ds={seeder.RUNTIME_DS:04x}",
                "frame_counter_offset=0x78c2",
                "actor_table_offset=0x1bae",
                "actor_stride=0x26",
                "visual_table_offset=0xc21e",
                "visual_stride=0x08",
                "target_kind=2",
                "target_behavior=4",
                "target_source_spawner=2",
                f"target_slot={self.target_slot}",
                f"natural_tick_count={len(self.natural_rows)}",
                f"seeded_tick_count={len(self.seeded_rows)}",
                f"tick_count={len(rows)}",
                f"first_frame={rows[0]['frame']}",
                f"last_frame={rows[-1]['frame']}",
                f"natural_rng_changes={rng_changes_natural}",
                f"seeded_rng_changes={rng_changes_seeded}",
                f"near_offset={self.args.near_dx},{self.args.near_dy}",
                "player_position_exogenous=seeded_near_only",
                "temp_copy=1",
                "visual_claim=0",
            ]
            lines.extend(fixture_row(row) for row in rows)
            self.fixture_path.write_text("\n".join(lines) + "\n", encoding="ascii")
        self.write_jsonl(
            {
                "type": "complete" if complete else "incomplete",
                "schema": SCHEMA,
                "promotion_ready": False,
                "original_runtime_claim": 0,
                "visual_claim": 0,
                "incomplete_reasons": reasons,
            }
        )
        self.jsonl.close()
        atomic_write_json(self.manifest_path, manifest)
        return complete

    def run(self) -> bool:
        deadline = time.monotonic() + self.args.total_timeout_seconds
        mem_fd: int | None = None
        reasons: list[str] = []
        seeded = False
        try:
            mem_fd = os.open(f"/proc/{self.pid}/mem", os.O_RDWR)
            while time.monotonic() < deadline:
                tick_raw = os.pread(mem_fd, 2, self.ds_base + FRAME_OFFSET)
                if len(tick_raw) != 2:
                    reasons.append("frame_counter_read_truncated")
                    break
                polled_frame = struct.unpack("<H", tick_raw)[0]
                if self.previous_frame is not None and polled_frame == self.previous_frame:
                    time.sleep(self.args.poll_seconds)
                    continue
                segment = os.pread(mem_fd, 0x10000, self.ds_base)
                if len(segment) != 0x10000:
                    reasons.append(f"data_segment_read_truncated:{len(segment)}")
                    break
                sample = decode_segment(segment, self.target_slot, self.previous_frame)
                frame = sample["frame"]
                if self.previous_frame is not None and frame == self.previous_frame:
                    continue
                if self.previous_frame is not None and sample["frame_delta"] != 1:
                    self.tick_gaps += 1
                self.previous_frame = frame
                self.all_rows += 1
                if sample["level"] != TARGET_LEVEL:
                    reasons.append(f"level_changed:{sample['level']}")
                    break
                actor = sample["target"]
                if self.target_slot is None:
                    if actor is None:
                        self.write_jsonl(sample)
                        continue
                    self.target_slot = actor["slot"]
                if actor is None:
                    reasons.append("target_actor_missing")
                    break
                if actor["behavior"] != TARGET_BEHAVIOR:
                    reasons.append(f"target_behavior_changed:{actor['behavior']}")
                    break
                sample["phase"] = "seeded_near" if seeded else "natural_far"
                sample["player_position_exogenous"] = seeded
                self.write_jsonl(sample)
                if seeded:
                    self.seeded_rows.append(sample)
                else:
                    self.natural_rows.append(sample)
                if not seeded and len(self.natural_rows) >= self.args.natural_ticks:
                    seeded = True
                if seeded:
                    self.write_player_near_target(mem_fd, actor)
                if len(self.seeded_rows) >= self.args.seeded_ticks:
                    break
            else:
                reasons.append("capture_timeout")
            if self.target_slot is None:
                reasons.append("behavior4_actor_not_observed")
            return self.finalize(reasons)
        except Exception as exc:
            return self.finalize(
                [*reasons, f"capture_exception:{type(exc).__name__}:{exc}"]
            )
        finally:
            if mem_fd is not None:
                os.close(mem_fd)


def run_live(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    out_dir = (
        Path(args.out_dir).resolve()
        if args.out_dir
        else run_dir / "behavior4_lockstep_capture"
    )
    validate_temp_run_dir(run_dir)
    self_check(run_dir / "LEZAC.EXE")
    out_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_path = out_dir / "behavior4_lockstep_manifest.json"
    atomic_write_json(
        bootstrap_path,
        {
            "schema": SCHEMA,
            "status": "starting",
            "complete": False,
            "promotion_ready": False,
            "original_runtime_claim": 0,
            "visual_claim": 0,
            "temp_copy": True,
            "incomplete_reasons": [],
        },
    )

    result: dict[str, Any] = {"hook_ran": False, "complete": False, "session": None}
    original_snapshot = seeder.write_runtime_state_snapshot

    def capture_hook(
        hook_run_dir: Path,
        pid: int,
        base: int,
        state: dict[str, int],
        phase: str,
    ) -> Path:
        if phase == "pre_capture" and state["level"] == TARGET_LEVEL and not result["hook_ran"]:
            result["hook_ran"] = True
            session = CaptureSession(args, out_dir, pid, base)
            result["session"] = session
            print(
                "behavior4_lockstep_capture=start"
                f" level={state['level']} pid={pid}"
                f" runtime_ds=0x{seeder.RUNTIME_DS:04x}"
                f" out={out_dir}",
                flush=True,
            )
            result["complete"] = session.run()
        return original_snapshot(hook_run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = capture_hook
    seeder_argv = [
        "seed_original_level.py",
        "--run-dir",
        str(run_dir),
        "--target-level",
        str(TARGET_LEVEL),
        "--approve-procmem",
        "--approve-runtime-instrumentation",
        "--dump-runtime-state",
        "--startup-seconds",
        str(args.startup_seconds),
        "--intro-seconds",
        str(args.intro_seconds),
        "--level-start-seconds",
        str(args.level_start_seconds),
    ]
    old_argv = sys.argv
    try:
        sys.argv = seeder_argv
        seeder_result = seeder.main()
    except Exception as exc:
        atomic_write_json(bootstrap_path, {
            "schema": SCHEMA,
            "status": "incomplete",
            "complete": False,
            "promotion_ready": False,
            "original_runtime_claim": 0,
            "visual_claim": 0,
            "incomplete_reasons": [f"seeder_exception:{type(exc).__name__}:{exc}"],
        })
        print(
            "behavior4_lockstep_capture=incomplete"
            f" reason=seeder_exception:{type(exc).__name__}:{exc}"
            f" manifest={bootstrap_path}",
            file=sys.stderr,
            flush=True,
        )
        return 2
    finally:
        sys.argv = old_argv
        seeder.write_runtime_state_snapshot = original_snapshot

    if not result["hook_ran"]:
        atomic_write_json(bootstrap_path, {
            "schema": SCHEMA,
            "status": "incomplete",
            "complete": False,
            "promotion_ready": False,
            "original_runtime_claim": 0,
            "visual_claim": 0,
            "incomplete_reasons": ["level3_hook_not_reached"],
        })
        print(
            "behavior4_lockstep_capture=incomplete reason=level3_hook_not_reached"
            f" manifest={bootstrap_path}",
            file=sys.stderr,
        )
        return 2
    session: CaptureSession = result["session"]
    if not result["complete"]:
        print(
            "behavior4_lockstep_capture=incomplete"
            f" natural={len(session.natural_rows)}"
            f" seeded={len(session.seeded_rows)}"
            f" gaps={session.tick_gaps}"
            f" manifest={session.manifest_path}",
            file=sys.stderr,
            flush=True,
        )
        return 2
    print(
        "behavior4_lockstep_capture=ok"
        f" natural={len(session.natural_rows)}"
        f" seeded={len(session.seeded_rows)}"
        f" gaps={session.tick_gaps}"
        " candidate_only=1 original_runtime_claim=0 visual_claim=0"
        f" fixture={session.fixture_path}"
        f" manifest={session.manifest_path}",
        flush=True,
    )
    return seeder_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--exe", type=Path, default=REPO_ROOT / "LEZAC.EXE")
    parser.add_argument("--run-dir")
    parser.add_argument("--out-dir")
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    parser.add_argument("--startup-seconds", type=float, default=6.0)
    parser.add_argument("--intro-seconds", type=float, default=3.0)
    parser.add_argument("--level-start-seconds", type=float, default=1.0)
    parser.add_argument("--total-timeout-seconds", type=float, default=35.0)
    parser.add_argument("--poll-seconds", type=float, default=0.0005)
    parser.add_argument("--natural-ticks", type=int, default=80)
    parser.add_argument("--seeded-ticks", type=int, default=80)
    parser.add_argument("--minimum-natural-retargets", type=int, default=3)
    parser.add_argument("--near-dx", type=int, default=40)
    parser.add_argument("--near-dy", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(actual_argv)
    if args.self_check:
        return self_check(args.exe.resolve())
    if not args.run_dir:
        parser.error("--run-dir is required for live capture")
    if not (args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error(
            "live capture requires --approve-procmem and "
            "--approve-runtime-instrumentation"
        )
    for name in (
        "total_timeout_seconds",
        "poll_seconds",
        "natural_ticks",
        "seeded_ticks",
        "minimum_natural_retargets",
    ):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    enter_private_xvfb(actual_argv)
    for executable in ("dosbox", "xdotool"):
        if not command_exists(executable):
            raise RuntimeError(f"missing live-capture command: {executable}")
    return run_live(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(
            "behavior4_lockstep_capture=error"
            f" reason={type(error).__name__}:{error}",
            file=sys.stderr,
        )
        raise SystemExit(2)
