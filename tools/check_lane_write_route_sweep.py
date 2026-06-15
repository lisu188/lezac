#!/usr/bin/env python3
"""Exercise lane-write route-sweep dry-run and guard behavior."""

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
        str(root / "tools" / "sweep_original_lane_write_routes.py"),
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
            f"lane-write sweep failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"lane-write sweep unexpectedly passed: {' '.join(args)}\n"
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
        description="Check lane-write route-sweep status output."
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
    out_base = Path(tempfile.gettempdir()) / "lezac-lane-write-route-sweep-check"
    cases = 0

    default_dry = run_sweep(
        root,
        [str(out_base / "default"), str(root), "--dry-run", "--skip-oracle"],
    )
    for snippet in [
        "lane_write_route_sweep=ok mode=dry_run",
        "offsets=2",
        "offset_labels=3d2d,3ec1",
        "offset_addresses=1000:3D2D,1000:3EC1",
        "routes=4",
        "route_labels=x2p00,x2p00_c0p50,x1p50_z0p50,x2p00_m0p35",
        "capture_commands=8",
        "oracle_commands=0",
        "runtime_freeze_preset=late-collapse",
        "environment_preflight=1",
        "route_preset=default",
        "environment_preflight_command=",
        "--probe-wsl",
        "--require-wsl-bash-on-windows",
        "--require-procmem-capture",
        "capture_command_x2p00_3d2d=",
        "capture_command_x2p00_3ec1=",
        "capture_command_x2p00_c0p50_3d2d=",
        "capture_command_x1p50_z0p50_3ec1=",
        "capture_command_x2p00_m0p35_3d2d=",
        "--freeze-ghidra-offset 1000:3D2D",
        "--freeze-ghidra-offset 1000:3EC1",
        "--freeze-patch-mode lane-write-cs-scratch",
        "--runtime-freeze-preset late-collapse",
        "--route-step x:2.00",
        "--route-step c:0.50",
        "--route-step z:0.50",
        "--route-step m:0.35",
    ]:
        require(default_dry, snippet, "default_dry_run")
    cases += 1

    forward_expanded = run_sweep(
        root,
        [
            str(out_base / "forward-expanded"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-preset",
            "forward-debris-expanded",
            "--offset",
            "forward-debris",
        ],
    )
    expanded_routes = (
        "route_labels=x2p00,x1p75,x2p25,x2p00_c0p25,x2p00_c0p50,"
        "x2p00_c0p75,x2p00_m0p35,x5p00_m0p50_x2p00,"
        "x3p00_z0p50_x2p00,x1p50_left0p50_x2p00"
    )
    for snippet in [
        "offsets=1",
        "offset_labels=3d2d",
        "offset_addresses=1000:3D2D",
        "routes=10",
        expanded_routes,
        "capture_commands=10",
        "oracle_commands=0",
        "route_preset=forward-debris-expanded",
        "capture_command_x1p75_3d2d=",
        "capture_command_x2p00_c0p25_3d2d=",
        "capture_command_x2p00_c0p75_3d2d=",
        "capture_command_x5p00_m0p50_x2p00_3d2d=",
        "capture_command_x1p50_left0p50_x2p00_3d2d=",
        "--freeze-ghidra-offset 1000:3D2D",
        "--route-step x:1.75",
        "--route-step x:2.25",
        "--route-step c:0.25",
        "--route-step c:0.75",
        "--route-step x:5.00",
        "--route-step left:0.50",
    ]:
        require(forward_expanded, snippet, "forward_expanded")
    require_not(
        forward_expanded,
        "--freeze-ghidra-offset 1000:3EC1",
        "forward_expanded",
    )
    cases += 1

    with_oracle = run_sweep(
        root,
        [
            str(out_base / "oracle"),
            str(root),
            "--dry-run",
            "--route",
            "x:2.00",
        ],
    )
    require(with_oracle, "oracle_commands=2", "with_oracle")
    require(with_oracle, "oracle_command_x2p00_3d2d=", "with_oracle")
    require(with_oracle, "--debug-explosion-playback-oracle", "with_oracle")
    cases += 1

    custom = run_sweep(
        root,
        [
            str(out_base / "custom"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "forward-collapse",
            "--offset",
            "reverse-debris",
            "--runtime-freeze-preset",
            "none",
            "--runtime-freeze-after-bomb-seconds",
            "0.125",
            "--route",
            "Left:0.25,space:0.75",
        ],
    )
    for snippet in [
        "offsets=2",
        "offset_labels=3d1b,3ec1",
        "offset_addresses=1000:3D1B,1000:3EC1",
        "routes=1",
        "route_labels=left0p25_space0p75",
        "runtime_freeze_preset=none",
        "--freeze-ghidra-offset 1000:3D1B",
        "--freeze-ghidra-offset 1000:3EC1",
        "--runtime-freeze-after-bomb-seconds 0.125",
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
        "refusing lane-write route sweep without --approve-procmem and "
        "--approve-runtime-instrumentation",
        "live_refusal",
    )
    require_not(live_refusal, "lane_write_route_sweep_manifest=", "live_refusal")
    cases += 1

    with tempfile.TemporaryDirectory(prefix="lezac-lane-write-empty-path-") as tmp:
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
    if os.name == "nt":
        require(live_preflight, "reason=wsl_bash_not_usable", "live_preflight")
        require(live_preflight, "wsl_bash_required=1", "live_preflight")
    else:
        require(live_preflight, "reason=missing_required", "live_preflight")
        require(live_preflight, "wsl_bash_required=0", "live_preflight")
    require(live_preflight, "wsl_bash_reason=missing_command", "live_preflight")
    require(live_preflight, "missing_required=", "live_preflight")
    require_not(
        live_preflight,
        "lane_write_route_sweep_manifest=",
        "live_preflight",
    )
    cases += 1

    repo_refusal = run_sweep(
        root,
        [str(root / "lane-write-route-sweep-refusal"), str(root), "--dry-run"],
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

    bad_offset = run_sweep(
        root,
        [
            str(out_base / "bad-offset"),
            str(root),
            "--dry-run",
            "--offset",
            "3D3F",
        ],
        expect_success=False,
    )
    require(bad_offset, "offset must be one of", "bad_offset")
    cases += 1

    no_runtime_gate = run_sweep(
        root,
        [
            str(out_base / "no-runtime-gate"),
            str(root),
            "--dry-run",
            "--runtime-freeze-preset",
            "none",
        ],
        expect_success=False,
    )
    require(
        no_runtime_gate,
        "lane-write route sweep requires a runtime freeze gate",
        "no_runtime_gate",
    )
    cases += 1

    print(f"lane_write_route_sweep_output=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
