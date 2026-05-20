#!/usr/bin/env python3
"""Check the generic debug-capture ready-result promotion pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from check_debug_capture_ready_manifest import make_fake_oracle
from check_debug_capture_summary import (
    require,
    write_actor_ready,
    write_visual_table_ready,
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_tool(
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the debug-capture ready manifest handoff pipeline."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-debug-ready-pipeline-") as tmp:
        base = Path(tmp)
        batch_dir = base / "batch"
        write_actor_ready(batch_dir)
        write_visual_table_ready(batch_dir)

        ready_manifest = base / "ready" / "ready_manifest.txt"
        batch = run_tool(
            root,
            "summarize_debug_capture_batch.py",
            [
                str(batch_dir),
                "--write-ready-manifest",
                str(ready_manifest),
                "--require-any-ready",
                "--require-environment-preflight",
            ],
        )
        for snippet in [
            "debug_capture_batch_summary=ok",
            "ready=2",
            "environment_ok=2",
            "debug_capture_ready_manifest=ok",
            f"path={ready_manifest.resolve()}",
            "ready_candidates=2",
            "capture=visual_table",
            "oracle_flag=--debug-visual-table-oracle",
        ]:
            require(batch, snippet, "batch_to_ready")

        fake_oracle = make_fake_oracle(base / "fake")
        result_manifest = base / "results" / "result_manifest.txt"
        logs = base / "logs"
        run = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [
                str(ready_manifest),
                "--oracle-binary",
                str(fake_oracle),
                "--require-source-environment-preflight",
                "--log-dir",
                str(logs),
                "--write-result-manifest",
                str(result_manifest),
            ],
        )
        for snippet in [
            "debug_capture_ready_manifest=ok mode=run",
            "ready_candidates=2",
            "status=ok",
            "returncode=0",
            "debug_capture_ready_result_manifest=ok",
            f"path={result_manifest.resolve()}",
            "failures=0",
        ]:
            require(run, snippet, "ready_run")

        summary = run_tool(
            root,
            "summarize_debug_capture_ready_results.py",
            [
                str(result_manifest),
                "--require-success",
                "--require-executed",
                "--require-source-environment-preflight",
            ],
        )
        for snippet in [
            "debug_capture_ready_result_summary=ok",
            "mode=run",
            "ready_candidates=2",
            "failures=0",
            "planned=0",
            "ok=2",
            "executed_candidates=2",
            "environment_preflight_ok=2",
            "logs_present=2",
            "logs_missing=0",
            "candidate_result index=0",
            "oracle=actor_update",
            "candidate_result index=1",
            "oracle=visual_table",
            "--debug-visual-table-oracle",
            "status=ok",
        ]:
            require(summary, snippet, "result_summary")
        cases += 1

        dry_result = base / "results" / "dry_result_manifest.txt"
        dry = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [
                str(ready_manifest),
                "--dry-run",
                "--oracle-binary",
                str(fake_oracle),
                "--write-result-manifest",
                str(dry_result),
            ],
        )
        require(dry, "debug_capture_ready_manifest=ok mode=dry_run", "dry_run")
        dry_required = run_tool(
            root,
            "summarize_debug_capture_ready_results.py",
            [str(dry_result), "--require-executed"],
            expect_success=False,
        )
        require(dry_required, "reason=candidates_not_executed", "dry_required")
        cases += 1

    print(f"debug_capture_ready_pipeline_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
