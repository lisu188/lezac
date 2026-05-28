#!/usr/bin/env python3
"""Check that ready-fixture provenance rules are documented and enforced."""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

from ready_result_fixture_guardrails import read_runtime_ledger_entries


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
    "EXPECTED_RUNTIME_EVIDENCE_LEDGER_KIND",
    "duplicate runtime_evidence_ledger",
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


def write_ledger(root: Path, lines: list[str]) -> None:
    ledger = root / "docs" / "recovery" / "runtime_evidence_ledger.md"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("\n".join(lines) + "\n", encoding="ascii")


def ledger_lines(*extra_top_level: str) -> list[str]:
    lines = [
        "# Runtime Evidence Ledger",
        "",
        "runtime_evidence_ledger=non_visual",
        *extra_top_level,
        "original_runtime_fixture_count=1",
        "",
        "```text",
        "- fixture=<name>.txt visual_claim=0 evidence=runtime_cs_runtime_ds_temp_copy docs=<path>",
        "```",
        "",
        "Current original-runtime fixtures:",
        "",
        "- fixture=sample_original.txt visual_claim=0 evidence=runtime_cs_runtime_ds_temp_copy docs=docs/recovery/original_runtime_fixture_notes.md",
    ]
    return lines


def require_ledger_error(lines: list[str], snippet: str, case: str) -> None:
    with tempfile.TemporaryDirectory(prefix="lezac-ledger-selftest-") as tmp:
        root = Path(tmp)
        write_ledger(root, lines)
        try:
            read_runtime_ledger_entries(root)
        except ValueError as exc:
            if snippet not in str(exc):
                raise RuntimeError(
                    f"{case} missing error snippet {snippet!r}: {exc}"
                ) from exc
            return
    raise RuntimeError(f"{case} unexpectedly passed")


def check_ledger_selftests() -> int:
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-ledger-selftest-") as tmp:
        root = Path(tmp)
        write_ledger(root, ledger_lines())
        entries = read_runtime_ledger_entries(root)
        if sorted(entries) != ["sample_original.txt"]:
            raise RuntimeError(f"valid ledger returned {entries!r}")
        cases += 1

    missing_kind = [
        line for line in ledger_lines() if not line.startswith("runtime_evidence_ledger=")
    ]
    require_ledger_error(
        missing_kind,
        "runtime evidence ledger missing runtime_evidence_ledger",
        "missing_kind",
    )
    cases += 1

    require_ledger_error(
        ledger_lines("runtime_evidence_ledger=non_visual"),
        "duplicate runtime_evidence_ledger",
        "duplicate_kind",
    )
    cases += 1

    wrong_kind = [
        "runtime_evidence_ledger=visual" if line == "runtime_evidence_ledger=non_visual" else line
        for line in ledger_lines()
    ]
    require_ledger_error(
        wrong_kind,
        "runtime_evidence_ledger='visual'; expected 'non_visual'",
        "wrong_kind",
    )
    cases += 1

    missing_count = [
        line
        for line in ledger_lines()
        if not line.startswith("original_runtime_fixture_count=")
    ]
    require_ledger_error(
        missing_count,
        "runtime evidence ledger missing original_runtime_fixture_count",
        "missing_count",
    )
    cases += 1

    require_ledger_error(
        ledger_lines("original_runtime_fixture_count=1"),
        "duplicate original_runtime_fixture_count",
        "duplicate_count",
    )
    cases += 1

    invalid_count = [
        "original_runtime_fixture_count=many"
        if line == "original_runtime_fixture_count=1"
        else line
        for line in ledger_lines()
    ]
    require_ledger_error(
        invalid_count,
        "invalid original_runtime_fixture_count: 'many'",
        "invalid_count",
    )
    cases += 1

    negative_count = [
        "original_runtime_fixture_count=-1"
        if line == "original_runtime_fixture_count=1"
        else line
        for line in ledger_lines()
    ]
    require_ledger_error(
        negative_count,
        "original_runtime_fixture_count must be non-negative",
        "negative_count",
    )
    cases += 1

    mismatched_count = [
        "original_runtime_fixture_count=2"
        if line == "original_runtime_fixture_count=1"
        else line
        for line in ledger_lines()
    ]
    require_ledger_error(
        mismatched_count,
        "original_runtime_fixture_count=2 does not match ledger entries=1",
        "mismatched_count",
    )
    cases += 1
    return cases


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
    ledger_selftests = check_ledger_selftests()
    print(
        "ready_fixture_provenance_contract=ok "
        "docs=1 validator=1 writers=4 runners=4 result_summaries=4 "
        "dry_run_missing_fixture_bypass=4 "
        f"ledger_selftests={ledger_selftests}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
