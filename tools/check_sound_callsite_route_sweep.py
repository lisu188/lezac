#!/usr/bin/env python3
"""Exercise sound-callsite route-sweep dry-run and guard behavior."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_sweep_env(
    root: Path,
    args: list[str],
    env: dict[str, str] | None,
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "sweep_original_sound_callsite_routes.py"),
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
            f"sound-callsite route-sweep command failed with {result.returncode}: "
            f"{' '.join(args)}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"sound-callsite route-sweep command unexpectedly passed: "
            f"{' '.join(args)}\n{result.stdout}"
        )
    return result.stdout


def run_sweep(root: Path, args: list[str], expect_success: bool = True) -> str:
    return run_sweep_env(root, args, None, expect_success)


def empty_path_env(empty_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(empty_dir)
    return env


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def require_not(text: str, snippet: str, case: str) -> None:
    if snippet in text:
        raise RuntimeError(f"{case} unexpectedly contained {snippet!r}\n{text}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check sound-callsite route-sweep status output."
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
    out_base = Path(tempfile.gettempdir()) / "lezac-sound-callsite-route-sweep-check"
    cases = 0

    default_dry = run_sweep(
        root,
        [str(out_base / "default"), str(root), "--dry-run"],
    )
    for snippet in [
        "sound_callsite_route_sweep=ok mode=dry_run",
        "target=contact_scanner_runtime_sound",
        "timings=before_bomb,before_route routes=4",
        "route_labels=x2p00,x5p00_m0p50_x2p00,x3p00_z0p50_x2p00,x1p50_left0p50_x2p00",
        "capture_commands=8",
        "capture_command_before_bomb_x2p00=",
        "capture_command_before_route_x2p00=",
        "environment_preflight=1",
        "environment_preflight_command=",
        "--probe-wsl",
        "--require-wsl-bash-on-windows",
        "--require-procmem-capture",
        "LEZAC_SOUND_CALLSITE_PROCMEM_DRY_RUN=1",
        "LEZAC_SOUND_CALLSITE_PROCMEM_SKIP_ENVIRONMENT_PREFLIGHT=1",
        "LEZAC_SOUND_CALLSITE_RUNTIME_FREEZE_BEFORE_ROUTE=1",
        "capture_original_sound_callsite_procmem.sh",
        "contact_scanner_runtime_sound",
        "LEZAC_SOUND_CALLSITE_ROUTE_STEPS=x:5.00,m:0.50,x:2.00",
    ]:
        require(default_dry, snippet, "default_dry_run")
    cases += 1

    custom = run_sweep(
        root,
        [
            str(out_base / "custom"),
            str(root),
            "--dry-run",
            "--target",
            "contact_scanner_runtime_sound",
            "--timing",
            "before_route",
            "--route",
            "x:2.00,c:0.50",
            "--route",
            "Left:0.25,space:0.75",
            "--sample-seconds",
            "1.5",
        ],
    )
    for snippet in [
        "target=contact_scanner_runtime_sound",
        "timings=before_route routes=2",
        "route_labels=x2p00_c0p50,left0p25_space0p75",
        "capture_commands=2",
        "capture_command_before_route_x2p00_c0p50=",
        "capture_command_before_route_left0p25_space0p75=",
        "environment_preflight=1",
        "LEZAC_SOUND_CALLSITE_RUNTIME_FREEZE_BEFORE_ROUTE=1",
        "LEZAC_SOUND_CALLSITE_ROUTE_STEPS=Left:0.25,space:0.75",
        "LEZAC_SOUND_CALLSITE_PROCMEM_SAMPLE_SECONDS=1.5",
    ]:
        require(custom, snippet, "custom_routes")
    cases += 1

    skip_environment = run_sweep(
        root,
        [
            str(out_base / "skip-environment"),
            str(root),
            "--dry-run",
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
        "refusing sound-callsite route sweep without --approve-procmem and "
        "--approve-runtime-instrumentation",
        "live_refusal",
    )
    require_not(live_refusal, "sound_callsite_route_sweep_manifest=", "live_refusal")
    cases += 1

    with tempfile.TemporaryDirectory(prefix="lezac-sound-callsite-empty-path-") as tmp:
        live_preflight = run_sweep_env(
            root,
            [
                str(out_base / "live-preflight"),
                str(root),
                "--approve-procmem",
                "--approve-runtime-instrumentation",
                "--timing",
                "before_route",
                "--route",
                "x:2.00",
            ],
            empty_path_env(Path(tmp)),
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
        "sound_callsite_route_sweep_manifest=",
        "live_preflight",
    )
    cases += 1

    repo_refusal = run_sweep(
        root,
        [str(root / "sound-callsite-route-sweep-refusal"), str(root), "--dry-run"],
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

    print(f"sound_callsite_route_sweep_output=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
