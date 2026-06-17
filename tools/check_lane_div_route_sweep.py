#!/usr/bin/env python3
"""Exercise lane-div route-sweep dry-run and guard behavior."""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_sweep(root: Path, args: list[str], expect_success: bool = True) -> str:
    return run_sweep_env(root, args, env=None, expect_success=expect_success)


def run_sweep_env(
    root: Path,
    args: list[str],
    env: dict[str, str] | None = None,
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "sweep_original_lane_div_routes.py"),
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env=env,
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError(
            f"lane-div sweep failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"lane-div sweep unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    return result.stdout


def run_lane_write_sweep(
    root: Path, args: list[str], expect_success: bool = True
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "sweep_original_lane_write_routes.py"),
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
            f"lane-write sweep failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"lane-write sweep unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def require_not(text: str, snippet: str, case: str) -> None:
    if snippet in text:
        raise RuntimeError(f"{case} unexpectedly contained {snippet!r}\n{text}")


def empty_path_env(empty_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(empty_dir)
    return env


def load_sweep_module(root: Path):
    module_path = root / "tools" / "sweep_original_lane_div_routes.py"
    spec = importlib.util.spec_from_file_location(
        "sweep_original_lane_div_routes", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def out_base_for(root: Path) -> Path:
    temp_root = Path(tempfile.gettempdir()).resolve()
    if temp_root == root or root in temp_root.parents:
        root_parts = root.parts
        if (
            len(root_parts) >= 5
            and root_parts[0] == "/"
            and root_parts[1] == "mnt"
            and len(root_parts[2]) == 1
            and root_parts[3] == "Users"
        ):
            temp_root = (
                Path("/")
                / "mnt"
                / root_parts[2]
                / "Users"
                / root_parts[4]
                / "AppData"
                / "Local"
                / "Temp"
            )
        elif os.name != "nt":
            temp_root = Path("/tmp")
        else:
            temp_root = root.parent
    temp_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="lezac-lane-div-route-sweep-check-", dir=temp_root))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-div route-sweep status output."
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
    out_base = out_base_for(root)
    cases = 0

    default_dry = run_sweep(
        root,
        [str(out_base / "default"), str(root), "--dry-run", "--skip-oracle"],
    )
    for snippet in [
        "lane_div_route_sweep=ok mode=dry_run",
        "offsets=1",
        "offset_labels=3ce3",
        "offset_addresses=1000:3CE3",
        "routes=1",
        "route_labels=x2p00_m0p35",
        "capture_commands=1",
        "oracle_commands=0",
        "runtime_freeze_preset=late-collapse",
        "environment_preflight=1",
        "route_preset=default",
        "environment_preflight_command=",
        "--probe-wsl",
        "--require-procmem-capture",
        "capture_command_x2p00_m0p35_3ce3=",
        "--freeze-ghidra-offset 1000:3CE3",
        "--freeze-patch-mode lane-div-cs-scratch",
        "--runtime-freeze-preset late-collapse",
        "--route-step x:2.00",
        "--route-step m:0.35",
    ]:
        require(default_dry, snippet, "default_dry_run")
    cases += 1

    followup = run_sweep(
        root,
        [
            str(out_base / "followup"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-preset",
            "forward-helper-followup",
            "--offset",
            "forward-divide",
            "--offset",
            "forward-divide-setup",
        ],
    )
    for snippet in [
        "offsets=2",
        "offset_labels=3ce3,3cd4",
        "offset_addresses=1000:3CE3,1000:3CD4",
        "routes=5",
        "route_labels=x2p00_m0p35,x2p00_m0p15,x2p00_m0p65,x1p50_m0p35,x2p50_m0p35",
        "capture_commands=10",
        "route_preset=forward-helper-followup",
        "capture_command_x2p00_m0p15_3ce3=",
        "capture_command_x2p50_m0p35_3cd4=",
        "--freeze-ghidra-offset 1000:3CE3",
        "--freeze-ghidra-offset 1000:3CD4",
        "--route-step m:0.15",
        "--route-step m:0.65",
    ]:
        require(followup, snippet, "followup")
    cases += 1

    broadened = run_sweep(
        root,
        [
            str(out_base / "broadened"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-preset",
            "forward-helper-broadened",
        ],
    )
    for snippet in [
        "offsets=1",
        "offset_labels=3ce3",
        "offset_addresses=1000:3CE3",
        "routes=2",
        "route_labels=x8p00,x5p00_m0p50_x4p00",
        "capture_commands=2",
        "route_preset=forward-helper-broadened",
        "capture_command_x8p00_3ce3=",
        "capture_command_x5p00_m0p50_x4p00_3ce3=",
        "--freeze-ghidra-offset 1000:3CE3",
        "--route-step x:8.00",
        "--route-step x:5.00",
        "--route-step m:0.50",
        "--route-step x:4.00",
    ]:
        require(broadened, snippet, "broadened")
    cases += 1

    delayed_bomb = run_sweep(
        root,
        [
            str(out_base / "delayed-bomb"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-preset",
            "forward-helper-delayed-bomb",
        ],
    )
    for snippet in [
        "offsets=1",
        "offset_labels=3ce3",
        "offset_addresses=1000:3CE3",
        "routes=3",
        "route_labels=x4p00_m0p50_x3p00,x6p00_m0p50_x3p00,x4p00_z0p50_m0p50_x3p00",
        "capture_commands=3",
        "route_preset=forward-helper-delayed-bomb",
        "capture_command_x4p00_m0p50_x3p00_3ce3=",
        "capture_command_x6p00_m0p50_x3p00_3ce3=",
        "capture_command_x4p00_z0p50_m0p50_x3p00_3ce3=",
        "--freeze-ghidra-offset 1000:3CE3",
        "--route-step x:4.00",
        "--route-step x:6.00",
        "--route-step z:0.50",
        "--route-step m:0.50",
        "--route-step x:3.00",
    ]:
        require(delayed_bomb, snippet, "delayed_bomb")
    cases += 1

    backtrack = run_sweep(
        root,
        [
            str(out_base / "backtrack"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-preset",
            "forward-helper-backtrack",
        ],
    )
    for snippet in [
        "offsets=1",
        "offset_labels=3ce3",
        "offset_addresses=1000:3CE3",
        "routes=3",
        "route_labels=x4p00_left1p00_m0p50_x4p00,x6p00_left1p00_m0p50_x4p00,x4p00_z0p50_left1p00_m0p50_x4p00",
        "capture_commands=3",
        "route_preset=forward-helper-backtrack",
        "capture_command_x4p00_left1p00_m0p50_x4p00_3ce3=",
        "capture_command_x6p00_left1p00_m0p50_x4p00_3ce3=",
        "capture_command_x4p00_z0p50_left1p00_m0p50_x4p00_3ce3=",
        "--freeze-ghidra-offset 1000:3CE3",
        "--route-step x:4.00",
        "--route-step x:6.00",
        "--route-step z:0.50",
        "--route-step Left:1.00",
        "--route-step m:0.50",
        "--route-step x:4.00",
    ]:
        require(backtrack, snippet, "backtrack")
    cases += 1

    custom = run_sweep(
        root,
        [
            str(out_base / "custom"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "reverse-divide",
            "--runtime-freeze-preset",
            "none",
            "--runtime-freeze-before-bomb",
            "--route",
            "Left:0.25,space:0.75",
        ],
    )
    for snippet in [
        "offsets=1",
        "offset_labels=3e77",
        "offset_addresses=1000:3E77",
        "routes=1",
        "route_labels=left0p25_space0p75",
        "runtime_freeze_preset=none",
        "--freeze-ghidra-offset 1000:3E77",
        "--runtime-freeze-before-bomb",
        "--route-step Left:0.25",
        "--route-step space:0.75",
    ]:
        require(custom, snippet, "custom")
    cases += 1

    with_oracle = run_sweep(
        root,
        [str(out_base / "oracle"), str(root), "--dry-run", "--route", "x:2.00"],
    )
    require(with_oracle, "oracle_commands=1", "with_oracle")
    require(with_oracle, "oracle_command_x2p00_3ce3=", "with_oracle")
    require(with_oracle, "--debug-explosion-playback-oracle", "with_oracle")
    cases += 1

    branch_route_manifest = out_base / "branch-anchor-routes.txt"
    branch_route_manifest.write_text(
        "\n".join(
            [
                "promotion=branch_anchor_route_candidates",
                "source_manifest=/tmp/lezac-branch-anchor-route-sweep/manifest.txt",
                "source_environment_preflight=ok",
                "required_targets=high_debris_word_gate,effect_forward_pass_call",
                "matching_routes=1",
                "route_0_label=x2p00_m0p35",
                "route_0_steps=x:2.00,m:0.35",
                "route_0_targets=high_debris_word_gate,effect_forward_pass_call",
                "",
            ]
        ),
        encoding="ascii",
    )
    manifest_dry = run_sweep(
        root,
        [
            str(out_base / "route-manifest"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-manifest",
            str(branch_route_manifest),
        ],
    )
    for snippet in [
        "routes=1",
        "route_labels=x2p00_m0p35",
        "route_preset=branch-anchor-route-manifest",
        f"route_manifest={branch_route_manifest.resolve()}",
        "capture_command_x2p00_m0p35_3ce3=",
        "--route-step x:2.00",
        "--route-step m:0.35",
    ]:
        require(manifest_dry, snippet, "route_manifest")
    cases += 1

    forward_route_manifest = out_base / "lane-div-forward-routes.txt"
    forward_route_manifest.write_text(
        "\n".join(
            [
                "promotion=lane_div_forward_route_candidates",
                "source_manifest=/tmp/lezac-lane-div-route-sweep/manifest.txt",
                "source_environment_preflight=ok",
                "required_candidate=forward_divide",
                "matching_routes=1",
                "route_0_label=x2p00_m0p35",
                "route_0_steps=x:2.00,m:0.35",
                "route_0_offset_label=3ce3",
                "route_0_offset_address=1000:3CE3",
                "route_0_lane_div_weight_local=0x0021",
                "route_0_lane_div_numerator_low=0xfff3",
                "route_0_lane_div_numerator_high=0xffff",
                "route_0_fixture=/tmp/candidate.txt",
                "",
            ]
        ),
        encoding="ascii",
    )
    forward_manifest_dry = run_sweep(
        root,
        [
            str(out_base / "forward-route-manifest"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-manifest",
            str(forward_route_manifest),
            "--offset",
            "forward-divide",
        ],
    )
    for snippet in [
        "routes=1",
        "route_labels=x2p00_m0p35",
        "route_preset=lane-div-forward-route-manifest",
        f"route_manifest={forward_route_manifest.resolve()}",
        "capture_command_x2p00_m0p35_3ce3=",
        "--freeze-ghidra-offset 1000:3CE3",
    ]:
        require(forward_manifest_dry, snippet, "forward_route_manifest")
    cases += 1

    lane_write_handoff = run_lane_write_sweep(
        root,
        [
            str(out_base / "lane-write-handoff"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-manifest",
            str(forward_route_manifest),
            "--offset",
            "forward-collapse",
            "--offset",
            "forward-debris",
        ],
    )
    for snippet in [
        "route_preset=lane-div-forward-route-manifest",
        "offset_labels=3d1b,3d2d",
        "route_labels=x2p00_m0p35",
        "capture_command_x2p00_m0p35_3d1b=",
        "capture_command_x2p00_m0p35_3d2d=",
        "--route-step x:2.00",
        "--route-step m:0.35",
    ]:
        require(lane_write_handoff, snippet, "lane_write_handoff")
    cases += 1

    forward_debris_route_manifest = out_base / "lane-div-forward-debris-routes.txt"
    forward_debris_route_manifest.write_text(
        "\n".join(
            [
                "promotion=lane_div_forward_debris_route_candidates",
                "source_manifest=/tmp/lezac-lane-div-route-sweep/manifest.txt",
                "source_environment_preflight=ok",
                "required_candidate=forward_divide_route_state_debris_marker",
                "matching_routes=1",
                "route_0_label=x2p00_m0p35",
                "route_0_steps=x:2.00,m:0.35",
                "route_0_offset_label=3ce3",
                "route_0_offset_address=1000:3CE3",
                "route_0_lane_div_weight_local=0x0021",
                "route_0_lane_div_numerator_low=0xfff3",
                "route_0_lane_div_numerator_high=0xffff",
                "route_0_route_state_max_lane_word_global=0xc004",
                "route_0_route_state_debris_marker_samples=1",
                "route_0_route_state_samples=2",
                "route_0_fixture=/tmp/candidate.txt",
                "",
            ]
        ),
        encoding="ascii",
    )
    forward_debris_manifest_dry = run_sweep(
        root,
        [
            str(out_base / "forward-debris-route-manifest"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-manifest",
            str(forward_debris_route_manifest),
            "--offset",
            "forward-divide",
        ],
    )
    for snippet in [
        "routes=1",
        "route_labels=x2p00_m0p35",
        "route_preset=lane-div-forward-debris-route-manifest",
        f"route_manifest={forward_debris_route_manifest.resolve()}",
        "capture_command_x2p00_m0p35_3ce3=",
        "--freeze-ghidra-offset 1000:3CE3",
    ]:
        require(
            forward_debris_manifest_dry,
            snippet,
            "forward_debris_route_manifest",
        )
    cases += 1

    lane_write_forward_debris_handoff = run_lane_write_sweep(
        root,
        [
            str(out_base / "lane-write-forward-debris-handoff"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-manifest",
            str(forward_debris_route_manifest),
            "--offset",
            "forward-debris",
        ],
    )
    for snippet in [
        "route_preset=lane-div-forward-debris-route-manifest",
        "offset_labels=3d2d",
        "route_labels=x2p00_m0p35",
        "capture_command_x2p00_m0p35_3d2d=",
        "--route-step x:2.00",
        "--route-step m:0.35",
    ]:
        require(
            lane_write_forward_debris_handoff,
            snippet,
            "lane_write_forward_debris_handoff",
        )
    cases += 1

    conflict = run_sweep(
        root,
        [
            str(out_base / "conflict"),
            str(root),
            "--dry-run",
            "--route",
            "x:2.00",
            "--route-manifest",
            str(branch_route_manifest),
        ],
        expect_success=False,
    )
    require(conflict, "use either --route or --route-manifest, not both", "conflict")
    cases += 1

    skip_environment = run_sweep(
        root,
        [
            str(out_base / "skip-environment"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--skip-environment-preflight",
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
        "refusing lane-div route sweep without --approve-procmem and "
        "--approve-runtime-instrumentation",
        "live_refusal",
    )
    cases += 1

    sweep_module = load_sweep_module(root)
    translated_candidate = sweep_module.oracle_candidate_argument(
        Path("/mnt/c/Tools/lezac_cpp.exe"),
        Path("/mnt/c/Users/andrz/AppData/Local/Temp/candidate.txt"),
    )
    if translated_candidate != "C:\\Users\\andrz\\AppData\\Local\\Temp\\candidate.txt":
        raise RuntimeError(f"windows oracle path was not translated: {translated_candidate}")
    cases += 1

    with tempfile.TemporaryDirectory(prefix="lezac-lane-div-empty-path-") as tmp:
        live_preflight = run_sweep_env(
            root,
            [
                str(out_base / "live-preflight"),
                str(root),
                "--approve-procmem",
                "--approve-runtime-instrumentation",
                "--skip-oracle",
                "--route",
                "x:2.00",
            ],
            env=empty_path_env(Path(tmp)),
            expect_success=False,
        )
    if os.name == "nt":
        require(live_preflight, "reason=wsl_bash_not_usable", "live_preflight")
        require(live_preflight, "wsl_bash_required=1", "live_preflight")
    else:
        require(live_preflight, "reason=missing_required", "live_preflight")
        require(live_preflight, "wsl_bash_required=0", "live_preflight")
    require(live_preflight, "wsl_bash_reason=missing_command", "live_preflight")
    cases += 1

    repo_refusal = run_sweep(
        root,
        [str(root / "lane-div-route-sweep-refusal"), str(root), "--dry-run"],
        expect_success=False,
    )
    require(repo_refusal, "choose an output directory outside the repository", "repo_refusal")
    cases += 1

    bad_route = run_sweep(
        root,
        [str(out_base / "bad-route"), str(root), "--dry-run", "--route", "x"],
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
    require(negative_route, "route step seconds must be non-negative", "negative_route")
    cases += 1

    bad_offset = run_sweep(
        root,
        [
            str(out_base / "bad-offset"),
            str(root),
            "--dry-run",
            "--offset",
            "3D2D",
        ],
        expect_success=False,
    )
    require(bad_offset, "offset must be one of", "bad_offset")
    cases += 1

    no_runtime_gate = run_sweep(
        root,
        [
            str(out_base / "no-runtime-gate"),
            str(root),
            "--dry-run",
            "--runtime-freeze-preset",
            "none",
        ],
        expect_success=False,
    )
    require(no_runtime_gate, "lane-div route sweep requires a runtime freeze gate", "no_runtime_gate")
    cases += 1

    print(f"lane_div_route_sweep_output=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
