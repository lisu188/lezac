#!/usr/bin/env python3
"""Check behavior-4 DOSBox-debug capture helper wiring."""

from __future__ import annotations

import argparse
from pathlib import Path


SCENARIOS = [
    "monster_spawner_behavior4_level2",
    "monster_spawner_behavior4_level3",
    "monster_behavior4_target_selection",
]

ANCHORS = [
    "1000:7A6B..7C2C",
    "1000:728C..731B",
    "1000:73E5..741B",
]

BREAKPOINTS = ["7A6B", "7C2C", "728C", "731B", "73E5", "741B"]

OUTPUTS = [
    "manifest.txt",
    "raw_debugger_dump.txt",
    "candidate_fixture.txt",
    "debugger_commands.txt",
    "debugger_commands_runtime.txt",
    "environment_preflight.log",
    "behavior4_debug_capture.log",
]


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, label: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{label} missing snippet: {snippet}")


def test_block(text: str, name: str) -> str:
    start = text.find(f"add_test(NAME {name}")
    if start < 0:
        raise RuntimeError(f"missing CMake add_test for {name}")
    prop_start = text.find(f"set_tests_properties({name}", start)
    if prop_start < 0:
        raise RuntimeError(f"missing CMake properties for {name}")
    next_test = text.find("\n        add_test(NAME ", prop_start + 1)
    if next_test < 0:
        next_test = text.find("\n    endif()", prop_start + 1)
    if next_test < 0:
        next_test = len(text)
    return text[start:next_test]


def collapse_ws(text: str) -> str:
    return " ".join(text.split())


def check_script(script_path: Path) -> None:
    text = script_path.read_text(encoding="utf-8")
    require(text, "#!/usr/bin/env bash", "script")
    require(text, "set -euo pipefail", "script")
    require(text, "usage: $0 out_dir [asset_dir] scenario", "script")
    require(text, "runtime_route=debugger_seeded", "script")
    require(text, "LEZAC_BEHAVIOR4_DEBUG_DRY_RUN", "script")
    require(text, "LEZAC_BEHAVIOR4_DEBUG_SKIP_ENVIRONMENT_PREFLIGHT", "script")
    require(text, "visual_claim=0", "script")
    require(text, "candidate_fixture=\"$out_dir/candidate_fixture.txt\"", "script")
    require(text, "runtime_commands_file=\"$out_dir/debugger_commands_runtime.txt\"", "script")
    require(text, "environment_preflight_log=\"$out_dir/environment_preflight.log\"", "script")
    require(text, "run_environment_preflight", "script")
    require(text, "preflight_original_evidence_environment.py", "script")
    require(text, "--require-debug-capture", "script")
    require(text, "write_runtime_command_plan", "script")
    require(text, "debugger_commands_runtime=$runtime_commands_file", "script")
    require(text, "environment_preflight=dry_run", "script")
    require(text, "grep -v '^#' \"$commands_file\"", "script")
    require(text, "capture=behavior4_runtime", "script")
    require(text, "scenario=$scenario", "script")
    require(text, "route=$runtime_route", "script")
    require(text, "spawner index=<index> behavior=4", "script")
    require(text, "actor_before slot=<slot> behavior=4", "script")
    require(text, "actor_after slot=<slot> behavior=4", "script")
    require(text, "players p1_dead=<0-or-1>", "script")
    require(text, "fixture_command=./build/lezac_cpp --debug-behavior4-runtime-oracle <candidate-fixture>", "script")
    require(text, "choose an output directory outside the repository", "script")
    require(text, "missing $asset_dir/LEZAC.EXE", "script")
    require(text, "dosbox-debug", "script")
    require(text, "xvfb-run", "script")
    require(text, "DEBUG LEZAC.EXE", "script")
    for scenario in SCENARIOS:
        require(text, scenario, "script")
    for output in OUTPUTS:
        require(text, output, "script")
    for anchor in ANCHORS:
        require(text, anchor, "script")
    for offset in BREAKPOINTS:
        require(text, f"BP <CS>:{offset}", "script")
    for dump in ["D DS:7900", "D DS:7A00", "D DS:7B00"]:
        require(text, dump, "script")


def check_cmake(cmake_path: Path) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    require(text, "find_program(BASH_EXECUTABLE bash)", "CMake")
    block = test_block(text, "behavior4_debug_capture_helper_dry_run")
    collapsed = collapse_ws(block)
    for snippet in [
        "LEZAC_BEHAVIOR4_DEBUG_DRY_RUN=1",
        "${BASH_EXECUTABLE}",
        "tools/capture_original_behavior4_debug.sh",
        "/tmp/lezac-behavior4-debug-dry-run",
        "${CMAKE_CURRENT_SOURCE_DIR}",
        "monster_behavior4_target_selection",
        "^behavior4_debug_capture=ok mode=dry_run scenario=monster_behavior4_target_selection route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run",
    ]:
        if collapse_ws(snippet) not in collapsed:
            raise RuntimeError(
                "behavior4_debug_capture_helper_dry_run missing snippet: "
                f"{snippet}"
            )


def check_docs(root: Path) -> None:
    readme = (root / "README_RECONSTRUCTION.md").read_text(encoding="utf-8")
    status = (root / "RECOVERY_STATUS.md").read_text(encoding="utf-8")
    for text, label in [(readme, "README"), (status, "RECOVERY_STATUS")]:
        require(text, "tools/capture_original_behavior4_debug.sh", label)
        require(text, "monster_behavior4_target_selection", label)
    require(status, "debugger_seeded", "RECOVERY_STATUS")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check behavior-4 DOSBox-debug capture helper coverage."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    check_script(root / "tools" / "capture_original_behavior4_debug.sh")
    check_cmake(root / "CMakeLists.txt")
    check_docs(root)
    print(
        "behavior4_debug_capture_helper=ok "
        f"scenarios={len(SCENARIOS)} anchors={len(BREAKPOINTS)} "
        f"outputs={len(OUTPUTS)} cmake_test=1 docs=2"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
