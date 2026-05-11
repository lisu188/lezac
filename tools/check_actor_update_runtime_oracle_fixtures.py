#!/usr/bin/env python3
"""Check actor-update runtime oracle fixtures and test wiring."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


REQUIRED_OFFSETS = [0x5CB0, 0x604F, 0x6053, 0x777F]

EXPECTED_OUTCOMES = {
    "actor_update_runtime_oracle_synthetic.txt": "ok",
    "actor_update_runtime_oracle_dispatch_gates_synthetic.txt": "ok",
    "actor_update_runtime_oracle_bad_segment.txt": (
        "breakpoint_segment_mismatch expected=0x1a2b actual=0xffff"
    ),
    "actor_update_runtime_oracle_missing_contact_scan.txt": "contact_scan_missing",
    "actor_update_runtime_oracle_bad_actor_slot.txt": "actor_slot_changed before=0 after=2",
}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_hex16(token: str, field: str) -> int:
    value = token.strip()
    if value.lower().startswith("0x"):
        value = value[2:]
    if not re.fullmatch(r"[0-9a-fA-F]{1,4}", value):
        raise RuntimeError(f"bad hex16 field={field} token={token}")
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


def require_field(fields: dict[str, str], name: str, record: str) -> int:
    if name not in fields:
        return -999999
    return parse_int(fields[name], f"{record}.{name}")


def parse_fixture(path: Path) -> tuple[dict[str, str], dict[str, dict[str, str]], list[tuple[int, int, int, int]], int]:
    values: dict[str, str] = {}
    records: dict[str, dict[str, str]] = {}
    breaks: list[tuple[int, int, int, int]] = []
    dump_bytes = 0
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
        if line.startswith(("actor_before ", "actor_after ", "contact_scan ", "tile_probe ")):
            record, fields = parse_record(line)
            records[record] = fields
            continue
        match = row_re.match(line)
        if match:
            segment = parse_hex16(match.group(1), "row_segment")
            if "runtime_ds" in values and segment != parse_hex16(
                values["runtime_ds"], "runtime_ds"
            ):
                return values, records, breaks, -1
            for byte_text in match.group(3).split():
                if not re.fullmatch(r"[0-9a-fA-F]{2}", byte_text):
                    raise RuntimeError(f"bad dump byte token={byte_text}")
                dump_bytes += 1
            continue
    return values, records, breaks, dump_bytes


def infer_outcome(
    values: dict[str, str],
    records: dict[str, dict[str, str]],
    breaks: list[tuple[int, int, int, int]],
    dump_bytes: int,
) -> str:
    if "runtime_cs" not in values:
        return "runtime_cs_missing"
    if "runtime_ds" not in values:
        return "runtime_ds_missing"
    if "scenario" not in values:
        return "scenario_missing"
    if "level" not in values:
        return "level_missing"
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
    seen_offsets = {ghidra_offset for _, ghidra_offset, _, _ in breaks}
    for offset in REQUIRED_OFFSETS:
        if offset not in seen_offsets:
            return f"missing_breakpoint offset={offset:04x}"
    if "actor_before" not in records:
        return "actor_before_missing"
    if "actor_after" not in records:
        return "actor_after_missing"
    if "contact_scan" not in records:
        return "contact_scan_missing"
    if "tile_probe" not in records:
        return "tile_probe_missing"

    before_slot = require_field(records["actor_before"], "slot", "actor_before")
    after_slot = require_field(records["actor_after"], "slot", "actor_after")
    if before_slot != after_slot:
        return f"actor_slot_changed before={before_slot} after={after_slot}"
    subject_slot = require_field(records["contact_scan"], "subject_slot", "contact_scan")
    if before_slot != subject_slot:
        return f"contact_scan_subject_mismatch actor={before_slot} scan={subject_slot}"
    before_flags = require_field(records["actor_before"], "flags", "actor_before")
    scan_before = require_field(records["contact_scan"], "flags_before", "contact_scan")
    if before_flags != scan_before:
        return (
            "contact_flags_before_mismatch actor="
            f"0x{before_flags & 0xffff:04x} scan=0x{scan_before & 0xffff:04x}"
        )
    after_flags = require_field(records["actor_after"], "flags", "actor_after")
    scan_after = require_field(records["contact_scan"], "flags_after", "contact_scan")
    if after_flags != scan_after:
        return (
            "contact_flags_after_mismatch actor="
            f"0x{after_flags & 0xffff:04x} scan=0x{scan_after & 0xffff:04x}"
        )
    if dump_bytes < 0:
        return "dump_segment_mismatch"
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
    for fixture_name, expected in EXPECTED_OUTCOMES.items():
        if fixture_name not in fixture_names:
            continue
        stem = Path(fixture_name).stem
        test_name = stem
        if f"add_test(NAME {test_name}" not in text:
            raise RuntimeError(f"CMake coverage missing for {fixture_name}: add_test")
        if f"set_tests_properties({test_name}" not in text:
            raise RuntimeError(
                f"CMake coverage missing for {fixture_name}: set_tests_properties"
            )
        if f"/tests/fixtures/dosbox/{fixture_name}" not in text:
            raise RuntimeError(
                f"CMake coverage missing for {fixture_name}: fixture path"
            )
        if expected == "ok":
            required = f"actor_update_runtime_oracle=ok fixture={stem}"
            if "--expect-error" in test_block(text, test_name):
                raise RuntimeError(f"valid fixture uses --expect-error: {fixture_name}")
        else:
            required = f"actor_update_runtime_oracle=error fixture={stem} reason={expected}"
            if "--expect-error" not in test_block(text, test_name):
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
        "--debug-actor-update-runtime-oracle",
        "debugActorUpdateRuntimeOracle",
        "0x5cb0, 0x604f, 0x6053, 0x777f",
        "contact_flags=",
        "tile_probe=",
        "damage_pending=",
        "dispatch_gates=",
        "visual_claim=0",
    ]:
        if snippet not in text:
            raise RuntimeError(f"C++ actor-update oracle missing snippet: {snippet}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check actor-update runtime oracle fixture expectations."
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
        default=default_repo_root() / "src" / "main.cpp",
        help="src/main.cpp path to verify command/source snippets; use '' to skip",
    )
    args = parser.parse_args()

    fixture_dir = args.fixture_dir.resolve()
    paths = sorted(fixture_dir.glob("actor_update_runtime_oracle*.txt"))
    names = {path.name for path in paths}
    missing = sorted(set(EXPECTED_OUTCOMES) - names)
    extra = sorted(names - set(EXPECTED_OUTCOMES))
    if missing:
        raise RuntimeError("missing actor-update fixtures: " + ",".join(missing))
    if extra:
        raise RuntimeError("unexpected actor-update fixtures: " + ",".join(extra))

    ok_count = 0
    malformed_count = 0
    for path in paths:
        values, records, breaks, dump_bytes = parse_fixture(path)
        outcome = infer_outcome(values, records, breaks, dump_bytes)
        expected = EXPECTED_OUTCOMES[path.name]
        if outcome != expected:
            raise RuntimeError(
                f"{path.name} outcome mismatch: expected {expected!r} got {outcome!r}"
            )
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
        "actor_update_runtime_oracle_fixtures=ok "
        f"files={len(paths)} valid={ok_count} malformed={malformed_count} "
        f"cmake_tests={cmake_count} source_command={source_command}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
