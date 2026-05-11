#!/usr/bin/env python3
"""Check lane-result ready result summarizer behavior."""

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
        str(root / "tools" / "summarize_lane_result_ready_results.py"),
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
        description="Check lane-result ready result summary output."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-lane-ready-results-") as tmp:
        base = Path(tmp)
        log0 = base / "logs" / "candidate_0_3d3f_x2p00.log"
        write_text(log0, "explosion_playback_oracle=ok\n")
        run_manifest = base / "run" / "result_manifest.txt"
        write_text(
            run_manifest,
            "\n".join(
                [
                    "result=lane_result_ready_manifest",
                    "mode=run",
                    "source_ready_manifest=/tmp/ready_manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=2",
                    "failures=0",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d3f",
                    "candidate_0_offset_address=1000:3D3F",
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
                    "candidate_1_offset_label=3ed3",
                    "candidate_1_offset_address=1000:3ED3",
                    "candidate_1_runtime_cs=01ED",
                    "candidate_1_runtime_ds=0C8F",
                    "candidate_1_fixture=/tmp/lane_reverse.txt",
                    "candidate_1_oracle=explosion_playback",
                    "candidate_1_oracle_flag=--debug-explosion-playback-oracle",
                    "candidate_1_status=ok",
                    "candidate_1_returncode=0",
                    "candidate_1_log=/tmp/missing-lane.log",
                    "candidate_1_command=./build/lezac_cpp --debug-explosion-playback-oracle /tmp/lane_reverse.txt",
                    "",
                ]
            ),
        )
        run_summary_text = run_summary(root, [str(run_manifest)])
        for snippet in [
            "lane_result_ready_result_summary=ok",
            "mode=run",
            "source_ready_manifest=/tmp/ready_manifest.txt",
            "oracle_binary=./build/lezac_cpp",
            "ready_candidates=2",
            "failures=0",
            "planned=0 ok=2 error=0 other=0",
            "executed_candidates=2",
            "logs_present=1",
            "logs_missing=1",
            "candidate_result index=0 route=x2p00 offset=3d3f",
            "candidate_result index=1 route=x1p50_z0p50 offset=3ed3",
        ]:
            require(run_summary_text, snippet, "run_manifest")
        cases += 1

        run_required = run_summary(
            root,
            [str(run_manifest.parent), "--require-success", "--require-executed"],
        )
        require(run_required, "ready_candidates=2", "run_required")
        cases += 1

        dry_manifest = base / "dry" / "result_manifest.txt"
        write_text(
            dry_manifest,
            "\n".join(
                [
                    "result=lane_result_ready_manifest",
                    "mode=dry_run",
                    "source_ready_manifest=/tmp/ready_manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "failures=0",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d3f",
                    "candidate_0_offset_address=1000:3D3F",
                    "candidate_0_oracle=explosion_playback",
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

        failure_manifest = base / "failure" / "result_manifest.txt"
        write_text(
            failure_manifest,
            "\n".join(
                [
                    "result=lane_result_ready_manifest",
                    "mode=run",
                    "source_ready_manifest=/tmp/ready_manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "failures=1",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d3f",
                    "candidate_0_offset_address=1000:3D3F",
                    "candidate_0_oracle=explosion_playback",
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

        other_manifest = base / "other" / "result_manifest.txt"
        write_text(
            other_manifest,
            "\n".join(
                [
                    "result=lane_result_ready_manifest",
                    "mode=run",
                    "source_ready_manifest=/tmp/ready_manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "failures=0",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d3f",
                    "candidate_0_offset_address=1000:3D3F",
                    "candidate_0_oracle=explosion_playback",
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

    print(f"lane_result_ready_results_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
