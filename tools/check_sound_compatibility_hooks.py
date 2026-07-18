#!/usr/bin/env python3
"""Guard remaining playSound(index) compatibility hooks.

These routes intentionally remain compatibility hooks until original
cursor/priority writes are recovered. The guard keeps that debt explicit,
requires gameplay to use named hook slots, and prevents new direct
playSound(index) callers from drifting in silently.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


EXPECTED_LIVE_HOOKS = {
    "level_complete": (
        "playCompatibilitySound(kLevelCompleteCompatibilityHookSlot);"
    ),
    "objective_pickup": (
        "playCompatibilitySound(kObjectivePickupCompatibilityHookSlot);"
    ),
}

EXPECTED_HELPER_SNIPPETS = [
    "constexpr size_t kCompatibilityObjectivePickupSound = 0;",
    "constexpr size_t kCompatibilityLevelCompleteSound = 5;",
    "constexpr size_t kObjectivePickupCompatibilityHookSlot = 0;",
    "constexpr size_t kLevelCompleteCompatibilityHookSlot = 1;",
    "struct RemainingSoundCompatibilityHook",
    "const char* captureBlocker;",
    "void playSound(size_t index)",
    "void playCompatibilitySound(size_t hookSlot)",
    "playSound(hook.index);",
    "playSound(soundIndexForSelector(selector));",
]

EXPECTED_RECOVERED_HOOK_SNIPPETS = [
    "constexpr uint16_t kBombPlaceSoundCursor = 0xea74;",
    "constexpr uint8_t kBombPlaceSoundPriority = 3;",
    "bool requestBombPlaceSound()",
    "requestBombPlaceSound();",
    "constexpr uint16_t kMonsterDeathSoundCursor = 0x003d;",
    "constexpr uint8_t kMonsterDeathSoundPriority = 12;",
    "bool requestMonsterDeathSound()",
    "requestMonsterDeathSound();",
    "constexpr uint16_t kRecordNamePromptSoundCursor = 0x0078;",
    "constexpr uint8_t kRecordNamePromptSoundPriority = 11;",
    "bool requestRecordNamePromptSound()",
    "requestRecordNamePromptSound();",
    "constexpr uint16_t kRecordNameCommitSoundCursor = 0x0008;",
    "constexpr uint8_t kRecordNameCommitSoundPriority = 11;",
    "bool requestRecordNameCommitSound()",
    "requestRecordNameCommitSound();",
    "constexpr uint16_t kRecordsPageSoundCursor = 0x0024;",
    "constexpr uint8_t kRecordsPageSoundPriority = 2;",
    "bool requestRecordsPageSound()",
    "requestRecordsPageSound();",
    "constexpr uint16_t kWeaponSwitchSoundCursor = 0x0024;",
    "constexpr uint8_t kWeaponSwitchSoundPriority = 2;",
    "bool requestWeaponSwitchSound()",
    "requestWeaponSwitchSound();",
    "constexpr uint16_t kLaunchPadSoundCursor = 0x0035;",
    "constexpr uint8_t kLaunchPadSoundPriority = 5;",
    "bool requestLaunchPadSound()",
    "requestLaunchPadSound();",
]

EXPECTED_REJECTED_OBJECTIVE_CANDIDATES = [
    "0x4b2c:collapse_playback",
    "0x6d75:bomb_object_high_gate",
    "0x6924:non_objective_tile_gate",
]

EXPECTED_CAPTURE_BLOCKERS = [
    "objective_pickup:rejected_static_candidates",
    "level_complete:no_static_candidate",
]

EXPECTED_ACTOR_CONTACT_CAPTURE_CANDIDATES = (
    "actor_contact_capture_candidates=0x5e81:contact_scanner,"
    "0x7386:actor_update"
)

EXPECTED_RUNTIME_CAPTURE_HANDOFFS = [
    "tools/capture_original_sound_callsite_procmem.sh",
    "tools/sweep_original_sound_callsite_routes.py",
    "LEZAC_SOUND_CALLSITE_APPROVE_PROCMEM",
    "LEZAC_SOUND_CALLSITE_APPROVE_RUNTIME_INSTRUMENTATION",
]

EXPECTED_RUNTIME_ROUTE_CLASSIFICATION = [
    "first_target=actor_update_runtime_cursor_0024_sound",
    "route_classes=natural:3,runtime_seeded:1",
    "state6_capture_blocker=shipped_actor_modes_exclude_6",
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
    require(text, "kRemainingSoundCompatibilityHooks", "source")
    require(text, "kRejectedObjectiveSoundCandidates", "source")
    require(text, "remaining_compat_hooks=", "source")
    require(text, "capture_blockers=", "source")
    require(text, "latch_preserved=", "source")
    require(text, "debugRemainingSoundCompatibilityHooks", "source")
    require(text, "--debug-remaining-sound-compat-hooks", "source")
    require(text, "remaining_sound_compat_hooks=ok", "source")
    require(text, "--debug-sound-runtime-capture-queue", "source")
    require(text, "sound_runtime_capture_queue=ok", "source")
    require(text, "original_cursor_priority_claim=0", "source")
    require(text, "capture_classes=", "source")
    require(text, "actor_contact_capture_candidates=", "source")
    require(text, "objective_pickup,level_complete", "source")
    for snippet in EXPECTED_RUNTIME_CAPTURE_HANDOFFS:
        require(text, snippet, "source")
    for snippet in EXPECTED_RUNTIME_ROUTE_CLASSIFICATION:
        source_snippet = (
            "natural:3,runtime_seeded:1"
            if snippet.startswith("route_classes=")
            else snippet
        )
        require(text, source_snippet, "source")
    for snippet in EXPECTED_REJECTED_OBJECTIVE_CANDIDATES:
        require(text, snippet, "source")
    for snippet in EXPECTED_CAPTURE_BLOCKERS:
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

    expected_lines = ["playSound(hook.index);"]
    actual_lines = sorted(line for _, line in call_lines)
    if actual_lines != expected_lines:
        formatted = ", ".join(f"{lineno}:{line}" for lineno, line in call_lines)
        raise RuntimeError(
            "direct playSound compatibility funnel changed: " + formatted
        )


def check_docs(root: Path) -> None:
    docs = {
        "GHIDRA_NOTES": root / "docs" / "GHIDRA_NOTES.md",
        "README": root / "README_RECONSTRUCTION.md",
        "RECOVERY_STATUS": root / "RECOVERY_STATUS.md",
    }
    for label, path in docs.items():
        text = path.read_text(encoding="utf-8")
        require_collapsed(text, "`playCompatibilitySound`", label)
        require_collapsed(text, "`playSound(index)`", label)
        require_collapsed(text, "compatibility hooks", label)
        require_collapsed(text, "original cursor/priority", label)
        require_collapsed(
            text,
            "remaining_compat_hooks=objective_pickup,level_complete",
            label,
        )
        require_collapsed(text, "--debug-remaining-sound-compat-hooks", label)
        require_collapsed(text, "latch_preserved=1", label)
        require_collapsed(text, "--debug-sound-runtime-capture-queue", label)
        require_collapsed(text, "sound_runtime_capture_queue=ok", label)
        require_collapsed(text, "original_cursor_priority_claim=0", label)
        require_collapsed(text, EXPECTED_ACTOR_CONTACT_CAPTURE_CANDIDATES, label)
        for snippet in EXPECTED_RUNTIME_CAPTURE_HANDOFFS:
            require_collapsed(text, snippet, label)
        for snippet in EXPECTED_RUNTIME_ROUTE_CLASSIFICATION:
            require_collapsed(text, snippet, label)
        for snippet in EXPECTED_REJECTED_OBJECTIVE_CANDIDATES:
            require_collapsed(text, snippet, label)
        for snippet in EXPECTED_CAPTURE_BLOCKERS:
            require_collapsed(text, snippet, label)


def check_cmake(cmake_path: Path) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    require(text, "sound_compatibility_hooks", "CMake")
    require(text, "tools/check_sound_compatibility_hooks.py", "CMake")
    require(text, "add_test(NAME remaining_sound_compat_hooks", "CMake")
    require(text, "add_test(NAME sound_runtime_capture_queue", "CMake")
    require(text, "sound_runtime_capture_queue=ok", "CMake")
    require(text, "original_cursor_priority_claim=0", "CMake")
    require(text, "capture_blockers=objective_pickup:rejected_static_candidates,level_complete:no_static_candidate", "CMake")
    require(text, "latch_preserved=1", "CMake")
    require(text, EXPECTED_ACTOR_CONTACT_CAPTURE_CANDIDATES, "CMake")
    for snippet in EXPECTED_RUNTIME_CAPTURE_HANDOFFS:
        require(text, snippet, "CMake")
    for snippet in EXPECTED_RUNTIME_ROUTE_CLASSIFICATION:
        require(text, snippet, "CMake")
    require(
        text,
        "^sound_compatibility_hooks=ok live_hooks=2 recovered_hooks=7 helpers=38 docs=3 rejected_objective_candidates=3 capture_blockers=2 runtime_capture_handoffs=4 runtime_route_classifications=3 live_diagnostic=1",
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
        "recovered_hooks=7 "
        f"helpers={len(EXPECTED_HELPER_SNIPPETS) + len(EXPECTED_RECOVERED_HOOK_SNIPPETS)} "
        "docs=3 "
        f"rejected_objective_candidates={len(EXPECTED_REJECTED_OBJECTIVE_CANDIDATES)} "
        f"capture_blockers={len(EXPECTED_CAPTURE_BLOCKERS)} "
        f"runtime_capture_handoffs={len(EXPECTED_RUNTIME_CAPTURE_HANDOFFS)} "
        "runtime_route_classifications="
        f"{len(EXPECTED_RUNTIME_ROUTE_CLASSIFICATION)} "
        "live_diagnostic=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
