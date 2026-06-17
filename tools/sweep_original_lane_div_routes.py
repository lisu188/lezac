#!/usr/bin/env python3
"""Plan or run original lane-divide route-step captures.

This helper classifies whether candidate routes reach the lane helper divide
setup/call sites before spending writeback probes on `1000:3D1B`/`1000:3D2D`.
It is process-memory instrumentation evidence only; generated candidates keep
`visual_claim=0`.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import subprocess
import sys


DEFAULT_ROUTES = [
    "x:2.00,m:0.35",
]
FOLLOWUP_ROUTES = [
    "x:2.00,m:0.35",
    "x:2.00,m:0.15",
    "x:2.00,m:0.65",
    "x:1.50,m:0.35",
    "x:2.50,m:0.35",
]
BROADENED_ROUTES = [
    "x:8.00",
    "x:5.00,m:0.50,x:4.00",
]
DELAYED_BOMB_ROUTES = [
    "x:4.00,m:0.50,x:3.00",
    "x:6.00,m:0.50,x:3.00",
    "x:4.00,z:0.50,m:0.50,x:3.00",
]
ROUTE_PRESETS = {
    "default": DEFAULT_ROUTES,
    "forward-helper-followup": FOLLOWUP_ROUTES,
    "forward-helper-broadened": BROADENED_ROUTES,
    "forward-helper-delayed-bomb": DELAYED_BOMB_ROUTES,
}
BRANCH_ANCHOR_ROUTE_PROMOTION = "branch_anchor_route_candidates"
LANE_WRITE_FORWARD_DEBRIS_ROUTE_PROMOTION = (
    "lane_write_forward_debris_route_candidates"
)
LANE_DIV_FORWARD_ROUTE_PROMOTION = "lane_div_forward_route_candidates"
LANE_DIV_FORWARD_DEBRIS_ROUTE_PROMOTION = (
    "lane_div_forward_debris_route_candidates"
)
DEFAULT_OFFSETS = ["1000:3CE3"]
OFFSET_ALIASES = {
    "FORWARD-DIVIDE-SETUP": "1000:3CD4",
    "FORWARD_DIVIDE_SETUP": "1000:3CD4",
    "DIVIDE-FORWARD-SETUP": "1000:3CD4",
    "DIVIDE_FORWARD_SETUP": "1000:3CD4",
    "FORWARD-DIVIDE": "1000:3CE3",
    "FORWARD_DIVIDE": "1000:3CE3",
    "DIVIDE-FORWARD": "1000:3CE3",
    "DIVIDE_FORWARD": "1000:3CE3",
    "REVERSE-DIVIDE-SETUP": "1000:3E68",
    "REVERSE_DIVIDE_SETUP": "1000:3E68",
    "DIVIDE-REVERSE-SETUP": "1000:3E68",
    "DIVIDE_REVERSE_SETUP": "1000:3E68",
    "REVERSE-DIVIDE": "1000:3E77",
    "REVERSE_DIVIDE": "1000:3E77",
    "DIVIDE-REVERSE": "1000:3E77",
    "DIVIDE_REVERSE": "1000:3E77",
}
VALID_OFFSETS = {
    "1000:3CD4",
    "1000:3CE3",
    "1000:3E68",
    "1000:3E77",
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
            "offset must be one of forward-divide, forward-divide-setup, "
            "reverse-divide, reverse-divide-setup, 1000:3CD4, 1000:3CE3, "
            "1000:3E68, 1000:3E77, 3CD4, 3CE3, 3E68, or 3E77"
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


def read_key_value_manifest(path: Path) -> dict[str, str]:
    if path.is_dir():
        path = path / "manifest.txt"
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"route manifest not found: {path}")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in values:
            raise ValueError(f"duplicate route manifest field: {key}")
        values[key] = value
    return values


def routes_from_route_manifest(path: Path) -> tuple[str, list[list[str]]]:
    values = read_key_value_manifest(path)
    promotion = values.get("promotion", "")
    route_preset = {
        BRANCH_ANCHOR_ROUTE_PROMOTION: "branch-anchor-route-manifest",
        LANE_WRITE_FORWARD_DEBRIS_ROUTE_PROMOTION: (
            "lane-write-forward-debris-route-manifest"
        ),
        LANE_DIV_FORWARD_ROUTE_PROMOTION: "lane-div-forward-route-manifest",
        LANE_DIV_FORWARD_DEBRIS_ROUTE_PROMOTION: (
            "lane-div-forward-debris-route-manifest"
        ),
    }.get(promotion)
    if route_preset is None:
        raise ValueError(
            f"unsupported route manifest promotion {promotion!r}; expected "
            f"{BRANCH_ANCHOR_ROUTE_PROMOTION!r}, "
            f"{LANE_WRITE_FORWARD_DEBRIS_ROUTE_PROMOTION!r}, or "
            f"{LANE_DIV_FORWARD_ROUTE_PROMOTION!r}, or "
            f"{LANE_DIV_FORWARD_DEBRIS_ROUTE_PROMOTION!r}"
        )
    raw_count = values.get("matching_routes", "")
    try:
        count = int(raw_count)
    except ValueError as exc:
        raise ValueError(f"invalid matching_routes value: {raw_count!r}") from exc
    if count <= 0:
        raise ValueError("route manifest has no matching routes")
    routes: list[list[str]] = []
    for index in range(count):
        steps = values.get(f"route_{index}_steps", "")
        if not steps:
            raise ValueError(f"missing route_{index}_steps")
        routes.append(parse_route(steps))
    return route_preset, routes


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
        or args.runtime_freeze_require_lane_update_flag is not None
        or args.runtime_freeze_require_lane_word_global_value is not None
        or args.runtime_freeze_require_lane_target_offset_global_value is not None
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
        "lane-div-cs-scratch",
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
        (
            "--runtime-freeze-require-lane-update-flag",
            args.runtime_freeze_require_lane_update_flag,
        ),
        (
            "--runtime-freeze-require-lane-word-global-value",
            args.runtime_freeze_require_lane_word_global_value,
        ),
        (
            "--runtime-freeze-require-lane-target-offset-global-value",
            args.runtime_freeze_require_lane_target_offset_global_value,
        ),
    ]:
        if value is not None:
            command += [option, value]
    return command


def build_oracle_command(args: argparse.Namespace, candidate: Path) -> list[str]:
    candidate_arg = oracle_candidate_argument(args.cpp_exe, candidate)
    return [
        str(args.cpp_exe),
        "--debug-explosion-playback-oracle",
        candidate_arg,
    ]


def wsl_drive_mount_to_windows_path(path: Path) -> str | None:
    normalized = str(path).replace("\\", "/")
    parts = normalized.split("/")
    if len(parts) < 3 or parts[0] != "" or parts[1] != "mnt" or len(parts[2]) != 1:
        return None
    drive = parts[2].upper()
    rest = "\\".join(parts[3:])
    return f"{drive}:\\" + rest if rest else f"{drive}:\\"


def oracle_candidate_argument(cpp_exe: Path, candidate: Path) -> str:
    if cpp_exe.suffix.lower() != ".exe":
        return str(candidate)
    return wsl_drive_mount_to_windows_path(candidate) or str(candidate)


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
        description="Plan or run route-step sweeps for original lane-div evidence."
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
            "lane-div offset; repeatable. Defaults to forward divide "
            "1000:3CE3"
        ),
    )
    parser.add_argument(
        "--route",
        action="append",
        type=parse_route,
        help="comma-separated KEY:SECONDS route; repeat for multiple route captures",
    )
    parser.add_argument(
        "--route-manifest",
        type=Path,
        help=(
            "branch_anchor_route_candidates, lane_write_forward_debris_route_candidates, "
            "lane_div_forward_route_candidates, or "
            "lane_div_forward_debris_route_candidates manifest whose matching "
            "route steps should be used when --route is omitted"
        ),
    )
    parser.add_argument(
        "--route-preset",
        choices=sorted(ROUTE_PRESETS),
        default="default",
        help=(
            "named route matrix to use when --route is omitted; "
            "forward-helper-followup covers reviewed helper-div timing variants; "
            "forward-helper-broadened covers the long right/jump routes pruned "
            "by the 2026-06-17 live lane-div pass; "
            "forward-helper-delayed-bomb covers later bomb-placement routes for "
            "the debris-marker search"
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
    parser.add_argument("--runtime-freeze-require-lane-update-flag")
    parser.add_argument("--runtime-freeze-require-lane-word-global-value")
    parser.add_argument("--runtime-freeze-require-lane-target-offset-global-value")
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
            "lane-div route sweep requires a runtime freeze gate; use "
            "--runtime-freeze-preset late-collapse, --runtime-freeze-before-route, "
            "--runtime-freeze-before-bomb, --runtime-freeze-after-bomb-seconds, "
            "or a runtime-freeze filter such as "
            "--runtime-freeze-require-high-debris-target-byte"
        )

    if args.route and args.route_manifest is not None:
        raise RuntimeError("use either --route or --route-manifest, not both")
    if args.route_manifest is not None:
        route_preset, routes = routes_from_route_manifest(args.route_manifest)
    else:
        route_preset = "custom" if args.route else args.route_preset
        routes = args.route or [parse_route(route) for route in ROUTE_PRESETS[route_preset]]
    route_labels = [route_label(route) for route in routes]
    offsets = selected_offsets(args)
    offset_labels = [offset_label(offset) for offset in offsets]
    capture_items: list[tuple[str, str, Path, list[str]]] = []
    for route_index, route in enumerate(routes):
        for offset in offsets:
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
        "lane_div_route_sweep=ok "
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
        + (
            f" route_manifest={args.route_manifest.resolve()}"
            if args.route_manifest is not None
            else ""
        )
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
            "refusing lane-div route sweep without --approve-procmem and "
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
        "capture=lane_div_route_sweep",
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
    if args.route_manifest is not None:
        manifest_lines.append(f"route_manifest={args.route_manifest.resolve()}")
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
            f"capture_status_{label}=lane_div_capture=ok "
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
    print(f"lane_div_route_sweep_manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
