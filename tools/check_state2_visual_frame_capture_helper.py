#!/usr/bin/env python3
"""Check the state-2 original visual-frame capture helper contract."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


SCRIPT = Path("tools/capture_original_state2_visual_frames.sh")
DOCS = (
    Path("README_RECONSTRUCTION.md"),
    Path("docs/recovery/frame_comparison.md"),
    Path("docs/recovery/original_runtime_fixture_notes.md"),
)
CMAKE = Path("CMakeLists.txt")


def read(root: Path, path: Path) -> str:
    full_path = root / path
    if not full_path.exists():
        raise RuntimeError(f"missing {path}")
    return full_path.read_text(encoding="utf-8")


def require(text: str, snippet: str, label: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{label} missing snippet {snippet!r}")


def check_script(root: Path) -> None:
    text = read(root, SCRIPT)
    for snippet in (
        "state2_death_table_consumption",
        "capture=state2_visual_frames",
        "route=debugger_seeded",
        "state2_game_4a.png",
        "state2_game_4f.png",
        "compare_state2_visual_row_game_previews.py",
        "preflight_original_evidence_environment.py",
        "--require-frame-capture",
        "--probe-wsl",
        "--require-wsl-bash-on-windows",
        "LEZAC_STATE2_VISUAL_FRAME_CAPTURE_DRY_RUN",
        "debugger_seeded_frame_capture_not_automated",
        "visual_claim=$visual_claim",
    ):
        require(text, snippet, str(SCRIPT))


def check_docs(root: Path) -> None:
    for path in DOCS:
        text = read(root, path)
        require(text, "capture_original_state2_visual_frames.sh", str(path))
        require(text, "state2_death_table_consumption", str(path))


def check_cmake(root: Path) -> None:
    text = read(root, CMAKE)
    for snippet in (
        "capture_original_state2_visual_frames.sh",
        "check_state2_visual_frame_capture_helper.py",
        "state2_visual_frame_capture_helper_dry_run",
        "state2_visual_frame_capture_helper_expectations",
    ):
        require(text, snippet, str(CMAKE))


def run_dry_run(root: Path, out_dir: Path) -> bool:
    bash = shutil.which("bash")
    if bash is None:
        return False
    if out_dir == root or root in out_dir.parents:
        out_dir = Path(tempfile.mkdtemp(prefix="lezac-state2-visual-frame-helper-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            bash,
            str(root / SCRIPT),
            str(out_dir),
            str(root),
            "state2_death_table_consumption",
        ],
        cwd=root,
        env={**os.environ, "LEZAC_STATE2_VISUAL_FRAME_CAPTURE_DRY_RUN": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"dry_run_failed status={proc.returncode} output={proc.stdout.strip()}"
        )
    for snippet in (
        "state2_visual_frame_capture=ok",
        "mode=dry_run",
        "scenario=state2_death_table_consumption",
        "route=debugger_seeded",
        "expected_frames=6",
    ):
        require(proc.stdout, snippet, "dry_run_output")

    manifest = (out_dir / "manifest.txt").read_text(encoding="utf-8")
    for snippet in (
        "capture=state2_visual_frames",
        "visual_claim=0",
        "expected_frame_count=6",
        "state2_game_4a",
        "state2_game_4f",
        "environment_preflight=dry_run",
    ):
        require(manifest, snippet, "dry_run_manifest")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()

    root = args.repo_root.resolve()
    check_script(root)
    check_docs(root)
    check_cmake(root)
    dry_run_checked = run_dry_run(root, args.out_dir.resolve())
    print(
        "state2_visual_frame_capture_helper=ok "
        "scenarios=1 frames=6 docs=3 ctest=2 "
        f"dry_run={'checked' if dry_run_checked else 'skipped_no_bash'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
