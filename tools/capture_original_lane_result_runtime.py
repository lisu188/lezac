#!/usr/bin/env python3
"""Run the original lane-result evidence capture sequence.

The default mode is intentionally guarded because it reads DOSBox process
memory through capture_original_explosion_procmem.py. Use --preflight-only for
the no-DOSBox local check that works in restricted shells.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import subprocess
import sys


OFFSETS = ["1000:3D3F", "1000:3ED3"]
OFFSET_ALIASES = {
    "FORWARD": "1000:3D3F",
    "REVERSE": "1000:3ED3",
}


def normalize_offset(value: str) -> str:
    token = value.upper()
    if token in OFFSET_ALIASES:
        return OFFSET_ALIASES[token]
    if ":" not in token:
        token = f"1000:{token}"
    if token not in OFFSETS:
        raise argparse.ArgumentTypeError(
            "offset must be one of forward, reverse, 1000:3D3F, 1000:3ED3, "
            "3D3F, or 3ED3"
        )
    return token


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def quote_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def run_logged(command: list[str], cwd: Path, log_path: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(
        f"$ {quote_command(command)}\n"
        f"exit_code={result.returncode}\n"
        f"{result.stdout}",
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {quote_command(command)}\n"
            f"see log: {log_path}\n{result.stdout}"
        )
    return result


def parse_candidate(stdout: str, default_path: Path) -> Path:
    for line in stdout.splitlines():
        if line.startswith("candidate="):
            return Path(line.split("=", 1)[1].strip())
    return default_path


def offset_label(offset: str) -> str:
    return offset.split(":", 1)[1].lower()


def offset_labels(offsets: list[str]) -> str:
    return ",".join(offset_label(offset) for offset in offsets)


def offset_addresses(offsets: list[str]) -> str:
    return ",".join(offsets)


def offset_dir_for(out_dir: Path, offset: str) -> Path:
    return out_dir / offset_label(offset)


def candidate_path_for(out_dir: Path, offset: str) -> Path:
    return offset_dir_for(out_dir, offset) / "explosion_playback_oracle_original_candidate.txt"


def build_capture_command(args: argparse.Namespace, offset: str, out_dir: Path) -> list[str]:
    root = repo_root()
    command = [
        sys.executable,
        str(root / "tools" / "capture_original_explosion_procmem.py"),
        str(offset_dir_for(out_dir, offset)),
        str(args.asset_dir),
        "--approve-procmem",
        "--mode",
        "regular",
        "--freeze-ghidra-offset",
        offset,
        "--freeze-patch-mode",
        "lane-result-cs-scratch",
        "--approve-instrumentation",
        "--approve-runtime-instrumentation",
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
    for step in args.route_steps or []:
        command += ["--route-step", step]
    return command


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


def build_oracle_command(args: argparse.Namespace, candidate: Path) -> list[str]:
    return [
        str(args.cpp_exe.resolve()),
        "--debug-explosion-playback-oracle",
        str(candidate),
    ]


def run_preflight(asset_dir: Path, out_dir: Path | None) -> str:
    root = repo_root()
    command = [
        sys.executable,
        str(root / "tools" / "check_explosion_lane_result_preflight.py"),
        str(asset_dir),
    ]
    if out_dir is None:
        result = subprocess.run(
            command,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout.strip())
        return result.stdout.strip()
    result = run_logged(command, root, out_dir / "preflight.log")
    return result.stdout.strip()


def capture_offset(args: argparse.Namespace, offset: str, out_dir: Path) -> Path:
    root = repo_root()
    label = offset_label(offset)
    offset_dir = offset_dir_for(out_dir, offset)
    offset_dir.mkdir(parents=True, exist_ok=True)
    command = build_capture_command(args, offset, out_dir)
    result = run_logged(command, root, out_dir / f"{label}_capture.log")
    candidate = parse_candidate(
        result.stdout, candidate_path_for(out_dir, offset)
    )
    if not candidate.exists():
        raise RuntimeError(f"candidate fixture missing for {offset}: {candidate}")
    return candidate


def run_oracle(args: argparse.Namespace, candidate: Path, out_dir: Path) -> None:
    if args.skip_oracle:
        return
    root = repo_root()
    cpp_exe = args.cpp_exe.resolve()
    if not cpp_exe.exists():
        raise RuntimeError(f"missing C++ executable: {cpp_exe}")
    label = candidate.parent.name
    command = build_oracle_command(args, candidate)
    run_logged(command, root, out_dir / f"{label}_oracle.log")


def selected_offsets(args: argparse.Namespace) -> list[str]:
    offsets = args.offsets or list(OFFSETS)
    selected: list[str] = []
    for offset in offsets:
        if offset not in selected:
            selected.append(offset)
    return selected


def print_dry_run(
    args: argparse.Namespace, out_dir: Path, preflight: str, offsets: list[str]
) -> None:
    environment_preflight_command = build_environment_preflight_command(args)
    print(
        "lane_result_capture_orchestrator=ok "
        f"mode=dry_run out_dir={out_dir} "
        f"environment_preflight={0 if args.skip_environment_preflight else 1} "
        f"offsets={len(offsets)} "
        f"capture_commands={len(offsets)} "
        f"oracle_commands={0 if args.skip_oracle else len(offsets)} "
        f"offset_labels={offset_labels(offsets)} "
        f"offset_addresses={offset_addresses(offsets)} {preflight}"
    )
    if not args.skip_environment_preflight:
        print(
            "environment_preflight_command="
            f"{quote_command(environment_preflight_command)}"
        )
    for offset in offsets:
        label = offset_label(offset)
        print(
            f"capture_command_{label}="
            + quote_command(build_capture_command(args, offset, out_dir))
        )
        if not args.skip_oracle:
            print(
                f"oracle_command_{label}="
                + quote_command(
                    build_oracle_command(args, candidate_path_for(out_dir, offset))
                )
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture original runtime lane-result evidence at 1000:3D3F and "
            "1000:3ED3, or run only the safe patch preflight."
        )
    )
    parser.add_argument("out_dir", nargs="?", type=Path)
    parser.add_argument(
        "asset_dir_pos",
        nargs="?",
        type=Path,
        help="optional asset directory, matching the older capture helper shape",
    )
    parser.add_argument(
        "--asset-dir",
        type=Path,
        default=None,
        help="directory containing LEZAC.EXE and assets; overrides positional asset_dir",
    )
    parser.add_argument(
        "--cpp-exe",
        type=Path,
        default=repo_root() / "build" / "lezac_cpp",
        help="C++ executable used to parse produced candidates",
    )
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-oracle", action="store_true")
    parser.add_argument(
        "--skip-environment-preflight",
        action="store_true",
        help="skip original-evidence host/tool preflight before live capture",
    )
    parser.add_argument(
        "--offset",
        dest="offsets",
        action="append",
        type=normalize_offset,
        help=(
            "capture only one lane-result offset; repeatable; accepts forward, "
            "reverse, 3D3F, or 3ED3; default is both"
        ),
    )
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    parser.add_argument("--runtime-freeze-after-bomb-seconds", default="0.0")
    parser.add_argument("--level-start-seconds", default="1.5")
    parser.add_argument("--right-hold-seconds", default="2.0")
    parser.add_argument("--sample-seconds", default="5.0")
    parser.add_argument("--sample-interval", default="0.005")
    parser.add_argument("--route-state-interval", default="0")
    parser.add_argument(
        "--route-step",
        dest="route_steps",
        action="append",
        help="repeatable KEY:SECONDS original-control route step passed to the capture helper",
    )
    parser.add_argument("--tail-freeze-check-seconds", default="0.75")
    args = parser.parse_args()

    if args.preflight_only and args.asset_dir is None and args.asset_dir_pos is None:
        asset_dir = args.out_dir if args.out_dir is not None else repo_root()
        args.out_dir = None
    else:
        asset_dir = args.asset_dir or args.asset_dir_pos or repo_root()
    args.asset_dir = asset_dir.resolve()
    if args.preflight_only:
        preflight = run_preflight(args.asset_dir, None)
        print(
            "lane_result_capture_orchestrator=ok "
            f"mode=preflight {preflight}"
        )
        return 0

    if args.out_dir is None:
        print("out_dir is required unless --preflight-only is used", file=sys.stderr)
        return 64

    out_dir = args.out_dir.resolve()
    root = repo_root().resolve()
    if out_dir == root or is_within(out_dir, root):
        print("choose an output directory outside the repository", file=sys.stderr)
        return 64
    if args.dry_run:
        preflight = run_preflight(args.asset_dir, None)
        print_dry_run(args, out_dir, preflight, selected_offsets(args))
        return 0
    if not args.approve_procmem or not args.approve_runtime_instrumentation:
        print(
            "refusing runtime capture without --approve-procmem and "
            "--approve-runtime-instrumentation",
            file=sys.stderr,
        )
        return 64
    out_dir.mkdir(parents=True, exist_ok=True)

    environment_preflight = "skipped"
    environment_preflight_command = build_environment_preflight_command(args)
    if not args.skip_environment_preflight:
        run_logged(
            environment_preflight_command,
            root,
            out_dir / "environment_preflight.log",
        )
        environment_preflight = "ok"

    preflight = run_preflight(args.asset_dir, out_dir)
    candidates: list[Path] = []
    offsets = selected_offsets(args)
    for offset in offsets:
        candidate = capture_offset(args, offset, out_dir)
        run_oracle(args, candidate, out_dir)
        candidates.append(candidate)

    manifest = out_dir / "manifest.txt"
    command_lines: list[str] = []
    environment_lines = [f"environment_preflight={environment_preflight}"]
    if not args.skip_environment_preflight:
        environment_lines.extend(
            [
                f"environment_preflight_command={quote_command(environment_preflight_command)}",
                f"environment_preflight_log={out_dir / 'environment_preflight.log'}",
            ]
        )
    for offset in offsets:
        label = offset_label(offset)
        command_lines.append(
            f"capture_command_{label}="
            + quote_command(build_capture_command(args, offset, out_dir))
        )
        if not args.skip_oracle:
            command_lines.append(
                f"oracle_command_{label}="
                + quote_command(
                    build_oracle_command(args, candidate_path_for(out_dir, offset))
                )
            )
    manifest.write_text(
        "\n".join(
            [
                "capture=lane_result_runtime",
                f"asset_dir={args.asset_dir}",
                f"cpp_exe={args.cpp_exe.resolve()}",
                f"offsets={len(offsets)}",
                f"offset_labels={offset_labels(offsets)}",
                f"offset_addresses={offset_addresses(offsets)}",
                *environment_lines,
                f"preflight={preflight}",
                "approve_procmem=1",
                "approve_runtime_instrumentation=1",
                "runtime_freeze_after_bomb_seconds="
                f"{args.runtime_freeze_after_bomb_seconds}",
                f"level_start_seconds={args.level_start_seconds}",
                f"right_hold_seconds={args.right_hold_seconds}",
                "route_steps=" + ",".join(args.route_steps or []),
                f"sample_seconds={args.sample_seconds}",
                f"sample_interval={args.sample_interval}",
                f"route_state_interval={args.route_state_interval}",
                f"tail_freeze_check_seconds={args.tail_freeze_check_seconds}",
                *[
                    f"candidate_{offset_label(offsets[index])}={candidate}"
                    for index, candidate in enumerate(candidates)
                ],
                f"skip_oracle={1 if args.skip_oracle else 0}",
                *command_lines,
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(
        "lane_result_capture_orchestrator=ok "
        f"mode=capture out_dir={out_dir} candidates={len(candidates)} "
        f"environment_preflight={environment_preflight} "
        f"offset_labels={offset_labels(offsets)} "
        f"offset_addresses={offset_addresses(offsets)} manifest={manifest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
