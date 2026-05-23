#!/usr/bin/env python3
"""Check frame-compare bundle summary behavior with synthetic bundles."""

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


def run_summary(
    root: Path,
    bundle: Path,
    *extra_args: str,
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_frame_compare_bundle.py"),
        str(bundle),
        *extra_args,
    ]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError(
            f"summary failed with {result.returncode}: {' '.join(command)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"summary unexpectedly passed: {' '.join(command)}\n{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def make_manifest(bundle: Path, scenario: str, original_exit: int, compare_exit: int) -> None:
    write_text(
        bundle / "manifest.txt",
        "\n".join(
            [
                f"scenario={scenario}",
                f"asset_dir={bundle / 'assets'}",
                f"cpp_dir={bundle / 'cpp'}",
                f"original_dir={bundle / 'original'}",
                f"diff_dir={bundle / 'diff'}",
                f"summary={bundle / 'frame_compare_summary.txt'}",
                f"original_capture_exit={original_exit}",
                f"original_capture_driver_log={bundle / 'original_capture_driver.log'}",
                f"original_capture_manifest={bundle / 'original' / 'manifest.txt'}",
                f"original_capture_log={bundle / 'original' / 'original_capture.log'}",
                f"original_environment_preflight_log={bundle / 'original' / 'environment_preflight.log'}",
                f"compare_exit={compare_exit}",
                "",
            ]
        ),
    )


def make_original_manifest(bundle: Path, preflight: str, exit_code: int) -> None:
    write_text(
        bundle / "original" / "manifest.txt",
        "\n".join(
            [
                "scenario=level1_bomb_route",
                "source=LEZAC.EXE via DOSBox",
                f"environment_preflight_exit={exit_code}",
                f"environment_preflight={preflight}",
                "",
            ]
        ),
    )


def make_success_bundle(bundle: Path) -> None:
    make_manifest(bundle, "level1_bomb_route", 0, 0)
    make_original_manifest(bundle, "ok", 0)
    touch_frame(bundle / "cpp" / "000_menu.ppm")
    touch_frame(bundle / "cpp" / "010_level1_start.ppm")
    touch_frame(bundle / "original" / "000_menu.png")
    touch_frame(bundle / "original" / "010_level1_start.png")
    touch_frame(bundle / "diff" / "010_level1_start.ppm")
    write_text(
        bundle / "frame_compare_summary.txt",
        "\n".join(
            [
                (
                    "compare label=000_menu frame_compare=ok size=320x200 "
                    "normalized=none pixels=64000 exact_match=1 "
                    "exact_different_pixels=0 threshold=0 "
                    "threshold_different_pixels=0 max_delta=0 mean_abs_delta=0.000000"
                ),
                (
                    "compare label=010_level1_start frame_compare=ok size=320x200 "
                    "normalized=none pixels=64000 exact_match=0 "
                    "exact_different_pixels=9 threshold=0 "
                    "threshold_different_pixels=9 max_delta=3 mean_abs_delta=1.250000"
                ),
                "",
            ]
        ),
    )
    write_text(
        bundle / "original" / "environment_preflight.log",
        "original_evidence_environment=ok wsl_bash_reason=none\n",
    )


def make_original_failure_bundle(bundle: Path) -> None:
    make_manifest(bundle, "level1_bomb_route", 4, 0)
    make_original_manifest(bundle, "error", 4)
    touch_frame(bundle / "cpp" / "000_menu.ppm")
    write_text(
        bundle / "frame_compare_summary.txt",
        "\n".join(
            [
                (
                    "original_capture_failed status=4 "
                    f"log={bundle / 'original_capture_driver.log'} "
                    f"manifest={bundle / 'original' / 'manifest.txt'}"
                ),
                "compare label=000_menu status=missing_original",
                "",
            ]
        ),
    )
    write_text(
        bundle / "original" / "environment_preflight.log",
        (
            "original_evidence_environment=error "
            "reason=wsl_bash_not_usable wsl_bash_reason=no_default_distro\n"
        ),
    )


def make_compare_failure_bundle(bundle: Path) -> None:
    make_manifest(bundle, "monster_bomb_reward", 0, 2)
    make_original_manifest(bundle, "ok", 0)
    touch_frame(bundle / "cpp" / "000_menu.ppm")
    touch_frame(bundle / "original" / "000_menu.png")
    write_text(
        bundle / "frame_compare_summary.txt",
        "compare label=000_menu frame_compare=error reason=bad_header\n",
    )
    write_text(
        bundle / "original" / "environment_preflight.log",
        "original_evidence_environment=ok wsl_bash_reason=none\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()
    root = args.repo_root.resolve()
    cases = 0

    with tempfile.TemporaryDirectory(prefix="lezac-frame-summary-") as tmp:
        base = Path(tmp)

        success = base / "success"
        make_success_bundle(success)
        success_output = run_summary(root, success)
        for snippet in [
            "frame_compare_bundle_summary=ok",
            "scenario=level1_bomb_route",
            "original_capture_exit=0",
            "compare_exit=0",
            "cpp_frames=2",
            "original_frames=2",
            "diff_frames=1",
            "compared=2",
            "missing_original=0",
            "compare_errors=0",
            "exact_matches=1",
            "max_exact_different_pixels=9",
            "max_mean_abs_delta=1.250000",
            "environment_preflight=ok",
            "environment_preflight_exit=0",
            "wsl_bash_reason=none",
            "promotion_ready=1",
            "reason=none",
        ]:
            require(success_output, snippet, "success")
        run_summary(root, success / "manifest.txt", "--require-promotion-ready")
        cases += 2

        original_failure = base / "original-failure"
        make_original_failure_bundle(original_failure)
        original_failure_output = run_summary(root, original_failure)
        for snippet in [
            "original_capture_exit=4",
            "missing_original=1",
            "environment_preflight=error",
            "environment_preflight_exit=4",
            "wsl_bash_reason=no_default_distro",
            "promotion_ready=0",
            "reason=original_capture_exit_4",
        ]:
            require(original_failure_output, snippet, "original_failure")
        require(
            run_summary(
                root,
                original_failure,
                "--require-promotion-ready",
                expect_success=False,
            ),
            "reason=not_promotion_ready block=original_capture_exit_4",
            "original_failure_required",
        )
        cases += 2

        compare_failure = base / "compare-failure"
        make_compare_failure_bundle(compare_failure)
        compare_failure_output = run_summary(root, compare_failure)
        for snippet in [
            "scenario=monster_bomb_reward",
            "compare_exit=2",
            "compare_errors=1",
            "promotion_ready=0",
            "reason=compare_exit_2",
        ]:
            require(compare_failure_output, snippet, "compare_failure")
        cases += 1

    print(f"frame_compare_bundle_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
