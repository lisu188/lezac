#!/usr/bin/env python3
"""Plan or run original actor/contact route-step captures.

The default matrix targets the still-open contact-scanner evidence gap with
both post-route and pre-route runtime-freeze timing. Live capture remains
guarded behind the actor/contact process-memory approval environment used by
the lower-level wrapper.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


TARGETS = [
    "actor_update_start",
    "actor_update_end",
    "actor_update_gate5",
    "actor_update_gate5_integration",
    "actor_update_gate6",
    "contact_scanner_callsite",
    "contact_scanner_start",
    "contact_scanner_end",
]

DEFAULT_ROUTES = [
    "x:2.00",
    "x:5.00,m:0.50,x:2.00",
    "x:3.00,z:0.50,x:2.00",
    "x:1.50,Left:0.50,x:2.00",
]

TIMING_BEFORE_BOMB = "before_bomb"
TIMING_BEFORE_ROUTE = "before_route"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def quote_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def parse_route(value: str) -> list[str]:
    steps = [item.strip() for item in value.split(",") if item.strip()]
    if not steps:
        raise argparse.ArgumentTypeError(
            "route must contain at least one KEY:SECONDS step"
        )
    for step in steps:
        if ":" not in step:
            raise argparse.ArgumentTypeError(f"route step must be KEY:SECONDS: {step}")
        key_name, seconds_text = step.split(":", 1)
        if not key_name:
            raise argparse.ArgumentTypeError("route step key must not be empty")
        try:
            seconds = float(seconds_text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"route step seconds must be numeric: {step}"
            ) from exc
        if seconds < 0:
            raise argparse.ArgumentTypeError("route step seconds must be non-negative")
    return steps


def route_label(steps: list[str]) -> str:
    chunks: list[str] = []
    for step in steps:
        key_name, seconds_text = step.split(":", 1)
        seconds = float(seconds_text)
        key_label = "".join(ch if ch.isalnum() else "_" for ch in key_name.lower())
        key_label = key_label.strip("_") or "key"
        time_label = f"{seconds:.2f}".replace(".", "p")
        chunks.append(f"{key_label}{time_label}")
    return "_".join(chunks)


def timing_values(value: str) -> list[str]:
    if value == "both":
        return [TIMING_BEFORE_BOMB, TIMING_BEFORE_ROUTE]
    return [value]


def env_for_capture(args: argparse.Namespace, route_steps: list[str], timing: str) -> dict[str, str]:
    env = {
        "LEZAC_ACTOR_CONTACT_ROUTE_STEPS": ",".join(route_steps),
        "LEZAC_ACTOR_CONTACT_PROCMEM_SAMPLE_SECONDS": args.sample_seconds,
        "LEZAC_ACTOR_CONTACT_PROCMEM_SAMPLE_INTERVAL": args.sample_interval,
        "LEZAC_ACTOR_CONTACT_PROCMEM_TAIL_FREEZE_SECONDS": args.tail_freeze_seconds,
    }
    if timing == TIMING_BEFORE_ROUTE:
        env["LEZAC_ACTOR_CONTACT_RUNTIME_FREEZE_BEFORE_ROUTE"] = "1"
    if args.dry_run:
        env["LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN"] = "1"
    if args.approve_procmem:
        env["LEZAC_ACTOR_CONTACT_APPROVE_PROCMEM"] = "1"
    if args.approve_runtime_instrumentation:
        env["LEZAC_ACTOR_CONTACT_APPROVE_RUNTIME_INSTRUMENTATION"] = "1"
    return env


def env_prefix(env: dict[str, str]) -> str:
    return " ".join(f"{key}={shlex.quote(value)}" for key, value in sorted(env.items()))


def build_capture_command(
    args: argparse.Namespace,
    route_steps: list[str],
    route_out_dir: Path,
    timing: str,
) -> tuple[list[str], dict[str, str], str]:
    root = repo_root()
    env = env_for_capture(args, route_steps, timing)
    command = [
        "bash",
        str(root / "tools" / "capture_original_actor_contact_procmem.sh"),
        str(route_out_dir),
        str(args.asset_dir),
        args.target,
    ]
    display = f"env {env_prefix(env)} {quote_command(command)}"
    return command, env, display


def run_logged(
    command: list[str],
    env_values: dict[str, str],
    cwd: Path,
    log_path: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_values)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {quote_command(command)}\n"
            f"see log: {log_path}"
        )
    return completed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or run route-step sweeps for original actor/contact evidence."
    )
    parser.add_argument("out_dir")
    parser.add_argument("asset_dir", nargs="?", default=".")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    parser.add_argument("--target", choices=TARGETS, default="contact_scanner_start")
    parser.add_argument(
        "--timing",
        choices=[TIMING_BEFORE_BOMB, TIMING_BEFORE_ROUTE, "both"],
        default="both",
        help="runtime freeze timing to sweep",
    )
    parser.add_argument(
        "--route",
        action="append",
        type=parse_route,
        help="comma-separated KEY:SECONDS route; repeat for multiple route captures",
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

    routes = args.route or [parse_route(route) for route in DEFAULT_ROUTES]
    timings = timing_values(args.timing)
    route_labels = [route_label(route) for route in routes]
    capture_entries: list[tuple[str, list[str], dict[str, str], str, Path]] = []
    for timing in timings:
        for index, route in enumerate(routes):
            label = f"{timing}_{route_labels[index]}"
            route_out_dir = out_dir / label
            command, env, display = build_capture_command(
                args, route, route_out_dir, timing
            )
            capture_entries.append((label, command, env, display, route_out_dir))

    print(
        "actor_contact_route_sweep=ok "
        f"mode={'dry_run' if args.dry_run else 'capture'} "
        f"out_dir={out_dir} target={args.target} "
        f"timings={','.join(timings)} routes={len(routes)} "
        f"route_labels={','.join(route_labels)} "
        f"capture_commands={len(capture_entries)}"
    )
    for label, _, _, display, _ in capture_entries:
        print(f"capture_command_{label}={display}")

    if args.dry_run:
        return 0
    if not args.approve_procmem or not args.approve_runtime_instrumentation:
        print(
            "refusing actor/contact route sweep without --approve-procmem and "
            "--approve-runtime-instrumentation",
            file=sys.stderr,
        )
        return 64
    if shutil.which("bash") is None:
        print("missing required command: bash", file=sys.stderr)
        return 69

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_lines = [
        "capture=actor_contact_route_sweep",
        f"asset_dir={asset_dir}",
        f"target={args.target}",
        f"timings={','.join(timings)}",
        f"routes={len(routes)}",
        f"route_labels={','.join(route_labels)}",
    ]
    for label, command, env, display, route_out_dir in capture_entries:
        route_out_dir.mkdir(parents=True, exist_ok=True)
        result = run_logged(command, env, root, out_dir / f"{label}_capture.log")
        manifest_lines.append(f"capture_command_{label}={display}")
        manifest_lines.append(
            f"capture_log_{label}={out_dir / (label + '_capture.log')}"
        )
        for line in result.stdout.splitlines():
            if line.startswith("actor_contact_procmem=ok"):
                manifest_lines.append(f"capture_status_{label}={line}")
    manifest = out_dir / "manifest.txt"
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="ascii")
    print(f"actor_contact_route_sweep_manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
