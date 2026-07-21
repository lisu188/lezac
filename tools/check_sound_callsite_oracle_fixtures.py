#!/usr/bin/env python3
"""Check sound-callsite runtime oracle fixtures and test wiring."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


EXPECTED_OUTCOMES = {
    "sound_callsite_oracle_synthetic.txt": "ok",
    "sound_callsite_oracle_bad_segment.txt": (
        "breakpoint_segment_mismatch expected=0x1a2b actual=0xffff"
    ),
    "sound_callsite_oracle_missing_request.txt": "sound_request_missing",
    "sound_callsite_oracle_bad_pending_cursor.txt": (
        "pending_cursor_dump_mismatch expected=0x002d actual=0x002e"
    ),
}
ORIGINAL_PREFIX = "sound_callsite_oracle_original"


def expected_outcome_for(name: str) -> str | None:
    if name in EXPECTED_OUTCOMES:
        return EXPECTED_OUTCOMES[name]
    if name.startswith(ORIGINAL_PREFIX) and name.endswith(".txt"):
        return "ok"
    return None


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def hex4(value: int) -> str:
    return f"0x{value & 0xffff:04x}"


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


def parse_far_pointer(token: str, field: str) -> tuple[int, int]:
    if ":" not in token:
        raise RuntimeError(f"bad far pointer field={field} token={token}")
    segment, offset = token.split(":", 1)
    return parse_hex16(segment, f"{field}.segment"), parse_hex16(
        offset, f"{field}.offset"
    )


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
        raise RuntimeError(f"missing_field record={record} field={name}")
    return fields[name]


def parse_fixture(
    path: Path,
) -> tuple[
    dict[str, str],
    dict[str, str],
    list[tuple[int, int, int, int]],
    dict[int, int],
    int,
]:
    values: dict[str, str] = {}
    request: dict[str, str] = {}
    breaks: list[tuple[int, int, int, int]] = []
    memory: dict[int, int] = {}
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
        if line.startswith("sound_request "):
            record, request = parse_record(line)
            if record != "sound_request":
                raise RuntimeError(f"unexpected record: {record}")
            continue
        match = row_re.match(line)
        if match:
            segment = parse_hex16(match.group(1), "row_segment")
            if "runtime_ds" in values and segment != parse_hex16(
                values["runtime_ds"], "runtime_ds"
            ):
                return values, request, breaks, {-1: -1}, dump_bytes
            address = parse_hex16(match.group(2), "row_address")
            cursor = address
            for byte_text in match.group(3).split():
                if not re.fullmatch(r"[0-9a-fA-F]{2}", byte_text):
                    raise RuntimeError(f"bad dump byte token={byte_text}")
                memory[cursor & 0xffff] = int(byte_text, 16)
                cursor += 1
                dump_bytes += 1
            continue
    return values, request, breaks, memory, dump_bytes


def word_if_present(memory: dict[int, int], address: int) -> int | None:
    lo = memory.get(address & 0xffff)
    hi = memory.get((address + 1) & 0xffff)
    if lo is None or hi is None:
        return None
    return lo | (hi << 8)


def byte_if_present(memory: dict[int, int], address: int) -> int | None:
    return memory.get(address & 0xffff)


def infer_outcome(
    values: dict[str, str],
    request: dict[str, str],
    breaks: list[tuple[int, int, int, int]],
    memory: dict[int, int],
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
    if -1 in memory:
        return "dump_segment_mismatch"

    runtime_cs = parse_hex16(values["runtime_cs"], "runtime_cs")
    seen_offsets = set()
    for ghidra_segment, ghidra_offset, runtime_segment, runtime_offset in breaks:
        if ghidra_segment != 0x1000:
            return (
                "breakpoint_ghidra_segment expected=0x1000 actual="
                f"{hex4(ghidra_segment)}"
            )
        if runtime_segment != runtime_cs:
            return (
                "breakpoint_segment_mismatch expected="
                f"{hex4(runtime_cs)} actual={hex4(runtime_segment)}"
            )
        if runtime_offset != ghidra_offset:
            return (
                "breakpoint_offset_mismatch expected="
                f"{ghidra_offset:04x} actual={runtime_offset:04x}"
            )
        seen_offsets.add(ghidra_offset)

    if not request:
        return "sound_request_missing"
    for field in [
        "label",
        "callsite",
        "latch",
        "cursor",
        "priority",
        "active_before",
        "current_priority_before",
        "pending_cursor",
        "pending_priority",
        "accepted",
        "active_after",
        "current_priority_after",
        "current_cursor_after",
        "direct_sweep",
    ]:
        if field not in request:
            return f"missing_field record=sound_request field={field}"

    callsite_segment, callsite_offset = parse_far_pointer(
        request["callsite"], "sound_request.callsite"
    )
    latch_segment, latch_offset = parse_far_pointer(
        request["latch"], "sound_request.latch"
    )
    if callsite_segment != 0x1000:
        return f"callsite_segment_not_1000 actual={hex4(callsite_segment)}"
    if latch_segment != 0x1000 or latch_offset != 0x165A:
        return f"latch_address_mismatch actual={hex4(latch_segment)}:{latch_offset:04x}"
    for offset in [callsite_offset, latch_offset]:
        if offset not in seen_offsets:
            return f"missing_breakpoint offset={offset:04x}"

    cursor = parse_hex16(request["cursor"], "sound_request.cursor")
    priority = parse_int(request["priority"], "sound_request.priority")
    pending_cursor = parse_hex16(
        request["pending_cursor"], "sound_request.pending_cursor"
    )
    pending_priority = parse_int(
        request["pending_priority"], "sound_request.pending_priority"
    )
    accepted = parse_int(request["accepted"], "sound_request.accepted")
    active_after = parse_int(request["active_after"], "sound_request.active_after")
    current_priority_after = parse_int(
        request["current_priority_after"], "sound_request.current_priority_after"
    )
    current_cursor_after = parse_hex16(
        request["current_cursor_after"], "sound_request.current_cursor_after"
    )
    direct_sweep = parse_int(request["direct_sweep"], "sound_request.direct_sweep")

    if pending_cursor != cursor:
        return f"pending_cursor_mismatch expected={hex4(cursor)} actual={hex4(pending_cursor)}"
    if pending_priority != priority:
        return f"pending_priority_mismatch expected={priority} actual={pending_priority}"
    if accepted != 0:
        if active_after == 0:
            return "accepted_but_inactive_after"
        if current_priority_after != priority:
            return (
                "accepted_priority_mismatch expected="
                f"{priority} actual={current_priority_after}"
            )
        if current_cursor_after != cursor:
            return (
                "accepted_cursor_mismatch expected="
                f"{hex4(cursor)} actual={hex4(current_cursor_after)}"
            )
    expected_direct_sweep = 1 if cursor > 0xEA60 else 0
    if direct_sweep != expected_direct_sweep:
        return (
            "direct_sweep_mismatch expected="
            f"{expected_direct_sweep} actual={direct_sweep}"
        )

    dumped_pending_cursor = word_if_present(memory, 0x2074)
    if dumped_pending_cursor is not None and dumped_pending_cursor != pending_cursor:
        return (
            "pending_cursor_dump_mismatch expected="
            f"{hex4(pending_cursor)} actual={hex4(dumped_pending_cursor)}"
        )
    dumped_pending_priority = byte_if_present(memory, 0x799F)
    if (
        dumped_pending_priority is not None
        and dumped_pending_priority != pending_priority
    ):
        return (
            "pending_priority_dump_mismatch expected="
            f"{hex4(pending_priority)} actual={hex4(dumped_pending_priority)}"
        )
    dumped_current_priority = byte_if_present(memory, 0x799E)
    if (
        dumped_current_priority is not None
        and dumped_current_priority != current_priority_after
    ):
        return (
            "current_priority_dump_mismatch expected="
            f"{hex4(current_priority_after)} actual={hex4(dumped_current_priority)}"
        )
    dumped_current_cursor = word_if_present(memory, 0x78C0)
    if dumped_current_cursor is not None and dumped_current_cursor != current_cursor_after:
        return (
            "current_cursor_dump_mismatch expected="
            f"{hex4(current_cursor_after)} actual={hex4(dumped_current_cursor)}"
        )
    dumped_active = byte_if_present(memory, 0x79C4)
    if dumped_active is not None and dumped_active != active_after:
        return (
            "active_flag_dump_mismatch expected="
            f"{hex4(active_after)} actual={hex4(dumped_active)}"
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
            raise RuntimeError(f"unexpected sound-callsite fixture: {fixture_name}")
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
            required = f"sound_callsite_oracle=ok fixture={stem}"
            if "--expect-error" in test_block(text, test_name):
                raise RuntimeError(f"valid fixture uses --expect-error: {fixture_name}")
        else:
            required = f"sound_callsite_oracle=error fixture={stem} reason={expected}"
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
        "--debug-sound-callsite-oracle",
        "debugSoundCallsiteOracle",
        "sound_request_missing",
        "pending_cursor_dump_mismatch",
        "direct_sweep=",
        "visual_claim=0",
    ]:
        if snippet not in text:
            raise RuntimeError(f"C++ sound-callsite oracle missing snippet: {snippet}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check sound-callsite runtime oracle fixture expectations."
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
        for path in fixture_dir.glob("sound_callsite_oracle*.txt")
        if not path.name.endswith("-LIS.txt")
    )
    names = {path.name for path in paths}
    missing = sorted(set(EXPECTED_OUTCOMES) - names)
    extra = sorted(name for name in names if expected_outcome_for(name) is None)
    if missing:
        raise RuntimeError("missing sound-callsite fixtures: " + ",".join(missing))
    if extra:
        raise RuntimeError("unexpected sound-callsite fixtures: " + ",".join(extra))

    ok_count = 0
    malformed_count = 0
    original_count = 0
    for path in paths:
        values, request, breaks, memory, _dump_bytes = parse_fixture(path)
        outcome = infer_outcome(values, request, breaks, memory)
        expected = expected_outcome_for(path.name)
        if expected is None:
            raise RuntimeError(f"unexpected sound-callsite fixture: {path.name}")
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
        "sound_callsite_oracle_fixtures=ok "
        f"files={len(paths)} valid={ok_count} malformed={malformed_count} "
        f"original={original_count} cmake_tests={cmake_count} "
        f"source_command={source_command}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
