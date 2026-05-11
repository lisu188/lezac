#!/usr/bin/env python3
"""Verify static actor/contact callsite anchors in LEZAC.EXE."""

from __future__ import annotations

import argparse
from pathlib import Path


CONTACT_SCANNER_ENTRY = 0x5CB0
CONTACT_SCANNER_RETURN = 0x604F
CONTACT_SCANNER_CALLSITE = 0x6555
ACTOR_UPDATE_ENTRY = 0x6053
IMAGE_SEGMENT = "1000"


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def image_base(data: bytes) -> int:
    if data[:2] != b"MZ":
        raise RuntimeError("LEZAC.EXE is not an MZ executable")
    return (data[8] | (data[9] << 8)) * 16


def code_byte(data: bytes, base: int, offset: int) -> int:
    index = base + offset
    if index < base or index >= len(data):
        raise RuntimeError(f"offset 1000:{offset:04X} maps outside LEZAC.EXE")
    return data[index]


def code_bytes(data: bytes, base: int, offset: int, length: int) -> bytes:
    return bytes(code_byte(data, base, offset + index) for index in range(length))


def near_call_target(data: bytes, base: int, call_offset: int) -> int:
    opcode = code_byte(data, base, call_offset)
    if opcode != 0xE8:
        raise RuntimeError(f"1000:{call_offset:04X} is not a near call")
    rel = code_byte(data, base, call_offset + 1) | (
        code_byte(data, base, call_offset + 2) << 8
    )
    if rel >= 0x8000:
        rel -= 0x10000
    return (call_offset + 3 + rel) & 0xFFFF


def scan_near_calls(data: bytes, base: int, target: int) -> list[int]:
    image_len = len(data) - base
    hits: list[int] = []
    for offset in range(0, image_len - 3):
        if data[base + offset] != 0xE8:
            continue
        rel = data[base + offset + 1] | (data[base + offset + 2] << 8)
        if rel >= 0x8000:
            rel -= 0x10000
        dest = (offset + 3 + rel) & 0xFFFF
        if dest == target:
            hits.append(offset)
    return hits


def fmt(offset: int) -> str:
    return f"{IMAGE_SEGMENT}:{offset:04X}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check static actor/contact callsite anchors in LEZAC.EXE."
    )
    parser.add_argument("repo_root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.repo_root.resolve()
    exe = root / "LEZAC.EXE"
    data = exe.read_bytes()
    base = image_base(data)

    entry_bytes = code_bytes(data, base, CONTACT_SCANNER_ENTRY, 2)
    return_bytes = code_bytes(data, base, CONTACT_SCANNER_RETURN, 3)
    callsite_bytes = code_bytes(data, base, CONTACT_SCANNER_CALLSITE, 3)
    actor_update_bytes = code_bytes(data, base, ACTOR_UPDATE_ENTRY, 2)
    if entry_bytes != bytes.fromhex("5589"):
        raise RuntimeError(
            f"unexpected contact scanner entry bytes: {entry_bytes.hex()}"
        )
    if return_bytes != bytes.fromhex("c9c202"):
        raise RuntimeError(
            f"unexpected contact scanner return bytes: {return_bytes.hex()}"
        )
    if callsite_bytes != bytes.fromhex("e858f7"):
        raise RuntimeError(
            f"unexpected contact scanner callsite bytes: {callsite_bytes.hex()}"
        )
    if actor_update_bytes != bytes.fromhex("5589"):
        raise RuntimeError(
            f"unexpected actor update entry bytes: {actor_update_bytes.hex()}"
        )

    calls = scan_near_calls(data, base, CONTACT_SCANNER_ENTRY)
    if calls != [CONTACT_SCANNER_CALLSITE]:
        raise RuntimeError(
            "unexpected direct contact scanner callsites: "
            + ",".join(fmt(call) for call in calls)
        )
    call_target = near_call_target(data, base, CONTACT_SCANNER_CALLSITE)
    if call_target != CONTACT_SCANNER_ENTRY:
        raise RuntimeError(
            f"callsite {fmt(CONTACT_SCANNER_CALLSITE)} targets {fmt(call_target)}"
        )

    print(
        "actor_contact_callsite_scan=ok "
        f"image_base=0x{base:04x} "
        f"scanner_entry={fmt(CONTACT_SCANNER_ENTRY)} "
        f"scanner_entry_bytes={entry_bytes.hex()} "
        f"scanner_return={fmt(CONTACT_SCANNER_RETURN)} "
        f"scanner_return_bytes={return_bytes.hex()} "
        f"scanner_calls={','.join(fmt(call) for call in calls)} "
        f"callsite_bytes={callsite_bytes.hex()} "
        f"actor_update_entry={fmt(ACTOR_UPDATE_ENTRY)} "
        f"actor_update_entry_bytes={actor_update_bytes.hex()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
