#!/usr/bin/env python3
"""Check the original-vs-C++ frame comparison workflow contract."""

from __future__ import annotations

import argparse
from pathlib import Path


WRAPPER = Path("tools/compare_original_cpp_frames.sh")
CPP_CAPTURE = Path("tools/capture_cpp_frames.sh")
ORIGINAL_CAPTURE = Path("tools/capture_original_dosbox_frames.sh")
COMPARATOR = Path("tools/frame_compare.py")
DOC = Path("docs/recovery/frame_comparison.md")
CMAKE = Path("CMakeLists.txt")

WRAPPER_SNIPPETS = [
    "set -euo pipefail",
    "choose an output directory outside the repository",
    "capture_cpp_frames.sh",
    "capture_original_dosbox_frames.sh",
    "frame_compare.py",
    "frame_compare_summary.txt",
    "manifest.txt",
    "diff_dir",
    "missing_original",
    "level1_bomb_route|monster_bomb_reward",
    "frame_compare_bundle=",
]

ORIGINAL_CAPTURE_SNIPPETS = [
    "preflight_original_evidence_environment.py",
    "--require-frame-capture",
    "--probe-wsl",
    "--require-wsl-bash-on-windows",
    "environment_preflight_command=",
    "environment_preflight_log=",
    "environment_preflight_exit=",
    "environment_preflight=ok",
    "environment_preflight=error",
    "LEZAC_ORIGINAL_FRAME_CAPTURE_SKIP_ENVIRONMENT_PREFLIGHT",
    "original_frame_capture=error",
]

DOC_SNIPPETS = [
    "tools/compare_original_cpp_frames.sh <out-dir> [asset-dir] [scenario]",
    "/tmp/lezac-frame-compare",
    "C++ frames",
    "DOSBox-original frames",
    "PPM diffs",
    "frame_compare_summary.txt",
    "Missing original frames should remain visible",
    "visually inspected",
    "environment_preflight.log",
    "wsl_bash_reason=no_default_distro",
]


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read(root: Path, path: Path) -> str:
    full_path = root / path
    if not full_path.exists():
        raise RuntimeError(f"missing {path}")
    return full_path.read_text(encoding="utf-8")


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def check_wrapper(root: Path) -> None:
    text = read(root, WRAPPER)
    for snippet in WRAPPER_SNIPPETS:
        require(text, snippet, str(WRAPPER))
    for helper in [CPP_CAPTURE, ORIGINAL_CAPTURE, COMPARATOR]:
        if not (root / helper).exists():
            raise RuntimeError(f"missing helper {helper}")


def check_original_capture(root: Path) -> None:
    text = read(root, ORIGINAL_CAPTURE)
    for snippet in ORIGINAL_CAPTURE_SNIPPETS:
        require(text, snippet, str(ORIGINAL_CAPTURE))


def check_docs(root: Path) -> None:
    text = read(root, DOC)
    for snippet in DOC_SNIPPETS:
        require(text, snippet, str(DOC))


def check_cmake(root: Path) -> None:
    text = read(root, CMAKE)
    require(text, "tools/check_frame_compare_workflow.py", str(CMAKE))
    require(text, "frame_compare_workflow_contract", str(CMAKE))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=str(default_repo_root()),
        help="repository root",
    )
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()

    check_wrapper(root)
    check_original_capture(root)
    check_docs(root)
    check_cmake(root)
    print(
        "frame_compare_workflow=ok "
        "wrapper=1 helpers=3 docs=1 ctest=1 scenarios=2 original_preflight=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
