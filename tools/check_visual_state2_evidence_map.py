#!/usr/bin/env python3
"""Check state-2 visual/death/reentry evidence handoff coverage."""

from __future__ import annotations

import argparse
from pathlib import Path


STATE2_FIXTURES = (
    "state2_runtime_frame_oracle_bad_breakpoint.txt",
    "state2_runtime_frame_oracle_bad_segment.txt",
    "state2_runtime_frame_oracle_missing_global_byte.txt",
    "state2_runtime_frame_oracle_missing_table_row.txt",
    "state2_runtime_frame_oracle_original.txt",
    "state2_runtime_frame_oracle_synthetic.txt",
)

VISUAL_FIXTURES = (
    "visual_table_oracle_bad_row_byte3_sprite.txt",
    "visual_table_oracle_bad_segment.txt",
    "visual_table_oracle_missing_row_byte.txt",
    "visual_table_oracle_original_state2_runtime.txt",
    "visual_table_oracle_sprite_without_row.txt",
    "visual_table_oracle_synthetic.txt",
)

STATE2_TESTS = tuple(Path(name).stem for name in STATE2_FIXTURES)
VISUAL_TESTS = tuple(Path(name).stem for name in VISUAL_FIXTURES)

MODEL_TESTS = (
    "autoplayer_death_reentry_dummy",
    "autoplayer_death_visuals_dummy",
    "player_damage_sound",
    "original_damage_counters",
    "player_state2_death_fields",
    "original_state2_return_model",
    "state2_animation_init_model",
    "state2_animation_advance_model",
    "state2_effect_placement_model",
    "player_state2_return_active",
    "monster_contact_damage_live",
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def require_test(cmake: str, name: str) -> None:
    require(cmake, f"add_test(NAME {name}", f"cmake:{name}")
    require(cmake, f"set_tests_properties({name}", f"cmake:{name}")


def require_fixture_set(root: Path, names: tuple[str, ...], pattern: str) -> int:
    fixture_dir = root / "tests" / "fixtures" / "dosbox"
    found = sorted(
        path.name
        for path in fixture_dir.glob(pattern)
        if not path.name.endswith("-LIS.txt")
    )
    expected = sorted(names)
    if found != expected:
        raise RuntimeError(
            f"fixture set mismatch pattern={pattern} "
            f"expected={','.join(expected)} found={','.join(found)}"
        )
    return len(found)


def check_cmake(root: Path) -> tuple[int, int, int, int]:
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    require(cmake, "check_visual_state2_evidence_map.py", "cmake:checker")
    require_test(cmake, "visual_state2_evidence_map")

    for name in STATE2_TESTS:
        require_test(cmake, name)
        require(cmake, "--debug-state2-runtime-frame-oracle", f"cmake:{name}")
    for name in VISUAL_TESTS:
        require_test(cmake, name)
        require(cmake, "--debug-visual-table-oracle", f"cmake:{name}")
    for name in MODEL_TESTS:
        require_test(cmake, name)

    state2_ctests = sum(
        1 for name in STATE2_TESTS if f"add_test(NAME {name}" in cmake
    )
    visual_ctests = sum(
        1 for name in VISUAL_TESTS if f"add_test(NAME {name}" in cmake
    )
    return state2_ctests, visual_ctests, len(MODEL_TESTS), 1


def check_source(root: Path) -> int:
    source = (root / "src" / "main.cpp").read_text(encoding="utf-8")
    for snippet in (
        "--debug-state2-runtime-frame-oracle",
        "--debug-visual-table-oracle",
        "debugState2RuntimeFrameOracle",
        "debugVisualTableOracle",
        "constexpr uint16_t kFrameEntryBase = 0xc322",
        "table_entry_base=0xc322",
        "effect0_xy=",
        "visual_claim=0",
    ):
        require(source, snippet, "source")
    return 2


def check_docs(root: Path) -> int:
    readme = (root / "README_RECONSTRUCTION.md").read_text(encoding="utf-8")
    ghidra = (root / "docs" / "GHIDRA_NOTES.md").read_text(encoding="utf-8")
    status = (root / "RECOVERY_STATUS.md").read_text(encoding="utf-8")

    for snippet in (
        "--debug-state2-runtime-frame-oracle",
        "DS:c322",
        "DS:c21e",
        "01ED:7C89",
        "visual_claim=0",
    ):
        require(readme, snippet, "README_RECONSTRUCTION.md")

    for snippet in (
        "1000:06ab",
        "1000:3108..311d",
        "1000:6053..6156",
        "1000:7df9..7e70",
        "--debug-state2-runtime-frame-oracle",
        "--debug-visual-table-oracle",
        "DS:006a",
        "DS:006c",
        "DS:006d",
        "DS:c322",
        "DS:c21e",
        "01ED:7C89",
        "visual_claim=0",
    ):
        require(ghidra, snippet, "docs/GHIDRA_NOTES.md")

    for snippet in (
        "--debug-visual-table-oracle",
        "DS:c322",
        "DS:c21e",
        "visual_claim=0",
    ):
        require(status, snippet, "RECOVERY_STATUS.md")
    return 3


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check state-2 visual evidence map coverage."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    state2_fixtures = require_fixture_set(
        root, STATE2_FIXTURES, "state2_runtime_frame_oracle*.txt"
    )
    visual_fixtures = require_fixture_set(
        root, VISUAL_FIXTURES, "visual_table_oracle*.txt"
    )
    state2_ctests, visual_ctests, model_ctests, checker_ctests = check_cmake(root)
    oracle_flags = check_source(root)
    docs = check_docs(root)

    print(
        "visual_state2_evidence_map=ok "
        f"state2_fixtures={state2_fixtures} "
        f"visual_fixtures={visual_fixtures} "
        f"state2_ctests={state2_ctests} "
        f"visual_ctests={visual_ctests} "
        f"model_ctests={model_ctests} "
        f"oracle_flags={oracle_flags} "
        f"docs={docs} checker_ctests={checker_ctests}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
