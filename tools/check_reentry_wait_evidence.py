#!/usr/bin/env python3
"""Validate the original shared-fallback trace, not a C++ gameplay replay."""

import argparse
import copy
from functools import lru_cache
import hashlib
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/boss_reentry_wait_original_level7.txt"
INTRO = ROOT / "tests/fixtures/boss_reentry_wait_original_intro.png"
EXPECTED_HASH = "e26aa4f34969721fecc384ba3cd9932d506789a33465845418635e4c0f876ce8"
VIEW_SAMPLES = (0, 1, 2, 3, 5, 10, 20, 39, 59, 79, 99, 119, 139, 159, 179,
                199, 239, 259, 279, 319, 379, 419)


def require(condition, message):
    if not condition:
        raise ValueError(message)


@lru_cache(maxsize=4096)
def raw(value, count):
    require(len(value) == count * 2 and all(c in "0123456789abcdef" for c in value), "invalid raw bytes")
    return bytes.fromhex(value)


def word(data, at):
    return struct.unpack_from("<H", data, at)[0]


@lru_cache(maxsize=32)
def pixels(value, count):
    result = bytearray()
    for run in value.split(","):
        length, color = run.split(":")
        length = int(length)
        require(0 < length <= count - len(result), "invalid pixel run")
        result.extend(raw(color, 1) * length)
    require(len(result) == count, "incomplete pixels")
    return bytes(result)


def parse(source):
    rows = []
    for line in source.splitlines():
        if not line or line.startswith("#"):
            continue
        tokens = line.split()
        tag = tokens[0]
        fields = {}
        for token in tokens if "=" in tag else tokens[1:]:
            key, value = token.split("=", 1)
            require(key not in fields, "duplicate field")
            fields[key] = value
        rows.append((tag, fields))
    return rows


def validate(rows, intro_bytes):
    require(rows[0][0] == "capture=boss_mass_probe_v1", "capture schema")
    require(rows[0][1] == dict(capture="boss_mass_probe_v1", level="7", temp_copy="1", seeded_case_boundary="1",
                             seeded_head_hp="0", seeded_head_lives="1", seeded_bomb="1", seeded_weapon="3",
                             per_tick_actor_seed="0", natural_campaign="0"), "capture provenance")
    require([tag for tag, _ in rows[1:5]] == ["map", "backdrop", "sprites", "case"], "initial records")
    map_fields = rows[1][1]
    require(map_fields["width"] == "140" and map_fields["height"] == "52", "map dimensions")
    raw(map_fields["bytes"], 7280)
    raw(map_fields["words"], 14560)
    pixels(rows[2][1]["bytes"], 60000)
    descriptors = raw(rows[3][1]["descriptors"], 368)
    initial = rows[4][1]
    require(initial["name"] == "massive_even" and initial["frame"] == "100" and
            initial["fallback"] == "0" and initial["resets"] == "0", "case seed")
    require(initial["lives"] == "99" and initial["player_state"] == "1", "initial player")
    require(struct.unpack("<6H", raw(initial["regs"], 12)) == (0x1A2, 0xC44, 0xC44, 0x18B3, 0x3FE4, 0x3FFE), "case registers")
    ticks, views, boundaries = [], [], []
    death, waiting, restart = None, None, None
    intro_seen = False
    expected_view = False
    for tag, f in rows[5:-2]:
        sample = int(f["sample"])
        if tag == "view":
            require(expected_view and sample == len(ticks) - 1, "view ordering")
            data = pixels(f["pixels"], 312 * 152)
            require(len(set(data)) >= 16 and hashlib.sha256(data).hexdigest() == f["indexed_sha256"], "view pixels/hash")
            require(f["source"] == "8" and f["destination"] == "1284", "view destination")
            views.append(sample)
            expected_view = False
            continue
        require(not expected_view and sample == len(ticks), "record ordering")
        if tag == "boundary":
            stage = f["stage"]
            if waiting is None:
                require(death is not None and sample == death + 60 and stage == "fallback_increment", "first waiting boundary")
                waiting = sample
            require(stage in {"fallback_increment", "fallback_promote", "level_init", "intro_wait", "intro_ack"}, "boundary stage")
            require(f["frame"] == str(100 + sample) and f["gate"] == "1", "boundary frame/gate")
            regs = struct.unpack("<6H", raw(f["regs"], 12))
            es, sp, bp = (0x40, 0x3DE0, 0x3FF2) if stage in {"intro_wait", "intro_ack"} else (0xC44, 0x3FE2 if stage == "level_init" else 0x3FE4, 0x3FFE)
            require(regs == (0x1A2, 0xC44, es, 0x18B3, sp, bp), "boundary registers")
            p1, flags = raw(f["p1"], 38), raw(f["flags"], 9)
            raw(f["p2"], 38)
            raw(f["visuals"], 16)
            raw(f["rng"], 4)
            require(waiting is not None and word(p1, 16) == (waiting - sample) % 65536, "boundary countdown")
            require(p1[21] == 2 and p1[36] == 100 and flags[2] == 0 and flags[5] == 98, "boundary player/lives")
            if stage == "fallback_increment":
                require(restart is None and int(f["counter"]) == sample - waiting < 230 and flags[1] == 2, "shared counter sequence")
            else:
                require(sample == waiting + 229 and f["counter"] == "230", "fallback threshold")
                require(flags[1] == (2 if stage == "fallback_promote" else 1), "fallback promotion")
                previous = boundaries[-1]
                require(all(f[key] == previous[key] for key in ("p1", "p2", "visuals")), "premature actor reset")
                if stage != "intro_wait":
                    require(f["rng"] == previous["rng"], "unexpected boundary RNG change")
                if stage == "intro_ack":
                    require(intro_seen, "ack without intro capture")
                    restart = sample
            boundaries.append(f)
        elif tag == "intro":
            require(not intro_seen and boundaries[-1]["stage"] == "intro_wait", "intro order")
            require(Path(f["file"]).name == f["file"] and "\\" not in f["file"], "unsafe intro name")
            require(hashlib.sha256(intro_bytes).hexdigest() == f["sha256"], "intro screenshot hash")
            require(intro_bytes[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack_from(">II", intro_bytes, 16) == (320, 200), "intro screenshot format")
            intro_seen = True
        elif tag == "tick":
            require(f["frame"] == str(101 + sample) and f["control"] == "idle", "tick clock/control")
            require(struct.unpack("<6H", raw(f["regs"], 12)) == (0x1A2, 0xC44, 0xA000, 0x18B3, 0x3FE4, 0x3FFE), "tick registers")
            p1 = raw(f["p1"], 38)
            visual = raw(f["player"], 8)
            if death is None and p1[21] == 2:
                death = sample
            if death is not None and sample == death + 60:
                waiting = sample
            input_missing = death is not None and sample > death and (restart is None or sample <= restart)
            require((f["input_regs"] == "-") == input_missing, "death/restart input boundary")
            if not input_missing:
                regs = struct.unpack("<6H", raw(f["input_regs"], 12))
                require(regs[:2] == (0x1A2, 0xC44) and regs[3:] == (0x18B3, 0x3FA2, 0x3FEE), "input registers")
            require(int(f["resets"]) == int(restart is not None), "reset count")
            if death is not None and restart is None:
                require(p1[21] == 2 and p1[36] == 100 and word(p1, 16) == (60 + death - sample) % 65536, "raw death/wait countdown")
            if waiting is not None and restart is None:
                require(f["player_state"] == "2" and f["lives"] == "98" and f["energy"] == "100", "waiting player")
                require(int(f["fallback"]) == sample - waiting + 1 and boundaries[-1]["stage"] == "fallback_increment", "waiting fallback")
                require(visual[:4] == struct.pack("<HH", 840, 328) and visual[4:] == descriptors[39 * 4:40 * 4], "waiting placement/descriptor")
                if sample > waiting:
                    previous = raw(ticks[-1]["p1"], 38)
                    require(p1[:16] + p1[18:] == previous[:16] + previous[18:], "waiting actor changed")
            elif restart is None:
                require(f["fallback"] == "0" and f["player_state"] == "1" and f["lives"] == "99", "active/death fallback reset")
            else:
                require(f["player_state"] == "1" and f["lives"] == "98" and p1[21] == 0 and p1[36] == 100, "restarted player")
                require(word(p1, 16) == (-229) % 65536 and int(f["fallback"]) == (230 if sample == restart else 0), "post-restart retained countdown/counter")
                require(f["map"] == "-" and f["flames"] == "-" and f["count"] == "7" and f["link_count"] == "6", "restarted map/actors")
                require(f["energy"] == ("255" if sample == restart else "100"), "restarted energy cache")
            ticks.append(f)
            expected_view = sample in VIEW_SAMPLES
        else:
            raise ValueError("unknown record")
    require(not expected_view and len(ticks) == 420 and views == list(VIEW_SAMPLES), "incomplete ticks/views")
    require(rows[-2:] == [("end", {"samples": "420"}), ("complete", {"cases": "1", "samples": "420", "views": "22"})], "completion footer")
    require([f["stage"] for f in boundaries] == ["fallback_increment"] * 230 + ["fallback_promote", "level_init", "intro_wait", "intro_ack"], "boundary lifecycle")
    require(intro_seen and death is not None and waiting == death + 60 and restart == waiting + 229, "missing death/restart")
    require(420 - restart >= 100, "insufficient resumed gameplay")
    return death, waiting, restart


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--intro", type=Path, default=INTRO)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    source = args.fixture.read_text(encoding="ascii")
    if args.fixture.resolve() == FIXTURE.resolve():
        require(hashlib.sha256(source.encode("ascii")).hexdigest() == EXPECTED_HASH, "fixture hash")
    intro_bytes = args.intro.read_bytes()
    rows = parse(source)
    death, waiting, restart = validate(rows, intro_bytes)
    mutations = 0
    if args.self_test:
        validate(parse(source.replace("\n", "\r\n")), intro_bytes)
        changes = []
        for index, (tag, f) in enumerate(rows):
            if tag == "boundary":
                for field in ("counter", "frame", "gate"):
                    changes.append((index, field, str(int(f[field]) + 1)))
                for field, at in (("p1", 16), ("p1", 21), ("flags", 1), ("flags", 5), ("regs", 2)):
                    data = bytearray.fromhex(f[field]); data[at] ^= 1
                    changes.append((index, field, data.hex()))
            elif tag == "tick" and int(f["sample"]) in {death, waiting, waiting + 179, restart - 1, restart, restart + 1, 419}:
                for field in ("sample", "frame", "fallback", "resets", "lives", "player_state"):
                    changes.append((index, field, str(int(f[field]) + 1)))
            elif tag == "view":
                changes.append((index, "indexed_sha256", "0" * 64))
        for index, field, value in changes:
            changed = copy.deepcopy(rows)
            changed[index][1][field] = value
            try:
                validate(changed, intro_bytes)
            except (ValueError, KeyError, IndexError):
                mutations += 1
            else:
                raise RuntimeError(f"accepted corrupt evidence: {index} {field}")
        for changed in (rows[:-1], rows[:len(rows) // 2], rows + [rows[-1]]):
            try:
                validate(changed, intro_bytes)
            except (ValueError, KeyError, IndexError):
                mutations += 1
            else:
                raise RuntimeError("accepted truncated/extended evidence")
    print(f"original_reentry_evidence=ok samples=420 increment_boundaries=230 intro=1 views=22"
          f" death={death} waiting={waiting} restart={restart} mutations={mutations} production_replay=0 whole_game_parity=0")


if __name__ == "__main__":
    main()
