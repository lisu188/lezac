#!/usr/bin/env python3
"""Check visual-table oracle fixtures and test wiring."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


REQUIRED_OFFSETS = [0x3108, 0x6053, 0x6148, 0x7C89, 0x7DDF]
FRAME_ENTRY_BASE = 0xC322

EXPECTED_OUTCOMES = {
    "visual_table_oracle_synthetic.txt": "ok",
    "visual_table_oracle_bad_segment.txt": (
        "breakpoint_segment_mismatch expected=0x1a2b actual=0xffff"
    ),
    "visual_table_oracle_missing_row_byte.txt": "missing_byte address=c4ed",
    "visual_table_oracle_sprite_without_row.txt": "visual_row_missing_for_sprite",
    "visual_table_oracle_bad_row_byte3_sprite.txt": (
        "sprite_index_row3_mismatch row3=67 sprite_index=66"
    ),
}
ORIGINAL_PREFIX = "visual_table_oracle_original"


def expected_outcome_for(name: str) -> str | None:
    if name in EXPECTED_OUTCOMES:
        return EXPECTED_OUTCOMES[name]
    if name.startswith(ORIGINAL_PREFIX) and name.endswith(".txt"):
        return "ok"
    return None


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_hex16(token: str, field: str) -> int:
    value = token.strip()
    if value.lower().startswith("0x"):
        value = value[2:]
    if not re.fullmatch(r"[0-9a-fA-F]{1,4}", value):
        raise RuntimeError(f"bad hex16 field={field} token={token}")
    return int(value, 16)


def parse_hex_byte(token: str, field: str) -> int:
    value = token.strip()
    if value.lower().startswith("0x"):
        value = value[2:]
    if not re.fullmatch(r"[0-9a-fA-F]{2}", value):
        raise RuntimeError(f"bad hex byte field={field} token={token}")
    return int(value, 16)


def parse_int(token: str, field: str) -> int:
    try:
        return int(token, 0)
    except ValueError as exc:
        raise RuntimeError(f"bad int field={field} token={token}") from exc


def parse_record(line: str) -> tuple[str, dict[str, str]]:
    record, _, rest = line.partition(" ")
    if not rest:
        raise RuntimeError(f"record without fields: {line}")
    fields: dict[str, str] = {}
    for token in rest.split():
        key, separator, value = token.partition("=")
        if not separator or not key or not value:
            raise RuntimeError(f"bad record field token={token}")
        fields[key] = value
    return record, fields


def require_field(fields: dict[str, str], name: str, record: str) -> str:
    if name not in fields:
        raise RuntimeError(f"{record}_{name}_missing")
    return fields[name]


def parse_row_bytes(value: str, field: str) -> list[int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        return []
    return [parse_hex_byte(part, field) for part in parts]


def parse_fixture(
    path: Path,
) -> tuple[
    dict[str, str],
    dict[str, list[dict[str, str]]],
    list[tuple[int, int, int, int]],
    dict[int, int],
]:
    values: dict[str, str] = {}
    records: dict[str, list[dict[str, str]]] = {}
    breaks: list[tuple[int, int, int, int]] = []
    memory: dict[int, int] = {}
    key_re = re.compile(r"^([A-Za-z0-9_]+)=(.*)$")
    break_re = re.compile(
        r"^break\s+ghidra=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\s+"
        r"runtime=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\s+label=([^\s]+).*$"
    )
    row_re = re.compile(r"^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\s+(.+)$")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("dump "):
            continue
        match = key_re.match(line)
        if match:
            values[match.group(1)] = match.group(2).strip()
            continue
        match = break_re.match(line)
        if match:
            breaks.append(
                (
                    parse_hex16(match.group(1), "ghidra_segment"),
                    parse_hex16(match.group(2), "ghidra_offset"),
                    parse_hex16(match.group(3), "runtime_segment"),
                    parse_hex16(match.group(4), "runtime_offset"),
                )
            )
            continue
        if line.startswith(("actor ", "visual ", "effect_before ", "effect_after ")):
            record, fields = parse_record(line)
            records.setdefault(record, []).append(fields)
            continue
        match = row_re.match(line)
        if match:
            segment = parse_hex16(match.group(1), "row_segment")
            if "runtime_ds" in values and segment != parse_hex16(
                values["runtime_ds"], "runtime_ds"
            ):
                memory[-1] = -1
                continue
            address = parse_hex16(match.group(2), "row_address")
            for index, byte_text in enumerate(match.group(3).split()):
                memory[address + index] = parse_hex_byte(byte_text, "dump")
            continue
    return values, records, breaks, memory


def infer_outcome(
    values: dict[str, str],
    records: dict[str, list[dict[str, str]]],
    breaks: list[tuple[int, int, int, int]],
    memory: dict[int, int],
) -> str:
    if "runtime_cs" not in values:
        return "runtime_cs_missing"
    if "runtime_ds" not in values:
        return "runtime_ds_missing"
    if "scenario" not in values:
        return "scenario_missing"
    if values.get("visual_claim", "0") != "0":
        return "visual_claim_not_supported"
    runtime_cs = parse_hex16(values["runtime_cs"], "runtime_cs")
    for ghidra_segment, ghidra_offset, runtime_segment, runtime_offset in breaks:
        if ghidra_segment != 0x1000:
            return (
                "breakpoint_ghidra_segment expected=0x1000 actual="
                f"0x{ghidra_segment:04x}"
            )
        if runtime_segment != runtime_cs:
            return (
                "breakpoint_segment_mismatch expected="
                f"0x{runtime_cs:04x} actual=0x{runtime_segment:04x}"
            )
        if runtime_offset != ghidra_offset:
            return (
                "breakpoint_offset_mismatch expected="
                f"{ghidra_offset:04x} actual={runtime_offset:04x}"
            )
    if values["scenario"] != "state2_death_table_consumption":
        return f"unknown_scenario value={values['scenario']}"
    seen_offsets = {ghidra_offset for _, ghidra_offset, _, _ in breaks}
    for offset in REQUIRED_OFFSETS:
        if offset not in seen_offsets:
            return f"missing_breakpoint offset={offset:04x}"
    if "actor" not in records:
        return "actor_missing"
    if "visual" not in records:
        return "visual_missing"
    if "effect_before" not in records:
        return "effect_before_missing"
    if "effect_after" not in records:
        return "effect_after_missing"

    visual_records = records["visual"]
    effect_before_records = records["effect_before"]
    effect_after_records = records["effect_after"]
    if len(effect_before_records) not in (1, len(visual_records)):
        return (
            "effect_before_count_mismatch expected=1_or_"
            f"{len(visual_records)} actual={len(effect_before_records)}"
        )
    if len(effect_after_records) not in (1, len(visual_records)):
        return (
            "effect_after_count_mismatch expected=1_or_"
            f"{len(visual_records)} actual={len(effect_after_records)}"
        )
    if len(effect_before_records) != len(effect_after_records):
        return (
            "effect_count_shape_mismatch before="
            f"{len(effect_before_records)} after={len(effect_after_records)}"
        )

    actor = records["actor"][0]
    anim_current = parse_hex16(
        require_field(actor, "anim_current", "actor"), "actor.anim_current"
    )
    anim_first = parse_hex16(
        require_field(actor, "anim_first", "actor"), "actor.anim_first"
    )
    anim_last = parse_hex16(
        require_field(actor, "anim_last", "actor"), "actor.anim_last"
    )
    bank_counts = {"BOMOMIMK": 91, "PROVA": 91, "FONTS": 68}
    visual_frames: list[int] = []
    first_bank: str | None = None
    first_sprite_source: str | None = None
    for visual in visual_records:
        visual_frame = parse_hex16(
            require_field(visual, "frame", "visual"), "visual.frame"
        )
        if not visual_frames:
            if visual_frame != anim_current:
                return (
                    "visual_frame_mismatch actor="
                    f"0x{anim_current:02x} visual=0x{visual_frame:02x}"
                )
        elif visual_frame != visual_frames[-1] + 1:
            return (
                "visual_frame_sequence_mismatch expected="
                f"0x{visual_frames[-1] + 1:02x} actual=0x{visual_frame:02x}"
            )
        if visual_frame < anim_first or visual_frame > anim_last:
            return (
                "visual_frame_out_of_range range="
                f"0x{anim_first:02x}..0x{anim_last:02x} "
                f"visual=0x{visual_frame:02x}"
            )
        visual_frames.append(visual_frame)

        row_address = parse_hex16(
            require_field(visual, "row_addr", "visual"), "visual.row_addr"
        )
        expected_row_address = FRAME_ENTRY_BASE + visual_frame * 4
        if row_address != expected_row_address:
            return (
                "row_addr_mismatch expected="
                f"0x{expected_row_address:04x} actual=0x{row_address:04x}"
            )
        has_visual_row = "row" in visual
        if "sprite_index" in visual and not has_visual_row:
            return "visual_row_missing_for_sprite"
        if not has_visual_row:
            return "visual_row_missing"
        claimed_row = parse_row_bytes(
            require_field(visual, "row", "visual"), "visual.row"
        )
        if len(claimed_row) != 4:
            return "row_byte_count field=visual.row"
        if -1 in memory:
            return "dump_segment_mismatch"
        memory_row: list[int] = []
        for address in range(row_address, row_address + 4):
            if address not in memory:
                return f"missing_byte address={address:04x}"
            memory_row.append(memory[address])
        if claimed_row != memory_row:
            expected = ",".join(f"{byte:02x}" for byte in memory_row)
            actual = ",".join(f"{byte:02x}" for byte in claimed_row)
            return f"visual_row_mismatch expected={expected} actual={actual}"

        bank = require_field(visual, "bank", "visual").upper().removesuffix(".SPR")
        if bank not in bank_counts:
            return f"unknown_sprite_bank value={bank}"
        if first_bank is None:
            first_bank = bank
        elif bank != first_bank:
            return f"visual_bank_changed first={first_bank} actual={bank}"
        sprite_index = parse_int(
            require_field(visual, "sprite_index", "visual"), "visual.sprite_index"
        )
        if sprite_index < 0 or sprite_index >= bank_counts[bank]:
            return f"sprite_index_out_of_range bank={bank} index={sprite_index}"
        sprite_source = visual.get("sprite_source", "runtime")
        if first_sprite_source is None:
            first_sprite_source = sprite_source
        elif sprite_source != first_sprite_source:
            return (
                "visual_sprite_source_changed first="
                f"{first_sprite_source} actual={sprite_source}"
            )
        if sprite_source == "row_byte0" and sprite_index != claimed_row[0]:
            return (
                "sprite_index_row0_mismatch row0="
                f"{claimed_row[0]} sprite_index={sprite_index}"
            )
        if sprite_source == "row_byte3" and sprite_index != claimed_row[3]:
            return (
                "sprite_index_row3_mismatch row3="
                f"{claimed_row[3]} sprite_index={sprite_index}"
            )
        if sprite_source not in {
            "row_byte0",
            "row_byte3",
            "runtime_draw_call",
            "static_table",
        }:
            return f"bad_sprite_source value={sprite_source}"

    effect_frames = (
        [visual_frames[0]]
        if len(effect_before_records) == 1
        else visual_frames
    )
    for index, expected_frame in enumerate(effect_frames):
        effect_before = effect_before_records[index]
        effect_after = effect_after_records[index]
        before_slot = parse_int(
            require_field(effect_before, "slot", "effect_before"),
            "effect_before.slot",
        )
        after_slot = parse_int(
            require_field(effect_after, "slot", "effect_after"), "effect_after.slot"
        )
        if before_slot != after_slot:
            return f"effect_slot_changed before={before_slot} after={after_slot}"
        before_frame = parse_hex16(
            require_field(effect_before, "frame", "effect_before"),
            "effect_before.frame",
        )
        if before_frame != expected_frame:
            return (
                "effect_before_frame_mismatch expected="
                f"0x{expected_frame:02x} actual=0x{before_frame:02x}"
            )
        after_frame = parse_hex16(
            require_field(effect_after, "frame", "effect_after"),
            "effect_after.frame",
        )
        if after_frame != expected_frame:
            return (
                "effect_after_frame_mismatch expected="
                f"0x{expected_frame:02x} actual=0x{after_frame:02x}"
            )
    return "ok"


def test_block(text: str, name: str) -> str:
    start = text.find(f"add_test(NAME {name}")
    if start < 0:
        return ""
    end = text.find("\n    add_test(NAME ", start + 1)
    if end < 0:
        end = text.find("\n    if(", start + 1)
    if end < 0:
        end = len(text)
    return text[start:end]


def check_cmake_coverage(cmake_path: Path, fixture_names: set[str]) -> int:
    text = cmake_path.read_text(encoding="utf-8")
    for fixture_name in sorted(fixture_names):
        expected = expected_outcome_for(fixture_name)
        if expected is None:
            raise RuntimeError(f"unexpected visual-table fixture: {fixture_name}")
        stem = Path(fixture_name).stem
        if f"add_test(NAME {stem}" not in text:
            raise RuntimeError(f"CMake coverage missing for {fixture_name}: add_test")
        if f"set_tests_properties({stem}" not in text:
            raise RuntimeError(
                f"CMake coverage missing for {fixture_name}: set_tests_properties"
            )
        if f"/tests/fixtures/dosbox/{fixture_name}" not in text:
            raise RuntimeError(
                f"CMake coverage missing for {fixture_name}: fixture path"
            )
        if expected == "ok":
            required = f"visual_table_oracle=ok fixture={stem}"
            if "--expect-error" in test_block(text, stem):
                raise RuntimeError(f"valid fixture uses --expect-error: {fixture_name}")
        else:
            required = f"visual_table_oracle=error fixture={stem} reason={expected}"
            if "--expect-error" not in test_block(text, stem):
                raise RuntimeError(
                    f"malformed fixture missing --expect-error: {fixture_name}"
                )
        if required not in text:
            raise RuntimeError(
                f"CMake coverage missing for {fixture_name}: {required}"
            )
    return len(fixture_names)


def check_source_contract(source_path: Path) -> None:
    text = source_path.read_text(encoding="utf-8")
    for snippet in [
        "--debug-visual-table-oracle",
        "debugVisualTableOracle",
        "requiredBreaks = {0x3108, 0x6053, 0x6148, 0x7c89, 0x7ddf}",
        "row_addr=",
        "sprite_source=",
        "row_byte3",
        "effect_after_frame=",
        "visual_claim=0",
    ]:
        if snippet not in text:
            raise RuntimeError(f"C++ visual-table oracle missing snippet: {snippet}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check visual-table oracle fixture expectations."
    )
    parser.add_argument(
        "fixture_dir",
        nargs="?",
        type=Path,
        default=default_repo_root() / "tests" / "fixtures" / "dosbox",
    )
    parser.add_argument(
        "--cmake",
        type=Path,
        default=default_repo_root() / "CMakeLists.txt",
        help="CMakeLists.txt path to verify test coverage; use '' to skip",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=default_repo_root() / "src" / "app" / "app.cpp",
        help="src/app/app.cpp path to verify command/source snippets; use '' to skip",
    )
    args = parser.parse_args()

    fixture_dir = args.fixture_dir.resolve()
    paths = sorted(
        path
        for path in fixture_dir.glob("visual_table_oracle*.txt")
        if not path.name.endswith("-LIS.txt")
    )
    names = {path.name for path in paths}
    missing = sorted(set(EXPECTED_OUTCOMES) - names)
    extra = sorted(name for name in names if expected_outcome_for(name) is None)
    if missing:
        raise RuntimeError("missing visual-table fixtures: " + ",".join(missing))
    if extra:
        raise RuntimeError("unexpected visual-table fixtures: " + ",".join(extra))

    ok_count = 0
    malformed_count = 0
    original_count = 0
    for path in paths:
        values, records, breaks, memory = parse_fixture(path)
        outcome = infer_outcome(values, records, breaks, memory)
        expected = expected_outcome_for(path.name)
        if expected is None:
            raise RuntimeError(f"unexpected visual-table fixture: {path.name}")
        if outcome != expected:
            raise RuntimeError(
                f"{path.name} outcome mismatch: expected {expected!r} got {outcome!r}"
            )
        if path.name not in EXPECTED_OUTCOMES:
            original_count += 1
        if outcome == "ok":
            ok_count += 1
        else:
            malformed_count += 1

    cmake_count = 0
    if str(args.cmake) != "":
        cmake_count = check_cmake_coverage(args.cmake.resolve(), names)
    source_command = 0
    if str(args.source) != "":
        check_source_contract(args.source.resolve())
        source_command = 1

    print(
        "visual_table_oracle_fixtures=ok "
        f"files={len(paths)} valid={ok_count} malformed={malformed_count} "
        f"original={original_count} cmake_tests={cmake_count} "
        f"source_command={source_command}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
