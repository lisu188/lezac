#!/usr/bin/env python3
"""Keep stale captured debris bytes outside the live-record decoder."""

from pathlib import Path
import struct

from original_debris_table import (
    COUNT_OFFSET, FIRST_SLOT, LAST_SLOT, STRIDE, TABLE_OFFSET, decode_live_debris,
)


def main() -> int:
    fixture = Path(__file__).resolve().parent.parent / "tests/fixtures/debris_rest_original.txt"
    rows = {
        fields["case"]: fields
        for line in fixture.read_text(encoding="ascii").splitlines()
        if line.startswith("case=")
        for fields in [dict(token.split("=", 1) for token in line.split())]
    }
    for name in ("rest_99", "rest_99_shift", "rest_99_double"):
        fields = rows[name]
        segment = bytearray(0x10000)
        last_live = int(fields["live_slot_after"])
        struct.pack_into("<H", segment, COUNT_OFFSET, last_live)
        expected = []
        if fields["after_debris"] != "none":
            expected = [(FIRST_SLOT + i, raw) for i, raw in enumerate(fields["after_debris"].split(","))]
        for slot, raw in [*expected, (last_live + 1, fields["inactive_tail"])]:
            offset = TABLE_OFFSET + slot * STRIDE
            segment[offset:offset + STRIDE] = bytes.fromhex(raw)
        if decode_live_debris(segment) != (last_live, expected):
            raise RuntimeError(f"{name}: inactive tail was decoded as live")

    segment = bytearray(0x10000)
    for last_live in (FIRST_SLOT + 80, LAST_SLOT):
        struct.pack_into("<H", segment, COUNT_OFFSET, last_live)
        bound, records = decode_live_debris(segment)
        if bound != last_live or len(records) != last_live - FIRST_SLOT + 1 or records[-1][0] != last_live:
            raise RuntimeError("live table was truncated to the historical 80-slot scan")

    for last_live in (FIRST_SLOT - 2, LAST_SLOT + 1):
        struct.pack_into("<H", segment, COUNT_OFFSET, last_live)
        try:
            decode_live_debris(segment)
        except ValueError:
            pass
        else:
            raise RuntimeError("invalid live bound was accepted")
    try:
        decode_live_debris(bytes(16))
    except ValueError:
        pass
    else:
        raise RuntimeError("truncated snapshot was accepted")
    print("original_debris_table=ok stale_tail_cases=3 full_live_range=1 invalid_bounds=2 truncated_guard=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
