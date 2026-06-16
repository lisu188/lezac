#!/usr/bin/env python3
"""Check recovered sound request callsite mapping across docs, C++, and CTest."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class SoundCue:
    name: str
    docs_anchor: str
    cursor: str
    priority: int
    docs_priority_needles: tuple[str, ...]
    source_needles: tuple[str, ...]
    ctest_names: tuple[str, ...]
    readme_needles: tuple[str, ...]


DIRECT_SWEEPS = {
    "0xea74": 4,
    "0xea7e": 5,
    "0xea88": 6,
    "0xeace": 7,
}


SOUND_CUES = [
    SoundCue(
        name="bomb_object",
        docs_anchor="1000:6cb3..6e3f",
        cursor="0x0012",
        priority=3,
        docs_priority_needles=("queues priority `3`",),
        source_needles=(
            "kBombObjectDefaultSoundCursor = 0x0000",
            "kBombObjectHighSoundCursor = 0x0012",
            "kBombObjectSoundPriority = 3",
            "requestBombObjectScoreSound",
        ),
        ctest_names=("bomb_object_sound",),
        readme_needles=("bomb-object destruction queues", "priority-`3` object cue"),
    ),
    SoundCue(
        name="portal",
        docs_anchor="1000:5999..5a72",
        cursor="0x001a",
        priority=4,
        docs_priority_needles=("DS:799f = 4",),
        source_needles=(
            "kPortalTeleportSoundCursor = 0x001a",
            "kPortalTeleportSoundPriority = 4",
            "requestPortalTeleportSound",
        ),
        ctest_names=("portal_sound",),
        readme_needles=("transfer queues cursor `0x001a`", "priority `4`"),
    ),
    SoundCue(
        name="tile_trigger",
        docs_anchor="1000:5740..586e",
        cursor="0x0027",
        priority=6,
        docs_priority_needles=("DS:799f = 6",),
        source_needles=(
            "kTileTriggerSoundCursor = 0x0027",
            "kTileTriggerSoundPriority = 6",
            "requestTileTriggerSound",
        ),
        ctest_names=("trigger_sound",),
        readme_needles=("tile-trigger activation", "cursor `0x0027`"),
    ),
    SoundCue(
        name="bonus_pickup",
        docs_anchor="1000:6e4b..6f8d",
        cursor="0x0008",
        priority=5,
        docs_priority_needles=("DS:799f = 5",),
        source_needles=(
            "collectBonusDrop",
            "requestSoundCursor(kBonusPickupSoundCursor, kBonusPickupSoundPriority)",
        ),
        ctest_names=("bonus_rewards",),
        readme_needles=("bonus pickup audio queues cursor", "`0x0008` at priority `5`"),
    ),
    SoundCue(
        name="player_damage",
        docs_anchor="1000:7f34..804e",
        cursor="0x002d",
        priority=4,
        docs_priority_needles=("DS:799f = 4",),
        source_needles=(
            "kPlayerDamageSoundCursor = 0x002d",
            "kPlayerDamageSoundPriority = 4",
            "requestPlayerDamageSound",
        ),
        ctest_names=("player_damage_sound", "original_damage_counters"),
        readme_needles=("accepted player damage queues cursor `0x002d`",),
    ),
    SoundCue(
        name="player_death",
        docs_anchor="1000:30a3",
        cursor="0x0056",
        priority=5,
        docs_priority_needles=("DS:799f = 5",),
        source_needles=(
            "kPlayerDeathSoundCursor = 0x0056",
            "kPlayerDeathSoundPriority = 5",
            "requestPlayerDeathSound",
            "beginPlayerDeath",
        ),
        ctest_names=("player_damage_sound", "player_state2_death_fields"),
        readme_needles=("player death/life-loss queues cursor `0x0056`",),
    ),
]


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise RuntimeError(f"{label}: missing {needle!r}")


def require_ctest(cmake_text: str, test_name: str) -> None:
    pattern = re.compile(rf"add_test\(NAME\s+{re.escape(test_name)}\b")
    if not pattern.search(cmake_text):
        raise RuntimeError(f"CMakeLists.txt: missing CTest {test_name!r}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check recovered sound callsite map consistency."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    source = read_text(root / "src" / "main.cpp")
    cmake = read_text(root / "CMakeLists.txt")
    readme = read_text(root / "README_RECONSTRUCTION.md")
    ghidra = read_text(root / "docs" / "GHIDRA_NOTES.md")

    require(ghidra, "1000:165a..167d", "ghidra priority latch")
    require(ghidra, "1000:0fbe..1088", "ghidra sound tick")
    require(source, "latchSoundRequest", "source priority latch")
    require(source, "pumpSoundLatch", "source sound pump")
    require_ctest(cmake, "sound_priority_latch")
    require_ctest(cmake, "sound_selector_map")
    require_ctest(cmake, "sound_cursor_segments")
    require_ctest(cmake, "son_step_fields")

    for offset, selector in DIRECT_SWEEPS.items():
        require(ghidra, offset, f"ghidra direct sweep {offset}")
        require(source, offset, f"source direct sweep {offset}")
        require(source, str(selector), f"source direct sweep selector {offset}")
    for cue in SOUND_CUES:
        require(ghidra, cue.docs_anchor, f"{cue.name} docs anchor")
        require(ghidra, cue.cursor, f"{cue.name} docs cursor")
        for needle in cue.docs_priority_needles:
            require(ghidra, needle, f"{cue.name} docs priority")
        for needle in cue.source_needles:
            require(source, needle, f"{cue.name} source")
        for test_name in cue.ctest_names:
            require_ctest(cmake, test_name)
        for needle in cue.readme_needles:
            require(readme, needle, f"{cue.name} readme")

    cue_names = ",".join(cue.name for cue in SOUND_CUES)
    direct_sweep_offsets = ",".join(DIRECT_SWEEPS)
    print(
        "sound_callsite_map=ok "
        f"cues={len(SOUND_CUES)} "
        f"cue_names={cue_names} "
        f"direct_sweeps={len(DIRECT_SWEEPS)} "
        f"direct_sweep_offsets={direct_sweep_offsets} "
        "priority_latch=1000:165a..167d "
        "tick_window=1000:0fbe..1088 "
        "tests=10"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
