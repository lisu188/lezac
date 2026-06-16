#!/usr/bin/env python3
"""Check sound-callsite process-memory route-sweep summary classification."""

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
        str(root / "tools" / "summarize_sound_callsite_route_sweep.py"),
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
            f"summarize_sound_callsite_route_sweep.py failed with "
            f"{result.returncode}: {args}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            "summarize_sound_callsite_route_sweep.py unexpectedly passed: "
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
                "capture=sound_callsite",
                "source=dosbox-debug-process-memory",
                "temp_copy=1",
                "visual_claim=0",
                "instrumented_runtime_child_memory=1",
                "target=actor_update_runtime_cursor_0035_sound",
                "scenario=actor_update_runtime_cursor_0035_sound",
                "capture_class=actor_contact_runtime",
                "static_region=actor_update",
                "level=1",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                "break ghidra=1000:6924 runtime=01ED:6924 label=actor_update_cursor_0035 observed=process_memory_runtime_freeze_runtime_child_memory_freeze_observed",
                "break ghidra=1000:165A runtime=01ED:165A label=sound_priority_latch observed=process_memory_runtime_latch_trace",
                "sound_request label=actor_update_cursor_0035 callsite=1000:6924 latch=1000:165A cursor=0x0035 priority=5 active_before=0 current_priority_before=0 pending_cursor=0x0035 pending_priority=5 accepted=1 active_after=1 current_priority_after=5 current_cursor_after=0x0035 direct_sweep=0",
                "dump DS:2070",
                "0C8F:2070 00 00 00 00 35 00 00 00 00 00 00 00 00 00 00 00",
                "dump DS:78C0",
                "0C8F:78C0 35 00",
                "dump DS:7990",
                "0C8F:7990 00 00 00 00 00 00 00 00 00 00 00 00 00 00 05 05",
                "dump DS:79C0",
                "0C8F:79C0 00 00 00 00 01 00 00 00",
                "",
            ]
        ),
    )


def write_incomplete_candidate(path: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=sound_callsite",
                "source=dosbox-debug-process-memory",
                "temp_copy=1",
                "visual_claim=0",
                "target=actor_update_runtime_cursor_0035_sound",
                "scenario=actor_update_runtime_cursor_0035_sound",
                "level=1",
                "# runtime_cs=<runtime-cs>",
                "# runtime_ds=<runtime-ds>",
                "break ghidra=1000:6924 runtime=<runtime-cs>:6924 label=actor_update_cursor_0035 observed=process_memory_runtime_freeze_unknown",
                "break ghidra=1000:165A runtime=<runtime-cs>:165A label=sound_priority_latch observed=fill_from_debugger_or_latch_trace",
                "# sound_request label=actor_update_cursor_0035 callsite=1000:6924 latch=1000:165A cursor=0x0035 priority=5 active_before=<0-or-1>",
                "",
            ]
        ),
    )


def write_mixed_sweep(base: Path) -> Path:
    ready = base / "ready" / "candidate.txt"
    incomplete = base / "incomplete" / "candidate.txt"
    write_ready_candidate(ready)
    write_incomplete_candidate(incomplete)
    manifest = base / "manifest.txt"
    write_text(
        manifest,
        "\n".join(
            [
                "capture=sound_callsite_route_sweep",
                "asset_dir=/tmp/lezac-assets",
                "target=actor_update_runtime_cursor_0035_sound",
                "timings=before_route",
                "routes=2",
                "route_labels=x2p00,x3p00_z0p50_x2p00",
                "environment_preflight=ok",
                "capture_command_before_route_x2p00=env LEZAC_SOUND_CALLSITE_ROUTE_STEPS=x:2.00 bash helper",
                "capture_status_before_route_x2p00=sound_callsite_procmem=ok mode=capture target=actor_update_runtime_cursor_0035_sound ghidra=1000:6924 runtime_cs=01ED runtime_ds=0C8F freeze_runtime=01ED:6924 freeze_observed=runtime_child_memory_freeze_observed candidate_fixture="
                + str(ready),
                "capture_command_before_route_x3p00_z0p50_x2p00=env LEZAC_SOUND_CALLSITE_ROUTE_STEPS=x:3.00,z:0.50,x:2.00 bash helper",
                "capture_status_before_route_x3p00_z0p50_x2p00=sound_callsite_procmem=ok mode=capture target=actor_update_runtime_cursor_0035_sound ghidra=1000:6924 runtime_cs=01ED runtime_ds=0C8F freeze_runtime=01ED:6924 freeze_observed=unknown candidate_fixture="
                + str(incomplete),
                "capture_command_before_bomb_x1p00=env LEZAC_SOUND_CALLSITE_ROUTE_STEPS=x:1.00 bash helper",
                "",
            ]
        ),
    )
    return manifest


def write_ready_sweep(base: Path) -> Path:
    ready = base / "ready" / "candidate.txt"
    write_ready_candidate(ready)
    manifest = base / "manifest.txt"
    write_text(
        manifest,
        "\n".join(
            [
                "capture=sound_callsite_route_sweep",
                "target=actor_update_runtime_cursor_0035_sound",
                "timings=before_route",
                "routes=1",
                "route_labels=x2p00",
                "environment_preflight=ok",
                "capture_command_before_route_x2p00=env bash helper",
                "capture_status_before_route_x2p00=sound_callsite_procmem=ok mode=capture target=actor_update_runtime_cursor_0035_sound ghidra=1000:6924 runtime_cs=01ED runtime_ds=0C8F freeze_observed=runtime_child_memory_freeze_observed candidate_fixture="
                + str(ready),
                "",
            ]
        ),
    )
    return manifest


def write_no_freeze_sweep(base: Path) -> Path:
    ready = base / "ready" / "candidate.txt"
    write_ready_candidate(ready)
    manifest = base / "manifest.txt"
    write_text(
        manifest,
        "\n".join(
            [
                "capture=sound_callsite_route_sweep",
                "target=actor_update_runtime_cursor_0035_sound",
                "timings=before_route",
                "routes=1",
                "route_labels=x2p00",
                "environment_preflight=skipped",
                "capture_command_before_route_x2p00=env bash helper",
                "capture_status_before_route_x2p00=sound_callsite_procmem=ok mode=capture target=actor_update_runtime_cursor_0035_sound ghidra=1000:6924 runtime_cs=01ED runtime_ds=0C8F freeze_observed=unknown candidate_fixture="
                + str(ready),
                "",
            ]
        ),
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check sound-callsite process-memory route-sweep summaries."
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
    with tempfile.TemporaryDirectory(prefix="lezac-sound-callsite-summary-") as tmp:
        base = Path(tmp)

        mixed = write_mixed_sweep(base / "mixed")
        mixed_out = run_tool(root, [str(mixed)])
        for snippet in [
            "sound_callsite_route_sweep_summary=ok",
            "target=actor_update_runtime_cursor_0035_sound",
            "capture_commands=3",
            "completed_captures=2",
            "observed_freezes=1",
            "ready_candidates=1",
            "incomplete_candidates=1",
            "missing_candidates=1",
            "missing_labels=before_bomb_x1p00",
            "sound_callsite_route_sweep_detail label=before_route_x2p00",
            "candidate_status=ready",
            "sound_callsite_route_sweep_detail label=before_route_x3p00_z0p50_x2p00",
            "candidate_status=incomplete",
            "candidate_missing=runtime_cs,runtime_ds,sound_request",
            "candidate_placeholders=1",
            "oracle_flag=--debug-sound-callsite-oracle",
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
        require(ready_out, "sound_callsite_ready_manifest=ok", "ready_manifest")
        require(ready_out, f"path={ready_manifest.resolve()}", "ready_manifest")
        ready_text = ready_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=debug_capture_ready_candidates",
            f"source_root={ready.parent}",
            "oracle_binary=./build/lezac_cpp",
            "ready_candidates=1",
            "candidate_0_capture=sound_callsite",
            "candidate_0_scenario=actor_update_runtime_cursor_0035_sound",
            "candidate_0_level=1",
            "candidate_0_environment_preflight=ok",
            "candidate_0_runtime_metadata=observed",
            "candidate_0_runtime_cs=01ED",
            "candidate_0_runtime_ds=0C8F",
            f"candidate_0_manifest={ready}",
            "candidate_0_oracle=sound_callsite",
            "candidate_0_oracle_flag=--debug-sound-callsite-oracle",
            "candidate_0_source_label=before_route_x2p00",
            "candidate_0_target=actor_update_runtime_cursor_0035_sound",
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
            "--debug-sound-callsite-oracle",
            "ready_manifest_dry_run",
        )
        cases += 1

        result_manifest = base / "ready-result" / "result_manifest.txt"
        run_repo_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [
                str(ready_manifest),
                "--dry-run",
                "--oracle-binary",
                "./build/lezac_cpp",
                "--write-result-manifest",
                str(result_manifest),
            ],
        )
        result_summary = run_repo_tool(
            root,
            "summarize_debug_capture_ready_results.py",
            [str(result_manifest)],
        )
        for snippet in [
            "debug_capture_ready_result_summary=ok",
            "mode=dry_run",
            "ready_candidates=1",
            "planned=1",
            "candidate_result index=0 capture=sound_callsite",
            "oracle=sound_callsite",
            "oracle_flag=--debug-sound-callsite-oracle",
            "--debug-sound-callsite-oracle",
        ]:
            require(result_summary, snippet, "ready_result_summary")
        cases += 1

        no_freeze = write_no_freeze_sweep(base / "no-freeze")
        no_freeze_out = run_tool(
            root, [str(no_freeze), "--require-observed-freeze"], False
        )
        require(no_freeze_out, "reason=no_observed_freezes", "no_freeze")
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

    print(f"sound_callsite_route_sweep_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
