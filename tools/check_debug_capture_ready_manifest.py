#!/usr/bin/env python3
"""Check debug-capture ready-manifest runner behavior."""

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
    write_contact_ready,
    write_text,
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


def make_fake_oracle(base: Path) -> Path:
    if os.name == "nt":
        fake = base / "fake_oracle.cmd"
        write_text(
            fake,
            "\r\n".join(
                [
                    "@echo off",
                    "echo fake_oracle flag=%1 fixture=%2",
                    'if "%1"=="--debug-behavior4-runtime-oracle" exit /b 0',
                    'if "%1"=="--debug-actor-update-runtime-oracle" exit /b 0',
                    'if "%1"=="--debug-contact-scanner-runtime-oracle" exit /b 0',
                    'if "%1"=="--debug-visual-table-oracle" exit /b 0',
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


def make_ready_manifest(root: Path, batch_dir: Path, ready_manifest: Path) -> str:
    write_actor_ready(batch_dir)
    return run_tool(
        root,
        "summarize_debug_capture_batch.py",
        [
            str(batch_dir),
            "--write-ready-manifest",
            str(ready_manifest),
        ],
    )


def replace_text(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="ascii")
    path.write_text(text.replace(old, new), encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check run_debug_capture_ready_manifest.py behavior."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-debug-ready-") as tmp:
        base = Path(tmp)
        ready_manifest = base / "ready" / "ready_manifest.txt"
        make_ready_manifest(root, base / "batch", ready_manifest)

        fake_oracle = make_fake_oracle(base / "fake")
        dry_result = base / "results" / "dry_result.txt"
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
        for snippet in [
            "debug_capture_ready_manifest=ok mode=dry_run",
            "ready_candidates=1",
            "debug_capture_ready_candidate index=0",
            "capture=actor_update_runtime",
            "status=planned",
            "returncode=not_run",
            "debug_capture_ready_result_manifest=ok",
            f"path={dry_result.resolve()}",
        ]:
            require(dry, snippet, "dry_run")
        dry_text = dry_result.read_text(encoding="utf-8")
        require(dry_text, "result=debug_capture_ready_manifest", "dry_result")
        require(dry_text, "candidate_0_status=planned", "dry_result")
        cases += 1

        visual_ready_manifest = base / "visual-ready" / "ready_manifest.txt"
        run_tool(
            root,
            "summarize_debug_capture_batch.py",
            [
                str(write_visual_table_ready(base / "visual-batch")),
                "--write-ready-manifest",
                str(visual_ready_manifest),
            ],
        )
        visual_dry = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [
                str(visual_ready_manifest),
                "--dry-run",
                "--oracle-binary",
                str(fake_oracle),
            ],
        )
        for snippet in [
            "debug_capture_ready_manifest=ok mode=dry_run",
            "ready_candidates=1",
            "capture=visual_table",
            "scenario=state2_death_table_consumption",
            "oracle=visual_table",
            "command=",
            "--debug-visual-table-oracle",
        ]:
            require(visual_dry, snippet, "visual_table_dry_run")
        cases += 1

        behavior_ready_manifest = base / "behavior-ready" / "ready_manifest.txt"
        run_tool(
            root,
            "summarize_debug_capture_batch.py",
            [
                str(write_behavior4_ready(base / "behavior-batch")),
                "--write-ready-manifest",
                str(behavior_ready_manifest),
            ],
        )
        behavior_dry = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [
                str(behavior_ready_manifest),
                "--dry-run",
                "--oracle-binary",
                str(fake_oracle),
            ],
        )
        for snippet in [
            "debug_capture_ready_manifest=ok mode=dry_run",
            "ready_candidates=1",
            "capture=behavior4_runtime",
            "scenario=monster_behavior4_target_selection",
            "oracle=behavior4",
            "command=",
            "--debug-behavior4-runtime-oracle",
        ]:
            require(behavior_dry, snippet, "behavior4_dry_run")
        cases += 1

        contact_ready_manifest = base / "contact-ready" / "ready_manifest.txt"
        run_tool(
            root,
            "summarize_debug_capture_batch.py",
            [
                str(write_contact_ready(base / "contact-batch")),
                "--write-ready-manifest",
                str(contact_ready_manifest),
            ],
        )
        contact_dry = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [
                str(contact_ready_manifest),
                "--dry-run",
                "--oracle-binary",
                str(fake_oracle),
            ],
        )
        for snippet in [
            "debug_capture_ready_manifest=ok mode=dry_run",
            "ready_candidates=1",
            "capture=contact_scanner_runtime",
            "scenario=monster_contact_damage_live",
            "oracle=contact_scanner",
            "command=",
            "--debug-contact-scanner-runtime-oracle",
        ]:
            require(contact_dry, snippet, "contact_scanner_dry_run")
        cases += 1

        run_result = base / "results" / "run_result.txt"
        logs = base / "logs"
        run = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [
                str(ready_manifest),
                "--oracle-binary",
                str(fake_oracle),
                "--log-dir",
                str(logs),
                "--write-result-manifest",
                str(run_result),
                "--timeout-seconds",
                "5",
                "--require-source-environment-preflight",
            ],
        )
        for snippet in [
            "debug_capture_ready_manifest=ok mode=run",
            "status=ok",
            "returncode=0",
            "debug_capture_ready_result_manifest=ok",
            f"path={run_result.resolve()}",
        ]:
            require(run, snippet, "run")
        run_text = run_result.read_text(encoding="utf-8")
        require(run_text, "candidate_0_status=ok", "run_result")
        require(run_text, "candidate_0_returncode=0", "run_result")
        cases += 1

        missing_fixture_manifest = base / "ready" / "missing_fixture.txt"
        missing_fixture_manifest.write_text(
            ready_manifest.read_text(encoding="ascii").replace(
                "candidate_0_fixture=", "candidate_0_fixture=/tmp/missing/"
            ),
            encoding="ascii",
        )
        missing = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [str(missing_fixture_manifest)],
            expect_success=False,
        )
        require(missing, "reason=candidate fixture not found", "missing_fixture")
        cases += 1

        env_manifest = base / "ready" / "bad_environment.txt"
        env_manifest.write_text(ready_manifest.read_text(encoding="ascii"), encoding="ascii")
        replace_text(
            env_manifest,
            "candidate_0_environment_preflight=ok",
            "candidate_0_environment_preflight=dry_run",
        )
        env = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [str(env_manifest), "--require-source-environment-preflight"],
            expect_success=False,
        )
        require(env, "candidate_0_environment_preflight='dry_run'", "bad_environment")
        cases += 1

        bad_flag_manifest = base / "ready" / "bad_flag.txt"
        bad_flag_manifest.write_text(
            ready_manifest.read_text(encoding="ascii"), encoding="ascii"
        )
        replace_text(
            bad_flag_manifest,
            "candidate_0_oracle_flag=--debug-actor-update-runtime-oracle",
            "candidate_0_oracle_flag=--debug-contact-scanner-runtime-oracle",
        )
        bad_flag = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [str(bad_flag_manifest)],
            expect_success=False,
        )
        require(bad_flag, "does not match candidate_0_oracle", "bad_flag")
        cases += 1

        missing_fixture_live = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [
                str(missing_fixture_manifest),
                "--allow-missing-fixtures",
            ],
            expect_success=False,
        )
        require(
            missing_fixture_live,
            "--allow-missing-fixtures requires --dry-run",
            "missing_fixture_live",
        )
        cases += 1

        extra_candidate_manifest = base / "ready" / "extra_candidate.txt"
        extra_candidate_manifest.write_text(
            ready_manifest.read_text(encoding="ascii").replace(
                "ready_candidates=1", "ready_candidates=0"
            ),
            encoding="ascii",
        )
        extra_candidate = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [str(extra_candidate_manifest), "--dry-run"],
            expect_success=False,
        )
        require(
            extra_candidate,
            "candidate index outside ready_candidates: 0 ready_candidates=0",
            "extra_candidate",
        )
        cases += 1

        duplicate_field_manifest = base / "ready" / "duplicate_field.txt"
        duplicate_field_manifest.write_text(
            ready_manifest.read_text(encoding="ascii")
            + "candidate_0_fixture=/tmp/other_debug_capture.txt\n",
            encoding="ascii",
        )
        duplicate_field = run_tool(
            root,
            "run_debug_capture_ready_manifest.py",
            [str(duplicate_field_manifest), "--dry-run"],
            expect_success=False,
        )
        require(
            duplicate_field,
            "duplicate manifest field: candidate_0_fixture",
            "duplicate_field",
        )
        cases += 1

    print(f"debug_capture_ready_manifest_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
