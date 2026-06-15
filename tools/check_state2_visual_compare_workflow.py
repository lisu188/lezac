#!/usr/bin/env python3
"""Exercise the state-2 visual row frame-compare helper."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


HELPER = Path("tools/compare_state2_visual_row_game_previews.py")
SUMMARIZER = Path("tools/summarize_frame_compare_bundle.py")
DOC = Path("docs/recovery/frame_comparison.md")
CMAKE = Path("CMakeLists.txt")


def read(root: Path, path: Path) -> str:
    full_path = root / path
    if not full_path.exists():
        raise RuntimeError(f"missing {path}")
    return full_path.read_text(encoding="utf-8")


def require(text: str, snippet: str, label: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{label} missing snippet {snippet!r}")


def run(command: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "command_failed status={} command={} output={}".format(
                proc.returncode, " ".join(command), proc.stdout.strip()
            )
        )
    return proc.stdout.strip()


def remove_tree_best_effort(path: Path) -> bool:
    def on_error(function, failing_path, _exc_info) -> None:
        try:
            os.chmod(failing_path, 0o700)
            function(failing_path)
        except OSError:
            pass

    for _attempt in range(3):
        try:
            shutil.rmtree(path, onerror=on_error)
            return True
        except PermissionError:
            time.sleep(0.2)
        except OSError:
            time.sleep(0.2)
    return not path.exists()


def fresh_output_dir(out_dir: Path) -> Path:
    if not out_dir.exists():
        return out_dir
    if remove_tree_best_effort(out_dir):
        return out_dir
    fallback = out_dir.parent / f"{out_dir.name}-{os.getpid()}"
    if fallback.exists() and not remove_tree_best_effort(fallback):
        raise RuntimeError(f"could not prepare output directory {fallback}")
    return fallback


def check_static_contract(root: Path) -> None:
    helper = read(root, HELPER)
    for snippet in (
        "state2_visual_row_game_preview",
        "state2_game_current_",
        "state2_game_cursor_",
        "state2_{variant}_{suffix}",
        "(\"current\",",
        "(\"cursor\",",
        "frame_compare_summary.txt",
        "missing_original",
        "current_renderer=row_byte3",
        "cursor_renderer=debug_only",
        "visual_claim=0",
    ):
        require(helper, snippet, str(HELPER))

    doc = read(root, DOC)
    for snippet in (
        "tools/compare_state2_visual_row_game_previews.py",
        "state2_game_cursor_4a",
        "state2_current_4a",
        "state2_cursor_4a",
    ):
        require(doc, snippet, str(DOC))

    cmake = read(root, CMAKE)
    require(cmake, "tools/check_state2_visual_compare_workflow.py", str(CMAKE))
    require(cmake, "tools/compare_state2_visual_row_game_previews.py", str(CMAKE))
    require(cmake, "state2_visual_compare_workflow", str(CMAKE))


def check_runtime(root: Path, cpp_exe: Path, out_dir: Path) -> None:
    out_dir = fresh_output_dir(out_dir)
    fake_original = out_dir / "fake_original"
    bundle = out_dir / "bundle"
    fake_original.mkdir(parents=True)

    run(
        [
            str(cpp_exe),
            "--capture-state2-visual-row-game-preview",
            str(fake_original),
        ],
        root,
    )
    output = run(
        [
            sys.executable,
            str(root / HELPER),
            str(bundle),
            str(cpp_exe),
            str(fake_original),
            "--overwrite",
        ],
        root,
    )
    for snippet in (
        "state2_visual_row_compare_bundle=ok",
        "compared=12",
        "missing_original=0",
        "compare_exit=0",
    ):
        require(output, snippet, "helper_output")

    summary = run(
        [sys.executable, str(root / SUMMARIZER), str(bundle)],
        root,
    )
    for snippet in (
        "frame_compare_bundle_summary=ok",
        "scenario=state2_visual_row_game_preview",
        "compare_exit=0",
        "compared=12",
        "missing_original=0",
        "exact_matches=6",
        "promotion_ready=1",
    ):
        require(summary, snippet, "summary_output")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", type=Path)
    parser.add_argument("cpp_exe", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()

    root = args.repo_root.resolve()
    cpp_exe = args.cpp_exe.resolve()
    if not cpp_exe.exists():
        raise RuntimeError(f"missing cpp executable {cpp_exe}")

    check_static_contract(root)
    check_runtime(root, cpp_exe, args.out_dir.resolve())
    print("state2_visual_compare_workflow=ok helpers=2 docs=1 ctest=1 compared=12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
