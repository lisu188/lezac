"""Validate pinned native results typing and compare the production replay."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import shutil
import struct
import uuid

import frame_compare
import level1_fidelity as fidelity
import level1_original as original
import level1_results as results

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/level1_typing"
PREFIX = ROOT / "tests/fixtures/level1_original/completion_gate"
REFERENCE_SHA256 = "824fcf62bc31c42d6b128bb42eec3d0f82e6f2e60ed22c366eb345a76150cfbf"
PREFIX_SHA256 = "18c029dcc107cf95b088a914cf60aa05fd30fbaf26501e3b2367ee91cd96ace8"
LINES = (("livello completato", 60, 11, 1, 25, 31, 27, 61),
         ("bonus distruzione; 340", 81, 9, 27, 241, 244, 240, 61),
         ("bomba bonus", 99, 9, 27, 25, 244, 240, 111),
         ("giocatore 1   4500", 120, 9, 27, 13, 31, 27, 79))
FROZEN = results.FROZEN + ("scores", "rng")


def load(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="ascii") as stream:
        return [fidelity.strict_json(line) for line in stream]


def validate(rows: list[dict]) -> list[dict]:
    fidelity.require(len(rows) == 91, "incomplete native typing")
    header, footer = rows[0], rows[-1]
    fidelity.require(header.get("kind") == "header" and header.get("schema") == "lezac-natural-result-typing-v1" and
                     header.get("exe_sha256") == original.EXE_SHA256 and header.get("entry") == 0x1611 and
                     header.get("original_fidelity_claim") is False, "invalid native typing header")
    native_bytes = bytes.fromhex(header["native_loaded_bytes"])
    fidelity.require(len(native_bytes) == 8 and native_bytes[:6].hex() == "ff76069a9c02", "native delay hook changed")
    fidelity.require(footer == {"kind": "complete", "samples": 89, "gameplay_frozen": True,
                     "typing_skip_claim": False, "level2_handoff_claim": False,
                     "original_fidelity_claim": False}, "incomplete native typing footer")
    baseline, previous, samples = header["baseline"], bytes(192000), []
    original.validate_raw(baseline)
    fidelity.require(baseline["frame"] == 305 and baseline["rng"] == 3146821024, "typing baseline changed")
    index = 0
    for line, (text, y, cell, font, shadow, high, low, x) in enumerate(LINES):
        limit = len(text) + 5
        for step in range(1, limit + 1):
            row = rows[index + 1]
            expected = {"kind": "sample", "sample": index, "text": "     " + text + "     ",
                        "character": step, "limit": limit, "color_span": 5, "delay_ms": 81,
                        "y": y, "x": x, "cell": cell, "font_base": font, "shadow_color": shadow,
                        "high_color": high, "low_color": low, "sequence": 917 + index}
            fidelity.require(all(type(row.get(key)) is type(value) and row[key] == value
                                 for key, value in expected.items()), "native typing metadata changed")
            original.validate_raw(row["state"])
            fidelity.require(all(row["state"][key] == baseline[key] for key in FROZEN), "native typing advanced gameplay, score or RNG")
            previous = original.decode_frame(row["rgb_delta_zlib_hex"], previous, row["rgb_sha256"])
            samples.append({**row, "line": line, "elapsed_ms": 500 + index * 81, "rgb": previous})
            index += 1
    return samples


def check_instructions():
    image = original.check_executable(ROOT / "LEZAC.EXE")
    for offset, code in {0x14C4: "8a461030e48bd08a460e30e42bc2408986f0fe",
                         0x154C: "2b86f0fe8986ecfe", 0x15EC: "8a460e30e42b86f2fe4050",
                         0x1611: "ff76069a9c024a08", 0x141A: "807e0800"}.items():
        fidelity.require(image[offset:offset + len(code) // 2].hex() == code, "native typing instruction changed")


def fixture() -> tuple[dict, list[dict]]:
    manifest = fidelity.strict_json((FIXTURE / "capture.json").read_text())
    fidelity.require(manifest["schema"] == "lezac-level1-typing-fixture-v1" and manifest["patches_restored"] is True and
                     manifest["prefix_canonical_sha256"] == PREFIX_SHA256 and manifest["samples"] == 89 and
                     all(manifest[key] is False for key in ("original_fidelity_claim", "wall_clock_claim",
                                                           "typing_skip_claim", "level2_handoff_claim")), "invalid typing fixture scope")
    fidelity.require(set(manifest["files"]) == {"reference.jsonl.gz", "route.txt"}, "invalid typing fixture inventory")
    for name, digest in manifest["files"].items():
        fidelity.require(fidelity.sha256(fidelity.safe_file(FIXTURE, name)) == digest, "typing fixture checksum mismatch")
    fidelity.require(manifest["files"]["reference.jsonl.gz"] == REFERENCE_SHA256, "native typing pin changed")
    rows = load(FIXTURE / "reference.jsonl.gz")
    header = rows[0]
    fidelity.require(header["observer_sha256"] == manifest["observer_sha256"] ==
                     fidelity.sha256(ROOT / "tools/capture_original_level1_typing.py"), "typing producer changed")
    fidelity.require(header["base_observer_sha256"] == manifest["base_observer_sha256"] == original.SOURCE_SHA256,
                     "typing prefix producer changed")
    fidelity.require(header["route_sha256"] == fidelity.sha256(PREFIX / "route.txt"), "typing prefix input changed")
    fidelity.require((FIXTURE / "route.txt").read_bytes() == (results.FIXTURE / "route.txt").read_bytes(), "typing replay route changed")
    check_instructions()
    return header, validate(rows)


def pack(capture: Path, out: Path) -> dict:
    fidelity.require(not out.exists() and not (capture / "failure.json").exists(), "typing output exists or capture failed")
    fidelity.require(original.fingerprint(capture) == PREFIX_SHA256 == original.fingerprint(PREFIX), "typing prefix changed")
    rows = load(capture / "typing.jsonl.gz")
    validate(rows)
    header = rows[0]
    fidelity.require(header["observer_sha256"] == fidelity.sha256(capture / "observer.py") ==
                     fidelity.sha256(ROOT / "tools/capture_original_level1_typing.py"), "typing capture producer differs")
    fidelity.require(fidelity.sha256(capture / "typing.jsonl.gz") == REFERENCE_SHA256 and
                     (capture / "typing.jsonl.gz").stat().st_size <= 262144, "typing capture pin or reserve changed")
    check_instructions()
    out.mkdir()
    shutil.copyfile(capture / "typing.jsonl.gz", out / "reference.jsonl.gz")
    shutil.copyfile(results.FIXTURE / "route.txt", out / "route.txt")
    manifest = {"schema": "lezac-level1-typing-fixture-v1", "samples": 89, "patches_restored": True,
                "prefix_canonical_sha256": PREFIX_SHA256, "observer_sha256": header["observer_sha256"],
                "base_observer_sha256": header["base_observer_sha256"],
                "files": {name: fidelity.sha256(out / name) for name in ("reference.jsonl.gz", "route.txt")},
                "original_fidelity_claim": False, "wall_clock_claim": False,
                "typing_skip_claim": False, "level2_handoff_claim": False}
    (out / "capture.json").write_bytes(original.json_bytes(manifest))
    return manifest


def guard() -> dict:
    fixture()
    rows = load(FIXTURE / "reference.jsonl.gz")
    mutations = (lambda r: r[-1].__setitem__("samples", 88),
                 lambda r: r[1].__setitem__("delay_ms", 0),
                 lambda r: r[1].__setitem__("color_span", 4),
                 lambda r: r[1].__setitem__("limit", 18),
                 lambda r: r[2].__setitem__("shadow_color", 0),
                 lambda r: r[2].__setitem__("high_color", 27),
                 lambda r: r[2]["state"].__setitem__("rng", 0),
                 lambda r: r[2]["state"].__setitem__("scores", (struct.pack("<I", 5690) + bytes.fromhex(r[2]["state"]["scores"])[4:]).hex()),
                 lambda r: r[2]["state"].__setitem__("frame", 306),
                 lambda r: r[2].__setitem__("rgb_sha256", "0" * 64),
                 lambda r: r[2].__setitem__("sample", 0),
                 lambda r: r[1].__setitem__("sample", False),
                 lambda r: r[1].__setitem__("character", True))
    for mutate in mutations:
        damaged = copy.deepcopy(rows)
        mutate(damaged)
        try:
            validate(damaged)
        except fidelity.EvidenceError:
            continue
        raise fidelity.EvidenceError("damaged typing evidence was accepted")
    return {"status": "guarded", "samples": 89, "mutations_rejected": len(mutations), "original_fidelity_claim": False}


def compare(cpp: Path, out: Path) -> dict:
    header, native = fixture()
    manifest = fidelity.load_manifest(cpp)
    candidate = [fidelity.strict_json(line) for line in (cpp / "result_typing.jsonl").read_text().splitlines()]
    fidelity.require(len(candidate) == 91 and candidate[0] == {"kind": "header", "schema": "lezac.level1.result-typing.v1",
                     "boundary": "draw-before-delay", "clock": "scheduled-elapsed-ms", "original_fidelity_claim": False} and
                     candidate[-1] == {"kind": "complete", "samples": 89, "original_fidelity_claim": False},
                     "incomplete C++ typing boundaries")
    out.mkdir(parents=True, exist_ok=True)
    changed, first, baseline_cpp = 0, None, None
    for index, (expected, actual) in enumerate(zip(native, candidate[1:-1])):
        metadata = {"kind": "sample", "sample": index, "line": expected["line"],
                    "step": expected["character"], "elapsed_ms": expected["elapsed_ms"],
                    "frame": f"typing_frame_{index:06d}.ppm"}
        fidelity.require(set(actual) == set(metadata) | {"state"} and
                         all(type(actual.get(key)) is type(value) and actual[key] == value
                             for key, value in metadata.items()), "C++ typing schedule changed")
        fidelity.validate_state(actual["state"])
        # The host sound pump is outside this silent gameplay-freeze claim.
        frozen = {key: value for key, value in actual["state"].items() if key != "sound_latch"}
        if baseline_cpp is None:
            baseline_cpp = frozen
        fidelity.require(frozen == baseline_cpp, "C++ typing advanced gameplay, score or RNG")
        diff = fidelity.first_difference(original.project_original(expected["state"], 1, header["atlas"]),
                                         original.project_cpp(actual["state"], 1))
        if diff and first is None:
            first = {"sample": index, **diff}
        pixels = fidelity.read_ppm(fidelity.safe_file(cpp, actual["frame"]))
        count = sum(expected["rgb"][i:i + 3] != pixels[i:i + 3] for i in range(0, len(pixels), 3))
        if count and first is None:
            first = {"sample": index, "path": "$.rgb", "differing_pixels": count}
        changed += count
        if index in (0, 5, 22, 28, 49, 55, 65, 71, 88):
            try:
                from PIL import Image
            except ImportError:
                Image = None
            for name, rgb in (("original", expected["rgb"]), ("cpp", pixels)):
                frame_compare.write_ppm(out / f"{name}_{index:02d}.ppm", (320, 200, bytearray(rgb)))
                if Image is not None:
                    Image.frombytes("RGB", (320, 200), rgb).save(out / f"{name}_{index:02d}.png")
    reels = results.compare(cpp, out / "results")
    report = {"status": "match" if first is None and changed == 0 and reels["status"] == "match" else "diverged",
              "typing_frames": 89, "typing_steps": [23, 27, 16, 23], "typing_delay_ms": 81, "award_start_ms": 7709,
              "prefix_frames": reels["prefix_frames"], "prefix_states": reels["prefix_states"], "result_frames": 42,
              "pixels": reels["pixels"] + 89 * 64000, "differing_pixels": changed + reels["differing_pixels"],
              "first_difference": first or reels["first_difference"], "alignment": "native-draw-before-delay-boundaries",
              "wall_clock_claim": False, "typing_skip_claim": False, "level2_handoff_claim": False, "original_fidelity_claim": False,
              "cpp_executable_sha256": manifest["executable_sha256"], "cpp_trace_sha256": manifest["trace_sha256"],
              "cpp_typing_stream_sha256": fidelity.sha256(cpp / "result_typing.jsonl"), "reference_sha256": REFERENCE_SHA256}
    (out / "comparison.json").write_bytes(original.json_bytes(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    packer = commands.add_parser("pack")
    packer.add_argument("--capture", type=Path, required=True)
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
        report = pack(args.capture, args.out)
    elif args.command == "guard":
        report = guard()
    else:
        if args.command == "replay":
            args.out.mkdir(parents=True, exist_ok=True)
            cpp = args.out / ("run-" + uuid.uuid4().hex)
            fidelity.record(args.exe, ROOT, FIXTURE / "route.txt", cpp, original_intro_wait=True,
                            result_reels=True, result_typing=True)
            out = cpp / "comparison"
        else:
            cpp, out = args.cpp, args.out
        report = compare(cpp, out)
        fidelity.require(report["status"] == "match", "native typing comparison diverged: " + json.dumps(report["first_difference"]))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
