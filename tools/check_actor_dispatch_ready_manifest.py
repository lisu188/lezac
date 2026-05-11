#!/usr/bin/env python3
"""Check actor dispatch ready-manifest runner behavior."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import shlex
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_ready(
    root: Path,
    args: list[str],
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "run_actor_dispatch_ready_manifest.py"),
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
            f"ready manifest runner failed with {result.returncode}: "
            f"{' '.join(args)}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"ready manifest runner unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check actor dispatch ready-manifest runner output."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    fixture = root / "tests" / "fixtures" / "dosbox" / (
        "actor_update_runtime_oracle_dispatch_gates_synthetic.txt"
    )
    scanner_fixture = root / "tests" / "fixtures" / "dosbox" / (
        "contact_scanner_runtime_oracle_synthetic.txt"
    )
    quoted_fixture = shlex.quote(str(fixture))
    quoted_scanner_fixture = shlex.quote(str(scanner_fixture))
    cases = 0

    with tempfile.TemporaryDirectory(prefix="lezac-ready-manifest-") as tmp:
        base = Path(tmp)
        ready_manifest = base / "ready" / "manifest.txt"
        write_text(
            ready_manifest,
            "\n".join(
                [
                    "promotion=actor_dispatch_gate_ready_candidates",
                    "source_manifest=/tmp/source/manifest.txt",
                    "oracle_binary=/tmp/lezac cpp/lezac_cpp",
                    "ready_candidates=2",
                    "candidate_0_target=actor_update_gate6",
                    "candidate_0_route=x3p00",
                    "candidate_0_ghidra=1000:654E",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0F3C",
                    "candidate_0_freeze_runtime=01ED:654E",
                    f"candidate_0_fixture={fixture}",
                    "candidate_0_oracle=actor_update",
                    "candidate_0_oracle_flag=--debug-actor-update-runtime-oracle",
                    "candidate_1_target=contact_scanner_start",
                    "candidate_1_route=x0p50",
                    "candidate_1_ghidra=1000:5CB0",
                    "candidate_1_runtime_cs=01ED",
                    "candidate_1_runtime_ds=0F3C",
                    "candidate_1_freeze_runtime=01ED:5CB0",
                    f"candidate_1_fixture={scanner_fixture}",
                    "candidate_1_oracle=contact_scanner",
                    "candidate_1_oracle_flag=--debug-contact-scanner-runtime-oracle",
                    "",
                ]
            ),
        )

        dry_result_manifest = base / "ready" / "dry_result_manifest.txt"
        dry = run_ready(
            root,
            [
                str(ready_manifest),
                "--dry-run",
                "--write-result-manifest",
                str(dry_result_manifest),
            ],
        )
        for snippet in [
            "actor_dispatch_ready_manifest=ok mode=dry_run",
            "ready_candidates=2",
            "oracle_binary=/tmp/lezac cpp/lezac_cpp",
            "actor_dispatch_ready_result_manifest=ok",
            f"path={dry_result_manifest.resolve()}",
            "ready_candidate index=0 target=actor_update_gate6",
            "ghidra=1000:654E runtime_cs=01ED runtime_ds=0F3C",
            "oracle=actor_update oracle_flag=--debug-actor-update-runtime-oracle",
            f"fixture={fixture}",
            "command='/tmp/lezac cpp/lezac_cpp' "
            f"--debug-actor-update-runtime-oracle {quoted_fixture}",
            "ready_candidate index=1 target=contact_scanner_start",
            "oracle=contact_scanner oracle_flag=--debug-contact-scanner-runtime-oracle",
            f"command='/tmp/lezac cpp/lezac_cpp' "
            f"--debug-contact-scanner-runtime-oracle {quoted_scanner_fixture}",
        ]:
            require(dry, snippet, "dry_run")
        cases += 1

        dry_result_text = dry_result_manifest.read_text(encoding="utf-8")
        for snippet in [
            "result=actor_dispatch_ready_manifest",
            "mode=dry_run",
            f"source_ready_manifest={ready_manifest.resolve()}",
            "oracle_binary=/tmp/lezac cpp/lezac_cpp",
            "ready_candidates=2",
            "failures=0",
            "candidate_0_target=actor_update_gate6",
            "candidate_0_status=planned",
            "candidate_0_returncode=not_run",
            "candidate_0_log=none",
            "candidate_1_target=contact_scanner_start",
            f"candidate_1_command='/tmp/lezac cpp/lezac_cpp' "
            f"--debug-contact-scanner-runtime-oracle {quoted_scanner_fixture}",
        ]:
            require(dry_result_text, snippet, "dry_result_manifest")
        cases += 1

        override = run_ready(
            root,
            [
                str(ready_manifest),
                "--dry-run",
                "--oracle-binary",
                "./build/lezac_cpp",
            ],
        )
        require(
            override,
            "command=./build/lezac_cpp --debug-actor-update-runtime-oracle "
            f"{quoted_fixture}",
            "override_binary",
        )
        cases += 1

        directory_input = run_ready(root, [str(ready_manifest.parent), "--dry-run"])
        require(
            directory_input,
            f"manifest={ready_manifest.resolve()}",
            "directory_input",
        )
        require(directory_input, "ready_candidates=2", "directory_input")
        cases += 1

        fake_oracle = make_fake_oracle(base / "fake")
        log_dir = base / "logs"
        live_result_manifest = base / "logs" / "result_manifest.txt"
        live = run_ready(
            root,
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
            "actor_dispatch_ready_manifest=ok mode=run",
            "ready_candidate index=0 target=actor_update_gate6",
            "status=ok returncode=0",
            "ready_candidate index=1 target=contact_scanner_start",
            "actor_dispatch_ready_result_manifest=ok",
            f"path={live_result_manifest.resolve()}",
            f"command={shlex.quote(str(fake_oracle))} "
            f"--debug-contact-scanner-runtime-oracle {quoted_scanner_fixture}",
        ]:
            require(live, snippet, "live_fake_oracle")
        for index, target, flag in [
            (0, "actor_update_gate6", "--debug-actor-update-runtime-oracle"),
            (1, "contact_scanner_start", "--debug-contact-scanner-runtime-oracle"),
        ]:
            log_text = (log_dir / f"candidate_{index}_{target}.log").read_text(
                encoding="utf-8"
            )
            require(log_text, f"fake_oracle flag={flag}", "live_fake_oracle_log")
        live_result_text = live_result_manifest.read_text(encoding="utf-8")
        for snippet in [
            "result=actor_dispatch_ready_manifest",
            "mode=run",
            f"source_ready_manifest={ready_manifest.resolve()}",
            f"oracle_binary={fake_oracle}",
            "ready_candidates=2",
            "failures=0",
            "candidate_0_status=ok",
            "candidate_0_returncode=0",
            f"candidate_0_log={log_dir / 'candidate_0_actor_update_gate6.log'}",
            "candidate_1_status=ok",
            "candidate_1_returncode=0",
            f"candidate_1_log={log_dir / 'candidate_1_contact_scanner_start.log'}",
        ]:
            require(live_result_text, snippet, "live_result_manifest")
        cases += 1

        zero_manifest = base / "zero" / "manifest.txt"
        write_text(
            zero_manifest,
            "\n".join(
                [
                    "promotion=actor_dispatch_gate_ready_candidates",
                    "source_manifest=/tmp/source/manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=0",
                    "",
                ]
            ),
        )
        zero = run_ready(root, [str(zero_manifest), "--dry-run"])
        require(zero, "ready_candidates=0", "zero_candidates")
        cases += 1

        bad_promotion = base / "bad-promotion" / "manifest.txt"
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
        bad = run_ready(root, [str(bad_promotion), "--dry-run"], False)
        require(bad, "actor_dispatch_ready_manifest=error", "bad_promotion")
        require(bad, "unsupported promotion", "bad_promotion")
        cases += 1

        bad_count = base / "bad-count" / "manifest.txt"
        write_text(
            bad_count,
            "\n".join(
                [
                    "promotion=actor_dispatch_gate_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=two",
                    "",
                ]
            ),
        )
        count = run_ready(root, [str(bad_count), "--dry-run"], False)
        require(count, "invalid ready_candidates value", "bad_count")
        cases += 1

        missing_field = base / "missing-field" / "manifest.txt"
        write_text(
            missing_field,
            "\n".join(
                [
                    "promotion=actor_dispatch_gate_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "candidate_0_target=actor_update_gate6",
                    "",
                ]
            ),
        )
        missing = run_ready(root, [str(missing_field), "--dry-run"], False)
        require(
            missing,
            "missing required manifest field: candidate_0_route",
            "missing_field",
        )
        cases += 1

        missing_fixture = base / "missing-fixture" / "manifest.txt"
        write_text(
            missing_fixture,
            "\n".join(
                [
                    "promotion=actor_dispatch_gate_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "candidate_0_target=actor_update_gate6",
                    "candidate_0_route=x3p00",
                    "candidate_0_ghidra=1000:654E",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0F3C",
                    "candidate_0_freeze_runtime=01ED:654E",
                    "candidate_0_fixture=missing_candidate.txt",
                    "candidate_0_oracle=actor_update",
                    "candidate_0_oracle_flag=--debug-actor-update-runtime-oracle",
                    "",
                ]
            ),
        )
        missing_fixture_result = run_ready(
            root, [str(missing_fixture), "--dry-run"], False
        )
        require(
            missing_fixture_result,
            "candidate fixture not found",
            "missing_fixture",
        )
        missing_fixture_allowed = run_ready(
            root,
            [
                str(missing_fixture),
                "--dry-run",
                "--allow-missing-fixtures",
            ],
        )
        require(
            missing_fixture_allowed,
            "ready_candidate index=0 target=actor_update_gate6",
            "missing_fixture_allowed",
        )
        cases += 1

        bad_oracle_flag = base / "bad-oracle-flag" / "manifest.txt"
        write_text(
            bad_oracle_flag,
            "\n".join(
                [
                    "promotion=actor_dispatch_gate_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "candidate_0_target=contact_scanner_start",
                    "candidate_0_route=x0p50",
                    "candidate_0_ghidra=1000:5CB0",
                    "candidate_0_runtime_cs=01ED",
                    "candidate_0_runtime_ds=0F3C",
                    "candidate_0_freeze_runtime=01ED:5CB0",
                    f"candidate_0_fixture={scanner_fixture}",
                    "candidate_0_oracle=contact_scanner",
                    "candidate_0_oracle_flag=--debug-actor-update-runtime-oracle",
                    "",
                ]
            ),
        )
        flag = run_ready(root, [str(bad_oracle_flag), "--dry-run"], False)
        require(flag, "does not match", "bad_oracle_flag")
        require(flag, "expected '--debug-contact-scanner-runtime-oracle'", "bad_oracle_flag")
        cases += 1

        missing_fixture_live = run_ready(
            root,
            [
                str(missing_fixture),
                "--allow-missing-fixtures",
            ],
            False,
        )
        require(
            missing_fixture_live,
            "--allow-missing-fixtures requires --dry-run",
            "missing_fixture_live",
        )
        cases += 1

        repo_output = run_ready(
            root,
            [
                str(ready_manifest),
                "--dry-run",
                "--write-result-manifest",
                str(root / "actor-dispatch-ready-result.txt"),
            ],
            False,
        )
        require(
            repo_output,
            "--write-result-manifest must be outside the repository",
            "repo_output",
        )
        cases += 1

    print(f"actor_dispatch_ready_manifest_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
