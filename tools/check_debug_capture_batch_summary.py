#!/usr/bin/env python3
"""Check batch DOSBox-debug capture summary classification."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from check_debug_capture_summary import (
    require,
    write_actor_ready,
    write_behavior4_ready,
    write_behavior4_skeleton,
    write_contact_missing,
    write_contact_ready,
    write_visual_table_ready,
    write_text,
)
from ready_result_checker_support import write_original_fixture_tree


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_batch(
    root: Path,
    args: list[str],
    expect_success: bool = True,
    env: dict[str, str] | None = None,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_debug_capture_batch.py"),
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
        write_behavior4_ready(base)
        actor_dir = write_actor_ready(base)
        write_contact_missing(base)
        write_contact_ready(base)
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
            "manifests=7",
            "supported=6",
            "unsupported=1",
            "ready=4",
            "incomplete=1",
            "missing=1",
            "environment_ok=4",
            "environment_not_ok=2",
            "runtime_observed=4",
            "oracle_commands=6",
            "debug_capture_batch_candidate index=0",
            "capture=actor_update_runtime",
            "candidate_status=ready",
            "capture=behavior4_runtime",
            "candidate_status=incomplete",
            "oracle_flag=--debug-behavior4-runtime-oracle",
            "capture=contact_scanner_runtime",
            "candidate_status=missing",
            "oracle_flag=--debug-contact-scanner-runtime-oracle",
            "capture=visual_table",
            "oracle_flag=--debug-visual-table-oracle",
            "debug_capture_ready_manifest=ok",
            f"path={ready_manifest.resolve()}",
            "ready_candidates=4",
        ]:
            require(batch, snippet, "batch_summary")
        ready_text = ready_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=debug_capture_ready_candidates",
            "ready_candidates=4",
            "candidate_0_capture=actor_update_runtime",
            "candidate_0_environment_preflight=ok",
            "candidate_0_oracle_flag=--debug-actor-update-runtime-oracle",
            "candidate_1_capture=behavior4_runtime",
            "candidate_1_oracle_flag=--debug-behavior4-runtime-oracle",
            "candidate_2_capture=contact_scanner_runtime",
            "candidate_2_oracle_flag=--debug-contact-scanner-runtime-oracle",
            "candidate_3_capture=visual_table",
            "candidate_3_oracle_flag=--debug-visual-table-oracle",
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

        duplicate_capture = base / "duplicate_capture"
        write_text(
            duplicate_capture / "manifest.txt",
            (actor_dir / "manifest.txt").read_text(encoding="ascii")
            + "runtime_cs=CAFE\n",
        )
        duplicate = run_batch(
            root,
            [str(duplicate_capture)],
            expect_success=False,
        )
        require(duplicate, "duplicate manifest field: runtime_cs", "duplicate_field")
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

        original_root = base / "original_root"
        original_fixture = write_original_fixture_tree(
            original_root,
            "actor_update_runtime_oracle_original_writer_unledgered.txt",
            runtime_ds="0F3C",
            include_ledger_entry=False,
        )
        actor_candidate = actor_dir / "candidate_fixture.txt"
        original_fixture.write_text(actor_candidate.read_text(encoding="ascii"), encoding="ascii")
        original_capture = base / "original_capture"
        write_text(
            original_capture / "manifest.txt",
            "\n".join(
                [
                    "capture=actor_update_runtime",
                    "source=dosbox-debug",
                    "scenario=object_collision_jump_live",
                    "expected_level=1",
                    "route=debugger_seeded",
                    f"candidate_fixture={original_fixture}",
                    "environment_preflight=ok",
                    "runtime_metadata=observed",
                    "runtime_cs=01ED",
                    "runtime_ds=0F3C",
                    "",
                ]
            ),
        )
        bad_original = run_batch(
            root,
            [
                str(original_capture),
                "--write-ready-manifest",
                str(base / "bad_original_ready.txt"),
            ],
            expect_success=False,
            env={"LEZAC_READY_RESULT_REPO_ROOT": str(original_root)},
        )
        require(
            bad_original,
            "candidate_0_fixture actor_update_runtime_oracle_original_writer_unledgered.txt "
            "is missing from runtime evidence ledger",
            "bad_original_writer_fixture",
        )
        cases += 1

    print(f"debug_capture_batch_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
