#!/usr/bin/env python3
"""Check explosion/debris/collapse evidence handoff wiring."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


LANE_RESULT_OFFSETS = ("1000:3D3F", "1000:3ED3")
LANE_DIV_OFFSETS = ("1000:3CD4", "1000:3CE3", "1000:3E68", "1000:3E77")
LANE_WRITE_OFFSETS = ("1000:3D1B", "1000:3D2D", "1000:3EAF", "1000:3EC1")
HIGH_EFFECT_OFFSETS = (
    "1000:4B6A",
    "1000:4C75",
    "1000:4C96",
    "1000:4CA9",
    "1000:4C99",
    "1000:4CAC",
)

EXPECTED_FIXTURE_COUNT = 47
EXPECTED_PLAYBACK_CTESTS = 47
EXPECTED_LANE_RESULT_HELPER_CTESTS = 24

HELPER_TESTS = (
    "explosion_lane_result_preflight",
    "explosion_lane_result_fixture_expectations",
    "explosion_lane_result_layout_expectations",
    "explosion_lane_result_orchestrator_cmake_expectations",
    "explosion_lane_result_wrapper_output_expectations",
    "explosion_lane_result_route_sweep_dry_run",
    "explosion_lane_result_route_sweep_output_expectations",
    "explosion_lane_result_route_sweep_summary_expectations",
    "explosion_lane_result_ready_manifest_expectations",
    "explosion_lane_result_ready_results_expectations",
    "explosion_lane_result_ready_pipeline_expectations",
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise RuntimeError(f"{label}: missing {needle!r}")


def require_test(cmake: str, name: str) -> None:
    if not re.search(rf"add_test\(NAME\s+{re.escape(name)}\b", cmake):
        raise RuntimeError(f"CMakeLists.txt: missing CTest {name!r}")


def count_tests(cmake: str, pattern: str) -> int:
    return len(re.findall(pattern, cmake))


def all_offsets() -> tuple[str, ...]:
    return LANE_RESULT_OFFSETS + LANE_DIV_OFFSETS + LANE_WRITE_OFFSETS + HIGH_EFFECT_OFFSETS


def check_docs(readme: str, ghidra: str, status: str) -> None:
    readme_needles = (
        "tools/check_explosion_lane_result_preflight.py",
        "tools/check_explosion_lane_result_wrapper.py",
        "tools/capture_original_lane_result_runtime.py",
        "tools/sweep_original_lane_result_routes.py",
        "tools/summarize_lane_result_route_sweep.py",
        "tools/run_lane_result_ready_manifest.py",
        "tools/summarize_lane_result_ready_results.py",
        "tools/check_lane_result_ready_pipeline.py",
        "--debug-explosion-playback-oracle",
        "lane-result-cs-scratch",
        "forward` alias maps to Ghidra `1000:3D3F`",
        "`1000:3ED3`",
        "visual_claim=0",
        "Natural-route forward `3D3F` evidence remains pending",
    )
    for needle in readme_needles:
        require(readme, needle, "README_RECONSTRUCTION.md")

    ghidra_lower = ghidra.lower()
    for offset in all_offsets():
        require(ghidra_lower, offset.lower(), "docs/GHIDRA_NOTES.md")
    for needle in (
        "lane-result",
        "lane-div",
        "lane-write",
        "visual_claim=0",
        "tools/summarize_lane_result_route_sweep.py",
        "tools/run_lane_result_ready_manifest.py",
        "tools/summarize_lane_result_ready_results.py",
    ):
        require(ghidra_lower, needle.lower(), "docs/GHIDRA_NOTES.md")

    for needle in (
        "tools/check_explosion_lane_result_preflight.py",
        "tools/check_explosion_lane_result_fixtures.py",
        "tools/check_explosion_lane_result_layout.py",
        "tools/check_explosion_lane_result_orchestrator.py",
        "tools/check_explosion_lane_result_wrapper.py",
        "tools/sweep_original_lane_result_routes.py",
        "tools/summarize_lane_result_route_sweep.py",
        "tools/run_lane_result_ready_manifest.py",
        "tools/summarize_lane_result_ready_results.py",
    ):
        require(status, needle, "RECOVERY_STATUS.md")


def check_source(source: str) -> None:
    for needle in (
        "--debug-explosion-playback-oracle",
        "explosion_playback_oracle=ok",
        "explosion_playback_oracle=error",
        "lane_div_scratch_present=",
        "lane_write_scratch_present=",
        "lane_result_scratch_present=",
        "bp4_local_present=",
        "observed_high_zero_branch=",
        "observed_high_word_gate=",
        "observed_effect_forward_call=",
        "observed_effect_reverse_call=",
        "observed_effect_forward_return=",
        "observed_effect_reverse_return=",
        "debris0_tile_index=",
        "collapse0_start=",
        "effect0_xy=",
        "freeze_expected_old_bytes=",
        "visual_claim=0",
    ):
        require(source, needle, "src/main.cpp")


def check_capture_helpers(root: Path) -> None:
    procmem = read_text(root / "tools" / "capture_original_explosion_procmem.py")
    for needle in (
        "FREEZE_PATCH_MODE_LANE_DIV_CS_SCRATCH",
        "FREEZE_PATCH_MODE_LANE_WRITE_CS_SCRATCH",
        "FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH",
        "lane-result-cs-scratch",
        "lane-write-cs-scratch",
        "lane-div-cs-scratch",
        "expected_original_bytes",
        "scratch_offset",
        "0xF280",
        "0xF200",
        '"kind": "debris-writeback"',
        "runtime_seed_kind=",
    ):
        require(procmem, needle, "capture_original_explosion_procmem.py")
    for offset in all_offsets():
        require(procmem, offset, "capture_original_explosion_procmem.py")

    lane_runtime = read_text(root / "tools" / "capture_original_lane_result_runtime.py")
    for needle in (
        'OFFSETS = ["1000:3D3F", "1000:3ED3"]',
        '"FORWARD": "1000:3D3F"',
        '"REVERSE": "1000:3ED3"',
        "--freeze-patch-mode",
        "lane-result-cs-scratch",
        "--debug-explosion-playback-oracle",
        "--preflight-only",
        "--skip-oracle",
        "oracle_command_",
    ):
        require(lane_runtime, needle, "capture_original_lane_result_runtime.py")

    sweep = read_text(root / "tools" / "sweep_original_lane_result_routes.py")
    summary = read_text(root / "tools" / "summarize_lane_result_route_sweep.py")
    runner = read_text(root / "tools" / "run_lane_result_ready_manifest.py")
    results = read_text(root / "tools" / "summarize_lane_result_ready_results.py")
    for needle in ("--route", "--offset", "--dry-run", "DEFAULT_ROUTES"):
        require(sweep, needle, "sweep_original_lane_result_routes.py")
    for needle in (
        "3d3f",
        "3ed3",
        "candidate_status=",
        "oracle_command=",
        "--write-ready-manifest",
        "lane_result_ready_manifest=ok",
    ):
        require(summary, needle, "summarize_lane_result_route_sweep.py")
    for needle in (
        "--debug-explosion-playback-oracle",
        "lane_result_ready_manifest=ok",
        "--write-result-manifest",
        "--require-source-environment-preflight",
    ):
        require(runner, needle, "run_lane_result_ready_manifest.py")
    for needle in (
        "EXPECTED_RESULT = \"lane_result_ready_manifest\"",
        "lane_result_ready_result_summary=ok",
        "--require-success",
        "--require-executed",
    ):
        require(results, needle, "summarize_lane_result_ready_results.py")


def check_python_checkers(root: Path) -> None:
    for rel_path in (
        "tools/check_explosion_lane_result_preflight.py",
        "tools/check_explosion_lane_result_fixtures.py",
        "tools/check_explosion_lane_result_layout.py",
        "tools/check_explosion_lane_result_orchestrator.py",
        "tools/check_explosion_lane_result_wrapper.py",
        "tools/check_lane_result_ready_manifest.py",
        "tools/check_lane_result_ready_results.py",
        "tools/check_lane_result_ready_pipeline.py",
        "tools/check_lane_result_route_sweep.py",
        "tools/check_lane_result_route_sweep_summary.py",
    ):
        path = root / rel_path
        if not path.is_file():
            raise RuntimeError(f"missing checker {rel_path}")

    preflight = read_text(root / "tools" / "check_explosion_lane_result_preflight.py")
    for needle in (
        "EXPECTED_RESULT_WRITE_TAIL",
        "1000:3D3F",
        "1000:3ED3",
        "expected_original_bytes",
        "scratch_offset=0xf280",
        "wrong_offset_guard=1",
    ):
        require(preflight, needle, "check_explosion_lane_result_preflight.py")

    fixture_checker = read_text(
        root / "tools" / "check_explosion_lane_result_fixtures.py"
    )
    for needle in (
        "EXPECTED_OUTCOMES",
        "explosion_playback_oracle_lane_result_scratch_synthetic.txt",
        "explosion_playback_oracle_lane_result_bad_loop_bounds.txt",
        "lane_result_field_without_present",
        "valid={ok_count} malformed={malformed_count}",
    ):
        require(fixture_checker, needle, "check_explosion_lane_result_fixtures.py")


def check_fixtures_and_cmake(root: Path, cmake: str) -> tuple[int, int, int]:
    fixture_dir = root / "tests" / "fixtures" / "dosbox"
    fixtures = sorted(fixture_dir.glob("explosion_playback_oracle*.txt"))
    if len(fixtures) != EXPECTED_FIXTURE_COUNT:
        raise RuntimeError(
            f"expected {EXPECTED_FIXTURE_COUNT} explosion fixtures, got {len(fixtures)}"
        )
    for fixture in fixtures:
        stem = fixture.stem
        require_test(cmake, stem)
        require(cmake, f"/tests/fixtures/dosbox/{fixture.name}", "CMakeLists.txt")

    for test_name in HELPER_TESTS:
        require_test(cmake, test_name)
    require_test(cmake, "python_tool_syntax_lane_result_preflight")
    require(cmake, "tools/check_explosion_evidence_map.py", "CMakeLists.txt")
    require(cmake, "tools/check_explosion_lane_result_preflight.py", "CMakeLists.txt")
    require(cmake, "tools/check_lane_result_ready_pipeline.py", "CMakeLists.txt")

    playback_ctests = count_tests(cmake, r"add_test\(NAME\s+explosion_playback_oracle")
    if playback_ctests != EXPECTED_PLAYBACK_CTESTS:
        raise RuntimeError(
            f"expected {EXPECTED_PLAYBACK_CTESTS} playback CTests, got {playback_ctests}"
        )
    helper_ctests = count_tests(
        cmake,
        r"add_test\(NAME\s+(?:explosion_lane_result|lane_result).*",
    )
    if helper_ctests != EXPECTED_LANE_RESULT_HELPER_CTESTS:
        raise RuntimeError(
            f"expected {EXPECTED_LANE_RESULT_HELPER_CTESTS} lane-result helper CTests, "
            f"got {helper_ctests}"
        )
    return len(fixtures), playback_ctests, helper_ctests


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check explosion/debris/collapse evidence handoff consistency."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cmake = read_text(root / "CMakeLists.txt")
    check_docs(
        read_text(root / "README_RECONSTRUCTION.md"),
        read_text(root / "docs" / "GHIDRA_NOTES.md"),
        read_text(root / "RECOVERY_STATUS.md"),
    )
    check_source(read_text(root / "src" / "main.cpp"))
    check_capture_helpers(root)
    check_python_checkers(root)
    fixtures, playback_ctests, helper_ctests = check_fixtures_and_cmake(root, cmake)
    print(
        "explosion_evidence_map=ok "
        f"fixtures={fixtures} "
        f"playback_ctests={playback_ctests} "
        f"lane_result_helper_ctests={helper_ctests} "
        f"critical_offsets={len(all_offsets())} "
        "lane_result_offsets=1000:3D3F,1000:3ED3 "
        "oracle_flag=--debug-explosion-playback-oracle docs=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
