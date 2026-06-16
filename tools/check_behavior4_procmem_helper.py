#!/usr/bin/env python3
"""Check behavior-4 process-memory capture helper wiring."""

from __future__ import annotations

import argparse
from pathlib import Path


TARGETS = {
    "spawner_loop_start": ("1000:7A6B", "spawner_loop"),
    "spawner_loop_end": ("1000:7C2C", "spawner_loop"),
    "behavior4_branch_start": ("1000:728C", "behavior4_branch"),
    "behavior4_branch_end": ("1000:731B", "behavior4_branch"),
    "integration_8_8_start": ("1000:73E5", "integration_8_8"),
    "integration_8_8_end": ("1000:741B", "integration_8_8"),
}

CMAKE_TESTS = {
    "spawner_loop_start": (
        "behavior4_procmem_helper_spawner_loop_start_dry_run",
        "/tmp/lezac-behavior4-procmem-spawner-start-dry-run",
    ),
    "spawner_loop_end": (
        "behavior4_procmem_helper_spawner_loop_end_dry_run",
        "/tmp/lezac-behavior4-procmem-spawner-end-dry-run",
    ),
    "behavior4_branch_start": (
        "behavior4_procmem_helper_branch_start_dry_run",
        "/tmp/lezac-behavior4-procmem-branch-start-dry-run",
    ),
    "behavior4_branch_end": (
        "behavior4_procmem_helper_branch_end_dry_run",
        "/tmp/lezac-behavior4-procmem-branch-end-dry-run",
    ),
    "integration_8_8_start": (
        "behavior4_procmem_helper_integration_start_dry_run",
        "/tmp/lezac-behavior4-procmem-integration-start-dry-run",
    ),
    "integration_8_8_end": (
        "behavior4_procmem_helper_integration_end_dry_run",
        "/tmp/lezac-behavior4-procmem-integration-end-dry-run",
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
        "capture=behavior4_process_memory",
        "source=dosbox-debug-process-memory",
        "capture=behavior4_runtime",
        "instrumented_runtime_child_memory=1",
        'candidate_fixture="$out_dir/${target}_behavior4_candidate.txt"',
        "environment_preflight_log=\"$out_dir/environment_preflight.log\"",
        "preflight_original_evidence_environment.py",
        "--probe-wsl",
        "--require-wsl-bash-on-windows",
        "--require-procmem-capture",
        "run_environment_preflight",
        "environment_preflight=dry_run",
        "environment_preflight=skipped",
        "environment_preflight=ok",
        "write_candidate_skeleton",
        "LEZAC_BEHAVIOR4_PROCMEM_DRY_RUN",
        "LEZAC_BEHAVIOR4_APPROVE_PROCMEM",
        "LEZAC_BEHAVIOR4_APPROVE_RUNTIME_INSTRUMENTATION",
        "LEZAC_BEHAVIOR4_ROUTE_STEPS",
        "LEZAC_BEHAVIOR4_RUNTIME_FREEZE_BEFORE_ROUTE",
        "--route-step \"$route_step\"",
        "capture_original_explosion_procmem.py",
        "--runtime-freeze-before-bomb",
        "--runtime-freeze-before-route",
        "--freeze-ghidra-offset \"$ghidra\"",
        "spawner index=<index> behavior=4",
        "actor_before slot=<slot> behavior=4",
        "actor_after slot=<slot> behavior=4",
        "players p1_dead=<0-or-1>",
        "route_state_dumps.txt",
        "runtime_metadata=observed",
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
            "LEZAC_BEHAVIOR4_PROCMEM_DRY_RUN=1",
            "${BASH_EXECUTABLE}",
            "tools/capture_original_behavior4_procmem.sh",
            out_dir,
            "${CMAKE_CURRENT_SOURCE_DIR}",
            target,
            (
                "^behavior4_procmem=ok mode=dry_run "
                f"target={target} ghidra={ghidra} "
                f"capture_class=behavior4_runtime static_region={region} "
                ".*procmem_out=.*environment_preflight=dry_run"
            ),
        ]:
            if collapse_ws(snippet) not in collapsed:
                raise RuntimeError(f"{test_name} missing snippet: {snippet}")

    block = test_block(text, "behavior4_procmem_helper_expectations")
    collapsed = collapse_ws(block)
    for snippet in [
        "tools/check_behavior4_procmem_helper.py",
        "${CMAKE_CURRENT_SOURCE_DIR}",
        "^behavior4_procmem_helper=ok targets=6 cmake_tests=6 docs=3",
    ]:
        if collapse_ws(snippet) not in collapsed:
            raise RuntimeError(
                "behavior4_procmem_helper_expectations missing snippet: "
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
        require(text, "tools/capture_original_behavior4_procmem.sh", label)
        require(text, "behavior4_branch_start", label)
        require(text, "LEZAC_BEHAVIOR4_APPROVE_PROCMEM=1", label)
        require(text, "behavior4_procmem", label)
        require(text, "candidate", label)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check behavior-4 process-memory helper coverage."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    check_script(root / "tools" / "capture_original_behavior4_procmem.sh")
    check_cmake(root / "CMakeLists.txt")
    check_docs(root)
    print(
        "behavior4_procmem_helper=ok "
        f"targets={len(TARGETS)} cmake_tests={len(CMAKE_TESTS)} docs=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
