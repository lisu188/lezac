"""Extract a compact isolated walker probe from the retained continuous native route."""
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original

SOURCE = Path("/dev/shm/lezac-natural-level2-completion-original-20261001-v1")
FIXTURE = ROOT / "tests/fixtures/walker_ledge_original.bin"
REPORT = Path("/dev/shm/lezac-walker-ledge-extraction-20261001-v1.json")


def target(state):
    actors, visuals = bytes.fromhex(state["actors"]), bytes.fromhex(state["visuals"])
    matches = []
    for i in range(state["actor_count"]):
        raw = actors[i * 38:(i + 1) * 38]
        if raw[0] == 1 and raw[21] == 3 and raw[37] == 2 and original.word(raw, 14) == 186:
            matches.append(raw + visuals[raw[1] * 8:(raw[1] + 1) * 8])
    fidelity.require(len(matches) == 1, "ambiguous native walker identity")
    return matches[0]


def rectangle(state):
    tiles, words = bytes.fromhex(state["tiles"]), bytes.fromhex(state["words"])
    indices = [(28 + y) * 100 + 46 + x for y in range(4) for x in range(18)]
    return bytes(tiles[i] for i in indices) + b"".join(words[i * 2:i * 2 + 2] for i in indices)


def main():
    fidelity.require(not FIXTURE.exists() and not REPORT.exists(), "fresh extraction outputs required")
    fidelity.require(fidelity.sha256(SOURCE / "extension.jsonl.gz") ==
                     "3a8c3079b44ddcc8431282fdcb5cbea304515b07484c38d6d7ba6c2e25805870", "native stream changed")
    rows = handoff.load(SOURCE / "extension.jsonl.gz")
    fidelity.require(len(rows) == 902 and rows[-1]["kind"] == "complete" and rows[-1]["patches_restored"], "incomplete capture")
    samples = rows[255:287]
    entry = samples[0]["pre"]
    fidelity.require(entry["frame"] == 572 and samples[-1]["post"]["frame"] == 603, "sample window changed")
    local = rectangle(entry)
    descriptors = (SOURCE / "initial-ds.bin").read_bytes()[0xc322:0xc322 + 92 * 4]
    data = b"LEZACLEDGE01" + struct.pack("<HBI4H", 572, 32, entry["rng"], 46, 28, 18, 4)
    data += local + descriptors + target(entry)
    for sample in samples:
        fidelity.require(sample["pre"]["frame"] == sample["post"]["frame"] and
                         rectangle(sample["pre"]) == rectangle(sample["post"]) == local, "local map is not static")
        data += struct.pack("<H", sample["post"]["frame"]) + target(sample["post"])
    with FIXTURE.open("xb") as output:
        output.write(data)
    report = {"fixture": str(FIXTURE), "fixture_bytes": len(data), "fixture_sha256": fidelity.sha256(FIXTURE),
              "fixture_fnv1a64": fidelity.fnv1a64(data), "source": str(SOURCE),
              "source_extension_sha256": fidelity.sha256(SOURCE / "extension.jsonl.gz"),
              "extractor_sha256": fidelity.sha256(Path(__file__)), "first_frame": 572, "frames": 32,
              "source_route_natural": True, "isolated_cpp_seeded": True, "all_actor_fields_compared": False,
              "original_fidelity_claim": False, "port_functionally_complete": False}
    REPORT.write_bytes(original.json_bytes(report))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
