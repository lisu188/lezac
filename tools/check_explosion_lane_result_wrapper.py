#!/usr/bin/env python3
"""Exercise lane-result capture wrapper status output without DOSBox."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


EXPECTED_RESULT_TAIL = "8b46f63b46f075c58a46f3c47e04268805c9c20600"


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_wrapper(root: Path, args: list[str], expect_success: bool = True) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "capture_original_lane_result_runtime.py"),
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
            f"wrapper command failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"wrapper command unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def require_not(text: str, snippet: str, case: str) -> None:
    if snippet in text:
        raise RuntimeError(f"{case} unexpectedly contained {snippet!r}\n{text}")


def check_success(text: str, case: str, snippets: list[str]) -> None:
    for snippet in [
        "lane_result_capture_orchestrator=ok",
        "result_tail=1",
        f"result_tail_bytes={EXPECTED_RESULT_TAIL}",
        "wrong_offset_guard=1",
        *snippets,
    ]:
        require(text, snippet, case)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-result wrapper dry-run/preflight status output."
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
        help="repository root containing LEZAC.EXE",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    out_base = Path(tempfile.gettempdir()) / "lezac-lane-result-wrapper-check"
    cpp_exe = root / "build" / "lezac_cpp"

    cases = 0

    check_success(
        run_wrapper(root, ["--preflight-only", "--asset-dir", str(root)]),
        "preflight",
        ["mode=preflight"],
    )
    cases += 1

    check_success(
        run_wrapper(root, [str(root), "--preflight-only"]),
        "preflight_positional",
        ["mode=preflight"],
    )
    cases += 1

    default_dry = run_wrapper(
        root,
        [str(out_base / "default"), str(root), "--dry-run", "--skip-oracle"],
    )
    check_success(
        default_dry,
        "default_dry_run",
        [
            "mode=dry_run",
            "offsets=2 capture_commands=2 oracle_commands=0",
            "offset_labels=3d3f,3ed3",
            "offset_addresses=1000:3D3F,1000:3ED3",
            "capture_command_3d3f=",
            "capture_command_3ed3=",
        ],
    )
    require_not(default_dry, "oracle_command_", "default_dry_run")
    cases += 1

    with_oracle = run_wrapper(
        root,
        [
            str(out_base / "with-oracle"),
            str(root),
            "--dry-run",
            "--cpp-exe",
            str(cpp_exe),
        ],
    )
    check_success(
        with_oracle,
        "with_oracle",
        [
            "oracle_commands=2",
            "oracle_command_3d3f=",
            "oracle_command_3ed3=",
        ],
    )
    cases += 1

    forward = run_wrapper(
        root,
        [
            str(out_base / "forward"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "forward",
        ],
    )
    check_success(
        forward,
        "forward",
        [
            "offsets=1 capture_commands=1 oracle_commands=0",
            "offset_labels=3d3f",
            "offset_addresses=1000:3D3F",
        ],
    )
    cases += 1

    reverse = run_wrapper(
        root,
        [
            str(out_base / "reverse"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "reverse",
        ],
    )
    check_success(
        reverse,
        "reverse",
        [
            "offsets=1 capture_commands=1 oracle_commands=0",
            "offset_labels=3ed3",
            "offset_addresses=1000:3ED3",
        ],
    )
    cases += 1

    raw_reverse = run_wrapper(
        root,
        [
            str(out_base / "raw-reverse"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "3ED3",
        ],
    )
    check_success(
        raw_reverse,
        "raw_reverse",
        [
            "offsets=1 capture_commands=1 oracle_commands=0",
            "offset_labels=3ed3",
            "offset_addresses=1000:3ED3",
        ],
    )
    cases += 1

    mixed = run_wrapper(
        root,
        [
            str(out_base / "mixed"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "reverse",
            "--offset",
            "forward",
        ],
    )
    check_success(
        mixed,
        "mixed",
        [
            "offsets=2 capture_commands=2 oracle_commands=0",
            "offset_labels=3ed3,3d3f",
            "offset_addresses=1000:3ED3,1000:3D3F",
        ],
    )
    cases += 1

    duplicate = run_wrapper(
        root,
        [
            str(out_base / "duplicate"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "3D3F",
            "--offset",
            "1000:3D3F",
        ],
    )
    check_success(
        duplicate,
        "duplicate",
        [
            "offsets=1 capture_commands=1 oracle_commands=0",
            "offset_labels=3d3f",
            "offset_addresses=1000:3D3F",
        ],
    )
    cases += 1

    timing = run_wrapper(
        root,
        [
            str(out_base / "timing"),
            str(root),
            "--dry-run",
            "--skip-oracle",
            "--offset",
            "forward",
            "--runtime-freeze-after-bomb-seconds",
            "0.125",
            "--level-start-seconds",
            "2.25",
            "--right-hold-seconds",
            "3.5",
            "--sample-seconds",
            "6.75",
            "--sample-interval",
            "0.015",
            "--route-state-interval",
            "0.5",
            "--route-step",
            "x:1.25",
            "--route-step",
            "Left:0.50",
            "--tail-freeze-check-seconds",
            "1.25",
        ],
    )
    check_success(
        timing,
        "timing",
        [
            "offsets=1 capture_commands=1 oracle_commands=0",
            "--runtime-freeze-after-bomb-seconds 0.125",
            "--level-start-seconds 2.25",
            "--right-hold-seconds 3.5",
            "--sample-seconds 6.75",
            "--sample-interval 0.015",
            "--route-state-interval 0.5",
            "--route-step x:1.25",
            "--route-step Left:0.50",
            "--tail-freeze-check-seconds 1.25",
        ],
    )
    cases += 1

    require(
        run_wrapper(
            root,
            [
                str(out_base / "bad-offset"),
                str(root),
                "--dry-run",
                "--skip-oracle",
                "--offset",
                "sideways",
            ],
            expect_success=False,
        ),
        "offset must be one of forward, reverse",
        "bad_offset",
    )
    cases += 1

    require(
        run_wrapper(
            root,
            [
                str(root / "lane-result-runtime-refusal"),
                str(root),
                "--dry-run",
                "--skip-oracle",
            ],
            expect_success=False,
        ),
        "choose an output directory outside the repository",
        "repo_output_refusal",
    )
    cases += 1

    require(
        run_wrapper(
            root,
            [str(out_base / "requires-approval"), str(root)],
            expect_success=False,
        ),
        "refusing runtime capture without --approve-procmem",
        "requires_approval",
    )
    cases += 1

    print(f"lane_result_wrapper_output=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
