"""Pinned native Level 1 result-reel validation and production replay."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import shutil
import struct
import uuid

import level1_fidelity as fidelity
import level1_original as original

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/level1_results"
PREFIX = ROOT / "tests/fixtures/level1_original/completion_gate"
EXPECTED_REFERENCE_SHA256 = "b45a7a1561052646eaa87e169909f92ec83c5dbc0380fec9b891db9e288d59f9"
FROZEN = ("frame", "players", "inventory", "destruction", "actor_count",
          "actors", "visuals", "progress", "spawners", "tiles", "words")


def load_rows(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="ascii") as stream:
        rows = [fidelity.strict_json(line) for line in stream]
    fidelity.require(len(rows) == 44, "native results record count changed")
    return rows


def validate_native(rows: list[dict]) -> list[dict]:
    fidelity.require(len(rows) == 44, "incomplete native results")
    header, footer = rows[0], rows[-1]
    fidelity.require(header.get("kind") == "header" and header.get("schema") == "lezac-natural-result-reels-v1" and
                     header.get("exe_sha256") == original.EXE_SHA256 and header.get("entry") == 0x2000 and
                     header.get("signature") == "26807d2c02" and header.get("original_fidelity_claim") is False and
                     header.get("level2_handoff_claim") is False, "invalid native results header")
    fidelity.require(footer == {"kind": "complete", "samples": 42, "steps": 41,
                     "gameplay_frozen": True, "original_fidelity_claim": False}, "incomplete native results footer")
    baseline, atlas = header["baseline"], header["atlas"]
    original.validate_raw(baseline)
    fidelity.require(fidelity.integer(atlas, 0, 65535), "invalid native atlas")
    score_bytes = bytes.fromhex(baseline["scores"])
    initial_score = struct.unpack_from("<I", score_bytes)[0]
    destroyed = original.word(bytes.fromhex(baseline["destruction"]), 2)
    inventory = bytes.fromhex(baseline["inventory"])
    award = destroyed * 10 + inventory[1] * 100 + inventory[2] * 500 + inventory[3] * 2000
    fidelity.require(initial_score == 850 and destroyed == 34 and award == 4840, "natural result fixture scope changed")
    target = [((original.word(score_bytes, offset) - atlas) & 65535) for offset in range(24, 42, 2)]
    current = [((original.word(score_bytes, offset) - atlas) & 65535) for offset in range(4, 22, 2)]
    remaining, digit = initial_score + award, 0
    while True:
        target[digit] = remaining % 10 * 64
        remaining //= 10
        digit += 1
        if not remaining or digit == 8:
            break
    phase, rng, previous, samples = 1, baseline["rng"], bytes(192000), []
    for index, row in enumerate(rows[1:-1]):
        fidelity.require(row.get("kind") == "sample" and row.get("sample") == index and row.get("player") == 1 and
                         row.get("sequence") == 917 + index, "native result sequence mismatch")
        state = row["state"]
        original.validate_raw(state)
        fidelity.require(all(state[key] == baseline[key] for key in FROZEN), "native results advanced gameplay")
        if index:
            changed = any(a != b for a, b in zip(current, target))
            current = [(a + (16 if digit % 2 == 0 else 8)) % 640 if a != b else a
                       for digit, (a, b) in enumerate(zip(current, target))]
            if not changed:
                phase = 2
            rng = (rng * 0x08088405 + 1) & 0xFFFFFFFF
        expected = [initial_score + award, phase, *current, *target]
        actual = original.project_original(state, 1, atlas)
        fidelity.require(actual["players"][0]["reel"] == expected and state["rng"] == rng,
                         "native whole award / reel / delayed RNG mismatch")
        fidelity.require(phase == (2 if index == 41 else 1), "native reels settled at the wrong boundary")
        previous = original.decode_frame(row["rgb_delta_zlib_hex"], previous, row["rgb_sha256"])
        samples.append({**row, "rgb": previous})
    return samples


def fixture() -> tuple[dict, list[dict]]:
    manifest = fidelity.strict_json((FIXTURE / "capture.json").read_text())
    fidelity.require(manifest["schema"] == "lezac-level1-results-fixture-v1" and manifest["patches_restored"] is True and
                     manifest["original_fidelity_claim"] is False and manifest["typing_timing_claim"] is False and
                     manifest["level2_handoff_claim"] is False, "invalid results fixture scope")
    fidelity.require(manifest["original_exe_sha256"] == original.EXE_SHA256 and
                     manifest["prefix_canonical_sha256"] == "18c029dcc107cf95b088a914cf60aa05fd30fbaf26501e3b2367ee91cd96ace8",
                     "native result prefix provenance changed")
    fidelity.require(set(manifest["files"]) == {"reference.jsonl.gz", "route.txt"}, "invalid results fixture inventory")
    for name, digest in manifest["files"].items():
        fidelity.require(fidelity.sha256(fidelity.safe_file(FIXTURE, name)) == digest, "results fixture checksum mismatch")
    fidelity.require(manifest["files"]["reference.jsonl.gz"] == EXPECTED_REFERENCE_SHA256, "native results pin changed")
    rows = load_rows(FIXTURE / "reference.jsonl.gz")
    fidelity.require(rows[0]["route_sha256"] == fidelity.sha256(PREFIX / "route.txt"), "native prefix input changed")
    settings, events = original.read_route(PREFIX / "route.txt")
    extended, extended_events = original.read_route(FIXTURE / "route.txt")
    fidelity.require(events == extended_events and extended["ticks"] == 660 and
                     all(settings[key] == extended[key] for key in ("seed", "step_us")), "results replay input changed")
    fidelity.require(rows[0]["observer_sha256"] == manifest["observer_sha256"] ==
                     fidelity.sha256(ROOT / "tools/capture_original_level1_results.py"), "native results producer changed")
    fidelity.require(rows[0]["base_observer_sha256"] == original.SOURCE_SHA256 == manifest["base_observer_sha256"],
                     "original prefix observer changed")
    image = original.check_executable(ROOT / "LEZAC.EXE")
    for offset, code in {0x1DC2: "6aff6a1f6a1f6a1f9a0000ac08", 0x1DCF: "6b06c8780a", 0x1FE8: "c4beecfd26010526115502",
                         0x1FF3: "c4beecfd0657e8b4f1", 0x2000: "26807d2c02",
                         0x201A: "6a0f9a9c024a08", 0x2021: "6a049aa81320093d02007609"}.items():
        fidelity.require(image[offset:offset + len(code) // 2].hex() == code, "native results instruction pin changed")
    return rows[0], validate_native(rows)


def pack(capture: Path, route: Path, out: Path) -> dict:
    fidelity.require(not out.exists(), "results fixture output already exists")
    prefix_hash = original.fingerprint(capture)
    fidelity.require(prefix_hash == original.fingerprint(PREFIX), "results capture changed the original gameplay prefix")
    header = load_rows(capture / "results.jsonl.gz")[0]
    validate_native(load_rows(capture / "results.jsonl.gz"))
    fidelity.require(header["observer_sha256"] == fidelity.sha256(capture / "observer.py") ==
                     fidelity.sha256(ROOT / "tools/capture_original_level1_results.py"), "capture producer differs from source")
    settings, events = original.read_route(capture / "route.txt")
    extended, extended_events = original.read_route(route)
    fidelity.require(events == extended_events and extended["ticks"] == 660 and
                     all(settings[key] == extended[key] for key in ("seed", "step_us")), "results input prefix changed")
    fidelity.require((capture / "results.jsonl.gz").stat().st_size <= 262144, "results fixture exceeds compact-evidence reserve")
    out.mkdir()
    shutil.copyfile(capture / "results.jsonl.gz", out / "reference.jsonl.gz")
    shutil.copyfile(route, out / "route.txt")
    manifest = {"schema": "lezac-level1-results-fixture-v1", "original_exe_sha256": original.EXE_SHA256,
                "observer_sha256": header["observer_sha256"], "base_observer_sha256": original.SOURCE_SHA256,
                "prefix_canonical_sha256": prefix_hash, "patches_restored": True, "samples": 42, "steps": 41,
                "files": {name: fidelity.sha256(out / name) for name in ("reference.jsonl.gz", "route.txt")},
                "original_fidelity_claim": False, "typing_timing_claim": False, "level2_handoff_claim": False}
    (out / "capture.json").write_bytes(original.json_bytes(manifest))
    return manifest


def guard() -> dict:
    fixture()
    rows = load_rows(FIXTURE / "reference.jsonl.gz")
    mutations = []
    def mutation(edit):
        altered = copy.deepcopy(rows)
        edit(altered)
        try:
            validate_native(altered)
        except (fidelity.EvidenceError, KeyError, ValueError):
            mutations.append(True)
            return
        raise fidelity.EvidenceError("results guard accepted a semantic mutation")
    mutation(lambda r: r[-1].__setitem__("samples", 41))
    mutation(lambda r: r[1]["state"].__setitem__("rng", 0))
    mutation(lambda r: r[2]["state"].__setitem__("rng", r[1]["state"]["rng"]))
    mutation(lambda r: r[1]["state"].__setitem__("scores", (struct.pack("<I", 5860) + bytes.fromhex(r[1]["state"]["scores"])[4:]).hex()))
    mutation(lambda r: r[1]["state"].__setitem__("scores", (bytes.fromhex(r[1]["state"]["scores"])[:44] + b"\x02" + bytes.fromhex(r[1]["state"]["scores"])[45:]).hex()))
    mutation(lambda r: r[2]["state"].__setitem__("frame", 306))
    mutation(lambda r: r[1].__setitem__("rgb_sha256", "0" * 64))
    mutation(lambda r: r[2].__setitem__("sample", 0))
    return {"status": "guarded", "samples": 42, "steps": 41, "mutations_rejected": len(mutations),
            "original_fidelity_claim": False}


def compare(cpp: Path, out: Path) -> dict:
    header, native = fixture()
    manifest = fidelity.load_manifest(cpp)
    checkpoints = {(row["tick"], row["phase"]): row["state"] for row in fidelity.trace_rows(cpp, manifest)
                   if row["kind"] == "checkpoint" and row["phase"] in ("present", "post_update") and row["tick"] <= 308}
    candidate = [fidelity.strict_json(line) for line in (cpp / "result_reels.jsonl").read_text().splitlines()]
    fidelity.require(candidate[0] == {"kind": "header", "schema": "lezac.level1.result-reels.v1",
                     "boundary": "prepared-score-then-after-delayed-rng", "original_fidelity_claim": False} and
                     candidate[-1] == {"kind": "complete", "samples": 42, "original_fidelity_claim": False} and
                     len(candidate) == 44, "incomplete C++ result boundaries")
    frames = states = changed = 0
    first = None
    for row in original.reference_rows(PREFIX):
        if row["kind"] != "sample":
            continue
        for phase, field in (("present", "rendered"), ("post_update", "post")):
            diff = fidelity.first_difference(original.project_original(row[field], 1, header["atlas"]),
                                             original.project_cpp(checkpoints[row["cpp_tick"], phase], 1))
            if diff and first is None:
                first = {"region": "prefix", "tick": row["cpp_tick"], "phase": phase, **diff}
            states += 1
        pixels = fidelity.read_ppm(cpp / f"frame_{row['cpp_tick']:06d}.ppm")
        prefix_changed = sum(row["rgb"][i:i+3] != pixels[i:i+3] for i in range(0, len(pixels), 3))
        if prefix_changed and first is None:
            first = {"region": "prefix", "tick": row["cpp_tick"], "path": "$.rgb", "differing_pixels": prefix_changed}
        changed += prefix_changed
        frames += 1
    out.mkdir(parents=True, exist_ok=True)
    for index, (expected, actual) in enumerate(zip(native, candidate[1:-1])):
        fidelity.require(set(actual) == {"kind", "sample", "player", "frame", "state"} and actual["kind"] == "sample" and
                         actual["sample"] == index and actual["player"] == 1 and
                         actual["frame"] == f"result_frame_{index:06d}.ppm", "invalid C++ result boundary")
        diff = fidelity.first_difference(original.project_original(expected["state"], 1, header["atlas"]),
                                         original.project_cpp(actual["state"], 1))
        if diff and first is None:
            first = {"region": "results", "sample": index, **diff}
        pixels = fidelity.read_ppm(fidelity.safe_file(cpp, actual["frame"]))
        pixels_changed = sum(expected["rgb"][i:i+3] != pixels[i:i+3] for i in range(0, len(pixels), 3))
        if pixels_changed and first is None:
            first = {"region": "results", "sample": index, "path": "$.rgb", "differing_pixels": pixels_changed}
        changed += pixels_changed
        if index in (0, 1, 20, 41):
            from PIL import Image
            Image.frombytes("RGB", (320, 200), expected["rgb"]).save(out / f"original_{index:02d}.png")
            Image.frombytes("RGB", (320, 200), pixels).save(out / f"cpp_{index:02d}.png")
    report = {"status": "match" if first is None and changed == 0 else "diverged",
              "prefix_frames": frames, "prefix_states": states, "result_frames": len(native), "reel_steps": 41,
              "pixels": (frames + len(native)) * 64000, "differing_pixels": changed, "first_difference": first,
              "phase_alignment": "native-loop-boundary", "typing_timing_claim": False, "level2_handoff_claim": False,
              "original_fidelity_claim": False, "cpp_executable_sha256": manifest["executable_sha256"],
              "cpp_trace_sha256": manifest["trace_sha256"], "cpp_result_stream_sha256": fidelity.sha256(cpp / "result_reels.jsonl"),
              "reference_sha256": EXPECTED_REFERENCE_SHA256}
    (out / "comparison.json").write_bytes(original.json_bytes(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    packer = commands.add_parser("pack")
    packer.add_argument("--capture", type=Path, required=True)
    packer.add_argument("--route", type=Path, required=True)
    packer.add_argument("--out", type=Path, default=FIXTURE)
    commands.add_parser("guard")
    comparer = commands.add_parser("compare")
    comparer.add_argument("--cpp", type=Path, required=True)
    comparer.add_argument("--out", type=Path, required=True)
    replay = commands.add_parser("replay")
    replay.add_argument("--exe", type=Path, required=True)
    replay.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "pack":
        report = pack(args.capture, args.route, args.out)
    elif args.command == "guard":
        report = guard()
    else:
        if args.command == "replay":
            args.out.mkdir(parents=True, exist_ok=True)
            cpp = args.out / ("run-" + uuid.uuid4().hex)
            fidelity.record(args.exe, ROOT, FIXTURE / "route.txt", cpp, original_intro_wait=True, result_reels=True)
            out = cpp / "comparison"
        else:
            cpp, out = args.cpp, args.out
        report = compare(cpp, out)
        fidelity.require(report["status"] == "match", "native results comparison diverged: " + json.dumps(report["first_difference"]))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
