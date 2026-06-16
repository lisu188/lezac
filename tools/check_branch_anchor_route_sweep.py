#!/usr/bin/env python3
"""Exercise branch-anchor route-sweep dry-run and guard behavior."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_sweep(root: Path, args: list[str], expect_success: bool = True) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "sweep_original_branch_anchor_routes.py"),
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
            f"branch-anchor sweep failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"branch-anchor sweep unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def require_not(text: str, snippet: str, case: str) -> None:
    if snippet in text:
        raise RuntimeError(f"{case} unexpectedly contained {snippet!r}\n{text}")


def load_sweep_module(root: Path):
    module_path = root / "tools" / "sweep_original_branch_anchor_routes.py"
    spec = importlib.util.spec_from_file_location(
        "sweep_original_branch_anchor_routes", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["sweep_original_branch_anchor_routes"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check branch-anchor route-sweep status output."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    out_base = Path(tempfile.gettempdir()) / "lezac-branch-anchor-sweep-check"
    out_base.mkdir(parents=True, exist_ok=True)
    cases = 0

    default_dry = run_sweep(
        root,
        [str(out_base / "default"), str(root), "--dry-run", "--skip-oracle"],
    )
    for snippet in [
        "branch_anchor_route_sweep=ok mode=dry_run",
        "targets=3",
        "target_labels=high_debris_target_sample,high_debris_word_gate,effect_forward_pass_call",
        "target_names=high_debris_target_sample,high_debris_word_gate,effect_forward_pass_call",
        "timings=before_bomb routes=4",
        "route_labels=x2p00,x2p00_c0p35,x2p00_c0p65,x2p00_m0p35",
        "capture_commands=12",
        "oracle_commands=0",
        "environment_preflight=1",
        "environment_preflight_command=",
        "--probe-wsl",
        "--require-wsl-bash-on-windows",
        "--require-procmem-capture",
        "capture_command_high_debris_target_sample_before_bomb_x2p00=",
        "capture_command_high_debris_word_gate_before_bomb_x2p00_c0p35=",
        "capture_command_effect_forward_pass_call_before_bomb_x2p00_c0p65=",
        "--freeze-ghidra-offset 1000:4B3F",
        "--freeze-ghidra-offset 1000:4C75",
        "--freeze-ghidra-offset 1000:4C96",
        "--freeze-patch-mode bp4-cs-scratch",
        "--freeze-patch-mode loop",
        "--runtime-freeze-before-bomb",
        "--route-step c:0.35",
        "--route-step c:0.65",
        "--route-step m:0.35",
    ]:
        require(default_dry, snippet, "default_dry")
    cases += 1

    selected = run_sweep(
        root,
        [
            str(out_base / "selected"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--target",
            "high_debris_word_gate",
            "--timing",
            "selected_base",
            "--route",
            "x:2.00,c:0.35",
        ],
    )
    for snippet in [
        "targets=1",
        "target_labels=high_debris_word_gate",
        "timings=selected_base routes=1",
        "route_labels=x2p00_c0p35",
        "capture_commands=1",
        "--freeze-ghidra-offset 1000:4C75",
        "--freeze-patch-mode bp4-cs-scratch",
        "--runtime-freeze-min-queue-score 0x78",
        "--runtime-freeze-min-debris-nonzero 0x20",
        "--runtime-freeze-min-collapse-nonzero 0x01",
        "--runtime-freeze-min-effect-nonzero 0x10",
        "--runtime-freeze-require-debris-base 0x209e",
        "--runtime-freeze-require-collapse-base 0x663e",
        "--runtime-freeze-require-effect-base 0xc22e",
    ]:
        require(selected, snippet, "selected_base")
    require_not(selected, "--runtime-freeze-before-bomb", "selected_base")
    cases += 1

    after_bomb = run_sweep(
        root,
        [
            str(out_base / "after-bomb"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--target",
            "high_debris_target_sample",
            "--timing",
            "after_bomb",
            "--after-bomb-seconds",
            "1.25",
            "--route",
            "Left:0.25,space:0.75",
        ],
    )
    for snippet in [
        "target_labels=high_debris_target_sample",
        "timings=after_bomb routes=1",
        "route_labels=left0p25_space0p75",
        "--freeze-ghidra-offset 1000:4B3F",
        "--runtime-freeze-after-bomb-seconds 1.25",
        "--route-step Left:0.25",
        "--route-step space:0.75",
    ]:
        require(after_bomb, snippet, "after_bomb")
    cases += 1

    all_targets = run_sweep(
        root,
        [
            str(out_base / "all-targets"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--target-set",
            "all",
            "--route",
            "x:2.00",
        ],
    )
    for snippet in [
        "targets=8",
        "target_names=high_debris_loop_entry,high_debris_target_sample,high_debris_target_byte_gate,high_debris_zero_target_branch,high_debris_nonzero_target_branch,high_debris_word_gate,effect_forward_pass_call,effect_reverse_pass_call",
        "capture_commands=8",
        "--freeze-ghidra-offset 1000:492F",
        "--freeze-ghidra-offset 1000:4CA9",
    ]:
        require(all_targets, snippet, "all_targets")
    cases += 1

    with_oracle = run_sweep(
        root,
        [
            str(out_base / "with-oracle"),
            str(root),
            "--dry-run",
            "--target",
            "effect_forward_pass_call",
            "--route",
            "x:2.00",
        ],
    )
    require(with_oracle, "oracle_commands=1", "with_oracle")
    require(with_oracle, "oracle_command_effect_forward_pass_call_before_bomb_x2p00=", "with_oracle")
    require(with_oracle, "--debug-explosion-playback-oracle", "with_oracle")
    cases += 1

    sweep_module = load_sweep_module(root)
    translated_candidate = sweep_module.oracle_candidate_argument(
        Path("/mnt/c/Tools/lezac_cpp.exe"),
        Path(
            "/mnt/c/Users/andrz/AppData/Local/Temp/"
            "lezac-branch-anchor-path-check/high/route/"
            "explosion_playback_oracle_original_candidate.txt"
        ),
    )
    expected_translated = (
        "C:\\Users\\andrz\\AppData\\Local\\Temp\\"
        "lezac-branch-anchor-path-check\\high\\route\\"
        "explosion_playback_oracle_original_candidate.txt"
    )
    if translated_candidate != expected_translated:
        raise RuntimeError(
            "windows_oracle_path translated to "
            f"{translated_candidate!r}, expected {expected_translated!r}"
        )
    cases += 1

    skip_environment = run_sweep(
        root,
        [
            str(out_base / "skip-environment"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--skip-environment-preflight",
            "--target",
            "high_debris_target_sample",
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
        "refusing branch-anchor route sweep without --approve-procmem and "
        "--approve-runtime-instrumentation",
        "live_refusal",
    )
    require_not(live_refusal, "branch_anchor_route_sweep_manifest=", "live_refusal")
    cases += 1

    repo_refusal = run_sweep(
        root,
        [str(root / "branch-anchor-route-sweep-refusal"), str(root), "--dry-run"],
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

    print(f"branch_anchor_route_sweep_output=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
