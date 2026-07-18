#!/usr/bin/env python3
"""Verify the dormant actor-mode-6 sound path and its shipped data sources."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


IMAGE_SEGMENT = "1000"
ACTOR_CONSTRUCTOR = 0x2F9F
ACTOR_MODE_STORE = 0x3056
ACTOR_MODE_LOAD = 0x615A
ACTOR_MODE6_GATE = 0x654E
CONTACT_SCANNER_ENTRY = 0x5CB0
CONTACT_SCANNER_CALL = 0x6555
STATE6_SOUND_PREDICATE = 0x5E59
SOUND_LATCH = 0x165A

CONSTRUCTOR_CALLS = [
    (0x55D2, 5),
    (0x5A3E, 5),
    (0x694D, 5),
    (0x6C5B, 2),
    (0x6DDA, 5),
    (0x7750, 5),
    (0x7B28, None),
]

EXPECTED_DIRECT_MODE_WRITES = [
    (0x3123, 2),
    (0x5C44, 2),
    (0x5C64, 2),
    (0x6414, 5),
    (0x64B5, 5),
    (0x74CF, 2),
    (0x7610, 5),
    (0x7E85, 0),
    (0x7E8F, 1),
]

EXPECTED_SPAWNER_MODE_COUNTS = Counter({3: 9, 4: 6})
STATE6_SOUND_BYTES = bytes.fromhex(
    "a1c27831d2b91d00f7f19209c07403e98900"
    "6a649aa81320093d46007618a1c27825010009c0"
    "750ec70674206900c6069f7904e8cbb7"
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def fmt(offset: int) -> str:
    return f"{IMAGE_SEGMENT}:{offset:04X}"


def image_base(data: bytes) -> int:
    if data[:2] != b"MZ":
        raise RuntimeError("LEZAC.EXE is not an MZ executable")
    base = int.from_bytes(data[8:10], "little") * 16
    if base >= len(data):
        raise RuntimeError("LEZAC.EXE MZ header extends past the file")
    return base


def code_bytes(data: bytes, base: int, offset: int, length: int) -> bytes:
    start = base + offset
    end = start + length
    if offset < 0 or start < base or end > len(data):
        raise RuntimeError(f"{fmt(offset)} maps outside LEZAC.EXE")
    return data[start:end]


def require_bytes(
    data: bytes, base: int, offset: int, expected: bytes, label: str
) -> None:
    observed = code_bytes(data, base, offset, len(expected))
    if observed != expected:
        raise RuntimeError(
            f"{label} at {fmt(offset)} expected {expected.hex()} got "
            f"{observed.hex()}"
        )


def rel8_target(data: bytes, base: int, offset: int) -> int:
    raw = code_bytes(data, base, offset + 1, 1)[0]
    displacement = raw - 0x100 if raw >= 0x80 else raw
    return (offset + 2 + displacement) & 0xFFFF


def rel16_target(data: bytes, base: int, offset: int) -> int:
    displacement = int.from_bytes(
        code_bytes(data, base, offset + 1, 2), "little", signed=True
    )
    return (offset + 3 + displacement) & 0xFFFF


def find_pattern(data: bytes, base: int, pattern: bytes) -> list[int]:
    image = data[base:]
    hits: list[int] = []
    start = 0
    while True:
        hit = image.find(pattern, start)
        if hit < 0:
            return hits
        hits.append(hit)
        start = hit + 1


def scan_near_calls(data: bytes, base: int, target: int) -> list[int]:
    image_length = min(0x10000, len(data) - base)
    hits: list[int] = []
    for offset in range(image_length - 2):
        if code_bytes(data, base, offset, 1) != b"\xe8":
            continue
        if rel16_target(data, base, offset) == target:
            hits.append(offset)
    return hits


def take_u16(data: bytes, offset: int, label: str) -> tuple[int, int]:
    if offset + 2 > len(data):
        raise RuntimeError(f"LIVELS.SCH truncated while reading {label}")
    return int.from_bytes(data[offset : offset + 2], "little"), offset + 2


def skip_bytes(data: bytes, offset: int, length: int, label: str) -> int:
    if length < 0 or offset + length > len(data):
        raise RuntimeError(f"LIVELS.SCH truncated while skipping {label}")
    return offset + length


def take_fixed_records(
    data: bytes, offset: int, width: int, label: str
) -> tuple[list[bytes], int]:
    if offset >= len(data):
        raise RuntimeError(f"LIVELS.SCH truncated before {label} count")
    count = data[offset]
    offset += 1
    records: list[bytes] = []
    for index in range(count):
        end = offset + width
        if end > len(data):
            raise RuntimeError(
                f"LIVELS.SCH truncated in {label} record {index + 1}"
            )
        records.append(data[offset:end])
        offset = end
    return records, offset


def raw_spawner_modes(data: bytes) -> list[list[int]]:
    offset = 0
    levels: list[list[int]] = []
    while offset < len(data):
        width, offset = take_u16(data, offset, "level width")
        height, offset = take_u16(data, offset, "level height")
        if width == 0 or height == 0:
            raise RuntimeError("LIVELS.SCH contains a zero-sized level")
        offset = skip_bytes(data, offset, 4, "level objective fields")
        tile_length, offset = take_u16(data, offset, "tile RLE length")
        offset = skip_bytes(data, offset, tile_length, "tile RLE payload")
        word_length, offset = take_u16(data, offset, "word RLE length")
        offset = skip_bytes(data, offset, word_length, "word RLE payload")
        offset = skip_bytes(data, offset, 4, "level scalar tail")
        spawners, offset = take_fixed_records(data, offset, 30, "spawner")
        _, offset = take_fixed_records(data, offset, 7, "portal")
        _, offset = take_fixed_records(data, offset, 14, "trigger")
        levels.append([record[26] for record in spawners])
    if offset != len(data):
        raise RuntimeError("LIVELS.SCH parser did not consume the complete file")
    return levels


def json_spawner_modes(path: Path) -> list[list[int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    levels = payload.get("levels")
    if not isinstance(levels, list):
        raise RuntimeError("LIVELS.SCH.json has no levels array")
    result: list[list[int]] = []
    for index, level in enumerate(levels):
        if not isinstance(level, dict) or not isinstance(
            level.get("monsterSpawners"), list
        ):
            raise RuntimeError(
                f"LIVELS.SCH.json level {index + 1} has no monsterSpawners"
            )
        result.append(
            [int(spawner["spawnArg"]) for spawner in level["monsterSpawners"]]
        )
    return result


def counter_text(values: Counter[int]) -> str:
    return ",".join(f"{value}:{values[value]}" for value in sorted(values))


def require_text(path: Path, needle: str) -> None:
    if needle not in path.read_text(encoding="utf-8"):
        raise RuntimeError(f"{path.name} is missing {needle!r}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the actor-mode-6 contact-scanner sound context."
    )
    parser.add_argument(
        "repo_root", nargs="?", type=Path, default=default_repo_root()
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    executable = (root / "LEZAC.EXE").read_bytes()
    base = image_base(executable)

    require_bytes(
        executable,
        base,
        ACTOR_MODE_STORE,
        bytes.fromhex("8a4604c47efc26884515"),
        "constructor mode store",
    )
    require_bytes(
        executable,
        base,
        ACTOR_MODE_LOAD,
        bytes.fromhex("c47e04268a45158846cf"),
        "actor-update mode load",
    )
    require_bytes(
        executable,
        base,
        ACTOR_MODE6_GATE,
        bytes.fromhex("807ecf06750755e858f7e98a0e"),
        "mode-6 scanner gate",
    )
    require_bytes(
        executable,
        base,
        STATE6_SOUND_PREDICATE,
        STATE6_SOUND_BYTES,
        "mode-6 sound predicate",
    )

    if rel8_target(executable, base, 0x5E66) != 0x5E6B:
        raise RuntimeError("modulus-zero branch no longer reaches random test")
    if rel16_target(executable, base, 0x5E68) != 0x5EF4:
        raise RuntimeError("modulus rejection no longer skips the sound block")
    if rel8_target(executable, base, 0x5E75) != 0x5E8F:
        raise RuntimeError("random threshold branch no longer skips the sound block")
    if rel8_target(executable, base, 0x5E7F) != 0x5E8F:
        raise RuntimeError("parity branch no longer skips the sound block")
    if rel16_target(executable, base, 0x5E8C) != SOUND_LATCH:
        raise RuntimeError("mode-6 sound request no longer calls the priority latch")
    if rel16_target(executable, base, CONTACT_SCANNER_CALL) != CONTACT_SCANNER_ENTRY:
        raise RuntimeError("mode-6 gate no longer calls the contact scanner")

    expected_calls = [offset for offset, _ in CONSTRUCTOR_CALLS]
    calls = scan_near_calls(executable, base, ACTOR_CONSTRUCTOR)
    if calls != expected_calls:
        raise RuntimeError(
            "unexpected actor constructor callsites: "
            + ",".join(fmt(offset) for offset in calls)
        )
    for callsite, mode in CONSTRUCTOR_CALLS[:-1]:
        expected = bytes((0x6A, int(mode)))
        require_bytes(
            executable,
            base,
            callsite - 2,
            expected,
            "immediate constructor mode",
        )
    require_bytes(
        executable,
        base,
        0x7B20,
        bytes.fromhex("c47efc268a451a50e874b4"),
        "spawner-sourced constructor mode",
    )

    dynamic_mode_stores = find_pattern(executable, base, bytes.fromhex("26884515"))
    if dynamic_mode_stores != [0x305C]:
        raise RuntimeError(
            "unexpected dynamic es:[di+15h] stores: "
            + ",".join(fmt(offset) for offset in dynamic_mode_stores)
        )
    immediate_store_offsets = find_pattern(
        executable, base, bytes.fromhex("26c64515")
    )
    direct_mode_writes = [
        (offset, code_bytes(executable, base, offset + 4, 1)[0])
        for offset in immediate_store_offsets
    ]
    if direct_mode_writes != EXPECTED_DIRECT_MODE_WRITES:
        raise RuntimeError(
            "unexpected direct actor mode writes: "
            + ",".join(
                f"{fmt(offset)}={mode}" for offset, mode in direct_mode_writes
            )
        )

    raw_modes = raw_spawner_modes((root / "LIVELS.SCH").read_bytes())
    exported_modes = json_spawner_modes(root / "src" / "LIVELS.SCH.json")
    if raw_modes != exported_modes:
        raise RuntimeError("raw and exported level spawner mode lists differ")
    mode_counts = Counter(mode for level in raw_modes for mode in level)
    if mode_counts != EXPECTED_SPAWNER_MODE_COUNTS:
        raise RuntimeError(
            "unexpected shipped spawner modes: " + counter_text(mode_counts)
        )

    blocker = "shipped_actor_modes_exclude_6"
    note_name = "sound_state6_process_memory_attempt_2026-07-16.md"
    require_text(root / "src" / "main.cpp", blocker)
    require_text(root / "CMakeLists.txt", "add_test(NAME sound_state6_context")
    for path in [
        root / "README_RECONSTRUCTION.md",
        root / "RECOVERY_STATUS.md",
        root / "docs" / "GHIDRA_NOTES.md",
        root / "docs" / "recovery" / note_name,
    ]:
        require_text(path, blocker)

    immediate_modes = Counter(
        int(mode) for _, mode in CONSTRUCTOR_CALLS if mode is not None
    )
    direct_modes = Counter(mode for _, mode in direct_mode_writes)
    print(
        "sound_state6_context=ok "
        f"image_base=0x{base:04x} "
        f"constructor={fmt(ACTOR_CONSTRUCTOR)} "
        f"constructor_calls={len(calls)} "
        f"constructor_immediate_modes={counter_text(immediate_modes)} "
        "dynamic_mode_source=spawner+0x1a "
        f"shipped_levels={len(raw_modes)} "
        f"shipped_spawners={sum(mode_counts.values())} "
        f"shipped_modes={counter_text(mode_counts)} "
        f"state6_spawners={mode_counts[6]} "
        f"direct_mode_writes={counter_text(direct_modes)} "
        f"gate={fmt(ACTOR_MODE6_GATE)} "
        f"scanner={fmt(CONTACT_SCANNER_ENTRY)} "
        "tick=DS:78C2 modulus=29 equivalent_period=58 "
        "random_bound=100 random_threshold_gt=70 parity=even "
        "cursor=0x0069 priority=4 "
        f"latch={fmt(SOUND_LATCH)} "
        f"natural_route_status=dormant blocker={blocker} "
        "seeded_route_required=1 docs=4"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
