#!/usr/bin/env python3
"""Check batch DOSBox-debug capture summary classification."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from check_debug_capture_summary import (
    require,
    write_actor_ready,
    write_behavior4_skeleton,
    write_contact_missing,
    write_visual_table_ready,
    write_text,
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_batch(
    root: Path,
    args: list[str],
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_debug_capture_batch.py"),
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
            f"summarize_debug_capture_batch.py failed with {result.returncode}: {args}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"summarize_debug_capture_batch.py unexpectedly passed: {args}\n"
            f"{result.stdout}"
        )
    return result.stdout


def write_unsupported(base: Path) -> None:
    write_text(
        base / "unsupported" / "manifest.txt",
        "\n".join(["capture=frame_sequence", "scenario=ignored", ""]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check summarize_debug_capture_batch.py behavior."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-debug-batch-") as tmp:
        base = Path(tmp)
        write_behavior4_skeleton(base)
        actor_dir = write_actor_ready(base)
        write_contact_missing(base)
        write_visual_table_ready(base)
        write_unsupported(base)

        ready_manifest = base / "ready" / "ready_manifest.txt"
        batch = run_batch(
            root,
            [
                str(base),
                "--write-ready-manifest",
                str(ready_manifest),
            ],
        )
        for snippet in [
            "debug_capture_batch_summary=ok",
            "manifests=5",
            "supported=4",
            "unsupported=1",
            "ready=2",
            "incomplete=1",
            "missing=1",
            "environment_ok=2",
            "environment_not_ok=2",
            "runtime_observed=2",
            "oracle_commands=4",
            "debug_capture_batch_candidate index=0",
            "capture=actor_update_runtime",
            "candidate_status=ready",
            "capture=behavior4_runtime",
            "candidate_status=incomplete",
            "capture=contact_scanner_runtime",
            "candidate_status=missing",
            "capture=visual_table",
            "oracle_flag=--debug-visual-table-oracle",
            "debug_capture_ready_manifest=ok",
            f"path={ready_manifest.resolve()}",
            "ready_candidates=2",
        ]:
            require(batch, snippet, "batch_summary")
        ready_text = ready_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=debug_capture_ready_candidates",
            "ready_candidates=2",
            "candidate_0_capture=actor_update_runtime",
            "candidate_0_environment_preflight=ok",
            "candidate_0_oracle_flag=--debug-actor-update-runtime-oracle",
            "candidate_1_capture=visual_table",
            "candidate_1_oracle_flag=--debug-visual-table-oracle",
        ]:
            require(ready_text, snippet, "ready_manifest")
        cases += 1

        run_batch(
            root,
            [str(actor_dir), "--require-any-ready", "--require-environment-preflight"],
        )
        cases += 1

        no_ready = run_batch(
            root,
            [str(base / "behavior4"), "--require-any-ready"],
            expect_success=False,
        )
        require(no_ready, "reason=no_ready_candidates", "require_any_ready")
        cases += 1

        preflight_required = run_batch(
            root,
            [str(base), "--require-environment-preflight"],
            expect_success=False,
        )
        require(
            preflight_required,
            "reason=environment_preflight_not_ok",
            "require_environment",
        )
        cases += 1

        unsupported_only = run_batch(
            root,
            [str(base / "unsupported")],
            expect_success=False,
        )
        require(
            unsupported_only,
            "reason=no_supported_captures",
            "unsupported_only",
        )
        cases += 1

    print(f"debug_capture_batch_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
