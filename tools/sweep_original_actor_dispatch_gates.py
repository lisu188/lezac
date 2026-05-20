#!/usr/bin/env python3
"""Plan or run original actor-update dispatch-gate sweeps."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from sweep_original_actor_contact_routes import (
    DEFAULT_ROUTES,
    TARGETS as CONTACT_TARGETS,
    TIMING_BEFORE_BOMB,
    TIMING_BEFORE_ROUTE,
    parse_route,
    quote_command,
    route_label,
    timing_values,
)


DEFAULT_TARGETS = [
    "actor_update_gate5",
    "actor_update_gate5_integration",
    "actor_update_gate5_exit",
    "actor_update_gate6",
    "contact_scanner_callsite",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def target_label(target: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in target).strip("_")


def build_sweep_command(
    root: Path,
    args: argparse.Namespace,
    target: str,
    target_out_dir: Path,
    routes: list[list[str]],
) -> list[str]:
    command = [
        sys.executable,
        str(root / "tools" / "sweep_original_actor_contact_routes.py"),
        str(target_out_dir),
        str(args.asset_dir),
        "--target",
        target,
        "--timing",
        args.timing,
        "--sample-seconds",
        args.sample_seconds,
        "--sample-interval",
        args.sample_interval,
        "--tail-freeze-seconds",
        args.tail_freeze_seconds,
    ]
    if args.dry_run:
        command.append("--dry-run")
    if args.approve_procmem:
        command.append("--approve-procmem")
    if args.approve_runtime_instrumentation:
        command.append("--approve-runtime-instrumentation")
    command.append("--skip-environment-preflight")
    for route in routes:
        command.extend(["--route", ",".join(route)])
    return command


def build_environment_preflight_command(
    root: Path, args: argparse.Namespace
) -> list[str]:
    return [
        sys.executable,
        str(root / "tools" / "preflight_original_evidence_environment.py"),
        str(args.asset_dir),
        "--probe-wsl",
        "--require-procmem-capture",
    ]


def run_logged(command: list[str], cwd: Path, log_path: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {quote_command(command)}\n"
            f"see log: {log_path}\n{completed.stdout}"
        )
    return completed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or run route sweeps for original actor-update gates."
    )
    parser.add_argument("out_dir")
    parser.add_argument("asset_dir", nargs="?", default=".")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    parser.add_argument(
        "--skip-environment-preflight",
        action="store_true",
        help="skip original-evidence host/tool preflight before live capture",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=CONTACT_TARGETS,
        help="actor/contact target to sweep; repeat to override the default gate set",
    )
    parser.add_argument(
        "--timing",
        choices=[TIMING_BEFORE_BOMB, TIMING_BEFORE_ROUTE, "both"],
        default=TIMING_BEFORE_ROUTE,
        help="runtime freeze timing to sweep",
    )
    parser.add_argument(
        "--route",
        action="append",
        type=parse_route,
        help="comma-separated KEY:SECONDS route; repeat for multiple routes",
    )
    parser.add_argument("--sample-seconds", default="1.0")
    parser.add_argument("--sample-interval", default="0.05")
    parser.add_argument("--tail-freeze-seconds", default="0.25")
    args = parser.parse_args()

    root = repo_root()
    out_dir = Path(args.out_dir).resolve()
    asset_dir = Path(args.asset_dir).resolve()
    repo_dir = root.resolve()
    if repo_dir in out_dir.parents or out_dir == repo_dir:
        raise RuntimeError("choose an output directory outside the repository")
    args.asset_dir = asset_dir

    targets = args.target or DEFAULT_TARGETS
    routes = args.route or [parse_route(route) for route in DEFAULT_ROUTES]
    timings = timing_values(args.timing)
    route_labels = [route_label(route) for route in routes]
    labels = [target_label(target) for target in targets]
    capture_commands = len(targets) * len(timings) * len(routes)

    commands: list[tuple[str, Path, list[str], str]] = []
    for target, label in zip(targets, labels):
        target_out_dir = out_dir / label
        command = build_sweep_command(root, args, target, target_out_dir, routes)
        commands.append((target, target_out_dir, command, quote_command(command)))
    environment_preflight_command = build_environment_preflight_command(root, args)

    print(
        "actor_dispatch_gate_sweep=ok "
        f"mode={'dry_run' if args.dry_run else 'capture'} "
        f"out_dir={out_dir} targets={len(targets)} "
        f"target_labels={','.join(targets)} "
        f"timings={','.join(timings)} routes={len(routes)} "
        f"route_labels={','.join(route_labels)} "
        f"sweep_commands={len(commands)} "
        f"capture_commands={capture_commands} "
        f"environment_preflight={0 if args.skip_environment_preflight else 1}"
    )
    if not args.skip_environment_preflight:
        print(
            "environment_preflight_command="
            f"{quote_command(environment_preflight_command)}"
        )
    for target, _, _, display in commands:
        print(f"sweep_command_{target}={display}")

    if args.dry_run:
        return 0
    if not args.approve_procmem or not args.approve_runtime_instrumentation:
        print(
            "refusing actor dispatch gate sweep without --approve-procmem and "
            "--approve-runtime-instrumentation",
            file=sys.stderr,
        )
        return 64
    out_dir.mkdir(parents=True, exist_ok=True)
    environment_preflight = "skipped"
    if not args.skip_environment_preflight:
        run_logged(
            environment_preflight_command,
            root,
            out_dir / "environment_preflight.log",
        )
        environment_preflight = "ok"
    elif shutil.which("bash") is None:
        print("missing required command: bash", file=sys.stderr)
        return 69
    manifest_lines = [
        "capture=actor_dispatch_gate_sweep",
        f"asset_dir={asset_dir}",
        f"targets={','.join(targets)}",
        f"timings={','.join(timings)}",
        f"routes={len(routes)}",
        f"route_labels={','.join(route_labels)}",
        f"environment_preflight={environment_preflight}",
    ]
    if not args.skip_environment_preflight:
        manifest_lines.extend(
            [
                f"environment_preflight_command={quote_command(environment_preflight_command)}",
                f"environment_preflight_log={out_dir / 'environment_preflight.log'}",
            ]
        )
    for target, target_out_dir, command, display in commands:
        target_out_dir.mkdir(parents=True, exist_ok=True)
        log_path = out_dir / f"{target_label(target)}_sweep.log"
        result = run_logged(command, root, log_path)
        manifest_lines.append(f"sweep_command_{target}={display}")
        manifest_lines.append(f"sweep_log_{target}={log_path}")
        for line in result.stdout.splitlines():
            if line.startswith("actor_contact_route_sweep=ok"):
                manifest_lines.append(f"sweep_status_{target}={line}")
            elif line.startswith("actor_contact_route_sweep_manifest="):
                manifest_lines.append(f"sweep_manifest_{target}={line.split('=', 1)[1]}")
    manifest = out_dir / "manifest.txt"
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="ascii")
    print(f"actor_dispatch_gate_sweep_manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
