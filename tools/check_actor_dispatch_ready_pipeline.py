#!/usr/bin/env python3
"""Check the actor dispatch ready-manifest pipeline end to end."""

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

    print(f"actor_dispatch_ready_pipeline_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
