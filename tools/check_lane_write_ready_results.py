#!/usr/bin/env python3
"""Check lane-write ready result summarizer behavior."""

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
        str(root / "tools" / "summarize_lane_write_ready_results.py"),
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
            f"ready result summary failed with {result.returncode}: "
            f"{' '.join(args)}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"ready result summary unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    return result.stdout


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-write ready result summary output."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-lane-write-ready-results-") as tmp:
        base = Path(tmp)
        log0 = base / "logs" / "candidate_0_3d2d_x2p00.log"
        log1 = base / "logs" / "candidate_1_3ec1_x1p50_z0p50.log"
        write_text(log0, "explosion_playback_oracle=ok\n")
        write_text(log1, "explosion_playback_oracle=ok\n")
        run_manifest = base / "run" / "result_manifest.txt"
        write_text(
            run_manifest,
            "\n".join(
                [
                    "result=lane_write_ready_manifest",
                    "mode=run",
                    "source_ready_manifest=/tmp/lane_write_ready_manifest.txt",
                    "source_environment_preflight=ok",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=2",
                    "failures=0",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d2d",
                    "candidate_0_offset_address=1000:3D2D",
                    "candidate_0_lane_write_kind=forward",
                    "candidate_0_lane_write_target=debris",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0C8F",
                    "candidate_0_fixture=/tmp/lane_forward.txt",
                    "candidate_0_oracle=explosion_playback",
                    "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
                    "candidate_0_status=ok",
                    "candidate_0_returncode=0",
                    f"candidate_0_log={log0}",
                    "candidate_0_command=./build/lezac_cpp --debug-explosion-playback-oracle /tmp/lane_forward.txt",
                    "candidate_1_route=x1p50_z0p50",
                    "candidate_1_offset_label=3ec1",
                    "candidate_1_offset_address=1000:3EC1",
                    "candidate_1_lane_write_kind=reverse",
                    "candidate_1_lane_write_target=debris",
                    "candidate_1_runtime_cs=01ED",
                    "candidate_1_runtime_ds=0C8F",
                    "candidate_1_fixture=/tmp/lane_reverse.txt",
                    "candidate_1_oracle=explosion_playback",
                    "candidate_1_oracle_flag=--debug-explosion-playback-oracle",
                    "candidate_1_status=ok",
                    "candidate_1_returncode=0",
                    f"candidate_1_log={log1}",
                    "candidate_1_command=./build/lezac_cpp --debug-explosion-playback-oracle /tmp/lane_reverse.txt",
                    "",
                ]
            ),
        )
        run_summary_text = run_summary(root, [str(run_manifest)])
        for snippet in [
            "lane_write_ready_result_summary=ok",
            "mode=run",
            "source_ready_manifest=/tmp/lane_write_ready_manifest.txt",
            "source_environment_preflight=ok",
            "oracle_binary=./build/lezac_cpp",
            "ready_candidates=2",
            "failures=0",
            "planned=0 ok=2 error=0 other=0",
            "executed_candidates=2",
            "logs_present=2",
            "logs_missing=0",
            "candidate_result index=0 route=x2p00 offset=3d2d",
            "kind=forward target=debris",
            "runtime_cs=01ED",
            "runtime_ds=0C8F",
            "fixture=/tmp/lane_forward.txt",
            "candidate_result index=1 route=x1p50_z0p50 offset=3ec1",
            "kind=reverse target=debris",
            "oracle_flag=--debug-explosion-playback-oracle",
        ]:
            require(run_summary_text, snippet, "run_manifest")
        cases += 1

        missing_log_manifest = base / "missing_log" / "result_manifest.txt"
        write_text(
            missing_log_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                f"candidate_1_log={log1}",
                "candidate_1_log=/tmp/missing-lane-write.log",
            ),
        )
        missing_log = run_summary(
            root, [str(missing_log_manifest), "--require-success"], False
        )
        require(missing_log, "reason=candidate_logs_missing", "missing_log")
        require(missing_log, "logs_missing=1", "missing_log")
        cases += 1

        run_required = run_summary(
            root,
            [
                str(run_manifest.parent),
                "--require-success",
                "--require-executed",
                "--require-source-environment-preflight",
            ],
        )
        require(run_required, "ready_candidates=2", "run_required")
        require(run_required, "source_environment_preflight=ok", "run_required")
        cases += 1

        dry_manifest = base / "dry" / "result_manifest.txt"
        write_text(
            dry_manifest,
            "\n".join(
                [
                    "result=lane_write_ready_manifest",
                    "mode=dry_run",
                    "source_ready_manifest=/tmp/lane_write_ready_manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "failures=0",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d2d",
                    "candidate_0_offset_address=1000:3D2D",
                    "candidate_0_lane_write_kind=forward",
                    "candidate_0_lane_write_target=debris",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0C8F",
                    "candidate_0_fixture=/tmp/lane.txt",
                    "candidate_0_oracle=explosion_playback",
                    "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
                    "candidate_0_status=planned",
                    "candidate_0_returncode=not_run",
                    "candidate_0_log=none",
                    "candidate_0_command=./build/lezac_cpp --debug-explosion-playback-oracle /tmp/lane.txt",
                    "",
                ]
            ),
        )
        dry = run_summary(root, [str(dry_manifest)])
        for snippet in [
            "mode=dry_run",
            "source_environment_preflight=unknown",
            "ready_candidates=1",
            "planned=1 ok=0 error=0 other=0",
            "executed_candidates=0",
        ]:
            require(dry, snippet, "dry_manifest")
        cases += 1

        dry_required = run_summary(
            root, [str(dry_manifest), "--require-executed"], False
        )
        require(dry_required, "reason=candidates_not_executed", "dry_required")
        cases += 1

        dry_preflight_required = run_summary(
            root,
            [str(dry_manifest), "--require-source-environment-preflight"],
            False,
        )
        require(
            dry_preflight_required,
            "reason=source_environment_preflight_not_ok",
            "dry_preflight_required",
        )
        require(
            dry_preflight_required,
            "source_environment_preflight=unknown",
            "dry_preflight_required",
        )
        cases += 1

        failure_manifest = base / "failure" / "result_manifest.txt"
        write_text(
            failure_manifest,
            "\n".join(
                [
                    "result=lane_write_ready_manifest",
                    "mode=run",
                    "source_ready_manifest=/tmp/lane_write_ready_manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "failures=1",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d2d",
                    "candidate_0_offset_address=1000:3D2D",
                    "candidate_0_lane_write_kind=forward",
                    "candidate_0_lane_write_target=debris",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0C8F",
                    "candidate_0_fixture=/tmp/lane.txt",
                    "candidate_0_oracle=explosion_playback",
                    "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
                    "candidate_0_status=error",
                    "candidate_0_returncode=2",
                    "candidate_0_log=none",
                    "candidate_0_command=./build/lezac_cpp --debug-explosion-playback-oracle /tmp/lane.txt",
                    "",
                ]
            ),
        )
        failure = run_summary(root, [str(failure_manifest), "--require-success"], False)
        require(failure, "reason=oracle_failures failures=1 error=1", "failure")
        cases += 1

        mismatch_manifest = base / "mismatch" / "result_manifest.txt"
        write_text(
            mismatch_manifest,
            failure_manifest.read_text(encoding="ascii").replace(
                "failures=1", "failures=0"
            ),
        )
        mismatch = run_summary(root, [str(mismatch_manifest)], False)
        require(mismatch, "reason=failure_count_mismatch", "mismatch")
        require(mismatch, "failures=0 error=1", "mismatch")
        cases += 1

        returncode_manifest = base / "returncode" / "result_manifest.txt"
        write_text(
            returncode_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "candidate_1_returncode=0", "candidate_1_returncode=7"
            ),
        )
        returncode = run_summary(root, [str(returncode_manifest)], False)
        require(returncode, "reason=status_returncode_mismatch", "returncode")
        require(
            returncode,
            "index=1 status=ok returncode=7 expected=0",
            "returncode",
        )
        cases += 1

        oracle_flag_manifest = base / "oracle_flag" / "result_manifest.txt"
        write_text(
            oracle_flag_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
                "candidate_0_oracle_flag=--debug-behavior4-runtime-oracle",
                1,
            ),
        )
        oracle_flag = run_summary(root, [str(oracle_flag_manifest)], False)
        require(
            oracle_flag,
            "candidate_0_oracle_flag='--debug-behavior4-runtime-oracle' "
            "does not match candidate_0_oracle='explosion_playback'",
            "oracle_flag",
        )
        cases += 1

        command_manifest = base / "command" / "result_manifest.txt"
        write_text(
            command_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "candidate_1_command=./build/lezac_cpp --debug-explosion-playback-oracle /tmp/lane_reverse.txt",
                "candidate_1_command=./build/lezac_cpp --debug-explosion-playback-oracle /tmp/wrong_lane_reverse.txt",
            ),
        )
        command = run_summary(root, [str(command_manifest)], False)
        require(
            command,
            "candidate_1_command does not end with oracle flag and fixture",
            "command",
        )
        require(
            command,
            "expected ['--debug-explosion-playback-oracle', '/tmp/lane_reverse.txt']",
            "command",
        )
        cases += 1

        runtime_manifest = base / "runtime" / "result_manifest.txt"
        write_text(
            runtime_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "candidate_1_runtime_cs=01ED", "candidate_1_runtime_cs=12345"
            ),
        )
        runtime = run_summary(root, [str(runtime_manifest)], False)
        require(
            runtime,
            "candidate_1_runtime_cs must be a 4-digit hexadecimal segment",
            "runtime",
        )
        cases += 1

        missing_kind_manifest = base / "missing_kind" / "result_manifest.txt"
        write_text(
            missing_kind_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "candidate_1_lane_write_kind=reverse\n", ""
            ),
        )
        missing_kind = run_summary(root, [str(missing_kind_manifest)], False)
        require(
            missing_kind,
            "missing required manifest field: candidate_1_lane_write_kind",
            "missing_kind",
        )
        cases += 1

        fixture_mismatch_path = base / "fixtures" / "lane_reverse.txt"
        write_text(fixture_mismatch_path, "runtime_cs=01ED\nruntime_ds=CAFE\n")
        fixture_mismatch_manifest = base / "fixture_mismatch" / "result_manifest.txt"
        write_text(
            fixture_mismatch_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "/tmp/lane_reverse.txt",
                fixture_mismatch_path.as_posix(),
            ),
        )
        fixture_mismatch = run_summary(root, [str(fixture_mismatch_manifest)], False)
        require(
            fixture_mismatch,
            "candidate_1_runtime_ds='0C8F' does not match fixture "
            "runtime_ds='CAFE'",
            "fixture_mismatch",
        )
        cases += 1

        visual_claim_path = base / "fixtures" / "lane_forward_visual_claim.txt"
        write_text(
            visual_claim_path,
            "temp_copy=1\nvisual_claim=1\nruntime_cs=01ED\nruntime_ds=0C8F\n",
        )
        visual_claim_manifest = base / "visual_claim" / "result_manifest.txt"
        write_text(
            visual_claim_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "/tmp/lane_forward.txt",
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

        temp_copy_path = base / "fixtures" / "lane_forward_temp_copy.txt"
        write_text(
            temp_copy_path,
            "temp_copy=0\nvisual_claim=0\nruntime_cs=01ED\nruntime_ds=0C8F\n",
        )
        temp_copy_manifest = base / "temp_copy" / "result_manifest.txt"
        write_text(
            temp_copy_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "/tmp/lane_forward.txt",
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

        duplicate_fixture_path = base / "fixtures" / "lane_forward_duplicate.txt"
        write_text(
            duplicate_fixture_path,
            "temp_copy=1\nvisual_claim=0\nruntime_cs=01ED\n"
            "runtime_ds=0C8F\nruntime_ds=0C8F\n",
        )
        duplicate_fixture_manifest = (
            base / "duplicate_fixture" / "result_manifest.txt"
        )
        write_text(
            duplicate_fixture_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "/tmp/lane_forward.txt",
                duplicate_fixture_path.as_posix(),
            ),
        )
        duplicate_fixture = run_summary(
            root,
            [str(duplicate_fixture_manifest)],
            False,
        )
        require(
            duplicate_fixture,
            "duplicate fixture field: runtime_ds",
            "duplicate_fixture",
        )
        cases += 1

        original_root = base / "original_root"
        original_fixture = write_original_fixture_tree(
            original_root,
            "explosion_playback_oracle_original_lane_write_ready.txt",
            runtime_ds="0C8F",
        )
        original_manifest = base / "original_fixture" / "result_manifest.txt"
        write_text(
            original_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "/tmp/lane_forward.txt", original_fixture.as_posix()
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
            "explosion_playback_oracle_original_lane_write_unledgered.txt",
            runtime_ds="0C8F",
            include_ledger_entry=False,
        )
        missing_ledger_manifest = base / "missing_ledger" / "result_manifest.txt"
        write_text(
            missing_ledger_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "/tmp/lane_forward.txt", missing_ledger_fixture.as_posix()
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
            "candidate_0_fixture "
            "explosion_playback_oracle_original_lane_write_unledgered.txt "
            "is missing from runtime evidence ledger",
            "missing_ledger",
        )
        cases += 1

        extra_manifest = base / "extra" / "result_manifest.txt"
        write_text(
            extra_manifest,
            run_manifest.read_text(encoding="ascii").replace(
                "ready_candidates=2", "ready_candidates=1"
            ),
        )
        extra = run_summary(root, [str(extra_manifest)], False)
        require(
            extra,
            "candidate index outside ready_candidates: 1 ready_candidates=1",
            "extra_candidate",
        )
        cases += 1

        duplicate_field_manifest = base / "duplicate_field" / "result_manifest.txt"
        write_text(
            duplicate_field_manifest,
            run_manifest.read_text(encoding="ascii")
            + "candidate_0_fixture=/tmp/other_lane_write.txt\n",
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
            run_manifest.read_text(encoding="ascii")
            .replace("candidate_1_status=ok", "candidate_1_status=planned")
            .replace("candidate_1_returncode=0", "candidate_1_returncode=not_run"),
        )
        mode_error = run_summary(root, [str(mode_manifest)], False)
        require(mode_error, "reason=mode_status_mismatch", "mode")
        require(mode_error, "mode=run planned=1 expected_planned=0", "mode")
        cases += 1

        other_manifest = base / "other" / "result_manifest.txt"
        write_text(
            other_manifest,
            "\n".join(
                [
                    "result=lane_write_ready_manifest",
                    "mode=run",
                    "source_ready_manifest=/tmp/lane_write_ready_manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "failures=0",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d2d",
                    "candidate_0_offset_address=1000:3D2D",
                    "candidate_0_lane_write_kind=forward",
                    "candidate_0_lane_write_target=debris",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0C8F",
                    "candidate_0_fixture=/tmp/lane.txt",
                    "candidate_0_oracle=explosion_playback",
                    "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
                    "candidate_0_status=skipped",
                    "candidate_0_returncode=not_run",
                    "candidate_0_log=none",
                    "candidate_0_command=./build/lezac_cpp --debug-explosion-playback-oracle /tmp/lane.txt",
                    "",
                ]
            ),
        )
        other = run_summary(root, [str(other_manifest)])
        require(other, "planned=0 ok=0 error=0 other=1", "other_status")
        other_required = run_summary(
            root, [str(other_manifest), "--require-success"], False
        )
        require(other_required, "reason=oracle_failures", "other_required")
        require(other_required, "failures=0 error=0 other=1", "other_required")
        cases += 1

        bad_result = base / "bad" / "result_manifest.txt"
        write_text(
            bad_result,
            "\n".join(
                [
                    "result=wrong_kind",
                    "mode=run",
                    "source_ready_manifest=/tmp/lane_write_ready_manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=0",
                    "failures=0",
                    "",
                ]
            ),
        )
        bad = run_summary(root, [str(bad_result)], False)
        require(bad, "unsupported result", "bad_result")
        cases += 1

        missing = run_summary(root, [str(base / "missing" / "result_manifest.txt")], False)
        require(missing, "manifest not found", "missing_manifest")
        cases += 1

    print(f"lane_write_ready_results_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
