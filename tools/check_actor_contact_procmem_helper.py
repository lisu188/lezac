#!/usr/bin/env python3
"""Check actor/contact process-memory capture helper wiring."""

from __future__ import annotations

import argparse
from pathlib import Path


TARGETS = {
    "actor_update_start": "1000:6053",
    "actor_update_end": "1000:777F",
    "actor_update_gate5": "1000:65A2",
    "actor_update_gate5_integration": "1000:65D7",
    "actor_update_gate5_exit": "1000:7595",
    "actor_update_gate6": "1000:654E",
    "contact_scanner_callsite": "1000:6555",
    "contact_scanner_start": "1000:5CB0",
    "contact_scanner_end": "1000:604F",
}

CMAKE_TESTS = {
    "actor_update_start": (
        "actor_contact_procmem_helper_dry_run",
        "/tmp/lezac-actor-contact-procmem-dry-run",
    ),
    "actor_update_end": (
        "actor_contact_procmem_helper_actor_update_end_dry_run",
        "/tmp/lezac-actor-contact-procmem-actor-update-end-dry-run",
    ),
    "actor_update_gate5": (
        "actor_contact_procmem_helper_actor_update_gate5_dry_run",
        "/tmp/lezac-actor-contact-procmem-gate5-dry-run",
    ),
    "actor_update_gate5_integration": (
        "actor_contact_procmem_helper_actor_update_gate5_integration_dry_run",
        "/tmp/lezac-actor-contact-procmem-gate5-integration-dry-run",
    ),
    "actor_update_gate5_exit": (
        "actor_contact_procmem_helper_actor_update_gate5_exit_dry_run",
        "/tmp/lezac-actor-contact-procmem-gate5-exit-dry-run",
    ),
    "actor_update_gate6": (
        "actor_contact_procmem_helper_actor_update_gate6_dry_run",
        "/tmp/lezac-actor-contact-procmem-gate6-dry-run",
    ),
    "contact_scanner_callsite": (
        "actor_contact_procmem_helper_contact_scanner_callsite_dry_run",
        "/tmp/lezac-actor-contact-procmem-contact-callsite-dry-run",
    ),
    "contact_scanner_start": (
        "actor_contact_procmem_helper_contact_scanner_start_dry_run",
        "/tmp/lezac-actor-contact-procmem-contact-start-dry-run",
    ),
    "contact_scanner_end": (
        "actor_contact_procmem_helper_contact_scanner_end_dry_run",
        "/tmp/lezac-actor-contact-procmem-contact-end-dry-run",
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
    require(text, "usage: $0 out_dir [asset_dir] target", "script")
    require(text, "capture=actor_contact_process_memory", "script")
    require(text, "source=dosbox-debug-process-memory", "script")
    require(text, "route=focused_no_window_original_controls_process_memory", "script")
    require(text, "visual_claim=0", "script")
    require(text, "contact_scanner_callsite", "script")
    require(text, "candidate_fixture=\"$out_dir/${target}_runtime_candidate.txt\"", "script")
    require(text, "environment_preflight_log=\"$out_dir/environment_preflight.log\"", "script")
    require(text, "preflight_original_evidence_environment.py", "script")
    require(text, "--probe-wsl", "script")
    require(text, "--require-wsl-bash-on-windows", "script")
    require(text, "--require-procmem-capture", "script")
    require(text, "run_environment_preflight", "script")
    require(text, "environment_preflight=dry_run", "script")
    require(text, "environment_preflight=skipped", "script")
    require(text, "environment_preflight=ok", "script")
    require(text, "write_candidate_skeleton", "script")
    require(text, "route_state_dumps.txt", "script")
    require(text, "LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN", "script")
    require(text, "LEZAC_ACTOR_CONTACT_APPROVE_PROCMEM", "script")
    require(text, "LEZAC_ACTOR_CONTACT_APPROVE_RUNTIME_INSTRUMENTATION", "script")
    require(text, "LEZAC_ACTOR_CONTACT_ROUTE_STEPS", "script")
    require(text, "LEZAC_ACTOR_CONTACT_RUNTIME_FREEZE_BEFORE_ROUTE", "script")
    require(text, "--route-step \"$route_step\"", "script")
    require(text, "capture_original_explosion_procmem.py", "script")
    require(text, "--runtime-freeze-before-bomb", "script")
    require(text, "--runtime-freeze-before-route", "script")
    require(text, "--freeze-ghidra-offset \"$ghidra\"", "script")
    require(text, "instrumented_freeze_observed", "script")
    require(text, "freeze_runtime_patch_applied", "script")
    require(text, "required_actor_update_breaks=1000:5CB0,1000:604F,1000:6053,1000:777F", "script")
    require(text, "dispatch_gate_candidate=$dispatch_gate_label", "script")
    require(text, "dispatch_gates=<emitted-by-oracle-after-required-breaks-and-semantic-records>", "script")
    require(text, "choose an output directory outside the repository", "script")
    require(text, "missing $asset_dir/LEZAC.EXE", "script")
    for target, ghidra in TARGETS.items():
        require(text, target, "script")
        require(text, ghidra, "script")


def check_cmake(cmake_path: Path) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    require(text, "find_program(BASH_EXECUTABLE bash)", "CMake")
    for target, (test_name, out_dir) in CMAKE_TESTS.items():
        block = test_block(text, test_name)
        collapsed = collapse_ws(block)
        ghidra = TARGETS[target]
        for snippet in [
            "LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1",
            "${BASH_EXECUTABLE}",
            "tools/capture_original_actor_contact_procmem.sh",
            out_dir,
            "${CMAKE_CURRENT_SOURCE_DIR}",
            target,
            (
                "^actor_contact_procmem=ok mode=dry_run "
                f"target={target} ghidra={ghidra} .*procmem_out="
            ),
            "environment_preflight=dry_run",
        ]:
            if collapse_ws(snippet) not in collapsed:
                raise RuntimeError(f"{test_name} missing snippet: {snippet}")

    block = test_block(text, "actor_contact_procmem_helper_expectations")
    collapsed = collapse_ws(block)
    for snippet in [
        "tools/check_actor_contact_procmem_helper.py",
        "${CMAKE_CURRENT_SOURCE_DIR}",
        "^actor_contact_procmem_helper=ok targets=9 cmake_tests=9 docs=2",
    ]:
        if collapse_ws(snippet) not in collapsed:
            raise RuntimeError(
                "actor_contact_procmem_helper_expectations missing snippet: "
                f"{snippet}"
            )


def check_docs(root: Path) -> None:
    readme = (root / "README_RECONSTRUCTION.md").read_text(encoding="utf-8")
    status = (root / "RECOVERY_STATUS.md").read_text(encoding="utf-8")
    for text, label in [(readme, "README"), (status, "RECOVERY_STATUS")]:
        require(text, "tools/capture_original_actor_contact_procmem.sh", label)
        require(text, "actor_update_start", label)
        require(text, "LEZAC_ACTOR_CONTACT_APPROVE_PROCMEM=1", label)
        require(text, "environment_preflight", label)
        require(text, "candidate", label)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check actor/contact process-memory helper coverage."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    check_script(root / "tools" / "capture_original_actor_contact_procmem.sh")
    check_cmake(root / "CMakeLists.txt")
    check_docs(root)
    print(
        "actor_contact_procmem_helper=ok "
        f"targets={len(TARGETS)} cmake_tests={len(CMAKE_TESTS)} docs=2"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
