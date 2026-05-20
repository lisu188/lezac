#!/usr/bin/env python3
"""Check lane-result capture orchestrator CMake coverage."""

from __future__ import annotations

import argparse
from pathlib import Path


EXPECTED_RESULT_TAIL = "8b46f63b46f075c58a46f3c47e04268805c9c20600"

EXPECTED_TESTS = {
    "explosion_lane_result_capture_orchestrator_preflight": {
        "snippets": [
            "--preflight-only",
            "--asset-dir ${CMAKE_CURRENT_SOURCE_DIR}",
            "mode=preflight",
            "result_tail=1",
            f"result_tail_bytes={EXPECTED_RESULT_TAIL}",
            "wrong_offset_guard=1",
        ],
    },
    "explosion_lane_result_capture_orchestrator_preflight_positional": {
        "snippets": [
            "${CMAKE_CURRENT_SOURCE_DIR}",
            "--preflight-only",
            "mode=preflight",
            "result_tail=1",
            f"result_tail_bytes={EXPECTED_RESULT_TAIL}",
            "wrong_offset_guard=1",
        ],
    },
    "explosion_lane_result_capture_orchestrator_dry_run": {
        "snippets": [
            "--dry-run",
            "--skip-oracle",
            "offsets=2 capture_commands=2 oracle_commands=0",
            "offset_labels=3d3f,3ed3",
            "offset_addresses=1000:3D3F,1000:3ED3",
            "environment_preflight=1",
            "result_tail=1",
            f"result_tail_bytes={EXPECTED_RESULT_TAIL}",
        ],
    },
    "explosion_lane_result_capture_orchestrator_dry_run_with_oracle": {
        "snippets": [
            "--dry-run",
            "--cpp-exe ${CMAKE_CURRENT_BINARY_DIR}/lezac_cpp",
            "offsets=2 capture_commands=2 oracle_commands=2",
            "offset_labels=3d3f,3ed3",
            "offset_addresses=1000:3D3F,1000:3ED3",
            "result_tail=1",
            f"result_tail_bytes={EXPECTED_RESULT_TAIL}",
        ],
    },
    "explosion_lane_result_capture_orchestrator_dry_run_single_offset": {
        "snippets": [
            "--offset 3D3F",
            "offsets=1 capture_commands=1 oracle_commands=0",
            "offset_labels=3d3f",
            "offset_addresses=1000:3D3F",
            "result_tail=1",
            f"result_tail_bytes={EXPECTED_RESULT_TAIL}",
        ],
    },
    "explosion_lane_result_capture_orchestrator_dry_run_reverse_alias": {
        "snippets": [
            "--offset reverse",
            "offsets=1 capture_commands=1 oracle_commands=0",
            "offset_labels=3ed3",
            "offset_addresses=1000:3ED3",
            "result_tail=1",
            f"result_tail_bytes={EXPECTED_RESULT_TAIL}",
        ],
    },
    "explosion_lane_result_capture_orchestrator_dry_run_mixed_order": {
        "snippets": [
            "--offset reverse",
            "--offset forward",
            "offsets=2 capture_commands=2 oracle_commands=0",
            "offset_labels=3ed3,3d3f",
            "offset_addresses=1000:3ED3,1000:3D3F",
            "result_tail=1",
            f"result_tail_bytes={EXPECTED_RESULT_TAIL}",
        ],
    },
    "explosion_lane_result_capture_orchestrator_dry_run_timing_args": {
        "snippets": [
            "--runtime-freeze-after-bomb-seconds 0.125",
            "--level-start-seconds 2.25",
            "--right-hold-seconds 3.5",
            "--sample-seconds 6.75",
            "--sample-interval 0.015",
            "--route-state-interval 0.5",
            "--route-step x:1.25",
            "--route-step Left:0.50",
            "--tail-freeze-check-seconds 1.25",
        ],
    },
    "explosion_lane_result_capture_orchestrator_dry_run_alias_offsets": {
        "snippets": [
            "--offset forward",
            "--offset reverse",
            "offsets=2 capture_commands=2 oracle_commands=0",
            "offset_labels=3d3f,3ed3",
            "offset_addresses=1000:3D3F,1000:3ED3",
            "result_tail=1",
            f"result_tail_bytes={EXPECTED_RESULT_TAIL}",
        ],
    },
    "explosion_lane_result_capture_orchestrator_dry_run_duplicate_offset": {
        "snippets": [
            "--offset 3D3F",
            "--offset 1000:3D3F",
            "offsets=1 capture_commands=1 oracle_commands=0",
            "offset_labels=3d3f",
            "offset_addresses=1000:3D3F",
            "result_tail=1",
            f"result_tail_bytes={EXPECTED_RESULT_TAIL}",
        ],
    },
    "explosion_lane_result_capture_orchestrator_bad_offset": {
        "will_fail": True,
        "snippets": [
            "--offset sideways",
        ],
    },
    "explosion_lane_result_capture_orchestrator_refuses_repo_output": {
        "will_fail": True,
        "snippets": [
            "${CMAKE_CURRENT_SOURCE_DIR}/lane-result-runtime-refusal",
        ],
    },
    "explosion_lane_result_capture_orchestrator_requires_approval": {
        "will_fail": True,
        "snippets": [
            "/tmp/lezac-lane-result-runtime-refusal",
        ],
    },
    "explosion_lane_result_wrapper_output_expectations": {
        "snippets": [
            "check_explosion_lane_result_wrapper.py",
            "${CMAKE_CURRENT_SOURCE_DIR}",
            "lane_result_wrapper_output=ok cases=15",
        ],
    },
}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_block(text: str, name: str) -> str:
    start = text.find(f"add_test(NAME {name}")
    if start < 0:
        raise RuntimeError(f"missing add_test for {name}")
    prop_start = text.find(f"set_tests_properties({name}", start)
    if prop_start < 0:
        raise RuntimeError(f"missing set_tests_properties for {name}")
    next_test = text.find("\n        add_test(NAME ", prop_start + 1)
    if next_test < 0:
        next_test = text.find("\n    endif()", prop_start + 1)
    if next_test < 0:
        next_test = len(text)
    return text[start:next_test]


def collapse_ws(text: str) -> str:
    return " ".join(text.split())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-result capture orchestrator CMake coverage."
    )
    parser.add_argument(
        "cmake",
        nargs="?",
        type=Path,
        default=default_repo_root() / "CMakeLists.txt",
    )
    args = parser.parse_args()

    text = args.cmake.resolve().read_text(encoding="utf-8")
    source_path = args.cmake.resolve().parent / "tools" / "capture_original_lane_result_runtime.py"
    source = source_path.read_text(encoding="utf-8")
    for snippet in [
        "mode=capture out_dir=",
        "offset_labels={offset_labels(offsets)}",
        "offset_addresses={offset_addresses(offsets)}",
        "environment_preflight={environment_preflight}",
        "build_environment_preflight_command",
        "manifest={manifest}",
    ]:
        if snippet not in source:
            raise RuntimeError(f"orchestrator source missing snippet: {snippet}")
    for name, expectation in EXPECTED_TESTS.items():
        block = test_block(text, name)
        collapsed = collapse_ws(block)
        for snippet in expectation["snippets"]:
            if collapse_ws(snippet) not in collapsed:
                raise RuntimeError(f"{name} missing snippet: {snippet}")
        has_will_fail = "WILL_FAIL TRUE" in block
        expected_will_fail = bool(expectation.get("will_fail", False))
        if has_will_fail != expected_will_fail:
            raise RuntimeError(
                f"{name} WILL_FAIL mismatch: expected {expected_will_fail}"
            )
    print(
        "lane_result_orchestrator_cmake=ok "
        f"tests={len(EXPECTED_TESTS)} will_fail="
        f"{sum(1 for item in EXPECTED_TESTS.values() if item.get('will_fail'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
