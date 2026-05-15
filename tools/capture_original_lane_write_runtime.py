#!/usr/bin/env python3
"""Run guarded original lane-write debris evidence captures.

This wrapper targets the still-open natural debris-side writeback gap at
`1000:3D2D` and `1000:3EC1`. It is intentionally conservative: preflight and
dry-run modes do not launch DOSBox or read process memory, while live capture
requires the same explicit approval flags as the lower-level process-memory
helper.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile


OFFSETS = ["1000:3D2D", "1000:3EC1"]
OFFSET_ALIASES = {
    "FORWARD": "1000:3D2D",
    "FORWARD-DEBRIS": "1000:3D2D",
    "REVERSE": "1000:3EC1",
    "REVERSE-DEBRIS": "1000:3EC1",
}
EXPECTED_ORIGINAL_BYTES = {
    "1000:3D2D": "889597",
    "1000:3EC1": "889598",
}


def normalize_offset(value: str) -> str:
    token = value.upper()
    if token in OFFSET_ALIASES:
        return OFFSET_ALIASES[token]
    if ":" not in token:
        token = f"1000:{token}"
    if token not in OFFSETS:
        raise argparse.ArgumentTypeError(
            "offset must be one of forward, reverse, forward-debris, "
            "reverse-debris, 1000:3D2D, 1000:3EC1, 3D2D, or 3EC1"
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


def run_logged(
    command: list[str], cwd: Path, log_path: Path
) -> subprocess.CompletedProcess[str]:
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
        raise RuntimeError(f"command failed; see {log_path}")
    return result


def parse_fields(output: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in output.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    return fields


def describe_patch(asset_dir: Path, offset: str) -> dict[str, str]:
    root = repo_root()
    command = [
        sys.executable,
        str(root / "tools" / "capture_original_explosion_procmem.py"),
        str(Path(tempfile.gettempdir()) / "lezac-lane-write-preflight"),
        str(asset_dir),
        "--describe-freeze-patch",
        "--freeze-ghidra-offset",
        offset,
        "--freeze-patch-mode",
        "lane-write-cs-scratch",
    ]
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
    fields = parse_fields(result.stdout)
    if fields.get("freeze_patch_description") != "ok":
        raise RuntimeError(result.stdout.strip())
    expected = EXPECTED_ORIGINAL_BYTES[offset]
    if fields.get("patch_mode") != "lane-write-cs-scratch":
        raise RuntimeError(f"unexpected patch_mode for {offset}: {result.stdout}")
    if fields.get("original_bytes", "").lower() != expected:
        raise RuntimeError(
            f"unexpected original bytes for {offset}: {result.stdout}"
        )
    if fields.get("scratch_offset") != "0xf080":
        raise RuntimeError(f"unexpected scratch offset for {offset}: {result.stdout}")
    if fields.get("scratch_length") != "12":
        raise RuntimeError(f"unexpected scratch length for {offset}: {result.stdout}")
    if fields.get("body_length") != "45":
        raise RuntimeError(f"unexpected body length for {offset}: {result.stdout}")
    return fields


def offset_label(offset: str) -> str:
    return offset.split(":", 1)[1].lower()


def offset_labels(offsets: list[str]) -> str:
    return ",".join(offset_label(offset) for offset in offsets)


def offset_addresses(offsets: list[str]) -> str:
    return ",".join(offsets)


def offset_dir_for(out_dir: Path, offset: str) -> Path:
    return out_dir / offset_label(offset)


def candidate_path_for(out_dir: Path, offset: str) -> Path:
    return (
        offset_dir_for(out_dir, offset)
        / "explosion_playback_oracle_original_candidate.txt"
    )


def selected_offsets(args: argparse.Namespace) -> list[str]:
    offsets = args.offsets or list(OFFSETS)
    selected: list[str] = []
    for offset in offsets:
        if offset not in selected:
            selected.append(offset)
    return selected


def run_preflight(asset_dir: Path, offsets: list[str], out_dir: Path | None) -> str:
    descriptions = {offset: describe_patch(asset_dir, offset) for offset in offsets}
    original_bytes = ",".join(
        f"{offset_label(offset)}:{descriptions[offset]['original_bytes'].lower()}"
        for offset in offsets
    )
    summary = (
        "lane_write_preflight=ok "
        f"asset_dir={asset_dir} "
        f"offsets={offset_addresses(offsets)} "
        f"original_bytes={original_bytes} "
        "scratch_offset=0xf080 scratch_length=12 body_length=45"
    )
    if out_dir is not None:
        (out_dir / "preflight.log").write_text(summary + "\n", encoding="utf-8")
    return summary


def build_capture_command(
    args: argparse.Namespace, offset: str, out_dir: Path
) -> list[str]:
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
        "lane-write-cs-scratch",
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
    if args.runtime_freeze_preset != "none":
        command += ["--runtime-freeze-preset", args.runtime_freeze_preset]
    for step in args.route_steps or []:
        command += ["--route-step", step]
    return command


def build_oracle_command(args: argparse.Namespace, candidate: Path) -> list[str]:
    return [
        str(args.cpp_exe.resolve()),
        "--debug-explosion-playback-oracle",
        str(candidate),
    ]


def parse_candidate(stdout: str, default_path: Path) -> Path:
    for line in stdout.splitlines():
        if line.startswith("candidate="):
            return Path(line.split("=", 1)[1].strip())
    return default_path


def capture_offset(args: argparse.Namespace, offset: str, out_dir: Path) -> Path:
    root = repo_root()
    label = offset_label(offset)
    offset_dir_for(out_dir, offset).mkdir(parents=True, exist_ok=True)
    command = build_capture_command(args, offset, out_dir)
    result = run_logged(command, root, out_dir / f"{label}_capture.log")
    candidate = parse_candidate(result.stdout, candidate_path_for(out_dir, offset))
    if not candidate.exists():
        raise RuntimeError(f"candidate fixture missing for {offset}: {candidate}")
    return candidate


def run_oracle(args: argparse.Namespace, candidate: Path, out_dir: Path) -> None:
    if args.skip_oracle:
        return
    cpp_exe = args.cpp_exe.resolve()
    if not cpp_exe.exists():
        raise RuntimeError(f"missing C++ executable: {cpp_exe}")
    run_logged(
        build_oracle_command(args, candidate),
        repo_root(),
        out_dir / f"{candidate.parent.name}_oracle.log",
    )


def print_dry_run(
    args: argparse.Namespace, out_dir: Path, preflight: str, offsets: list[str]
) -> None:
    print(
        "lane_write_capture_orchestrator=ok "
        f"mode=dry_run out_dir={out_dir} offsets={len(offsets)} "
        f"capture_commands={len(offsets)} "
        f"oracle_commands={0 if args.skip_oracle else len(offsets)} "
        f"offset_labels={offset_labels(offsets)} "
        f"offset_addresses={offset_addresses(offsets)} {preflight}"
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
            "Capture original runtime lane-write debris evidence at 1000:3D2D "
            "and 1000:3EC1, or run only safe preflight/dry-run planning."
        )
    )
    parser.add_argument("out_dir", nargs="?", type=Path)
    parser.add_argument("asset_dir_pos", nargs="?", type=Path)
    parser.add_argument("--asset-dir", type=Path, default=None)
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
        "--offset",
        dest="offsets",
        action="append",
        type=normalize_offset,
        help=(
            "capture one lane-write debris offset; repeatable; accepts forward, "
            "reverse, 3D2D, or 3EC1; default is both"
        ),
    )
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    parser.add_argument(
        "--runtime-freeze-preset",
        choices=["late-collapse", "none"],
        default="late-collapse",
    )
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
        help="repeatable KEY:SECONDS original-control route step",
    )
    parser.add_argument("--tail-freeze-check-seconds", default="0.75")
    args = parser.parse_args()

    if args.preflight_only and args.asset_dir is None and args.asset_dir_pos is None:
        asset_dir = args.out_dir if args.out_dir is not None else repo_root()
        args.out_dir = None
    else:
        asset_dir = args.asset_dir or args.asset_dir_pos or repo_root()
    args.asset_dir = asset_dir.resolve()
    offsets = selected_offsets(args)

    if args.preflight_only:
        preflight = run_preflight(args.asset_dir, offsets, None)
        print(f"lane_write_capture_orchestrator=ok mode=preflight {preflight}")
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
        print_dry_run(args, out_dir, run_preflight(args.asset_dir, offsets, None), offsets)
        return 0
    if not args.approve_procmem or not args.approve_runtime_instrumentation:
        print(
            "refusing runtime capture without --approve-procmem and "
            "--approve-runtime-instrumentation",
            file=sys.stderr,
        )
        return 64

    out_dir.mkdir(parents=True, exist_ok=True)
    preflight = run_preflight(args.asset_dir, offsets, out_dir)
    candidates: list[Path] = []
    for offset in offsets:
        candidate = capture_offset(args, offset, out_dir)
        run_oracle(args, candidate, out_dir)
        candidates.append(candidate)

    command_lines: list[str] = []
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

    manifest = out_dir / "manifest.txt"
    manifest.write_text(
        "\n".join(
            [
                "capture=lane_write_runtime",
                f"asset_dir={args.asset_dir}",
                f"cpp_exe={args.cpp_exe.resolve()}",
                f"offsets={len(offsets)}",
                f"offset_labels={offset_labels(offsets)}",
                f"offset_addresses={offset_addresses(offsets)}",
                f"preflight={preflight}",
                "approve_procmem=1",
                "approve_runtime_instrumentation=1",
                f"runtime_freeze_preset={args.runtime_freeze_preset}",
                "runtime_freeze_after_bomb_seconds="
                f"{args.runtime_freeze_after_bomb_seconds}",
                f"level_start_seconds={args.level_start_seconds}",
                f"right_hold_seconds={args.right_hold_seconds}",
                f"sample_seconds={args.sample_seconds}",
                f"sample_interval={args.sample_interval}",
                f"route_state_interval={args.route_state_interval}",
                "route_steps="
                + ",".join(args.route_steps or [f"x:{args.right_hold_seconds}"]),
                f"tail_freeze_check_seconds={args.tail_freeze_check_seconds}",
                *[
                    f"candidate_{offset_label(offset)}={candidate}"
                    for offset, candidate in zip(offsets, candidates)
                ],
                *command_lines,
            ]
        )
        + "\n",
        encoding="ascii",
    )
    print(
        "lane_write_capture_orchestrator=ok "
        f"mode=capture manifest={manifest} candidates={len(candidates)} "
        f"offset_labels={offset_labels(offsets)} "
        f"offset_addresses={offset_addresses(offsets)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
