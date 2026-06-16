#!/usr/bin/env python3
"""Check synthetic actor dispatch-gate sweep summary output."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import shlex
import sys
import tempfile

from ready_result_checker_support import write_original_fixture_tree


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_summary(
    root: Path,
    manifest: Path,
    expect_success: bool = True,
    extra_args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_actor_dispatch_gate_sweep.py"),
        str(manifest),
    ]
    if extra_args:
        command.extend(extra_args)
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
            f"sweep summary failed with {result.returncode}: {manifest}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"sweep summary unexpectedly passed: {manifest}\n{result.stdout}"
        )
    return result


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check actor dispatch-gate sweep summary behavior."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-actor-dispatch-summary-") as tmp:
        base = Path(tmp)
        dispatch = base / "dispatch"
        gate5 = dispatch / "actor_update_gate5" / "manifest.txt"
        gate6 = dispatch / "actor_update_gate6" / "manifest.txt"
        write_text(
            gate5,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=actor_update_gate5",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x2p00",
                    "environment_preflight=skipped",
                    "capture_status_x2p00=actor_contact_procmem=ok mode=capture target=actor_update_gate5 ghidra=1000:65A2 runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:65A2 freeze_observed=0 manifest=/tmp/gate5/manifest.txt raw_dump=/tmp/gate5/raw.txt candidate_fixture=/tmp/gate5/candidate_fixture.txt procmem_manifest=/tmp/gate5/procmem_manifest.txt",
                    "",
                ]
            ),
        )
        write_text(
            gate6,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=actor_update_gate6",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x3p00",
                    "environment_preflight=skipped",
                    "capture_status_x3p00=actor_contact_procmem=ok mode=capture target=actor_update_gate6 ghidra=1000:654E runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:654E freeze_observed=1 manifest=/tmp/gate6/manifest.txt raw_dump=/tmp/gate6/raw.txt candidate_fixture=/tmp/gate6/candidate_fixture.txt procmem_manifest=/tmp/gate6/procmem_manifest.txt",
                    "",
                ]
            ),
        )
        dispatch_manifest = dispatch / "manifest.txt"
        write_text(
            dispatch_manifest,
            "\n".join(
                [
                    "capture=actor_dispatch_gate_sweep",
                    "asset_dir=/repo",
                    "targets=actor_update_gate5,actor_update_gate6",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x2p00",
                    "environment_preflight=ok",
                    f"sweep_manifest_actor_update_gate5={gate5}",
                    f"sweep_manifest_actor_update_gate6={gate6}",
                    "",
                ]
            ),
        )
        result = run_summary(root, dispatch_manifest).stdout
        for snippet in [
            "actor_dispatch_gate_sweep_summary=ok",
            "capture=actor_dispatch_gate_sweep",
            "mode=dispatch",
            "environment_preflight=ok",
            "child_environment_preflights=skipped",
            "targets=2",
            "route_sweeps=2",
            "captures=2",
            "freezes=1",
            "dispatch_gate_freezes=1",
            "ready_candidates=0",
            "incomplete_candidates=0",
            "missing_candidates=1",
            "none_candidates=0",
            "observed_targets=actor_update_gate6",
            "observed_dispatch_gates=actor_update_gate6",
            "missing_targets=actor_update_gate5",
            "candidate_fixtures=/tmp/gate6/candidate_fixture.txt",
            "freeze target=actor_update_gate6 dispatch_gate_candidate=actor_update_gate6 route=x3p00 ghidra=1000:654E",
            "candidate_status=missing candidate_missing=file candidate_placeholders=0",
            "oracle=actor_update oracle_flag=--debug-actor-update-runtime-oracle",
            "oracle_command=./build/lezac_cpp --debug-actor-update-runtime-oracle /tmp/gate6/candidate_fixture.txt",
        ]:
            require(result, snippet, "dispatch_manifest")
        cases += 1

        dispatch_gate_required = run_summary(
            root,
            dispatch_manifest,
            extra_args=["--require-dispatch-gate-freeze"],
        ).stdout
        require(
            dispatch_gate_required,
            "observed_dispatch_gates=actor_update_gate6",
            "dispatch_gate_required",
        )
        cases += 1

        duplicate_gate_manifest = base / "duplicate_gate" / "manifest.txt"
        write_text(
            duplicate_gate_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=actor_update_gate6",
                    "timings=before_route",
                    "routes=2",
                    "route_labels=x3p00,x3p50",
                    "environment_preflight=ok",
                    "capture_status_x3p00=actor_contact_procmem=ok mode=capture target=actor_update_gate6 ghidra=1000:654E runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:654E freeze_observed=1 raw_dump=/tmp/dup/raw-a.txt candidate_fixture=/tmp/dup/candidate-a.txt",
                    "capture_status_x3p50=actor_contact_procmem=ok mode=capture target=actor_update_gate6 ghidra=1000:654E runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:654E freeze_observed=1 raw_dump=/tmp/dup/raw-b.txt candidate_fixture=/tmp/dup/candidate-b.txt",
                    "",
                ]
            ),
        )
        duplicate_gate = run_summary(root, duplicate_gate_manifest).stdout
        for snippet in [
            "freezes=2",
            "dispatch_gate_freezes=2",
            "observed_targets=actor_update_gate6",
            "observed_dispatch_gates=actor_update_gate6",
        ]:
            require(duplicate_gate, snippet, "duplicate_gate_manifest")
        cases += 1

        preflight_required = run_summary(
            root,
            dispatch_manifest,
            extra_args=["--require-environment-preflight"],
        ).stdout
        require(
            preflight_required,
            "environment_preflight=ok",
            "dispatch_preflight_required",
        )
        cases += 1

        custom_binary = run_summary(
            root,
            dispatch_manifest,
            extra_args=["--oracle-binary", "/tmp/lezac cpp/lezac_cpp"],
        ).stdout
        require(
            custom_binary,
            "oracle_command='/tmp/lezac cpp/lezac_cpp' "
            "--debug-actor-update-runtime-oracle /tmp/gate6/candidate_fixture.txt",
            "custom_oracle_binary",
        )
        cases += 1

        ready_candidate = base / "ready" / "actor_update_candidate.txt"
        write_text(
            ready_candidate,
            "\n".join(
                [
                    "capture=actor_update_runtime",
                    "source=synthetic",
                    "temp_copy=1",
                    "visual_claim=0",
                    "scenario=object_collision_jump_live",
                    "level=1",
                    "runtime_cs=01ED",
                    "runtime_ds=0F3C",
                    "break ghidra=1000:5CB0 runtime=01ED:5CB0 label=contact_scanner_start",
                    "break ghidra=1000:604F runtime=01ED:604F label=contact_scanner_end",
                    "break ghidra=1000:6053 runtime=01ED:6053 label=actor_update_start",
                    "break ghidra=1000:777F runtime=01ED:777F label=actor_update_end",
                    "actor_before slot=0 behavior=3 kind=1 state=0 x=0x0068 y=0x00a8 vx8=32 vy8=0 hp=3 flags=0x0000 contact=0 on_ground=1",
                    "actor_after slot=0 behavior=3 kind=1 state=0 x=0x0069 y=0x00a8 vx8=32 vy8=0 hp=3 flags=0x0005 contact=1 on_ground=1",
                    "contact_scan subject_slot=0 other_slot=1 flags_before=0x0000 flags_after=0x0005 contact=1 player_contact=0 monster_contact=0 object_contact=1 damage_pending=0",
                    "tile_probe tile_x=13 tile_y=22 tile=0x0025 object=0x0013 passable=0 standable=1",
                    "",
                ]
            ),
        )
        ready_manifest = base / "ready" / "manifest.txt"
        write_text(
            ready_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
            "target=actor_update_gate6",
            "timings=before_route",
            "routes=1",
            "route_labels=x3p00",
            "environment_preflight=ok",
            f"capture_status_x3p00=actor_contact_procmem=ok mode=capture target=actor_update_gate6 ghidra=1000:654E runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:654E freeze_observed=1 raw_dump=/tmp/ready/raw.txt candidate_fixture={ready_candidate}",
                    "",
                ]
            ),
        )
        ready = run_summary(root, ready_manifest).stdout
        for snippet in [
            "ready_candidates=1",
            "dispatch_gate_freezes=1",
            "incomplete_candidates=0",
            "missing_candidates=0",
            "none_candidates=0",
            "candidate_status=ready",
            "candidate_missing=none",
            "candidate_placeholders=0",
            "oracle=actor_update oracle_flag=--debug-actor-update-runtime-oracle",
        ]:
            require(ready, snippet, "ready_actor_candidate")
        cases += 1

        ready_required = run_summary(
            root,
            ready_manifest,
            extra_args=["--require-ready"],
        ).stdout
        require(ready_required, "candidate_status=ready", "ready_required")
        cases += 1

        ready_promotion_manifest = base / "ready" / "promotion_manifest.txt"
        ready_promotion = run_summary(
            root,
            ready_manifest,
            extra_args=["--write-ready-manifest", str(ready_promotion_manifest)],
        ).stdout
        for snippet in [
            "actor_dispatch_gate_ready_manifest=ok",
            f"path={ready_promotion_manifest.resolve()}",
            "ready_candidates=1",
        ]:
            require(ready_promotion, snippet, "ready_promotion_output")
        promotion_text = ready_promotion_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=actor_dispatch_gate_ready_candidates",
            f"source_manifest={ready_manifest.resolve()}",
            "source_environment_preflight=ok",
            "child_environment_preflights=none",
            "oracle_binary=./build/lezac_cpp",
            "ready_candidates=1",
            "candidate_0_target=actor_update_gate6",
            "candidate_0_route=x3p00",
            "candidate_0_ghidra=1000:654E",
            f"candidate_0_fixture={ready_candidate}",
            "candidate_0_oracle=actor_update",
            "candidate_0_oracle_flag=--debug-actor-update-runtime-oracle",
            "candidate_0_oracle_command=./build/lezac_cpp "
            "--debug-actor-update-runtime-oracle "
            f"{shlex.quote(str(ready_candidate))}",
        ]:
            require(promotion_text, snippet, "ready_promotion_manifest")
        cases += 1

        original_root = base / "original_root"
        original_fixture = write_original_fixture_tree(
            original_root,
            "actor_update_runtime_oracle_original_writer_unledgered.txt",
            runtime_ds="0F3C",
            include_ledger_entry=False,
        )
        original_fixture.write_text(
            ready_candidate.read_text(encoding="ascii"), encoding="ascii"
        )
        bad_original_manifest = base / "bad_original" / "manifest.txt"
        write_text(
            bad_original_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=actor_update_gate6",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x3p00",
                    "environment_preflight=ok",
                    f"capture_status_x3p00=actor_contact_procmem=ok mode=capture target=actor_update_gate6 ghidra=1000:654E runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:654E freeze_observed=1 raw_dump=/tmp/original/raw.txt candidate_fixture={original_fixture}",
                    "",
                ]
            ),
        )
        bad_original = run_summary(
            root,
            bad_original_manifest,
            expect_success=False,
            extra_args=[
                "--write-ready-manifest",
                str(base / "bad_original" / "promotion_manifest.txt"),
            ],
            env={"LEZAC_READY_RESULT_REPO_ROOT": str(original_root)},
        ).stdout
        require(
            bad_original,
            "candidate_0_fixture actor_update_runtime_oracle_original_writer_unledgered.txt "
            "is missing from runtime evidence ledger",
            "bad_original_writer_fixture",
        )
        cases += 1

        skeleton_candidate = base / "skeleton" / "actor_update_candidate.txt"
        write_text(
            skeleton_candidate,
            "\n".join(
                [
                    "# LEZAC actor/contact process-memory oracle candidate.",
                    "# Candidate only: fill semantic actor/contact records before promotion.",
                    "capture=actor_update_runtime",
                    "source=dosbox-debug-process-memory",
                    "temp_copy=1",
                    "visual_claim=0",
                    "target=actor_update_gate6",
                    "scenario=object_collision_jump_live",
                    "runtime_cs=01ED",
                    "runtime_ds=0F3C",
                    "break ghidra=1000:5CB0 runtime=01ED:5CB0 label=contact_scanner_start",
                    "break ghidra=1000:604F runtime=01ED:604F label=contact_scanner_end",
                    "# actor_before slot=<slot> behavior=<behavior> kind=<kind> state=<state>",
                    "# actor_after slot=<slot> behavior=<behavior> kind=<kind> state=<state>",
                    "# contact_scan subject_slot=<slot> other_slot=<slot>",
                    "# tile_probe tile_x=<x> tile_y=<y>",
                    "",
                ]
            ),
        )
        skeleton_manifest = base / "skeleton" / "manifest.txt"
        write_text(
            skeleton_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
            "target=actor_update_gate6",
            "timings=before_route",
            "routes=1",
            "route_labels=x3p00",
            "environment_preflight=ok",
            f"capture_status_x3p00=actor_contact_procmem=ok mode=capture target=actor_update_gate6 ghidra=1000:654E runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:654E freeze_observed=1 raw_dump=/tmp/skeleton/raw.txt candidate_fixture={skeleton_candidate}",
                    "",
                ]
            ),
        )
        skeleton = run_summary(root, skeleton_manifest).stdout
        for snippet in [
            "ready_candidates=0",
            "incomplete_candidates=1",
            "missing_candidates=0",
            "none_candidates=0",
            "candidate_status=incomplete",
            "candidate_missing=level,actor_before,actor_after,contact_scan,tile_probe,break_6053,break_777f",
            "candidate_placeholders=1",
        ]:
            require(skeleton, snippet, "skeleton_actor_candidate")
        cases += 1

        skeleton_required = run_summary(
            root,
            skeleton_manifest,
            expect_success=False,
            extra_args=["--require-ready"],
        ).stdout
        for snippet in [
            "actor_dispatch_gate_sweep_summary=error reason=candidates_not_ready",
            "ready_candidates=0 incomplete_candidates=1 missing_candidates=0 none_candidates=0",
        ]:
            require(skeleton_required, snippet, "skeleton_required")
        cases += 1

        direct_manifest = base / "direct" / "manifest.txt"
        write_text(
            direct_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=contact_scanner_callsite",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x1p50",
                    "environment_preflight=ok",
                    "capture_status_x1p50=actor_contact_procmem=ok mode=capture target=contact_scanner_callsite ghidra=1000:6555 runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:6555 freeze_observed=runtime_child_memory_freeze_observed raw_dump=/tmp/contact/raw.txt candidate_fixture=/tmp/contact/candidate_fixture.txt",
                    "",
                ]
            ),
        )
        direct = run_summary(root, direct_manifest.parent).stdout
        for snippet in [
            "capture=actor_contact_route_sweep",
            "mode=route",
            "environment_preflight=ok",
            "child_environment_preflights=none",
            "targets=1",
            "route_sweeps=1",
            "captures=1",
            "freezes=1",
            "observed_targets=contact_scanner_callsite",
            "observed_dispatch_gates=contact_scanner_callsite",
            "missing_targets=none",
            "candidate_fixtures=/tmp/contact/candidate_fixture.txt",
            "candidate_status=missing candidate_missing=file candidate_placeholders=0",
            "oracle=actor_update oracle_flag=--debug-actor-update-runtime-oracle",
            "oracle_command=./build/lezac_cpp --debug-actor-update-runtime-oracle /tmp/contact/candidate_fixture.txt",
        ]:
            require(direct, snippet, "direct_route_manifest")
        cases += 1

        all_target_route_manifest = base / "all_target_route" / "manifest.txt"
        write_text(
            all_target_route_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=all",
                    "targets=2",
                    "target_names=actor_update_gate5,contact_scanner_start",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x2p00",
                    "environment_preflight=ok",
                    "capture_status_actor_update_gate5_before_route_x2p00=actor_contact_procmem=ok mode=capture target=actor_update_gate5 ghidra=1000:65A2 runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:65A2 freeze_observed=0 raw_dump=/tmp/all/gate5/raw.txt candidate_fixture=/tmp/all/gate5/candidate_fixture.txt",
                    "capture_status_contact_scanner_start_before_route_x2p00=actor_contact_procmem=ok mode=capture target=contact_scanner_start ghidra=1000:5CB0 runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:5CB0 freeze_observed=1 raw_dump=/tmp/all/scanner/raw.txt candidate_fixture=/tmp/all/scanner/candidate_fixture.txt",
                    "",
                ]
            ),
        )
        all_target_route = run_summary(root, all_target_route_manifest).stdout
        for snippet in [
            "capture=actor_contact_route_sweep",
            "mode=route",
            "targets=2",
            "captures=2",
            "freezes=1",
            "dispatch_gate_freezes=0",
            "observed_targets=contact_scanner_start",
            "missing_targets=actor_update_gate5",
            "freeze target=contact_scanner_start dispatch_gate_candidate=none route=before_route_x2p00 ghidra=1000:5CB0",
            "candidate_status=missing candidate_missing=file candidate_placeholders=0",
            "oracle=contact_scanner oracle_flag=--debug-contact-scanner-runtime-oracle",
        ]:
            require(all_target_route, snippet, "all_target_route_manifest")
        cases += 1

        scanner_manifest = base / "scanner" / "manifest.txt"
        write_text(
            scanner_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=contact_scanner_start",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x0p50",
                    "environment_preflight=ok",
                    "capture_status_x0p50=actor_contact_procmem=ok mode=capture target=contact_scanner_start ghidra=1000:5CB0 runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:5CB0 freeze_observed=1 raw_dump=/tmp/scanner/raw.txt candidate_fixture=/tmp/scanner/candidate_fixture.txt",
                    "",
                ]
            ),
        )
        scanner = run_summary(root, scanner_manifest).stdout
        for snippet in [
            "observed_targets=contact_scanner_start",
            "observed_dispatch_gates=none",
            "candidate_fixtures=/tmp/scanner/candidate_fixture.txt",
            "candidate_status=missing candidate_missing=file candidate_placeholders=0",
            "oracle=contact_scanner oracle_flag=--debug-contact-scanner-runtime-oracle",
            "oracle_command=./build/lezac_cpp --debug-contact-scanner-runtime-oracle /tmp/scanner/candidate_fixture.txt",
        ]:
            require(scanner, snippet, "scanner_route_manifest")
        cases += 1

        scanner_gate_required = run_summary(
            root,
            scanner_manifest,
            expect_success=False,
            extra_args=["--require-dispatch-gate-freeze"],
        ).stdout
        for snippet in [
            "reason=no_dispatch_gate_freezes",
            "freezes=1",
            "dispatch_gate_freezes=0",
            "observed_targets=contact_scanner_start",
        ]:
            require(scanner_gate_required, snippet, "scanner_gate_required")
        cases += 1

        incomplete_scanner_fields = (
            base / "incomplete_scanner_fields" / "contact_scanner_candidate.txt"
        )
        write_text(
            incomplete_scanner_fields,
            "\n".join(
                [
                    "capture=contact_scanner_runtime",
                    "source=synthetic",
                    "temp_copy=1",
                    "visual_claim=0",
                    "scenario=monster_contact_damage_live",
                    "level=1",
                    "runtime_cs=01ED",
                    "runtime_ds=0F3C",
                    "break ghidra=1000:5CB0 runtime=01ED:5CB0 label=contact_scanner_start",
                    "break ghidra=1000:604F runtime=01ED:604F label=contact_scanner_end",
                    "subject_actor slot=0 kind=0 state=0 x=0x0068 y=0x00a8 flags=0x0000",
                    "other_actor slot=3 kind=2 state=0 x=0x006a y=0x00a8 flags=0x0000",
                    "contact_scan subject_slot=0 other_slot=3 flags_before=0x0000 flags_after=0x0002 contact=1 player_contact=1 monster_contact=0 object_contact=0 damage_pending=1",
                    "",
                ]
            ),
        )
        incomplete_scanner_manifest = (
            base / "incomplete_scanner_fields" / "manifest.txt"
        )
        write_text(
            incomplete_scanner_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=contact_scanner_end",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x0p25",
                    "environment_preflight=ok",
                    f"capture_status_x0p25=actor_contact_procmem=ok mode=capture target=contact_scanner_end ghidra=1000:604F runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:604F freeze_observed=1 raw_dump=/tmp/incomplete_scanner/raw.txt candidate_fixture={incomplete_scanner_fields}",
                    "",
                ]
            ),
        )
        incomplete_scanner = run_summary(root, incomplete_scanner_manifest).stdout
        for snippet in [
            "ready_candidates=0",
            "incomplete_candidates=1",
            "candidate_status=incomplete",
            "candidate_missing=subject_actor.w,subject_actor.h,other_actor.w,other_actor.h,contact_scan.overlap_x,contact_scan.overlap_y",
        ]:
            require(incomplete_scanner, snippet, "incomplete_scanner_fields")
        cases += 1

        ready_scanner_candidate = base / "ready_scanner" / "contact_scanner_candidate.txt"
        write_text(
            ready_scanner_candidate,
            "\n".join(
                [
                    "capture=contact_scanner_runtime",
                    "source=synthetic",
                    "temp_copy=1",
                    "visual_claim=0",
                    "scenario=monster_contact_damage_live",
                    "level=1",
                    "runtime_cs=01ED",
                    "runtime_ds=0F3C",
                    "break ghidra=1000:5CB0 runtime=01ED:5CB0 label=contact_scanner_start",
                    "break ghidra=1000:604F runtime=01ED:604F label=contact_scanner_end",
                    "subject_actor slot=0 behavior=0 kind=0 state=0 x=0x0068 y=0x00a8 w=16 h=24 flags=0x0000 contact=0",
                    "other_actor slot=3 behavior=4 kind=2 state=0 x=0x006a y=0x00a8 w=16 h=16 flags=0x0000 contact=0",
                    "contact_scan subject_slot=0 other_slot=3 flags_before=0x0000 flags_after=0x0002 contact=1 player_contact=1 monster_contact=0 object_contact=0 damage_pending=1 overlap_x=14 overlap_y=24",
                    "",
                ]
            ),
        )
        ready_scanner_manifest = base / "ready_scanner" / "manifest.txt"
        write_text(
            ready_scanner_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=contact_scanner_end",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x0p50",
                    "environment_preflight=ok",
                    f"capture_status_x0p50=actor_contact_procmem=ok mode=capture target=contact_scanner_end ghidra=1000:604F runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:604F freeze_observed=1 raw_dump=/tmp/ready_scanner/raw.txt candidate_fixture={ready_scanner_candidate}",
                    "",
                ]
            ),
        )
        ready_scanner = run_summary(root, ready_scanner_manifest).stdout
        for snippet in [
            "ready_candidates=1",
            "incomplete_candidates=0",
            "missing_candidates=0",
            "none_candidates=0",
            "observed_targets=contact_scanner_end",
            "candidate_status=ready",
            "candidate_missing=none",
            "oracle=contact_scanner oracle_flag=--debug-contact-scanner-runtime-oracle",
            "oracle_command=./build/lezac_cpp --debug-contact-scanner-runtime-oracle",
        ]:
            require(ready_scanner, snippet, "ready_scanner_candidate")
        cases += 1

        ready_scanner_promotion_manifest = (
            base / "ready_scanner" / "promotion_manifest.txt"
        )
        ready_scanner_promotion = run_summary(
            root,
            ready_scanner_manifest,
            extra_args=[
                "--write-ready-manifest",
                str(ready_scanner_promotion_manifest),
            ],
        ).stdout
        require(
            ready_scanner_promotion,
            "actor_dispatch_gate_ready_manifest=ok",
            "ready_scanner_promotion_output",
        )
        ready_scanner_promotion_text = ready_scanner_promotion_manifest.read_text(
            encoding="ascii"
        )
        for snippet in [
            "candidate_0_target=contact_scanner_end",
            "candidate_0_ghidra=1000:604F",
            f"candidate_0_fixture={ready_scanner_candidate}",
            "candidate_0_oracle=contact_scanner",
            "candidate_0_oracle_flag=--debug-contact-scanner-runtime-oracle",
            "candidate_0_oracle_command=./build/lezac_cpp "
            "--debug-contact-scanner-runtime-oracle "
            f"{shlex.quote(str(ready_scanner_candidate))}",
        ]:
            require(
                ready_scanner_promotion_text,
                snippet,
                "ready_scanner_promotion_manifest",
            )
        cases += 1

        dry_manifest = base / "dry" / "manifest.txt"
        write_text(
            dry_manifest,
            "\n".join(
                [
                    "capture=actor_dispatch_gate_sweep",
                    "asset_dir=/repo",
                    "targets=actor_update_gate5,actor_update_gate6",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x2p00",
                    "environment_preflight=ok",
                    "",
                ]
            ),
        )
        dry = run_summary(root, dry_manifest).stdout
        for snippet in [
            "mode=dispatch",
            "environment_preflight=ok",
            "targets=2",
            "route_sweeps=0",
            "captures=0",
            "freezes=0",
            "dispatch_gate_freezes=0",
            "ready_candidates=0",
            "incomplete_candidates=0",
            "missing_candidates=0",
            "none_candidates=0",
            "observed_targets=none",
            "observed_dispatch_gates=none",
            "missing_targets=actor_update_gate5,actor_update_gate6",
            "candidate_fixtures=none",
        ]:
            require(dry, snippet, "dry_manifest")
        cases += 1

        dry_required = run_summary(
            root,
            dry_manifest,
            extra_args=["--require-ready"],
        ).stdout
        require(dry_required, "freezes=0", "dry_required")
        cases += 1

        all_targets = (
            "actor_update_start,actor_update_end,actor_update_gate5,"
            "actor_update_gate5_integration,actor_update_gate5_exit,"
            "actor_update_gate6,contact_scanner_callsite,"
            "contact_scanner_start,contact_scanner_end"
        )
        all_targets_manifest = base / "all_targets" / "manifest.txt"
        write_text(
            all_targets_manifest,
            "\n".join(
                [
                    "capture=actor_dispatch_gate_sweep",
                    "asset_dir=/repo",
                    f"targets={all_targets}",
                    "timings=before_route",
                    "routes=4",
                    "route_labels=x2p00,x5p00_m0p50_x2p00,x3p00_z0p50_x2p00,x1p50_left0p50_x2p00",
                    "environment_preflight=ok",
                    "",
                ]
            ),
        )
        all_targets_summary = run_summary(root, all_targets_manifest).stdout
        for snippet in [
            "mode=dispatch",
            "environment_preflight=ok",
            "targets=9",
            "route_sweeps=0",
            "captures=0",
            "freezes=0",
            "dispatch_gate_freezes=0",
            "observed_targets=none",
            "observed_dispatch_gates=none",
            f"missing_targets={all_targets}",
        ]:
            require(all_targets_summary, snippet, "all_targets_dry_manifest")
        cases += 1

        missing_preflight_manifest = base / "missing_preflight" / "manifest.txt"
        write_text(
            missing_preflight_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=contact_scanner_start",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x0p50",
                    "",
                ]
            ),
        )
        missing_preflight = run_summary(
            root,
            missing_preflight_manifest,
            expect_success=False,
            extra_args=["--require-environment-preflight"],
        ).stdout
        for snippet in [
            "actor_dispatch_gate_sweep_summary=error reason=environment_preflight_not_ok",
            "environment_preflight=unknown",
            "child_environment_preflights=none",
        ]:
            require(missing_preflight, snippet, "missing_environment_preflight")
        cases += 1

        duplicate_field_manifest = base / "duplicate_field" / "manifest.txt"
        write_text(
            duplicate_field_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=contact_scanner_start",
                    "target=actor_update_gate6",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x0p50",
                    "environment_preflight=ok",
                    "",
                ]
            ),
        )
        duplicate_field = run_summary(
            root,
            duplicate_field_manifest,
            expect_success=False,
        ).stdout
        require(
            duplicate_field,
            "duplicate manifest field: target",
            "duplicate_field",
        )
        cases += 1

        missing = run_summary(root, base / "missing" / "manifest.txt", False).stdout
        require(missing, "actor_dispatch_gate_sweep_summary=error", "missing_manifest")
        require(missing, "manifest not found", "missing_manifest")
        cases += 1

    print(f"actor_dispatch_gate_sweep_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
