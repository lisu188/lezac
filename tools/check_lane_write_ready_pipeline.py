#!/usr/bin/env python3
"""Check the lane-write ready-manifest handoff end to end."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


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


def run_tool(
    root: Path,
    script: str,
    args: list[str],
    expect_success: bool = True,
) -> str:
    command = [sys.executable, str(root / "tools" / script), *args]
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
            f"{script} failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"{script} unexpectedly passed: {' '.join(args)}\n{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def write_fixture(path: Path) -> None:
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
                "runtime_freeze_patch_applied=1",
                "runtime_freeze_old_bytes=889597",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                "instrumented_lane_write_scratch_present=1",
                "instrumented_lane_write_cs_offset=0xf080",
                "instrumented_lane_write_kind=forward",
                "instrumented_lane_write_target=debris",
                "instrumented_lane_write_output=0x0035",
                "instrumented_lane_write_di=0x0898",
                "instrumented_lane_write_tag=0x4ee8",
                "instrumented_lane_write_active_count=0x0001",
                "instrumented_lane_write_loop_index=0x0001",
                "instrumented_lane_write_result_local=0x0035",
                "",
            ]
        ),
    )


def write_ready_manifest(path: Path, fixture: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "promotion=lane_write_ready_candidates",
                "source_manifest=/tmp/source/manifest.txt",
                "source_environment_preflight=ok",
                "oracle_binary=/tmp/lezac cpp/lezac_cpp",
                "ready_candidates=1",
                "candidate_0_route=x2p00_c0p50",
                "candidate_0_offset_label=3d2d",
                "candidate_0_offset_address=1000:3D2D",
                "candidate_0_runtime_cs=01ED",
                "candidate_0_runtime_ds=0C8F",
                f"candidate_0_fixture={fixture}",
                "candidate_0_oracle=explosion_playback",
                "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
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

    with tempfile.TemporaryDirectory(prefix="lezac-lane-write-ready-") as tmp:
        base = Path(tmp)
        fixture = base / "fixture" / "lane_write.txt"
        write_fixture(fixture)
        quoted_fixture = shlex.quote(str(fixture))
        ready_manifest = base / "ready" / "manifest.txt"
        write_ready_manifest(ready_manifest, fixture)

        dry_result_manifest = base / "ready" / "dry_result_manifest.txt"
        dry = run_tool(
            root,
            "run_lane_write_ready_manifest.py",
            [
                str(ready_manifest),
                "--dry-run",
                "--write-result-manifest",
                str(dry_result_manifest),
            ],
        )
        for snippet in [
            "lane_write_ready_manifest=ok mode=dry_run",
            "source_environment_preflight=ok",
            "ready_candidates=1",
            "lane_write_ready_result_manifest=ok",
            "ready_candidate index=0 route=x2p00_c0p50 offset=3d2d",
            "offset_address=1000:3D2D runtime_cs=01ED runtime_ds=0C8F",
            "oracle=explosion_playback oracle_flag=--debug-explosion-playback-oracle",
            f"fixture={fixture}",
            "command='/tmp/lezac cpp/lezac_cpp' "
            f"--debug-explosion-playback-oracle {quoted_fixture}",
        ]:
            require(dry, snippet, "dry_run")
        cases += 1

        dry_result_text = dry_result_manifest.read_text(encoding="utf-8")
        for snippet in [
            "result=lane_write_ready_manifest",
            "mode=dry_run",
            f"source_ready_manifest={ready_manifest.resolve()}",
            "source_environment_preflight=ok",
            "ready_candidates=1",
            "failures=0",
            "candidate_0_status=planned",
            "candidate_0_returncode=not_run",
            f"candidate_0_command='/tmp/lezac cpp/lezac_cpp' "
            f"--debug-explosion-playback-oracle {quoted_fixture}",
        ]:
            require(dry_result_text, snippet, "dry_result_manifest")
        cases += 1

        dry_summary = run_tool(
            root,
            "summarize_lane_write_ready_results.py",
            [str(dry_result_manifest)],
        )
        for snippet in [
            "lane_write_ready_result_summary=ok",
            "mode=dry_run",
            "ready_candidates=1",
            "planned=1",
            "executed_candidates=0",
            "candidate_result index=0 route=x2p00_c0p50 offset=3d2d",
        ]:
            require(dry_summary, snippet, "dry_summary")
        cases += 1

        dry_require_executed = run_tool(
            root,
            "summarize_lane_write_ready_results.py",
            [str(dry_result_manifest), "--require-executed"],
            expect_success=False,
        )
        require(
            dry_require_executed,
            "reason=candidates_not_executed planned=1",
            "dry_require_executed",
        )
        cases += 1

        fake_oracle = make_fake_oracle(base / "fake")
        log_dir = base / "logs"
        live_result_manifest = base / "logs" / "result_manifest.txt"
        live = run_tool(
            root,
            "run_lane_write_ready_manifest.py",
            [
                str(ready_manifest),
                "--oracle-binary",
                str(fake_oracle),
                "--log-dir",
                str(log_dir),
                "--write-result-manifest",
                str(live_result_manifest),
                "--timeout-seconds",
                "5",
            ],
        )
        for snippet in [
            "lane_write_ready_manifest=ok mode=run",
            "ready_candidate index=0 route=x2p00_c0p50",
            "status=ok returncode=0",
            "lane_write_ready_result_manifest=ok",
            f"command={shlex.quote(str(fake_oracle))} "
            f"--debug-explosion-playback-oracle {quoted_fixture}",
        ]:
            require(live, snippet, "live")
        log_path = log_dir / "candidate_0_3d2d_x2p00_c0p50.log"
        require(
            log_path.read_text(encoding="utf-8"),
            "fake_oracle flag=--debug-explosion-playback-oracle",
            "live_log",
        )
        cases += 1

        live_summary = run_tool(
            root,
            "summarize_lane_write_ready_results.py",
            [
                str(live_result_manifest),
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
            "planned=0",
            "ok=1",
            "executed_candidates=1",
            "logs_present=1",
        ]:
            require(live_summary, snippet, "live_summary")
        cases += 1

        bad_promotion = base / "bad-promotion" / "manifest.txt"
        write_text(
            bad_promotion,
            "\n".join(
                [
                    "promotion=lane_result_ready_candidates",
                    "source_environment_preflight=ok",
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
        require(bad, "lane_write_ready_candidates", "bad_promotion")
        cases += 1

    print(f"lane_write_ready_pipeline_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
