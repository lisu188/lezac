from __future__ import annotations

import argparse
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from typing import Any, Iterator

import level1_fidelity as fidelity
import seed_original_level as seeder

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = fidelity.sha256(Path(__file__))
SCHEMA = "lezac-level1-original-v1"
EXE_SHA256 = "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec"
HOOKS = ((0x77D2, "31c0a3c278"), (0x7A13, "803ee67900"),
         (0x7A57, "c606e87900"), (0x8283, "803ec57900"))
BANK = {key: 0x1B78 + i for i, key in enumerate(
    ("m", "z", "x", "n", "c", "up", "left", "right", "insert", "down"))}
SCRATCH, TRAMPOLINES, SCRATCH_SIZE = 0x800, 0x200, 0x614
RESIDENT_PARAGRAPHS = 0x100
RESIDENT_MARKER = b"LEZAC-L1-ORACLE-RESIDENT-V1\0"
REGISTER_ENCODING = "saved-far-call-caller-v1"
PREVIEW_DRAWS, PREFIX_TICKS = 390, 3
RAW_FIELDS = {"frame", "rng", "players", "inventory", "scores", "destruction",
              "actor_count", "actors", "visuals", "globals", "progress", "spawners", "tiles", "words"}
PROJECTION = "active-player-motion-animation-health-inventory-score,hud-reels-palette-queue,map-planes,progress,rng-v1"
LIMITS = ["one-controlled-rng-seed-before-level-initialization", "normalized-control-bank-event-injection",
          "main-routine-paused-while-interrupts-continue", "not-host-typematic-timing", "no-audio-waveform-comparison",
          "actor-pool-bytes-retained-but-not-all-fields-compared"]
require = fidelity.require


def resident_program() -> bytes:
    image = bytearray(RESIDENT_PARAGRAPHS * 16 - 0x100)
    code = bytes.fromhex("0e58a36001") + b"\xba" + struct.pack("<H", RESIDENT_PARAGRAPHS) + bytes.fromhex("b80031cd21")
    image[:len(code)] = code
    image[0x20:0x20 + len(RESIDENT_MARKER)] = RESIDENT_MARKER
    return bytes(image)


def far_call(offset: int, segment: int) -> bytes:
    return b"\x9a" + struct.pack("<HH", offset, segment)


def trampoline(stage: int, image: bytes) -> bytes:
    entry, original = HOOKS[stage - 1]
    code = bytearray.fromhex("9c6089e5")
    for i, operation in enumerate(("8b4614", "8cd8", "8cc0", "8cd0", "89e883c016", "8b4604")):
        code += bytes.fromhex(operation) + b"\x2e\xa3" + struct.pack("<H", SCRATCH + 2 + i * 2)
    code += b"\x2e\x66\xff\x06" + struct.pack("<H", SCRATCH + 16)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, stage)
    code += b"\x2e\x83\x3e" + struct.pack("<H", SCRATCH + 14) + bytes([stage]) + b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, 0)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH + 14, 0)
    code += b"\x61\x9d" + image[entry:entry + len(original) // 2] + b"\xcb"
    require(len(code) < 0x80, "trampoline overlaps its neighbour")
    return bytes(code)


def encode_frame(current: bytes, previous: bytes) -> str:
    return zlib.compress(bytes(a ^ b for a, b in zip(current, previous)), 6).hex()


def decode_frame(encoded: Any, previous: bytes, checksum: Any) -> bytes:
    require(isinstance(encoded, str) and len(encoded) <= 400000 and len(encoded) % 2 == 0,
            "invalid compressed original frame length")
    data = hex_bytes(encoded, len(encoded) // 2)
    decoder = zlib.decompressobj()
    delta = decoder.decompress(data, 192001)
    require(len(delta) == 192000 and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            "invalid compressed original full-frame payload")
    current = bytes(a ^ b for a, b in zip(delta, previous))
    require(hashlib.sha256(current).hexdigest() == checksum, "original full-frame checksum mismatch")
    return current


def check_executable(path: Path) -> bytes:
    require(fidelity.sha256(path) == EXE_SHA256, "unsupported original executable")
    image = path.read_bytes()[0x770:]
    for stage, (entry, original) in enumerate(HOOKS, 1):
        require(image[entry:entry + len(original) // 2].hex() == original, "original hook window changed")
        trampoline(stage, image)
    return image


def read_route(path: Path) -> tuple[dict[str, int], dict[int, list[dict[str, str]]]]:
    settings, events = fidelity.read_route(path)
    require(settings["ticks"] >= 5, "original route needs menu, introduction and gameplay")
    require(events.get(0) in ([{"action": "down", "key": "1"}], [{"action": "down", "key": "2"}]), "invalid original menu prefix")
    mode = events[0][0]["key"]
    require(events.get(1) == [{"action": "up", "key": mode}] and 2 not in events,
            "invalid original menu release")
    require(events.get(3) == [{"action": "down", "key": "return"}], "invalid introduction acknowledgement")
    require(events.get(4, [])[:1] == [{"action": "up", "key": "return"}], "introduction key must release before gameplay input")
    for tick, items in events.items():
        if tick < 4:
            continue
        for event in items:
            require(event["key"] in BANK or (tick == 4 and event == {"action": "up", "key": "return"}),
                    "unsupported original gameplay key; no silent UI-event substitution")
    return settings, events


def initial_seed(seed: int) -> int:
    for _ in range(PREVIEW_DRAWS):
        seed = (seed * 0x08088405 + 1) & 0xFFFFFFFF
    return seed


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def hex_bytes(value: Any, count: int) -> bytes:
    require(isinstance(value, str) and len(value) == count * 2 and re.fullmatch("[0-9a-f]*", value) is not None,
            "invalid original byte field")
    return bytes.fromhex(value)


def word(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def validate_raw(state: Any) -> None:
    require(isinstance(state, dict) and set(state) == RAW_FIELDS, "invalid original state schema")
    require(fidelity.integer(state["frame"], 0, 65535) and fidelity.integer(state["rng"], 0, 2**32 - 1), "invalid original counters")
    require(fidelity.integer(state["actor_count"], 0, 30), "invalid original actor count")
    for key, length in {"inventory": 12, "scores": 92, "destruction": 4, "globals": 90,
                        "progress": 36, "tiles": 1980, "words": 3960, "actors": state["actor_count"] * 38}.items():
        hex_bytes(state[key], length)
    for key, width, maximum in (("visuals", 8, 32), ("spawners", 30, 32)):
        require(isinstance(state[key], str) and len(state[key]) % (width * 2) == 0 and len(state[key]) <= width * maximum * 2,
                "invalid original table size")
        hex_bytes(state[key], len(state[key]) // 2)
    require(isinstance(state["players"], list) and len(state["players"]) == 2, "missing original player")
    for player in state["players"]:
        require(isinstance(player, dict) and set(player) == {"raw", "visual", "xy", "v", "f"}, "invalid original player fields")
        raw, visual = hex_bytes(player["raw"], 38), hex_bytes(player["visual"], 8)
        require(player["xy"] == list(struct.unpack_from("<HH", visual)) and
                player["v"] == list(struct.unpack_from("<hh", raw, 6)) and player["f"] == [raw[10], raw[12]],
                "original decoded player disagrees with retained bytes")


def project_original(state: dict[str, Any], count: int, atlas: int) -> dict[str, Any]:
    g, progress, scores, inventory = (bytes.fromhex(state[key]) for key in ("globals", "progress", "scores", "inventory"))
    players = []
    for i in range(count):
        p, reel = state["players"][i], scores[i * 46:(i + 1) * 46]
        raw = bytes.fromhex(p["raw"])
        players.append({"xy": [float(x) for x in p["xy"]], "velocity": p["v"], "fractions": p["f"],
                        "animation": list(raw[22:28]) + [struct.unpack_from("b", raw, 28)[0]],
                        "energy": raw[36], "reserve": g[0x4A + i],
                        "inventory": list(inventory[i * 4:i * 4 + 4]) + [inventory[8 + i] - 1],
                        "reel": [struct.unpack_from("<I", reel)[0], reel[44]] +
                        [((word(reel, at) - atlas) & 65535) for at in (*range(4, 22, 2), *range(24, 42, 2))]})
    return {"frame": state["frame"], "rng": state["rng"], "tiles_hex": state["tiles"], "words_hex": state["words"],
            "players": players, "progress": [word(progress, 18), word(bytes.fromhex(state["destruction"]), 2)],
            "hud": [word(progress, 20), g[0x16], g[0x15], int(g[0x4C] != 255), int(g[0x4D] != 255), g[0x2B],
                    *g[0x2E:0x30], *g[0x32:0x38], *g[0x3C:0x42]]}


def project_cpp(state: dict[str, Any], count: int) -> dict[str, Any]:
    players = []
    for p in state["players"][:count]:
        players.append({"xy": [p["x"], p["y"]], "velocity": [p["vx8"], p["vy8"]],
                        "fractions": [p["frac_x"], p["frac_y"]], "animation": p["animation"],
                        "energy": p["health"][0], "reserve": p["health"][1] & 255,
                        "inventory": p["inventory"], "reel": p["hud_score"]})
    return {"frame": state["logic_tick"] & 65535, "rng": state["random_seed"],
            "tiles_hex": state["tiles_hex"], "words_hex": state["words_hex"], "players": players,
            "progress": state["progress"][:2], "hud": state["hud"]}


@contextmanager
def compressed_writer(path: Path):
    with path.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=6) as stream:
        yield lambda value: stream.write(json_bytes(value))


def reference_rows(root: Path) -> Iterator[dict[str, Any]]:
    manifest = fidelity.strict_json(fidelity.safe_file(root, "manifest.json").read_text())
    require(set(manifest) == {"schema", "status", "files", "assets", "original_fidelity_claim"}, "invalid original manifest")
    require(manifest["schema"] == SCHEMA and manifest["status"] == "captured" and manifest["original_fidelity_claim"] is False,
            "unqualified original manifest")
    require(set(manifest["files"]) == {"reference.jsonl.gz", "route.txt", "initial-ds.bin", "backdrop.bin", "dosbox.conf", "L1ORACLE.COM"}, "invalid original file inventory")
    for name, digest in manifest["files"].items():
        require(fidelity.sha256(fidelity.safe_file(root, name)) == digest, "original file checksum mismatch: " + name)
    require(set(manifest["assets"]) == set(fidelity.ASSETS), "invalid original asset inventory")
    for name, digest in manifest["assets"].items():
        require(re.fullmatch("[0-9a-f]{64}", digest) is not None and fidelity.sha256(ROOT / name) == digest,
                "original asset provenance mismatch")
    settings, events = read_route(root / "route.txt")
    initial = (root / "initial-ds.bin").read_bytes()
    require(len(initial) == 65536 and (root / "backdrop.bin").stat().st_size == 60000, "truncated original initialization")
    atlas = word(initial, 0x2070)
    expected_count, index = settings["ticks"] - PREFIX_TICKS, 0
    previous_pixels = bytes(192000)
    require((root / "L1ORACLE.COM").read_bytes() == resident_program(), "unexpected resident instrumentation loader")
    ended = False
    with gzip.open(root / "reference.jsonl.gz", "rt", encoding="ascii") as stream:
        first = stream.readline(4 * 1024 * 1024)
        header = fidelity.strict_json(first)
        require(set(header) == {"kind", "schema", "exe_sha256", "settings", "initial_rng", "preview_draws", "prefix_ticks", "hooks",
                               "limits", "projection", "registers", "register_encoding", "resident_segment", "resident_mcb", "atlas", "dimensions", "source_sha256", "dosbox_sha256", "original_fidelity_claim"},
                "invalid original header fields")
        require(header["kind"] == "header" and header["schema"] == SCHEMA and header["exe_sha256"] == EXE_SHA256 and
                header["settings"] == settings and header["initial_rng"] == initial_seed(settings["seed"]) and
                header["preview_draws"] == PREVIEW_DRAWS and header["prefix_ticks"] == PREFIX_TICKS and
                header["hooks"] == [[at, raw] for at, raw in HOOKS] and header["limits"] == LIMITS and
                header["projection"] == PROJECTION and header["dimensions"] == [320, 200] and header["atlas"] == atlas and
                header["register_encoding"] == REGISTER_ENCODING and
                header["original_fidelity_claim"] is False, "invalid original capture contract")
        segment = header["resident_segment"]
        require(fidelity.integer(segment, 1, 0xA000 - RESIDENT_PARAGRAPHS), "invalid resident segment")
        mcb = hex_bytes(header["resident_mcb"], 16)
        require(mcb[0] in (ord("M"), ord("Z")) and word(mcb, 1) == segment and word(mcb, 3) >= RESIDENT_PARAGRAPHS, "instrumentation memory is not DOS-owned")
        for field in ("source_sha256", "dosbox_sha256"):
            require(isinstance(header[field], str) and re.fullmatch("[0-9a-f]{64}", header[field]) is not None, "missing capture executable identity")
        registers = header["registers"]
        require(isinstance(registers, list) and len(registers) == 6 and all(fidelity.integer(r, 0, 65535) for r in registers), "invalid original registers")
        require(registers[1] - registers[0] == seeder.RUNTIME_DS - 0x01ED, "invalid CS/DS relationship")
        yield header
        while True:
            line = stream.readline(4 * 1024 * 1024)
            if not line:
                break
            require(not ended and line.endswith("\n"), "late or oversized original record")
            row = fidelity.strict_json(line)
            if row.get("kind") == "complete":
                require(set(row) == {"kind", "samples", "frames", "patches_restored", "original_fidelity_claim"} and
                        row["samples"] == row["frames"] == index == expected_count and row["patches_restored"] is True and
                        row["original_fidelity_claim"] is False, "incomplete original capture")
                ended = True
            else:
                require(set(row) == {"kind", "sample", "cpp_tick", "events", "registers", "sequences", "pre", "rendered", "post", "rgb_delta_zlib_hex", "rgb_sha256"} and
                        row["kind"] == "sample" and row["sample"] == index < expected_count and
                        row["cpp_tick"] == index + PREFIX_TICKS + 1 and
                        row["events"] == [e for e in events.get(index + PREFIX_TICKS, []) if e["key"] in BANK] and
                        row["sequences"] == [2 + index * 3, 3 + index * 3, 4 + index * 3], "original route/sequence mismatch")
                require(isinstance(row["registers"], list) and len(row["registers"]) == 3, "missing original phase registers")
                for reg in row["registers"]:
                    require(isinstance(reg, list) and len(reg) == 6 and all(fidelity.integer(r, 0, 65535) for r in reg) and
                            reg[:2] == registers[:2] and reg[3] == registers[3], "original phase register mismatch")
                for phase in ("pre", "rendered", "post"):
                    validate_raw(row[phase])
                    require(row[phase]["frame"] == (index + 1) & 65535, "original skipped/duplicate frame")
                require(project_original(row["pre"], int(events[0][0]["key"]), atlas) ==
                        project_original(row["rendered"], int(events[0][0]["key"]), atlas), "render hook mutated compared gameplay state")
                previous_pixels = decode_frame(row["rgb_delta_zlib_hex"], previous_pixels, row["rgb_sha256"])
                row["rgb"] = previous_pixels
                index += 1
            yield row
    require(ended, "missing original completion record")


def fingerprint(reference: Path) -> str:
    digest = hashlib.sha256()
    count = 1
    atlas = 0
    for row in reference_rows(reference):
        if row["kind"] == "header":
            atlas = row["atlas"]
            _, events = read_route(reference / "route.txt")
            count = int(events[0][0]["key"])
            digest.update(json_bytes({key: row[key] for key in
                ("schema", "exe_sha256", "settings", "initial_rng", "preview_draws", "prefix_ticks", "hooks", "limits", "projection")}))
        elif row["kind"] == "sample":
            digest.update(json_bytes({"sample": row["sample"], "tick": row["cpp_tick"], "events": row["events"],
                "present": project_original(row["rendered"], count, atlas),
                "post": project_original(row["post"], count, atlas), "rgb_sha256": row["rgb_sha256"]}))
        else:
            digest.update(json_bytes(row))
    return digest.hexdigest()


def compare(reference: Path, candidate: Path, out: Path | None = None) -> dict[str, Any]:
    require(not out or not out.exists(), "comparison output already exists")
    manifest = fidelity.load_manifest(candidate)
    require((reference / "route.txt").read_bytes() == (candidate / "route.txt").read_bytes(), "different input streams")
    cpp_header = None
    checkpoints = {}
    for row in fidelity.trace_rows(candidate, manifest):
        if row["kind"] == "header":
            cpp_header = row
        elif row["kind"] == "checkpoint" and row.get("phase") in ("present", "post_update"):
            checkpoints[row["tick"], row["phase"]] = row["state"]
    require(cpp_header is not None and cpp_header["phase_model"] == "cpp-pre-actors-v2", "original replay requires pre-actor presentation")
    count = 1
    frames = states = changed_pixels = 0
    first = first_frames = header = None
    for row in reference_rows(reference):
        if row["kind"] == "header":
            header = row
            _, events = read_route(reference / "route.txt")
            count = int(events[0][0]["key"])
        elif row["kind"] == "sample":
            tick = row["cpp_tick"]
            for source, phase in (("rendered", "present"), ("post", "post_update")):
                require((tick, phase) in checkpoints, "missing C++ phase")
                expected = project_original(row[source], count, header["atlas"])
                actual = project_cpp(checkpoints[tick, phase], count)
                difference = fidelity.first_difference(expected, actual)
                states += 1
                if difference is not None and first is None:
                    first = {"sample": row["sample"], "tick": tick, "phase": phase, **difference}
            original = row["rgb"]
            actual_pixels = fidelity.read_ppm(candidate / f"frame_{tick:06d}.ppm")
            pixels = sum(original[i:i + 3] != actual_pixels[i:i + 3] for i in range(0, len(original), 3)) if original != actual_pixels else 0
            changed_pixels += pixels
            frames += 1
            if pixels and first is None:
                pixel = next(i // 3 for i in range(0, len(original), 3) if original[i:i + 3] != actual_pixels[i:i + 3])
                first = {"sample": row["sample"], "tick": tick, "phase": "present", "path": "$.rgb",
                         "x": pixel % 320, "y": pixel // 320}
            if first is not None and first_frames is None:
                first_frames = original, actual_pixels
    report = {"status": "match" if first is None else "diverged", "frames": frames, "states": states,
              "pixels": frames * 64000, "differing_pixels": changed_pixels, "first_divergence": first,
              "projection": PROJECTION, "limits": LIMITS, "original_fidelity_claim": False}
    if out:
        out.mkdir(parents=True)
        if first_frames:
            left, right = first_frames
            for name, data in (("original", left), ("candidate", right), ("difference", bytes(abs(a - b) for a, b in zip(left, right)))):
                (out / f"{name}.ppm").write_bytes(b"P6\n320 200\n255\n" + data)
        (out / "comparison.json").write_bytes(json_bytes(report))
    return report


class OriginalSession:
    def __init__(self, args: argparse.Namespace, run: Path, output: Path):
        self.args, self.run, self.output = args, run, output
        self.image = check_executable(ROOT / "LEZAC.EXE")
        self.settings, self.events = read_route(args.route)
        self.child = self.mem = None
        self.cs = self.ds = self.base = self.resident = self.resident_segment = 0
        self.sequence = 0
        self.patched, self.restored = False, False

    def read(self, at: int, count: int) -> bytes:
        value = os.pread(self.mem.fileno(), count, at)
        require(len(value) == count, "short owned-child memory read")
        return value

    def write(self, at: int, data: bytes) -> None:
        require(os.pwrite(self.mem.fileno(), data, at) == len(data), "short owned-child memory write")

    @contextmanager
    def stopped(self, resume: bool = True):
        require(self.child.poll() is None, "owned DOSBox exited")
        os.kill(self.child.pid, signal.SIGSTOP)
        try:
            deadline = time.monotonic() + 3
            while "State:\tT" not in Path(f"/proc/{self.child.pid}/status").read_text():
                require(time.monotonic() < deadline, "owned child failed to stop")
                time.sleep(.001)
            yield
        finally:
            if resume and self.child.poll() is None:
                os.kill(self.child.pid, signal.SIGCONT)

    def wait(self, stage: int) -> tuple[int, ...]:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            require(self.child.poll() is None, "owned DOSBox exited during capture")
            values = struct.unpack("<8HI", self.read(self.resident + SCRATCH, 20))
            if values[0] == stage and values[7] == 0 and values[8] == self.sequence + 1:
                self.sequence = values[8]
                require(values[2] - values[1] == seeder.RUNTIME_DS - 0x01ED, "runtime CS/DS changed")
                return values[1:7]
            time.sleep(.0005)
        raise fidelity.EvidenceError(f"original stage {stage} timeout; handshake={values}")

    def release(self, stage: int) -> None:
        self.write(self.resident + SCRATCH + 14, struct.pack("<H", stage))

    def xdo(self, *args: str) -> str:
        return subprocess.check_output(["xdotool", *args], text=True, timeout=15).strip()

    def screenshot(self) -> bytes:
        from PIL import ImageGrab
        deadline, previous = time.monotonic() + 2, None
        while time.monotonic() < deadline:
            time.sleep(.035)
            geometry = dict(item.split("=", 1) for item in self.xdo("getwindowgeometry", "--shell", self.window).splitlines())
            x, y, width, height = (int(geometry[key]) for key in ("X", "Y", "WIDTH", "HEIGHT"))
            require((width, height) == (320, 200), "original window is not an unscaled full VGA frame")
            image = ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).crop((x, y, x + width, y + height)).convert("RGB")
            pixels = image.tobytes()
            if pixels == previous:
                return pixels
            previous = pixels
        raise fidelity.EvidenceError("original frame did not stabilize at presentation hook")

    def state(self) -> dict[str, Any]:
        d = self.read(self.ds, 65536)
        def far(offset: int, size: int) -> bytes:
            off, segment = struct.unpack_from("<HH", d, offset)
            require(0 < segment < 0xA000, "unexpected original heap segment")
            return self.read(self.base + (segment << 4) + off, size)
        count, visuals = d[0x208D], d[0xC496]
        require(count <= 30 and visuals <= 32 and d[0x79A6] <= 32, "original actor table overflow")
        players = []
        for i in (1, 2):
            a = d[0x1B62 + i * 38:0x1B62 + (i + 1) * 38]
            require(a[1] < 32, "invalid player visual slot")
            v = d[0xC21E + a[1] * 8:0xC226 + a[1] * 8]
            players.append({"raw": a.hex(), "visual": v.hex(), "xy": list(struct.unpack_from("<HH", v)),
                            "v": list(struct.unpack_from("<hh", a, 6)), "f": [a[10], a[12]]})
        return {"frame": word(d, 0x78C2), "rng": struct.unpack_from("<I", d, 0x1AFE)[0], "players": players,
                "inventory": d[0x1B6C:0x1B78].hex(), "scores": d[0x785A:0x78B6].hex(),
                "destruction": d[0x78C6:0x78CA].hex(), "actor_count": count,
                "actors": d[0x1BD4:0x1BD4 + count * 38].hex(), "visuals": d[0xC21E:0xC21E + visuals * 8].hex(),
                "globals": d[0x79A0:0x79FA].hex(), "progress": d[0x2076:0x209A].hex(),
                "spawners": d[0x74C6:0x74C6 + d[0x79A6] * 30].hex(),
                "tiles": far(0xC1E0, 1980).hex(), "words": far(0x6612, 3960).hex()}

    def close(self) -> None:
        try:
            if self.child is not None and self.child.poll() is None:
                if self.patched:
                    with self.stopped(resume=False):
                        for entry, original in HOOKS:
                            self.write(self.cs + entry, bytes.fromhex(original))
                        self.write(self.resident + TRAMPOLINES, bytes(SCRATCH_SIZE))
                        self.restored = all(self.read(self.cs + entry, len(original) // 2).hex() == original for entry, original in HOOKS)
                        require(self.restored, "original hook restoration failed")
                self.child.kill()
                self.child.wait(timeout=5)
        finally:
            if self.child is not None and self.child.poll() is None:
                self.child.kill()
                self.child.wait(timeout=5)
            if self.mem is not None:
                self.mem.close()

    def capture(self, write_record) -> int:
        config = "[sdl]\nfullscreen=false\noutput=surface\n[dosbox]\nmemsize=16\n[render]\nframeskip=0\naspect=false\nscaler=none\n[cpu]\ncore=normal\ncycles=fixed 6000\n"
        (self.output / "dosbox.conf").write_text(config, encoding="ascii")
        (self.run / "L1ORACLE.COM").write_bytes(resident_program())
        (self.output / "L1ORACLE.COM").write_bytes(resident_program())
        with (self.output / "dosbox.log").open("w") as log:
            self.child = subprocess.Popen(["dosbox", "-conf", str(self.output / "dosbox.conf"), "-c", f"mount c {self.run}", "-c", "c:", "-c", "L1ORACLE.COM", "-c", "LEZAC.EXE"],
                                          env=dict(os.environ, SDL_AUDIODRIVER="dummy"), stdout=log, stderr=subprocess.STDOUT)
        time.sleep(self.args.startup_seconds)
        self.window = self.xdo("search", "--pid", str(self.child.pid), "--name", "DOSBox").splitlines()[-1]
        self.xdo("windowfocus", "--sync", self.window)
        self.mem = open(f"/proc/{self.child.pid}/mem", "r+b", buffering=0)
        matches = []
        for signature in seeder.scan_process(self.child.pid, seeder.DATA_SIGNATURE):
            ds = signature - seeder.DATA_STRING_OFFSET
            cs = ds - ((seeder.RUNTIME_DS - 0x01ED) << 4)
            if all(self.read(cs + at, len(raw) // 2).hex() == raw for at, raw in HOOKS):
                matches.append((cs, ds))
        require(len(matches) == 1, "original code/data mapping is ambiguous")
        self.cs, self.ds = matches[0]
        residents = []
        for marker in seeder.scan_process(self.child.pid, RESIDENT_MARKER):
            resident = marker - 0x120
            segment = word(self.read(resident + 0x160, 2), 0)
            mcb = self.read(resident - 16, 16)
            if mcb[0] in (ord("M"), ord("Z")) and word(mcb, 1) == segment and word(mcb, 3) >= RESIDENT_PARAGRAPHS:
                residents.append((resident, segment, mcb))
        require(len(residents) == 1, "resident instrumentation allocation is ambiguous")
        self.resident, self.resident_segment, mcb = residents[0]
        self.base = self.resident - (self.resident_segment << 4)
        require(self.cs >= self.resident + RESIDENT_PARAGRAPHS * 16, "instrumentation overlaps original executable")
        with self.stopped():
            require(self.read(self.resident + TRAMPOLINES, SCRATCH_SIZE) == bytes(SCRATCH_SIZE), "original scratch is occupied")
            self.patched = True
            for stage, (entry, _) in enumerate(HOOKS, 1):
                at = TRAMPOLINES + (stage - 1) * 0x80
                self.write(self.resident + at, trampoline(stage, self.image))
                self.write(self.cs + entry, far_call(at, self.resident_segment))
        mode = self.events[0][0]["key"]
        self.xdo("key", mode)
        time.sleep(.5)
        self.xdo("key", mode)
        registers = self.wait(1)
        require(self.base == self.cs - (registers[0] << 4), "resident allocation and caller segment disagree")
        self.write(self.ds + 0x1AFE, struct.pack("<I", initial_seed(self.settings["seed"])))
        self.release(1)
        time.sleep(self.args.intro_seconds)
        self.xdo("key", "Return")
        pre_registers = self.wait(2)
        initial = self.read(self.ds, 65536)
        require(initial[0x1B78:0x1B82] == bytes(10), "unexpected held original gameplay input")
        (self.output / "initial-ds.bin").write_bytes(initial)
        off, segment = struct.unpack_from("<HH", initial, 0xC498)
        (self.output / "backdrop.bin").write_bytes(self.read(self.base + (segment << 4) + off, 60000))
        write_record({"kind": "header", "schema": SCHEMA, "exe_sha256": EXE_SHA256, "settings": self.settings,
                      "initial_rng": initial_seed(self.settings["seed"]), "preview_draws": PREVIEW_DRAWS, "prefix_ticks": PREFIX_TICKS,
                      "hooks": HOOKS, "limits": LIMITS, "projection": PROJECTION, "registers": registers, "register_encoding": REGISTER_ENCODING,
                      "resident_segment": self.resident_segment, "resident_mcb": mcb.hex(),
                      "atlas": word(initial, 0x2070), "dimensions": [320, 200], "source_sha256": SOURCE_SHA256,
                      "dosbox_sha256": fidelity.sha256(Path(f"/proc/{self.child.pid}/exe")), "original_fidelity_claim": False})
        count = self.settings["ticks"] - PREFIX_TICKS
        previous_pixels = bytes(192000)
        for index in range(count):
            pre, sequence = self.state(), self.sequence
            events = [e for e in self.events.get(index + PREFIX_TICKS, []) if e["key"] in BANK]
            for event in events:
                self.write(self.ds + BANK[event["key"]], bytes([event["action"] != "up"]))
            self.release(2)
            render_registers = self.wait(3)
            rendered = self.state()
            pixels = self.screenshot()
            self.release(3)
            post_registers = self.wait(4)
            post = self.state()
            write_record({"kind": "sample", "sample": index, "cpp_tick": index + PREFIX_TICKS + 1, "events": events,
                          "registers": [pre_registers, render_registers, post_registers], "sequences": [sequence, sequence + 1, sequence + 2],
                          "pre": pre, "rendered": rendered, "post": post,
                          "rgb_delta_zlib_hex": encode_frame(pixels, previous_pixels), "rgb_sha256": hashlib.sha256(pixels).hexdigest()})
            previous_pixels = pixels
            if index % 50 == 0 or index + 1 == count:
                print(f"original_level1_sample={index + 1}/{count} xy={post['players'][0]['xy']} rng={post['rng']}", flush=True)
            if index + 1 != count:
                self.release(4)
                pre_registers = self.wait(2)
        return count


def capture(args: argparse.Namespace) -> dict[str, Any]:
    require(args.approve_procmem and args.approve_runtime_instrumentation, "explicit capture approvals required")
    check_executable(ROOT / "LEZAC.EXE")
    read_route(args.route)
    require(sys.platform.startswith("linux") and Path("/proc").is_dir(), "original capture requires Linux/WSL")
    require(1 <= args.startup_seconds <= 60 and 1 <= args.intro_seconds <= 60, "invalid original startup wait")
    for command in ("dosbox", "xdotool", "xvfb-run"):
        require(shutil.which(command) is not None, "missing capture tool: " + command)
    if not args.private_xvfb:
        env = dict(os.environ, SDL_AUDIODRIVER="dummy")
        env.pop("SDL_VIDEODRIVER", None)
        command = ["xvfb-run", "-a", sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--private-xvfb"]
        result = subprocess.run(command, env=env, timeout=3600)
        require(result.returncode == 0, "private original capture failed")
        return {"status": "captured", "out": str(args.out), "original_fidelity_claim": False}
    require(bool(os.environ.get("DISPLAY")), "private capture has no display")
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ.pop("SDL_VIDEODRIVER", None)
    output = args.out.resolve()
    require(output != ROOT and ROOT not in output.parents and not output.exists(), "capture requires a new output outside the repository")
    output.mkdir(parents=True)
    assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
    shutil.copyfile(args.route, output / "route.txt")
    session = None
    try:
        with tempfile.TemporaryDirectory(prefix="lezac-level1-original-") as temporary:
            run = Path(temporary)
            for path in ROOT.iterdir():
                if path.suffix.upper() in {".EXE", ".DAT", ".SPR", ".PAL", ".SCH", ".SON", ".MST", ".CAR", ".ZBG", ".DOC"}:
                    shutil.copyfile(path, run / path.name)
            session = OriginalSession(args, run, output)
            with compressed_writer(output / "reference.jsonl.gz") as write_record:
                try:
                    samples = session.capture(write_record)
                finally:
                    session.close()
                require(session.restored, "original instrumentation was not restored")
                write_record({"kind": "complete", "samples": samples, "frames": samples, "patches_restored": True, "original_fidelity_claim": False})
        require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, "shipped assets changed during capture")
        require(fidelity.sha256(Path(__file__)) == SOURCE_SHA256, "capture source changed during execution")
        files = {name: fidelity.sha256(output / name) for name in ("reference.jsonl.gz", "route.txt", "initial-ds.bin", "backdrop.bin", "dosbox.conf", "L1ORACLE.COM")}
        (output / "manifest.json").write_bytes(json_bytes({"schema": SCHEMA, "status": "captured", "assets": assets, "files": files, "original_fidelity_claim": False}))
        sum(1 for _ in reference_rows(output))
        return {"status": "captured", "samples": samples, "original_fidelity_claim": False}
    except BaseException as error:
        (output / "failure.json").write_bytes(json_bytes({"status": "incomplete", "error": str(error), "original_fidelity_claim": False}))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture and compare controlled original Level 1 input routes, without global fidelity claims.")
    sub = parser.add_subparsers(dest="command", required=True)
    live = sub.add_parser("capture")
    live.add_argument("--route", type=Path, required=True)
    live.add_argument("--out", type=Path, required=True)
    live.add_argument("--approve-procmem", action="store_true")
    live.add_argument("--approve-runtime-instrumentation", action="store_true")
    live.add_argument("--startup-seconds", type=float, default=10)
    live.add_argument("--intro-seconds", type=float, default=3)
    live.add_argument("--private-xvfb", action="store_true", help=argparse.SUPPRESS)
    verify = sub.add_parser("validate")
    verify.add_argument("reference", type=Path)
    identity = sub.add_parser("fingerprint")
    identity.add_argument("reference", type=Path)
    diff = sub.add_parser("compare")
    diff.add_argument("reference", type=Path)
    diff.add_argument("candidate", type=Path)
    diff.add_argument("--out", type=Path)
    sub.add_parser("self-check")
    args = parser.parse_args()
    try:
        if args.command == "capture":
            report = capture(args)
        elif args.command == "validate":
            records = sum(1 for _ in reference_rows(args.reference))
            report = {"status": "valid", "records": records, "original_fidelity_claim": False}
        elif args.command == "fingerprint":
            report = {"status": "valid", "sha256": fingerprint(args.reference), "original_fidelity_claim": False}
        elif args.command == "compare":
            report = compare(args.reference, args.candidate, args.out)
        else:
            check_executable(ROOT / "LEZAC.EXE")
            report = {"status": "valid", "hooks": len(HOOKS), "live": False, "original_fidelity_claim": False}
        print(json.dumps(report, sort_keys=True))
        return 1 if report["status"] == "diverged" else 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "invalid", "error": str(error), "original_fidelity_claim": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
