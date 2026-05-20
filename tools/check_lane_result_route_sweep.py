#!/usr/bin/env python3
"""Exercise lane-result route-sweep dry-run and guard behavior."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_sweep(root: Path, args: list[str], expect_success: bool = True) -> str:
    return run_sweep_env(root, args, env=None, expect_success=expect_success)


def run_sweep_env(
    root: Path,
    args: list[str],
    env: dict[str, str] | None = None,
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "sweep_original_lane_result_routes.py"),
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env=env,
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError(
            f"route-sweep command failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"route-sweep command unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def require_not(text: str, snippet: str, case: str) -> None:
    if snippet in text:
        raise RuntimeError(f"{case} unexpectedly contained {snippet!r}\n{text}")


def empty_path_env(empty_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(empty_dir)
    return env


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-result route-sweep status output."
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
    out_base = Path(tempfile.gettempdir()) / "lezac-lane-result-route-sweep-check"
    cases = 0

    default_dry = run_sweep(
        root,
        [str(out_base / "default"), str(root), "--dry-run", "--skip-oracle"],
    )
    for snippet in [
        "lane_result_route_sweep=ok mode=dry_run",
        "offset=forward routes=4",
        "route_labels=x2p00,x2p00_c0p50,x1p50_z0p50,x2p00_m0p35",
        "capture_commands=4",
        "environment_preflight=1",
        "environment_preflight_command=",
        "--probe-wsl",
        "--require-procmem-capture",
        "capture_command_x2p00=",
        "capture_command_x2p00_c0p50=",
        "capture_command_x1p50_z0p50=",
        "capture_command_x2p00_m0p35=",
        "--route-step x:2.00",
        "--route-step c:0.50",
        "--route-step z:0.50",
        "--route-step m:0.35",
        "--skip-oracle",
    ]:
        require(default_dry, snippet, "default_dry_run")
    cases += 1

    custom = run_sweep(
        root,
        [
            str(out_base / "custom"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "reverse",
            "--route",
            "x:2.00,c:0.50",
            "--route",
            "Left:0.25,space:0.75",
        ],
    )
    for snippet in [
        "offset=reverse routes=2",
        "route_labels=x2p00_c0p50,left0p25_space0p75",
        "capture_commands=2",
        "environment_preflight=1",
        "capture_command_x2p00_c0p50=",
        "capture_command_left0p25_space0p75=",
        "--offset reverse",
        "--route-step Left:0.25",
        "--route-step space:0.75",
    ]:
        require(custom, snippet, "custom_routes")
    cases += 1

    skip_environment = run_sweep(
        root,
        [
            str(out_base / "skip-environment"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--skip-environment-preflight",
            "--route",
            "x:2.00",
        ],
    )
    require(skip_environment, "environment_preflight=0", "skip_environment")
    require_not(
        skip_environment,
        "environment_preflight_command=",
        "skip_environment",
    )
    cases += 1

    live_refusal = run_sweep(
        root,
        [str(out_base / "live-refusal"), str(root)],
        expect_success=False,
    )
    require(
        live_refusal,
        "refusing route sweep without --approve-procmem and "
        "--approve-runtime-instrumentation",
        "live_refusal",
    )
    require_not(live_refusal, "lane_result_route_sweep_manifest=", "live_refusal")
    cases += 1

    with tempfile.TemporaryDirectory(prefix="lezac-lane-empty-path-") as tmp:
        live_preflight = run_sweep_env(
            root,
            [
                str(out_base / "live-preflight"),
                str(root),
                "--approve-procmem",
                "--approve-runtime-instrumentation",
                "--skip-oracle",
                "--route",
                "x:2.00",
            ],
            env=empty_path_env(Path(tmp)),
            expect_success=False,
        )
    require(live_preflight, "reason=missing_required", "live_preflight")
    require(live_preflight, "wsl_bash_reason=missing_command", "live_preflight")
    require(live_preflight, "missing_required=", "live_preflight")
    require_not(
        live_preflight,
        "lane_result_route_sweep_manifest=",
        "live_preflight",
    )
    cases += 1

    repo_refusal = run_sweep(
        root,
        [str(root / "lane-result-route-sweep-refusal"), str(root), "--dry-run"],
        expect_success=False,
    )
    require(
        repo_refusal,
        "choose an output directory outside the repository",
        "repo_refusal",
    )
    cases += 1

    bad_route = run_sweep(
        root,
        [
            str(out_base / "bad-route"),
            str(root),
            "--dry-run",
            "--route",
            "x",
        ],
        expect_success=False,
    )
    require(bad_route, "route step must be KEY:SECONDS", "bad_route")
    cases += 1

    negative_route = run_sweep(
        root,
        [
            str(out_base / "negative-route"),
            str(root),
            "--dry-run",
            "--route",
            "x:-0.25",
        ],
        expect_success=False,
    )
    require(
        negative_route,
        "route step seconds must be non-negative",
        "negative_route",
    )
    cases += 1

    print(f"lane_result_route_sweep_output=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
