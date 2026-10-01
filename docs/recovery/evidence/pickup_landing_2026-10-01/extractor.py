"""Extract a small, seeded-C++ label probe from the retained continuous native route."""
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import level1_fidelity as fidelity
import level1_original as original
from PIL import Image

NATIVE = Path("/dev/shm/lezac-natural-level2-progress-original-20261001-v1")
CPP = Path("/dev/shm/lezac-natural-level2-progress-cpp-20261001-v2")
OUT = ROOT / "docs/recovery/evidence/pickup_landing_2026-10-01"
FIXTURE = ROOT / "tests/fixtures/pickup_landing_original.bin"
STREAM_SHA256 = "b154ebd525e60f2a11e00b18a64f09f1f2f8321834d4da859e59b343e269b1ae"


def labels(state):
    actors, visuals = bytes.fromhex(state["actors"]), bytes.fromhex(state["visuals"])
    result = []
    for offset in range(0, len(actors), 38):
        actor = actors[offset:offset + 38]
        if actor[0] == 0x0a:
            visual = visuals[actor[1] * 8:(actor[1] + 1) * 8]
            fidelity.require(len(visual) == 8, "label visual is absent")
            result.append(actor + visual)
    return result


def main():
    fidelity.require(not OUT.exists() or not any(OUT.iterdir()), "promoted evidence already exists")
    fidelity.require(fidelity.sha256(NATIVE / "extension.jsonl.gz") == STREAM_SHA256, "native stream changed")
    with gzip.open(NATIVE / "extension.jsonl.gz", "rt") as source:
        rows = [fidelity.strict_json(line) for line in source]
    fidelity.require(rows[-1]["patches_restored"] is True and rows[-1]["frames"] == 600, "incomplete native route")
    selected = rows[368:394]
    fidelity.require([row["sample"] for row in selected] == list(range(367, 393)), "native slice is misaligned")
    entry = selected[0]["rendered"]
    fidelity.require(entry["frame"] == 685 and entry["players"][0]["xy"] == [33, 370], "entry differs")
    ds = (NATIVE / "initial-ds.bin").read_bytes()
    descriptors = ds[0xc322:0xc322 + 92 * 4]
    payload = bytearray(b"LEZACPICKUP1")
    payload += struct.pack("<HBII", 685, 26, entry["rng"], selected[0]["post"]["rng"])
    payload += bytes.fromhex(entry["players"][0]["raw"] + entry["players"][0]["visual"])
    payload += descriptors
    tiles, words = bytes.fromhex(entry["tiles"]), bytes.fromhex(entry["words"])
    cells = [y * 100 + x for y in range(45, 50) for x in range(3, 8)]
    payload += bytes(tiles[cell] for cell in cells)
    payload += b"".join(words[cell * 2:cell * 2 + 2] for cell in cells)
    samples = []
    for row in selected:
        actors = labels(row["post"])
        payload += struct.pack("<HB", row["post"]["frame"], len(actors)) + b"".join(actors)
        samples.append({"sample": row["sample"], "frame": row["post"]["frame"],
                        "labels": [actor.hex() for actor in actors]})
    fidelity.require(sum(len(row["labels"]) for row in samples) == 48 and samples[-1]["labels"] == [], "lifetime differs")
    OUT.mkdir(exist_ok=True)
    if FIXTURE.exists():
        fidelity.require(FIXTURE.read_bytes() == payload, "existing fixture differs from the extracted bytes")
    else:
        FIXTURE.write_bytes(payload)
    report = {"schema": "lezac-pickup-landing-extraction-v1", "native_stream_sha256": STREAM_SHA256,
              "extractor_sha256": fidelity.sha256(Path(__file__)), "fixture_sha256": fidelity.sha256(FIXTURE),
              "fixture_fnv1a64": fidelity.fnv1a64(payload), "fixture_bytes": len(payload),
              "native_capture_seeded_after_entry": False, "cpp_probe_player_and_local_map_seeded": True,
              "scope": "two pickup indicators and their 26 post-update lifetime boundaries only",
              "entry_player": entry["players"][0], "entry_rng": entry["rng"],
              "creation_rng": selected[0]["post"]["rng"], "samples": samples,
              "manual_input_claim": False, "wall_clock_claim": False, "original_fidelity_claim": False,
              "port_functionally_complete": False}
    (OUT / "extraction.json").write_bytes(original.json_bytes(report))
    previous = bytes(192000)
    for row in rows[1:370]:
        previous = original.decode_frame(row["rgb_delta_zlib_hex"], previous, row["rgb_sha256"])
    Image.frombytes("RGB", (320, 200), previous).save(OUT / "original_368.png")
    Image.frombytes("RGB", (320, 200), fidelity.read_ppm(CPP / "frame_001111.ppm")).save(OUT / "cpp_368.png")
    for name, source in (("cpp_before_368.png", Path("/dev/shm/lezac-natural-level2-progress-comparison-20261001-v1/cpp_368.png")),
                         ("comparison_before.json", Path("/dev/shm/lezac-natural-level2-progress-comparison-20261001-v1/comparison.json")),
                         ("comparison_after.json", Path("/dev/shm/lezac-natural-level2-progress-comparison-20261001-v2/comparison.json"))):
        (OUT / name).write_bytes(source.read_bytes())
    print(json.dumps({key: value for key, value in report.items() if key not in ("samples", "entry_player")}, sort_keys=True))


if __name__ == "__main__":
    main()
