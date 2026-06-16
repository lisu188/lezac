#!/usr/bin/env python3
"""Plan or run original lane-result route-step captures.

The default mode is a dry-run command matrix for the still-open natural
`1000:3D3F` evidence gap. Live capture remains guarded behind the same process
memory and runtime-instrumentation approval flags as the lower-level wrapper.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


DEFAULT_ROUTES = [
    "x:2.00",
    "x:2.00,c:0.50",
    "x:1.50,z:0.50",
    "x:2.00,m:0.35",
]
OFFSET_LABELS = {
    "forward": "3d3f",
    "reverse": "3ed3",
    "3d3f": "3d3f",
    "1000:3d3f": "3d3f",
    "3ed3": "3ed3",
    "1000:3ed3": "3ed3",
}
OFFSET_ALIASES = {
    "FORWARD": "forward",
    "3D3F": "forward",
    "1000:3D3F": "forward",
    "REVERSE": "reverse",
    "3ED3": "reverse",
    "1000:3ED3": "reverse",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def quote_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def normalize_offset(value: str) -> str:
    token = value.upper()
    if token not in OFFSET_ALIASES:
        raise argparse.ArgumentTypeError(
            "offset must be one of forward, reverse, 1000:3D3F, 1000:3ED3, "
            "3D3F, or 3ED3"
        )
    return OFFSET_ALIASES[token]


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


def build_capture_command(
    args: argparse.Namespace, route_steps: list[str], route_out_dir: Path
) -> list[str]:
    root = repo_root()
    command = [
        sys.executable,
        str(root / "tools" / "capture_original_lane_result_runtime.py"),
        str(route_out_dir),
        str(args.asset_dir),
        "--cpp-exe",
        str(args.cpp_exe),
        "--offset",
        args.offset,
        "--runtime-freeze-after-bomb-seconds",
        args.runtime_freeze_after_bomb_seconds,
        "--level-start-seconds",
        args.level_start_seconds,
        "--right-hold-seconds",
        args.right_hold_seconds,
        "--sample-seconds",
        args.sample_seconds,
        "--sample-interval",
        args.sample_interval,
        "--route-state-interval",
        args.route_state_interval,
        "--tail-freeze-check-seconds",
        args.tail_freeze_check_seconds,
    ]
    for step in route_steps:
        command += ["--route-step", step]
    if args.approve_procmem:
        command.append("--approve-procmem")
    if args.approve_runtime_instrumentation:
        command.append("--approve-runtime-instrumentation")
    command.append("--skip-environment-preflight")
    if args.skip_oracle:
        command.append("--skip-oracle")
    return command


def route_candidate_path(route_out_dir: Path, offset: str) -> Path:
    label = OFFSET_LABELS.get(offset.lower(), offset.split(":", 1)[-1].lower())
    return (
        route_out_dir
        / label
        / "explosion_playback_oracle_original_candidate.txt"
    )


def build_oracle_command(args: argparse.Namespace, candidate: Path) -> list[str]:
    return [
        str(args.cpp_exe),
        "--debug-explosion-playback-oracle",
        str(candidate),
    ]


def build_environment_preflight_command(args: argparse.Namespace) -> list[str]:
    root = repo_root()
    return [
        sys.executable,
        str(root / "tools" / "preflight_original_evidence_environment.py"),
        str(args.asset_dir),
        "--probe-wsl",
        "--require-wsl-bash-on-windows",
        "--require-procmem-capture",
    ]


def run_logged(
    command: list[str], cwd: Path, log_path: Path
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
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
        description="Plan or run route-step sweeps for original lane-result evidence."
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
    parser.add_argument("--skip-oracle", action="store_true")
    parser.add_argument(
        "--cpp-exe",
        type=Path,
        default=repo_root() / "build" / "lezac_cpp",
        help="C++ executable delegated to per-route oracle checks",
    )
    parser.add_argument("--offset", type=normalize_offset, default="forward")
    parser.add_argument(
        "--route",
        action="append",
        type=parse_route,
        help="comma-separated KEY:SECONDS route; repeat for multiple route captures",
    )
    parser.add_argument("--runtime-freeze-after-bomb-seconds", default="0.0")
    parser.add_argument("--level-start-seconds", default="1.5")
    parser.add_argument("--right-hold-seconds", default="2.0")
    parser.add_argument("--sample-seconds", default="5.0")
    parser.add_argument("--sample-interval", default="0.005")
    parser.add_argument("--route-state-interval", default="0")
    parser.add_argument("--tail-freeze-check-seconds", default="0.75")
    args = parser.parse_args()

    root = repo_root()
    out_dir = Path(args.out_dir).resolve()
    asset_dir = Path(args.asset_dir).resolve()
    repo_dir = root.resolve()
    if repo_dir in out_dir.parents or out_dir == repo_dir:
        raise RuntimeError("choose an output directory outside the repository")
    args.asset_dir = asset_dir
    args.cpp_exe = args.cpp_exe.resolve()
    routes = args.route or [parse_route(route) for route in DEFAULT_ROUTES]
    route_labels = [route_label(route) for route in routes]
    commands = [
        build_capture_command(args, route, out_dir / route_labels[index])
        for index, route in enumerate(routes)
    ]
    environment_preflight_command = build_environment_preflight_command(args)

    print(
        "lane_result_route_sweep=ok "
        f"mode={'dry_run' if args.dry_run else 'capture'} "
        f"out_dir={out_dir} offset={args.offset} routes={len(routes)} "
        f"route_labels={','.join(route_labels)} "
        f"capture_commands={len(commands)} "
        f"oracle_commands={0 if args.skip_oracle else len(commands)} "
        f"cpp_exe={args.cpp_exe} "
        f"environment_preflight={0 if args.skip_environment_preflight else 1}"
    )
    if not args.skip_environment_preflight:
        print(
            "environment_preflight_command="
            f"{quote_command(environment_preflight_command)}"
        )
    for index, command in enumerate(commands):
        print(f"capture_command_{route_labels[index]}={quote_command(command)}")
        if not args.skip_oracle:
            candidate = route_candidate_path(out_dir / route_labels[index], args.offset)
            print(
                f"oracle_command_{route_labels[index]}="
                f"{quote_command(build_oracle_command(args, candidate))}"
            )

    if args.dry_run:
        return 0
    if not args.approve_procmem or not args.approve_runtime_instrumentation:
        print(
            "refusing route sweep without --approve-procmem and "
            "--approve-runtime-instrumentation",
            file=sys.stderr,
        )
        return 64

    out_dir.mkdir(parents=True, exist_ok=True)
    environment_preflight = "skipped"
    if not args.skip_environment_preflight:
        result = run_logged(
            environment_preflight_command,
            root,
            out_dir / "environment_preflight.log",
        )
        environment_preflight = "ok"
    manifest_lines = [
        "capture=lane_result_route_sweep",
        f"asset_dir={asset_dir}",
        f"cpp_exe={args.cpp_exe}",
        f"offset={args.offset}",
        f"routes={len(routes)}",
        f"route_labels={','.join(route_labels)}",
        f"skip_oracle={1 if args.skip_oracle else 0}",
        f"environment_preflight={environment_preflight}",
    ]
    if not args.skip_environment_preflight:
        manifest_lines.append(
            f"environment_preflight_command={quote_command(environment_preflight_command)}"
        )
        manifest_lines.append(
            f"environment_preflight_log={out_dir / 'environment_preflight.log'}"
        )
    for index, command in enumerate(commands):
        label = route_labels[index]
        route_out_dir = out_dir / label
        route_out_dir.mkdir(parents=True, exist_ok=True)
        result = run_logged(command, root, out_dir / f"{label}_capture.log")
        manifest_lines.append(f"capture_command_{label}={quote_command(command)}")
        if not args.skip_oracle:
            manifest_lines.append(
                f"oracle_command_{label}="
                f"{quote_command(build_oracle_command(args, route_candidate_path(route_out_dir, args.offset)))}"
            )
        manifest_lines.append(
            f"capture_log_{label}={out_dir / (label + '_capture.log')}"
        )
        for line in result.stdout.splitlines():
            if line.startswith("lane_result_capture_orchestrator=ok"):
                manifest_lines.append(f"capture_status_{label}={line}")
    manifest = out_dir / "manifest.txt"
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="ascii")
    print(f"lane_result_route_sweep_manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
