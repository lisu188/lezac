#!/usr/bin/env python3
"""Verify the static actor/contact scanner callsite control-flow context."""

from __future__ import annotations

import argparse
from pathlib import Path


IMAGE_SEGMENT = "1000"
ACTOR_UPDATE_START = 0x6053
ACTOR_UPDATE_END = 0x777F
CONTACT_SCANNER_ENTRY = 0x5CB0
CONTACT_SCANNER_GATE = 0x654E
CONTACT_SCANNER_SKIP = 0x6552
CONTACT_SCANNER_CALLSITE = 0x6555
CONTACT_SCANNER_AFTER_CALL = 0x6558
CONTACT_SCANNER_SKIP_TARGET = 0x655B
SIBLING_GATE = 0x65A2
SIBLING_SKIP = 0x65A6
SIBLING_MOTION_BRANCH = 0x65BD
SIBLING_END_BRANCH = 0x65CE
SIBLING_END_JUMP = 0x65D4
SIBLING_INTEGRATION_JUMP = 0x65D7
SIBLING_SKIP_TARGET = 0x65DA
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


def scan_near_jumps(data: bytes, base: int, start: int, end: int, target: int) -> list[int]:
    hits: list[int] = []
    for offset in range(start, end - 2):
        if code_byte(data, base, offset) != 0xE9:
            continue
        if rel16_target(data, base, offset) == target:
            hits.append(offset)
    return hits


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
    sibling_gate_bytes = require_bytes(
        data, base, SIBLING_GATE, bytes.fromhex("807ecf057532"), "sibling gate"
    )
    sibling_motion_branch_bytes = require_bytes(
        data,
        base,
        SIBLING_MOTION_BRANCH,
        bytes.fromhex("7518"),
        "sibling motion branch",
    )
    sibling_end_branch_bytes = require_bytes(
        data,
        base,
        SIBLING_END_BRANCH,
        bytes.fromhex("7504"),
        "sibling end branch",
    )
    sibling_end_jump_bytes = require_bytes(
        data,
        base,
        SIBLING_END_JUMP,
        bytes.fromhex("e9a811"),
        "sibling end jump",
    )
    sibling_integration_jump_bytes = require_bytes(
        data,
        base,
        SIBLING_INTEGRATION_JUMP,
        bytes.fromhex("e90b0e"),
        "sibling integration jump",
    )

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
    sibling_skip_target = rel8_target(data, base, SIBLING_SKIP)
    if sibling_skip_target != SIBLING_SKIP_TARGET:
        raise RuntimeError(
            f"sibling skip branch targets {fmt(sibling_skip_target)} instead of "
            f"{fmt(SIBLING_SKIP_TARGET)}"
        )
    sibling_motion_target = rel8_target(data, base, SIBLING_MOTION_BRANCH)
    if sibling_motion_target != SIBLING_INTEGRATION_JUMP:
        raise RuntimeError(
            f"sibling motion branch targets {fmt(sibling_motion_target)} instead "
            f"of {fmt(SIBLING_INTEGRATION_JUMP)}"
        )
    sibling_end_branch_target = rel8_target(data, base, SIBLING_END_BRANCH)
    if sibling_end_branch_target != SIBLING_END_JUMP:
        raise RuntimeError(
            f"sibling end branch targets {fmt(sibling_end_branch_target)} instead "
            f"of {fmt(SIBLING_END_JUMP)}"
        )
    sibling_end_target = rel16_target(data, base, SIBLING_END_JUMP)
    if sibling_end_target != ACTOR_UPDATE_END:
        raise RuntimeError(
            f"sibling end jump targets {fmt(sibling_end_target)} instead of "
            f"{fmt(ACTOR_UPDATE_END)}"
        )
    sibling_integration_target = rel16_target(data, base, SIBLING_INTEGRATION_JUMP)
    if sibling_integration_target != SHARED_INTEGRATION:
        raise RuntimeError(
            f"sibling integration jump targets {fmt(sibling_integration_target)} "
            f"instead of {fmt(SHARED_INTEGRATION)}"
        )
    integration_jumps = scan_near_jumps(
        data, base, ACTOR_UPDATE_START, ACTOR_UPDATE_END, SHARED_INTEGRATION
    )
    expected_integration_jumps = [CONTACT_SCANNER_AFTER_CALL, SIBLING_INTEGRATION_JUMP]
    if integration_jumps != expected_integration_jumps:
        raise RuntimeError(
            "unexpected direct jumps to shared integration: "
            + ",".join(fmt(offset) for offset in integration_jumps)
        )

    snippet = code_bytes(data, base, CONTACT_SCANNER_GATE, 17)
    sibling_snippet = code_bytes(data, base, SIBLING_GATE, 0x38)
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
        f"snippet={snippet.hex()} "
        f"sibling_gate={fmt(SIBLING_GATE)} "
        f"sibling_gate_bytes={sibling_gate_bytes.hex()} "
        "sibling_gate_value=0x05 "
        f"sibling_skip_target={fmt(sibling_skip_target)} "
        f"sibling_motion_branch={fmt(SIBLING_MOTION_BRANCH)} "
        f"sibling_motion_branch_bytes={sibling_motion_branch_bytes.hex()} "
        f"sibling_motion_target={fmt(sibling_motion_target)} "
        f"sibling_end_branch={fmt(SIBLING_END_BRANCH)} "
        f"sibling_end_branch_bytes={sibling_end_branch_bytes.hex()} "
        f"sibling_end_jump={fmt(SIBLING_END_JUMP)} "
        f"sibling_end_jump_bytes={sibling_end_jump_bytes.hex()} "
        f"sibling_end_target={fmt(sibling_end_target)} "
        f"sibling_integration_jump={fmt(SIBLING_INTEGRATION_JUMP)} "
        f"sibling_integration_jump_bytes={sibling_integration_jump_bytes.hex()} "
        f"sibling_integration_target={fmt(sibling_integration_target)} "
        "integration_jumps="
        f"{','.join(fmt(offset) for offset in integration_jumps)} "
        f"sibling_snippet={sibling_snippet.hex()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
