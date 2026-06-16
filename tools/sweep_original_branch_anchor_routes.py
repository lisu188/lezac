#!/usr/bin/env python3
"""Plan or run original high-debris branch-anchor route probes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess
import sys


DEFAULT_ROUTES = [
    "x:2.00",
    "x:2.00,c:0.35",
    "x:2.00,c:0.65",
    "x:2.00,m:0.35",
]

TIMING_AFTER_BOMB = "after_bomb"
TIMING_BEFORE_BOMB = "before_bomb"
TIMING_SELECTED_BASE = "selected_base"


@dataclass(frozen=True)
class Target:
    offset: str
    patch_mode: str


TARGETS = {
    "high_debris_loop_entry": Target("1000:492F", "loop"),
    "high_debris_target_sample": Target("1000:4B3F", "loop"),
    "high_debris_target_byte_gate": Target("1000:4B61", "loop"),
    "high_debris_zero_target_branch": Target("1000:4B6A", "loop"),
    "high_debris_nonzero_target_branch": Target("1000:4C20", "loop"),
    "high_debris_word_gate": Target("1000:4C75", "bp4-cs-scratch"),
    "effect_forward_pass_call": Target("1000:4C96", "loop"),
    "effect_reverse_pass_call": Target("1000:4CA9", "loop"),
}

DEFAULT_TARGETS = [
    "high_debris_target_sample",
    "high_debris_word_gate",
    "effect_forward_pass_call",
]

TARGET_SETS = {
    "default": DEFAULT_TARGETS,
    "all": list(TARGETS),
}


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
    if value == "all":
        return [TIMING_BEFORE_BOMB, TIMING_AFTER_BOMB, TIMING_SELECTED_BASE]
    if value == "before-and-selected":
        return [TIMING_BEFORE_BOMB, TIMING_SELECTED_BASE]
    return [value]


def target_dir_name(target: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in target).strip("_")


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
    target_name: str,
    timing: str,
    out_dir: Path,
) -> list[str]:
    root = repo_root()
    target = TARGETS[target_name]
    command = [
        sys.executable,
        str(root / "tools" / "capture_original_explosion_procmem.py"),
        str(out_dir),
        str(args.asset_dir),
        "--approve-procmem",
        "--mode",
        "regular",
        "--freeze-ghidra-offset",
        target.offset,
        "--freeze-patch-mode",
        target.patch_mode,
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
    if timing == TIMING_BEFORE_BOMB:
        command.append("--runtime-freeze-before-bomb")
    elif timing == TIMING_AFTER_BOMB:
        command += ["--runtime-freeze-after-bomb-seconds", args.after_bomb_seconds]
    elif timing == TIMING_SELECTED_BASE:
        command += [
            "--runtime-freeze-min-queue-score",
            args.selected_min_queue_score,
            "--runtime-freeze-min-debris-nonzero",
            args.selected_min_debris_nonzero,
            "--runtime-freeze-min-collapse-nonzero",
            args.selected_min_collapse_nonzero,
            "--runtime-freeze-min-effect-nonzero",
            args.selected_min_effect_nonzero,
            "--runtime-freeze-require-debris-base",
            args.selected_debris_base,
            "--runtime-freeze-require-collapse-base",
            args.selected_collapse_base,
            "--runtime-freeze-require-effect-base",
            args.selected_effect_base,
        ]
    else:
        raise RuntimeError(f"unsupported timing: {timing}")
    return command


def build_oracle_command(args: argparse.Namespace, candidate: Path) -> list[str]:
    return [
        str(args.cpp_exe),
        "--debug-explosion-playback-oracle",
        oracle_candidate_argument(args.cpp_exe, candidate),
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
        description="Plan or run route sweeps for original high-debris branch anchors."
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
        help="record oracle failures in the manifest and continue",
    )
    parser.add_argument(
        "--cpp-exe",
        type=Path,
        default=repo_root() / "build" / "lezac_cpp",
        help="C++ executable used to parse produced candidates",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=sorted(TARGETS),
        help="branch anchor to probe; repeat to override the default target set",
    )
    parser.add_argument(
        "--target-set",
        choices=sorted(TARGET_SETS),
        default="default",
        help="named branch-anchor set to sweep when --target is omitted",
    )
    parser.add_argument(
        "--timing",
        choices=[
            TIMING_AFTER_BOMB,
            TIMING_BEFORE_BOMB,
            TIMING_SELECTED_BASE,
            "before-and-selected",
            "all",
        ],
        default=TIMING_BEFORE_BOMB,
        help="runtime freeze timing to use for each branch-anchor probe",
    )
    parser.add_argument(
        "--route",
        action="append",
        type=parse_route,
        help="comma-separated KEY:SECONDS route; repeat for multiple routes",
    )
    parser.add_argument("--after-bomb-seconds", default="0.0")
    parser.add_argument("--selected-min-queue-score", default="0x78")
    parser.add_argument("--selected-min-debris-nonzero", default="0x20")
    parser.add_argument("--selected-min-collapse-nonzero", default="0x01")
    parser.add_argument("--selected-min-effect-nonzero", default="0x10")
    parser.add_argument("--selected-debris-base", default="0x209e")
    parser.add_argument("--selected-collapse-base", default="0x663e")
    parser.add_argument("--selected-effect-base", default="0xc22e")
    parser.add_argument("--level-start-seconds", default="3.0")
    parser.add_argument("--right-hold-seconds", default="2.0")
    parser.add_argument("--sample-seconds", default="8.0")
    parser.add_argument("--sample-interval", default="0.005")
    parser.add_argument("--route-state-interval", default="0.25")
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

    targets = args.target or TARGET_SETS[args.target_set]
    timings = timing_values(args.timing)
    routes = args.route or [parse_route(route) for route in DEFAULT_ROUTES]
    route_labels = [route_label(route) for route in routes]
    target_labels = [target_dir_name(target) for target in targets]
    capture_items: list[tuple[str, str, str, Path, list[str]]] = []
    for target_name in targets:
        for timing in timings:
            for route_index, route in enumerate(routes):
                route_label_value = route_labels[route_index]
                label = f"{target_dir_name(target_name)}_{timing}_{route_label_value}"
                capture_out_dir = (
                    out_dir
                    / target_dir_name(target_name)
                    / timing
                    / route_label_value
                )
                capture_items.append(
                    (
                        label,
                        target_name,
                        route_label_value,
                        capture_out_dir,
                        build_capture_command(
                            args, route, target_name, timing, capture_out_dir
                        ),
                    )
                )
    environment_preflight_command = build_environment_preflight_command(args)

    print(
        "branch_anchor_route_sweep=ok "
        f"mode={'dry_run' if args.dry_run else 'capture'} "
        f"out_dir={out_dir} targets={len(targets)} "
        f"target_labels={','.join(target_labels)} "
        f"target_names={','.join(targets)} "
        f"timings={','.join(timings)} routes={len(routes)} "
        f"route_labels={','.join(route_labels)} "
        f"capture_commands={len(capture_items)} "
        f"oracle_commands={0 if args.skip_oracle else len(capture_items)} "
        f"environment_preflight={0 if args.skip_environment_preflight else 1}"
    )
    if not args.skip_environment_preflight:
        print(
            "environment_preflight_command="
            f"{quote_command(environment_preflight_command)}"
        )
    for label, _, _, capture_out_dir, command in capture_items:
        print(f"capture_command_{label}={quote_command(command)}")
        if not args.skip_oracle:
            candidate = capture_out_dir / "explosion_playback_oracle_original_candidate.txt"
            print(
                f"oracle_command_{label}="
                f"{quote_command(build_oracle_command(args, candidate))}"
            )

    if args.dry_run:
        return 0
    if not args.approve_procmem or not args.approve_runtime_instrumentation:
        print(
            "refusing branch-anchor route sweep without --approve-procmem and "
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
        "capture=branch_anchor_route_sweep",
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
    for label, target_name, route_label_value, capture_out_dir, command in capture_items:
        capture_out_dir.mkdir(parents=True, exist_ok=True)
        result = run_logged(command, root, out_dir / f"{label}_capture.log")
        candidate = parse_candidate(
            result.stdout,
            capture_out_dir / "explosion_playback_oracle_original_candidate.txt",
        )
        target = TARGETS[target_name]
        manifest_lines.append(f"capture_command_{label}={quote_command(command)}")
        manifest_lines.append(f"capture_log_{label}={out_dir / (label + '_capture.log')}")
        manifest_lines.append(
            f"capture_status_{label}=branch_anchor_capture=ok "
            f"route={route_label_value} target={target_name} "
            f"offset={target.offset} patch_mode={target.patch_mode} "
            f"manifest={capture_out_dir / 'manifest.txt'} candidate={candidate}"
        )
        if args.skip_oracle:
            continue
        oracle_command = build_oracle_command(args, candidate)
        oracle_log = out_dir / f"{label}_oracle.log"
        manifest_lines.append(f"oracle_command_{label}={quote_command(oracle_command)}")
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
    print(f"branch_anchor_route_sweep_manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
