#!/usr/bin/env python3
"""Scan LIVELS.SCH for sites that can seed original falling-debris fragments.

This is the reproducible half of the `natural_forward_debris_writeback_3d2d`
staging analysis. It answers, per shipped level, "how many bomb-object tiles
have a qualifying tile directly above them" -- i.e. how many cells a bomb can
consume such that `1000:370E` is called and a debris fragment is seeded.

Why it matters: level 1 scores ZERO. Its five bomb objects all lack a
qualifying tile above, so a bomb there can never seed a fragment, and therefore
can never reach the forward-debris writeback at `1000:3D2D`. Every historical
level-1 capture sweep for that item was structurally incapable of succeeding.
This scanner exists so that conclusion is auditable and stays true.

The relevant original constraints, from the shipped bytes:
  * `1000:5AFD` clears `DS:661E`, gates the consumed tile to `[0x67, 0x72]`
    (`5B22`/`5B26`), requires the word above to be non-zero (`5B58`) and to
    have bit 15 clear (`5B5D`).
  * `1000:6D57 2b 06 04 c2` seeds from `consumed_index - width`, i.e. the cell
    directly above.
  * `1000:3742/3747` require the qualifying word to be `> 0x3FFF`, so a
    seedable word lies in `[0x4000, 0x7FFF]`.

Self-check: `--self-check` decodes LIVELS.SCH and verifies the decode against
values the port's own loader produces, so a broken decoder cannot silently
report zeros.
"""

from __future__ import annotations

import argparse
from pathlib import Path


BOMB_OBJECT_LO = 0x67
BOMB_OBJECT_HI = 0x72
SEEDABLE_WORD_LO = 0x4000
SEEDABLE_WORD_HI = 0x7FFF

# Level dimensions the port's loader produces, used as a decode self-check.
EXPECTED_DIMENSIONS = [
    (60, 33), (100, 53), (150, 60), (100, 58), (110, 62), (180, 64), (140, 52),
]
EXPECTED_TOTAL_TILES = 47700

# Per-level counts this scanner must reproduce. Level 1 scoring zero is the
# load-bearing result; the rest are recorded so a data change is visible.
EXPECTED_SEEDABLE = [0, 6, 10, 14, 12, 30, 15]
EXPECTED_BOMB_OBJECTS = [5, 30, 54, 60, 102, 142, 65]


def decode_rle3(encoded: bytes, target_size: int) -> list[int]:
    """Exact mirror of the port's decodeLevelRle3 (src/app/app.cpp:988).

    Each command is three bytes: `cmd, a, b`. The high nibble of `cmd` plus one
    is a run length for `a`; the low nibble plus one is a run length for `b`.
    """
    out = [0] * (target_size + 32)
    pos = 0
    i = 0

    def run(value: int, length: int) -> None:
        nonlocal pos
        end = min(pos + length, len(out) - 1)
        for k in range(pos, end + 1):
            out[k] = value
        pos += length

    while pos < target_size and i + 2 < len(encoded):
        cmd = encoded[i]; a = encoded[i + 1]; b = encoded[i + 2]
        i += 3
        run(a, (cmd >> 4) + 1)
        if pos >= target_size:
            break
        run(b, (cmd & 0x0F) + 1)
    return out[:target_size]


def load_levels(path: Path) -> list[dict]:
    """Exact mirror of the port's loadRawLevels (src/app/app.cpp:1474)."""
    data = path.read_bytes()
    levels = []
    off = 0

    def u8() -> int:
        nonlocal off
        v = data[off]; off += 1; return v

    def u16() -> int:
        nonlocal off
        v = int.from_bytes(data[off:off + 2], "little"); off += 2; return v

    def blob(n: int) -> bytes:
        nonlocal off
        v = data[off:off + n]; off += n; return v

    def records(size: int) -> int:
        nonlocal off
        count = u8()
        off += count * size
        return count

    while off < len(data):
        width = u16(); height = u16()
        if not (0 < width <= 300 and 0 < height <= 200):
            raise RuntimeError("invalid raw level dimensions")
        objective = u8()
        required_bonus = u16()
        required_destruction = u8()
        count = width * height
        tiles = decode_rle3(blob(u16()), count)
        word_bytes = decode_rle3(blob(u16()), count * 2)
        words = [word_bytes[i] | (word_bytes[i + 1] << 8)
                 for i in range(0, count * 2, 2)]
        field_a = u16(); field_b = u16()
        spawners = records(30)
        records(7)
        records(14)
        levels.append({
            "width": width, "height": height, "objective": objective,
            "required_bonus": required_bonus,
            "required_destruction": required_destruction,
            "field_a": field_a, "field_b": field_b,
            "spawners": spawners, "tiles": tiles, "words": words,
        })
    return levels


def scan(level: dict) -> tuple[int, int]:
    """Return (bomb object tiles, tiles that can seed a debris fragment)."""
    width = level["width"]
    height = level["height"]
    tiles = level["tiles"]
    words = level["words"]
    objects = 0
    seedable = 0
    for y in range(height):
        for x in range(width):
            index = y * width + x
            tile = tiles[index]
            if not (BOMB_OBJECT_LO <= tile <= BOMB_OBJECT_HI):
                continue
            objects += 1
            if y == 0:
                continue
            above = words[index - width]
            if SEEDABLE_WORD_LO <= above <= SEEDABLE_WORD_HI:
                seedable += 1
    return objects, seedable


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan LIVELS.SCH for original debris-seeding sites.")
    parser.add_argument("levels", nargs="?", type=Path,
                        default=Path(__file__).resolve().parent.parent / "LIVELS.SCH")
    parser.add_argument("--self-check", action="store_true",
                        help="verify the decode against the port's own values")
    args = parser.parse_args()

    levels = load_levels(args.levels)
    if len(levels) != 7:
        raise RuntimeError(f"expected 7 shipped levels, decoded {len(levels)}")

    dims = [(lv["width"], lv["height"]) for lv in levels]
    total_tiles = sum(w * h for w, h in dims)
    if dims != EXPECTED_DIMENSIONS or total_tiles != EXPECTED_TOTAL_TILES:
        raise RuntimeError(
            f"level decode mismatch: dims={dims} total_tiles={total_tiles}")

    if args.self_check:
        # Level 1's objective tile 108 must occur exactly once, at tile (27,15).
        first = levels[0]
        hits = [(i % first["width"], i // first["width"])
                for i, t in enumerate(first["tiles"]) if t == 108]
        if hits != [(27, 15)]:
            raise RuntimeError(f"level-1 objective tile spot-check failed: {hits}")
        print("scan_livels_debris_sites_self_check=ok "
              f"levels={len(levels)} total_tiles={total_tiles} "
              "l1_objective_tile=108@27,15")
        return 0

    objects = []
    seedable = []
    for level in levels:
        obj, seed = scan(level)
        objects.append(obj)
        seedable.append(seed)

    if objects != EXPECTED_BOMB_OBJECTS or seedable != EXPECTED_SEEDABLE:
        raise RuntimeError(
            f"scan drifted: bomb_objects={objects} seedable={seedable}")

    # The load-bearing assertion: no bomb on level 1 can seed a fragment.
    if seedable[0] != 0:
        raise RuntimeError("level 1 unexpectedly has a debris-seeding site")
    # And the scan is not an empty query -- it must find bomb objects at all.
    if sum(objects) == 0:
        raise RuntimeError("scan found no bomb-object tiles; decoder is broken")

    print(
        "livels_debris_sites=ok "
        f"levels={len(levels)} total_tiles={total_tiles} "
        f"bomb_objects={','.join(str(v) for v in objects)} "
        f"bomb_objects_total={sum(objects)} "
        f"seedable={','.join(str(v) for v in seedable)} "
        f"seedable_total={sum(seedable)} "
        "level1_seedable=0 "
        "level1_capture_viable=0 "
        "visual_claim=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
