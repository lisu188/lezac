#!/usr/bin/env python3
"""Check the sealed controlled boss combat and optional production replay."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "docs/recovery/evidence/boss_active_combat_20261001"
MANIFEST_SHA = "3f77b9901dc7e89dd2115c8fbeadaaf0c115f5c83bb11485bf5f9a4dbf4c0853"
VIEWS = (0, 1, 15, 16, 20, 39, 59, 99, 199, 399, 599, 799)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fields(row):
    tokens = row.split()
    pairs = [token.split("=", 1) for token in tokens if "=" in token]
    require(all(len(pair) == 2 for pair in pairs), "malformed record")
    result = dict(pairs)
    require(len(result) == len(pairs), "duplicate field")
    return result


def decode_view(value):
    pixels = bytearray()
    for run in value.split(","):
        count, pixel = run.split(":")
        require(0 < int(count) <= 47424 - len(pixels) and len(pixel) == 2, "invalid indexed run")
        pixels.extend(bytes.fromhex(pixel) * int(count))
    require(len(pixels) == 47424, "truncated indexed view")
    return bytes(pixels)


def validate_trace(raw):
    rows = [row for row in raw.decode("ascii").splitlines() if row and not row.startswith("#")]
    require(fields(rows[0]) == dict(capture="boss_active_combat_original_v1", level="7", temp_copy="1",
            seeded_case_boundary="1", head_health_modified="0", seeded_bomb="0", latched_input="1",
            physical_keyboard="0", per_tick_actor_seed="0", natural_campaign="0"), "combat scope")
    require(rows[-2:] == ["end samples=800", "complete cases=1 samples=800 views=12"], "incomplete combat")
    cases = [fields(row) for row in rows if row.startswith("case ")]
    require(len(cases) == 1 and cases[0]["name"] == "latched_fire_even" and cases[0]["frame"] == "100", "case")
    initial = cases[0]
    head = bytes.fromhex(initial["actors"].split(",")[0].split(":")[0])
    require(len(head) == 38 and head[0] == 30 and head[2] == 1 and head[36] == 10 and
            initial["count"] == "7" and initial["ammo"] == "c8140600c8140600", "unchanged boss/initial inventory")
    ticks = [fields(row) for row in rows if row.startswith("tick ")]
    require(len(ticks) == 800, "tick count")
    for sample, tick in enumerate(ticks):
        require(int(tick["sample"]) == sample and int(tick["frame"]) == 101 + sample, "tick continuity")
        require(len(tick["ammo"]) == 16 and tick["weapons"] == "0101" and len(tick["latches"]) == 4 and
                tick["resets"] == "0" and tick["active_players"] == "1", "inventory/lifecycle fields")
        require(tick["control"] in ("idle", "fire"), "control")
        if tick["input_regs"] != "-":
            require(tick["normalized"] == ("0000000100" if tick["control"] == "fire" else "0000000000"), "normalized input")
    keys = [fields(row) for row in rows if row.startswith("key ")]
    expected = [(sample - 1, sample, value) for shot in range(33)
                for sample, value in ((16 + 24 * shot, "01"), (17 + 24 * shot, "00"))]
    require(len(keys) == len(expected), "key count")
    for key, (previous, sample, value) in zip(keys, expected):
        require(int(key["sample"]) == previous and int(key["next_sample"]) == sample and
                key["address"] == "1b7b" and key["value"] == value and key["after_render"] == "1" and
                key["before"] == ticks[previous]["latches"][:2], "key schedule/boundary")
    views = [fields(row) for row in rows if row.startswith("view ")]
    require(tuple(int(view["sample"]) for view in views) == VIEWS, "view coverage")
    for view in views:
        require(sha(decode_view(view["pixels"])) == view["indexed_sha256"], "indexed view hash")
    boundaries = [fields(row) for row in rows if row.startswith("boundary ")]
    require(len(boundaries) == 48 and all(row["stage"] == "fallback_increment" for row in boundaries), "shared wait coverage")
    reentries = sum(ticks[i - 1]["player_state"] == "2" and ticks[i]["player_state"] == "1" for i in range(1, 800))
    require(reentries == 3 and ticks[-1]["lives"] == "96" and ticks[-1]["ammo"] == "b2140600c8140600" and
            sum(tick["control"] == "fire" for tick in ticks) == 22, "shot/reentry coverage")
    return views[-1]


def load_evidence():
    manifest_raw = (EVIDENCE / "manifest.json").read_bytes()
    require(sha(manifest_raw) == MANIFEST_SHA, "combat manifest changed")
    manifest = json.loads(manifest_raw)
    require(manifest["schema"] == 1 and all(manifest[key] is False for key in
            ("whole_game_parity", "natural_campaign", "physical_keyboard")), "manifest scope")
    require(sha((ROOT / "LEZAC.EXE").read_bytes()) == manifest["original_exe_sha256"], "original executable changed")
    for name, digest in manifest["files"].items():
        require(Path(name).name == name and "/" not in name and "\\" not in name, "evidence path")
        require(sha((EVIDENCE / name).read_bytes()) == digest, "evidence changed: " + name)
    fixture = ROOT / "tests/fixtures/boss_active_combat_original_level7.txt.gz"
    require(manifest["fixture"] == fixture.relative_to(ROOT).as_posix(), "fixture path")
    packed = fixture.read_bytes()
    raw = gzip.decompress(packed)
    require(sha(packed) == manifest["fixture_sha256"] and sha(raw) == manifest["trace_sha256"], "fixture changed")
    original = json.loads((EVIDENCE / "original.json").read_bytes())
    require(original["status"] == "captured_candidate" and original["observer_exit_code"] == 0 and
            original["hooks_restored"] is True and original["audio"] == "dummy" and
            original["head_before_warmup"]["hp"] == 10 and original["head_before_warmup"]["lives"] == 1 and
            all(child["returncode"] is not None for child in original["owned_dosbox"]), "original outcome")
    require(original["production_replay"] is False and original["whole_game_parity"] is False,
            "capture-time scope changed")
    for name, item in original["sources"].items():
        source = gzip.decompress((EVIDENCE / item["file"]).read_bytes())
        require(sha(source) == item["sha256"], "executed source changed")
        if name.startswith("tools/"):
            require(sha((ROOT / name).read_bytes().replace(b"\r\n", b"\n")) == manifest["sources_lf"][name], "capture source drift")
    cpp = json.loads((EVIDENCE / "cpp.json").read_bytes())
    require(cpp["status"] == "passed" and cpp["exit_code"] == 0 and cpp["audio"] == "dummy" and
            cpp["production_replay"] is True and cpp["whole_game_parity"] is False and
            sha(gzip.decompress((EVIDENCE / "cpp_source.cpp.gz").read_bytes())) == cpp["source_sha256"], "archived replay outcome/source")
    require(sha(gzip.decompress((EVIDENCE / "producer.py.gz").read_bytes())) == manifest["producer_sha256"], "producer changed")
    last = validate_trace(raw)
    palette = (ROOT / "BOMPAL.PAL").read_bytes()
    rgb = bytearray()
    for value in decode_view(last["pixels"]):
        j = value - 176
        color = (j * 43 // 38, j * 23 // 38, 14 - j * 12 // 38) if 176 <= value <= 214 else palette[3 * value:3 * value + 3]
        rgb.extend(((v << 2) | (v >> 4)) & 255 for v in color)
    for version in ("original", "cpp"):
        ppm = gzip.decompress((EVIDENCE / (version + "_799.ppm.gz")).read_bytes())
        require(ppm == b"P6\n312 152\n255\n" + rgb and sha(rgb) == manifest["images"][version], "preview not bound to original indexed view")
    return raw


def mutations(raw):
    text = raw.decode("ascii")
    yield text.rsplit("complete ", 1)[0]
    yield text.split("end samples=", 1)[0]
    for old, new in (("head_health_modified=0", "head_health_modified=1"),
                     ("physical_keyboard=0", "physical_keyboard=1"),
                     ("per_tick_actor_seed=0", "per_tick_actor_seed=1"),
                     ("tick sample=16 ", "tick sample=17 "),
                     ("key sample=15 next_sample=16", "key sample=15 next_sample=17"),
                     ("address=1b7b", "address=1b80"), ("after_render=1", "after_render=0")):
        require(old in text, "mutation target missing")
        yield text.replace(old, new, 1)
    rows = text.splitlines()
    for prefix, key, value in (("tick sample=16 ", "control", "idle"),
                               ("tick sample=16 ", "ammo", "c8140600c8140600"),
                               ("tick sample=16 ", "latches", "0100"),
                               ("tick sample=16 ", "normalized", "0000000000"),
                               ("tick sample=0 ", "rng", "00000000"),
                               ("case ", "weapons", "0401")):
        changed = list(rows)
        index = next(i for i, row in enumerate(rows) if row.startswith(prefix))
        old = key + "=" + fields(rows[index])[key]
        require(old != key + "=" + value, "mutation unchanged")
        changed[index] = rows[index].replace(old, key + "=" + value)
        yield "\n".join(changed) + "\n"
    key_row = next(row for row in rows if row.startswith("key sample=15 "))
    yield text.replace(key_row + "\n", "", 1)
    yield text.replace(key_row + "\n", key_row + "\n" + key_row + "\n", 1)
    index = next(i for i, row in enumerate(rows) if row.startswith("case "))
    original = fields(rows[index])["actors"]
    head_raw, tail = original.split(":", 1)
    for offset in (2, 36):
        head = bytearray.fromhex(head_raw)
        head[offset] = 0
        changed = list(rows)
        changed[index] = rows[index].replace("actors=" + original, "actors=" + head.hex() + ":" + tail)
        yield "\n".join(changed) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path)
    args = parser.parse_args()
    raw = load_evidence()
    if not args.exe:
        print("boss_active_combat_evidence=ok samples=800 views=12 shots=22 reentries=3 keys=66 sealed_replay=1 live_replay=0 whole_game_parity=0")
        return
    environment = os.environ.copy()
    environment.update(SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy")
    with tempfile.TemporaryDirectory(prefix="lezac-boss-active-combat-") as directory:
        path = Path(directory) / "trace.txt"

        def run(data):
            path.write_bytes(data)
            return subprocess.run([str(args.exe.resolve()), "--debug-boss-active-combat-original", str(path)],
                                  cwd=ROOT, env=environment, capture_output=True, text=True, timeout=60)

        for data in (raw, raw.replace(b"\n", b"\r\n")):
            result = run(data)
            require(result.returncode == 0 and "different_pixels=0" in result.stdout and
                    "shots=22 reentries=3" in result.stdout and "whole_game_parity=0" in result.stdout, "production replay failed: " + result.stderr)
        count = 0
        for data in mutations(raw):
            result = run(data.encode("ascii"))
            require(result.returncode != 0 and "boss-continuous" in result.stderr, "mutation accepted or unrelated failure")
            if count >= 17:
                require("sample=0: head health seed contradicts provenance" in result.stderr,
                        "reduced starting health was not rejected at the case boundary")
            count += 1
    print(f"boss_active_combat_fixture=ok samples=800 views=12 shots=22 reentries=3 keys=66 newline_variants=2 mutations_rejected={count} silent_children=1 whole_game_parity=0")


if __name__ == "__main__":
    main()
