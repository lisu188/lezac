#!/usr/bin/env python3
"""Plan or run original lane-write route-step captures.

The default dry-run matrix targets the still-open natural debris writeback
gap at `1000:3D2D` and `1000:3EC1`. Live capture remains guarded behind the
same process-memory and runtime-instrumentation approvals as the lower-level
process-memory helper.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import subprocess
import sys


DEFAULT_ROUTES = [
    "x:2.00",
    "x:2.00,c:0.50",
    "x:1.50,z:0.50",
    "x:2.00,m:0.35",
]
FORWARD_DEBRIS_EXPANDED_ROUTES = [
    "x:2.00",
    "x:1.75",
    "x:2.25",
    "x:2.00,c:0.25",
    "x:2.00,c:0.50",
    "x:2.00,c:0.75",
    "x:2.00,m:0.35",
    "x:5.00,m:0.50,x:2.00",
    "x:3.00,z:0.50,x:2.00",
    "x:1.50,left:0.50,x:2.00",
]
ROUTE_PRESETS = {
    "default": DEFAULT_ROUTES,
    "forward-debris-expanded": FORWARD_DEBRIS_EXPANDED_ROUTES,
}
DEFAULT_OFFSETS = ["1000:3D2D", "1000:3EC1"]
OFFSET_ALIASES = {
    "FORWARD-COLLAPSE": "1000:3D1B",
    "FORWARD_COLLAPSE": "1000:3D1B",
    "COLLAPSE-FORWARD": "1000:3D1B",
    "COLLAPSE_FORWARD": "1000:3D1B",
    "FORWARD-DEBRIS": "1000:3D2D",
    "FORWARD_DEBRIS": "1000:3D2D",
    "DEBRIS-FORWARD": "1000:3D2D",
    "DEBRIS_FORWARD": "1000:3D2D",
    "REVERSE-COLLAPSE": "1000:3EAF",
    "REVERSE_COLLAPSE": "1000:3EAF",
    "COLLAPSE-REVERSE": "1000:3EAF",
    "COLLAPSE_REVERSE": "1000:3EAF",
    "REVERSE-DEBRIS": "1000:3EC1",
    "REVERSE_DEBRIS": "1000:3EC1",
    "DEBRIS-REVERSE": "1000:3EC1",
    "DEBRIS_REVERSE": "1000:3EC1",
}
VALID_OFFSETS = {
    "1000:3D1B",
    "1000:3D2D",
    "1000:3EAF",
    "1000:3EC1",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def quote_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def normalize_offset(value: str) -> str:
    token = value.upper()
    if token in OFFSET_ALIASES:
        return OFFSET_ALIASES[token]
    if ":" not in token:
        token = f"1000:{token}"
    if token not in VALID_OFFSETS:
        raise argparse.ArgumentTypeError(
            "offset must be one of forward-debris, reverse-debris, "
            "forward-collapse, reverse-collapse, 1000:3D1B, 1000:3D2D, "
            "1000:3EAF, 1000:3EC1, 3D1B, 3D2D, 3EAF, or 3EC1"
        )
    return token


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


def offset_label(offset: str) -> str:
    return offset.split(":", 1)[1].lower()


def selected_offsets(args: argparse.Namespace) -> list[str]:
    offsets = args.offsets or list(DEFAULT_OFFSETS)
    selected: list[str] = []
    for offset in offsets:
        if offset not in selected:
            selected.append(offset)
    return selected


def runtime_freeze_gate_enabled(args: argparse.Namespace) -> bool:
    return (
        args.runtime_freeze_preset != "none"
        or args.runtime_freeze_before_route
        or args.runtime_freeze_before_bomb
        or args.runtime_freeze_after_bomb_seconds is not None
        or args.runtime_freeze_min_queue_score is not None
        or args.runtime_freeze_min_debris_nonzero is not None
        or args.runtime_freeze_min_collapse_nonzero is not None
        or args.runtime_freeze_min_effect_nonzero is not None
        or args.runtime_freeze_require_debris_base is not None
        or args.runtime_freeze_require_collapse_base is not None
        or args.runtime_freeze_require_effect_base is not None
        or args.runtime_freeze_require_high_debris_target_byte is not None
        or args.runtime_freeze_require_high_debris_word_layer_value is not None
    )


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


def build_capture_command(
    args: argparse.Namespace,
    route_steps: list[str],
    offset: str,
    route_out_dir: Path,
) -> list[str]:
    root = repo_root()
    command = [
        sys.executable,
        str(root / "tools" / "capture_original_explosion_procmem.py"),
        str(route_out_dir),
        str(args.asset_dir),
        "--approve-procmem",
        "--mode",
        "regular",
        "--freeze-ghidra-offset",
        offset,
        "--freeze-patch-mode",
        "lane-write-cs-scratch",
        "--approve-instrumentation",
        "--approve-runtime-instrumentation",
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
    if args.runtime_freeze_preset != "none":
        command += ["--runtime-freeze-preset", args.runtime_freeze_preset]
    if args.runtime_freeze_before_route:
        command.append("--runtime-freeze-before-route")
    if args.runtime_freeze_before_bomb:
        command.append("--runtime-freeze-before-bomb")
    if args.runtime_freeze_after_bomb_seconds is not None:
        command += [
            "--runtime-freeze-after-bomb-seconds",
            args.runtime_freeze_after_bomb_seconds,
        ]
    for option, value in [
        ("--runtime-freeze-min-queue-score", args.runtime_freeze_min_queue_score),
        ("--runtime-freeze-min-debris-nonzero", args.runtime_freeze_min_debris_nonzero),
        (
            "--runtime-freeze-min-collapse-nonzero",
            args.runtime_freeze_min_collapse_nonzero,
        ),
        ("--runtime-freeze-min-effect-nonzero", args.runtime_freeze_min_effect_nonzero),
        ("--runtime-freeze-require-debris-base", args.runtime_freeze_require_debris_base),
        (
            "--runtime-freeze-require-collapse-base",
            args.runtime_freeze_require_collapse_base,
        ),
        ("--runtime-freeze-require-effect-base", args.runtime_freeze_require_effect_base),
        (
            "--runtime-freeze-require-high-debris-target-byte",
            args.runtime_freeze_require_high_debris_target_byte,
        ),
        (
            "--runtime-freeze-require-high-debris-word-layer-value",
            args.runtime_freeze_require_high_debris_word_layer_value,
        ),
    ]:
        if value is not None:
            command += [option, value]
    return command


def build_oracle_command(args: argparse.Namespace, candidate: Path) -> list[str]:
    return [
        str(args.cpp_exe),
        "--debug-explosion-playback-oracle",
        str(candidate),
    ]


def parse_candidate(stdout: str, default_path: Path) -> Path:
    for line in stdout.splitlines():
        if line.startswith("candidate="):
            return Path(line.split("=", 1)[1].strip())
    return default_path


def run_logged(
    command: list[str], cwd: Path, log_path: Path
) -> subprocess.CompletedProcess[str]:
    completed = run_logged_optional(command, cwd, log_path)
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {quote_command(command)}\n"
            f"see log: {log_path}\n{completed.stdout}"
        )
    return completed


def run_logged_optional(
    command: list[str], cwd: Path, log_path: Path
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError as exc:
        output = (
            f"command launch failed: {quote_command(command)}\n"
            f"{exc.__class__.__name__}: {exc}\n"
        )
        log_path.write_text(output, encoding="utf-8")
        return subprocess.CompletedProcess(command, 127, output)
    log_path.write_text(completed.stdout, encoding="utf-8")
    return completed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or run route-step sweeps for original lane-write evidence."
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
        "--continue-on-oracle-error",
        action="store_true",
        help=(
            "record oracle launch/parse failures in the sweep manifest and "
            "continue collecting route captures"
        ),
    )
    parser.add_argument(
        "--cpp-exe",
        type=Path,
        default=repo_root() / "build" / "lezac_cpp",
        help="C++ executable used to parse produced candidates",
    )
    parser.add_argument(
        "--offset",
        dest="offsets",
        action="append",
        type=normalize_offset,
        help=(
            "lane-write offset; repeatable. Defaults to natural debris "
            "writebacks 1000:3D2D and 1000:3EC1"
        ),
    )
    parser.add_argument(
        "--route",
        action="append",
        type=parse_route,
        help="comma-separated KEY:SECONDS route; repeat for multiple route captures",
    )
    parser.add_argument(
        "--route-preset",
        choices=sorted(ROUTE_PRESETS),
        default="default",
        help=(
            "named route matrix to use when --route is omitted; "
            "forward-debris-expanded keeps the pending 1000:3D2D search "
            "anchored to a reviewed dry-run plan"
        ),
    )
    parser.add_argument(
        "--runtime-freeze-preset",
        choices=["late-collapse", "none"],
        default="late-collapse",
    )
    parser.add_argument("--runtime-freeze-before-route", action="store_true")
    parser.add_argument("--runtime-freeze-before-bomb", action="store_true")
    parser.add_argument("--runtime-freeze-after-bomb-seconds")
    parser.add_argument("--runtime-freeze-min-queue-score")
    parser.add_argument("--runtime-freeze-min-debris-nonzero")
    parser.add_argument("--runtime-freeze-min-collapse-nonzero")
    parser.add_argument("--runtime-freeze-min-effect-nonzero")
    parser.add_argument("--runtime-freeze-require-debris-base")
    parser.add_argument("--runtime-freeze-require-collapse-base")
    parser.add_argument("--runtime-freeze-require-effect-base")
    parser.add_argument("--runtime-freeze-require-high-debris-target-byte")
    parser.add_argument("--runtime-freeze-require-high-debris-word-layer-value")
    parser.add_argument("--level-start-seconds", default="3.0")
    parser.add_argument("--right-hold-seconds", default="2.0")
    parser.add_argument("--sample-seconds", default="8.0")
    parser.add_argument("--sample-interval", default="0.08")
    parser.add_argument("--route-state-interval", default="0.25")
    parser.add_argument("--tail-freeze-check-seconds", default="0.5")
    args = parser.parse_args()

    root = repo_root()
    out_dir = Path(args.out_dir).resolve()
    asset_dir = Path(args.asset_dir).resolve()
    repo_dir = root.resolve()
    if repo_dir in out_dir.parents or out_dir == repo_dir:
        raise RuntimeError("choose an output directory outside the repository")
    args.asset_dir = asset_dir
    args.cpp_exe = args.cpp_exe.resolve()
    if not runtime_freeze_gate_enabled(args):
        raise RuntimeError(
            "lane-write route sweep requires a runtime freeze gate; use "
            "--runtime-freeze-preset late-collapse, --runtime-freeze-before-route, "
            "--runtime-freeze-before-bomb, --runtime-freeze-after-bomb-seconds, "
            "or a runtime-freeze filter such as "
            "--runtime-freeze-require-high-debris-target-byte"
        )

    route_preset = "custom" if args.route else args.route_preset
    routes = args.route or [parse_route(route) for route in ROUTE_PRESETS[route_preset]]
    route_labels = [route_label(route) for route in routes]
    offsets = selected_offsets(args)
    offset_labels = [offset_label(offset) for offset in offsets]
    capture_items: list[tuple[str, str, Path, list[str]]] = []
    for route_index, route in enumerate(routes):
        for offset in offsets:
            label = f"{route_labels[route_index]}_{offset_label(offset)}"
            route_out_dir = out_dir / route_labels[route_index] / offset_label(offset)
            capture_items.append(
                (
                    route_labels[route_index],
                    offset,
                    route_out_dir,
                    build_capture_command(args, route, offset, route_out_dir),
                )
            )

    print(
        "lane_write_route_sweep=ok "
        f"mode={'dry_run' if args.dry_run else 'capture'} "
        f"out_dir={out_dir} offsets={len(offsets)} "
        f"offset_labels={','.join(offset_labels)} "
        f"offset_addresses={','.join(offsets)} "
        f"routes={len(routes)} route_labels={','.join(route_labels)} "
        f"capture_commands={len(capture_items)} "
        f"oracle_commands={0 if args.skip_oracle else len(capture_items)} "
        f"runtime_freeze_preset={args.runtime_freeze_preset} "
        f"environment_preflight={0 if args.skip_environment_preflight else 1} "
        f"route_preset={route_preset}"
    )
    environment_preflight_command = build_environment_preflight_command(args)
    if not args.skip_environment_preflight:
        print(
            "environment_preflight_command="
            f"{quote_command(environment_preflight_command)}"
        )
    for route_label_value, offset, route_out_dir, command in capture_items:
        label = f"{route_label_value}_{offset_label(offset)}"
        print(f"capture_command_{label}={quote_command(command)}")
        if not args.skip_oracle:
            candidate = route_out_dir / "explosion_playback_oracle_original_candidate.txt"
            print(
                f"oracle_command_{label}="
                f"{quote_command(build_oracle_command(args, candidate))}"
            )

    if args.dry_run:
        return 0
    if not args.approve_procmem or not args.approve_runtime_instrumentation:
        print(
            "refusing lane-write route sweep without --approve-procmem and "
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

    manifest_lines = [
        "capture=lane_write_route_sweep",
        f"asset_dir={asset_dir}",
        f"offsets={len(offsets)}",
        f"offset_labels={','.join(offset_labels)}",
        f"offset_addresses={','.join(offsets)}",
        f"routes={len(routes)}",
        f"route_labels={','.join(route_labels)}",
        f"route_preset={route_preset}",
        f"runtime_freeze_preset={args.runtime_freeze_preset}",
        f"environment_preflight={environment_preflight}",
    ]
    if not args.skip_environment_preflight:
        manifest_lines.append(
            f"environment_preflight_command={quote_command(environment_preflight_command)}"
        )
        manifest_lines.append(
            f"environment_preflight_log={out_dir / 'environment_preflight.log'}"
        )

    for route_label_value, offset, route_out_dir, command in capture_items:
        label = f"{route_label_value}_{offset_label(offset)}"
        route_out_dir.mkdir(parents=True, exist_ok=True)
        result = run_logged(command, root, out_dir / f"{label}_capture.log")
        candidate = parse_candidate(
            result.stdout,
            route_out_dir / "explosion_playback_oracle_original_candidate.txt",
        )
        manifest_lines.append(f"capture_command_{label}={quote_command(command)}")
        manifest_lines.append(f"capture_log_{label}={out_dir / (label + '_capture.log')}")
        manifest_lines.append(
            f"capture_status_{label}=lane_write_capture=ok "
            f"route={route_label_value} offset={offset_label(offset)} "
            f"offset_address={offset} manifest={route_out_dir / 'manifest.txt'} "
            f"candidate={candidate}"
        )
        if not args.skip_oracle:
            oracle_command = build_oracle_command(args, candidate)
            oracle_log = out_dir / f"{label}_oracle.log"
            manifest_lines.append(
                f"oracle_command_{label}={quote_command(oracle_command)}"
            )
            manifest_lines.append(f"oracle_log_{label}={oracle_log}")
            oracle_result = run_logged_optional(oracle_command, root, oracle_log)
            if oracle_result.returncode != 0:
                manifest_lines.append(
                    f"oracle_status_{label}=oracle_error "
                    f"returncode={oracle_result.returncode} log={oracle_log}"
                )
                if not args.continue_on_oracle_error:
                    raise RuntimeError(
                        f"oracle command failed ({oracle_result.returncode}): "
                        f"{quote_command(oracle_command)}\n"
                        f"see log: {oracle_log}\n{oracle_result.stdout}"
                    )
                continue
            for line in oracle_result.stdout.splitlines():
                if line.startswith("explosion_playback_oracle=ok"):
                    manifest_lines.append(f"oracle_status_{label}={line}")

    manifest = out_dir / "manifest.txt"
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="ascii")
    print(f"lane_write_route_sweep_manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
