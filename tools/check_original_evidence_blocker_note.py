#!/usr/bin/env python3
"""Check the recorded Windows original-evidence blocker note."""

from __future__ import annotations

import argparse
from pathlib import Path


DOC = Path("docs/recovery/original_evidence_blocked_windows_2026-05-23.md")
CMAKE = Path("CMakeLists.txt")

DOC_SNIPPETS = [
    "original_evidence_blocker=windows_no_default_wsl_distro",
    "date=2026-05-23",
    "host=windows",
    "assets=ok",
    "wsl=found",
    "wsl_probe=ok",
    "wsl_bash_probe=error_4294967295",
    "wsl_bash_reason=no_default_distro",
    "missing_required=bash,dosbox,xvfb-run,xdotool",
    "environment_preflight=error",
    "not_original_evidence=1",
    "visual_claim=0",
    "original_evidence_blocker=windows_wsl_dosbox_debug_probe_failed",
    "date=2026-06-16",
    "command=wsl -- bash -lc 'set -e; command -v dosbox-debug; dosbox-debug -version'",
    "wsl_dosbox_debug_probe=error",
    "wsl_error=WSL_E_DEFAULT_DISTRO_NOT_FOUND",
    "reason=wsl_bash_not_usable",
    "tools/preflight_original_evidence_environment.py . --require-assets --require-frame-capture --probe-wsl --require-wsl-bash-on-windows",
    "wsl -- bash -lc 'set -e; command -v dosbox-debug; dosbox-debug -version'",
    "tools/compare_original_cpp_frames.sh /tmp/lezac-frame-compare . level1_bomb_route",
    "tools/summarize_frame_compare_bundle.py /tmp/lezac-frame-compare --require-promotion-ready",
    "frame_compare_summary.txt",
    "manifest.txt",
    "environment_preflight.log",
    "visual_claim=1",
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


def check_doc(root: Path) -> None:
    text = read(root, DOC)
    for snippet in DOC_SNIPPETS:
        require(text, snippet, str(DOC))


def check_cmake(root: Path) -> None:
    text = read(root, CMAKE)
    require(text, "tools/check_original_evidence_blocker_note.py", str(CMAKE))
    require(text, "original_evidence_blocker_note_expectations", str(CMAKE))
    require(
        text,
        "^original_evidence_blocker_note=ok docs=1 ctest=1 commands=4 blocker=windows_no_default_wsl_distro",
        str(CMAKE),
    )


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

    check_doc(root)
    check_cmake(root)
    print(
        "original_evidence_blocker_note=ok "
        "docs=1 ctest=1 commands=4 blocker=windows_no_default_wsl_distro"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
