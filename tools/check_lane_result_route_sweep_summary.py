#!/usr/bin/env python3
"""Exercise lane-result route-sweep summary and promotion output."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from ready_result_checker_support import write_original_fixture_tree


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_summary(
    root: Path,
    args: list[str],
    expect_success: bool = True,
    env: dict[str, str] | None = None,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_lane_result_route_sweep.py"),
        *args,
    ]
    process_env = os.environ.copy()
    if env is not None:
        process_env.update(env)
    result = subprocess.run(
        command,
        cwd=root,
        env=process_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError(
            f"summary command failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"summary command unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    return result.stdout


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def write_candidate(path: Path, freeze: bool, placeholder: bool = False) -> None:
    lane_lines = []
    if freeze:
        lane_lines = [
            "instrumented_lane_result_scratch_present=1",
            "instrumented_lane_result_cs_offset=0xf280",
            "instrumented_lane_result_kind=forward",
            "instrumented_lane_result_output=0x0004",
            "instrumented_lane_result_es=0x2b3c",
            "instrumented_lane_result_di=0x78d2",
            "instrumented_lane_result_arg_offset=0x78d2",
            "instrumented_lane_result_arg_segment=0x2b3c",
            "instrumented_lane_result_result_local=0x0004",
            "instrumented_lane_result_active_count=0x0001",
            "instrumented_lane_result_loop_index=0x0001",
            "instrumented_lane_result_target_before=0x0010",
        ]
    else:
        lane_lines = ["instrumented_lane_result_scratch_present=0"]
    if placeholder:
        lane_lines.append("# fill me: <instrumented_lane_result_output>")
    write_text(
        path,
        "\n".join(
            [
                "capture=explosion_playback",
                "source=synthetic",
                "temp_copy=1",
                "visual_claim=0",
                "instrumented_freeze_observed=" + ("1" if freeze else "0"),
                "instrumented_freeze_patch_mode=lane-result-cs-scratch",
                "freeze_expected_old_bytes=268805",
                "freeze_old_bytes=268805",
                "runtime_freeze_patch_applied=1",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                *lane_lines,
                "",
            ]
        ),
    )


def write_runtime_manifest(path: Path, candidate: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=lane_result_runtime",
                "asset_dir=/repo",
                "cpp_exe=./build/lezac_cpp",
                "offsets=1",
                "offset_labels=3d3f",
                "offset_addresses=1000:3D3F",
                "preflight=lane_result_preflight=ok",
                f"candidate_3d3f={candidate}",
                "skip_oracle=1",
                "",
            ]
        ),
    )


def write_route_sweep(path: Path, labels: list[str], child_manifests: list[Path]) -> None:
    lines = [
        "capture=lane_result_route_sweep",
        "asset_dir=/repo",
        "offset=forward",
        f"routes={len(labels)}",
        "route_labels=" + ",".join(labels),
        "environment_preflight=ok",
    ]
    for label, child in zip(labels, child_manifests):
        lines.append(
            f"capture_status_{label}=lane_result_capture_orchestrator=ok "
            f"mode=capture out_dir=/tmp/{label} candidates=1 "
            "offset_labels=3d3f offset_addresses=1000:3D3F "
            f"manifest={child}"
        )
    lines.append("")
    write_text(path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-result route-sweep summary behavior."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-lane-result-summary-") as tmp:
        base = Path(tmp)
        ready_candidate = base / "ready" / "candidate.txt"
        no_freeze_candidate = base / "no_freeze" / "candidate.txt"
        incomplete_candidate = base / "incomplete" / "candidate.txt"
        write_candidate(ready_candidate, freeze=True)
        write_candidate(no_freeze_candidate, freeze=False)
        write_candidate(incomplete_candidate, freeze=True, placeholder=True)

        ready_manifest = base / "ready" / "manifest.txt"
        no_freeze_manifest = base / "no_freeze" / "manifest.txt"
        incomplete_manifest = base / "incomplete" / "manifest.txt"
        write_runtime_manifest(ready_manifest, ready_candidate)
        write_runtime_manifest(no_freeze_manifest, no_freeze_candidate)
        write_runtime_manifest(incomplete_manifest, incomplete_candidate)

        sweep_manifest = base / "manifest.txt"
        write_route_sweep(
            sweep_manifest,
            ["ready", "no_freeze"],
            [ready_manifest, no_freeze_manifest],
        )
        summary = run_summary(root, [str(sweep_manifest)])
        for snippet in [
            "lane_result_route_sweep_summary=ok",
            "mode=route",
            "environment_preflight=ok",
            "routes=2",
            "candidates=2",
            "observed_freezes=1",
            "ready_candidates=1",
            "no_freeze_candidates=1",
            "incomplete_candidates=0",
            "missing_candidates=0",
            "observed_offsets=3d3f",
            "missing_offsets=none",
            "candidate route=ready offset=3d3f",
            "candidate_status=ready",
            "candidate route=no_freeze offset=3d3f",
            "candidate_status=no_freeze",
            "oracle_flag=--debug-explosion-playback-oracle",
        ]:
            require(summary, snippet, "mixed_summary")
        cases += 1

        required = run_summary(root, [str(sweep_manifest), "--require-ready"])
        require(required, "ready_candidates=1", "mixed_require_ready")
        cases += 1

        required_preflight = run_summary(
            root, [str(sweep_manifest), "--require-environment-preflight"]
        )
        require(
            required_preflight,
            "environment_preflight=ok",
            "mixed_require_environment_preflight",
        )
        cases += 1

        promotion_manifest = base / "promotion" / "manifest.txt"
        promoted = run_summary(
            root,
            [
                str(sweep_manifest),
                "--write-ready-manifest",
                str(promotion_manifest),
            ],
        )
        require(promoted, "lane_result_ready_manifest=ok", "promotion_output")
        require(promoted, f"path={promotion_manifest.resolve()}", "promotion_output")
        promotion_text = promotion_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=lane_result_ready_candidates",
            "ready_candidates=1",
            "source_environment_preflight=ok",
            "candidate_0_route=ready",
            "candidate_0_offset_label=3d3f",
            "candidate_0_offset_address=1000:3D3F",
            f"candidate_0_fixture={ready_candidate}",
            "candidate_0_oracle=explosion_playback",
            "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
        ]:
            require(promotion_text, snippet, "promotion_manifest")
        cases += 1

        original_root = base / "original_root"
        original_fixture = write_original_fixture_tree(
            original_root,
            "explosion_playback_oracle_original_writer_unledgered.txt",
            runtime_ds="0C8F",
            include_ledger_entry=False,
        )
        write_candidate(original_fixture, freeze=True)
        bad_original_runtime = base / "bad_original" / "manifest.txt"
        write_runtime_manifest(bad_original_runtime, original_fixture)
        bad_original_sweep = base / "bad_original_sweep.txt"
        write_route_sweep(
            bad_original_sweep,
            ["original"],
            [bad_original_runtime],
        )
        bad_original = run_summary(
            root,
            [
                str(bad_original_sweep),
                "--write-ready-manifest",
                str(base / "bad_original_promotion.txt"),
            ],
            expect_success=False,
            env={"LEZAC_READY_RESULT_REPO_ROOT": str(original_root)},
        )
        require(
            bad_original,
            "candidate_0_fixture explosion_playback_oracle_original_writer_unledgered.txt "
            "is missing from runtime evidence ledger",
            "bad_original_writer_fixture",
        )
        cases += 1

        no_ready_sweep = base / "no_ready_manifest.txt"
        write_route_sweep(no_ready_sweep, ["no_freeze"], [no_freeze_manifest])
        no_ready = run_summary(
            root, [str(no_ready_sweep), "--require-ready"], expect_success=False
        )
        require(no_ready, "reason=no_ready_candidates", "no_ready_required")
        require(no_ready, "no_freeze_candidates=1", "no_ready_required")
        cases += 1

        incomplete_sweep = base / "incomplete_manifest.txt"
        write_route_sweep(
            incomplete_sweep,
            ["ready", "incomplete"],
            [ready_manifest, incomplete_manifest],
        )
        incomplete = run_summary(
            root, [str(incomplete_sweep), "--require-ready"], expect_success=False
        )
        require(incomplete, "reason=candidates_not_ready", "incomplete_required")
        require(incomplete, "incomplete_candidates=1", "incomplete_required")
        require(incomplete, "candidate_placeholders=1", "incomplete_required")
        cases += 1

        direct = run_summary(root, [str(ready_manifest)])
        require(direct, "mode=runtime", "direct_runtime")
        require(direct, "environment_preflight=unknown", "direct_runtime")
        require(direct, "routes=1", "direct_runtime")
        require(direct, "candidate route=direct offset=3d3f", "direct_runtime")
        cases += 1

        missing_preflight = run_summary(
            root,
            [str(ready_manifest), "--require-environment-preflight"],
            expect_success=False,
        )
        require(
            missing_preflight,
            "reason=environment_preflight_not_ok",
            "missing_environment_preflight",
        )
        require(
            missing_preflight,
            "environment_preflight=unknown",
            "missing_environment_preflight",
        )
        cases += 1

    print(f"lane_result_route_sweep_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
