#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src"


def read(path: str) -> bytes:
    return (ROOT / path).read_bytes()


def vga6_to_8(v: int) -> int:
    return ((v << 2) | (v >> 4)) & 0xFF


def bytes_to_hex_rows(blob: bytes, row_width: int) -> List[str]:
    return [" ".join(f"{b:02x}" for b in blob[i : i + row_width]) for i in range(0, len(blob), row_width)]


def le16(data: bytes, off: int) -> int:
    return data[off] | (data[off + 1] << 8)


def le32(data: bytes, off: int) -> int:
    return data[off] | (data[off + 1] << 8) | (data[off + 2] << 16) | (data[off + 3] << 24)


def decode_level_rle3(encoded: bytes, target_size: int) -> bytes:
    out = bytearray(target_size + 32)
    pos = 0
    i = 0

    def run(value: int, length: int) -> None:
        nonlocal pos
        end = min(pos + length, len(out) - 1)
        for idx in range(pos, end + 1):
            out[idx] = value
        pos += length

    while pos < target_size and i + 2 < len(encoded):
        cmd = encoded[i]
        a = encoded[i + 1]
        b = encoded[i + 2]
        i += 3
        run(a, (cmd >> 4) + 1)
        if pos >= target_size:
            break
        run(b, (cmd & 0x0F) + 1)

    return bytes(out[:target_size])


def write_json(filename: str, obj: object) -> None:
    out_path = OUT / filename
    out_path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def export_palette() -> None:
    data = read("BOMPAL.PAL")
    if len(data) != 768:
        raise ValueError("BOMPAL.PAL has unexpected size")
    colors = []
    for i in range(256):
        r, g, b = data[i * 3 : i * 3 + 3]
        colors.append({"index": i, "vga6": [r, g, b], "rgb8": [vga6_to_8(r), vga6_to_8(g), vga6_to_8(b)]})
    write_json("BOMPAL.PAL.json", {"file": "BOMPAL.PAL", "type": "vga_palette_256", "colors": colors})


def export_background() -> None:
    data = read("SFONLEF.ZBG")
    if len(data) < 768:
        raise ValueError("SFONLEF.ZBG too small")

    pal = []
    for i in range(256):
        r, g, b = data[i * 3 : i * 3 + 3]
        pal.append({"index": i, "rgb8": [vga6_to_8(r), vga6_to_8(g), vga6_to_8(b)]})

    pixels = bytearray()
    off = 768
    while off < len(data):
        cmd = data[off]
        off += 1
        if cmd >= 0xC0:
            if off >= len(data):
                raise ValueError("truncated RLE run")
            pixels.extend([data[off]] * (cmd & 0x3F))
            off += 1
        else:
            pixels.append(cmd)

    width, height = 321, 388
    if len(pixels) != width * height:
        raise ValueError(f"unexpected background decoded size {len(pixels)}")

    rows = bytes_to_hex_rows(bytes(pixels), width)
    write_json(
        "SFONLEF.ZBG.json",
        {
            "file": "SFONLEF.ZBG",
            "type": "indexed_background",
            "width": width,
            "height": height,
            "palette": pal,
            "pixel_rows_hex": rows,
        },
    )


def export_tiles() -> None:
    data = read("CARO.CAR")
    if len(data) < 2:
        raise ValueError("CARO.CAR too small")
    count = (data[0] << 8) | data[1]
    payload = data[2:]
    expected = count * 64
    if len(payload) != expected:
        raise ValueError("CARO.CAR unexpected size")
    tiles = []
    for i in range(count):
        tile = payload[i * 64 : (i + 1) * 64]
        tiles.append({"index": i, "rows_hex": bytes_to_hex_rows(tile, 8)})
    write_json("CARO.CAR.json", {"file": "CARO.CAR", "type": "tile_bank", "tile_count": count, "tiles": tiles})


def export_sprites(path: str) -> None:
    data = read(path)
    off = 0
    count = data[off]
    off += 1
    sprites = []
    for i in range(count):
        w = data[off]
        h = data[off + 1]
        off += 2
        size = w * h
        px = data[off : off + size]
        off += size
        sprites.append({"index": i, "width": w, "height": h, "rows_hex": bytes_to_hex_rows(px, w)})
    if off != len(data):
        raise ValueError(f"{path} trailing data")
    write_json(f"{path}.json", {"file": path, "type": "sprite_bank", "sprite_count": count, "sprites": sprites})


def export_records() -> None:
    data = read("RECS.DAT")
    off = 0
    count = data[off]
    off += 1
    records = []
    for i in range(count):
        score = le32(data, off)
        off += 4
        level = data[off]
        off += 1
        raw = data[off : off + 8]
        off += 8
        name = raw.decode("latin1").replace(":", " ").rstrip()
        records.append(
            {
                "index": i,
                "score": score,
                "level": level,
                "encoded_name": raw.decode("latin1"),
                "decoded_name": name or "nessuno",
            }
        )
    if off != len(data):
        raise ValueError("RECS.DAT trailing bytes")
    write_json("RECS.DAT.json", {"file": "RECS.DAT", "type": "high_scores", "record_count": count, "records": records})


def export_son() -> None:
    data = read("PROEFS.SON")
    size = le16(data, 0)
    payload = data[2:]
    if size == 0 or len(payload) % size != 0:
        raise ValueError("PROEFS.SON invalid fixed record size")
    records = []
    for i in range(0, len(payload), size):
        rec = payload[i : i + size]
        records.append({"index": i // size, "bytes_hex": " ".join(f"{b:02x}" for b in rec)})
    write_json(
        "PROEFS.SON.json",
        {"file": "PROEFS.SON", "type": "sound_bank", "record_size": size, "record_count": len(records), "records": records},
    )


def export_gran() -> None:
    data = read("GRAN.MST")
    rec_size = 57
    if len(data) != 7 * rec_size:
        raise ValueError("GRAN.MST unexpected size")
    records = []
    for i in range(7):
        rec = data[i * rec_size : (i + 1) * rec_size]
        records.append({"index": i, "bytes_hex": " ".join(f"{b:02x}" for b in rec)})
    write_json("GRAN.MST.json", {"file": "GRAN.MST", "type": "gran_records", "record_size": rec_size, "records": records})


def parse_spawner(rec: bytes) -> dict:
    return {
        "x": le16(rec, 0),
        "y": le16(rec, 2),
        "tileIndex": le16(rec, 4),
        "savedWordOrLink": le16(rec, 6),
        "enabled": rec[8],
        "spawnBudget": rec[9],
        "liveAllowance": rec[10],
        "monsterKind": rec[11],
        "param0Base": le16(rec, 12),
        "param0Range": le16(rec, 14),
        "param1Base": le16(rec, 16),
        "param1Range": le16(rec, 18),
        "param2Base": le16(rec, 20),
        "param2Range": le16(rec, 22),
        "randomBase": rec[24],
        "randomRange": rec[25],
        "spawnArg": rec[26],
        "cooldown": rec[27],
        "cooldownReset": rec[28],
        "animationDelay": rec[29],
    }


def parse_portal(rec: bytes) -> dict:
    return {"key": le16(rec, 0), "x": le16(rec, 2), "y": le16(rec, 4), "marker": rec[6]}


def parse_trigger(rec: bytes) -> dict:
    return {
        "wordRangeFirst": le16(rec, 0),
        "wordRangeLast": le16(rec, 2),
        "triggerKey": le16(rec, 4),
        "from": list(rec[6:10]),
        "to": list(rec[10:14]),
    }


def get_fixed_records(data: bytes, off: int, width: int):
    count = data[off]
    off += 1
    recs = []
    for _ in range(count):
        recs.append(data[off : off + width])
        off += width
    return recs, off


def export_levels() -> None:
    data = read("LIVELS.SCH")
    levels = []
    off = 0
    while off < len(data):
        level_start = off
        width = le16(data, off)
        off += 2
        height = le16(data, off)
        off += 2
        objective_tile = data[off]
        off += 1
        required_bonus = le16(data, off)
        off += 2
        required_destruction = data[off]
        off += 1

        tile_len = le16(data, off)
        off += 2
        tile_encoded = data[off : off + tile_len]
        off += tile_len

        tile_count = width * height
        tiles = decode_level_rle3(tile_encoded, tile_count)

        word_len = le16(data, off)
        off += 2
        word_encoded = data[off : off + word_len]
        off += word_len
        word_layer_bytes = decode_level_rle3(word_encoded, tile_count * 2)
        words = [le16(word_layer_bytes, i) for i in range(0, len(word_layer_bytes), 2)]

        field_a = le16(data, off)
        off += 2
        field_b = le16(data, off)
        off += 2

        spawners_raw, off = get_fixed_records(data, off, 30)
        portals_raw, off = get_fixed_records(data, off, 7)
        triggers_raw, off = get_fixed_records(data, off, 14)

        starting_objectives = sum(1 for t in tiles if t == objective_tile)
        starting_destructible = sum(1 for t in tiles if t > 1 and t != 0xFF and t != objective_tile)

        levels.append(
            {
                "fileOffset": level_start,
                "width": width,
                "height": height,
                "objectiveTile": objective_tile,
                "requiredBonus": required_bonus,
                "requiredDestruction": required_destruction,
                "tileEncodedSize": tile_len,
                "wordEncodedSize": word_len,
                "fieldA": field_a,
                "fieldB": field_b,
                "startingObjectiveTiles": starting_objectives,
                "startingDestructibleTiles": starting_destructible,
                "tiles_rows_hex": bytes_to_hex_rows(tiles, width),
                "word_rows_hex": [
                    " ".join(f"{w:04x}" for w in words[row * width : (row + 1) * width])
                    for row in range(height)
                ],
                "monsterSpawners": [parse_spawner(r) for r in spawners_raw],
                "portals": [parse_portal(r) for r in portals_raw],
                "tileTriggers": [parse_trigger(r) for r in triggers_raw],
            }
        )

    write_json("LIVELS.SCH.json", {"file": "LIVELS.SCH", "type": "level_bank", "level_count": len(levels), "levels": levels})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    export_palette()
    export_background()
    export_tiles()
    export_sprites("BOMOMIMK.SPR")
    export_sprites("PROVA.SPR")
    export_sprites("FONTS.SPR")
    export_records()
    export_son()
    export_gran()
    export_levels()
    print("Exported JSON resources into", OUT)


if __name__ == "__main__":
    main()
