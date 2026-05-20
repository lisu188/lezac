#!/usr/bin/env python3
"""Check debug-capture ready-result summarizer behavior."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


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
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_debug_capture_ready_results.py"),
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
            f"summarizer failed with {result.returncode}: {args}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(f"summarizer unexpectedly passed: {args}\n{result.stdout}")
    return result.stdout


def manifest_text(log: Path, *, mode: str = "run", status: str = "ok") -> str:
    failures = "0" if status != "error" else "1"
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
            f"candidate_0_status={status}",
            f"candidate_0_returncode={'7' if status == 'error' else '0'}",
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
            "candidate_1_log=none",
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
            "candidate_2_log=none",
            "candidate_2_command=/tmp/lezac_cpp --debug-visual-table-oracle /tmp/capture/visual_table.txt",
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
            "logs_present=1",
            "logs_missing=0",
            "candidate_result index=0 capture=behavior4_runtime",
            "candidate_result index=2 capture=visual_table",
            "oracle=visual_table",
            "--debug-visual-table-oracle",
        ]:
            require(run, snippet, "run_summary")
        cases += 1

        dry_manifest = base / "dry" / "result_manifest.txt"
        write_text(dry_manifest, manifest_text(log, mode="dry_run"))
        dry = run_summary(root, [str(dry_manifest)])
        require(dry, "mode=dry_run", "dry_summary")
        require(dry, "planned=2", "dry_summary")
        require(dry, "executed_candidates=1", "dry_summary")
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
