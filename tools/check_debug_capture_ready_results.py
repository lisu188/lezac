#!/usr/bin/env python3
"""Check debug-capture ready-result summarizer behavior."""

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


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_summary(
    root: Path,
    args: list[str],
    expect_success: bool = True,
    env: dict[str, str] | None = None,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_debug_capture_ready_results.py"),
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
            f"summarizer failed with {result.returncode}: {args}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(f"summarizer unexpectedly passed: {args}\n{result.stdout}")
    return result.stdout


def manifest_text(log: Path, *, mode: str = "run", status: str = "ok") -> str:
    failures = "0" if status != "error" else "1"
    log1 = log.parent / "candidate_1.log"
    log2 = log.parent / "candidate_2.log"
    return "\n".join(
        (
            "result=debug_capture_ready_manifest",
            f"mode={mode}",
            "source_ready_manifest=/tmp/ready_manifest.txt",
            "source_root=/tmp/source",
            "oracle_binary=/tmp/lezac_cpp",
            "ready_candidates=3",
            f"failures={failures}",
            "candidate_0_capture=behavior4_runtime",
            "candidate_0_scenario=monster_behavior4_target_selection",
            "candidate_0_level=3",
            "candidate_0_environment_preflight=ok",
            "candidate_0_runtime_metadata=ok",
            "candidate_0_runtime_cs=01ED",
            "candidate_0_runtime_ds=0C8F",
            "candidate_0_manifest=/tmp/capture/manifest.txt",
            "candidate_0_fixture=/tmp/capture/behavior4.txt",
            "candidate_0_oracle=behavior4",
            "candidate_0_oracle_flag=--debug-behavior4-runtime-oracle",
            (
                "candidate_0_status=planned"
                if mode == "dry_run"
                else f"candidate_0_status={status}"
            ),
            (
                "candidate_0_returncode=not_run"
                if mode == "dry_run"
                else f"candidate_0_returncode={'7' if status == 'error' else '0'}"
            ),
            f"candidate_0_log={log}",
            "candidate_0_command=/tmp/lezac_cpp --debug-behavior4-runtime-oracle /tmp/capture/behavior4.txt",
            "candidate_1_capture=actor_update_runtime",
            "candidate_1_scenario=object_collision_jump_live",
            "candidate_1_level=1",
            "candidate_1_environment_preflight=ok",
            "candidate_1_runtime_metadata=ok",
            "candidate_1_runtime_cs=01ED",
            "candidate_1_runtime_ds=0C8F",
            "candidate_1_manifest=/tmp/capture/manifest.txt",
            "candidate_1_fixture=/tmp/capture/actor_update.txt",
            "candidate_1_oracle=actor_update",
            "candidate_1_oracle_flag=--debug-actor-update-runtime-oracle",
            (
                "candidate_1_status=planned"
                if mode == "dry_run"
                else "candidate_1_status=ok"
            ),
            (
                "candidate_1_returncode=not_run"
                if mode == "dry_run"
                else "candidate_1_returncode=0"
            ),
            (
                "candidate_1_log=none"
                if mode == "dry_run"
                else f"candidate_1_log={log1}"
            ),
            "candidate_1_command=/tmp/lezac_cpp --debug-actor-update-runtime-oracle /tmp/capture/actor_update.txt",
            "candidate_2_capture=visual_table",
            "candidate_2_scenario=state2_death_table_consumption",
            "candidate_2_level=1",
            "candidate_2_environment_preflight=ok",
            "candidate_2_runtime_metadata=ok",
            "candidate_2_runtime_cs=1A2B",
            "candidate_2_runtime_ds=2B3C",
            "candidate_2_manifest=/tmp/capture/visual_table_manifest.txt",
            "candidate_2_fixture=/tmp/capture/visual_table.txt",
            "candidate_2_oracle=visual_table",
            "candidate_2_oracle_flag=--debug-visual-table-oracle",
            (
                "candidate_2_status=planned"
                if mode == "dry_run"
                else "candidate_2_status=ok"
            ),
            (
                "candidate_2_returncode=not_run"
                if mode == "dry_run"
                else "candidate_2_returncode=0"
            ),
            (
                "candidate_2_log=none"
                if mode == "dry_run"
                else f"candidate_2_log={log2}"
            ),
            "candidate_2_command=/tmp/lezac_cpp --debug-visual-table-oracle /tmp/capture/visual_table.txt",
            "",
        )
    )


def contact_manifest_text(log: Path) -> str:
    return "\n".join(
        (
            "result=debug_capture_ready_manifest",
            "mode=run",
            "source_ready_manifest=/tmp/contact_ready_manifest.txt",
            "source_root=/tmp/contact_source",
            "oracle_binary=/tmp/lezac_cpp",
            "ready_candidates=1",
            "failures=0",
            "candidate_0_capture=contact_scanner_runtime",
            "candidate_0_scenario=monster_contact_damage_live",
            "candidate_0_level=1",
            "candidate_0_environment_preflight=ok",
            "candidate_0_runtime_metadata=ok",
            "candidate_0_runtime_cs=01ED",
            "candidate_0_runtime_ds=0C8F",
            "candidate_0_manifest=/tmp/capture/contact_manifest.txt",
            "candidate_0_fixture=/tmp/capture/contact_scanner.txt",
            "candidate_0_oracle=contact_scanner",
            "candidate_0_oracle_flag=--debug-contact-scanner-runtime-oracle",
            "candidate_0_status=ok",
            "candidate_0_returncode=0",
            f"candidate_0_log={log}",
            "candidate_0_command=/tmp/lezac_cpp --debug-contact-scanner-runtime-oracle /tmp/capture/contact_scanner.txt",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check summarize_debug_capture_ready_results.py behavior."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-debug-ready-results-") as tmp:
        base = Path(tmp)
        log = base / "logs" / "candidate_0.log"
        write_text(log, "oracle ok\n")
        write_text(log.parent / "candidate_1.log", "actor oracle ok\n")
        write_text(log.parent / "candidate_2.log", "visual oracle ok\n")

        run_manifest = base / "run" / "result_manifest.txt"
        write_text(run_manifest, manifest_text(log))
        run = run_summary(root, [str(run_manifest), "--require-success"])
        for snippet in [
            "debug_capture_ready_result_summary=ok",
            "mode=run",
            "ready_candidates=3",
            "failures=0",
            "planned=0",
            "ok=3",
            "error=0",
            "executed_candidates=3",
            "environment_preflight_ok=3",
            "logs_present=3",
            "logs_missing=0",
            "candidate_result index=0 capture=behavior4_runtime",
            "runtime_cs=01ED",
            "runtime_ds=0C8F",
            "fixture=/tmp/capture/behavior4.txt",
            "candidate_result index=2 capture=visual_table",
            "oracle=visual_table",
            "oracle_flag=--debug-visual-table-oracle",
            "--debug-visual-table-oracle",
        ]:
            require(run, snippet, "run_summary")
        cases += 1

        contact_log = base / "logs" / "contact_scanner.log"
        write_text(contact_log, "contact scanner oracle ok\n")
        contact_manifest = base / "contact" / "result_manifest.txt"
        write_text(contact_manifest, contact_manifest_text(contact_log))
        contact = run_summary(root, [str(contact_manifest), "--require-success"])
        for snippet in [
            "debug_capture_ready_result_summary=ok",
            "ready_candidates=1",
            "ok=1",
            "executed_candidates=1",
            "environment_preflight_ok=1",
            "logs_present=1",
            "candidate_result index=0 capture=contact_scanner_runtime",
            "scenario=monster_contact_damage_live",
            "runtime_cs=01ED",
            "runtime_ds=0C8F",
            "fixture=/tmp/capture/contact_scanner.txt",
            "oracle=contact_scanner",
            "oracle_flag=--debug-contact-scanner-runtime-oracle",
            "--debug-contact-scanner-runtime-oracle",
        ]:
            require(contact, snippet, "contact_summary")
        cases += 1

        missing_log_manifest = base / "missing_log" / "result_manifest.txt"
        write_text(
            missing_log_manifest,
            manifest_text(log).replace(
                f"candidate_2_log={log.parent / 'candidate_2.log'}",
                "candidate_2_log=/tmp/missing-visual-table.log",
            ),
        )
        missing_log = run_summary(
            root, [str(missing_log_manifest), "--require-success"], False
        )
        require(missing_log, "reason=candidate_logs_missing", "missing_log")
        require(missing_log, "logs_missing=1", "missing_log")
        cases += 1

        dry_manifest = base / "dry" / "result_manifest.txt"
        write_text(dry_manifest, manifest_text(log, mode="dry_run"))
        dry = run_summary(root, [str(dry_manifest)])
        require(dry, "mode=dry_run", "dry_summary")
        require(dry, "planned=3", "dry_summary")
        require(dry, "executed_candidates=0", "dry_summary")
        dry_required = run_summary(
            root, [str(dry_manifest), "--require-executed"], False
        )
        require(dry_required, "reason=candidates_not_executed", "dry_required")
        cases += 1

        failure_manifest = base / "failure" / "result_manifest.txt"
        write_text(failure_manifest, manifest_text(log, status="error"))
        failure = run_summary(root, [str(failure_manifest)], True)
        require(failure, "failures=1", "failure_summary")
        require(failure, "error=1", "failure_summary")
        failure_required = run_summary(
            root, [str(failure_manifest), "--require-success"], False
        )
        require(failure_required, "reason=oracle_failures", "failure_required")
        cases += 1

        mismatch_manifest = base / "mismatch" / "result_manifest.txt"
        write_text(
            mismatch_manifest,
            manifest_text(log, status="error").replace("failures=1", "failures=0"),
        )
        mismatch = run_summary(root, [str(mismatch_manifest)], False)
        require(mismatch, "reason=failure_count_mismatch", "mismatch_summary")
        require(mismatch, "failures=0 error=1", "mismatch_summary")
        cases += 1

        returncode_manifest = base / "returncode" / "result_manifest.txt"
        write_text(
            returncode_manifest,
            manifest_text(log).replace(
                "candidate_1_returncode=0", "candidate_1_returncode=7"
            ),
        )
        returncode = run_summary(root, [str(returncode_manifest)], False)
        require(
            returncode,
            "reason=status_returncode_mismatch",
            "returncode_summary",
        )
        require(
            returncode,
            "index=1 status=ok returncode=7 expected=0",
            "returncode_summary",
        )
        cases += 1

        oracle_flag_manifest = base / "oracle_flag" / "result_manifest.txt"
        write_text(
            oracle_flag_manifest,
            manifest_text(log).replace(
                "candidate_1_oracle_flag=--debug-actor-update-runtime-oracle",
                "candidate_1_oracle_flag=--debug-contact-scanner-runtime-oracle",
            ),
        )
        oracle_flag = run_summary(root, [str(oracle_flag_manifest)], False)
        require(
            oracle_flag,
            "candidate_1_oracle_flag='--debug-contact-scanner-runtime-oracle' "
            "does not match candidate_1_oracle='actor_update'",
            "oracle_flag_summary",
        )
        cases += 1

        command_manifest = base / "command" / "result_manifest.txt"
        write_text(
            command_manifest,
            manifest_text(log).replace(
                "candidate_2_command=/tmp/lezac_cpp --debug-visual-table-oracle /tmp/capture/visual_table.txt",
                "candidate_2_command=/tmp/lezac_cpp --debug-visual-table-oracle /tmp/capture/wrong_visual_table.txt",
            ),
        )
        command = run_summary(root, [str(command_manifest)], False)
        require(
            command,
            "candidate_2_command does not end with oracle flag and fixture",
            "command_summary",
        )
        require(
            command,
            "expected ['--debug-visual-table-oracle', '/tmp/capture/visual_table.txt']",
            "command_summary",
        )
        cases += 1

        runtime_manifest = base / "runtime" / "result_manifest.txt"
        write_text(
            runtime_manifest,
            manifest_text(log).replace(
                "candidate_0_runtime_cs=01ED", "candidate_0_runtime_cs=ZZZZ"
            ),
        )
        runtime = run_summary(root, [str(runtime_manifest)], False)
        require(
            runtime,
            "candidate_0_runtime_cs must be a 4-digit hexadecimal segment",
            "runtime_summary",
        )
        cases += 1

        fixture_mismatch_path = base / "fixtures" / "actor_update.txt"
        write_text(fixture_mismatch_path, "runtime_cs=01ED\nruntime_ds=BEEF\n")
        fixture_mismatch_manifest = base / "fixture_mismatch" / "result_manifest.txt"
        write_text(
            fixture_mismatch_manifest,
            manifest_text(log).replace(
                "/tmp/capture/actor_update.txt",
                fixture_mismatch_path.as_posix(),
            ),
        )
        fixture_mismatch = run_summary(root, [str(fixture_mismatch_manifest)], False)
        require(
            fixture_mismatch,
            "candidate_1_runtime_ds='0C8F' does not match fixture "
            "runtime_ds='BEEF'",
            "fixture_mismatch",
        )
        cases += 1

        visual_claim_path = base / "fixtures" / "behavior4_visual_claim.txt"
        write_text(
            visual_claim_path,
            "temp_copy=1\nvisual_claim=1\nruntime_cs=01ED\nruntime_ds=0C8F\n",
        )
        visual_claim_manifest = base / "visual_claim" / "result_manifest.txt"
        write_text(
            visual_claim_manifest,
            manifest_text(log).replace(
                "/tmp/capture/behavior4.txt",
                visual_claim_path.as_posix(),
            ),
        )
        visual_claim = run_summary(root, [str(visual_claim_manifest)], False)
        require(
            visual_claim,
            "candidate_0_fixture visual_claim='1' is not supported",
            "visual_claim",
        )
        cases += 1

        temp_copy_path = base / "fixtures" / "behavior4_temp_copy.txt"
        write_text(
            temp_copy_path,
            "temp_copy=0\nvisual_claim=0\nruntime_cs=01ED\nruntime_ds=0C8F\n",
        )
        temp_copy_manifest = base / "temp_copy" / "result_manifest.txt"
        write_text(
            temp_copy_manifest,
            manifest_text(log).replace(
                "/tmp/capture/behavior4.txt",
                temp_copy_path.as_posix(),
            ),
        )
        temp_copy = run_summary(root, [str(temp_copy_manifest)], False)
        require(
            temp_copy,
            "candidate_0_fixture temp_copy='0' does not identify a temp-copy capture",
            "temp_copy",
        )
        cases += 1

        original_root = base / "original_root"
        original_fixture = write_original_fixture_tree(
            original_root,
            "behavior4_runtime_oracle_original_ready.txt",
            runtime_ds="0C8F",
        )
        original_manifest = base / "original_fixture" / "result_manifest.txt"
        write_text(
            original_manifest,
            manifest_text(log).replace(
                "/tmp/capture/behavior4.txt", original_fixture.as_posix()
            ),
        )
        original = run_summary(
            root,
            [str(original_manifest)],
            env={"LEZAC_READY_RESULT_REPO_ROOT": str(original_root)},
        )
        require(
            original,
            f"fixture={original_fixture.as_posix()}",
            "original_fixture",
        )
        cases += 1

        missing_ledger_root = base / "missing_ledger_root"
        missing_ledger_fixture = write_original_fixture_tree(
            missing_ledger_root,
            "behavior4_runtime_oracle_original_unledgered.txt",
            runtime_ds="0C8F",
            include_ledger_entry=False,
        )
        missing_ledger_manifest = base / "missing_ledger" / "result_manifest.txt"
        write_text(
            missing_ledger_manifest,
            manifest_text(log).replace(
                "/tmp/capture/behavior4.txt", missing_ledger_fixture.as_posix()
            ),
        )
        missing_ledger = run_summary(
            root,
            [str(missing_ledger_manifest)],
            False,
            {"LEZAC_READY_RESULT_REPO_ROOT": str(missing_ledger_root)},
        )
        require(
            missing_ledger,
            "candidate_0_fixture behavior4_runtime_oracle_original_unledgered.txt "
            "is missing from runtime evidence ledger",
            "missing_ledger",
        )
        cases += 1

        missing_note_root = base / "missing_note_root"
        missing_note_fixture = write_original_fixture_tree(
            missing_note_root,
            "behavior4_runtime_oracle_original_missing_note.txt",
            runtime_ds="0C8F",
            note_names_fixture=False,
        )
        missing_note_manifest = base / "missing_note" / "result_manifest.txt"
        write_text(
            missing_note_manifest,
            manifest_text(log).replace(
                "/tmp/capture/behavior4.txt", missing_note_fixture.as_posix()
            ),
        )
        missing_note = run_summary(
            root,
            [str(missing_note_manifest)],
            False,
            {"LEZAC_READY_RESULT_REPO_ROOT": str(missing_note_root)},
        )
        require(
            missing_note,
            "candidate_0_fixture behavior4_runtime_oracle_original_missing_note.txt "
            "ledger docs does not name fixture",
            "missing_note",
        )
        cases += 1

        extra_manifest = base / "extra" / "result_manifest.txt"
        write_text(
            extra_manifest,
            manifest_text(log).replace("ready_candidates=3", "ready_candidates=2"),
        )
        extra = run_summary(root, [str(extra_manifest)], False)
        require(
            extra,
            "candidate index outside ready_candidates: 2 ready_candidates=2",
            "extra_candidate",
        )
        cases += 1

        duplicate_field_manifest = base / "duplicate_field" / "result_manifest.txt"
        write_text(
            duplicate_field_manifest,
            manifest_text(log) + "candidate_0_fixture=/tmp/other_debug_capture.txt\n",
        )
        duplicate_field = run_summary(root, [str(duplicate_field_manifest)], False)
        require(
            duplicate_field,
            "duplicate manifest field: candidate_0_fixture",
            "duplicate_field",
        )
        cases += 1

        mode_manifest = base / "mode" / "result_manifest.txt"
        write_text(
            mode_manifest,
            manifest_text(log)
            .replace("candidate_1_status=ok", "candidate_1_status=planned")
            .replace("candidate_1_returncode=0", "candidate_1_returncode=not_run"),
        )
        mode_error = run_summary(root, [str(mode_manifest)], False)
        require(mode_error, "reason=mode_status_mismatch", "mode_summary")
        require(mode_error, "mode=run planned=1 expected_planned=0", "mode_summary")
        cases += 1

        other_manifest = base / "other" / "result_manifest.txt"
        write_text(
            other_manifest,
            "\n".join(
                [
                    "result=debug_capture_ready_manifest",
                    "mode=run",
                    "source_ready_manifest=/tmp/ready_manifest.txt",
                    "source_root=/tmp/source",
                    "oracle_binary=/tmp/lezac_cpp",
                    "ready_candidates=1",
                    "failures=0",
                    "candidate_0_capture=behavior4_runtime",
                    "candidate_0_scenario=monster_behavior4_target_selection",
                    "candidate_0_level=3",
                    "candidate_0_environment_preflight=ok",
                    "candidate_0_runtime_metadata=ok",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0C8F",
                    "candidate_0_oracle=behavior4",
                    "candidate_0_oracle_flag=--debug-behavior4-runtime-oracle",
                    "candidate_0_fixture=/tmp/capture/behavior4.txt",
                    "candidate_0_status=skipped",
                    "candidate_0_returncode=not_run",
                    "candidate_0_log=none",
                    "candidate_0_command=/tmp/lezac_cpp --debug-behavior4-runtime-oracle /tmp/capture/behavior4.txt",
                    "",
                ]
            ),
        )
        other = run_summary(root, [str(other_manifest)])
        require(other, "planned=0", "other_summary")
        require(other, "other=1", "other_summary")
        other_required = run_summary(
            root, [str(other_manifest), "--require-success"], False
        )
        require(other_required, "reason=oracle_failures", "other_required")
        require(other_required, "failures=0 error=0 other=1", "other_required")
        cases += 1

        env_manifest = base / "env" / "result_manifest.txt"
        write_text(
            env_manifest,
            manifest_text(log).replace(
                "candidate_1_environment_preflight=ok",
                "candidate_1_environment_preflight=missing_dosbox",
            ),
        )
        env = run_summary(root, [str(env_manifest)])
        require(env, "environment_preflight_not_ok=1", "env_summary")
        env_required = run_summary(
            root,
            [str(env_manifest), "--require-source-environment-preflight"],
            False,
        )
        require(
            env_required,
            "reason=source_environment_preflight_not_ok",
            "env_required",
        )
        cases += 1

        bad_result = base / "bad" / "result_manifest.txt"
        write_text(
            bad_result,
            manifest_text(log).replace(
                "result=debug_capture_ready_manifest",
                "result=lane_result_ready_manifest",
            ),
        )
        bad = run_summary(root, [str(bad_result)], False)
        require(bad, "unsupported result", "bad_result")
        cases += 1

        missing = run_summary(
            root, [str(base / "missing" / "result_manifest.txt")], False
        )
        require(missing, "manifest not found", "missing_manifest")
        cases += 1

    print(f"debug_capture_ready_results_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
