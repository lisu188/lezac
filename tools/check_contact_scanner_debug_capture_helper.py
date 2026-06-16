#!/usr/bin/env python3
"""Check contact-scanner DOSBox-debug capture helper wiring."""

from __future__ import annotations

import argparse
from pathlib import Path


SCENARIOS = [
    "monster_contact_damage_live",
    "object_collision_jump_live",
    "monster_behavior4_chase",
]

ANCHORS = ["1000:5CB0..604F"]

BREAKPOINTS = ["5CB0", "604F"]

OUTPUTS = [
    "manifest.txt",
    "raw_debugger_dump.txt",
    "candidate_fixture.txt",
    "debugger_commands.txt",
    "debugger_commands_runtime.txt",
    "environment_preflight.log",
    "contact_scanner_debug_capture.log",
]

CMAKE_TESTS = [
    (
        "contact_scanner_debug_capture_helper_dry_run",
        "monster_contact_damage_live",
        "/tmp/lezac-contact-scanner-debug-dry-run",
    ),
    (
        "contact_scanner_debug_capture_helper_object_dry_run",
        "object_collision_jump_live",
        "/tmp/lezac-contact-scanner-debug-object-dry-run",
    ),
    (
        "contact_scanner_debug_capture_helper_behavior4_dry_run",
        "monster_behavior4_chase",
        "/tmp/lezac-contact-scanner-debug-behavior4-dry-run",
    ),
]


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, label: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{label} missing snippet: {snippet}")


def collapse_ws(text: str) -> str:
    return " ".join(text.split())


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


def check_script(script_path: Path) -> None:
    text = script_path.read_text(encoding="utf-8")
    require(text, "#!/usr/bin/env bash", "script")
    require(text, "set -euo pipefail", "script")
    require(text, "usage: $0 out_dir [asset_dir] scenario", "script")
    require(text, "runtime_route=debugger_seeded", "script")
    require(text, "LEZAC_CONTACT_SCANNER_DEBUG_DRY_RUN", "script")
    require(text, "LEZAC_CONTACT_SCANNER_DEBUG_SKIP_ENVIRONMENT_PREFLIGHT", "script")
    require(text, "visual_claim=0", "script")
    require(text, "candidate_fixture=\"$out_dir/candidate_fixture.txt\"", "script")
    require(text, "runtime_commands_file=\"$out_dir/debugger_commands_runtime.txt\"", "script")
    require(text, "environment_preflight_log=\"$out_dir/environment_preflight.log\"", "script")
    require(text, "run_environment_preflight", "script")
    require(text, "preflight_original_evidence_environment.py", "script")
    require(text, "--require-debug-capture", "script")
    require(text, "--probe-wsl", "script")
    require(text, "--require-wsl-bash-on-windows", "script")
    require(text, "write_runtime_command_plan", "script")
    require(text, "debugger_commands_runtime=$runtime_commands_file", "script")
    require(text, "environment_preflight=dry_run", "script")
    require(text, "grep -v '^#' \"$commands_file\"", "script")
    require(text, "capture=contact_scanner_runtime", "script")
    require(text, "scenario=$scenario", "script")
    require(text, "route=$runtime_route", "script")
    require(text, "subject_actor slot=<slot>", "script")
    require(text, "contact_scan subject_slot=<slot>", "script")
    require(text, "fixture_command=./build/lezac_cpp --debug-contact-scanner-runtime-oracle <candidate-fixture>", "script")
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
    for dump in ["D DS:7900", "D DS:79E0"]:
        require(text, dump, "script")


def check_cmake(cmake_path: Path) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    require(text, "find_program(BASH_EXECUTABLE bash)", "CMake")
    for test_name, scenario, out_dir in CMAKE_TESTS:
        block = test_block(text, test_name)
        collapsed = collapse_ws(block)
        for snippet in [
            "LEZAC_CONTACT_SCANNER_DEBUG_DRY_RUN=1",
            "${BASH_EXECUTABLE}",
            "tools/capture_original_contact_scanner_debug.sh",
            out_dir,
            "${CMAKE_CURRENT_SOURCE_DIR}",
            scenario,
            (
                "^contact_scanner_debug_capture=ok mode=dry_run "
                f"scenario={scenario} route=debugger_seeded "
                ".*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run"
            ),
        ]:
            if collapse_ws(snippet) not in collapsed:
                raise RuntimeError(f"{test_name} missing snippet: {snippet}")

    block = test_block(text, "contact_scanner_debug_capture_helper_expectations")
    collapsed = collapse_ws(block)
    for snippet in [
        "tools/check_contact_scanner_debug_capture_helper.py",
        "${CMAKE_CURRENT_SOURCE_DIR}",
        "^contact_scanner_debug_capture_helper=ok scenarios=3 anchors=2 outputs=7 cmake_tests=3 docs=2",
    ]:
        if collapse_ws(snippet) not in collapsed:
            raise RuntimeError(
                "contact_scanner_debug_capture_helper_expectations missing snippet: "
                f"{snippet}"
            )


def check_docs(root: Path) -> None:
    readme = (root / "README_RECONSTRUCTION.md").read_text(encoding="utf-8")
    status = (root / "RECOVERY_STATUS.md").read_text(encoding="utf-8")
    for text, label in [(readme, "README"), (status, "RECOVERY_STATUS")]:
        require(text, "tools/capture_original_contact_scanner_debug.sh", label)
        require(text, "monster_contact_damage_live", label)
    require(status, "debugger_seeded", "RECOVERY_STATUS")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check contact-scanner DOSBox-debug capture helper coverage."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    check_script(root / "tools" / "capture_original_contact_scanner_debug.sh")
    check_cmake(root / "CMakeLists.txt")
    check_docs(root)
    print(
        "contact_scanner_debug_capture_helper=ok "
        f"scenarios={len(SCENARIOS)} anchors={len(BREAKPOINTS)} "
        f"outputs={len(OUTPUTS)} cmake_tests={len(CMAKE_TESTS)} docs=2"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
