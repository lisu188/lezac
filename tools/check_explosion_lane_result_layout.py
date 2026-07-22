#!/usr/bin/env python3
"""Check lane-result scratch field layout across helper/oracle tooling."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


EXPECTED_FIELDS = [
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


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def quoted_names(text: str) -> list[str]:
    return re.findall(r'"([a-z_]+)"', text)


def require_equal(actual: list[str], expected: list[str], label: str) -> None:
    if actual != expected:
        raise RuntimeError(
            f"{label} mismatch: expected {','.join(expected)} actual {','.join(actual)}"
        )


def extract_bracket_list(text: str, marker: str, label: str) -> list[str]:
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"missing marker for {label}: {marker}")
    open_bracket = text.find("[", start)
    close_bracket = text.find("]", open_bracket)
    if open_bracket < 0 or close_bracket < 0:
        raise RuntimeError(f"missing bracket list for {label}")
    return quoted_names(text[open_bracket:close_bracket])


def extract_cpp_lane_result_fields(src: str) -> list[str]:
    marker = "kLaneResultFieldNames{"
    start = src.find(marker)
    if start < 0:
        raise RuntimeError("missing C++ kLaneResultFieldNames")
    close_brace = src.find("};", start)
    if close_brace < 0:
        raise RuntimeError("unterminated C++ kLaneResultFieldNames")
    return quoted_names(src[start:close_brace])


def extract_scratch_dict_fields(src: str) -> list[str]:
    marker = "runtime_lane_result_scratch = {"
    start = src.find(marker)
    if start < 0:
        raise RuntimeError("missing runtime_lane_result_scratch dict")
    close_brace = src.find("}", start)
    if close_brace < 0:
        raise RuntimeError("unterminated runtime_lane_result_scratch dict")
    return re.findall(r'"([a-z_]+)"\s*:', src[start:close_brace])


def extract_writer_field_loops(src: str) -> list[list[str]]:
    loops: list[list[str]] = []
    search_from = 0
    marker = "runtime_lane_result_scratch[field]"
    while True:
        use = src.find(marker, search_from)
        if use < 0:
            break
        loop = src.rfind("for field in [", 0, use)
        if loop < 0:
            raise RuntimeError("lane-result writer missing for-field loop")
        close_bracket = src.find("]", loop)
        if close_bracket < 0 or close_bracket > use:
            raise RuntimeError("unterminated lane-result writer field loop")
        fields = quoted_names(src[loop:close_bracket])
        loops.append(fields)
        search_from = use + len(marker)
    return loops


def require_candidate_freeze_old_byte_fields(src: str) -> None:
    start = src.find('out.write("capture=explosion_playback\\n")')
    if start < 0:
        raise RuntimeError("missing candidate fixture writer")
    end = src.find('instrumentation_manifest = ""', start)
    if end < 0:
        raise RuntimeError("missing instrumentation manifest writer")
    candidate_writer = src[start:end]
    for key in ["freeze_expected_old_bytes", "freeze_old_bytes"]:
        if f'"{key}=' not in candidate_writer and f'f"{key}=' not in candidate_writer:
            raise RuntimeError(f"candidate writer missing {key}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-result scratch field layout consistency."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()

    main_cpp = (root / "src" / "app" / "app.cpp").read_text(encoding="utf-8")
    capture = (
        root / "tools" / "capture_original_explosion_procmem.py"
    ).read_text(encoding="utf-8")
    fixture_checker = (
        root / "tools" / "check_explosion_lane_result_fixtures.py"
    ).read_text(encoding="utf-8")

    require_equal(
        extract_bracket_list(fixture_checker, "LANE_RESULT_FIELDS = [", "fixture checker"),
        EXPECTED_FIELDS,
        "fixture checker",
    )
    require_equal(
        extract_cpp_lane_result_fields(main_cpp),
        EXPECTED_FIELDS,
        "C++ oracle",
    )
    require_equal(
        extract_scratch_dict_fields(capture),
        EXPECTED_FIELDS,
        "capture scratch dict",
    )
    writer_loops = extract_writer_field_loops(capture)
    if not writer_loops:
        raise RuntimeError("no lane-result writer loops found")
    for index, fields in enumerate(writer_loops):
        require_equal(fields, EXPECTED_FIELDS, f"capture writer loop {index}")
    require_candidate_freeze_old_byte_fields(capture)
    for field in EXPECTED_FIELDS:
        if f" lane_result_{field}=" not in main_cpp:
            raise RuntimeError(f"C++ success output missing lane_result_{field}")

    print(
        "lane_result_layout=ok "
        f"fields={len(EXPECTED_FIELDS)} writer_loops={len(writer_loops)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
