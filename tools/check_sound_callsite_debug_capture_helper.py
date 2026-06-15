#!/usr/bin/env python3
"""Check sound-callsite DOSBox-debug capture helper wiring."""

from __future__ import annotations

import argparse
from pathlib import Path


SCENARIOS = {
    "bomb_object_sound": ("6CB3", "0x0000", "3"),
    "bomb_place_sound": ("557B", "0xea74", "3"),
    "portal_teleport_sound": ("5999", "0x001a", "4"),
    "tile_trigger_sound": ("5740", "0x0027", "6"),
    "bonus_pickup_sound": ("6E4B", "0x0008", "5"),
    "player_damage_sound": ("7F84", "0x002d", "4"),
    "player_death_sound": ("30A3", "0x0056", "5"),
}

OUTPUTS = [
    "manifest.txt",
    "raw_debugger_dump.txt",
    "candidate_fixture.txt",
    "debugger_commands.txt",
    "debugger_commands_runtime.txt",
    "environment_preflight.log",
    "sound_callsite_debug_capture.log",
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
    next_test = text.find("\n            add_test(NAME ", prop_start + 1)
    if next_test < 0:
        next_test = text.find("\n        endif()", prop_start + 1)
    if next_test < 0:
        next_test = text.find("\n        add_test(NAME ", prop_start + 1)
    if next_test < 0:
        next_test = len(text)
    return text[start:next_test]


def check_script(script_path: Path) -> None:
    text = script_path.read_text(encoding="utf-8")
    for snippet in [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "usage: $0 out_dir [asset_dir] scenario",
        "route=debugger_seeded",
        "LEZAC_SOUND_CALLSITE_DEBUG_DRY_RUN",
        "LEZAC_SOUND_CALLSITE_DEBUG_SKIP_ENVIRONMENT_PREFLIGHT",
        "visual_claim=0",
        "capture=sound_callsite",
        "candidate_fixture=\"$out_dir/candidate_fixture.txt\"",
        "runtime_commands_file=\"$out_dir/debugger_commands_runtime.txt\"",
        "environment_preflight_log=\"$out_dir/environment_preflight.log\"",
        "run_environment_preflight",
        "preflight_original_evidence_environment.py",
        "--require-debug-capture",
        "--probe-wsl",
        "--require-wsl-bash-on-windows",
        "write_runtime_command_plan",
        "debugger_commands_runtime=$runtime_commands_file",
        "environment_preflight=dry_run",
        "grep -v '^#' \"$commands_file\"",
        "choose an output directory outside the repository",
        "missing $asset_dir/LEZAC.EXE",
        "dosbox-debug",
        "xvfb-run",
        "DEBUG LEZAC.EXE",
        "fixture_command=./build/lezac_cpp --debug-sound-callsite-oracle <candidate-fixture>",
        "sound_request label=$request_label",
        "D DS:2070",
        "D DS:78C0",
        "D DS:7990",
        "D DS:79C0",
        "BP <CS>:165A",
    ]:
        require(text, snippet, "script")
    for scenario, (offset, cursor, priority) in SCENARIOS.items():
        require(text, scenario, "script")
        require(text, f"callsite_offset={offset}", "script")
        require(text, f"cursor={cursor}", "script")
        require(text, f"priority={priority}", "script")
    for output in OUTPUTS:
        require(text, output, "script")


def check_cmake(cmake_path: Path) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    require(text, "find_program(BASH_EXECUTABLE bash)", "CMake")
    require(text, "foreach(sound_callsite_scenario", "CMake")
    require(text, "sound_callsite_debug_capture_helper_${sound_callsite_scenario}_dry_run", "CMake")
    require(text, "LEZAC_SOUND_CALLSITE_DEBUG_DRY_RUN=1", "CMake")
    require(text, "tools/capture_original_sound_callsite_debug.sh", "CMake")
    require(text, "${sound_callsite_scenario}", "CMake")
    require(
        text,
        "^sound_callsite_debug_capture=ok mode=dry_run scenario=${sound_callsite_scenario} route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run",
        "CMake",
    )
    for scenario in SCENARIOS:
        require(text, scenario, "CMake")

    block = test_block(text, "sound_callsite_debug_capture_helper_expectations")
    collapsed = collapse_ws(block)
    for snippet in [
        "tools/check_sound_callsite_debug_capture_helper.py",
        "${CMAKE_CURRENT_SOURCE_DIR}",
        "^sound_callsite_debug_capture_helper=ok scenarios=7 anchors=8 outputs=7 cmake_tests=7 docs=3",
    ]:
        if collapse_ws(snippet) not in collapsed:
            raise RuntimeError(
                "sound_callsite_debug_capture_helper_expectations missing snippet: "
                f"{snippet}"
            )


def check_docs(root: Path) -> None:
    readme = (root / "README_RECONSTRUCTION.md").read_text(encoding="utf-8")
    status = (root / "RECOVERY_STATUS.md").read_text(encoding="utf-8")
    ghidra = (root / "docs" / "GHIDRA_NOTES.md").read_text(encoding="utf-8")
    for text, label in [
        (readme, "README"),
        (status, "RECOVERY_STATUS"),
        (ghidra, "GHIDRA_NOTES"),
    ]:
        require(text, "tools/capture_original_sound_callsite_debug.sh", label)
        require(text, "bomb_place_sound", label)
        require(text, "player_damage_sound", label)
        require(text, "sound_callsite", label)
    require(status, "debugger_seeded", "RECOVERY_STATUS")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check sound-callsite DOSBox-debug capture helper coverage."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    check_script(root / "tools" / "capture_original_sound_callsite_debug.sh")
    check_cmake(root / "CMakeLists.txt")
    check_docs(root)
    print(
        "sound_callsite_debug_capture_helper=ok "
        f"scenarios={len(SCENARIOS)} anchors=8 outputs={len(OUTPUTS)} "
        f"cmake_tests={len(SCENARIOS)} docs=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
