#!/usr/bin/env python3
"""Exercise lane-write capture wrapper status output without DOSBox."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_tool(root: Path, args: list[str], expect_success: bool = True) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "capture_original_lane_write_runtime.py"),
        *args,
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
            f"lane-write wrapper failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"lane-write wrapper unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def require_not(text: str, snippet: str, case: str) -> None:
    if snippet in text:
        raise RuntimeError(f"{case} unexpectedly contained {snippet!r}\n{text}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-write wrapper preflight/dry-run status output."
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
        help="repository root containing LEZAC.EXE",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    out_base = Path(tempfile.gettempdir()) / "lezac-lane-write-wrapper-check"
    cases = 0

    preflight = run_tool(root, ["--preflight-only", "--asset-dir", str(root)])
    for snippet in [
        "lane_write_capture_orchestrator=ok mode=preflight",
        "lane_write_preflight=ok",
        "offsets=1000:3D2D,1000:3EC1",
        "original_bytes=3d2d:889597,3ec1:889598",
        "scratch_offset=0xf080 scratch_length=12 body_length=45",
    ]:
        require(preflight, snippet, "preflight")
    cases += 1

    positional_preflight = run_tool(root, [str(root), "--preflight-only"])
    require(
        positional_preflight,
        "lane_write_capture_orchestrator=ok mode=preflight",
        "positional_preflight",
    )
    require(
        positional_preflight,
        "original_bytes=3d2d:889597,3ec1:889598",
        "positional_preflight",
    )
    cases += 1

    default_dry = run_tool(
        root,
        [str(out_base / "default"), str(root), "--dry-run", "--skip-oracle"],
    )
    for snippet in [
        "lane_write_capture_orchestrator=ok mode=dry_run",
        "offsets=2 capture_commands=2 oracle_commands=0",
        "offset_labels=3d2d,3ec1",
        "offset_addresses=1000:3D2D,1000:3EC1",
        "lane_write_preflight=ok",
        "capture_command_3d2d=",
        "capture_command_3ec1=",
        "--freeze-patch-mode lane-write-cs-scratch",
        "--runtime-freeze-preset late-collapse",
    ]:
        require(default_dry, snippet, "default_dry")
    cases += 1

    with_oracle = run_tool(
        root,
        [
            str(out_base / "with-oracle"),
            str(root),
            "--dry-run",
            "--cpp-exe",
            str(root / "build" / "lezac_cpp"),
        ],
    )
    require(with_oracle, "oracle_commands=2", "with_oracle")
    require(with_oracle, "oracle_command_3d2d=", "with_oracle")
    require(with_oracle, "--debug-explosion-playback-oracle", "with_oracle")
    cases += 1

    reverse = run_tool(
        root,
        [
            str(out_base / "reverse"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "reverse",
        ],
    )
    require(reverse, "offsets=1 capture_commands=1", "reverse")
    require(reverse, "offset_labels=3ec1", "reverse")
    require(reverse, "offset_addresses=1000:3EC1", "reverse")
    require(reverse, "original_bytes=3ec1:889598", "reverse")
    cases += 1

    timing = run_tool(
        root,
        [
            str(out_base / "timing"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "forward",
            "--runtime-freeze-preset",
            "none",
            "--runtime-freeze-after-bomb-seconds",
            "0.125",
            "--level-start-seconds",
            "2.25",
            "--right-hold-seconds",
            "3.50",
            "--sample-seconds",
            "6.75",
            "--sample-interval",
            "0.015",
            "--route-state-interval",
            "0.50",
            "--route-step",
            "x:1.25",
            "--route-step",
            "Left:0.50",
            "--tail-freeze-check-seconds",
            "1.25",
        ],
    )
    for snippet in [
        "offset_labels=3d2d",
        "--runtime-freeze-after-bomb-seconds 0.125",
        "--level-start-seconds 2.25",
        "--right-hold-seconds 3.50",
        "--sample-seconds 6.75",
        "--sample-interval 0.015",
        "--route-state-interval 0.50",
        "--tail-freeze-check-seconds 1.25",
        "--route-step x:1.25",
        "--route-step Left:0.50",
    ]:
        require(timing, snippet, "timing")
    require_not(timing, "--runtime-freeze-preset late-collapse", "timing")
    cases += 1

    bad_offset = run_tool(
        root,
        [
            str(out_base / "bad-offset"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "sideways",
        ],
        expect_success=False,
    )
    require(bad_offset, "offset must be one of", "bad_offset")
    cases += 1

    repo_refusal = run_tool(
        root,
        [str(root / "lane-write-runtime-refusal"), str(root), "--dry-run"],
        expect_success=False,
    )
    require(
        repo_refusal,
        "choose an output directory outside the repository",
        "repo_refusal",
    )
    cases += 1

    approval_refusal = run_tool(
        root,
        [str(out_base / "approval-refusal"), str(root)],
        expect_success=False,
    )
    require(
        approval_refusal,
        "refusing runtime capture without --approve-procmem and "
        "--approve-runtime-instrumentation",
        "approval_refusal",
    )
    cases += 1

    print(f"lane_write_wrapper_output=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
