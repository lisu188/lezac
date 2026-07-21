#!/usr/bin/env python3
"""Lock the recovered 1000:6924 launch-pad path and its runtime table row."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


IMAGE_SEGMENT = "1000"
INPUT_IRQ_KEYS = 0x10A5
UP_DOWN_CANCEL = 0x68C5
DOWN_GATE = 0x68E2
PORTAL_TILE_GATE = 0x68EC
PORTAL_HELPER_CALL = 0x690C
PORTAL_HELPER = 0x5999
LAUNCH_TILE_GATE = 0x6912
LAUNCH_SOUND_CALL = 0x692F
SOUND_LATCH = 0x165A
LAUNCH_ACTOR_CALL = 0x694D
ACTOR_CONSTRUCTOR = 0x2F9F
ACTOR_ARGUMENT_STORES = 0x3043
MODE5_TIMER_GATE = 0x65A2

EXPECTED_INPUT_IRQ_BYTES = bytes.fromhex(
    "3c2c75048826791b"
    "3c2d750488267a1b"
    "3c3275048826781b"
    "3c31750488267b1b"
    "3c2e750488267c1b"
)
EXPECTED_UP_DOWN_BYTES = bytes.fromhex(
    "a0821b30e48bd0a0861b30e403c23d0200750a"
    "c606861b00c606821b00"
)
EXPECTED_DOWN_GATE_BYTES = bytes.fromhex("803e861b017403e97201")
EXPECTED_PORTAL_GATE_BYTES = bytes.fromhex(
    "803e552045751fa104c28bf0d1e001f00346d640d1e0"
    "c43e126603f826ff3555e88af0e94c01"
)
EXPECTED_LAUNCH_BYTES = bytes.fromhex(
    "803e552027754e807ede007548c746f230f8"
    "c70674203500c6069f7905e828ad"
    "8b46d4050400508b46d2050d00506a006838ff"
    "6a5b6a0b6a056a05e84fc6"
)
EXPECTED_ARGUMENT_STORE_BYTES = bytes.fromhex(
    "8a4608c47efc268805"
    "8a4606c47efc26884502"
    "8a4604c47efc26884515"
    "837e0a1f741c8b7e0ac1e7028a8523c3"
)
EXPECTED_MODE5_TIMER_BYTES = bytes.fromhex(
    "807ecf057532a1c278250100c47e0426284502"
    "c47e0426807d02007518"
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def image_base(data: bytes) -> int:
    if data[:2] != b"MZ":
        raise RuntimeError("LEZAC.EXE is not an MZ executable")
    return (data[8] | (data[9] << 8)) * 16


def code_bytes(data: bytes, base: int, offset: int, length: int) -> bytes:
    start = base + offset
    end = start + length
    if start < base or end > len(data):
        raise RuntimeError(f"offset {fmt(offset)} maps outside LEZAC.EXE")
    return data[start:end]


def require_bytes(
    data: bytes, base: int, offset: int, expected: bytes, label: str
) -> None:
    observed = code_bytes(data, base, offset, len(expected))
    if observed != expected:
        raise RuntimeError(
            f"{label} at {fmt(offset)} expected {expected.hex()} got {observed.hex()}"
        )


def rel16_target(data: bytes, base: int, offset: int) -> int:
    encoded = code_bytes(data, base, offset, 3)
    if encoded[0] not in (0xE8, 0xE9):
        raise RuntimeError(f"{fmt(offset)} is not a near call/jump")
    displacement = encoded[1] | (encoded[2] << 8)
    if displacement >= 0x8000:
        displacement -= 0x10000
    return (offset + 3 + displacement) & 0xFFFF


def require_target(
    data: bytes, base: int, offset: int, expected: int, label: str
) -> None:
    observed = rel16_target(data, base, offset)
    if observed != expected:
        raise RuntimeError(
            f"{label} at {fmt(offset)} targets {fmt(observed)} instead of "
            f"{fmt(expected)}"
        )


def fmt(offset: int) -> str:
    return f"{IMAGE_SEGMENT}:{offset:04X}"


def parse_fixture(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise RuntimeError(f"malformed fixture line: {raw_line}")
        fields[key] = value
    return fields


def require_field(fields: dict[str, str], key: str, expected: str) -> None:
    observed = fields.get(key)
    if observed != expected:
        raise RuntimeError(f"fixture {key} expected {expected!r} got {observed!r}")


def require_text(path: Path, needle: str) -> None:
    if needle not in path.read_text(encoding="utf-8"):
        raise RuntimeError(f"{path.name} is missing {needle!r}")


def check_level_tiles(root: Path) -> tuple[int, int, int]:
    bank = json.loads((root / "src" / "LIVELS.SCH.json").read_text(encoding="utf-8"))
    counts: list[int] = []
    for level_index, level in enumerate(bank["levels"], 1):
        rows = [[int(value, 16) for value in row.split()]
                for row in level["tiles_rows_hex"]]
        count = 0
        for y, row in enumerate(rows):
            for x, tile in enumerate(row):
                if tile != 0x27:
                    continue
                count += 1
                if x == 0 or x + 1 >= len(row) or row[x - 1] != 0x25 or row[x + 1] != 0x28:
                    raise RuntimeError(
                        f"level {level_index} launch tile at {x},{y} lacks 25/27/28 triplet"
                    )
        counts.append(count)
    if counts != [0, 0, 0, 0, 0, 4, 3]:
        raise RuntimeError(f"unexpected launch-pad tile counts: {counts}")
    return sum(counts), counts[5], counts[6]


def check_tile_art(root: Path) -> None:
    bank = json.loads((root / "src" / "CARO.CAR.json").read_text(encoding="utf-8"))
    tiles = bank["tiles"]
    if len(tiles) != 132 or tiles[0x27]["index"] != 0x27 or tiles[0x28]["index"] != 0x28:
        raise RuntimeError("unexpected CARO.CAR launch-pad tile metadata")
    if tiles[0x27]["rows_hex"] == tiles[0x28]["rows_hex"]:
        raise RuntimeError("launch-pad halves unexpectedly match")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the static and runtime evidence for the launch-pad path."
    )
    parser.add_argument("repo_root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()
    root = args.repo_root.resolve()

    executable = (root / "LEZAC.EXE").read_bytes()
    base = image_base(executable)
    require_bytes(executable, base, INPUT_IRQ_KEYS, EXPECTED_INPUT_IRQ_BYTES,
                  "Z/X/M/N/C input IRQ mapping")
    require_bytes(executable, base, UP_DOWN_CANCEL, EXPECTED_UP_DOWN_BYTES,
                  "Up+Down cancellation")
    require_bytes(executable, base, DOWN_GATE, EXPECTED_DOWN_GATE_BYTES,
                  "Down input gate")
    require_bytes(executable, base, PORTAL_TILE_GATE, EXPECTED_PORTAL_GATE_BYTES,
                  "portal tile branch")
    require_target(executable, base, PORTAL_HELPER_CALL, PORTAL_HELPER,
                   "portal helper call")
    require_bytes(executable, base, LAUNCH_TILE_GATE, EXPECTED_LAUNCH_BYTES,
                  "launch-pad branch")
    require_target(executable, base, LAUNCH_SOUND_CALL, SOUND_LATCH,
                   "launch-pad sound latch call")
    require_target(executable, base, LAUNCH_ACTOR_CALL, ACTOR_CONSTRUCTOR,
                   "launch-pad actor constructor call")
    require_bytes(executable, base, ACTOR_ARGUMENT_STORES,
                  EXPECTED_ARGUMENT_STORE_BYTES, "actor argument stores")
    require_bytes(executable, base, MODE5_TIMER_GATE, EXPECTED_MODE5_TIMER_BYTES,
                  "mode-5 timer gate")

    fixture = parse_fixture(
        root / "tests" / "fixtures" / "dosbox" /
        "launch_pad_visual_table_original.txt"
    )
    for key, expected in {
        "capture": "launch_pad_visual_table",
        "source": "dosbox-debug-process-memory",
        "temp_copy": "1",
        "visual_claim": "0",
        "runtime_cs": "01ED",
        "runtime_ds": "0C8F",
        "table_base": "0xC322",
        "visual_frame": "0x5B",
        "frame_row_address": "0xC48E",
        "frame_row": "00 00 00 00",
        "sprite_bank": "BOMOMIMK.SPR",
        "sprite_count": "91",
        "sentinel_after_last_sprite": "1",
        "probe_freeze_observed": "1",
        "semantic_scope": "table_row_only",
    }.items():
        require_field(fixture, key, expected)

    sprites = json.loads(
        (root / "src" / "BOMOMIMK.SPR.json").read_text(encoding="utf-8")
    )
    if len(sprites["sprites"]) != 91:
        raise RuntimeError("BOMOMIMK.SPR no longer contains 91 sprites")

    total, level6, level7 = check_level_tiles(root)
    check_tile_art(root)

    source = root / "src" / "app" / "app.cpp"
    for snippet in [
        "constexpr uint8_t kLaunchPadTile = 0x27;",
        "constexpr uint16_t kLaunchPadSoundCursor = 0x0035;",
        "constexpr uint8_t kLaunchPadSoundPriority = 5;",
        "bool activateLaunchPad(Player& player, bool down)",
        "void updateLaunchPadMarkers()",
        "bool requestLaunchPadSound()",
        "void debugAutoplayerLaunchPadRoute(const std::string& scenario)",
        'scenario == "launch_pad_route"',
        '{0x6924, "launch_pad"}',
    ]:
        require_text(source, snippet)

    cmake = root / "CMakeLists.txt"
    require_text(cmake, "add_test(NAME sound_launch_pad_context")
    require_text(cmake, "add_test(NAME autoplayer_launch_pad_route_dummy")
    require_text(cmake, "add_test(NAME frame_sequence_capture_launch_pad_route_dummy")

    docs = [
        root / "README_RECONSTRUCTION.md",
        root / "RECOVERY_STATUS.md",
        root / "docs" / "GHIDRA_NOTES.md",
        root / "docs" / "recovery" /
        "sound_launch_pad_process_memory_2026-07-16.md",
    ]
    for path in docs:
        require_text(path, "1000:6924")
        require_text(path, "0x0035")
        require_text(path, "launch_pad_route")

    print(
        "sound_launch_pad_context=ok "
        f"image_base=0x{base:04x} input_irq={fmt(INPUT_IRQ_KEYS)} "
        f"down_gate={fmt(DOWN_GATE)} portal_gate={fmt(PORTAL_TILE_GATE)} "
        f"launch_gate={fmt(LAUNCH_TILE_GATE)} sound=0x0035/p5 "
        "launch_velocity=-2000 normal_jump_velocity=-848 "
        "marker=frame0x5b/kind0x0b/mode5/timer5/vy-200 "
        "visual_row=DS:C48E:00000000 sentinel=1 "
        f"launch_tiles={total} level6={level6} level7={level7} docs=4"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
