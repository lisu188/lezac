"""Pinned natural Level 1 acknowledgment and Level 2 production comparison."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import shutil
import uuid

import frame_compare
import level1_fidelity as fidelity
import level1_original as original
import level1_results as results

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/level1_handoff"
PREFIX = results.PREFIX
FRAMES, FIRST_TICK = 12, 731
REFERENCE_SHA256 = "5cb0fb3dddceb0b6d4a7e90530724205aae75e9f98ebc80500c8857885ab20b3"
PREFIX_SHA256 = "18c029dcc107cf95b088a914cf60aa05fd30fbaf26501e3b2367ee91cd96ace8"
OBSERVER_SHA256 = "0af5c0a1f0ef7f87c4898ecc512784db315d281547b97bf45e57bfa5c87b1985"
BASE_SHA256 = "f1797c57fe6363f9e189fb2ab0b9c76d32b5d2f46305458e2ba513b1d7d18758"
TYPING_SHA256 = "53285006b7ce80b60f5a929f931478b6514fbb40815e3cc9b1d19007f9e0d76e"
CLAIMS = ("manual_input_claim", "wall_clock_claim", "all_actor_fields_compared", "original_fidelity_claim")
PALETTE_INDICES = tuple(i for i in range(256) if not 176 <= i <= 214)


def exact_fields(value, expected, message):
    fidelity.require(isinstance(value, dict) and
                     all(type(value.get(key)) is type(item) and value[key] == item
                         for key, item in expected.items()), message)


def load(path):
    with gzip.open(path, "rt", encoding="ascii") as stream:
        return [fidelity.strict_json(line) for line in stream]


def dac(value):
    data = original.hex_bytes(value, 768)
    fidelity.require(all(component <= 63 for component in data), "native DAC component exceeds six bits")
    return data


def validate_level2(state):
    fidelity.require(isinstance(state, dict) and set(state) == original.RAW_FIELDS, "invalid Level 2 schema")
    original.hex_bytes(state["tiles"], 5300)
    original.hex_bytes(state["words"], 10600)
    # Reuse the pinned non-map contract only after validating both complete larger planes.
    original.validate_raw({**state, "tiles": state["tiles"][:3960], "words": state["words"][:7920]})
    for player in state["players"]:
        for key, low, high in (("xy", 0, 65535), ("v", -32768, 32767), ("f", 0, 255)):
            fidelity.require(isinstance(player[key], list) and len(player[key]) == 2 and
                             all(fidelity.integer(v, low, high) for v in player[key]), "invalid decoded native player")
    inventory = original.hex_bytes(state["inventory"], 12)
    fidelity.require(inventory[:10].hex() == "c8140500c81406000101", "Level 2 inventory refilled or selection retained")
    fidelity.require(bytes.fromhex(state["globals"])[0x17] == 2, "native boundary is not Level 2")


def validate(rows):
    fidelity.require(isinstance(rows, list) and len(rows) == FRAMES + 2, "incomplete native handoff")
    header, footer = rows[0], rows[-1]
    expected = {"kind": "header", "schema": "lezac-natural-level1-handoff-v1",
                "exe_sha256": original.EXE_SHA256, "observer_sha256": OBSERVER_SHA256,
                "base_observer_sha256": BASE_SHA256, "typing_observer_sha256": TYPING_SHA256,
                "prefix_route_sha256": fidelity.sha256(PREFIX / "route.txt"),
                "entry": 0x2049, "intro_entry": 0x2C72, "signature": "9a0f034a08", "frames": FRAMES,
                **dict.fromkeys(CLAIMS, False)}
    exact_fields(header, expected, "invalid native handoff header or producer")
    fidelity.require(set(header) == set(expected) | {"baseline", "baseline_dac", "intro", "intro_dac", "ack", "atlas", "dimensions"},
                     "unexpected handoff header fields")
    fidelity.require(header["dimensions"] == [100, 53] and
                     all(type(v) is int for v in header["dimensions"]) and
                     fidelity.integer(header["atlas"], 0, 65535), "invalid native dimensions or atlas")
    expected_footer = {"kind": "complete", "frames": FRAMES, "patches_restored": True,
                       **dict.fromkeys(("manual_input_claim", "wall_clock_claim", "original_fidelity_claim"), False)}
    exact_fields(footer, expected_footer, "incomplete native handoff footer")
    fidelity.require(set(footer) == set(expected_footer), "unexpected handoff footer fields")
    baseline = header["baseline"]
    original.validate_raw(baseline)
    _, reels = results.fixture()
    fidelity.require(all(baseline[key] == reels[-1]["state"][key] for key in results.FROZEN + ("scores", "rng")),
                     "handoff no longer follows the pinned natural results")
    fidelity.require(dac(header["baseline_dac"])[765:] == bytes((31, 31, 31)), "results palette baseline changed")
    ack = header["ack"]
    fidelity.require(isinstance(ack, dict) and set(ack) == {"head", "tail", "key_word", "bda_hex"} and
                     all(fidelity.integer(ack[k], 0, 65535) for k in ("head", "tail", "key_word")), "invalid acknowledgment metadata")
    bios = original.hex_bytes(ack["bda_hex"], 64)
    head, tail = ack["head"], ack["tail"]
    fidelity.require(0x1E <= head < 0x3E and head % 2 == 0 and tail == (head + 2 if head < 0x3C else 0x1E) and
                     original.word(bios, 0x1A) == head and original.word(bios, 0x1C) == tail and
                     original.word(bios, head) == ack["key_word"] == 0x1C0D, "acknowledgment was not fresh Return")
    intro = header["intro"]
    validate_level2(intro)
    fidelity.require(intro["frame"] == 305 and intro["rng"] == 2497022769 and
                     bytes.fromhex(intro["globals"])[13] == bytes.fromhex(baseline["globals"])[13] == 34,
                     "intro advanced gameplay or reset the red animation phase")
    initial, intro_dac = (ROOT / "BOMPAL.PAL").read_bytes(), dac(header["intro_dac"])
    fidelity.require(len(initial) == 768 and all(intro_dac[i*3:i*3+3] == initial[i*3:i*3+3]
                     for i in range(256) if not 176 <= i <= 182), "intro did not reload the full BOMPAL palette")
    previous, samples, phase = bytes(192000), [], 34
    registers = None
    for index, row in enumerate(rows[1:-1]):
        exact_fields(row, {"kind": "sample", "sample": index}, "invalid native sample index")
        fidelity.require(set(row) == {"kind", "sample", "registers", "sequences", "pre", "rendered", "post", "dac",
                                     "rgb_delta_zlib_hex", "rgb_sha256"}, "unexpected native sample fields")
        fidelity.require(row["sequences"] == [919 + index*3 + i for i in range(3)] and
                         all(type(v) is int for v in row["sequences"]), "skipped native boundary")
        fidelity.require(isinstance(row["registers"], list) and len(row["registers"]) == 3, "missing phase registers")
        for reg in row["registers"]:
            fidelity.require(isinstance(reg, list) and len(reg) == 6 and
                             all(fidelity.integer(v, 0, 65535) for v in reg), "invalid phase registers")
            if registers is None:
                registers = reg
            fidelity.require(reg[:2] == registers[:2] and reg[3] == registers[3] and
                             reg[1] - reg[0] == original.seeder.RUNTIME_DS - 0x01ED, "native segment relation changed")
        fidelity.require(isinstance(row["dac"], list) and len(row["dac"]) == 3, "missing native palette boundary")
        for value in row["dac"]:
            dac(value)
        for name in ("pre", "rendered", "post"):
            state = row[name]
            validate_level2(state)
            fidelity.require(state["frame"] == 306 + index and state["rng"] == 4248953211,
                             "native handoff frame or RNG changed")
            expected_phase = phase
            if name == "post" and state["frame"] % 5 == 0:
                expected_phase += 7
            fidelity.require(bytes.fromhex(state["globals"])[13] == expected_phase, "red phase lifecycle changed")
        fidelity.require(original.project_original(row["pre"], 1, header["atlas"]) ==
                         original.project_original(row["rendered"], 1, header["atlas"]), "render hook mutated gameplay")
        phase = bytes.fromhex(row["post"]["globals"])[13]
        previous = original.decode_frame(row["rgb_delta_zlib_hex"], previous, row["rgb_sha256"])
        samples.append({**row, "rgb": previous})
    return samples


def check_sources():
    for path, digest in (("tools/capture_original_level1_handoff.py", OBSERVER_SHA256),
                         ("tools/level1_original.py", BASE_SHA256),
                         ("tools/capture_original_level1_typing.py", TYPING_SHA256)):
        fidelity.require(fidelity.sha256(ROOT / path) == digest, "handoff producer changed: " + path)
    image = original.check_executable(ROOT / "LEZAC.EXE")
    for offset, code in {0x2049: "9a0f034a08", 0x2C72: "9a0f034a08",
                         0x2AF2: "c606741b01c606751b01", 0x2F69: "c6066c1bc8c6066d1b14c6066e1b06c6066f1b00",
                         0x2BF9: "bfa72a0e57e808db", 0x78C: "89fab90001bb0000b81210cd10"}.items():
        fidelity.require(image[offset:offset + len(code)//2].hex() == code, "handoff native instruction changed")
    fidelity.require(image[0x2AA7:0x2AB2] == b"\nbompal.pal", "native palette filename changed")


def check_route(path):
    settings, events = fidelity.read_route(path)
    prefix_settings, prefix_events = original.read_route(PREFIX / "route.txt")
    fidelity.require(settings["ticks"] == 742 and
                     all(settings[k] == prefix_settings[k] for k in ("seed", "step_us")) and
                     events == {**prefix_events, 660: [{"action": "down", "key": "return"}],
                                661: [{"action": "up", "key": "return"}],
                                730: [{"action": "down", "key": "return"}],
                                731: [{"action": "up", "key": "return"}]}, "handoff route changed")


def fixture():
    check_sources()
    check_route(FIXTURE / "route.txt")
    manifest = fidelity.strict_json((FIXTURE / "capture.json").read_text())
    expected = {"schema": "lezac-level1-handoff-fixture-v1", "frames": FRAMES, "patches_restored": True,
                "prefix_canonical_sha256": PREFIX_SHA256, "observer_sha256": OBSERVER_SHA256,
                "base_observer_sha256": BASE_SHA256, "typing_observer_sha256": TYPING_SHA256,
                **dict.fromkeys(CLAIMS, False)}
    exact_fields(manifest, expected, "invalid handoff fixture scope")
    fidelity.require(set(manifest) == set(expected) | {"files"} and
                     set(manifest["files"]) == {"reference.jsonl.gz", "route.txt"}, "invalid fixture inventory")
    for name, digest in manifest["files"].items():
        fidelity.require(fidelity.sha256(fidelity.safe_file(FIXTURE, name)) == digest, "handoff fixture checksum changed")
    fidelity.require(manifest["files"]["reference.jsonl.gz"] == REFERENCE_SHA256 and
                     original.fingerprint(PREFIX) == PREFIX_SHA256, "handoff or prefix pin changed")
    rows = load(FIXTURE / "reference.jsonl.gz")
    return rows[0], validate(rows)


def pack(capture, out):
    check_sources()
    check_route(FIXTURE / "route.txt")
    fidelity.require(not (capture / "failure.json").exists() and
                     original.fingerprint(capture) == original.fingerprint(PREFIX) == PREFIX_SHA256,
                     "failed capture or changed natural prefix")
    source = capture / "handoff.jsonl.gz"
    fidelity.require(fidelity.sha256(source) == REFERENCE_SHA256 and source.stat().st_size <= 131072 and
                     fidelity.sha256(capture / "observer.py") == OBSERVER_SHA256, "capture identity or compact reserve changed")
    validate(load(source))
    fidelity.require(not out.exists() or (out == FIXTURE and {p.name for p in out.iterdir()} == {"route.txt"}),
                     "fixture output already contains evidence")
    out.mkdir(parents=True, exist_ok=True)
    if out != FIXTURE:
        shutil.copyfile(FIXTURE / "route.txt", out / "route.txt")
    shutil.copyfile(source, out / "reference.jsonl.gz")
    manifest = {"schema": "lezac-level1-handoff-fixture-v1", "frames": FRAMES, "patches_restored": True,
                "prefix_canonical_sha256": PREFIX_SHA256, "observer_sha256": OBSERVER_SHA256,
                "base_observer_sha256": BASE_SHA256, "typing_observer_sha256": TYPING_SHA256,
                "files": {name: fidelity.sha256(out / name) for name in ("reference.jsonl.gz", "route.txt")},
                **dict.fromkeys(CLAIMS, False)}
    (out / "capture.json").write_bytes(original.json_bytes(manifest))
    return manifest


def boundary(state, palette):
    return {**original.project_cpp(state, 1), "level": state["level"],
            "p2_inventory": state["players"][1]["inventory"], "score": state["players"][0]["score"],
            "red_phase": state["presentation"][4],
            "palette": [palette[i*3:i*3+3].hex() for i in PALETTE_INDICES]}


def native_boundary(state, value, atlas):
    inventory, scores = bytes.fromhex(state["inventory"]), bytes.fromhex(state["scores"])
    palette = bytes((v << 2 | v >> 4 for v in dac(value)))
    return {**original.project_original(state, 1, atlas), "level": bytes.fromhex(state["globals"])[0x17],
            "p2_inventory": list(inventory[4:8]) + [inventory[9]-1], "score": int.from_bytes(scores[:4], "little"),
            "red_phase": bytes.fromhex(state["globals"])[13],
            "palette": [palette[i*3:i*3+3].hex() for i in PALETTE_INDICES]}


def compare(cpp, out):
    header, samples = fixture()
    manifest = fidelity.load_manifest(cpp)
    fidelity.require((cpp / "route.txt").read_bytes() == (FIXTURE / "route.txt").read_bytes(), "different replay input")
    fidelity.require(manifest["asset_sha256"] == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS},
                     "different replay assets")
    checkpoints = {}
    for row in fidelity.trace_rows(cpp, manifest):
        if row["kind"] == "header":
            fidelity.require(row["phase_model"] == "cpp-pre-actors-v2" and
                             row["input_model"] == "sdl-events-original-intro-wait-v1", "wrong replay boundary model")
        elif row["kind"] == "checkpoint" and row["phase"] in ("present", "post_update"):
            checkpoints[row["tick"], row["phase"]] = row
    fidelity.require(not out.exists(), "comparison output already exists")
    out.mkdir(parents=True)
    first, changed, prefix_frames, prefix_states, prefix_atlas = None, 0, 0, 0, None
    for expected in original.reference_rows(PREFIX):
        if expected["kind"] == "header":
            prefix_atlas = expected["atlas"]
        if expected["kind"] != "sample":
            continue
        tick = expected["cpp_tick"]
        for name, phase in (("rendered", "present"), ("post", "post_update")):
            fidelity.require((tick, phase) in checkpoints, "missing prefix boundary")
            diff = fidelity.first_difference(original.project_original(expected[name], 1, prefix_atlas),
                                             original.project_cpp(checkpoints[tick, phase]["state"], 1))
            prefix_states += 1
            if diff and first is None:
                first = {"region": "prefix", "tick": tick, "phase": phase, **diff}
        pixels = fidelity.read_ppm(cpp / f"frame_{tick:06d}.ppm")
        count = sum(expected["rgb"][i:i+3] != pixels[i:i+3] for i in range(0, len(pixels), 3))
        if count and first is None:
            first = {"region": "prefix", "tick": tick, "path": "$.rgb", "differing_pixels": count}
        changed += count
        prefix_frames += 1
    for index, expected in enumerate(samples):
        tick = FIRST_TICK + index
        for name, phase, pi in (("rendered", "present", 1), ("post", "post_update", 2)):
            fidelity.require((tick, phase) in checkpoints, "missing Level 2 boundary")
            state = checkpoints[tick, phase]["state"]
            diff = fidelity.first_difference(native_boundary(expected[name], expected["dac"][pi], header["atlas"]),
                                             boundary(state, bytes.fromhex(state["palette_rgb_hex"])))
            if diff and first is None:
                first = {"region": "level2", "sample": index, "phase": phase, **diff}
        pixels = fidelity.read_ppm(cpp / checkpoints[tick, "present"]["frame"])
        count = sum(expected["rgb"][i:i+3] != pixels[i:i+3] for i in range(0, len(pixels), 3))
        if count and first is None:
            first = {"region": "level2", "sample": index, "path": "$.rgb", "differing_pixels": count}
        changed += count
        if index in (0, 11):
            try:
                from PIL import Image
            except ImportError:
                Image = None
            for name, rgb in (("original", expected["rgb"]), ("cpp", pixels)):
                frame_compare.write_ppm(out / f"{name}_{index:02d}.ppm", (320, 200, bytearray(rgb)))
                if Image is not None:
                    Image.frombytes("RGB", (320, 200), rgb).save(out / f"{name}_{index:02d}.png")
    report = {"status": "match" if first is None and changed == 0 else "diverged", "prefix_frames": prefix_frames,
              "prefix_states": prefix_states, "level2_frames": len(samples), "level2_states": len(samples)*2,
              "pixels": (prefix_frames + len(samples))*64000, "differing_pixels": changed, "first_difference": first,
              "map_tiles_per_state": 5300, "map_word_bytes_per_state": 10600,
              "palette_entries_per_state": len(PALETTE_INDICES), "all_dac_entries_compared": False,
              "alignment": "native-render-and-post-update-boundaries", **dict.fromkeys(CLAIMS, False),
              "cpp_executable_sha256": manifest["executable_sha256"], "cpp_trace_sha256": manifest["trace_sha256"],
              "reference_sha256": REFERENCE_SHA256}
    (out / "comparison.json").write_bytes(original.json_bytes(report))
    return report


def guard():
    fixture()
    rows = load(FIXTURE / "reference.jsonl.gz")
    mutations = (lambda r: r.pop(), lambda r: r[-1].__setitem__("frames", 11),
                 lambda r: r[-1].__setitem__("patches_restored", False),
                 lambda r: r[0].__setitem__("manual_input_claim", True),
                 lambda r: r[0].__setitem__("observer_sha256", "0"*64),
                 lambda r: r[0]["ack"].__setitem__("key_word", 0),
                 lambda r: r[0]["ack"].__setitem__("head", True),
                 lambda r: r[0]["intro"].__setitem__("rng", 0),
                 lambda r: r[0].__setitem__("intro_dac", r[0]["baseline_dac"]),
                 lambda r: r[1].__setitem__("sample", False),
                 lambda r: r[1]["sequences"].__setitem__(0, True),
                 lambda r: r[1]["registers"][0].__setitem__(0, True),
                 lambda r: r[1]["pre"].__setitem__("tiles", r[1]["pre"]["tiles"][:-2]),
                 lambda r: r[1]["post"].__setitem__("words", r[1]["post"]["words"][:-2]),
                 lambda r: r[1]["pre"].__setitem__("inventory", "c8140600" + r[1]["pre"]["inventory"][8:]),
                 lambda r: r[1]["post"].__setitem__("inventory", r[1]["post"]["inventory"][:8] + "c8140500" + r[1]["post"]["inventory"][16:]),
                 lambda r: r[1]["post"].__setitem__("frame", True),
                 lambda r: r[1]["post"].__setitem__("rng", 0),
                 lambda r: r[1]["dac"].__setitem__(0, "ff" + r[1]["dac"][0][2:]),
                 lambda r: r[1].__setitem__("rgb_sha256", "0"*64),
                 lambda r: r[1]["rendered"].__setitem__("tiles", ("01" if r[1]["rendered"]["tiles"][:2] != "01" else "00") + r[1]["rendered"]["tiles"][2:]))
    for mutate in mutations:
        damaged = copy.deepcopy(rows)
        mutate(damaged)
        try:
            validate(damaged)
        except fidelity.EvidenceError:
            continue
        raise fidelity.EvidenceError("damaged handoff evidence was accepted")
    sample = rows[1]
    expected = native_boundary(sample["rendered"], sample["dac"][1], rows[0]["atlas"])
    p = expected["players"][0]
    palette = bytes((v << 2 | v >> 4 for v in dac(sample["dac"][1])))
    candidate = {"logic_tick": expected["frame"], "random_seed": expected["rng"],
                 "tiles_hex": expected["tiles_hex"], "words_hex": expected["words_hex"],
                 "level": expected["level"], "progress": expected["progress"], "hud": expected["hud"],
                 "presentation": [0, 0, 0, 0, expected["red_phase"]], "palette_rgb_hex": palette.hex(),
                 "players": [{"x": p["xy"][0], "y": p["xy"][1], "vx8": p["velocity"][0], "vy8": p["velocity"][1],
                              "frac_x": p["fractions"][0], "frac_y": p["fractions"][1], "animation": p["animation"],
                              "health": [p["energy"], p["reserve"]], "inventory": p["inventory"], "hud_score": p["reel"],
                              "score": expected["score"]}, {"inventory": expected["p2_inventory"]}]}
    fidelity.require(fidelity.first_difference(expected, boundary(candidate, palette)) is None, "comparison projection changed")
    cpp_mutations = (lambda s: s.__setitem__("level", 1),
                     lambda s: s.__setitem__("tiles_hex", s["tiles_hex"][:-2] + "ff"),
                     lambda s: s.__setitem__("words_hex", s["words_hex"][:-4] + "ffff"),
                     lambda s: s["players"][0]["inventory"].__setitem__(2, 6),
                     lambda s: s["players"][1]["inventory"].__setitem__(2, 5),
                     lambda s: s["players"][0].__setitem__("score", 5860),
                     lambda s: s["presentation"].__setitem__(4, 0),
                     lambda s: s.__setitem__("palette_rgb_hex", s["palette_rgb_hex"][:1530] + "7d7d7d"),
                     lambda s: s.__setitem__("logic_tick", True))
    for mutate in cpp_mutations:
        damaged = copy.deepcopy(candidate)
        mutate(damaged)
        fidelity.require(fidelity.first_difference(expected, boundary(damaged, bytes.fromhex(damaged["palette_rgb_hex"]))) is not None,
                         "comparison missed a damaged C++ boundary")
    return {"status": "guarded", "frames": FRAMES, "native_mutations_rejected": len(mutations),
            "cpp_mutations_rejected": len(cpp_mutations), "mutations_rejected": len(mutations) + len(cpp_mutations),
            "original_fidelity_claim": False}


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
            cpp = args.out / ("run-" + uuid.uuid4().hex)
            fidelity.record(args.exe, ROOT, FIXTURE / "route.txt", cpp, original_intro_wait=True)
            out = cpp / "comparison"
        else:
            cpp, out = args.cpp, args.out
        report = compare(cpp, out)
        fidelity.require(report["status"] == "match", "native handoff comparison diverged: " + json.dumps(report["first_difference"]))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
