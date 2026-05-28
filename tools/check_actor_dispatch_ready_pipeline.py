#!/usr/bin/env python3
"""Check the actor dispatch ready-manifest pipeline end to end."""

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
                    'if "%1"=="--debug-actor-update-runtime-oracle" exit /b 0',
                    'if "%1"=="--debug-contact-scanner-runtime-oracle" exit /b 0',
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
                "sys.exit(0 if flag.startswith('--debug-') else 7)",
                "",
            ]
        ),
    )
    fake.chmod(0o755)
    return fake


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def write_ready_actor_fixture(path: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=actor_update_runtime",
                "source=synthetic",
                "temp_copy=1",
                "visual_claim=0",
                "scenario=object_collision_jump_live",
                "level=1",
                "runtime_cs=01ED",
                "runtime_ds=0F3C",
                "break ghidra=1000:5CB0 runtime=01ED:5CB0 label=contact_scanner_start",
                "break ghidra=1000:604F runtime=01ED:604F label=contact_scanner_end",
                "break ghidra=1000:6053 runtime=01ED:6053 label=actor_update_start",
                "break ghidra=1000:777F runtime=01ED:777F label=actor_update_end",
                "actor_before slot=0 behavior=3 kind=1 state=0 x=0x0068 y=0x00a8 vx8=32 vy8=0 hp=3 flags=0x0000 contact=0 on_ground=1",
                "actor_after slot=0 behavior=3 kind=1 state=0 x=0x0069 y=0x00a8 vx8=32 vy8=0 hp=3 flags=0x0005 contact=1 on_ground=1",
                "contact_scan subject_slot=0 other_slot=1 flags_before=0x0000 flags_after=0x0005 contact=1 player_contact=0 monster_contact=0 object_contact=1 damage_pending=0",
                "tile_probe tile_x=13 tile_y=22 tile=0x0025 object=0x0013 passable=0 standable=1",
                "",
            ]
        ),
    )


def write_ready_scanner_fixture(path: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=contact_scanner_runtime",
                "source=synthetic",
                "temp_copy=1",
                "visual_claim=0",
                "scenario=monster_contact_damage_live",
                "level=1",
                "runtime_cs=01ED",
                "runtime_ds=0F3C",
                "break ghidra=1000:5CB0 runtime=01ED:5CB0 label=contact_scanner_start",
                "break ghidra=1000:604F runtime=01ED:604F label=contact_scanner_end",
                "subject_actor slot=0 behavior=0 kind=0 state=0 x=0x0068 y=0x00a8 flags=0x0000 contact=0",
                "other_actor slot=3 behavior=4 kind=2 state=0 x=0x006a y=0x00a8 flags=0x0000 contact=0",
                "contact_scan subject_slot=0 other_slot=3 flags_before=0x0000 flags_after=0x0002 contact=1 player_contact=1 monster_contact=0 object_contact=0 damage_pending=1",
                "",
            ]
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check dispatch ready manifest promotion pipeline."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-ready-pipeline-") as tmp:
        base = Path(tmp)
        ready_candidate = base / "candidate" / "actor_update_candidate.txt"
        write_ready_actor_fixture(ready_candidate)

        child_manifest = base / "dispatch" / "actor_update_gate6" / "manifest.txt"
        write_text(
            child_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=actor_update_gate6",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x3p00",
                    "environment_preflight=skipped",
                    f"capture_status_x3p00=actor_contact_procmem=ok mode=capture target=actor_update_gate6 ghidra=1000:654E runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:654E freeze_observed=1 raw_dump=/tmp/ready/raw.txt candidate_fixture={ready_candidate}",
                    "",
                ]
            ),
        )
        dispatch_manifest = base / "dispatch" / "manifest.txt"
        write_text(
            dispatch_manifest,
            "\n".join(
                [
                    "capture=actor_dispatch_gate_sweep",
                    "asset_dir=/repo",
                    "targets=actor_update_gate6",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x3p00",
                    "environment_preflight=ok",
                    f"sweep_manifest_actor_update_gate6={child_manifest}",
                    "",
                ]
            ),
        )

        ready_manifest = base / "ready_manifest.txt"
        summary = run_tool(
            root,
            "summarize_actor_dispatch_gate_sweep.py",
            [
                str(dispatch_manifest),
                "--require-ready",
                "--require-environment-preflight",
                "--write-ready-manifest",
                str(ready_manifest),
            ],
        )
        for snippet in [
            "actor_dispatch_gate_sweep_summary=ok",
            "mode=dispatch",
            "ready_candidates=1",
            "actor_dispatch_gate_ready_manifest=ok",
            f"path={ready_manifest.resolve()}",
        ]:
            require(summary, snippet, "pipeline_summary")
        ready_text = ready_manifest.read_text(encoding="ascii")
        for snippet in [
            "source_environment_preflight=ok",
            "child_environment_preflights=skipped",
        ]:
            require(ready_text, snippet, "pipeline_ready_manifest")

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
            "run_actor_dispatch_ready_manifest.py",
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
        require(
            blocked,
            "child_environment_preflights=skipped",
            "blocked_source_environment_preflight",
        )
        cases += 1

        fake_oracle = make_fake_oracle(base / "fake")
        log_dir = base / "logs"
        result_manifest = base / "results" / "result_manifest.txt"
        runner = run_tool(
            root,
            "run_actor_dispatch_ready_manifest.py",
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
            "actor_dispatch_ready_manifest=ok mode=run",
            "ready_candidate index=0 target=actor_update_gate6",
            "status=ok returncode=0",
            "actor_dispatch_ready_result_manifest=ok",
            f"path={result_manifest.resolve()}",
        ]:
            require(runner, snippet, "pipeline_runner")

        result = run_tool(
            root,
            "summarize_actor_dispatch_ready_results.py",
            [
                str(result_manifest),
                "--require-success",
                "--require-executed",
                "--require-source-environment-preflight",
            ],
        )
        for snippet in [
            "actor_dispatch_ready_result_summary=ok",
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

        ready_scanner_candidate = base / "scanner_candidate" / "contact_scanner_candidate.txt"
        write_ready_scanner_fixture(ready_scanner_candidate)
        scanner_child_manifest = (
            base / "scanner_dispatch" / "contact_scanner_end" / "manifest.txt"
        )
        write_text(
            scanner_child_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=contact_scanner_end",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x0p50",
                    "environment_preflight=skipped",
                    f"capture_status_x0p50=actor_contact_procmem=ok mode=capture target=contact_scanner_end ghidra=1000:604F runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:604F freeze_observed=1 raw_dump=/tmp/scanner_ready/raw.txt candidate_fixture={ready_scanner_candidate}",
                    "",
                ]
            ),
        )
        scanner_dispatch_manifest = base / "scanner_dispatch" / "manifest.txt"
        write_text(
            scanner_dispatch_manifest,
            "\n".join(
                [
                    "capture=actor_dispatch_gate_sweep",
                    "asset_dir=/repo",
                    "targets=contact_scanner_end",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x0p50",
                    "environment_preflight=ok",
                    f"sweep_manifest_contact_scanner_end={scanner_child_manifest}",
                    "",
                ]
            ),
        )

        scanner_ready_manifest = base / "scanner_ready_manifest.txt"
        scanner_summary = run_tool(
            root,
            "summarize_actor_dispatch_gate_sweep.py",
            [
                str(scanner_dispatch_manifest),
                "--require-ready",
                "--require-environment-preflight",
                "--write-ready-manifest",
                str(scanner_ready_manifest),
            ],
        )
        for snippet in [
            "actor_dispatch_gate_sweep_summary=ok",
            "ready_candidates=1",
            "observed_targets=contact_scanner_end",
            "oracle=contact_scanner oracle_flag=--debug-contact-scanner-runtime-oracle",
            "actor_dispatch_gate_ready_manifest=ok",
            f"path={scanner_ready_manifest.resolve()}",
        ]:
            require(scanner_summary, snippet, "scanner_pipeline_summary")

        scanner_log_dir = base / "scanner_logs"
        scanner_result_manifest = base / "scanner_results" / "result_manifest.txt"
        scanner_runner = run_tool(
            root,
            "run_actor_dispatch_ready_manifest.py",
            [
                str(scanner_ready_manifest),
                "--require-source-environment-preflight",
                "--oracle-binary",
                str(fake_oracle),
                "--log-dir",
                str(scanner_log_dir),
                "--write-result-manifest",
                str(scanner_result_manifest),
                "--timeout-seconds",
                "5",
            ],
        )
        for snippet in [
            "actor_dispatch_ready_manifest=ok mode=run",
            "ready_candidate index=0 target=contact_scanner_end",
            "oracle=contact_scanner",
            "--debug-contact-scanner-runtime-oracle",
            "status=ok returncode=0",
            "actor_dispatch_ready_result_manifest=ok",
            f"path={scanner_result_manifest.resolve()}",
        ]:
            require(scanner_runner, snippet, "scanner_pipeline_runner")

        scanner_result = run_tool(
            root,
            "summarize_actor_dispatch_ready_results.py",
            [
                str(scanner_result_manifest),
                "--require-success",
                "--require-executed",
                "--require-source-environment-preflight",
            ],
        )
        for snippet in [
            "actor_dispatch_ready_result_summary=ok",
            "mode=run",
            "ready_candidates=1",
            "failures=0",
            "planned=0 ok=1 error=0 other=0",
            "executed_candidates=1",
            "candidate_result index=0 target=contact_scanner_end",
            "oracle_flag=--debug-contact-scanner-runtime-oracle",
        ]:
            require(scanner_result, snippet, "scanner_pipeline_result")
        cases += 1

        original_root = base / "original_root"
        original_fixture = write_original_fixture_tree(
            original_root,
            "actor_update_runtime_oracle_original_runner_unledgered.txt",
            runtime_ds="0F3C",
            include_ledger_entry=False,
        )
        bad_original_manifest = base / "bad_original_ready.txt"
        write_text(
            bad_original_manifest,
            "\n".join(
                [
                    "promotion=actor_dispatch_gate_ready_candidates",
                    "source_environment_preflight=ok",
                    "child_environment_preflights=skipped",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "candidate_0_target=actor_update_gate6",
                    "candidate_0_route=x3p00",
                    "candidate_0_ghidra=1000:654E",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0F3C",
                    "candidate_0_freeze_runtime=01ED:654E",
                    f"candidate_0_fixture={original_fixture}",
                    "candidate_0_oracle=actor_update",
                    "candidate_0_oracle_flag=--debug-actor-update-runtime-oracle",
                    "",
                ]
            ),
        )
        bad_original = run_tool(
            root,
            "run_actor_dispatch_ready_manifest.py",
            [str(bad_original_manifest), "--dry-run"],
            expect_success=False,
            env={"LEZAC_READY_RESULT_REPO_ROOT": str(original_root)},
        )
        require(
            bad_original,
            "candidate_0_fixture actor_update_runtime_oracle_original_runner_unledgered.txt "
            "is missing from runtime evidence ledger",
            "bad_original_runner_fixture",
        )
        cases += 1

    print(f"actor_dispatch_ready_pipeline_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
