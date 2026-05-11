#!/usr/bin/env python3
"""Verify the static actor/contact scanner callsite control-flow context."""

from __future__ import annotations

import argparse
from pathlib import Path


IMAGE_SEGMENT = "1000"
CONTACT_SCANNER_ENTRY = 0x5CB0
CONTACT_SCANNER_GATE = 0x654E
CONTACT_SCANNER_SKIP = 0x6552
CONTACT_SCANNER_CALLSITE = 0x6555
CONTACT_SCANNER_AFTER_CALL = 0x6558
CONTACT_SCANNER_SKIP_TARGET = 0x655B
SHARED_INTEGRATION = 0x73E5


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def image_base(data: bytes) -> int:
    if data[:2] != b"MZ":
        raise RuntimeError("LEZAC.EXE is not an MZ executable")
    return (data[8] | (data[9] << 8)) * 16


def code_byte(data: bytes, base: int, offset: int) -> int:
    index = base + offset
    if index < base or index >= len(data):
        raise RuntimeError(f"offset {fmt(offset)} maps outside LEZAC.EXE")
    return data[index]


def code_bytes(data: bytes, base: int, offset: int, length: int) -> bytes:
    return bytes(code_byte(data, base, offset + index) for index in range(length))


def rel8_target(data: bytes, base: int, offset: int) -> int:
    rel = code_byte(data, base, offset + 1)
    if rel >= 0x80:
        rel -= 0x100
    return (offset + 2 + rel) & 0xFFFF


def rel16_target(data: bytes, base: int, offset: int) -> int:
    rel = code_byte(data, base, offset + 1) | (
        code_byte(data, base, offset + 2) << 8
    )
    if rel >= 0x8000:
        rel -= 0x10000
    return (offset + 3 + rel) & 0xFFFF


def fmt(offset: int) -> str:
    return f"{IMAGE_SEGMENT}:{offset:04X}"


def require_bytes(
    data: bytes, base: int, offset: int, expected: bytes, label: str
) -> bytes:
    observed = code_bytes(data, base, offset, len(expected))
    if observed != expected:
        raise RuntimeError(
            f"{label} at {fmt(offset)} expected {expected.hex()} got {observed.hex()}"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check static actor/contact scanner callsite context."
    )
    parser.add_argument("repo_root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.repo_root.resolve()
    data = (root / "LEZAC.EXE").read_bytes()
    base = image_base(data)

    gate_bytes = require_bytes(
        data, base, CONTACT_SCANNER_GATE, bytes.fromhex("807ecf06"), "gate compare"
    )
    skip_bytes = require_bytes(
        data, base, CONTACT_SCANNER_SKIP, bytes.fromhex("7507"), "skip branch"
    )
    push_bytes = require_bytes(
        data, base, CONTACT_SCANNER_CALLSITE - 1, bytes.fromhex("55"), "call setup"
    )
    call_bytes = require_bytes(
        data,
        base,
        CONTACT_SCANNER_CALLSITE,
        bytes.fromhex("e858f7"),
        "scanner call",
    )
    jump_bytes = require_bytes(
        data,
        base,
        CONTACT_SCANNER_AFTER_CALL,
        bytes.fromhex("e98a0e"),
        "post-call jump",
    )
    post_skip_bytes = code_bytes(data, base, CONTACT_SCANNER_SKIP_TARGET, 4)

    skip_target = rel8_target(data, base, CONTACT_SCANNER_SKIP)
    if skip_target != CONTACT_SCANNER_SKIP_TARGET:
        raise RuntimeError(
            f"skip branch targets {fmt(skip_target)} instead of "
            f"{fmt(CONTACT_SCANNER_SKIP_TARGET)}"
        )
    call_target = rel16_target(data, base, CONTACT_SCANNER_CALLSITE)
    if call_target != CONTACT_SCANNER_ENTRY:
        raise RuntimeError(
            f"scanner call targets {fmt(call_target)} instead of "
            f"{fmt(CONTACT_SCANNER_ENTRY)}"
        )
    jump_target = rel16_target(data, base, CONTACT_SCANNER_AFTER_CALL)
    if jump_target != SHARED_INTEGRATION:
        raise RuntimeError(
            f"post-call jump targets {fmt(jump_target)} instead of "
            f"{fmt(SHARED_INTEGRATION)}"
        )

    snippet = code_bytes(data, base, CONTACT_SCANNER_GATE, 17)
    print(
        "actor_contact_callsite_context=ok "
        f"image_base=0x{base:04x} "
        f"gate={fmt(CONTACT_SCANNER_GATE)} "
        f"gate_bytes={gate_bytes.hex()} "
        "gate_value=0x06 "
        f"skip_branch={fmt(CONTACT_SCANNER_SKIP)} "
        f"skip_bytes={skip_bytes.hex()} "
        f"skip_target={fmt(skip_target)} "
        f"call_setup={fmt(CONTACT_SCANNER_CALLSITE - 1)} "
        f"call_setup_bytes={push_bytes.hex()} "
        f"callsite={fmt(CONTACT_SCANNER_CALLSITE)} "
        f"call_bytes={call_bytes.hex()} "
        f"call_target={fmt(call_target)} "
        f"post_call_jump={fmt(CONTACT_SCANNER_AFTER_CALL)} "
        f"post_call_jump_bytes={jump_bytes.hex()} "
        f"integration={fmt(jump_target)} "
        f"post_skip={fmt(CONTACT_SCANNER_SKIP_TARGET)} "
        f"post_skip_bytes={post_skip_bytes.hex()} "
        f"snippet={snippet.hex()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
