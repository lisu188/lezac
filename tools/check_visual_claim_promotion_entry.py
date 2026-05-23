#!/usr/bin/env python3
"""Check visual-claim promotion ledger entry generation."""

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


def make_bundle(root: Path, ready: bool = True) -> Path:
    bundle = root / "docs" / "recovery" / "frame_compare" / "sample"
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


def run_entry(
    repo_root: Path,
    fixture: str,
    bundle: Path,
    docs: Path,
    *extra_args: str,
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(repo_root / "tools" / "write_visual_claim_promotion_entry.py"),
        fixture,
        str(bundle),
        str(docs),
        "--repo-root",
        str(bundle.parents[3]),
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
            f"entry writer failed with {result.returncode}: {' '.join(command)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"entry writer unexpectedly passed: {' '.join(command)}\n{result.stdout}"
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

    with tempfile.TemporaryDirectory(prefix="lezac-visual-entry-") as tmp:
        root = Path(tmp)
        fixture = "sample_original.txt"
        write_text(root / "tests" / "fixtures" / "dosbox" / fixture, "visual_claim=1\n")
        docs = root / "docs" / "recovery" / "sample_note.md"
        write_text(docs, "# Sample note\n")
        bundle = make_bundle(root)

        auto = run_entry(repo_root, fixture, bundle, docs)
        for snippet in [
            "visual_claim_promotion_entry=ok",
            "fixture=sample_original.txt",
            "label=010_level1_start",
            "promotion_ready=1",
            "- fixture=sample_original.txt visual_claim=1",
            "original_frame=docs/recovery/frame_compare/sample/original/010_level1_start.png",
            "cpp_frame=docs/recovery/frame_compare/sample/cpp/010_level1_start.ppm",
            "comparison=docs/recovery/frame_compare/sample/diff/010_level1_start.ppm",
            "frame_compare_bundle=docs/recovery/frame_compare/sample",
            "docs=docs/recovery/sample_note.md",
        ]:
            require(auto, snippet, "auto")
        cases += 1

        explicit = run_entry(repo_root, fixture, bundle, docs, "--label", "010_level1_start")
        require(explicit, "label=010_level1_start", "explicit")
        cases += 1

        missing_label = run_entry(
            repo_root,
            fixture,
            bundle,
            docs,
            "--label",
            "000_menu",
            expect_success=False,
        )
        require(missing_label, "missing_artifact_for_label=000_menu", "missing_label")
        cases += 1

        unready_bundle = make_bundle(root / "unready", ready=False)
        write_text(root / "unready" / "tests" / "fixtures" / "dosbox" / fixture, "visual_claim=1\n")
        unready_docs = root / "unready" / "docs" / "recovery" / "sample_note.md"
        write_text(unready_docs, "# Sample note\n")
        unready = run_entry(
            repo_root,
            fixture,
            unready_bundle,
            unready_docs,
            expect_success=False,
        )
        require(unready, "frame_compare_bundle_not_ready", "unready")
        cases += 1

    print(f"visual_claim_promotion_entry_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
