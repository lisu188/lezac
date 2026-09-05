"""Decode live original debris records, excluding uncleared table tails."""

import struct

FIRST_SLOT = 200
LAST_SLOT = 0x640
COUNT_OFFSET = 0x207E
TABLE_OFFSET = 0x2093
STRIDE = 11


def decode_live_debris(segment: bytes) -> tuple[int, list[tuple[int, str]]]:
    if len(segment) != 0x10000:
        raise ValueError("expected one complete original data-segment snapshot")
    last_live = struct.unpack_from("<H", segment, COUNT_OFFSET)[0]
    if not FIRST_SLOT - 1 <= last_live <= LAST_SLOT:
        raise ValueError(f"invalid debris live bound: {last_live}")
    records = []
    for slot in range(FIRST_SLOT, last_live + 1):
        offset = TABLE_OFFSET + slot * STRIDE
        records.append((slot, segment[offset:offset + STRIDE].hex()))
    return last_live, records
