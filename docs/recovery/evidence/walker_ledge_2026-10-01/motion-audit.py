"""Audit every mapped boundary and locate independently decoded monster motion differences."""
import json
import argparse
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original

NATIVE = Path("/dev/shm/lezac-natural-level2-completion-original-20261001-v1")
CPP = Path("/dev/shm/lezac-natural-level2-completion-cpp-20261001-v1")
OUT = Path("/dev/shm/lezac-level2-monster-divergence-20261001-v1.json")


def actors(state):
    data, visuals = bytes.fromhex(state["actors"]), bytes.fromhex(state["visuals"])
    result = []
    for i in range(state["actor_count"]):
        raw = data[i * 38:(i + 1) * 38]
        if not 1 <= raw[0] <= 8:
            continue
        visual = visuals[raw[1] * 8:(raw[1] + 1) * 8]
        result.append({"raw": raw.hex(), "visual": visual.hex(), "slot": i,
                       "position": [original.word(visual, 0), original.word(visual, 2) - raw[20], raw[20]],
                       "motion": list(struct.unpack_from("<hhHH", raw, 6)),
                       "identity": [raw[0], raw[21], raw[37] - 1, int(raw[37] != 0)],
                       "ai": list(struct.unpack_from("<HHH", raw, 14))})
    return result


def main():
    global CPP, OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpp", type=Path, default=CPP)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    CPP, OUT = args.cpp, args.out
    fidelity.require(not OUT.exists(), "fresh report required")
    manifest = fidelity.strict_json((NATIVE / "extension-manifest.json").read_text())
    fidelity.require(manifest["status"] == "captured" and manifest["extension_sha256"] ==
                     fidelity.sha256(NATIVE / "extension.jsonl.gz"), "native provenance differs")
    fidelity.require((CPP / "route.txt").read_bytes() == (NATIVE / "extension-route.txt").read_bytes(), "different input routes")
    rows = handoff.load(NATIVE / "extension.jsonl.gz")
    fidelity.require(len(rows) == 902 and rows[-1]["kind"] == "complete" and rows[-1]["patches_restored"], "incomplete native capture")
    checkpoints = {(r["tick"], r["phase"]): r["state"] for r in
                   fidelity.trace_rows(CPP, fidelity.load_manifest(CPP)) if
                   r["kind"] == "checkpoint" and r["tick"] >= 743 and r["phase"] in ("present", "post_update")}
    fidelity.require(len(checkpoints) == 1800, "incomplete C++ checkpoints")
    mapped, monster_differences, observations = [], [], []
    for row in rows[1:-1]:
        for name, phase, dac_index in (("rendered", "present", 1), ("post", "post_update", 2)):
            cpp, native = checkpoints[row["cpp_tick"], phase], row[name]
            difference = fidelity.first_difference(handoff.native_boundary(native, row["dac"][dac_index], rows[0]["atlas"]),
                                                   handoff.boundary(cpp, bytes.fromhex(cpp["palette_rgb_hex"])))
            if difference:
                mapped.append({"sample": row["sample"], "phase": phase, **difference})
            expected = actors(native)
            actual = [m for m in cpp["monsters"] if 1 <= m["identity"][0] <= 8]
            projected = [{k: m[k][:3] if k == "ai" else m[k] for k in ("position", "motion", "identity", "ai")} for m in expected]
            candidate = [{k: m[k][:3] if k == "ai" else m[k] for k in ("position", "motion", "identity", "ai")} for m in actual]
            difference = fidelity.first_difference(projected, candidate)
            if difference:
                monster_differences.append({"sample": row["sample"], "phase": phase, **difference})
                if len(observations) < 8:
                    observations.append({"sample": row["sample"], "phase": phase, "frame": native["frame"],
                                         "native": expected, "cpp": actual})
        if row["sample"] in (843, 844, 845, 846, 899):
            observations.append({"sample": row["sample"], "phase": "pre", "frame": row["pre"]["frame"],
                                 "native": actors(row["pre"]), "cpp": checkpoints[row["cpp_tick"], "present"]["monsters"]})
    report = {"mapped_boundary_count": 1800, "mapped_differences": mapped,
              "monster_projected_difference_count": len(monster_differences), "monster_first_differences": monster_differences[:12],
              "observations": observations, "all_actor_fields_compared": False, "original_fidelity_claim": False,
              "port_functionally_complete": False}
    OUT.write_bytes(original.json_bytes(report))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
