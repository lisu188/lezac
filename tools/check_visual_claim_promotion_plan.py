#!/usr/bin/env python3
"""Check visual-claim promotion batch planning."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def touch_frame(path: Path) -> None:
    write_text(path, "P3\n1 1\n255\n0 0 0\n")


def make_bundle(root: Path, name: str, ready: bool = True) -> Path:
    bundle = root / "docs" / "recovery" / "frame_compare" / name
    touch_frame(bundle / "cpp" / "000_menu.ppm")
    touch_frame(bundle / "cpp" / "010_level1_start.ppm")
    touch_frame(bundle / "original" / "000_menu.png")
    touch_frame(bundle / "original" / "010_level1_start.png")
    touch_frame(bundle / "diff" / "010_level1_start.ppm")
    write_text(
        bundle / "manifest.txt",
        "\n".join(
            [
                "scenario=level1_bomb_route",
                f"cpp_dir={bundle / 'cpp'}",
                f"original_dir={bundle / 'original'}",
                f"diff_dir={bundle / 'diff'}",
                f"summary={bundle / 'frame_compare_summary.txt'}",
                "original_capture_exit=0",
                f"original_capture_manifest={bundle / 'original' / 'manifest.txt'}",
                f"original_environment_preflight_log={bundle / 'original' / 'environment_preflight.log'}",
                "compare_exit=0",
                "",
            ]
        ),
    )
    if ready:
        summary = "\n".join(
            [
                (
                    "compare label=000_menu frame_compare=ok size=320x200 "
                    "normalized=none pixels=64000 exact_match=1 "
                    "exact_different_pixels=0 threshold=0 "
                    "threshold_different_pixels=0 max_delta=0 mean_abs_delta=0.000000"
                ),
                (
                    "compare label=010_level1_start frame_compare=ok size=320x200 "
                    "normalized=none pixels=64000 exact_match=1 "
                    "exact_different_pixels=0 threshold=0 "
                    "threshold_different_pixels=0 max_delta=0 mean_abs_delta=0.000000"
                ),
                "",
            ]
        )
    else:
        summary = "compare label=010_level1_start status=missing_original\n"
    write_text(bundle / "frame_compare_summary.txt", summary)
    write_text(
        bundle / "original" / "manifest.txt",
        "environment_preflight_exit=0\nenvironment_preflight=ok\n",
    )
    write_text(
        bundle / "original" / "environment_preflight.log",
        "original_evidence_environment=ok wsl_bash_reason=none\n",
    )
    return bundle


def make_fixture(root: Path, name: str, claim: str = "0") -> None:
    write_text(root / "tests" / "fixtures" / "dosbox" / name, f"visual_claim={claim}\n")


def make_docs(root: Path, name: str) -> Path:
    docs = root / "docs" / "recovery" / name
    write_text(docs, "# Sample note\n")
    return docs


def write_manifest(path: Path, lines: list[str]) -> Path:
    write_text(path, "\n".join(lines) + "\n")
    return path


def run_plan(
    repo_root: Path,
    synthetic_root: Path,
    manifest: Path,
    *extra_args: str,
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(repo_root / "tools" / "plan_visual_claim_promotions.py"),
        str(manifest),
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
            f"promotion plan failed with {result.returncode}: {' '.join(command)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"promotion plan unexpectedly passed: {' '.join(command)}\n{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    cases = 0

    with tempfile.TemporaryDirectory(prefix="lezac-visual-plan-") as tmp:
        root = Path(tmp)
        make_fixture(root, "ready_original.txt", "0")
        make_fixture(root, "already_promoted.txt", "1")
        make_fixture(root, "blocked_original.txt", "0")
        docs = make_docs(root, "sample_note.md")
        ready_bundle = make_bundle(root, "ready")
        second_ready_bundle = make_bundle(root, "second-ready")
        blocked_bundle = make_bundle(root, "blocked", ready=False)

        mixed_manifest = write_manifest(
            root / "docs" / "recovery" / "visual_candidates_mixed.txt",
            [
                "promotion=visual_claim_candidates",
                "candidates=2",
                "candidate_0_fixture=ready_original.txt",
                "candidate_0_frame_compare_bundle=docs/recovery/frame_compare/ready",
                "candidate_0_docs=docs/recovery/sample_note.md",
                "candidate_0_label=010_level1_start",
                "candidate_1_fixture=blocked_original.txt",
                "candidate_1_frame_compare_bundle=docs/recovery/frame_compare/blocked",
                "candidate_1_docs=docs/recovery/sample_note.md",
                "candidate_1_label=010_level1_start",
            ],
        )
        mixed = run_plan(repo_root, root, mixed_manifest)
        for snippet in [
            "visual_claim_promotion_plan=ok",
            "candidates=2",
            "ready=1",
            "blocked=1",
            "index=0 status=ready fixture=ready_original.txt",
            "fixture_current_visual_claim=0",
            "- fixture=ready_original.txt visual_claim=1",
            "index=1 status=blocked fixture=blocked_original.txt",
            "frame_compare_bundle_not_ready=",
        ]:
            require(mixed, snippet, "mixed")
        cases += 1

        ready_entries = root / "docs" / "recovery" / "visual_ready_entries.txt"
        mixed_written = run_plan(
            repo_root,
            root,
            mixed_manifest,
            "--write-ready-entries",
            str(ready_entries),
        )
        require(mixed_written, "visual_claim_ready_entries=ok", "mixed_written")
        require(mixed_written, "entries=1", "mixed_written")
        ready_entries_text = ready_entries.read_text(encoding="ascii")
        require(ready_entries_text, "- fixture=ready_original.txt visual_claim=1", "ready_entries")
        if "blocked_original.txt" in ready_entries_text:
            raise RuntimeError("ready entries included blocked candidate")
        cases += 1

        ledger_write = run_plan(
            repo_root,
            root,
            mixed_manifest,
            "--write-ready-entries",
            str(root / "docs" / "recovery" / "visual_claim_promotions.md"),
            expect_success=False,
        )
        require(
            ledger_write,
            "refusing_to_overwrite_visual_claim_ledger=docs/recovery/visual_claim_promotions.md",
            "ledger_write",
        )
        cases += 1

        mixed_required = run_plan(
            repo_root,
            root,
            mixed_manifest,
            "--require-all-ready",
            expect_success=False,
        )
        require(mixed_required, "reason=blocked_candidates ready=1 blocked=1", "mixed_required")
        cases += 1

        ready_manifest = write_manifest(
            root / "docs" / "recovery" / "visual_candidates_ready.txt",
            [
                "promotion=visual_claim_candidates",
                "candidates=2",
                "candidate_0_fixture=ready_original.txt",
                "candidate_0_frame_compare_bundle=docs/recovery/frame_compare/ready",
                "candidate_0_docs=docs/recovery/sample_note.md",
                "candidate_1_fixture=already_promoted.txt",
                "candidate_1_frame_compare_bundle=docs/recovery/frame_compare/second-ready",
                "candidate_1_docs=docs/recovery/sample_note.md",
                "candidate_1_label=010_level1_start",
            ],
        )
        ready = run_plan(repo_root, root, ready_manifest, "--require-all-ready")
        for snippet in [
            "candidates=2",
            "ready=2",
            "blocked=0",
            "index=0 status=ready fixture=ready_original.txt label=010_level1_start",
            "index=1 status=ready fixture=already_promoted.txt",
            "fixture_current_visual_claim=1",
        ]:
            require(ready, snippet, "ready")
        cases += 1

        bad_promotion = write_manifest(
            root / "docs" / "recovery" / "visual_candidates_bad_promotion.txt",
            [
                "promotion=runtime_evidence",
                "candidates=0",
            ],
        )
        require(
            run_plan(repo_root, root, bad_promotion, expect_success=False),
            "bad_promotion=runtime_evidence",
            "bad_promotion",
        )
        cases += 1

        bad_index = write_manifest(
            root / "docs" / "recovery" / "visual_candidates_bad_index.txt",
            [
                "promotion=visual_claim_candidates",
                "candidates=1",
                "candidate_1_fixture=ready_original.txt",
                "candidate_1_frame_compare_bundle=docs/recovery/frame_compare/ready",
                "candidate_1_docs=docs/recovery/sample_note.md",
            ],
        )
        require(
            run_plan(repo_root, root, bad_index, expect_success=False),
            "candidate_index_outside_count=1",
            "bad_index",
        )
        cases += 1

        missing_docs = write_manifest(
            root / "docs" / "recovery" / "visual_candidates_missing_docs.txt",
            [
                "promotion=visual_claim_candidates",
                "candidates=1",
                "candidate_0_fixture=ready_original.txt",
                "candidate_0_frame_compare_bundle=docs/recovery/frame_compare/ready",
            ],
        )
        require(
            run_plan(repo_root, root, missing_docs, expect_success=False),
            "missing_candidate_0_docs",
            "missing_docs",
        )
        cases += 1

    print(f"visual_claim_promotion_plan_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
