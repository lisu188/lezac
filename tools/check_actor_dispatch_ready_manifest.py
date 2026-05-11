#!/usr/bin/env python3
"""Check actor dispatch ready-manifest runner behavior."""

from __future__ import annotations

import argparse
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

        dry = run_ready(root, [str(ready_manifest), "--dry-run"])
        for snippet in [
            "actor_dispatch_ready_manifest=ok mode=dry_run",
            "ready_candidates=2",
            "oracle_binary=/tmp/lezac cpp/lezac_cpp",
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

    print(f"actor_dispatch_ready_manifest_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
