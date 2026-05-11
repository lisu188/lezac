#!/usr/bin/env python3
"""Check actor dispatch ready result summarizer behavior."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_summary(
    root: Path,
    args: list[str],
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_actor_dispatch_ready_results.py"),
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
        description="Check actor dispatch ready result summary output."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-ready-results-") as tmp:
        base = Path(tmp)
        log0 = base / "logs" / "candidate_0_actor_update_gate6.log"
        write_text(log0, "actor_update_runtime_oracle=ok\n")
        run_manifest = base / "run" / "result_manifest.txt"
        write_text(
            run_manifest,
            "\n".join(
                [
                    "result=actor_dispatch_ready_manifest",
                    "mode=run",
                    "source_ready_manifest=/tmp/ready_manifest.txt",
                    "source_environment_preflight=ok",
                    "child_environment_preflights=skipped",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=2",
                    "failures=0",
                    "candidate_0_target=actor_update_gate6",
                    "candidate_0_route=x3p00",
                    "candidate_0_ghidra=1000:654E",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0F3C",
                    "candidate_0_freeze_runtime=01ED:654E",
                    "candidate_0_fixture=/tmp/actor_update.txt",
                    "candidate_0_oracle=actor_update",
                    "candidate_0_oracle_flag=--debug-actor-update-runtime-oracle",
                    "candidate_0_status=ok",
                    "candidate_0_returncode=0",
                    f"candidate_0_log={log0}",
                    "candidate_0_command=./build/lezac_cpp --debug-actor-update-runtime-oracle /tmp/actor_update.txt",
                    "candidate_1_target=contact_scanner_start",
                    "candidate_1_route=x0p50",
                    "candidate_1_ghidra=1000:5CB0",
                    "candidate_1_runtime_cs=01ED",
                    "candidate_1_runtime_ds=0F3C",
                    "candidate_1_freeze_runtime=01ED:5CB0",
                    "candidate_1_fixture=/tmp/contact_scanner.txt",
                    "candidate_1_oracle=contact_scanner",
                    "candidate_1_oracle_flag=--debug-contact-scanner-runtime-oracle",
                    "candidate_1_status=ok",
                    "candidate_1_returncode=0",
                    "candidate_1_log=/tmp/missing-contact.log",
                    "candidate_1_command=./build/lezac_cpp --debug-contact-scanner-runtime-oracle /tmp/contact_scanner.txt",
                    "",
                ]
            ),
        )
        run_summary_text = run_summary(root, [str(run_manifest)])
        for snippet in [
            "actor_dispatch_ready_result_summary=ok",
            "mode=run",
            "source_ready_manifest=/tmp/ready_manifest.txt",
            "source_environment_preflight=ok",
            "child_environment_preflights=skipped",
            "oracle_binary=./build/lezac_cpp",
            "ready_candidates=2",
            "failures=0",
            "planned=0 ok=2 error=0 other=0",
            "executed_candidates=2",
            "logs_present=1",
            "logs_missing=1",
            "candidate_result index=0 target=actor_update_gate6",
            "candidate_result index=1 target=contact_scanner_start",
        ]:
            require(run_summary_text, snippet, "run_manifest")
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
                    "result=actor_dispatch_ready_manifest",
                    "mode=dry_run",
                    "source_ready_manifest=/tmp/ready_manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "failures=0",
                    "candidate_0_target=actor_update_gate6",
                    "candidate_0_route=x3p00",
                    "candidate_0_oracle=actor_update",
                    "candidate_0_status=planned",
                    "candidate_0_returncode=not_run",
                    "candidate_0_log=none",
                    "candidate_0_command=./build/lezac_cpp --debug-actor-update-runtime-oracle /tmp/actor_update.txt",
                    "",
                ]
            ),
        )
        dry = run_summary(root, [str(dry_manifest)])
        for snippet in [
            "mode=dry_run",
            "source_environment_preflight=unknown",
            "child_environment_preflights=unknown",
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
                    "result=actor_dispatch_ready_manifest",
                    "mode=run",
                    "source_ready_manifest=/tmp/ready_manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "failures=1",
                    "candidate_0_target=actor_update_gate6",
                    "candidate_0_route=x3p00",
                    "candidate_0_oracle=actor_update",
                    "candidate_0_status=error",
                    "candidate_0_returncode=2",
                    "candidate_0_log=none",
                    "candidate_0_command=./build/lezac_cpp --debug-actor-update-runtime-oracle /tmp/actor_update.txt",
                    "",
                ]
            ),
        )
        failure = run_summary(root, [str(failure_manifest), "--require-success"], False)
        require(failure, "reason=oracle_failures failures=1 error=1", "failure")
        cases += 1

        bad_result = base / "bad" / "result_manifest.txt"
        write_text(
            bad_result,
            "\n".join(
                [
                    "result=wrong_kind",
                    "mode=run",
                    "source_ready_manifest=/tmp/ready_manifest.txt",
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

    print(f"actor_dispatch_ready_results_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
