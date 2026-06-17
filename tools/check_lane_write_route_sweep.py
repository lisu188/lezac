#!/usr/bin/env python3
"""Exercise lane-write route-sweep dry-run and guard behavior."""

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
        env=env,
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
    module_path = root / "tools" / "sweep_original_lane_write_routes.py"
    spec = importlib.util.spec_from_file_location(
        "sweep_original_lane_write_routes", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def temp_root_for(root: Path) -> Path:
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
    return temp_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-write route-sweep status output."
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
    temp_root = temp_root_for(root)
    out_base = Path(
        tempfile.mkdtemp(prefix="lezac-lane-write-route-sweep-check-", dir=temp_root)
    )
    cases = 0

    default_dry = run_sweep(
        root,
        [str(out_base / "default"), str(root), "--dry-run", "--skip-oracle"],
    )
    for snippet in [
        "lane_write_route_sweep=ok mode=dry_run",
        "offsets=2",
        "offset_labels=3d2d,3ec1",
        "offset_addresses=1000:3D2D,1000:3EC1",
        "routes=4",
        "route_labels=x2p00,x2p00_c0p50,x1p50_z0p50,x2p00_m0p35",
        "capture_commands=8",
        "oracle_commands=0",
        "runtime_freeze_preset=late-collapse",
        "environment_preflight=1",
        "route_preset=default",
        "environment_preflight_command=",
        "--probe-wsl",
        "--require-wsl-bash-on-windows",
        "--require-procmem-capture",
        "capture_command_x2p00_3d2d=",
        "capture_command_x2p00_3ec1=",
        "capture_command_x2p00_c0p50_3d2d=",
        "capture_command_x1p50_z0p50_3ec1=",
        "capture_command_x2p00_m0p35_3d2d=",
        "--freeze-ghidra-offset 1000:3D2D",
        "--freeze-ghidra-offset 1000:3EC1",
        "--freeze-patch-mode lane-write-cs-scratch",
        "--runtime-freeze-preset late-collapse",
        "--route-step x:2.00",
        "--route-step c:0.50",
        "--route-step z:0.50",
        "--route-step m:0.35",
    ]:
        require(default_dry, snippet, "default_dry_run")
    cases += 1

    forward_expanded = run_sweep(
        root,
        [
            str(out_base / "forward-expanded"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-preset",
            "forward-debris-expanded",
            "--offset",
            "forward-debris",
        ],
    )
    expanded_routes = (
        "route_labels=x2p00,x1p75,x2p25,x2p00_c0p25,x2p00_c0p50,"
        "x2p00_c0p75,x2p00_m0p35,x5p00_m0p50_x2p00,"
        "x3p00_z0p50_x2p00,x1p50_left0p50_x2p00"
    )
    for snippet in [
        "offsets=1",
        "offset_labels=3d2d",
        "offset_addresses=1000:3D2D",
        "routes=10",
        expanded_routes,
        "capture_commands=10",
        "oracle_commands=0",
        "route_preset=forward-debris-expanded",
        "capture_command_x1p75_3d2d=",
        "capture_command_x2p00_c0p25_3d2d=",
        "capture_command_x2p00_c0p75_3d2d=",
        "capture_command_x5p00_m0p50_x2p00_3d2d=",
        "capture_command_x1p50_left0p50_x2p00_3d2d=",
        "--freeze-ghidra-offset 1000:3D2D",
        "--route-step x:1.75",
        "--route-step x:2.25",
        "--route-step c:0.25",
        "--route-step c:0.75",
        "--route-step x:5.00",
        "--route-step left:0.50",
    ]:
        require(forward_expanded, snippet, "forward_expanded")
    require_not(
        forward_expanded,
        "--freeze-ghidra-offset 1000:3EC1",
        "forward_expanded",
    )
    cases += 1

    helper_tag_open = run_sweep(
        root,
        [
            str(out_base / "helper-tag-open"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-preset",
            "forward-helper-tag-open",
            "--offset",
            "forward-collapse",
            "--offset",
            "forward-debris",
            "--runtime-freeze-preset",
            "none",
            "--runtime-freeze-before-bomb",
        ],
    )
    for snippet in [
        "offsets=2",
        "offset_labels=3d1b,3d2d",
        "offset_addresses=1000:3D1B,1000:3D2D",
        "routes=2",
        "route_labels=x3p00_z0p50_x2p00,x1p50_left0p50_x2p00",
        "capture_commands=4",
        "oracle_commands=0",
        "runtime_freeze_preset=none",
        "route_preset=forward-helper-tag-open",
        "capture_command_x3p00_z0p50_x2p00_3d1b=",
        "capture_command_x3p00_z0p50_x2p00_3d2d=",
        "capture_command_x1p50_left0p50_x2p00_3d1b=",
        "capture_command_x1p50_left0p50_x2p00_3d2d=",
        "--freeze-ghidra-offset 1000:3D1B",
        "--freeze-ghidra-offset 1000:3D2D",
        "--runtime-freeze-before-bomb",
        "--route-step z:0.50",
        "--route-step left:0.50",
    ]:
        require(helper_tag_open, snippet, "helper_tag_open")
    require_not(
        helper_tag_open,
        "--runtime-freeze-preset late-collapse",
        "helper_tag_open",
    )
    cases += 1

    with_oracle = run_sweep(
        root,
        [
            str(out_base / "oracle"),
            str(root),
            "--dry-run",
            "--route",
            "x:2.00",
        ],
    )
    require(with_oracle, "oracle_commands=2", "with_oracle")
    require(with_oracle, "oracle_command_x2p00_3d2d=", "with_oracle")
    require(with_oracle, "--debug-explosion-playback-oracle", "with_oracle")
    cases += 1

    sweep_module = load_sweep_module(root)
    translated_candidate = sweep_module.oracle_candidate_argument(
        Path("/mnt/c/Tools/lezac_cpp.exe"),
        Path(
            "/mnt/c/Users/andrz/AppData/Local/Temp/"
            "lezac-lane-write-path-check/x2p00/3d2d/"
            "explosion_playback_oracle_original_candidate.txt"
        ),
    )
    expected_translated = (
        "C:\\Users\\andrz\\AppData\\Local\\Temp\\"
        "lezac-lane-write-path-check\\x2p00\\3d2d\\"
        "explosion_playback_oracle_original_candidate.txt"
    )
    if translated_candidate != expected_translated:
        raise RuntimeError(
            "windows_oracle_path translated to "
            f"{translated_candidate!r}, expected {expected_translated!r}"
        )
    linux_path = Path("/mnt/c/Users/andrz/AppData/Local/Temp/candidate.txt")
    linux_candidate = sweep_module.oracle_candidate_argument(
        Path("/usr/local/bin/lezac_cpp"),
        linux_path,
    )
    if linux_candidate != str(linux_path):
        raise RuntimeError(f"linux oracle path was unexpectedly translated: {linux_candidate!r}")
    cases += 1

    custom = run_sweep(
        root,
        [
            str(out_base / "custom"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "forward-collapse",
            "--offset",
            "reverse-debris",
            "--runtime-freeze-preset",
            "none",
            "--runtime-freeze-after-bomb-seconds",
            "0.125",
            "--route",
            "Left:0.25,space:0.75",
        ],
    )
    for snippet in [
        "offsets=2",
        "offset_labels=3d1b,3ec1",
        "offset_addresses=1000:3D1B,1000:3EC1",
        "routes=1",
        "route_labels=left0p25_space0p75",
        "runtime_freeze_preset=none",
        "--freeze-ghidra-offset 1000:3D1B",
        "--freeze-ghidra-offset 1000:3EC1",
        "--runtime-freeze-after-bomb-seconds 0.125",
        "--route-step Left:0.25",
        "--route-step space:0.75",
    ]:
        require(custom, snippet, "custom_routes")
    cases += 1

    gated = run_sweep(
        root,
        [
            str(out_base / "gated"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "forward-debris",
            "--runtime-freeze-preset",
            "none",
            "--runtime-freeze-min-queue-score",
            "0x90",
            "--runtime-freeze-min-debris-nonzero",
            "0x20",
            "--runtime-freeze-min-collapse-nonzero",
            "0x10",
            "--runtime-freeze-min-effect-nonzero",
            "0x10",
            "--runtime-freeze-require-debris-base",
            "0x209e",
            "--runtime-freeze-require-collapse-base",
            "0x6620",
            "--runtime-freeze-require-effect-base",
            "0xc22e",
            "--runtime-freeze-require-high-debris-target-byte",
            "0x05",
            "--runtime-freeze-require-high-debris-word-layer-value",
            "0x0005",
            "--runtime-freeze-require-lane-update-flag",
            "0x01",
            "--runtime-freeze-require-lane-word-global-value",
            "0x8002",
            "--runtime-freeze-require-lane-target-offset-global-value",
            "0x07be",
            "--route",
            "x:2.00",
        ],
    )
    for snippet in [
        "offsets=1",
        "offset_labels=3d2d",
        "runtime_freeze_preset=none",
        "--runtime-freeze-min-queue-score 0x90",
        "--runtime-freeze-min-debris-nonzero 0x20",
        "--runtime-freeze-min-collapse-nonzero 0x10",
        "--runtime-freeze-min-effect-nonzero 0x10",
        "--runtime-freeze-require-debris-base 0x209e",
        "--runtime-freeze-require-collapse-base 0x6620",
        "--runtime-freeze-require-effect-base 0xc22e",
        "--runtime-freeze-require-high-debris-target-byte 0x05",
        "--runtime-freeze-require-high-debris-word-layer-value 0x0005",
        "--runtime-freeze-require-lane-update-flag 0x01",
        "--runtime-freeze-require-lane-word-global-value 0x8002",
        "--runtime-freeze-require-lane-target-offset-global-value 0x07be",
    ]:
        require(gated, snippet, "gated_runtime_freeze")
    cases += 1

    branch_route_manifest = out_base / "branch-anchor-routes.txt"
    branch_route_manifest.write_text(
        "\n".join(
            [
                "promotion=branch_anchor_route_candidates",
                "source_manifest=/tmp/lezac-branch-anchor-route-sweep/manifest.txt",
                "source_environment_preflight=ok",
                "required_targets=high_debris_word_gate,effect_forward_pass_call",
                "matching_routes=2",
                "route_0_label=x2p00_m0p35",
                "route_0_steps=x:2.00,m:0.35",
                "route_0_targets=high_debris_word_gate,effect_forward_pass_call",
                "route_1_label=x3p00_z0p50_x2p00",
                "route_1_steps=x:3.00,z:0.50,x:2.00",
                "route_1_targets=high_debris_word_gate,effect_forward_pass_call",
                "",
            ]
        ),
        encoding="ascii",
    )
    route_manifest_dry = run_sweep(
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
        "offsets=1",
        "offset_labels=3d2d",
        "routes=2",
        "route_labels=x2p00_m0p35,x3p00_z0p50_x2p00",
        "capture_commands=2",
        "route_preset=branch-anchor-route-manifest",
        f"route_manifest={branch_route_manifest.resolve()}",
        "route_manifest_default_offsets=1000:3D2D",
        "capture_command_x2p00_m0p35_3d2d=",
        "capture_command_x3p00_z0p50_x2p00_3d2d=",
        "--freeze-ghidra-offset 1000:3D2D",
        "--route-step x:2.00",
        "--route-step m:0.35",
        "--route-step z:0.50",
        "--route-step x:3.00",
    ]:
        require(route_manifest_dry, snippet, "route_manifest")
    cases += 1

    forward_debris_route_manifest = out_base / "forward-debris-routes.txt"
    forward_debris_route_manifest.write_text(
        "\n".join(
            [
                "promotion=lane_write_forward_debris_route_candidates",
                "source_manifest=/tmp/lezac-forward-debris-sweep/manifest.txt",
                "source_environment_preflight=ok",
                "required_candidate=forward_debris_tag",
                "matching_routes=1",
                "route_0_label=x2p00_m0p35",
                "route_0_steps=x:2.00,m:0.35",
                "route_0_offset_label=3d2d",
                "route_0_offset_address=1000:3D2D",
                "route_0_lane_write_tag=0x4ee8",
                "route_0_lane_write_di=0x0898",
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
        ],
    )
    for snippet in [
        "offsets=1",
        "offset_labels=3d2d",
        "routes=1",
        "route_labels=x2p00_m0p35",
        "capture_commands=1",
        "route_preset=lane-write-forward-debris-route-manifest",
        f"route_manifest={forward_debris_route_manifest.resolve()}",
        "route_manifest_default_offsets=1000:3D2D",
        "capture_command_x2p00_m0p35_3d2d=",
        "--freeze-ghidra-offset 1000:3D2D",
        "--route-step x:2.00",
        "--route-step m:0.35",
    ]:
        require(
            forward_debris_manifest_dry,
            snippet,
            "forward_debris_route_manifest",
        )
    cases += 1

    lane_div_forward_manifest = out_base / "lane-div-forward-routes.txt"
    lane_div_forward_manifest.write_text(
        "\n".join(
            [
                "promotion=lane_div_forward_route_candidates",
                "source_manifest=/tmp/lezac-lane-div-forward/manifest.txt",
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
    lane_div_forward_dry = run_sweep(
        root,
        [
            str(out_base / "lane-div-forward-route-manifest"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-manifest",
            str(lane_div_forward_manifest),
        ],
    )
    for snippet in [
        "offsets=2",
        "offset_labels=3d1b,3d2d",
        "offset_addresses=1000:3D1B,1000:3D2D",
        "routes=1",
        "route_labels=x2p00_m0p35",
        "capture_commands=2",
        "route_preset=lane-div-forward-route-manifest",
        f"route_manifest={lane_div_forward_manifest.resolve()}",
        "route_manifest_default_offsets=1000:3D1B,1000:3D2D",
        "capture_command_x2p00_m0p35_3d1b=",
        "capture_command_x2p00_m0p35_3d2d=",
        "--freeze-ghidra-offset 1000:3D1B",
        "--freeze-ghidra-offset 1000:3D2D",
        "--route-step x:2.00",
        "--route-step m:0.35",
    ]:
        require(
            lane_div_forward_dry,
            snippet,
            "lane_div_forward_route_manifest",
        )
    cases += 1

    lane_div_forward_debris_manifest = out_base / "lane-div-forward-debris-routes.txt"
    lane_div_forward_debris_manifest.write_text(
        "\n".join(
            [
                "promotion=lane_div_forward_debris_route_candidates",
                "source_manifest=/tmp/lezac-lane-div-forward-debris/manifest.txt",
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
    lane_div_forward_debris_dry = run_sweep(
        root,
        [
            str(out_base / "lane-div-forward-debris-route-manifest"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--route-manifest",
            str(lane_div_forward_debris_manifest),
        ],
    )
    for snippet in [
        "offsets=1",
        "offset_labels=3d2d",
        "routes=1",
        "route_labels=x2p00_m0p35",
        "capture_commands=1",
        "route_preset=lane-div-forward-debris-route-manifest",
        f"route_manifest={lane_div_forward_debris_manifest.resolve()}",
        "route_manifest_default_offsets=1000:3D2D",
        "capture_command_x2p00_m0p35_3d2d=",
        "--freeze-ghidra-offset 1000:3D2D",
        "--route-step x:2.00",
        "--route-step m:0.35",
    ]:
        require(
            lane_div_forward_debris_dry,
            snippet,
            "lane_div_forward_debris_route_manifest",
        )
    cases += 1

    route_manifest_conflict = run_sweep(
        root,
        [
            str(out_base / "route-manifest-conflict"),
            str(root),
            "--dry-run",
            "--route",
            "x:2.00",
            "--route-manifest",
            str(branch_route_manifest),
        ],
        expect_success=False,
    )
    require(
        route_manifest_conflict,
        "use either --route or --route-manifest, not both",
        "route_manifest_conflict",
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
        "refusing lane-write route sweep without --approve-procmem and "
        "--approve-runtime-instrumentation",
        "live_refusal",
    )
    require_not(live_refusal, "lane_write_route_sweep_manifest=", "live_refusal")
    cases += 1

    optional_log = out_base / "optional-oracle-error.log"
    optional = sweep_module.run_logged_optional(
        [str(out_base / "missing-oracle-binary")],
        root,
        optional_log,
    )
    if optional.returncode == 0:
        raise RuntimeError("optional oracle failure unexpectedly succeeded")
    require(optional.stdout, "command launch failed:", "optional_oracle_error")
    require(optional_log.read_text(encoding="utf-8"), "command launch failed:",
            "optional_oracle_error")
    cases += 1

    with tempfile.TemporaryDirectory(
        prefix="lezac-lane-write-empty-path-",
        dir=temp_root,
    ) as tmp:
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
    require(live_preflight, "missing_required=", "live_preflight")
    require_not(
        live_preflight,
        "lane_write_route_sweep_manifest=",
        "live_preflight",
    )
    cases += 1

    repo_refusal = run_sweep(
        root,
        [str(root / "lane-write-route-sweep-refusal"), str(root), "--dry-run"],
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

    bad_offset = run_sweep(
        root,
        [
            str(out_base / "bad-offset"),
            str(root),
            "--dry-run",
            "--offset",
            "3D3F",
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
    require(
        no_runtime_gate,
        "lane-write route sweep requires a runtime freeze gate",
        "no_runtime_gate",
    )
    cases += 1

    print(f"lane_write_route_sweep_output=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
