#!/usr/bin/env python3
"""Validate original bomb damage observations, without claiming C++ replay parity."""

from pathlib import Path


def check(source):
    header = False
    descriptors = False
    complete = False
    cases = {}
    name = None
    start = 0
    for line in source.splitlines():
        if not line or line.startswith("#"):
            continue
        if complete:
            raise ValueError("data after completion")
        if not header and not line.startswith("capture="):
            raise ValueError("missing provenance")
        fields = {}
        for token in line.split():
            if "=" in token:
                key, value = token.split("=", 1)
                if key in fields:
                    raise ValueError("duplicate field")
                fields[key] = value
        if line.startswith("capture="):
            if header or fields != {"capture": "bomb_actor_order_original_v1", "seeded": "1",
                                    "temp_copy": "1", "player": "240,168", "spawners": "0"}:
                raise ValueError("invalid provenance")
            header = True
        elif line.startswith("sprites "):
            if descriptors or cases or len(bytes.fromhex(fields["descriptors"])) != 92 * 4:
                raise ValueError("invalid descriptors")
            descriptors = True
        elif line.startswith("case "):
            if not descriptors or name is not None or fields["name"] not in ("bomb_first", "monster_first") or fields["name"] in cases:
                raise ValueError("invalid case")
            name = fields["name"]
            cases[name] = []
            start = int(fields["frame"])
            raw = bytes.fromhex(fields["raw"])
            bomb = bytes.fromhex(fields["bomb"])
            if start % 2 != 1 or raw != bytes.fromhex("010200010200000000009a004e0000000000000006032c2c2d03030101000000000000001f00"):
                raise ValueError("invalid monster seed or frame parity")
            if fields["x"] != "336" or fields["y"] != "174" or fields["rng"] != "12345678":
                raise ValueError("invalid monster position or RNG seed")
            expected_bomb = bytearray(38)
            expected_bomb[0], expected_bomb[1], expected_bomb[0x14], expected_bomb[0x15] = 13, 3, 8, 2
            if bomb != expected_bomb or fields["bomb_x"] != "336" or fields["bomb_y"] != "176" or fields["cell"] != "-1":
                raise ValueError("invalid bomb seed")
        elif line.startswith("tick "):
            if name is None:
                raise ValueError("tick outside case")
            index = len(cases[name])
            if int(fields["sample"]) != index or int(fields["frame"]) != start + index:
                raise ValueError("nonconsecutive tick")
            actor, visual = (bytes.fromhex(part) for part in fields["target"].split(":"))
            if len(actor) != 38 or len(visual) != 8 or actor[0] != 1 or actor[1] != 2 or actor[0x15] != 3:
                raise ValueError("invalid target")
            others = [] if fields["others"] == "-" else fields["others"].split(",")
            if not 1 <= int(fields["count"]) <= 30 or int(fields["count"]) != 1 + len(others):
                raise ValueError("invalid live actor count")
            for entry in others:
                raw, displayed = (bytes.fromhex(part) for part in entry.split(":"))
                if len(raw) != 38 or len(displayed) != 8:
                    raise ValueError("invalid other actor")
            cells = {}
            if fields["map"] != "-":
                for cell in fields["map"].split(","):
                    key, value = cell.split(":")
                    key = int(key)
                    if key in cells or not 0 <= key < 1980:
                        raise ValueError("invalid map delta")
                    cells[key] = int(value, 16)
                    if not 0 <= cells[key] <= 255:
                        raise ValueError("invalid map byte")
            # The target remains fixed, so its pre-motion footprint is stable.
            if visual[:4] != bytes.fromhex("5001ae00") or actor[6:10] != bytes(4):
                raise ValueError("target moved")
            damage = 2 * sum(cells.get(cell) == 0x75 for cell in (1302, 1303, 1362, 1363))
            previous_hp = cases[name][-1][0] if index else 31
            if actor[0x24] != previous_hp - damage:
                raise ValueError("HP does not match observed flame footprint")
            cases[name].append((actor[0x24], damage, cells, actor[0x16:0x1d], visual[4:]))
        elif line.startswith("end "):
            if name is None or fields["samples"] != "25" or len(cases[name]) != 25:
                raise ValueError("incomplete case")
            name = None
        elif line.startswith("complete "):
            if name is not None or fields["cases"] != "2" or set(cases) != {"bomb_first", "monster_first"}:
                raise ValueError("incomplete capture")
            complete = True
        else:
            raise ValueError("unexpected row")
    if not complete:
        raise ValueError("missing completion")
    expected_hp = [31, 31, 27, 21] + [19] * 21
    if [row[0] for row in cases["bomb_first"]] != expected_hp or cases["bomb_first"] != cases["monster_first"]:
        raise ValueError("unexpected ordered damage trace")


def main():
    root = Path(__file__).resolve().parent.parent
    source = (root / "tests/fixtures/bomb_actor_order_original.txt").read_text(encoding="ascii")
    check(source)
    check(source.replace("\n", "\r\n"))
    mutants = [source.rsplit("complete ", 1)[0]]
    mutants.extend("\n".join(row for row in source.splitlines() if not row.startswith(prefix))
                   for prefix in ("capture=", "sprites "))
    mutants.extend((source.replace("x=336 y=174", "x=335 y=174", 1),
                    source.replace("rng=12345678", "rng=12345679", 1)))
    rows = source.splitlines()
    index = next(i for i, row in enumerate(rows) if row.startswith("tick sample=2 "))
    fields = dict(token.split("=", 1) for token in rows[index].split()[1:])
    for key, value in (("target", fields["target"][:72] + "1a" + fields["target"][74:]),
                       ("map", fields["map"].replace("1302:75", "1302:00")),
                       ("frame", str(int(fields["frame"]) + 1))):
        modified = dict(fields, **{key: value})
        mutant = rows[:]
        mutant[index] = "tick " + " ".join(f"{k}={v}" for k, v in modified.items())
        mutants.append("\n".join(mutant))
    for mutant in mutants:
        try:
            check(mutant)
        except (ValueError, KeyError):
            continue
        raise RuntimeError("invalid bomb observation was accepted")
    print("bomb_actor_order_observation=ok cases=2 samples=50 first_damage_sample=2 damage=4,6,2 total_damage=12 "
          "same_phase=1 mutations_rejected=8 cpp_damage_claim=0")


if __name__ == "__main__":
    main()
