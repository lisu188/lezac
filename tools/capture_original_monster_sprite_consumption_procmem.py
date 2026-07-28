#!/usr/bin/env python3
"""Capture a natural level-1 monster kill from the original LEZAC.EXE.

This helper is intentionally Linux/WSL-only.  A live invocation always
re-executes itself below ``xvfb-run -a`` before starting DOSBox, even when the
caller already has a desktop DISPLAY.  That makes accidental popup windows
impossible.  The caller must supply a temporary run directory containing a
copy of the original game and its assets; the repository checkout is refused.

The capture is tick-locked on DS:78C2.  After a two-byte poll observes a new
tick, exactly one 64-KiB ``os.pread`` snapshots the complete data segment.
Actor rows (DS:1BAE, stride 0x26), visual rows (DS:C21E, stride 8), sprite
descriptors (DS:C322), RNG, score, and the driven XTEST input are consequently
from one non-torn sample.  Route-dependent input and player position are
explicitly exogenous.

The default route pre-positions player 1 near x=328, drops a small bomb at
frame 218 before the known natural frame-257 kind-1 spawn, retreats, and uses
bounded retries if necessary.  After a fatal transition it follows
the descriptor-decoded reward visual (sprites 61..67) and attempts collection.
Every authoritative checkpoint also starts an invisible X11 window snapshot;
the tick sampler remains non-blocking while the PNG is written.

Outputs:
  * ``monster_sprite_consumption_ticks.jsonl`` -- metadata, one full row per
    sampled tick, and a terminal complete/incomplete record.
  * ``monster_sprite_consumption_manifest.json`` -- promotion gate, checkpoint
    frames/screenshots, descriptor fingerprint, route attempts, and exact
    incomplete reasons.

Timeouts and route failures never create a successful-looking artifact:
``promotion_ready`` remains false unless pre-impact, fatal impact, corpse
playback, reward visibility, collection, every checkpoint screenshot exists,
and the authoritative tick stream is consecutive.

Live process-memory observation requires both explicit approval flags.  The
``--self-check`` path is non-live and pins the executable, sprite-bank, table,
and fatal-transition assumptions without launching DOSBox or Xvfb.
"""

from __future__ import annotations

import argparse
import hashlib
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


SCHEMA = "lezac_original_monster_sprite_consumption_v1"
XVFB_MARKER = "LEZAC_MONSTER_SPRITE_CAPTURE_INSIDE_XVFB"

FRAME_OFFSET = 0x78C2
LEVEL_OFFSET = 0x79B7
RNG_OFFSET = 0x1AFE
P1_SCORE_OFFSET = 0x785A

ACTOR_TABLE_OFFSET = 0x1BAE
ACTOR_COUNT_OFFSET = 0x208D
ACTOR_STRIDE = 0x26
MAX_ACTORS = 64

VISUAL_TABLE_OFFSET = 0xC21E
VISUAL_COUNT_OFFSET = 0xC496
VISUAL_STRIDE = 8
MAX_VISUALS = 96

DESCRIPTOR_TABLE_OFFSET = 0xC322
DESCRIPTOR_STRIDE = 4
DESCRIPTOR_ENTRIES = 92
DESCRIPTOR_BYTES = DESCRIPTOR_STRIDE * DESCRIPTOR_ENTRIES

KIND_ONE = 1
DEATH_KIND = 0x0C
DEATH_BEHAVIOR = 2
REWARD_SPRITES = frozenset(range(61, 68))
REQUIRED_CHECKPOINTS = (
    "pre_impact",
    "fatal_impact",
    "corpse_playback",
    "reward_visible",
    "collection",
)

REQUIRED_LEVEL1_ASSETS = (
    "LEZAC.EXE",
    "BOMOMIMK.SPR",
    "BOMPAL.PAL",
    "LIVELS.SCH",
    "PROEFS.SON",
    "CARO.CAR",
    "SFONLEF.ZBG",
)


class CaptureIncomplete(RuntimeError):
    """Expected live-capture failure that must leave an incomplete manifest."""


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


def parse_sprite_bank(path: Path) -> dict[str, Any]:
    """Parse the original counted [w,h,pixels...] SPR layout."""
    data = path.read_bytes()
    if not data:
        raise RuntimeError(f"empty sprite bank: {path}")
    count = data[0]
    position = 1
    dimensions: list[list[int]] = []
    payload_bytes = 0
    pixel_offsets: list[int] = []
    for index in range(count):
        if position + 2 > len(data):
            raise RuntimeError(f"sprite {index} header is truncated in {path}")
        width = data[position]
        height = data[position + 1]
        position += 2
        size = width * height
        if width == 0 or height == 0 or position + size > len(data):
            raise RuntimeError(f"sprite {index} payload is invalid in {path}")
        pixel_offsets.append(payload_bytes)
        dimensions.append([width, height])
        payload_bytes += size
        position += size
    if position != len(data):
        raise RuntimeError(
            f"sprite bank has {len(data) - position} trailing bytes: {path}"
        )
    return {
        "count": count,
        "dimensions": dimensions,
        "payload_bytes": payload_bytes,
        "pixel_offsets": pixel_offsets,
        "file_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def self_check(exe_path: Path, sprite_path: Path) -> int:
    """Static, non-live validation of every address/layout assumption."""
    exe = exe_path.read_bytes()
    if len(exe) < 0x0770 or exe[:2] != b"MZ":
        raise RuntimeError(f"{exe_path} is not the shipped MZ executable")
    image_base = int.from_bytes(exe[8:10], "little") * 16
    if image_base != 0x0770:
        raise RuntimeError(
            f"unexpected MZ image base 0x{image_base:04x} in {exe_path}"
        )
    image = exe[image_base:]

    pinned_windows = {
        # Normal fatal damage: reset +1B, behavior 2, kind 0x0C, byte +2 0x19.
        "fatal_reset_byte1b": (
            0x74BB,
            bytes.fromhex("c47e0426c6451b00"),
        ),
        "fatal_behavior_kind_byte02": (
            0x74CC,
            bytes.fromhex(
                "c47ec626c6451502c47ec626c6050cc47ec626c6450219"
            ),
        ),
        # Source-spawner slot is actor +0x25 and returns through DS:74B2.
        "fatal_source_spawner_return": (
            0x74E3,
            bytes.fromhex("c47ec626807d25007610c47ec6268a452530e46bf81e"),
        ),
        # Seven reward score words, indexed by the reward selector.
        "reward_score_table": (
            0xAA56,
            bytes.fromhex("d007e803dc05d007b80be8038813"),
        ),
        # Adjacent normal/impact/reward table bytes consumed by actor code.
        "monster_sprite_tables": (
            0xAA70,
            bytes.fromhex(
                "5a002841474e53595d642c2d2e2f0102222702090a11151c1d2345494a4f"
            ),
        ),
    }
    for label, (offset, expected) in pinned_windows.items():
        actual = image[offset:offset + len(expected)]
        if actual != expected:
            raise RuntimeError(
                f"{label} mismatch at 1000:{offset:04x}: "
                f"expected={expected.hex()} actual={actual.hex()}"
            )

    signature_at = image.find(seeder.DATA_SIGNATURE)
    if signature_at < 0:
        raise RuntimeError("DOSBox data-segment locator signature is missing")

    sprite = parse_sprite_bank(sprite_path)
    if (
        sprite["count"] != 91
        or sprite["payload_bytes"] != 19985
        or sprite["file_bytes"] != 20168
    ):
        raise RuntimeError(
            "BOMOMIMK.SPR static profile changed: "
            f"count={sprite['count']} payload={sprite['payload_bytes']} "
            f"file_bytes={sprite['file_bytes']}"
        )
    expected_ranges = {
        "kind1_left": (43, 44),
        "kind1_right": (45, 46),
        "kind2": (39, 41),
        "kind3": (49, 51),
        "kind4": (53, 55),
        "rewards": (61, 67),
    }
    for first, last in expected_ranges.values():
        if not (0 <= first <= last < sprite["count"]):
            raise RuntimeError("monster sprite range is outside BOMOMIMK.SPR")

    # A live descriptor entry k points at zero-based file sprite k-1.  Its
    # pixel offset is cumulative payload, with entry zero reserved.
    descriptor_offsets = [0] + sprite["pixel_offsets"]
    if len(descriptor_offsets) != DESCRIPTOR_ENTRIES:
        raise RuntimeError("descriptor entry count no longer matches sprite bank")
    if descriptor_offsets[44] != 11008 or descriptor_offsets[68] != 15741:
        raise RuntimeError("descriptor cumulative offsets changed")

    print(
        "monster_sprite_consumption_self_check=ok"
        f" schema={SCHEMA}"
        f" image_base=0x{image_base:04x}"
        f" data_signature=1000:{signature_at:04x}"
        f" runtime_ds=0x{seeder.RUNTIME_DS:04x}"
        f" tick=ds:{FRAME_OFFSET:04x}"
        f" actors=ds:{ACTOR_TABLE_OFFSET:04x}/0x{ACTOR_STRIDE:02x}"
        f" visuals=ds:{VISUAL_TABLE_OFFSET:04x}/0x{VISUAL_STRIDE:02x}"
        f" descriptors=ds:{DESCRIPTOR_TABLE_OFFSET:04x}"
        f"/{DESCRIPTOR_ENTRIES}x{DESCRIPTOR_STRIDE}"
        f" sprites={sprite['count']}"
        f" payload_bytes={sprite['payload_bytes']}"
        " reward_sprites=61-67"
        f" pinned_windows={len(pinned_windows)}"
        " live=0 popup_windows=0"
    )
    return 0


def validate_temp_run_dir(run_dir: Path) -> None:
    if not run_dir.is_dir():
        raise RuntimeError(f"run directory does not exist: {run_dir}")
    resolved_repo = REPO_ROOT.resolve()
    if run_dir == resolved_repo or (run_dir / ".git").exists() or (
        run_dir / ".codex-git"
    ).exists():
        raise RuntimeError(
            "--run-dir must be a temporary copy, not the repository checkout"
        )
    missing = [name for name in REQUIRED_LEVEL1_ASSETS if not (run_dir / name).is_file()]
    if missing:
        raise RuntimeError(
            "temporary run directory is missing original assets: "
            + ",".join(missing)
        )


def enter_private_xvfb(argv: list[str]) -> None:
    """Always isolate live DOSBox in a fresh invisible Xvfb display."""
    if not sys.platform.startswith("linux") or not Path("/proc").is_dir():
        raise RuntimeError(
            "live capture is Linux/WSL-only; invoke it through WSL"
        )
    if os.environ.get(XVFB_MARKER) == "1":
        if not os.environ.get("DISPLAY"):
            raise RuntimeError("xvfb child has no DISPLAY")
        return
    if not command_exists("xvfb-run"):
        raise RuntimeError("missing xvfb-run for popup-free live capture")
    environment = os.environ.copy()
    environment[XVFB_MARKER] = "1"
    command = ["xvfb-run", "-a", sys.executable, str(SCRIPT_PATH), *argv]
    os.execvpe(command[0], command, environment)


def descriptor_contract(
    segment: bytes,
) -> tuple[dict[str, Any], dict[bytes, int]]:
    raw = segment[
        DESCRIPTOR_TABLE_OFFSET:DESCRIPTOR_TABLE_OFFSET + DESCRIPTOR_BYTES
    ]
    if len(raw) != DESCRIPTOR_BYTES:
        raise CaptureIncomplete("descriptor_table_truncated")
    entries = []
    descriptor_to_sprite: dict[bytes, int] = {}
    for entry in range(DESCRIPTOR_ENTRIES):
        offset = entry * DESCRIPTOR_STRIDE
        width = raw[offset]
        height = raw[offset + 1]
        pixel_offset = u16(raw, offset + 2)
        sprite_index = None if entry == 0 else entry - 1
        entries.append(
            {
                "entry": entry,
                "sprite_index": sprite_index,
                "width": width,
                "height": height,
                "pixel_offset": pixel_offset,
                "raw": raw[offset:offset + DESCRIPTOR_STRIDE].hex(),
            }
        )
        if entry != 0:
            descriptor_to_sprite[
                raw[offset:offset + DESCRIPTOR_STRIDE]
            ] = entry - 1
    if raw[:4] != b"\0\0\0\0":
        raise CaptureIncomplete("descriptor_entry0_not_reserved")
    if len(descriptor_to_sprite) != DESCRIPTOR_ENTRIES - 1:
        raise CaptureIncomplete("descriptor_rows_not_unique")
    contract = {
        "offset": f"0x{DESCRIPTOR_TABLE_OFFSET:04x}",
        "stride": DESCRIPTOR_STRIDE,
        "entries": DESCRIPTOR_ENTRIES,
        "entry0_reserved": True,
        "mapping": "entry_k_to_zero_based_file_sprite_k_minus_1",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "raw": raw.hex(),
        "decoded": entries,
    }
    return contract, descriptor_to_sprite


def decode_visual(
    raw: bytes,
    slot: int,
    descriptor_to_sprite: dict[bytes, int],
) -> dict[str, Any]:
    descriptor_raw = raw[4:8]
    return {
        "slot": slot,
        "x": i16(raw, 0),
        "y": i16(raw, 2),
        "descriptor_raw": descriptor_raw.hex(),
        "pixel_offset": u16(raw, 6),
        "sprite_index": descriptor_to_sprite.get(descriptor_raw),
        "raw": raw.hex(),
    }


def decode_segment(
    segment: bytes,
    descriptor_to_sprite: dict[bytes, int],
    previous_frame: int | None,
) -> dict[str, Any]:
    frame = u16(segment, FRAME_OFFSET)
    actor_count = segment[ACTOR_COUNT_OFFSET]
    visual_count = segment[VISUAL_COUNT_OFFSET]
    if actor_count > MAX_ACTORS:
        raise CaptureIncomplete(f"implausible_actor_count:{actor_count}")
    if visual_count > MAX_VISUALS:
        raise CaptureIncomplete(f"implausible_visual_count:{visual_count}")

    visuals = []
    for slot in range(visual_count):
        offset = VISUAL_TABLE_OFFSET + slot * VISUAL_STRIDE
        raw = segment[offset:offset + VISUAL_STRIDE]
        if len(raw) != VISUAL_STRIDE:
            raise CaptureIncomplete(f"visual_row_truncated:{slot}")
        visuals.append(decode_visual(raw, slot, descriptor_to_sprite))
    visual_by_slot = {row["slot"]: row for row in visuals}

    # DS:208D is the highest live 1-based actor slot.  Slot zero is reserved,
    # but preserving it in every row is useful when checking table indexing.
    actors = []
    for slot in range(actor_count + 1):
        offset = ACTOR_TABLE_OFFSET + slot * ACTOR_STRIDE
        raw = segment[offset:offset + ACTOR_STRIDE]
        if len(raw) != ACTOR_STRIDE:
            raise CaptureIncomplete(f"actor_row_truncated:{slot}")
        visual_slot = raw[1]
        actors.append(
            {
                "slot": slot,
                "kind": raw[0],
                "visual_slot": visual_slot,
                "byte02": raw[2],
                "anim_a": raw[3],
                "anim_b": raw[4],
                "behavior": raw[0x15],
                "byte1a": raw[0x1A],
                "byte1b": raw[0x1B],
                "byte24": raw[0x24],
                "source_spawner": raw[0x25],
                "raw": raw.hex(),
                "visual": visual_by_slot.get(visual_slot),
            }
        )

    player_visual = visual_by_slot.get(0)
    player = None
    if player_visual is not None:
        player = dict(player_visual)
        player["position_exogenous"] = True

    reward_candidates = [
        row for row in visuals if row["sprite_index"] in REWARD_SPRITES
    ]
    return {
        "type": "tick",
        "schema": SCHEMA,
        "frame": frame,
        "frame_delta": (
            None if previous_frame is None else (frame - previous_frame) & 0xFFFF
        ),
        "level": segment[LEVEL_OFFSET],
        "rng": u32(segment, RNG_OFFSET),
        "score": u32(segment, P1_SCORE_OFFSET),
        "player": player,
        "actor_count": actor_count,
        "actor_slot_count": actor_count + 1,
        "actors": actors,
        "visual_count": visual_count,
        "visuals": visuals,
        "reward_candidates": reward_candidates,
        "checkpoints": [],
        "screenshots": {},
    }


def actor_at(sample: dict[str, Any], slot: int | None) -> dict[str, Any] | None:
    if slot is None:
        return None
    for actor in sample["actors"]:
        if actor["slot"] == slot:
            return actor
    return None


def first_natural_kind_one(sample: dict[str, Any]) -> dict[str, Any] | None:
    for actor in sample["actors"]:
        if (
            actor["slot"] > 0
            and actor["kind"] == KIND_ONE
            and actor["behavior"] not in (0, DEATH_BEHAVIOR)
            and actor["source_spawner"] > 0
            and actor["visual"] is not None
        ):
            return actor
    return None


def nearest_reward(
    sample: dict[str, Any],
    death_x: int | None,
    death_y: int | None,
) -> dict[str, Any] | None:
    candidates = sample["reward_candidates"]
    if not candidates:
        return None
    if death_x is None or death_y is None:
        return candidates[0]
    return min(
        candidates,
        key=lambda row: abs(row["x"] - death_x) + abs(row["y"] - death_y),
    )


class XTestDriver:
    """Real XTEST input only; never use xdotool's --window XSendEvent path."""

    def __init__(self, dosbox_pid: int):
        self.dosbox_pid = dosbox_pid
        self.window: str | None = None
        self.held: set[str] = set()
        self.events: list[dict[str, Any]] = []

    def find_window(self) -> str:
        try:
            result = subprocess.check_output(
                ["xdotool", "search", "--name", "DOSBox"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2.0,
            ).split()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            result = []
        if not result:
            raise CaptureIncomplete(
                f"dosbox_window_not_found_for_pid:{self.dosbox_pid}"
            )
        self.window = result[-1]
        return self.window

    def focus(self) -> None:
        window = self.window or self.find_window()
        for command in (
            ["xdotool", "windowfocus", window],
            ["xdotool", "windowactivate", "--sync", window],
        ):
            try:
                result = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2.0,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                continue
            if result.returncode == 0:
                return
        self.window = None
        raise CaptureIncomplete("dosbox_window_focus_failed")

    def _run_key(self, action: str, key_name: str) -> None:
        self.focus()
        subprocess.run(
            ["xdotool", action, "--clearmodifiers", key_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3.0,
            check=True,
        )

    def tap(self, key_name: str, reason: str) -> None:
        self._run_key("key", key_name)
        self.events.append(
            {"action": "tap", "key": key_name, "reason": reason}
        )

    def hold_only(self, key_name: str | None, reason: str) -> None:
        desired = set() if key_name is None else {key_name}
        for held_key in sorted(self.held - desired):
            self._run_key("keyup", held_key)
            self.held.remove(held_key)
            self.events.append(
                {"action": "keyup", "key": held_key, "reason": reason}
            )
        for new_key in sorted(desired - self.held):
            self._run_key("keydown", new_key)
            self.held.add(new_key)
            self.events.append(
                {"action": "keydown", "key": new_key, "reason": reason}
            )

    def release_all(self, reason: str) -> None:
        self.hold_only(None, reason)

    def input_state(self) -> dict[str, Any]:
        state = {
            "held_keys": sorted(self.held),
            "events_since_previous": list(self.events),
            "exogenous": True,
        }
        self.events.clear()
        return state


class CaptureSession:
    def __init__(
        self,
        args: argparse.Namespace,
        run_dir: Path,
        out_dir: Path,
        pid: int,
        base: int,
        window: str,
    ):
        self.args = args
        self.run_dir = run_dir
        self.out_dir = out_dir
        self.pid = pid
        self.base = base
        self.ds_base = base + (seeder.RUNTIME_DS << 4)
        self.driver = XTestDriver(pid)
        self.driver.window = window
        self.jsonl_path = out_dir / "monster_sprite_consumption_ticks.jsonl"
        self.manifest_path = out_dir / "monster_sprite_consumption_manifest.json"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl = self.jsonl_path.open("w", encoding="utf-8")
        self.manifest: dict[str, Any] = {
            "schema": SCHEMA,
            "status": "running",
            "complete": False,
            "promotion_ready": False,
            "visual_claim": 0,
            "original_runtime_claim": 0,
            "source": "LEZAC.EXE via DOSBox /proc/mem",
            "temp_copy": True,
            "popup_windows": 0,
            "xvfb_isolated": True,
            "run_dir": str(run_dir),
            "out_dir": str(out_dir),
            "jsonl": str(self.jsonl_path),
            "manifest": str(self.manifest_path),
            "runtime_ds": f"0x{seeder.RUNTIME_DS:04x}",
            "frame_counter": f"0x{FRAME_OFFSET:04x}",
            "read_contract": "one_64k_pread_per_sampled_ds78c2_tick",
            "exogenous_fields": ["input", "player.x", "player.y"],
            "bomb_type": 1,
            "bomb_damage": 1,
            "checkpoints": {},
            "required_checkpoints": list(REQUIRED_CHECKPOINTS),
            "incomplete_reasons": [],
            "bomb_attempts": [],
            "route": {
                "method": "real_xtest_closed_loop",
                "parking_x": args.parking_x,
                "parking_tolerance": args.parking_tolerance,
                "first_bomb_frame": args.first_bomb_frame,
                "fire_hold_ticks": args.fire_hold_ticks,
                "bomb_distance": args.bomb_distance,
                "flee_ticks": args.flee_ticks,
                "retry_ticks": args.bomb_retry_ticks,
                "max_bombs": args.max_bombs,
            },
            "offsets": {
                "level": f"0x{LEVEL_OFFSET:04x}",
                "rng_u32": f"0x{RNG_OFFSET:04x}",
                "p1_score_u32": f"0x{P1_SCORE_OFFSET:04x}",
                "actor_table": f"0x{ACTOR_TABLE_OFFSET:04x}",
                "actor_count": f"0x{ACTOR_COUNT_OFFSET:04x}",
                "actor_stride": ACTOR_STRIDE,
                "actor_index_base": 1,
                "actor_neutral_bytes": {
                    "byte02": "0x02",
                    "byte1a": "0x1a",
                    "byte1b": "0x1b",
                    "byte24": "0x24",
                },
                "visual_table": f"0x{VISUAL_TABLE_OFFSET:04x}",
                "visual_count": f"0x{VISUAL_COUNT_OFFSET:04x}",
                "visual_stride": VISUAL_STRIDE,
                "visual_index_base": 0,
                "descriptor_table": f"0x{DESCRIPTOR_TABLE_OFFSET:04x}",
                "descriptor_stride": DESCRIPTOR_STRIDE,
                "descriptor_entries": DESCRIPTOR_ENTRIES,
            },
        }
        atomic_write_json(self.manifest_path, self.manifest)

        self.previous_frame: int | None = None
        self.first_frame: int | None = None
        self.last_frame: int | None = None
        self.tick_rows = 0
        self.tick_gaps = 0
        self.target_slot: int | None = None
        self.target_spawn_frame: int | None = None
        self.fatal_frame: int | None = None
        self.fatal_score: int | None = None
        self.death_x: int | None = None
        self.death_y: int | None = None
        self.reward_identity: tuple[int, int] | None = None
        self.reward_visible_score: int | None = None
        self.last_bomb_frame: int | None = None
        self.fire_release_frame: int | None = None
        self.flee_until_frame: int | None = None
        self.bomb_attempts = 0
        self.last_player_x: int | None = None
        self.player_still_ticks = 0
        self.last_jump_frame: int | None = None
        self.descriptor: dict[str, Any] | None = None
        self.descriptor_to_sprite: dict[bytes, int] = {}
        self.screenshot_processes: dict[str, subprocess.Popen[bytes]] = {}

    def write_jsonl(self, value: dict[str, Any]) -> None:
        self.jsonl.write(json.dumps(value, sort_keys=True) + "\n")
        self.jsonl.flush()

    def initialize_descriptor(self, segment: bytes) -> None:
        contract, descriptor_to_sprite = descriptor_contract(segment)
        self.descriptor = contract
        self.descriptor_to_sprite = descriptor_to_sprite
        self.manifest["descriptor"] = {
            key: value
            for key, value in contract.items()
            if key not in ("raw", "decoded")
        }
        self.write_jsonl(
            {
                "type": "metadata",
                "schema": SCHEMA,
                "runtime_ds": f"0x{seeder.RUNTIME_DS:04x}",
                "read_contract": "one_64k_pread_per_sampled_ds78c2_tick",
                "exogenous_fields": ["input", "player.x", "player.y"],
                "bomb_type": 1,
                "bomb_damage": 1,
                "offsets": self.manifest["offsets"],
                "descriptor": contract,
            }
        )
        atomic_write_json(self.manifest_path, self.manifest)

    def screenshot(self, frame: int, checkpoints: list[str]) -> str:
        joined = "_".join(checkpoints)
        target = self.out_dir / f"checkpoint_{frame:05d}_{joined}.png"
        if target.exists():
            target.unlink()
        window = self.driver.window or self.driver.find_window()
        process = subprocess.Popen(
            ["import", "-window", window, str(target)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.screenshot_processes[target.name] = process
        return target.name

    def add_checkpoints(
        self,
        sample: dict[str, Any],
        candidates: list[str],
    ) -> None:
        new_labels = [
            label for label in candidates if label not in self.manifest["checkpoints"]
        ]
        new_labels = list(dict.fromkeys(new_labels))
        if not new_labels:
            return
        self.driver.release_all("checkpoint")
        screenshot = self.screenshot(sample["frame"], new_labels)
        for label in new_labels:
            sample["checkpoints"].append(label)
            sample["screenshots"][label] = screenshot
            self.manifest["checkpoints"][label] = {
                "frame": sample["frame"],
                "screenshot": screenshot,
                "screenshot_capture": "headless_x11_import",
                "screenshot_request_is_async": True,
                "tick_row_is_authoritative": True,
            }
        atomic_write_json(self.manifest_path, self.manifest)

    def frame_elapsed(self, now: int, then: int | None) -> int:
        return 0 if then is None else (now - then) & 0xFFFF

    def target_is_fatal(self, actor: dict[str, Any] | None) -> bool:
        return actor is not None and (
            actor["behavior"] == DEATH_BEHAVIOR or actor["kind"] == DEATH_KIND
        )

    def classify_and_checkpoint(self, sample: dict[str, Any]) -> None:
        frame = sample["frame"]
        player = sample["player"]
        target = actor_at(sample, self.target_slot)

        if self.target_slot is None:
            natural = first_natural_kind_one(sample)
            if natural is not None:
                self.target_slot = natural["slot"]
                self.target_spawn_frame = frame
                target = natural
                sample["target_actor_slot"] = self.target_slot
                sample["target_spawn_observed"] = True
        else:
            sample["target_actor_slot"] = self.target_slot
            sample["target_spawn_observed"] = False

        pre_impact_ready = False
        if (
            self.target_slot is not None
            and self.last_bomb_frame is not None
            and "pre_impact" not in self.manifest["checkpoints"]
            and target is not None
            and target["visual"] is not None
            and player is not None
            and not self.target_is_fatal(target)
        ):
            pre_impact_ready = True

        new_checkpoints: list[str] = []
        if pre_impact_ready:
            new_checkpoints.append("pre_impact")

        if self.fatal_frame is None and self.target_is_fatal(target):
            self.fatal_frame = frame
            self.fatal_score = sample["score"]
            if target is not None and target["visual"] is not None:
                self.death_x = target["visual"]["x"]
                self.death_y = target["visual"]["y"]
            new_checkpoints.append("fatal_impact")
            # The first death-state visual is the first corpse playback row.
            # It may be the same tick as the fatal transition.
            if target is not None and target["visual"] is not None:
                new_checkpoints.append("corpse_playback")

        if (
            self.fatal_frame is not None
            and "corpse_playback" not in self.manifest["checkpoints"]
            and target is not None
            and target["visual"] is not None
            and self.target_is_fatal(target)
        ):
            new_checkpoints.append("corpse_playback")

        reward = nearest_reward(sample, self.death_x, self.death_y)
        sample["reward_candidate"] = reward
        if reward is not None and self.reward_identity is None:
            self.reward_identity = (reward["slot"], reward["sprite_index"])
            self.reward_visible_score = sample["score"]
            new_checkpoints.append("reward_visible")

        if (
            self.reward_identity is not None
            and "collection" not in self.manifest["checkpoints"]
            and self.reward_visible_score is not None
        ):
            reward_still_visible = any(
                row["slot"] == self.reward_identity[0]
                and row["sprite_index"] == self.reward_identity[1]
                for row in sample["reward_candidates"]
            )
            if not reward_still_visible and sample["score"] > self.reward_visible_score:
                new_checkpoints.append("collection")

        sample["phase"] = (
            "complete"
            if "collection" in self.manifest["checkpoints"] or "collection" in new_checkpoints
            else "collect_reward"
            if self.reward_identity is not None
            else "corpse_playback"
            if self.fatal_frame is not None
            else "attack"
            if self.target_slot is not None
            else "wait_natural_spawn"
        )
        self.add_checkpoints(sample, new_checkpoints)

    def update_stuck_state(self, player: dict[str, Any] | None) -> None:
        if player is None:
            return
        if self.last_player_x == player["x"] and self.driver.held:
            self.player_still_ticks += 1
        else:
            self.player_still_ticks = 0
        self.last_player_x = player["x"]

    def maybe_jump(self, frame: int, reason: str) -> None:
        if self.player_still_ticks < self.args.stuck_ticks:
            return
        if (
            self.last_jump_frame is None
            or self.frame_elapsed(frame, self.last_jump_frame)
            >= self.args.jump_retry_ticks
        ):
            self.driver.tap(self.args.jump_key, reason)
            self.last_jump_frame = frame
            self.player_still_ticks = 0

    def move_toward(self, frame: int, player_x: int, target_x: int, reason: str) -> None:
        delta = target_x - player_x
        if abs(delta) <= self.args.parking_tolerance:
            self.driver.release_all(reason + "_arrived")
            return
        self.driver.hold_only(
            self.args.right_key if delta > 0 else self.args.left_key,
            reason,
        )
        self.maybe_jump(frame, reason + "_stuck_jump")

    def drive(self, sample: dict[str, Any]) -> None:
        frame = sample["frame"]
        player = sample["player"]
        target = actor_at(sample, self.target_slot)
        self.update_stuck_state(player)
        if player is None:
            self.driver.release_all("player_visual_missing")
            return

        if "collection" in self.manifest["checkpoints"]:
            self.driver.release_all("capture_complete")
            return

        reward = sample.get("reward_candidate")
        if self.reward_identity is not None:
            if reward is not None:
                self.move_toward(
                    frame,
                    player["x"],
                    reward["x"],
                    "collect_reward",
                )
            else:
                self.driver.release_all("reward_temporarily_missing")
            return

        if self.fatal_frame is not None:
            self.driver.release_all("wait_reward_visual")
            return

        if (
            self.fire_release_frame is not None
            and self.frame_elapsed(frame, self.fire_release_frame) >= 0x8000
        ):
            self.driver.hold_only(self.args.fire_key, "bomb_fire_hold")
            return
        if self.fire_release_frame is not None:
            self.fire_release_frame = None
            self.driver.release_all("bomb_fire_hold_complete")

        if self.target_slot is None:
            if self.bomb_attempts == 0:
                if (
                    frame >= self.args.first_bomb_frame
                    and abs(player["x"] - self.args.parking_x)
                    <= self.args.parking_tolerance
                ):
                    self.driver.release_all("pre_spawn_bomb_placement")
                    self.driver.hold_only(
                        self.args.fire_key, "kill_first_kind1"
                    )
                    self.bomb_attempts = 1
                    self.last_bomb_frame = frame
                    self.fire_release_frame = (
                        frame + self.args.fire_hold_ticks
                    ) & 0xFFFF
                    self.flee_until_frame = (
                        frame + self.args.flee_ticks
                    ) & 0xFFFF
                    self.manifest["bomb_attempts"].append(
                        {
                            "attempt": self.bomb_attempts,
                            "frame": frame,
                            "player": [player["x"], player["y"]],
                            "target": None,
                            "target_slot": None,
                            "timing": "pre_spawn",
                        }
                    )
                    atomic_write_json(self.manifest_path, self.manifest)
                    return
                # Use only normal controls to park beside the known first
                # level-1 spawn lane. Player position remains exogenous.
                self.move_toward(
                    frame,
                    player["x"],
                    self.args.parking_x,
                    "preposition_for_natural_spawn",
                )
                return
            if (
                self.flee_until_frame is not None
                and self.frame_elapsed(frame, self.flee_until_frame) >= 0x8000
            ):
                self.driver.hold_only(
                    self.args.left_key, "retreat_from_pre_spawn_bomb"
                )
            else:
                self.flee_until_frame = None
                self.driver.release_all("wait_natural_spawn_after_bomb")
            return

        if target is None or target["visual"] is None:
            self.driver.release_all("target_actor_missing")
            return

        if (
            self.flee_until_frame is not None
            and self.frame_elapsed(frame, self.flee_until_frame) >= 0x8000
        ):
            # Unsigned frame is still before the deadline.
            self.driver.hold_only(self.args.left_key, "retreat_from_bomb")
            return

        if self.flee_until_frame is not None:
            self.flee_until_frame = None

        since_bomb = self.frame_elapsed(frame, self.last_bomb_frame)
        ready_for_attempt = (
            self.bomb_attempts == 0
            or since_bomb >= self.args.bomb_retry_ticks
        )
        dx = target["visual"]["x"] - player["x"]
        dy = target["visual"]["y"] - player["y"]
        if (
            ready_for_attempt
            and self.bomb_attempts < self.args.max_bombs
            and abs(dx) <= self.args.bomb_distance
            and abs(dy) <= 24
        ):
            self.driver.release_all("bomb_placement")
            self.driver.hold_only(self.args.fire_key, "kill_kind1")
            self.bomb_attempts += 1
            self.last_bomb_frame = frame
            self.fire_release_frame = (
                frame + self.args.fire_hold_ticks
            ) & 0xFFFF
            self.flee_until_frame = (frame + self.args.flee_ticks) & 0xFFFF
            attempt = {
                "attempt": self.bomb_attempts,
                "frame": frame,
                "player": [player["x"], player["y"]],
                "target": [target["visual"]["x"], target["visual"]["y"]],
                "target_slot": self.target_slot,
                "timing": "retry_after_spawn",
            }
            self.manifest["bomb_attempts"].append(attempt)
            atomic_write_json(self.manifest_path, self.manifest)
            return

        if self.bomb_attempts >= self.args.max_bombs and ready_for_attempt:
            self.driver.release_all("bomb_attempt_limit")
            return

        self.move_toward(
            frame,
            player["x"],
            target["visual"]["x"],
            "approach_kind1",
        )

    def finalize(self, extra_reasons: list[str] | None = None) -> bool:
        try:
            self.driver.release_all("capture_finalize")
        except Exception as exc:  # Preserve the evidence even if keyup fails.
            self.manifest["incomplete_reasons"].append(
                f"input_release_failed:{type(exc).__name__}"
            )
        if extra_reasons:
            self.manifest["incomplete_reasons"].extend(extra_reasons)
        for screenshot, process in self.screenshot_processes.items():
            try:
                returncode = process.wait(
                    timeout=self.args.screenshot_timeout_seconds
                )
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                self.manifest["incomplete_reasons"].append(
                    f"checkpoint_screenshot_timeout:{screenshot}"
                )
                continue
            if returncode != 0:
                self.manifest["incomplete_reasons"].append(
                    f"checkpoint_screenshot_failed:{screenshot}:{returncode}"
                )
        missing = [
            label
            for label in REQUIRED_CHECKPOINTS
            if label not in self.manifest["checkpoints"]
        ]
        for label in missing:
            self.manifest["incomplete_reasons"].append(
                f"checkpoint_missing:{label}"
            )
        missing_screenshots = [
            label
            for label, value in self.manifest["checkpoints"].items()
            if not value.get("screenshot")
            or not (self.out_dir / value["screenshot"]).is_file()
            or (self.out_dir / value["screenshot"]).stat().st_size == 0
        ]
        for label in missing_screenshots:
            self.manifest["incomplete_reasons"].append(
                f"checkpoint_screenshot_missing:{label}"
            )
        if self.tick_gaps:
            self.manifest["incomplete_reasons"].append(
                f"nonconsecutive_tick_stream:{self.tick_gaps}"
            )
        # Stable de-duplication keeps the first, most specific failure.
        reasons = list(dict.fromkeys(self.manifest["incomplete_reasons"]))
        complete = not missing and not missing_screenshots and not reasons
        self.manifest.update(
            {
                "status": "complete" if complete else "incomplete",
                "complete": complete,
                "promotion_ready": complete,
                "original_runtime_claim": 1 if complete else 0,
                "visual_claim": 0,
                "incomplete_reasons": reasons,
                "first_frame": self.first_frame,
                "last_frame": self.last_frame,
                "tick_rows": self.tick_rows,
                "tick_gaps": self.tick_gaps,
                "target_actor_slot": self.target_slot,
                "target_spawn_frame": self.target_spawn_frame,
                "fatal_frame": self.fatal_frame,
                "fatal_score": self.fatal_score,
                "impact_equals_death": (
                    self.manifest["checkpoints"].get("fatal_impact", {}).get("frame")
                    == self.manifest["checkpoints"].get("corpse_playback", {}).get("frame")
                ),
                "reward_identity": (
                    None
                    if self.reward_identity is None
                    else {
                        "visual_slot": self.reward_identity[0],
                        "sprite_index": self.reward_identity[1],
                    }
                ),
            }
        )
        self.write_jsonl(
            {
                "type": "complete" if complete else "incomplete",
                "schema": SCHEMA,
                "promotion_ready": complete,
                "original_runtime_claim": 1 if complete else 0,
                "visual_claim": 0,
                "checkpoints": self.manifest["checkpoints"],
                "incomplete_reasons": reasons,
                "tick_rows": self.tick_rows,
                "tick_gaps": self.tick_gaps,
            }
        )
        atomic_write_json(self.manifest_path, self.manifest)
        self.jsonl.close()
        return complete

    def run(self) -> bool:
        deadline = time.monotonic() + self.args.total_timeout_seconds
        spawn_deadline = time.monotonic() + self.args.spawn_timeout_seconds
        mem_fd: int | None = None
        try:
            mem_fd = os.open(f"/proc/{self.pid}/mem", os.O_RDONLY)
            # Obtain the descriptor map from the first authoritative segment
            # read.  That read is also recorded as the first sampled tick.
            poll_frame = None
            complete = False
            failure_reasons: list[str] = []
            while time.monotonic() < deadline:
                tick_raw = os.pread(mem_fd, 2, self.ds_base + FRAME_OFFSET)
                if len(tick_raw) != 2:
                    failure_reasons.append("frame_counter_read_truncated")
                    break
                tick = struct.unpack("<H", tick_raw)[0]
                if poll_frame is not None and tick == poll_frame:
                    time.sleep(self.args.poll_seconds)
                    continue
                poll_frame = tick

                # Exactly one complete data-segment pread for this sampled tick.
                segment = os.pread(mem_fd, 0x10000, self.ds_base)
                if len(segment) != 0x10000:
                    failure_reasons.append(
                        f"data_segment_read_truncated:{len(segment)}"
                    )
                    break
                if self.descriptor is None:
                    self.initialize_descriptor(segment)
                sample = decode_segment(
                    segment, self.descriptor_to_sprite, self.previous_frame
                )
                frame = sample["frame"]
                if self.previous_frame is not None and frame == self.previous_frame:
                    # A duplicate would violate the one-row-per-tick contract.
                    # It can only arise from an emulator-memory race between
                    # the small poll and the full pread, so wait for the next.
                    continue
                if (
                    self.previous_frame is not None
                    and sample["frame_delta"] is not None
                    and sample["frame_delta"] > 1
                ):
                    self.tick_gaps += 1
                self.first_frame = frame if self.first_frame is None else self.first_frame
                self.last_frame = frame
                self.previous_frame = frame
                self.tick_rows += 1

                sample["input"] = self.driver.input_state()
                self.classify_and_checkpoint(sample)
                self.write_jsonl(sample)
                self.drive(sample)

                if (
                    self.target_slot is None
                    and time.monotonic() >= spawn_deadline
                ):
                    failure_reasons.append("timeout_waiting_natural_kind1_spawn")
                    break
                if "collection" in self.manifest["checkpoints"]:
                    complete = True
                    break
                if (
                    self.bomb_attempts >= self.args.max_bombs
                    and self.last_bomb_frame is not None
                    and self.frame_elapsed(frame, self.last_bomb_frame)
                    >= self.args.bomb_retry_ticks
                    and self.fatal_frame is None
                ):
                    failure_reasons.append("bomb_attempt_limit_without_fatal_impact")
                    break

            if not complete and not failure_reasons:
                if self.target_slot is None:
                    failure_reasons.append("timeout_waiting_natural_kind1_spawn")
                elif self.fatal_frame is None:
                    failure_reasons.append("timeout_waiting_fatal_impact")
                elif self.reward_identity is None:
                    failure_reasons.append("timeout_waiting_reward_visible")
                else:
                    failure_reasons.append("timeout_waiting_reward_collection")
            return self.finalize(failure_reasons)
        except Exception as exc:
            reason = f"capture_exception:{type(exc).__name__}:{exc}"
            return self.finalize([reason])
        finally:
            if mem_fd is not None:
                os.close(mem_fd)


def find_dosbox_window(timeout: float = 8.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            windows = subprocess.check_output(
                ["xdotool", "search", "--name", "DOSBox"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2.0,
            ).split()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            windows = []
        if windows:
            return windows[-1]
        time.sleep(0.1)
    raise CaptureIncomplete("dosbox_window_not_found")


def run_live(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    out_dir = (
        Path(args.out_dir).resolve()
        if args.out_dir
        else run_dir / "monster_sprite_consumption_capture"
    )
    validate_temp_run_dir(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_manifest = out_dir / "monster_sprite_consumption_manifest.json"
    bootstrap: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "starting",
        "complete": False,
        "promotion_ready": False,
        "original_runtime_claim": 0,
        "visual_claim": 0,
        "popup_windows": 0,
        "xvfb_isolated": True,
        "run_dir": str(run_dir),
        "out_dir": str(out_dir),
        "incomplete_reasons": [],
    }
    atomic_write_json(bootstrap_manifest, bootstrap)

    result: dict[str, Any] = {
        "hook_ran": False,
        "complete": False,
        "session": None,
    }
    original_snapshot = seeder.write_runtime_state_snapshot

    def capture_hook(
        hook_run_dir: Path,
        pid: int,
        base: int,
        state: dict[str, int],
        phase: str,
    ) -> Path:
        if phase == "pre_capture" and state["level"] == 1 and not result["hook_ran"]:
            result["hook_ran"] = True
            window = find_dosbox_window()
            session = CaptureSession(
                args,
                Path(hook_run_dir).resolve(),
                out_dir,
                pid,
                base,
                window,
            )
            result["session"] = session
            print(
                "monster_sprite_consumption_capture=start"
                f" level={state['level']}"
                f" pid={pid}"
                f" runtime_ds=0x{seeder.RUNTIME_DS:04x}"
                f" popup_windows=0"
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
        if result["session"] is None:
            bootstrap.update(
                {
                    "status": "incomplete",
                    "incomplete_reasons": [
                        f"seeder_exception:{type(exc).__name__}:{exc}"
                    ],
                }
            )
            atomic_write_json(bootstrap_manifest, bootstrap)
        print(
            "monster_sprite_consumption_capture=incomplete"
            f" reason=seeder_exception:{type(exc).__name__}"
            f" manifest={bootstrap_manifest}",
            file=sys.stderr,
            flush=True,
        )
        return 2
    finally:
        sys.argv = old_argv
        seeder.write_runtime_state_snapshot = original_snapshot

    if not result["hook_ran"]:
        bootstrap.update(
            {
                "status": "incomplete",
                "incomplete_reasons": ["level1_capture_hook_not_reached"],
            }
        )
        atomic_write_json(bootstrap_manifest, bootstrap)
        print(
            "monster_sprite_consumption_capture=incomplete"
            " reason=level1_capture_hook_not_reached"
            f" manifest={bootstrap_manifest}",
            file=sys.stderr,
            flush=True,
        )
        return 2
    session: CaptureSession = result["session"]
    if not result["complete"]:
        print(
            "monster_sprite_consumption_capture=incomplete"
            f" ticks={session.tick_rows}"
            f" checkpoints={len(session.manifest['checkpoints'])}"
            f" reasons={','.join(session.manifest['incomplete_reasons'])}"
            f" jsonl={session.jsonl_path}"
            f" manifest={session.manifest_path}",
            file=sys.stderr,
            flush=True,
        )
        return 2
    print(
        "monster_sprite_consumption_capture=ok"
        f" ticks={session.tick_rows}"
        f" tick_gaps={session.tick_gaps}"
        f" checkpoints={len(session.manifest['checkpoints'])}"
        f" bombs={session.bomb_attempts}"
        " original_runtime_claim=1 visual_claim=0"
        f" jsonl={session.jsonl_path}"
        f" manifest={session.manifest_path}",
        flush=True,
    )
    return seeder_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="static LEZAC.EXE/BOMOMIMK.SPR check; no DOSBox, Xvfb, or writes",
    )
    parser.add_argument(
        "--exe",
        type=Path,
        default=REPO_ROOT / "LEZAC.EXE",
        help="LEZAC.EXE for --self-check",
    )
    parser.add_argument(
        "--sprite-file",
        type=Path,
        default=REPO_ROOT / "BOMOMIMK.SPR",
        help="BOMOMIMK.SPR for --self-check",
    )
    parser.add_argument(
        "--run-dir",
        help="caller-created temporary directory containing copied original assets",
    )
    parser.add_argument(
        "--out-dir",
        help="capture output directory (default: <run-dir>/monster_sprite_consumption_capture)",
    )
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")

    parser.add_argument("--startup-seconds", type=float, default=6.0)
    parser.add_argument("--intro-seconds", type=float, default=3.0)
    parser.add_argument("--level-start-seconds", type=float, default=1.0)
    parser.add_argument("--spawn-timeout-seconds", type=float, default=25.0)
    parser.add_argument("--total-timeout-seconds", type=float, default=90.0)
    parser.add_argument("--screenshot-timeout-seconds", type=float, default=3.0)
    parser.add_argument("--poll-seconds", type=float, default=0.0005)

    parser.add_argument("--left-key", default="z")
    parser.add_argument("--right-key", default="x")
    parser.add_argument("--jump-key", default="m")
    parser.add_argument("--fire-key", default="n")
    parser.add_argument("--parking-x", type=int, default=328)
    parser.add_argument("--parking-tolerance", type=int, default=5)
    parser.add_argument("--first-bomb-frame", type=int, default=218)
    parser.add_argument("--fire-hold-ticks", type=int, default=4)
    parser.add_argument("--bomb-distance", type=int, default=24)
    parser.add_argument("--flee-ticks", type=int, default=48)
    parser.add_argument("--bomb-retry-ticks", type=int, default=120)
    parser.add_argument("--max-bombs", type=int, default=6)
    parser.add_argument("--stuck-ticks", type=int, default=20)
    parser.add_argument("--jump-retry-ticks", type=int, default=30)
    return parser


def validate_numeric_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    positive = {
        "--spawn-timeout-seconds": args.spawn_timeout_seconds,
        "--total-timeout-seconds": args.total_timeout_seconds,
        "--screenshot-timeout-seconds": args.screenshot_timeout_seconds,
        "--poll-seconds": args.poll_seconds,
        "--parking-tolerance": args.parking_tolerance,
        "--first-bomb-frame": args.first_bomb_frame,
        "--fire-hold-ticks": args.fire_hold_ticks,
        "--bomb-distance": args.bomb_distance,
        "--flee-ticks": args.flee_ticks,
        "--bomb-retry-ticks": args.bomb_retry_ticks,
        "--max-bombs": args.max_bombs,
        "--stuck-ticks": args.stuck_ticks,
        "--jump-retry-ticks": args.jump_retry_ticks,
    }
    for name, value in positive.items():
        if value <= 0:
            parser.error(f"{name} must be positive")
    if args.total_timeout_seconds <= args.spawn_timeout_seconds:
        parser.error("--total-timeout-seconds must exceed --spawn-timeout-seconds")


def main(argv: list[str] | None = None) -> int:
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(actual_argv)
    if args.self_check:
        return self_check(args.exe.resolve(), args.sprite_file.resolve())
    validate_numeric_args(parser, args)
    if not args.run_dir:
        parser.error("--run-dir is required for live capture")
    if not (args.approve_procmem and args.approve_runtime_instrumentation):
        parser.error(
            "live capture requires --approve-procmem "
            "and --approve-runtime-instrumentation"
        )
    enter_private_xvfb(actual_argv)
    for executable in ("dosbox", "xdotool", "import"):
        if not command_exists(executable):
            raise RuntimeError(f"missing required live-capture command: {executable}")
    return run_live(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(
            "monster_sprite_consumption_capture=error"
            f" reason={type(error).__name__}:{error}",
            file=sys.stderr,
        )
        raise SystemExit(2)
