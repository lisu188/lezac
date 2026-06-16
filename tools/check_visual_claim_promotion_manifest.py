#!/usr/bin/env python3
"""Check visual-claim promotion manifest writing."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from check_visual_claim_promotion_plan import (
    make_bundle,
    make_docs,
    make_fixture,
    require,
    run_plan,
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_writer(
    repo_root: Path,
    synthetic_root: Path,
    out_manifest: Path,
    *extra_args: str,
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(repo_root / "tools" / "write_visual_claim_promotion_manifest.py"),
        str(out_manifest),
        "--repo-root",
        str(synthetic_root),
        *extra_args,
    ]
    result = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError(
            f"manifest writer failed with {result.returncode}: {' '.join(command)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"manifest writer unexpectedly passed: {' '.join(command)}\n{result.stdout}"
        )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    cases = 0

    with tempfile.TemporaryDirectory(prefix="lezac-visual-manifest-") as tmp:
        root = Path(tmp)
        make_fixture(root, "ready_original.txt", "0")
        make_fixture(root, "already_promoted.txt", "1")
        make_docs(root, "sample_note.md")
        make_bundle(root, "ready")
        make_bundle(root, "second-ready")

        out_manifest = root / "docs" / "recovery" / "visual_candidates.txt"
        output = run_writer(
            repo_root,
            root,
            out_manifest,
            "--candidate",
            "ready_original.txt",
            "docs/recovery/frame_compare/ready",
            "docs/recovery/sample_note.md",
            "010_level1_start",
            "--candidate",
            "already_promoted.txt",
            "docs/recovery/frame_compare/second-ready",
            "docs/recovery/sample_note.md",
        )
        for snippet in [
            "visual_claim_promotion_manifest=ok",
            "path=docs/recovery/visual_candidates.txt",
            "candidates=2",
        ]:
            require(output, snippet, "writer")
        manifest_text = out_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=visual_claim_candidates",
            "candidates=2",
            "candidate_0_fixture=ready_original.txt",
            "candidate_0_frame_compare_bundle=docs/recovery/frame_compare/ready",
            "candidate_0_docs=docs/recovery/sample_note.md",
            "candidate_0_label=010_level1_start",
            "candidate_1_fixture=already_promoted.txt",
            "candidate_1_frame_compare_bundle=docs/recovery/frame_compare/second-ready",
            "candidate_1_docs=docs/recovery/sample_note.md",
        ]:
            require(manifest_text, snippet, "manifest")
        plan = run_plan(repo_root, root, out_manifest, "--require-all-ready")
        require(plan, "ready=2", "planner")
        cases += 1

        bad_candidate = run_writer(
            repo_root,
            root,
            root / "docs" / "recovery" / "bad_candidate.txt",
            "--candidate",
            "ready_original.txt",
            "docs/recovery/frame_compare/ready",
            expect_success=False,
        )
        require(bad_candidate, "candidate_requires_3_or_4_values=2", "bad_candidate")
        cases += 1

        missing_fixture = run_writer(
            repo_root,
            root,
            root / "docs" / "recovery" / "missing_fixture.txt",
            "--candidate",
            "missing_original.txt",
            "docs/recovery/frame_compare/ready",
            "docs/recovery/sample_note.md",
            expect_success=False,
        )
        require(missing_fixture, "missing_fixture=", "missing_fixture")
        cases += 1

        docs_outside = root / "docs" / "outside.md"
        docs_outside.parent.mkdir(parents=True, exist_ok=True)
        docs_outside.write_text("# Outside\n", encoding="ascii")
        bad_docs = run_writer(
            repo_root,
            root,
            root / "docs" / "recovery" / "bad_docs.txt",
            "--candidate",
            "ready_original.txt",
            "docs/recovery/frame_compare/ready",
            "docs/outside.md",
            expect_success=False,
        )
        require(bad_docs, "docs_outside_recovery=docs/outside.md", "bad_docs")
        cases += 1

        ledger_output = run_writer(
            repo_root,
            root,
            root / "docs" / "recovery" / "visual_claim_promotions.md",
            "--candidate",
            "ready_original.txt",
            "docs/recovery/frame_compare/ready",
            "docs/recovery/sample_note.md",
            expect_success=False,
        )
        require(
            ledger_output,
            "refusing_to_overwrite_visual_claim_ledger=docs/recovery/visual_claim_promotions.md",
            "ledger_output",
        )
        cases += 1

        no_candidates = run_writer(
            repo_root,
            root,
            root / "docs" / "recovery" / "no_candidates.txt",
            expect_success=False,
        )
        require(no_candidates, "no_candidates", "no_candidates")
        cases += 1

    print(f"visual_claim_promotion_manifest_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
