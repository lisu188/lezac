#!/usr/bin/env python3
"""Guard direct playSound(index) compatibility hooks.

These callers intentionally remain compatibility hooks until original
cursor/priority writes are recovered. The guard keeps that debt explicit and
prevents new direct hooks from drifting in silently.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


EXPECTED_LIVE_HOOKS = {
    "level_complete": (
        "if (completeTimer_ == 0) playSound(kCompatibilityLevelCompleteSound);"
    ),
    "objective_pickup": "playSound(kCompatibilityObjectivePickupSound);",
    "monster_death": "playSound(kCompatibilityMonsterDeathSound);",
}

EXPECTED_HELPER_SNIPPETS = [
    "constexpr size_t kCompatibilityObjectivePickupSound = 0;",
    "constexpr size_t kCompatibilityMonsterDeathSound = 4;",
    "constexpr size_t kCompatibilityLevelCompleteSound = 5;",
    "void playSound(size_t index)",
    "playSound(soundIndexForSelector(selector));",
]

EXPECTED_RECOVERED_HOOK_SNIPPETS = [
    "constexpr uint16_t kBombPlaceSoundCursor = 0xea74;",
    "constexpr uint8_t kBombPlaceSoundPriority = 3;",
    "bool requestBombPlaceSound()",
    "requestBombPlaceSound();",
]


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, label: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{label} missing snippet: {snippet}")


def require_collapsed(text: str, snippet: str, label: str) -> None:
    collapsed_text = " ".join(text.split())
    collapsed_snippet = " ".join(snippet.split())
    if collapsed_snippet not in collapsed_text:
        raise RuntimeError(f"{label} missing snippet: {snippet}")


def check_source(source_path: Path) -> None:
    text = source_path.read_text(encoding="utf-8")
    for snippet in EXPECTED_HELPER_SNIPPETS:
        require(text, snippet, "source")
    for snippet in EXPECTED_RECOVERED_HOOK_SNIPPETS:
        require(text, snippet, "source")
    for snippet in EXPECTED_LIVE_HOOKS.values():
        require(text, snippet, "source")

    call_lines = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if "playSound(" not in line:
            continue
        if "void playSound(" in line:
            continue
        if "playSound(soundIndexForSelector(selector))" in line:
            continue
        call_lines.append((lineno, line.strip()))

    expected_lines = sorted(EXPECTED_LIVE_HOOKS.values())
    actual_lines = sorted(line for _, line in call_lines)
    if actual_lines != expected_lines:
        formatted = ", ".join(f"{lineno}:{line}" for lineno, line in call_lines)
        raise RuntimeError(
            "direct playSound compatibility hook set changed: " + formatted
        )


def check_docs(root: Path) -> None:
    docs = {
        "GHIDRA_NOTES": root / "docs" / "GHIDRA_NOTES.md",
        "README": root / "README_RECONSTRUCTION.md",
        "RECOVERY_STATUS": root / "RECOVERY_STATUS.md",
    }
    for label, path in docs.items():
        text = path.read_text(encoding="utf-8")
        require_collapsed(text, "direct `playSound(index)`", label)
        require_collapsed(text, "compatibility hooks", label)
        require_collapsed(text, "original cursor/priority", label)


def check_cmake(cmake_path: Path) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    require(text, "sound_compatibility_hooks", "CMake")
    require(text, "tools/check_sound_compatibility_hooks.py", "CMake")
    require(
        text,
        "^sound_compatibility_hooks=ok live_hooks=3 recovered_hooks=1 helpers=9 docs=3",
        "CMake",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check direct playSound compatibility hooks stay explicit."
    )
    parser.add_argument("repo_root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.repo_root.resolve()
    check_source(root / "src" / "main.cpp")
    check_docs(root)
    check_cmake(root / "CMakeLists.txt")
    print(
        "sound_compatibility_hooks=ok "
        f"live_hooks={len(EXPECTED_LIVE_HOOKS)} "
        "recovered_hooks=1 "
        f"helpers={len(EXPECTED_HELPER_SNIPPETS) + len(EXPECTED_RECOVERED_HOOK_SNIPPETS)} "
        "docs=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
