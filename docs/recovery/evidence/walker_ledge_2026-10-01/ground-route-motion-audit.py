"""Read-only bounded motion audit of the failed 1200-frame completion route."""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original

NATIVE = Path("/dev/shm/lezac-natural-level2-ground-objective-original-20261001-v1")
CPP = Path("/dev/shm/lezac-natural-level2-ground-objective-cpp-20261001-v1")
OUT = Path("/dev/shm/lezac-level2-ground-objective-motion-20261001-v1.json")
DECODER = ROOT / "build-codex-tmp/inspect-level2-monster-divergence-20261001.py"


def main():
    fidelity.require(not OUT.exists(), "fresh report required")
    fidelity.require(fidelity.sha256(DECODER) ==
                     "ec7efada6079d51d72dec06f88f556bba1a52660fc50d81610334b6a153814f9",
                     "independent decoder changed")
    spec = importlib.util.spec_from_file_location("motion_decoder", DECODER)
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    manifest = fidelity.strict_json((NATIVE / "extension-manifest.json").read_text())
    source_hash = fidelity.sha256(NATIVE / "extension.jsonl.gz")
    fidelity.require(manifest["status"] == "captured" and manifest["frames"] == 1200
                     and manifest["prefix_canonical_sha256"] == handoff.PREFIX_SHA256
                     and source_hash == manifest["extension_sha256"] ==
                     "6825c8a3e7eb604dd5e523d99c1aff87d7ac84bceccb017ae6e10cd52c54d42e",
                     "native source or prefix differs")
    fidelity.require((CPP / "route.txt").read_bytes() ==
                     (NATIVE / "extension-route.txt").read_bytes(), "different routes")
    rows = handoff.load(NATIVE / "extension.jsonl.gz")
    fidelity.require(len(rows) == 1202 and rows[0]["frames"] == 1200
                     and rows[-1]["kind"] == "complete" and rows[-1]["frames"] == 1200
                     and rows[-1]["patches_restored"], "incomplete native capture")
    checkpoints = {(r["tick"], r["phase"]): r["state"] for r in
                   fidelity.trace_rows(CPP, fidelity.load_manifest(CPP)) if
                   r["kind"] == "checkpoint" and r["tick"] >= 743
                   and r["phase"] in ("present", "post_update")}
    fidelity.require(len(checkpoints) == 2400, "incomplete C++ checkpoints")
    mapped, motion = [], []
    fields = ("position", "motion", "identity", "ai")
    for index, row in enumerate(rows[1:-1]):
        fidelity.require(row["sample"] == index and row["cpp_tick"] == 743 + index,
                         "sample alignment differs")
        for name, phase, dac_index in (("rendered", "present", 1), ("post", "post_update", 2)):
            cpp, native = checkpoints[row["cpp_tick"], phase], row[name]
            fidelity.require(native["frame"] == 318 + index, "native frame skipped")
            difference = fidelity.first_difference(
                handoff.native_boundary(native, row["dac"][dac_index], rows[0]["atlas"]),
                handoff.boundary(cpp, bytes.fromhex(cpp["palette_rgb_hex"])))
            if difference:
                mapped.append({"sample": index, "phase": phase, **difference})
            expected = decoder.actors(native)
            actual = [m for m in cpp["monsters"] if 1 <= m["identity"][0] <= 8]
            project = lambda items: [{k: m[k][:3] if k == "ai" else m[k] for k in fields}
                                     for m in items]
            difference = fidelity.first_difference(project(expected), project(actual))
            if difference:
                motion.append({"sample": index, "phase": phase, **difference})
    report = {"frames": 1200, "mapped_boundaries": 2400, "mapped_differences": len(mapped),
              "monster_projected_differences": len(motion), "first_mapped": mapped[:1],
              "first_motion": motion[:1], "native_sha256": source_hash,
              "audit_sha256": fidelity.sha256(Path(__file__)), "live_kind_scope": "1..8",
              "all_actor_fields_compared": False, "all_dac_entries_compared": False,
              "original_fidelity_claim": False, "port_functionally_complete": False,
              "natural_level2_completion": False}
    OUT.write_bytes(original.json_bytes(report))
    print(original.json_bytes(report).decode("ascii"))


if __name__ == "__main__":
    main()
