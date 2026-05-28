#!/usr/bin/env python3
"""Check that ready-fixture provenance rules are documented and enforced."""

from __future__ import annotations

import argparse
from pathlib import Path


DOC = Path("docs/recovery/ready_fixture_provenance_contract.md")
VALIDATOR = Path("tools/ready_result_fixture_guardrails.py")

WRITERS = [
    Path("tools/summarize_debug_capture_batch.py"),
    Path("tools/summarize_actor_dispatch_gate_sweep.py"),
    Path("tools/summarize_lane_result_route_sweep.py"),
    Path("tools/summarize_lane_write_route_sweep.py"),
]
RUNNERS = [
    Path("tools/run_debug_capture_ready_manifest.py"),
    Path("tools/run_actor_dispatch_ready_manifest.py"),
    Path("tools/run_lane_result_ready_manifest.py"),
    Path("tools/run_lane_write_ready_manifest.py"),
]
RESULT_SUMMARIES = [
    Path("tools/summarize_debug_capture_ready_results.py"),
    Path("tools/summarize_actor_dispatch_ready_results.py"),
    Path("tools/summarize_lane_result_ready_results.py"),
    Path("tools/summarize_lane_write_ready_results.py"),
]

DOC_SNIPPETS = [
    "ready_fixture_provenance_contract=1",
    "runtime_cs",
    "runtime_ds",
    "visual_claim=0",
    "temp_copy=1",
    "tests/fixtures/dosbox",
    "original",
    "docs/recovery/runtime_evidence_ledger.md",
    "docs/recovery/original_runtime_fixture_notes.md",
    "docs/recovery/visual_claim_promotions.md",
    "tools/summarize_frame_compare_bundle.py",
    "promotion_ready=1",
    "runtime_cs_runtime_ds_temp_copy",
    "tools/ready_result_fixture_guardrails.py",
    "--allow-missing-fixtures",
    "dry-run-only forensic bypass",
]

VALIDATOR_SNIPPETS = [
    "def parse_runtime_segment_value",
    "def validate_runtime_fixture_evidence",
    "runtime evidence ledger missing",
    "original_runtime_fixture_count",
    "duplicate runtime evidence ledger fixture",
    "duplicate runtime evidence ledger field",
    "visual_claim",
    "temp_copy",
    "does not match fixture",
    "runtime_cs_runtime_ds_temp_copy",
]


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def read(root: Path, path: Path) -> str:
    full_path = root / path
    if not full_path.exists():
        raise RuntimeError(f"missing {path}")
    return full_path.read_text(encoding="utf-8")


def check_doc(root: Path) -> None:
    text = read(root, DOC)
    for snippet in DOC_SNIPPETS:
        require(text, snippet, str(DOC))
    for path in WRITERS + RUNNERS + RESULT_SUMMARIES:
        require(text, path.as_posix(), str(DOC))


def check_validator(root: Path) -> None:
    text = read(root, VALIDATOR)
    for snippet in VALIDATOR_SNIPPETS:
        require(text, snippet, str(VALIDATOR))


def check_call_sites(root: Path) -> None:
    for path in WRITERS + RUNNERS + RESULT_SUMMARIES:
        text = read(root, path)
        require(text, "from ready_result_fixture_guardrails import", str(path))
        require(text, "validate_runtime_fixture_evidence", str(path))
    for path in WRITERS + RUNNERS:
        text = read(root, path)
        require(text, "parse_runtime_segment_value", str(path))
    for path in RUNNERS:
        text = read(root, path)
        require(text, "--allow-missing-fixtures", str(path))
        require(text, "--allow-missing-fixtures requires --dry-run", str(path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=str(default_repo_root()),
        help="repository root",
    )
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()

    check_doc(root)
    check_validator(root)
    check_call_sites(root)
    print(
        "ready_fixture_provenance_contract=ok "
        "docs=1 validator=1 writers=4 runners=4 result_summaries=4 "
        "dry_run_missing_fixture_bypass=4"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
