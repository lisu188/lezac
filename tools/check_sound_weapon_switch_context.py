#!/usr/bin/env python3
"""Verify the original weapon-switch hold/release state machine and sound."""

from __future__ import annotations

import argparse
from pathlib import Path


IMAGE_SEGMENT = "1000"
PLAYER1_COUNTER_POINTER = 0x61CC
PLAYER2_COUNTER_POINTER = 0x6239
CHORD_GATE = 0x6813
SOUND_REQUEST = 0x6844
SOUND_LATCH_CALL = 0x684F
SELECTION_START = 0x6852
COUNTER_RESET = 0x68BD
SOUND_LATCH = 0x165A

PLAYER1_POINTER_BYTES = bytes.fromhex("b8b0798cdaa3bc798916be79eb6b")
PLAYER2_POINTER_BYTES = bytes.fromhex("b8b1798cdaa3bc798916be79")
CHORD_GATE_BYTES = bytes.fromhex(
    "a0841b30e48bd0a0831b30e403c23d02007514"
    "c606831b00c606841b00c43ebc7926fe05e9ed02"
    "c43ebc7926803d057279"
)
SOUND_REQUEST_BYTES = bytes.fromhex("c70674202400c6069f7902e808ae")
SELECTION_BYTES = bytes.fromhex(
    "8a46e330e48bf8c685751b02c606a37900"
    "8a46e330e48bf88a85731b30e499b90400f7f992408846ee"
    "8a56ee8a46e330e48bf88895731bfe06a379"
    "8a46ee30e48bd08a46e330e48bf8c1e70203fa"
    "80bd671b007707803ea3790476b5803ea379047608"
    "c47e0426c64524fec43ebc7926c60500"
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def fmt(offset: int) -> str:
    return f"{IMAGE_SEGMENT}:{offset:04X}"


def image_base(data: bytes) -> int:
    if data[:2] != b"MZ":
        raise RuntimeError("LEZAC.EXE is not an MZ executable")
    base = int.from_bytes(data[8:10], "little") * 16
    if base >= len(data):
        raise RuntimeError("LEZAC.EXE MZ header extends past the file")
    return base


def code_bytes(data: bytes, base: int, offset: int, length: int) -> bytes:
    start = base + offset
    end = start + length
    if offset < 0 or start < base or end > len(data):
        raise RuntimeError(f"{fmt(offset)} maps outside LEZAC.EXE")
    return data[start:end]


def require_bytes(
    data: bytes, base: int, offset: int, expected: bytes, label: str
) -> None:
    observed = code_bytes(data, base, offset, len(expected))
    if observed != expected:
        raise RuntimeError(
            f"{label} at {fmt(offset)} expected {expected.hex()} got "
            f"{observed.hex()}"
        )


def rel8_target(data: bytes, base: int, offset: int) -> int:
    raw = code_bytes(data, base, offset + 1, 1)[0]
    displacement = raw - 0x100 if raw >= 0x80 else raw
    return (offset + 2 + displacement) & 0xFFFF


def rel16_target(data: bytes, base: int, offset: int) -> int:
    displacement = int.from_bytes(
        code_bytes(data, base, offset + 1, 2), "little", signed=True
    )
    return (offset + 3 + displacement) & 0xFFFF


def require_text(path: Path, needle: str) -> None:
    if needle not in path.read_text(encoding="utf-8"):
        raise RuntimeError(f"{path.name} is missing {needle!r}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check original weapon-switch state and sound context."
    )
    parser.add_argument(
        "repo_root", nargs="?", type=Path, default=default_repo_root()
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    executable = (root / "LEZAC.EXE").read_bytes()
    base = image_base(executable)

    require_bytes(
        executable,
        base,
        PLAYER1_COUNTER_POINTER,
        PLAYER1_POINTER_BYTES,
        "player-1 weapon-switch counter pointer",
    )
    require_bytes(
        executable,
        base,
        PLAYER2_COUNTER_POINTER,
        PLAYER2_POINTER_BYTES,
        "player-2 weapon-switch counter pointer",
    )
    require_bytes(
        executable, base, CHORD_GATE, CHORD_GATE_BYTES, "weapon-switch chord gate"
    )
    require_bytes(
        executable,
        base,
        SOUND_REQUEST,
        SOUND_REQUEST_BYTES,
        "weapon-switch sound request",
    )
    require_bytes(
        executable,
        base,
        SELECTION_START,
        SELECTION_BYTES,
        "weapon selection and counter reset",
    )

    branch_targets = {
        0x6824: 0x683A,
        0x6837: 0x6B27,
        0x6842: COUNTER_RESET,
        0x68A5: 0x68AE,
        0x68AC: 0x6863,
        0x68B3: COUNTER_RESET,
    }
    for branch, expected in branch_targets.items():
        opcode = code_bytes(executable, base, branch, 1)[0]
        target = (
            rel16_target(executable, base, branch)
            if opcode in {0xE8, 0xE9}
            else rel8_target(executable, base, branch)
        )
        if target != expected:
            raise RuntimeError(
                f"branch {fmt(branch)} expected {fmt(expected)} got {fmt(target)}"
            )
    if rel16_target(executable, base, SOUND_LATCH_CALL) != SOUND_LATCH:
        raise RuntimeError("weapon-switch sound request no longer calls the priority latch")

    source = root / "src" / "app" / "app.cpp"
    for snippet in [
        "constexpr uint8_t kWeaponSwitchHoldTicks = 5;",
        "constexpr uint16_t kWeaponSwitchSoundCursor = 0x0024;",
        "constexpr uint8_t kWeaponSwitchSoundPriority = 2;",
        "void updateWeaponSwitch(BombInventory& inventory, uint8_t& holdTicks,",
        "if (holdTicks >= kWeaponSwitchHoldTicks)",
        "requestWeaponSwitchSound();",
        "bool requestWeaponSwitchSound()",
        "weapon_switch_sound=ok",
        "--debug-weapon-switch-sound",
    ]:
        require_text(source, snippet)

    cmake = root / "CMakeLists.txt"
    require_text(cmake, "add_test(NAME sound_weapon_switch_context")
    require_text(cmake, "add_test(NAME weapon_switch_sound")

    note_name = "sound_weapon_switch_process_memory_2026-07-16.md"
    docs = [
        root / "README_RECONSTRUCTION.md",
        root / "RECOVERY_STATUS.md",
        root / "docs" / "GHIDRA_NOTES.md",
        root / "docs" / "recovery" / note_name,
    ]
    for path in docs:
        require_text(path, "weapon_switch_sound=ok")
        require_text(path, "runtime_hold_counter=0x14")

    print(
        "sound_weapon_switch_context=ok "
        f"image_base=0x{base:04x} "
        "players=2 counters=DS:79B0,DS:79B1 "
        "inputs=DS:1B83+DS:1B84 threshold_ticks=5 trigger=release "
        f"sound={fmt(SOUND_REQUEST)} cursor=0x0024 priority=2 "
        f"selection={fmt(SELECTION_START)} counter_reset={fmt(COUNTER_RESET)} "
        f"latch={fmt(SOUND_LATCH)} runtime_route=z+x:1.50 "
        "runtime_hold_counter=0x14 runtime_cursor=0x0024 runtime_priority=2 docs=4"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
