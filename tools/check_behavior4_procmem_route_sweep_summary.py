#!/usr/bin/env python3
"""Check behavior-4 process-memory route-sweep summary classification."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def run_tool(root: Path, args: list[str], expect_success: bool = True) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_behavior4_procmem_route_sweep.py"),
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
            f"summarize_behavior4_procmem_route_sweep.py failed with "
            f"{result.returncode}: {args}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            "summarize_behavior4_procmem_route_sweep.py unexpectedly passed: "
            f"{args}\n{result.stdout}"
        )
    return result.stdout


def run_repo_tool(
    root: Path,
    tool: str,
    args: list[str],
    expect_success: bool = True,
) -> str:
    command = [sys.executable, str(root / "tools" / tool), *args]
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
            f"{tool} failed with {result.returncode}: {args}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(f"{tool} unexpectedly passed: {args}\n{result.stdout}")
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing {snippet!r}\n{text}")


def write_ready_candidate(path: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=behavior4_runtime",
                "source=dosbox-debug-process-memory",
                "temp_copy=1",
                "visual_claim=0",
                "scenario=monster_behavior4_target_selection",
                "level=3",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                "break ghidra=1000:7A6B runtime=01ED:7A6B label=spawner_loop_start",
                "break ghidra=1000:7C2C runtime=01ED:7C2C label=spawner_loop_end",
                "break ghidra=1000:728C runtime=01ED:728C label=behavior4_branch_start",
                "break ghidra=1000:731B runtime=01ED:731B label=behavior4_branch_end",
                "break ghidra=1000:73E5 runtime=01ED:73E5 label=integration_8_8_start",
                "break ghidra=1000:741B runtime=01ED:741B label=integration_8_8_end",
                "spawner index=5 behavior=4 ai0=20 ai1=214 ai2=66 hp=4 spawn_timer=30",
                "actor_before slot=0 behavior=4 x=0x0068 y=0x00a8 vx8=0 vy8=0 motion_timer=0 target=2 hp=4 dead=0",
                "actor_after slot=0 behavior=4 x=0x0069 y=0x00a8 vx8=32 vy8=0 motion_timer=1 target=1 hp=4 dead=0",
                "players p1_dead=0 p2_dead=1 p1_state=0 p2_state=2 target_before=2 target_after=1",
                "",
            ]
        ),
    )


def write_incomplete_candidate(path: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=behavior4_runtime",
                "source=dosbox-debug-process-memory",
                "temp_copy=1",
                "visual_claim=0",
                "scenario=monster_behavior4_target_selection",
                "level=3",
                "# runtime_cs=<runtime-cs>",
                "# runtime_ds=<runtime-ds>",
                "# spawner index=<index> behavior=4",
                "",
            ]
        ),
    )


def write_capture_manifest(path: Path, patch_applied: bool, freeze_observed: str) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=behavior4_process_memory",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                "freeze_runtime=01ED:728C",
                f"freeze_runtime_patch_applied={1 if patch_applied else 0}",
                f"instrumented_freeze_observed={freeze_observed}",
                "",
            ]
        ),
    )


def write_mixed_sweep(base: Path) -> Path:
    ready = base / "ready" / "candidate.txt"
    incomplete = base / "incomplete" / "candidate.txt"
    ready_capture = base / "ready" / "manifest.txt"
    incomplete_capture = base / "incomplete" / "manifest.txt"
    write_ready_candidate(ready)
    write_incomplete_candidate(incomplete)
    write_capture_manifest(ready_capture, True, "runtime_child_memory_freeze_observed")
    write_capture_manifest(incomplete_capture, True, "0")
    manifest = base / "manifest.txt"
    write_text(
        manifest,
        "\n".join(
            [
                "capture=behavior4_procmem_route_sweep",
                "asset_dir=/tmp/lezac-assets",
                "scenario=monster_behavior4_target_selection",
                "expected_level=3",
                "targets=2",
                "target_names=behavior4_branch_start,integration_8_8_start",
                "timings=before_route",
                "routes=2",
                "route_labels=x2p00,x3p00_z0p50_x2p00",
                "environment_preflight=ok",
                "capture_command_behavior4_branch_start_before_route_x2p00=env LEZAC_BEHAVIOR4_ROUTE_STEPS=x:2.00 bash helper",
                "capture_status_behavior4_branch_start_before_route_x2p00=behavior4_procmem=ok mode=capture target=behavior4_branch_start ghidra=1000:728C runtime_cs=01ED runtime_ds=0C8F freeze_runtime=01ED:728C freeze_observed=runtime_child_memory_freeze_observed manifest="
                + str(ready_capture)
                + " candidate_fixture="
                + str(ready),
                "capture_command_integration_8_8_start_before_route_x3p00_z0p50_x2p00=env LEZAC_BEHAVIOR4_ROUTE_STEPS=x:3.00,z:0.50,x:2.00 bash helper",
                "capture_status_integration_8_8_start_before_route_x3p00_z0p50_x2p00=behavior4_procmem=ok mode=capture target=integration_8_8_start ghidra=1000:73E5 runtime_cs=01ED runtime_ds=0C8F freeze_runtime=01ED:73E5 freeze_observed=unknown manifest="
                + str(incomplete_capture)
                + " candidate_fixture="
                + str(incomplete),
                "capture_command_behavior4_branch_end_before_bomb_x1p00=env LEZAC_BEHAVIOR4_ROUTE_STEPS=x:1.00 bash helper",
                "",
            ]
        ),
    )
    return manifest


def write_ready_sweep(base: Path) -> Path:
    ready = base / "ready" / "candidate.txt"
    ready_capture = base / "ready" / "manifest.txt"
    write_ready_candidate(ready)
    write_capture_manifest(ready_capture, True, "runtime_child_memory_freeze_observed")
    manifest = base / "manifest.txt"
    write_text(
        manifest,
        "\n".join(
            [
                "capture=behavior4_procmem_route_sweep",
                "scenario=monster_behavior4_target_selection",
                "expected_level=3",
                "targets=1",
                "target_names=behavior4_branch_start",
                "timings=before_route",
                "routes=1",
                "route_labels=x2p00",
                "environment_preflight=ok",
                "capture_command_behavior4_branch_start_before_route_x2p00=env bash helper",
                "capture_status_behavior4_branch_start_before_route_x2p00=behavior4_procmem=ok mode=capture target=behavior4_branch_start ghidra=1000:728C runtime_cs=01ED runtime_ds=0C8F freeze_observed=runtime_child_memory_freeze_observed manifest="
                + str(ready_capture)
                + " candidate_fixture="
                + str(ready),
                "",
            ]
        ),
    )
    return manifest


def write_no_freeze_sweep(base: Path) -> Path:
    ready = base / "ready" / "candidate.txt"
    ready_capture = base / "ready" / "manifest.txt"
    write_ready_candidate(ready)
    write_capture_manifest(ready_capture, True, "0")
    manifest = base / "manifest.txt"
    write_text(
        manifest,
        "\n".join(
            [
                "capture=behavior4_procmem_route_sweep",
                "scenario=monster_behavior4_target_selection",
                "expected_level=3",
                "targets=1",
                "target_names=behavior4_branch_start",
                "timings=before_route",
                "routes=1",
                "route_labels=x2p00",
                "environment_preflight=skipped",
                "capture_command_behavior4_branch_start_before_route_x2p00=env bash helper",
                "capture_status_behavior4_branch_start_before_route_x2p00=behavior4_procmem=ok mode=capture target=behavior4_branch_start ghidra=1000:728C runtime_cs=01ED runtime_ds=0C8F freeze_observed=unknown manifest="
                + str(ready_capture)
                + " candidate_fixture="
                + str(ready),
                "",
            ]
        ),
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check behavior-4 process-memory route-sweep summaries."
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
    )
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-behavior4-procmem-summary-") as tmp:
        base = Path(tmp)

        mixed = write_mixed_sweep(base / "mixed")
        mixed_out = run_tool(root, [str(mixed)])
        for snippet in [
            "behavior4_procmem_route_sweep_summary=ok",
            "scenario=monster_behavior4_target_selection",
            "expected_level=3",
            "targets=2",
            "capture_commands=3",
            "completed_captures=2",
            "observed_freezes=1",
            "patched_no_freeze_candidates=1",
            "ready_candidates=1",
            "incomplete_candidates=1",
            "missing_candidates=1",
            "missing_labels=behavior4_branch_end_before_bomb_x1p00",
            "behavior4_procmem_route_sweep_detail label=behavior4_branch_start_before_route_x2p00",
            "candidate_status=ready",
            "runtime_patch_applied=1",
            "freeze_observed=1",
            "behavior4_procmem_route_sweep_detail label=integration_8_8_start_before_route_x3p00_z0p50_x2p00",
            "candidate_status=incomplete",
            "candidate_missing=runtime_cs,runtime_ds,spawner,actor_before,actor_after,players,break_7a6b,break_7c2c,break_728c,break_731b,break_73e5,break_741b",
            "candidate_placeholders=1",
            "freeze_observed=0",
            "oracle_flag=--debug-behavior4-runtime-oracle",
            "environment_preflight=ok",
        ]:
            require(mixed_out, snippet, "mixed_summary")
        cases += 1

        require_ready_fail = run_tool(root, [str(mixed), "--require-ready"], False)
        require(require_ready_fail, "reason=candidates_not_ready", "require_ready")
        require(require_ready_fail, "incomplete_candidates=1", "require_ready")
        require(require_ready_fail, "missing_candidates=1", "require_ready")
        cases += 1

        ready = write_ready_sweep(base / "ready")
        ready_manifest = base / "ready-manifest" / "ready_manifest.txt"
        ready_out = run_tool(
            root,
            [
                str(ready),
                "--require-ready",
                "--require-observed-freeze",
                "--require-environment-preflight",
                "--write-ready-manifest",
                str(ready_manifest),
            ],
        )
        require(ready_out, "ready_candidates=1", "ready_summary")
        require(ready_out, "observed_freezes=1", "ready_summary")
        require(ready_out, "patched_no_freeze_candidates=0", "ready_summary")
        require(ready_out, "behavior4_procmem_ready_manifest=ok", "ready_manifest")
        require(ready_out, f"path={ready_manifest.resolve()}", "ready_manifest")
        ready_text = ready_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=debug_capture_ready_candidates",
            f"source_root={ready.parent}",
            "oracle_binary=./build/lezac_cpp",
            "ready_candidates=1",
            "candidate_0_capture=behavior4_runtime",
            "candidate_0_scenario=monster_behavior4_target_selection",
            "candidate_0_level=3",
            "candidate_0_environment_preflight=ok",
            "candidate_0_runtime_metadata=observed",
            "candidate_0_runtime_cs=01ED",
            "candidate_0_runtime_ds=0C8F",
            f"candidate_0_manifest={ready}",
            "candidate_0_oracle=behavior4",
            "candidate_0_oracle_flag=--debug-behavior4-runtime-oracle",
            "candidate_0_source_label=behavior4_branch_start_before_route_x2p00",
            "candidate_0_target=behavior4_branch_start",
            "candidate_0_timing=before_route",
            "candidate_0_route_label=x2p00",
        ]:
            require(ready_text, snippet, "ready_manifest_text")
        ready_dry_run = run_repo_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [str(ready_manifest), "--dry-run", "--oracle-binary", "./build/lezac_cpp"],
        )
        require(
            ready_dry_run,
            "debug_capture_ready_manifest=ok mode=dry_run",
            "ready_manifest_dry_run",
        )
        require(
            ready_dry_run,
            "--debug-behavior4-runtime-oracle",
            "ready_manifest_dry_run",
        )
        cases += 1

        no_freeze = write_no_freeze_sweep(base / "no-freeze")
        no_freeze_out = run_tool(
            root, [str(no_freeze), "--require-observed-freeze"], False
        )
        require(no_freeze_out, "reason=no_observed_freezes", "no_freeze")
        require(no_freeze_out, "patched_no_freeze_candidates=1", "no_freeze")
        cases += 1

        preflight_out = run_tool(
            root, [str(no_freeze), "--require-environment-preflight"], False
        )
        require(
            preflight_out,
            "reason=environment_preflight_not_ok environment_preflight=skipped",
            "preflight",
        )
        cases += 1

        bad_manifest = base / "bad" / "manifest.txt"
        write_text(bad_manifest, "capture=other\n")
        bad_out = run_tool(root, [str(bad_manifest)], False)
        require(bad_out, "unsupported capture type: other", "bad_manifest")
        cases += 1

    print(f"behavior4_procmem_route_sweep_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
