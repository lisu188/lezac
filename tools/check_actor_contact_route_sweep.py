#!/usr/bin/env python3
"""Exercise actor/contact route-sweep dry-run and guard behavior."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_sweep(root: Path, args: list[str], expect_success: bool = True) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "sweep_original_actor_contact_routes.py"),
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
            f"actor/contact route-sweep command failed with {result.returncode}: "
            f"{' '.join(args)}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"actor/contact route-sweep command unexpectedly passed: "
            f"{' '.join(args)}\n{result.stdout}"
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
        description="Check actor/contact route-sweep status output."
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
    out_base = Path(tempfile.gettempdir()) / "lezac-actor-contact-route-sweep-check"
    cases = 0

    default_dry = run_sweep(
        root,
        [str(out_base / "default"), str(root), "--dry-run"],
    )
    for snippet in [
        "actor_contact_route_sweep=ok mode=dry_run",
        "target=contact_scanner_start",
        "timings=before_bomb,before_route routes=4",
        "route_labels=x2p00,x5p00_m0p50_x2p00,x3p00_z0p50_x2p00,x1p50_left0p50_x2p00",
        "capture_commands=8",
        "capture_command_before_bomb_x2p00=",
        "capture_command_before_route_x2p00=",
        "LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1",
        "LEZAC_ACTOR_CONTACT_RUNTIME_FREEZE_BEFORE_ROUTE=1",
        "capture_original_actor_contact_procmem.sh",
        "contact_scanner_start",
        "LEZAC_ACTOR_CONTACT_ROUTE_STEPS=x:5.00,m:0.50,x:2.00",
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
            "contact_scanner_callsite",
            "--timing",
            "before_route",
            "--route",
            "x:2.00,c:0.50",
            "--route",
            "Left:0.25,space:0.75",
        ],
    )
    for snippet in [
        "target=contact_scanner_callsite",
        "timings=before_route routes=2",
        "route_labels=x2p00_c0p50,left0p25_space0p75",
        "capture_commands=2",
        "capture_command_before_route_x2p00_c0p50=",
        "capture_command_before_route_left0p25_space0p75=",
        "LEZAC_ACTOR_CONTACT_RUNTIME_FREEZE_BEFORE_ROUTE=1",
        "LEZAC_ACTOR_CONTACT_ROUTE_STEPS=Left:0.25,space:0.75",
    ]:
        require(custom, snippet, "custom_routes")
    cases += 1

    live_refusal = run_sweep(
        root,
        [str(out_base / "live-refusal"), str(root)],
        expect_success=False,
    )
    require(
        live_refusal,
        "refusing actor/contact route sweep without --approve-procmem and "
        "--approve-runtime-instrumentation",
        "live_refusal",
    )
    require_not(live_refusal, "actor_contact_route_sweep_manifest=", "live_refusal")
    cases += 1

    repo_refusal = run_sweep(
        root,
        [str(root / "actor-contact-route-sweep-refusal"), str(root), "--dry-run"],
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

    print(f"actor_contact_route_sweep_output=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
