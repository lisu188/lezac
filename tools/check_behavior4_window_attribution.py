#!/usr/bin/env python3
"""Pin the disproof that Ghidra 1000:728C..731B is a behavior-4 branch.

The open evidence item was long tracked as `behavior4_branch_runtime_fixture`,
"behavior-4 branch semantics fixture at 1000:728C..731B". The shipped bytes
show that window is reachable ONLY from a `cmp al,3 / je` guard, and that the
behavior-4 arm jumps clean past it. A behavior-4 actor therefore never
executes a single instruction in that window, on any level, ever -- so no
capture can ever fill a fixture for it as specified.

This checker pins the instruction bytes that carry the disproof, so the item
cannot silently drift back to the wrong routine.
"""

from __future__ import annotations

import argparse
from pathlib import Path


# MZ image base for LEZAC.EXE: file_offset = ghidra_addr + IMAGE_BASE.
IMAGE_BASE = 0x0770

WINDOW_START = 0x728C
WINDOW_END = 0x731B

# The behavior-4 arm's last instruction: `jmp 0x732C`, past the whole window.
BEHAVIOR4_SKIP = (0x714F, bytes.fromhex("e9da01"), "jmp 0x732C past the window")

# The only external entry into the window is guarded by a compare against 3.
WINDOW_GUARD = [
    (0x7152, bytes.fromhex("3c03"), "cmp al,3"),
    (0x7154, bytes.fromhex("7403"), "je (taken only when the selector is 3)"),
]

# The window's own gate local [bp-0x20] is written at exactly these four sites,
# all inside the behavior-3 arm. modrm 0x46 + disp8 0xe0 addresses [bp-0x20].
GATE_WRITES = [
    (0x716B, bytes.fromhex("8846e0"), "mov [bp-0x20],al"),
    (0x71A0, bytes.fromhex("c646e001"), "mov byte [bp-0x20],1"),
    (0x71F3, bytes.fromhex("c646e001"), "mov byte [bp-0x20],1"),
    (0x723D, bytes.fromhex("c646e001"), "mov byte [bp-0x20],1"),
]


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def check(image: bytes, ghidra: int, expected: bytes, label: str) -> None:
    offset = ghidra + IMAGE_BASE
    actual = image[offset:offset + len(expected)]
    if actual != expected:
        raise RuntimeError(
            f"1000:{ghidra:04X} (file 0x{offset:04X}) is {actual.hex()}, "
            f"expected {expected.hex()} ({label})")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pin that 1000:728C..731B is behavior-3-only.")
    parser.add_argument("repo_root", nargs="?", type=Path,
                        default=default_repo_root())
    args = parser.parse_args()

    image = (args.repo_root / "LEZAC.EXE").read_bytes()

    check(image, *BEHAVIOR4_SKIP)
    for ghidra, expected, label in WINDOW_GUARD:
        check(image, ghidra, expected, label)
    for ghidra, expected, label in GATE_WRITES:
        check(image, ghidra, expected, label)

    # Every gate write must sit before the window, i.e. inside the behavior-3
    # arm that falls into it -- not inside the window itself.
    for ghidra, _expected, _label in GATE_WRITES:
        if WINDOW_START <= ghidra <= WINDOW_END:
            raise RuntimeError(
                f"gate write 1000:{ghidra:04X} unexpectedly lies inside the window")

    print(
        "behavior4_window_attribution=ok "
        f"window=1000:{WINDOW_START:04X}..{WINDOW_END:04X} "
        f"window_bytes={WINDOW_END - WINDOW_START + 1} "
        f"behavior4_skip=1000:{BEHAVIOR4_SKIP[0]:04X} "
        f"entry_guard=cmp_al_3 "
        f"gate_writes={len(GATE_WRITES)} "
        "gate_writes_inside_window=0 "
        "behavior4_executes_window=0 "
        "attribution=behavior3_only "
        "original_fidelity_claim=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
