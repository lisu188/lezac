#!/usr/bin/env python3
"""Check lane-result explosion oracle fixtures for expected parser outcomes."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


LANE_RESULT_FIELDS = [
    "output",
    "es",
    "di",
    "arg_offset",
    "arg_segment",
    "result_local",
    "active_count",
    "loop_index",
    "target_before",
]

EXPECTED_OUTCOMES = {
    "explosion_playback_oracle_lane_result_scratch_synthetic.txt": "ok",
    "explosion_playback_oracle_lane_result_reverse_scratch_synthetic.txt": "ok",
    "explosion_playback_oracle_lane_result_missing_target_before.txt": (
        "lane_result_field_missing field=target_before"
    ),
    "explosion_playback_oracle_lane_result_bad_far_pointer.txt": (
        "lane_result_far_pointer_mismatch"
    ),
    "explosion_playback_oracle_lane_result_bad_output_local.txt": (
        "lane_result_output_local_mismatch"
    ),
    "explosion_playback_oracle_lane_result_bad_expected_old_bytes.txt": (
        "freeze_expected_old_bytes_mismatch"
    ),
    "explosion_playback_oracle_lane_result_expected_without_old_bytes.txt": (
        "freeze_expected_without_old_bytes"
    ),
    "explosion_playback_oracle_lane_result_missing_expected_old_bytes.txt": (
        "lane_result_expected_old_bytes_missing"
    ),
    "explosion_playback_oracle_lane_result_bad_scratch_offset.txt": (
        "lane_result_scratch_offset_mismatch"
    ),
    "explosion_playback_oracle_lane_result_bad_kind.txt": (
        "lane_result_forward_kind_without_forward_freeze"
    ),
    "explosion_playback_oracle_lane_result_bad_loop_bounds.txt": (
        "lane_result_loop_bounds"
    ),
    "explosion_playback_oracle_lane_result_bad_target_before_width.txt": (
        "lane_result_target_before_width"
    ),
    "explosion_playback_oracle_lane_result_field_without_present.txt": (
        "lane_result_field_without_present"
    ),
}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_hex16(value: str, field: str) -> int:
    token = value.strip()
    if token.lower().startswith("0x"):
        token = token[2:]
    if not re.fullmatch(r"[0-9a-fA-F]{1,4}", token):
        raise RuntimeError(f"bad hex16 field={field} token={value}")
    return int(token, 16)


def normalize_hex_bytes(value: str, field: str) -> str:
    token = value.strip()
    if token.lower().startswith("0x"):
        token = token[2:]
    if len(token) % 2 != 0 or not re.fullmatch(r"[0-9a-fA-F]*", token):
        raise RuntimeError(f"bad hex bytes field={field} token={value}")
    return token.lower()


def parse_fixture(path: Path) -> tuple[dict[str, str], set[int]]:
    values: dict[str, str] = {}
    observed_breaks: set[int] = set()
    key_re = re.compile(r"^([A-Za-z0-9_]+)=(.*)$")
    break_re = re.compile(r"^break\s+ghidra=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})\s+")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = key_re.match(line)
        if match:
            values[match.group(1)] = match.group(2).strip()
            continue
        match = break_re.match(line)
        if match and "observed=runtime_child_memory_freeze_observed" in line:
            observed_breaks.add(int(match.group(2), 16))
    return values, observed_breaks


def infer_lane_result_outcome(values: dict[str, str], observed_breaks: set[int]) -> str:
    if "freeze_expected_old_bytes" in values:
        expected = normalize_hex_bytes(
            values["freeze_expected_old_bytes"], "freeze_expected_old_bytes"
        )
        if "freeze_old_bytes" not in values:
            return "freeze_expected_without_old_bytes"
        old = normalize_hex_bytes(values["freeze_old_bytes"], "freeze_old_bytes")
        if not old.startswith(expected):
            return "freeze_expected_old_bytes_mismatch"

    observed_forward = 0x3D3F in observed_breaks
    observed_reverse = 0x3ED3 in observed_breaks
    have_present = "instrumented_lane_result_scratch_present" in values
    scratch_present = values.get("instrumented_lane_result_scratch_present") == "1"
    have_value_field = any(
        f"instrumented_lane_result_{field}" in values for field in LANE_RESULT_FIELDS
    )

    if have_present and scratch_present:
        if not observed_forward and not observed_reverse:
            return "lane_result_scratch_without_lane_result_freeze"
        expected_old_bytes = values.get("freeze_expected_old_bytes")
        if (
            expected_old_bytes is None
            or normalize_hex_bytes(
                expected_old_bytes, "freeze_expected_old_bytes"
            )
            != "268805"
        ):
            return "lane_result_expected_old_bytes_missing"
        if "instrumented_lane_result_cs_offset" not in values:
            return "lane_result_offset_missing"
        if parse_hex16(
            values["instrumented_lane_result_cs_offset"],
            "instrumented_lane_result_cs_offset",
        ) != 0xF280:
            return "lane_result_scratch_offset_mismatch"
        if "instrumented_lane_result_kind" not in values:
            return "lane_result_kind_missing"
        kind = values["instrumented_lane_result_kind"]
        if kind == "forward" and not observed_forward:
            return "lane_result_forward_kind_without_forward_freeze"
        if kind == "reverse" and not observed_reverse:
            return "lane_result_reverse_kind_without_reverse_freeze"
        if kind not in {"forward", "reverse"}:
            return f"bad_lane_result_kind value={kind}"
        parsed: dict[str, int] = {}
        for field in LANE_RESULT_FIELDS:
            key = f"instrumented_lane_result_{field}"
            if key not in values:
                return f"lane_result_field_missing field={field}"
            parsed[field] = parse_hex16(values[key], key)
        output = parsed["output"]
        if output != parsed["result_local"] or (output & 0xFF00) != 0:
            return "lane_result_output_local_mismatch"
        if (parsed["target_before"] & 0xFF00) != 0:
            return "lane_result_target_before_width"
        if parsed["es"] != parsed["arg_segment"] or parsed["di"] != parsed["arg_offset"]:
            return "lane_result_far_pointer_mismatch"
        active_count = parsed["active_count"]
        loop_index = parsed["loop_index"]
        if loop_index == 0 or active_count == 0 or loop_index > active_count:
            return "lane_result_loop_bounds"

    if have_value_field and (not have_present or not scratch_present):
        return "lane_result_field_without_present"
    return "ok"


def check_cmake_coverage(cmake_path: Path, fixture_names: set[str]) -> int:
    text = cmake_path.read_text(encoding="utf-8")
    for fixture_name, expected in EXPECTED_OUTCOMES.items():
        if fixture_name not in fixture_names:
            continue
        stem = Path(fixture_name).stem
        test_start = text.find(f"add_test(NAME {stem}")
        if test_start < 0:
            raise RuntimeError(f"CMake coverage missing for {fixture_name}: add_test")
        test_end = text.find(f"set_tests_properties({stem}", test_start)
        if test_end < 0:
            raise RuntimeError(
                f"CMake coverage missing for {fixture_name}: set_tests_properties"
            )
        add_test_block = text[test_start:test_end]
        has_expect_error = "--expect-error" in add_test_block
        if expected == "ok" and has_expect_error:
            raise RuntimeError(f"CMake valid fixture uses --expect-error: {fixture_name}")
        if expected != "ok" and not has_expect_error:
            raise RuntimeError(
                f"CMake malformed fixture missing --expect-error: {fixture_name}"
            )
        required = [
            f"/tests/fixtures/dosbox/{fixture_name}",
        ]
        if expected == "ok":
            required.append(f"explosion_playback_oracle=ok fixture={stem}")
        else:
            required.append(
                f"explosion_playback_oracle=error fixture={stem} reason={expected}"
            )
        for snippet in required:
            if snippet not in text:
                raise RuntimeError(
                    f"CMake coverage missing for {fixture_name}: {snippet}"
                )
    return len(fixture_names)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-result explosion oracle fixture expectations."
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
    args = parser.parse_args()

    fixture_dir = args.fixture_dir.resolve()
    paths = sorted(fixture_dir.glob("explosion_playback_oracle_lane_result*.txt"))
    names = {path.name for path in paths}
    missing = sorted(set(EXPECTED_OUTCOMES) - names)
    extra = sorted(names - set(EXPECTED_OUTCOMES))
    if missing:
        raise RuntimeError("missing lane-result fixtures: " + ",".join(missing))
    if extra:
        raise RuntimeError("unexpected lane-result fixtures: " + ",".join(extra))

    ok_count = 0
    malformed_count = 0
    for path in paths:
        values, observed_breaks = parse_fixture(path)
        outcome = infer_lane_result_outcome(values, observed_breaks)
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
    print(
        "lane_result_fixtures=ok "
        f"files={len(paths)} valid={ok_count} malformed={malformed_count} "
        f"cmake_tests={cmake_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
