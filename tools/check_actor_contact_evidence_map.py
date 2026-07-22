#!/usr/bin/env python3
"""Check actor/contact evidence handoff wiring across docs, tools, and tests."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


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

GATE_TARGETS = (
    "actor_update_gate5",
    "actor_update_gate5_integration",
    "actor_update_gate5_exit",
    "actor_update_gate6",
    "contact_scanner_callsite",
)

ACTOR_UPDATE_FIXTURES = (
    "actor_update_runtime_oracle_synthetic.txt",
    "actor_update_runtime_oracle_dispatch_gates_synthetic.txt",
    "actor_update_runtime_oracle_bad_segment.txt",
    "actor_update_runtime_oracle_missing_contact_scan.txt",
    "actor_update_runtime_oracle_bad_actor_slot.txt",
)

CONTACT_SCANNER_FIXTURES = (
    "contact_scanner_runtime_oracle_synthetic.txt",
    "contact_scanner_runtime_oracle_bad_segment.txt",
    "contact_scanner_runtime_oracle_missing_contact_scan.txt",
    "contact_scanner_runtime_oracle_missing_dimensions.txt",
    "contact_scanner_runtime_oracle_bad_subject_flags.txt",
)

EXPECTED_CTESTS = (
    "actor_dispatch_gate_sweep_summary_expectations",
    "actor_dispatch_ready_manifest_expectations",
    "actor_dispatch_ready_results_expectations",
    "actor_dispatch_ready_pipeline_expectations",
    "actor_contact_route_sweep_dry_run",
    "actor_dispatch_gate_sweep_dry_run",
    "actor_contact_callsite_scan",
    "actor_contact_callsite_context",
    "actor_update_dispatch_gates",
    "actor_update_debug_capture_helper_dry_run",
    "contact_scanner_debug_capture_helper_dry_run",
    "actor_contact_procmem_helper_dry_run",
    "actor_update_debug_capture_helper_expectations",
    "contact_scanner_debug_capture_helper_expectations",
    "actor_contact_procmem_helper_expectations",
    "actor_update_runtime_oracle_fixture_expectations",
    "contact_scanner_runtime_oracle_fixture_expectations",
    "actor_update_runtime_oracle_synthetic",
    "actor_update_runtime_oracle_dispatch_gates_synthetic",
    "actor_update_runtime_oracle_bad_segment",
    "actor_update_runtime_oracle_missing_contact_scan",
    "actor_update_runtime_oracle_bad_actor_slot",
    "contact_scanner_runtime_oracle_synthetic",
    "contact_scanner_runtime_oracle_bad_segment",
    "contact_scanner_runtime_oracle_missing_contact_scan",
    "contact_scanner_runtime_oracle_missing_dimensions",
    "contact_scanner_runtime_oracle_bad_subject_flags",
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise RuntimeError(f"{label}: missing {needle!r}")


def require_test(cmake_text: str, name: str) -> None:
    if not re.search(rf"add_test\(NAME\s+{re.escape(name)}\b", cmake_text):
        raise RuntimeError(f"CMakeLists.txt: missing CTest {name!r}")


def require_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing file: {path}")


def require_all_targets(text: str, label: str, anchors: bool = True) -> None:
    for target, anchor in TARGETS.items():
        require(text, target, label)
        if anchors:
            require(text, anchor, label)


def check_docs(readme: str, ghidra: str, status: str) -> None:
    for anchor in ("1000:5CB0..604F", "1000:6053..777F"):
        require(readme, anchor, "README")
        require(ghidra, anchor.lower(), "GHIDRA_NOTES")
    for needle in (
        "--debug-actor-update-runtime-oracle",
        "--debug-contact-scanner-runtime-oracle",
        "tools/capture_original_actor_update_debug.sh",
        "tools/capture_original_contact_scanner_debug.sh",
        "tools/capture_original_actor_contact_procmem.sh",
        "tools/sweep_original_actor_contact_routes.py",
        "tools/sweep_original_actor_dispatch_gates.py",
        "tools/summarize_actor_dispatch_gate_sweep.py",
        "tools/run_actor_dispatch_ready_manifest.py",
        "tools/summarize_actor_dispatch_ready_results.py",
        "candidate_fixture.txt",
        "visual_claim=0",
        "dispatch_gates=",
    ):
        require(readme, needle, "README")
    for target in TARGETS:
        require(readme, target, "README")

    for needle in (
        "contact_scanner_callsite",
        "dispatch_gates=",
        "tools/check_actor_contact_callsite_context.py",
        "tools/check_actor_update_dispatch_gates.py",
        "tools/sweep_original_actor_dispatch_gates.py",
        "1000:6555",
        "1000:654E",
        "1000:65A2",
        "1000:7595",
    ):
        require(ghidra, needle, "GHIDRA_NOTES")
    require(status, "tools/summarize_actor_dispatch_gate_sweep.py", "RECOVERY_STATUS")
    require(status, "tools/run_actor_dispatch_ready_manifest.py", "RECOVERY_STATUS")
    require(status, "tools/summarize_actor_dispatch_ready_results.py", "RECOVERY_STATUS")


def check_source(source: str) -> None:
    for needle in (
        "--debug-actor-update-runtime-oracle",
        "--debug-contact-scanner-runtime-oracle",
        "actor_update_runtime_oracle=ok",
        "contact_scanner_runtime_oracle=ok",
        "runtime_cs=",
        "runtime_ds=",
        "contact_flags=",
        "scan_subject=",
        "tile_probe=",
        "dispatch_gates=",
        "overlap=",
        "visual_claim=0",
        "contact_scan_missing",
        "breakpoint_segment_mismatch",
    ):
        require(source, needle, "src/main.cpp")


def check_tools(root: Path) -> None:
    procmem = read_text(root / "tools" / "capture_original_actor_contact_procmem.sh")
    require_all_targets(procmem, "capture_original_actor_contact_procmem.sh")
    for needle in (
        "required_actor_update_breaks=1000:5CB0,1000:604F,1000:6053,1000:777F",
        "dispatch_gate_candidate=$dispatch_gate_label",
        "dispatch_gates=<emitted-by-oracle-after-required-breaks-and-semantic-records>",
        "route_state_dumps.txt",
        "LEZAC_ACTOR_CONTACT_APPROVE_PROCMEM",
        "LEZAC_ACTOR_CONTACT_APPROVE_RUNTIME_INSTRUMENTATION",
        "LEZAC_ACTOR_CONTACT_RUNTIME_FREEZE_BEFORE_ROUTE",
        "--runtime-freeze-before-route",
        "--runtime-freeze-before-bomb",
    ):
        require(procmem, needle, "capture_original_actor_contact_procmem.sh")

    update_debug = read_text(root / "tools" / "capture_original_actor_update_debug.sh")
    for needle in (
        "capture=actor_update_runtime",
        "anchors=1000:5CB0..604F,1000:6053..777F",
        "BP <CS>:5CB0",
        "BP <CS>:604F",
        "BP <CS>:6053",
        "BP <CS>:777F",
        "fixture_command=./build/lezac_cpp --debug-actor-update-runtime-oracle",
    ):
        require(update_debug, needle, "capture_original_actor_update_debug.sh")

    scanner_debug = read_text(
        root / "tools" / "capture_original_contact_scanner_debug.sh"
    )
    for needle in (
        "capture=contact_scanner_runtime",
        "anchors=1000:5CB0..604F",
        "BP <CS>:5CB0",
        "BP <CS>:604F",
        "fixture_command=./build/lezac_cpp --debug-contact-scanner-runtime-oracle",
    ):
        require(scanner_debug, needle, "capture_original_contact_scanner_debug.sh")

    callsite_scan = read_text(root / "tools" / "check_actor_contact_callsite_scan.py")
    for needle in ("0x5CB0", "0x604F", "0x6555", "0x6053", "e858f7"):
        require(callsite_scan, needle, "check_actor_contact_callsite_scan.py")

    callsite_context = read_text(
        root / "tools" / "check_actor_contact_callsite_context.py"
    )
    for needle in (
        "0x654E",
        "0x6555",
        "0x5CB0",
        "0x73E5",
        "0x65A2",
        "0x65D7",
    ):
        require(callsite_context, needle, "check_actor_contact_callsite_context.py")

    dispatch_gates = read_text(root / "tools" / "check_actor_update_dispatch_gates.py")
    for needle in ("0x6053", "0x777F", "0x654E", "0x65A2", "0x7595", "0x73E5"):
        require(dispatch_gates, needle, "check_actor_update_dispatch_gates.py")

    procmem_helper = read_text(root / "tools" / "check_actor_contact_procmem_helper.py")
    require_all_targets(procmem_helper, "check_actor_contact_procmem_helper.py")

    route_sweep = read_text(root / "tools" / "sweep_original_actor_contact_routes.py")
    dispatch_sweep = read_text(
        root / "tools" / "sweep_original_actor_dispatch_gates.py"
    )
    require_all_targets(route_sweep, "sweep_original_actor_contact_routes.py", anchors=False)
    for target in GATE_TARGETS:
        require(dispatch_sweep, target, "sweep_original_actor_dispatch_gates.py")

    summary = read_text(root / "tools" / "summarize_actor_dispatch_gate_sweep.py")
    for needle in (
        "--debug-actor-update-runtime-oracle",
        "--debug-contact-scanner-runtime-oracle",
        "candidate_status=",
        "oracle_command=",
        "actor_dispatch_gate",
    ):
        require(summary, needle, "summarize_actor_dispatch_gate_sweep.py")

    runner = read_text(root / "tools" / "run_actor_dispatch_ready_manifest.py")
    results = read_text(root / "tools" / "summarize_actor_dispatch_ready_results.py")
    for needle in (
        "--debug-actor-update-runtime-oracle",
        "--debug-contact-scanner-runtime-oracle",
    ):
        require(runner, needle, "run_actor_dispatch_ready_manifest.py")
    require(results, "actor_dispatch_ready_result_summary=ok", "ready results summarizer")


def check_fixtures(root: Path) -> None:
    fixture_dir = root / "tests" / "fixtures" / "dosbox"
    for filename in ACTOR_UPDATE_FIXTURES + CONTACT_SCANNER_FIXTURES:
        require_file(fixture_dir / filename)
    actor_paths = sorted(fixture_dir.glob("actor_update_runtime_oracle*.txt"))
    scanner_paths = sorted(fixture_dir.glob("contact_scanner_runtime_oracle*.txt"))
    if [path.name for path in actor_paths] != sorted(ACTOR_UPDATE_FIXTURES):
        raise RuntimeError("actor_update runtime fixture set changed")
    if [path.name for path in scanner_paths] != sorted(CONTACT_SCANNER_FIXTURES):
        raise RuntimeError("contact_scanner runtime fixture set changed")


def check_cmake(cmake: str) -> None:
    require(cmake, "tools/check_actor_contact_evidence_map.py", "CMakeLists.txt")
    for test_name in EXPECTED_CTESTS:
        require_test(cmake, test_name)
    require(
        cmake,
        "^actor_update_runtime_oracle_fixtures=ok files=5 valid=2 malformed=3",
        "CMakeLists.txt",
    )
    require(
        cmake,
        "^contact_scanner_runtime_oracle_fixtures=ok files=5 valid=1 malformed=4",
        "CMakeLists.txt",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check actor/contact recovery evidence handoff consistency."
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
    check_source(read_text(root / "src" / "app" / "app.cpp"))
    check_tools(root)
    check_fixtures(root)
    check_cmake(cmake)

    print(
        "actor_contact_evidence_map=ok "
        f"targets={len(TARGETS)} "
        f"gate_targets={len(GATE_TARGETS)} "
        f"actor_update_fixtures={len(ACTOR_UPDATE_FIXTURES)} "
        f"contact_scanner_fixtures={len(CONTACT_SCANNER_FIXTURES)} "
        f"ctests={len(EXPECTED_CTESTS)} "
        "oracle_flags=2 docs=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
