#!/usr/bin/env python3
"""Check the lane-result ready-manifest pipeline end to end."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


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
            f"{tool} failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"{tool} unexpectedly passed: {' '.join(args)}\n{result.stdout}"
        )
    return result.stdout


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def make_fake_oracle(base: Path) -> Path:
    if os.name == "nt":
        fake = base / "fake_oracle.cmd"
        write_text(
            fake,
            "\r\n".join(
                [
                    "@echo off",
                    "echo fake_oracle flag=%1 fixture=%2",
                    'if "%1"=="--debug-explosion-playback-oracle" exit /b 0',
                    "exit /b 7",
                    "",
                ]
            ),
        )
        return fake

    fake = base / "fake_oracle.py"
    write_text(
        fake,
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import sys",
                "flag = sys.argv[1] if len(sys.argv) > 1 else ''",
                "fixture = sys.argv[2] if len(sys.argv) > 2 else ''",
                "print(f'fake_oracle flag={flag} fixture={fixture}')",
                "sys.exit(0 if flag == '--debug-explosion-playback-oracle' else 7)",
                "",
            ]
        ),
    )
    fake.chmod(0o755)
    return fake


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def write_ready_fixture(path: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=explosion_playback",
                "source=synthetic",
                "temp_copy=1",
                "visual_claim=0",
                "instrumented_freeze_observed=1",
                "instrumented_freeze_patch_mode=lane-result-cs-scratch",
                "freeze_expected_old_bytes=268805",
                "freeze_old_bytes=268805",
                "runtime_freeze_patch_applied=1",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                "instrumented_lane_result_scratch_present=1",
                "instrumented_lane_result_cs_offset=0xf280",
                "instrumented_lane_result_kind=forward",
                "instrumented_lane_result_output=0x0004",
                "instrumented_lane_result_es=0x2b3c",
                "instrumented_lane_result_di=0x78d2",
                "instrumented_lane_result_arg_offset=0x78d2",
                "instrumented_lane_result_arg_segment=0x2b3c",
                "instrumented_lane_result_result_local=0x0004",
                "instrumented_lane_result_active_count=0x0001",
                "instrumented_lane_result_loop_index=0x0001",
                "instrumented_lane_result_target_before=0x0010",
                "",
            ]
        ),
    )


def write_runtime_manifest(path: Path, fixture: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=lane_result_runtime",
                "asset_dir=/repo",
                "cpp_exe=./build/lezac_cpp",
                "offsets=1",
                "offset_labels=3d3f",
                "offset_addresses=1000:3D3F",
                f"candidate_3d3f={fixture}",
                "skip_oracle=1",
                "",
            ]
        ),
    )


def write_route_sweep(path: Path, child_manifest: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=lane_result_route_sweep",
                "asset_dir=/repo",
                "offset=forward",
                "routes=1",
                "route_labels=x2p00_c0p50",
                "environment_preflight=ok",
                "capture_status_x2p00_c0p50=lane_result_capture_orchestrator=ok "
                "mode=capture out_dir=/tmp/lane candidates=1 "
                "offset_labels=3d3f offset_addresses=1000:3D3F "
                f"manifest={child_manifest}",
                "",
            ]
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-result ready manifest promotion pipeline."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-lane-ready-pipeline-") as tmp:
        base = Path(tmp)
        fixture = base / "candidate" / "lane_result_candidate.txt"
        write_ready_fixture(fixture)
        runtime_manifest = base / "runtime" / "manifest.txt"
        write_runtime_manifest(runtime_manifest, fixture)
        sweep_manifest = base / "sweep" / "manifest.txt"
        write_route_sweep(sweep_manifest, runtime_manifest)

        ready_manifest = base / "ready_manifest.txt"
        summary = run_tool(
            root,
            "summarize_lane_result_route_sweep.py",
            [
                str(sweep_manifest),
                "--require-ready",
                "--require-environment-preflight",
                "--write-ready-manifest",
                str(ready_manifest),
            ],
        )
        for snippet in [
            "lane_result_route_sweep_summary=ok",
            "mode=route",
            "ready_candidates=1",
            "lane_result_ready_manifest=ok",
            f"path={ready_manifest.resolve()}",
        ]:
            require(summary, snippet, "pipeline_summary")
        ready_text = ready_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=lane_result_ready_candidates",
            "source_environment_preflight=ok",
            "candidate_0_route=x2p00_c0p50",
            "candidate_0_offset_label=3d3f",
            "candidate_0_oracle=explosion_playback",
            "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
        ]:
            require(ready_text, snippet, "ready_manifest")

        dry_result_manifest = base / "dry" / "result_manifest.txt"
        dry = run_tool(
            root,
            "run_lane_result_ready_manifest.py",
            [
                str(ready_manifest),
                "--dry-run",
                "--require-source-environment-preflight",
                "--write-result-manifest",
                str(dry_result_manifest),
            ],
        )
        for snippet in [
            "lane_result_ready_manifest=ok mode=dry_run",
            "ready_candidates=1",
            "source_environment_preflight=ok",
            "ready_candidate index=0 route=x2p00_c0p50 offset=3d3f",
            "oracle=explosion_playback",
            "lane_result_ready_result_manifest=ok",
            f"path={dry_result_manifest.resolve()}",
        ]:
            require(dry, snippet, "pipeline_dry_run")
        dry_result = run_tool(
            root,
            "summarize_lane_result_ready_results.py",
            [str(dry_result_manifest), "--require-source-environment-preflight"],
        )
        for snippet in [
            "lane_result_ready_result_summary=ok",
            "mode=dry_run",
            "ready_candidates=1",
            "planned=1 ok=0 error=0 other=0",
            "executed_candidates=0",
        ]:
            require(dry_result, snippet, "pipeline_dry_result")

        fake_oracle = make_fake_oracle(base / "fake")
        log_dir = base / "logs"
        result_manifest = base / "results" / "result_manifest.txt"
        runner = run_tool(
            root,
            "run_lane_result_ready_manifest.py",
            [
                str(ready_manifest),
                "--require-source-environment-preflight",
                "--oracle-binary",
                str(fake_oracle),
                "--log-dir",
                str(log_dir),
                "--write-result-manifest",
                str(result_manifest),
                "--timeout-seconds",
                "5",
            ],
        )
        for snippet in [
            "lane_result_ready_manifest=ok mode=run",
            "ready_candidate index=0 route=x2p00_c0p50",
            "status=ok returncode=0",
            "lane_result_ready_result_manifest=ok",
            f"path={result_manifest.resolve()}",
        ]:
            require(runner, snippet, "pipeline_runner")
        log_text = (log_dir / "candidate_0_3d3f_x2p00_c0p50.log").read_text(
            encoding="utf-8"
        )
        require(
            log_text,
            "fake_oracle flag=--debug-explosion-playback-oracle",
            "pipeline_runner_log",
        )

        result = run_tool(
            root,
            "summarize_lane_result_ready_results.py",
            [
                str(result_manifest),
                "--require-success",
                "--require-executed",
                "--require-source-environment-preflight",
            ],
        )
        for snippet in [
            "lane_result_ready_result_summary=ok",
            "mode=run",
            "ready_candidates=1",
            "failures=0",
            "planned=0 ok=1 error=0 other=0",
            "executed_candidates=1",
            "logs_present=1",
            "logs_missing=0",
        ]:
            require(result, snippet, "pipeline_result")
        cases += 1

        bad_promotion = base / "bad_promotion.txt"
        write_text(
            bad_promotion,
            "\n".join(
                [
                    "promotion=wrong_kind",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=0",
                    "",
                ]
            ),
        )
        bad = run_tool(
            root,
            "run_lane_result_ready_manifest.py",
            [str(bad_promotion), "--dry-run"],
            expect_success=False,
        )
        require(bad, "unsupported promotion", "bad_promotion")
        cases += 1

        bad_flag = base / "bad_flag.txt"
        write_text(
            bad_flag,
            "\n".join(
                [
                    "promotion=lane_result_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d3f",
                    "candidate_0_offset_address=1000:3D3F",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0C8F",
                    f"candidate_0_fixture={fixture}",
                    "candidate_0_oracle=explosion_playback",
                    "candidate_0_oracle_flag=--debug-actor-update-runtime-oracle",
                    "",
                ]
            ),
        )
        flag = run_tool(
            root,
            "run_lane_result_ready_manifest.py",
            [str(bad_flag), "--dry-run"],
            expect_success=False,
        )
        require(flag, "does not match", "bad_flag")
        require(flag, "--debug-explosion-playback-oracle", "bad_flag")
        cases += 1

        repo_output = run_tool(
            root,
            "run_lane_result_ready_manifest.py",
            [
                str(ready_manifest),
                "--dry-run",
                "--write-result-manifest",
                str(root / "lane-result-ready-result.txt"),
            ],
            expect_success=False,
        )
        require(
            repo_output,
            "--write-result-manifest must be outside the repository",
            "repo_output",
        )
        cases += 1

        missing_fixture = base / "missing_fixture.txt"
        write_text(
            missing_fixture,
            "\n".join(
                [
                    "promotion=lane_result_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d3f",
                    "candidate_0_offset_address=1000:3D3F",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0C8F",
                    "candidate_0_fixture=missing.txt",
                    "candidate_0_oracle=explosion_playback",
                    "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
                    "",
                ]
            ),
        )
        missing = run_tool(
            root,
            "run_lane_result_ready_manifest.py",
            [str(missing_fixture), "--dry-run"],
            expect_success=False,
        )
        require(missing, "candidate fixture not found", "missing_fixture")
        allowed = run_tool(
            root,
            "run_lane_result_ready_manifest.py",
            [str(missing_fixture), "--dry-run", "--allow-missing-fixtures"],
        )
        require(allowed, "ready_candidate index=0 route=x2p00", "missing_allowed")
        cases += 1

        dry_required = run_tool(
            root,
            "summarize_lane_result_ready_results.py",
            [str(dry_result_manifest), "--require-executed"],
            expect_success=False,
        )
        require(dry_required, "reason=candidates_not_executed", "dry_required")
        cases += 1

        failure_manifest = base / "failure_result.txt"
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
        failure = run_tool(
            root,
            "summarize_lane_result_ready_results.py",
            [str(failure_manifest), "--require-success"],
            expect_success=False,
        )
        require(failure, "reason=oracle_failures failures=1 error=1", "failure")
        cases += 1

    print(f"lane_result_ready_pipeline_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
