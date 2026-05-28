#!/usr/bin/env python3
"""Check lane-write ready-manifest runner behavior."""

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


def run_ready(root: Path, args: list[str], expect_success: bool = True) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "run_lane_write_ready_manifest.py"),
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
                "instrumented_lane_write_cs_offset=0xf080",
                "instrumented_lane_write_kind=forward",
                "instrumented_lane_write_target=debris",
                "instrumented_lane_write_scratch_present=1",
                "instrumented_lane_write_output=0x0035",
                "instrumented_lane_write_di=0x0898",
                "instrumented_lane_write_tag=0x4ee8",
                "instrumented_lane_write_active_count=0x0001",
                "instrumented_lane_write_loop_index=0x0001",
                "instrumented_lane_write_result_local=0x0035",
                "runtime_freeze_patch_applied=1",
                "runtime_freeze_old_bytes=889597",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
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
                "candidate_0_lane_write_kind=forward",
                "candidate_0_lane_write_target=debris",
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
        description="Check lane-write ready-manifest runner output."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-lane-write-ready-manifest-") as tmp:
        base = Path(tmp)
        fixture = base / "fixture" / "lane_write.txt"
        write_fixture(fixture)
        quoted_fixture = shlex.quote(str(fixture))
        ready_manifest = base / "ready" / "manifest.txt"
        write_ready_manifest(ready_manifest, fixture)

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
            "lane_write_ready_manifest=ok mode=dry_run",
            "source_environment_preflight=ok",
            "ready_candidates=1",
            "oracle_binary=/tmp/lezac cpp/lezac_cpp",
            "lane_write_ready_result_manifest=ok",
            f"path={dry_result_manifest.resolve()}",
            "ready_candidate index=0 route=x2p00_c0p50 offset=3d2d",
            "offset_address=1000:3D2D kind=forward target=debris",
            "runtime_cs=01ED runtime_ds=0C8F",
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
            "oracle_binary=/tmp/lezac cpp/lezac_cpp",
            "ready_candidates=1",
            "failures=0",
            "candidate_0_route=x2p00_c0p50",
            "candidate_0_offset_label=3d2d",
            "candidate_0_offset_address=1000:3D2D",
            "candidate_0_lane_write_kind=forward",
            "candidate_0_lane_write_target=debris",
            "candidate_0_status=planned",
            "candidate_0_returncode=not_run",
            "candidate_0_log=none",
            f"candidate_0_command='/tmp/lezac cpp/lezac_cpp' "
            f"--debug-explosion-playback-oracle {quoted_fixture}",
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
            "command=./build/lezac_cpp --debug-explosion-playback-oracle "
            f"{quoted_fixture}",
            "override_binary",
        )
        cases += 1

        directory_input = run_ready(root, [str(ready_manifest.parent), "--dry-run"])
        require(directory_input, f"manifest={ready_manifest.resolve()}", "directory")
        require(directory_input, "ready_candidates=1", "directory")
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
            "lane_write_ready_manifest=ok mode=run",
            "ready_candidate index=0 route=x2p00_c0p50",
            "kind=forward target=debris",
            "status=ok returncode=0",
            "lane_write_ready_result_manifest=ok",
            f"path={live_result_manifest.resolve()}",
            f"command={shlex.quote(str(fake_oracle))} "
            f"--debug-explosion-playback-oracle {quoted_fixture}",
        ]:
            require(live, snippet, "live_fake_oracle")
        log_path = log_dir / "candidate_0_3d2d_x2p00_c0p50.log"
        require(
            log_path.read_text(encoding="utf-8"),
            "fake_oracle flag=--debug-explosion-playback-oracle",
            "live_fake_oracle_log",
        )
        cases += 1

        zero_manifest = base / "zero" / "manifest.txt"
        write_text(
            zero_manifest,
            "\n".join(
                [
                    "promotion=lane_write_ready_candidates",
                    "source_manifest=/tmp/source/manifest.txt",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=0",
                    "",
                ]
            ),
        )
        zero = run_ready(root, [str(zero_manifest), "--dry-run"])
        require(zero, "source_environment_preflight=unknown", "zero")
        require(zero, "ready_candidates=0", "zero")
        cases += 1

        preflight_required = run_ready(
            root,
            [str(ready_manifest), "--dry-run", "--require-source-environment-preflight"],
        )
        require(preflight_required, "source_environment_preflight=ok", "preflight")
        cases += 1

        zero_preflight_required = run_ready(
            root,
            [
                str(zero_manifest),
                "--dry-run",
                "--require-source-environment-preflight",
            ],
            False,
        )
        require(
            zero_preflight_required,
            "reason=source_environment_preflight_not_ok",
            "zero_preflight",
        )
        require(
            zero_preflight_required,
            "source_environment_preflight=unknown",
            "zero_preflight",
        )
        cases += 1

        bad_promotion = base / "bad-promotion" / "manifest.txt"
        write_text(
            bad_promotion,
            "\n".join(
                [
                    "promotion=lane_result_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=0",
                    "",
                ]
            ),
        )
        bad = run_ready(root, [str(bad_promotion), "--dry-run"], False)
        require(bad, "lane_write_ready_manifest=error", "bad_promotion")
        require(bad, "unsupported promotion", "bad_promotion")
        cases += 1

        bad_count = base / "bad-count" / "manifest.txt"
        write_text(
            bad_count,
            "\n".join(
                [
                    "promotion=lane_write_ready_candidates",
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
                    "promotion=lane_write_ready_candidates",
                    "oracle_binary=./build/lezac_cpp",
                    "ready_candidates=1",
                    "candidate_0_route=x2p00",
                    "",
                ]
            ),
        )
        missing = run_ready(root, [str(missing_field), "--dry-run"], False)
        require(
            missing,
            "missing required manifest field: candidate_0_fixture",
            "missing_field",
        )
        cases += 1

        missing_fixture = base / "missing-fixture" / "manifest.txt"
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
                    "candidate_0_fixture=missing_candidate.txt",
                    "candidate_0_oracle=explosion_playback",
                    "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
                    "",
                ]
            ),
        )
        missing_fixture_result = run_ready(
            root, [str(missing_fixture), "--dry-run"], False
        )
        require(missing_fixture_result, "candidate fixture not found", "missing_fixture")
        missing_fixture_allowed = run_ready(
            root,
            [str(missing_fixture), "--dry-run", "--allow-missing-fixtures"],
        )
        require(
            missing_fixture_allowed,
            "ready_candidate index=0 route=x2p00",
            "missing_fixture_allowed",
        )
        cases += 1

        duplicate_fixture_path = base / "fixture" / "lane_write_duplicate.txt"
        write_text(
            duplicate_fixture_path,
            "temp_copy=1\nvisual_claim=0\nruntime_cs=01ED\n"
            "runtime_ds=0C8F\nruntime_ds=0C8F\n",
        )
        duplicate_fixture_manifest = base / "duplicate-fixture" / "manifest.txt"
        write_ready_manifest(duplicate_fixture_manifest, duplicate_fixture_path)
        duplicate_fixture = run_ready(
            root,
            [str(duplicate_fixture_manifest), "--dry-run"],
            False,
        )
        require(
            duplicate_fixture,
            "duplicate fixture field: runtime_ds",
            "duplicate_fixture",
        )
        cases += 1

        bad_oracle = base / "bad-oracle" / "manifest.txt"
        write_text(
            bad_oracle,
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
                    "candidate_0_oracle=actor_update",
                    "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
                    "",
                ]
            ),
        )
        oracle = run_ready(root, [str(bad_oracle), "--dry-run"], False)
        require(oracle, "unsupported value", "bad_oracle")
        require(oracle, "expected 'explosion_playback'", "bad_oracle")
        cases += 1

        bad_oracle_flag = base / "bad-oracle-flag" / "manifest.txt"
        write_text(
            bad_oracle_flag,
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
        flag = run_ready(root, [str(bad_oracle_flag), "--dry-run"], False)
        require(flag, "does not match", "bad_oracle_flag")
        require(flag, "--debug-explosion-playback-oracle", "bad_oracle_flag")
        cases += 1

        missing_fixture_live = run_ready(
            root,
            [str(missing_fixture), "--allow-missing-fixtures"],
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
                str(root / "lane-write-ready-result.txt"),
            ],
            False,
        )
        require(
            repo_output,
            "--write-result-manifest must be outside the repository",
            "repo_output",
        )
        cases += 1

        extra_candidate_manifest = base / "extra-candidate" / "manifest.txt"
        write_text(
            extra_candidate_manifest,
            ready_manifest.read_text(encoding="ascii").replace(
                "ready_candidates=1", "ready_candidates=0"
            ),
        )
        extra_candidate = run_ready(
            root,
            [str(extra_candidate_manifest), "--dry-run"],
            False,
        )
        require(
            extra_candidate,
            "candidate index outside ready_candidates: 0 ready_candidates=0",
            "extra_candidate",
        )
        cases += 1

        duplicate_field_manifest = base / "duplicate-field" / "manifest.txt"
        write_text(
            duplicate_field_manifest,
            ready_manifest.read_text(encoding="ascii")
            + "candidate_0_fixture=/tmp/other_lane_write.txt\n",
        )
        duplicate_field = run_ready(
            root,
            [str(duplicate_field_manifest), "--dry-run"],
            False,
        )
        require(
            duplicate_field,
            "duplicate manifest field: candidate_0_fixture",
            "duplicate_field",
        )
        cases += 1

    print(f"lane_write_ready_manifest_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
