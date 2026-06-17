#!/usr/bin/env python3
"""Check sound-callsite process-memory capture helper wiring."""

from __future__ import annotations

import argparse
from pathlib import Path


TARGETS = {
    "contact_scanner_runtime_sound": ("1000:5E81", "contact_scanner"),
    "actor_update_runtime_cursor_0024_sound": ("1000:6844", "actor_update"),
    "actor_update_runtime_cursor_0035_sound": ("1000:6924", "actor_update"),
    "actor_update_runtime_cursor_0021_sound": ("1000:7386", "actor_update"),
}

CMAKE_TESTS = {
    "contact_scanner_runtime_sound": (
        "sound_callsite_procmem_helper_contact_scanner_dry_run",
        "/tmp/lezac-sound-callsite-procmem-contact-dry-run",
    ),
    "actor_update_runtime_cursor_0024_sound": (
        "sound_callsite_procmem_helper_actor_update_cursor_0024_dry_run",
        "/tmp/lezac-sound-callsite-procmem-actor-update-0024-dry-run",
    ),
    "actor_update_runtime_cursor_0035_sound": (
        "sound_callsite_procmem_helper_actor_update_cursor_0035_dry_run",
        "/tmp/lezac-sound-callsite-procmem-actor-update-0035-dry-run",
    ),
    "actor_update_runtime_cursor_0021_sound": (
        "sound_callsite_procmem_helper_actor_update_cursor_0021_dry_run",
        "/tmp/lezac-sound-callsite-procmem-actor-update-0021-dry-run",
    ),
}


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
        next_test = text.find("\n        add_test(NAME ", prop_start + 1)
    if next_test < 0:
        next_test = text.find("\n        endif()", prop_start + 1)
    if next_test < 0:
        next_test = len(text)
    return text[start:next_test]


def check_script(script_path: Path) -> None:
    text = script_path.read_text(encoding="utf-8")
    for snippet in [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "usage: $0 out_dir [asset_dir] target",
        "capture=sound_callsite_process_memory",
        "source=dosbox-debug-process-memory",
        "capture=sound_callsite",
        "instrumented_runtime_child_memory=1",
        "contact_scanner_runtime_sound",
        "actor_update_runtime_cursor_0024_sound",
        "actor_update_runtime_cursor_0035_sound",
        "actor_update_runtime_cursor_0021_sound",
        'candidate_fixture="$out_dir/${target}_sound_callsite_candidate.txt"',
        "environment_preflight_log=\"$out_dir/environment_preflight.log\"",
        "preflight_original_evidence_environment.py",
        "--probe-wsl",
        "--require-wsl-bash-on-windows",
        "--require-procmem-capture",
        "run_environment_preflight",
        "freeze_was_observed",
        "classify_promotion_status",
        "environment_preflight=dry_run",
        "environment_preflight=skipped",
        "environment_preflight=ok",
        "promotion_status=dry_run",
        "promotion_status=$promotion_status",
        "promotion_blocker=$promotion_blocker",
        "promotion_blocker=no_observed_freeze",
        "freeze_runtime_patch_applied=$freeze_runtime_patch_applied",
        "write_candidate_skeleton",
        "LEZAC_SOUND_CALLSITE_PROCMEM_DRY_RUN",
        "LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM",
        "LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION",
        "LEZAC_SOUND_CALLSITE_ROUTE_STEPS",
        "LEZAC_SOUND_CALLSITE_RUNTIME_FREEZE_BEFORE_ROUTE",
        "--route-step \"$route_step\"",
        "capture_original_explosion_procmem.py",
        "--runtime-freeze-before-bomb",
        "--runtime-freeze-before-route",
        "--freeze-ghidra-offset \"$ghidra\"",
        "sound_request label=$label",
        "route_state_dumps.txt",
        "choose an output directory outside the repository",
        "missing $asset_dir/LEZAC.EXE",
        "visual_claim=0",
    ]:
        require(text, snippet, "script")
    for target, (ghidra, region) in TARGETS.items():
        require(text, target, "script")
        require(text, ghidra, "script")
        require(text, region, "script")


def check_cmake(cmake_path: Path) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    require(text, "find_program(BASH_EXECUTABLE bash)", "CMake")
    for target, (test_name, out_dir) in CMAKE_TESTS.items():
        block = test_block(text, test_name)
        collapsed = collapse_ws(block)
        ghidra, region = TARGETS[target]
        for snippet in [
            "LEZAC_SOUND_CALLSITE_PROCMEM_DRY_RUN=1",
            "${BASH_EXECUTABLE}",
            "tools/capture_original_sound_callsite_procmem.sh",
            out_dir,
            "${CMAKE_CURRENT_SOURCE_DIR}",
            target,
            (
                "^sound_callsite_procmem=ok mode=dry_run "
                f"target={target} ghidra={ghidra} "
                f"capture_class=actor_contact_runtime static_region={region} "
                ".*procmem_out=.*environment_preflight=dry_run"
            ),
        ]:
            if collapse_ws(snippet) not in collapsed:
                raise RuntimeError(f"{test_name} missing snippet: {snippet}")

    block = test_block(text, "sound_callsite_procmem_helper_expectations")
    collapsed = collapse_ws(block)
    for snippet in [
        "tools/check_sound_callsite_procmem_helper.py",
        "${CMAKE_CURRENT_SOURCE_DIR}",
        "^sound_callsite_procmem_helper=ok targets=4 cmake_tests=4 docs=3",
    ]:
        if collapse_ws(snippet) not in collapsed:
            raise RuntimeError(
                "sound_callsite_procmem_helper_expectations missing snippet: "
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
        require(text, "tools/capture_original_sound_callsite_procmem.sh", label)
        require(text, "contact_scanner_runtime_sound", label)
        require(text, "actor_update_runtime_cursor_0024_sound", label)
        require(text, "actor_update_runtime_cursor_0035_sound", label)
        require(text, "actor_update_runtime_cursor_0021_sound", label)
        require(text, "LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM=1", label)
        require(text, "sound_callsite_procmem", label)
        require(text, "promotion_blocker", label)
        require(text, "candidate", label)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check sound-callsite process-memory helper coverage."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    check_script(root / "tools" / "capture_original_sound_callsite_procmem.sh")
    check_cmake(root / "CMakeLists.txt")
    check_docs(root)
    print(
        "sound_callsite_procmem_helper=ok "
        f"targets={len(TARGETS)} cmake_tests={len(CMAKE_TESTS)} docs=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
