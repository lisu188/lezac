#!/usr/bin/env python3
"""Verify static actor-update dispatch gates that compare [bp-31h]."""

from __future__ import annotations

import argparse
from pathlib import Path


IMAGE_SEGMENT = "1000"
ACTOR_UPDATE_START = 0x6053
ACTOR_UPDATE_END = 0x777F
CONTACT_GATE6 = 0x654E
CONTACT_GATE6_SKIP = 0x6552
CONTACT_GATE6_SKIP_TARGET = 0x655B
CONTACT_SCANNER_CALLSITE = 0x6555
CONTACT_SCANNER_ENTRY = 0x5CB0
CONTACT_GATE6_INTEGRATION_JUMP = 0x6558
GATE5_INTEGRATION = 0x65A2
GATE5_INTEGRATION_SKIP = 0x65A6
GATE5_INTEGRATION_SKIP_TARGET = 0x65DA
GATE5_INTEGRATION_JUMP = 0x65D7
GATE5_EXIT = 0x7595
GATE5_EXIT_SKIP = 0x7599
GATE5_EXIT_SKIP_TARGET = 0x759E
GATE5_EXIT_JUMP = 0x759B
SHARED_INTEGRATION = 0x73E5


EXPECTED_BP31_GATES = [
    (CONTACT_GATE6, 0x06),
    (GATE5_INTEGRATION, 0x05),
    (GATE5_EXIT, 0x05),
]


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


def scan_bp31_gates(data: bytes, base: int) -> list[tuple[int, int]]:
    gates: list[tuple[int, int]] = []
    pattern = bytes.fromhex("807ecf")
    for offset in range(ACTOR_UPDATE_START, ACTOR_UPDATE_END - len(pattern)):
        if code_bytes(data, base, offset, len(pattern)) == pattern:
            gates.append((offset, code_byte(data, base, offset + len(pattern))))
    return gates


def require_bytes(
    data: bytes, base: int, offset: int, expected: bytes, label: str
) -> bytes:
    observed = code_bytes(data, base, offset, len(expected))
    if observed != expected:
        raise RuntimeError(
            f"{label} at {fmt(offset)} expected {expected.hex()} got {observed.hex()}"
        )
    return observed


def require_rel8_target(
    data: bytes, base: int, offset: int, expected: int, label: str
) -> int:
    observed = rel8_target(data, base, offset)
    if observed != expected:
        raise RuntimeError(
            f"{label} at {fmt(offset)} targets {fmt(observed)} instead of "
            f"{fmt(expected)}"
        )
    return observed


def require_rel16_target(
    data: bytes, base: int, offset: int, expected: int, label: str
) -> int:
    observed = rel16_target(data, base, offset)
    if observed != expected:
        raise RuntimeError(
            f"{label} at {fmt(offset)} targets {fmt(observed)} instead of "
            f"{fmt(expected)}"
        )
    return observed


def fmt(offset: int) -> str:
    return f"{IMAGE_SEGMENT}:{offset:04X}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check static actor-update [bp-31h] dispatch gates."
    )
    parser.add_argument("repo_root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.repo_root.resolve()
    data = (root / "LEZAC.EXE").read_bytes()
    base = image_base(data)

    gates = scan_bp31_gates(data, base)
    if gates != EXPECTED_BP31_GATES:
        raise RuntimeError(
            "unexpected actor-update [bp-31h] gates: "
            + ",".join(f"{fmt(offset)}={value:02X}" for offset, value in gates)
        )

    gate6_bytes = require_bytes(
        data, base, CONTACT_GATE6, bytes.fromhex("807ecf06750755e858f7e98a0e"),
        "contact gate6 snippet",
    )
    gate6_skip_target = require_rel8_target(
        data, base, CONTACT_GATE6_SKIP, CONTACT_GATE6_SKIP_TARGET, "gate6 skip"
    )
    gate6_call_target = require_rel16_target(
        data,
        base,
        CONTACT_SCANNER_CALLSITE,
        CONTACT_SCANNER_ENTRY,
        "gate6 scanner call",
    )
    gate6_integration_target = require_rel16_target(
        data,
        base,
        CONTACT_GATE6_INTEGRATION_JUMP,
        SHARED_INTEGRATION,
        "gate6 integration jump",
    )

    gate5_integration_bytes = require_bytes(
        data,
        base,
        GATE5_INTEGRATION,
        bytes.fromhex("807ecf057532"),
        "gate5 integration snippet",
    )
    gate5_integration_skip_target = require_rel8_target(
        data,
        base,
        GATE5_INTEGRATION_SKIP,
        GATE5_INTEGRATION_SKIP_TARGET,
        "gate5 integration skip",
    )
    gate5_integration_target = require_rel16_target(
        data,
        base,
        GATE5_INTEGRATION_JUMP,
        SHARED_INTEGRATION,
        "gate5 integration jump",
    )

    gate5_exit_bytes = require_bytes(
        data,
        base,
        GATE5_EXIT,
        bytes.fromhex("807ecf057503e9e101"),
        "gate5 exit snippet",
    )
    gate5_exit_skip_target = require_rel8_target(
        data, base, GATE5_EXIT_SKIP, GATE5_EXIT_SKIP_TARGET, "gate5 exit skip"
    )
    gate5_exit_target = require_rel16_target(
        data, base, GATE5_EXIT_JUMP, ACTOR_UPDATE_END, "gate5 exit jump"
    )

    gate_summary = ",".join(
        f"{fmt(offset)}={value:02X}" for offset, value in gates
    )
    print(
        "actor_update_dispatch_gates=ok "
        f"image_base=0x{base:04x} "
        f"gates={gate_summary} "
        f"gate6={fmt(CONTACT_GATE6)} "
        f"gate6_bytes={gate6_bytes.hex()} "
        f"gate6_skip_target={fmt(gate6_skip_target)} "
        f"gate6_call_target={fmt(gate6_call_target)} "
        f"gate6_integration={fmt(gate6_integration_target)} "
        f"gate5_integration={fmt(GATE5_INTEGRATION)} "
        f"gate5_integration_bytes={gate5_integration_bytes.hex()} "
        f"gate5_integration_skip_target={fmt(gate5_integration_skip_target)} "
        f"gate5_integration_target={fmt(gate5_integration_target)} "
        f"gate5_exit={fmt(GATE5_EXIT)} "
        f"gate5_exit_bytes={gate5_exit_bytes.hex()} "
        f"gate5_exit_skip_target={fmt(gate5_exit_skip_target)} "
        f"gate5_exit_target={fmt(gate5_exit_target)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
