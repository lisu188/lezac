#!/usr/bin/env python3
"""Check the lane-write ready-manifest pipeline end to end."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from ready_result_checker_support import write_original_fixture_tree


OFFSET_MODEL = {
    "3d2d": ("1000:3D2D", "forward", "debris", "889597"),
    "3ec1": ("1000:3EC1", "reverse", "debris", "889598"),
}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_tool(
    root: Path,
    tool: str,
    args: list[str],
    expect_success: bool = True,
    env: dict[str, str] | None = None,
) -> str:
    command = [sys.executable, str(root / "tools" / tool), *args]
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


def write_ready_fixture(path: Path, offset_label: str) -> None:
    _, kind, target, old_bytes = OFFSET_MODEL[offset_label]
    write_text(
        path,
        "\n".join(
            [
                "capture=explosion_playback",
                "source=synthetic",
                "temp_copy=1",
                "visual_claim=0",
                "instrumented_freeze_observed=1",
                "instrumented_freeze_patch_mode=lane-write-cs-scratch",
                "instrumented_lane_write_cs_offset=0xf080",
                f"instrumented_lane_write_kind={kind}",
                f"instrumented_lane_write_target={target}",
                "instrumented_lane_write_scratch_present=1",
                "instrumented_lane_write_output=0x0035",
                "instrumented_lane_write_di=0x0898",
                "instrumented_lane_write_tag=0x4ee8",
                "instrumented_lane_write_active_count=0x0001",
                "instrumented_lane_write_loop_index=0x0001",
                "instrumented_lane_write_result_local=0x0035",
                "runtime_freeze_patch_applied=1",
                f"runtime_freeze_old_bytes={old_bytes}",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                "",
            ]
        ),
    )


def write_runtime_manifest(path: Path, fixture: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=original_explosion_process_memory",
                "asset_dir=/repo",
                f"fixture_candidate={fixture}",
                "skip_oracle=1",
                "",
            ]
        ),
    )


def write_route_sweep(path: Path, child_manifest: Path, fixture: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=lane_write_route_sweep",
                "asset_dir=/repo",
                "offsets=1",
                "offset_labels=3d2d",
                "offset_addresses=1000:3D2D",
                "routes=1",
                "route_labels=x2p00_c0p50",
                "environment_preflight=ok",
                "capture_status_x2p00_c0p50=lane_write_capture=ok "
                "route=x2p00_c0p50 offset=3d2d offset_address=1000:3D2D "
                f"manifest={child_manifest} candidate={fixture}",
                "",
            ]
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-write ready manifest promotion pipeline."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-lane-write-ready-pipeline-") as tmp:
        base = Path(tmp)
        fixture = base / "candidate" / "lane_write_candidate.txt"
        write_ready_fixture(fixture, "3d2d")
        runtime_manifest = base / "runtime" / "manifest.txt"
        write_runtime_manifest(runtime_manifest, fixture)
        sweep_manifest = base / "sweep" / "manifest.txt"
        write_route_sweep(sweep_manifest, runtime_manifest, fixture)

        ready_manifest = base / "ready_manifest.txt"
        summary = run_tool(
            root,
            "summarize_lane_write_route_sweep.py",
            [
                str(sweep_manifest),
                "--require-ready",
                "--require-environment-preflight",
                "--write-ready-manifest",
                str(ready_manifest),
            ],
        )
        for snippet in [
            "lane_write_route_sweep_summary=ok",
            "mode=route",
            "ready_candidates=1",
            "lane_write_ready_manifest=ok",
            f"path={ready_manifest.resolve()}",
        ]:
            require(summary, snippet, "pipeline_summary")
        ready_text = ready_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=lane_write_ready_candidates",
            "source_environment_preflight=ok",
            "candidate_0_route=x2p00_c0p50",
            "candidate_0_offset_label=3d2d",
            "candidate_0_lane_write_kind=forward",
            "candidate_0_lane_write_target=debris",
            "candidate_0_oracle=explosion_playback",
            "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
        ]:
            require(ready_text, snippet, "ready_manifest")

        blocked_ready_manifest = base / "blocked_ready_manifest.txt"
        write_text(
            blocked_ready_manifest,
            ready_text.replace(
                "source_environment_preflight=ok",
                "source_environment_preflight=error",
            ),
        )
        blocked = run_tool(
            root,
            "run_lane_write_ready_manifest.py",
            [
                str(blocked_ready_manifest),
                "--dry-run",
                "--require-source-environment-preflight",
            ],
            expect_success=False,
        )
        require(
            blocked,
            "reason=source_environment_preflight_not_ok",
            "blocked_source_environment_preflight",
        )
        require(
            blocked,
            "source_environment_preflight=error",
            "blocked_source_environment_preflight",
        )
        cases += 1

        dry_result_manifest = base / "dry" / "result_manifest.txt"
        dry = run_tool(
            root,
            "run_lane_write_ready_manifest.py",
            [
                str(ready_manifest),
                "--dry-run",
                "--require-source-environment-preflight",
                "--write-result-manifest",
                str(dry_result_manifest),
            ],
        )
        for snippet in [
            "lane_write_ready_manifest=ok mode=dry_run",
            "ready_candidates=1",
            "source_environment_preflight=ok",
            "ready_candidate index=0 route=x2p00_c0p50 offset=3d2d",
            "kind=forward target=debris",
            "oracle=explosion_playback",
            "lane_write_ready_result_manifest=ok",
            f"path={dry_result_manifest.resolve()}",
        ]:
            require(dry, snippet, "pipeline_dry_run")
        dry_result = run_tool(
            root,
            "summarize_lane_write_ready_results.py",
            [str(dry_result_manifest), "--require-source-environment-preflight"],
        )
        for snippet in [
            "lane_write_ready_result_summary=ok",
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
            "run_lane_write_ready_manifest.py",
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
            "lane_write_ready_manifest=ok mode=run",
            "ready_candidate index=0 route=x2p00_c0p50",
            "kind=forward target=debris",
            "status=ok returncode=0",
            "lane_write_ready_result_manifest=ok",
            f"path={result_manifest.resolve()}",
        ]:
            require(runner, snippet, "pipeline_runner")
        log_text = (log_dir / "candidate_0_3d2d_x2p00_c0p50.log").read_text(
            encoding="utf-8"
        )
        require(
            log_text,
            "fake_oracle flag=--debug-explosion-playback-oracle",
            "pipeline_runner_log",
        )

        result = run_tool(
            root,
            "summarize_lane_write_ready_results.py",
            [
                str(result_manifest),
                "--require-success",
                "--require-executed",
                "--require-source-environment-preflight",
            ],
        )
        for snippet in [
            "lane_write_ready_result_summary=ok",
            "mode=run",
            "ready_candidates=1",
            "failures=0",
            "planned=0 ok=1 error=0 other=0",
            "executed_candidates=1",
            "logs_present=1",
            "logs_missing=0",
            "kind=forward target=debris",
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
            "run_lane_write_ready_manifest.py",
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
                    "promotion=lane_write_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d2d",
                    "candidate_0_offset_address=1000:3D2D",
                    "candidate_0_lane_write_kind=forward",
                    "candidate_0_lane_write_target=debris",
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
            "run_lane_write_ready_manifest.py",
            [str(bad_flag), "--dry-run"],
            expect_success=False,
        )
        require(flag, "does not match", "bad_flag")
        require(flag, "--debug-explosion-playback-oracle", "bad_flag")
        cases += 1

        repo_output = run_tool(
            root,
            "run_lane_write_ready_manifest.py",
            [
                str(ready_manifest),
                "--dry-run",
                "--write-result-manifest",
                str(root / "lane-write-ready-result.txt"),
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
                    "promotion=lane_write_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d2d",
                    "candidate_0_offset_address=1000:3D2D",
                    "candidate_0_lane_write_kind=forward",
                    "candidate_0_lane_write_target=debris",
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
            "run_lane_write_ready_manifest.py",
            [str(missing_fixture), "--dry-run"],
            expect_success=False,
        )
        require(missing, "candidate fixture not found", "missing_fixture")
        allowed = run_tool(
            root,
            "run_lane_write_ready_manifest.py",
            [str(missing_fixture), "--dry-run", "--allow-missing-fixtures"],
        )
        require(allowed, "ready_candidate index=0 route=x2p00", "missing_allowed")
        cases += 1

        original_root = base / "original_root"
        original_fixture = write_original_fixture_tree(
            original_root,
            "explosion_playback_oracle_original_lane_write_runner_unledgered.txt",
            runtime_ds="0C8F",
            include_ledger_entry=False,
        )
        bad_original_manifest = base / "bad_original_ready.txt"
        write_text(
            bad_original_manifest,
            "\n".join(
                [
                    "promotion=lane_write_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "candidate_0_route=x2p00",
                    "candidate_0_offset_label=3d2d",
                    "candidate_0_offset_address=1000:3D2D",
                    "candidate_0_lane_write_kind=forward",
                    "candidate_0_lane_write_target=debris",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0C8F",
                    f"candidate_0_fixture={original_fixture}",
                    "candidate_0_oracle=explosion_playback",
                    "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
                    "",
                ]
            ),
        )
        bad_original = run_tool(
            root,
            "run_lane_write_ready_manifest.py",
            [str(bad_original_manifest), "--dry-run"],
            expect_success=False,
            env={"LEZAC_READY_RESULT_REPO_ROOT": str(original_root)},
        )
        require(
            bad_original,
            "candidate_0_fixture "
            "explosion_playback_oracle_original_lane_write_runner_unledgered.txt "
            "is missing from runtime evidence ledger",
            "bad_original_runner_fixture",
        )
        cases += 1

        dry_required = run_tool(
            root,
            "summarize_lane_write_ready_results.py",
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
        failure = run_tool(
            root,
            "summarize_lane_write_ready_results.py",
            [str(failure_manifest), "--require-success"],
            expect_success=False,
        )
        require(failure, "reason=oracle_failures failures=1 error=1", "failure")
        cases += 1

    print(f"lane_write_ready_pipeline_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
