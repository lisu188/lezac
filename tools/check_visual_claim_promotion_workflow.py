#!/usr/bin/env python3
"""Check that the visual-claim promotion workflow stays wired together."""

from __future__ import annotations

import argparse
from pathlib import Path


DOC = Path("docs/recovery/visual_claim_promotions.md")

WORKFLOW_TOOLS = [
    Path("tools/summarize_frame_compare_bundle.py"),
    Path("tools/check_visual_claim_guardrail.py"),
    Path("tools/validate_visual_claim_promotion_candidate.py"),
    Path("tools/write_visual_claim_promotion_entry.py"),
    Path("tools/plan_visual_claim_promotions.py"),
    Path("tools/write_visual_claim_promotion_manifest.py"),
]

WORKFLOW_TESTS = [
    "frame_compare_bundle_summary_expectations",
    "visual_claim_guardrail",
    "visual_claim_promotion_entry_expectations",
    "visual_claim_promotion_candidate_expectations",
    "visual_claim_promotion_plan_expectations",
    "visual_claim_promotion_manifest_expectations",
]

DOC_SNIPPETS = [
    "promotion_ledger=visual_claim",
    "visual_claim=1",
    "visual_claim=0",
    "original_frame=<path>",
    "cpp_frame=<path>",
    "comparison=<path>",
    "frame_compare_bundle=<path>",
    "docs=<path>",
    "tools/summarize_frame_compare_bundle.py <bundle> --require-promotion-ready",
    "tools/validate_visual_claim_promotion_candidate.py",
    "tools/write_visual_claim_promotion_entry.py",
    "promotion=visual_claim_candidates",
    "tools/write_visual_claim_promotion_manifest.py",
    "tools/plan_visual_claim_promotions.py",
    "--write-ready-entries",
    "--require-all-ready",
    "The planner refuses to write directly",
    "tools/check_visual_claim_guardrail.py --self-test",
]

TOOL_SNIPPETS = {
    Path("tools/summarize_frame_compare_bundle.py"): [
        "promotion_ready",
        "--require-promotion-ready",
        "promotion_block_reason",
    ],
    Path("tools/check_visual_claim_guardrail.py"): [
        "LEDGER = Path(\"docs/recovery/visual_claim_promotions.md\")",
        "check_frame_compare_bundle",
        "promoted fixture missing from ledger",
        "ledger entry without promoted fixture",
        "frame_compare_bundle_not_ready",
    ],
    Path("tools/validate_visual_claim_promotion_candidate.py"): [
        "fixture_visual_claim",
        "validate_generated_entry",
        "check_frame_compare_bundle",
        "make_entry",
        "entry_valid=1",
    ],
    Path("tools/write_visual_claim_promotion_entry.py"): [
        "make_entry",
        "frame_artifacts",
        "frame_compare_bundle_not_ready",
        "no_compared_frame_labels",
        "docs_outside_recovery",
    ],
    Path("tools/plan_visual_claim_promotions.py"): [
        "PROMOTION_KIND = \"visual_claim_candidates\"",
        "validate_generated_entry",
        "write_ready_entries",
        "reject_real_ledger_target",
        "--write-ready-entries",
        "--require-all-ready",
    ],
    Path("tools/write_visual_claim_promotion_manifest.py"): [
        "PROMOTION_KIND",
        "reject_real_ledger_output",
        "resolve_bundle",
        "candidate_requires_3_or_4_values",
        "docs_outside_recovery",
    ],
}


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


def check_doc(root: Path) -> int:
    text = read(root, DOC)
    for snippet in DOC_SNIPPETS:
        require(text, snippet, str(DOC))
    for path in WORKFLOW_TOOLS:
        require(text, path.as_posix(), str(DOC))
    return 1


def check_tools(root: Path) -> int:
    for path in WORKFLOW_TOOLS:
        text = read(root, path)
        for snippet in TOOL_SNIPPETS[path]:
            require(text, snippet, str(path))
    return len(WORKFLOW_TOOLS)


def check_cmake(root: Path) -> int:
    text = read(root, Path("CMakeLists.txt"))
    for path in WORKFLOW_TOOLS:
        require(text, path.as_posix(), "CMakeLists.txt")
    for test in WORKFLOW_TESTS:
        require(text, test, "CMakeLists.txt")
    require(text, "check_visual_claim_promotion_workflow.py", "CMakeLists.txt")
    require(text, "visual_claim_promotion_workflow=ok", "CMakeLists.txt")
    return len(WORKFLOW_TESTS)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check docs, tools, and CTest entries for visual-claim promotion."
    )
    parser.add_argument("repo_root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()
    root = args.repo_root.resolve()

    docs = check_doc(root)
    tools = check_tools(root)
    ctest = check_cmake(root)
    print(
        "visual_claim_promotion_workflow=ok "
        f"docs={docs} tools={tools} ctest={ctest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
