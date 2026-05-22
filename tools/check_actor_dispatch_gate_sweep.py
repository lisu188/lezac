#!/usr/bin/env python3
"""Exercise actor dispatch-gate sweep dry-run and guard behavior."""

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
        str(root / "tools" / "sweep_original_actor_dispatch_gates.py"),
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
            f"actor dispatch sweep failed with {result.returncode}: "
            f"{' '.join(args)}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"actor dispatch sweep unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
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
        description="Check actor dispatch-gate sweep status output."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    out_base = Path(tempfile.gettempdir()) / "lezac-actor-dispatch-sweep-check"
    cases = 0

    default_dry = run_sweep(root, [str(out_base / "default"), str(root), "--dry-run"])
    for snippet in [
        "actor_dispatch_gate_sweep=ok mode=dry_run",
        "targets=5",
        "target_labels=actor_update_gate5,actor_update_gate5_integration,actor_update_gate5_exit,actor_update_gate6,contact_scanner_callsite",
        "timings=before_route routes=4",
        "route_labels=x2p00,x5p00_m0p50_x2p00,x3p00_z0p50_x2p00,x1p50_left0p50_x2p00",
        "sweep_commands=5",
        "capture_commands=20",
        "environment_preflight=1",
        "environment_preflight_command=",
        "--probe-wsl",
        "--require-wsl-bash-on-windows",
        "--require-procmem-capture",
        "sweep_command_actor_update_gate5=",
        "sweep_command_actor_update_gate5_exit=",
        "sweep_original_actor_contact_routes.py",
        "--skip-environment-preflight",
        "--target actor_update_gate6",
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
            "actor_update_gate5",
            "--target",
            "actor_update_gate6",
            "--timing",
            "both",
            "--route",
            "x:2.00,c:0.50",
            "--route",
            "Left:0.25,space:0.75",
        ],
    )
    for snippet in [
        "targets=2",
        "target_labels=actor_update_gate5,actor_update_gate6",
        "timings=before_bomb,before_route routes=2",
        "route_labels=x2p00_c0p50,left0p25_space0p75",
        "sweep_commands=2",
        "capture_commands=8",
        "environment_preflight=1",
        "--timing both",
        "--route Left:0.25,space:0.75",
    ]:
        require(custom, snippet, "custom_dry_run")
    cases += 1

    all_targets = run_sweep(
        root,
        [
            str(out_base / "all-targets"),
            str(root),
            "--dry-run",
            "--target-set",
            "all",
        ],
    )
    for snippet in [
        "targets=9",
        "target_labels=actor_update_start,actor_update_end,actor_update_gate5,actor_update_gate5_integration,actor_update_gate5_exit,actor_update_gate6,contact_scanner_callsite,contact_scanner_start,contact_scanner_end",
        "timings=before_route routes=4",
        "sweep_commands=9",
        "capture_commands=36",
        "sweep_command_actor_update_start=",
        "sweep_command_contact_scanner_end=",
        "--target actor_update_end",
        "--target contact_scanner_start",
    ]:
        require(all_targets, snippet, "all_targets_dry_run")
    cases += 1

    target_override = run_sweep(
        root,
        [
            str(out_base / "target-override"),
            str(root),
            "--dry-run",
            "--target-set",
            "all",
            "--target",
            "contact_scanner_end",
            "--route",
            "x:2.00",
        ],
    )
    for snippet in [
        "targets=1",
        "target_labels=contact_scanner_end",
        "routes=1",
        "sweep_commands=1",
        "capture_commands=1",
        "sweep_command_contact_scanner_end=",
        "--target contact_scanner_end",
    ]:
        require(target_override, snippet, "target_override")
    cases += 1

    skip_environment = run_sweep(
        root,
        [
            str(out_base / "skip-environment"),
            str(root),
            "--dry-run",
            "--skip-environment-preflight",
            "--target",
            "actor_update_gate6",
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
        "refusing actor dispatch gate sweep without --approve-procmem and "
        "--approve-runtime-instrumentation",
        "live_refusal",
    )
    require_not(live_refusal, "actor_dispatch_gate_sweep_manifest=", "live_refusal")
    cases += 1

    with tempfile.TemporaryDirectory(prefix="lezac-actor-dispatch-empty-path-") as tmp:
        live_preflight = run_sweep_env(
            root,
            [
                str(out_base / "live-preflight"),
                str(root),
                "--approve-procmem",
                "--approve-runtime-instrumentation",
                "--target",
                "actor_update_gate6",
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
        "actor_dispatch_gate_sweep_manifest=",
        "live_preflight",
    )
    cases += 1

    repo_refusal = run_sweep(
        root,
        [str(root / "actor-dispatch-sweep-refusal"), str(root), "--dry-run"],
        expect_success=False,
    )
    require(repo_refusal, "choose an output directory outside the repository", "repo_refusal")
    cases += 1

    bad_route = run_sweep(
        root,
        [str(out_base / "bad-route"), str(root), "--dry-run", "--route", "x"],
        expect_success=False,
    )
    require(bad_route, "route step must be KEY:SECONDS", "bad_route")
    cases += 1

    print(f"actor_dispatch_gate_sweep_output=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
