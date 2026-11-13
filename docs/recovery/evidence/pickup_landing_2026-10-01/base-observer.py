"""Private exploration of ordinary Level 2 play after the pinned natural handoff."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import capture_original_level1_handoff as producer
import frame_compare
import level1_fidelity as fidelity
import level1_handoff as handoff
import level1_original as original

FRAMES = 180
FIRST_TICK = handoff.FIRST_TICK + handoff.FRAMES
EVENTS = {0: [("down", "x")], 16: [("down", "m")], 36: [("up", "m")],
          80: [("up", "x")], 90: [("down", "z")], 105: [("up", "z")],
          115: [("down", "n")], 116: [("up", "n")],
          130: [("down", "x")], 160: [("up", "x")]}
CLAIMS = dict.fromkeys(handoff.CLAIMS, False)


def reserve(planned):
    stat = os.statvfs("/dev/shm")
    free, total = stat.f_bavail * stat.f_frsize, stat.f_blocks * stat.f_frsize
    fidelity.require(free - planned > total // 10, "RAM output would cross the 90-percent reserve")


def route_bytes():
    settings, events = fidelity.read_route(handoff.FIXTURE / "route.txt")
    lines = ["LEZAC_LEVEL1_ROUTE_V1", "seed " + str(settings["seed"]),
             "ticks " + str(settings["ticks"] + FRAMES), "step_us " + str(settings["step_us"])]
    merged = dict(events)
    for index, items in EVENTS.items():
        tick = FIRST_TICK - 1 + index
        fidelity.require(tick not in merged, "extension overlaps prefix input")
        merged[tick] = [{"action": action, "key": key} for action, key in items]
    for tick, items in sorted(merged.items()):
        for item in items:
            lines.append(f"event {tick} {item['action']} {item['key']}")
    return ("\n".join(lines + ["end", ""])).encode("ascii")


class ExtensionSession(producer.HandoffSession):
    def extend(self, emit):
        initial = self.dynamic_state()
        fidelity.require(initial["frame"] == 317, "extension did not begin at the verified boundary")
        data = self.read(self.ds, 65536)
        atlas = original.word(data, 0x2070)
        emit({"kind": "header", "schema": "lezac-private-level2-extension-v1", "frames": FRAMES,
              "first_tick": FIRST_TICK, "observer_sha256": fidelity.sha256(Path(__file__)),
              "base_handoff_observer_sha256": fidelity.sha256(ROOT / "tools/capture_original_level1_handoff.py"),
              "atlas": atlas, "initial": initial, "audio": "dummy", **CLAIMS})
        previous = bytes(192000)
        for index in range(FRAMES):
            self.release(4)
            pre_regs = self.wait(2)
            pre, sequence = self.dynamic_state(), self.sequence
            pre_dac = self.dac()
            events = [{"action": action, "key": key} for action, key in EVENTS.get(index, [])]
            for event in events:
                self.write(self.ds + original.BANK[event["key"]], bytes([event["action"] != "up"]))
            self.release(2)
            render_regs = self.wait(3)
            rendered, rendered_dac = self.dynamic_state(), self.dac()
            pixels = self.screenshot()
            if index in (0, 40, 80, 120, FRAMES - 1):
                frame_compare.write_ppm(self.output / f"extension-{index:03d}.ppm", (320, 200, bytearray(pixels)))
            self.release(3)
            post_regs = self.wait(4)
            post, post_dac = self.dynamic_state(), self.dac()
            fidelity.require(pre["frame"] == rendered["frame"] == post["frame"] == 318 + index,
                             "extension skipped a native frame")
            emit({"kind": "sample", "sample": index, "cpp_tick": FIRST_TICK + index,
                  "events": events, "registers": [pre_regs, render_regs, post_regs],
                  "sequences": [sequence, sequence + 1, sequence + 2],
                  "pre": pre, "rendered": rendered, "post": post,
                  "dac": [pre_dac, rendered_dac, post_dac],
                  "rgb_delta_zlib_hex": original.encode_frame(pixels, previous),
                  "rgb_sha256": hashlib.sha256(pixels).hexdigest()})
            previous = pixels
            if index % 20 == 0 or index + 1 == FRAMES:
                print(f"level2_extension={index+1}/{FRAMES} xy={post['players'][0]['xy']} "
                      f"actors={post['actor_count']} rng={post['rng']}", flush=True)


def capture(out):
    fidelity.require(os.environ.get("DISPLAY"), "private display required")
    fidelity.require(out.parent == Path("/dev/shm") and not out.exists(), "new RAM capture required")
    reserve(32 * 1024 * 1024)
    handoff.check_sources()
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ.pop("SDL_VIDEODRIVER", None)
    out.mkdir()
    shutil.copyfile(Path(__file__), out / "extension-observer.py")
    shutil.copyfile(ROOT / "tools/capture_original_level1_handoff.py", out / "observer.py")
    shutil.copyfile(producer.PREFIX / "route.txt", out / "route.txt")
    (out / "extension-route.txt").write_bytes(route_bytes())
    assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
    args = argparse.Namespace(route=producer.PREFIX / "route.txt", startup_seconds=10, intro_seconds=3)
    try:
        with tempfile.TemporaryDirectory(prefix="lezac-level2-extension-", dir="/dev/shm") as temporary:
            run = Path(temporary)
            for path in ROOT.iterdir():
                if path.suffix.upper() in {".EXE", ".DAT", ".SPR", ".PAL", ".SCH", ".SON", ".MST", ".CAR", ".ZBG", ".DOC"}:
                    shutil.copyfile(path, run / path.name)
            session = ExtensionSession(args, run, out)
            with original.compressed_writer(out / "reference.jsonl.gz") as prefix_emit, \
                    original.compressed_writer(out / "handoff.jsonl.gz") as handoff_emit, \
                    original.compressed_writer(out / "extension.jsonl.gz") as extension_emit:
                session.handoff_emit = handoff_emit
                try:
                    count = session.capture(prefix_emit)
                    session.extend(extension_emit)
                finally:
                    session.close()
                fidelity.require(session.restored and session.ack_restored and session.intro_restored, "hooks not restored")
                prefix_emit({"kind": "complete", "samples": count, "frames": count,
                             "patches_restored": True, "original_fidelity_claim": False})
                handoff_emit({"kind": "complete", "frames": producer.FRAMES, "patches_restored": True,
                              "manual_input_claim": False, "wall_clock_claim": False, "original_fidelity_claim": False})
                extension_emit({"kind": "complete", "frames": FRAMES, "patches_restored": True, **CLAIMS})
        fidelity.require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, "assets changed")
        files = {name: fidelity.sha256(out / name) for name in
                 ("reference.jsonl.gz", "route.txt", "initial-ds.bin", "backdrop.bin", "dosbox.conf", "L1ORACLE.COM")}
        (out / "manifest.json").write_bytes(original.json_bytes({"schema": original.SCHEMA, "status": "captured",
            "assets": assets, "files": files, "original_fidelity_claim": False}))
        canonical = original.fingerprint(out)
        fidelity.require(canonical == handoff.PREFIX_SHA256, "ordinary prefix differs from pinned evidence")
        handoff.validate(handoff.load(out / "handoff.jsonl.gz"))
        report = {"status": "captured", "frames": FRAMES, "prefix_canonical_sha256": canonical,
                  "extension_sha256": fidelity.sha256(out / "extension.jsonl.gz"),
                  "handoff_sha256": fidelity.sha256(out / "handoff.jsonl.gz"),
                  "observer_sha256": fidelity.sha256(out / "extension-observer.py"), "assets": assets, **CLAIMS}
        (out / "extension-manifest.json").write_bytes(original.json_bytes(report))
        print(original.json_bytes(report).decode("ascii"), flush=True)
    except BaseException as error:
        (out / "failure.json").write_bytes(original.json_bytes({"status": "incomplete", "error": str(error), **CLAIMS}))
        raise


def record(exe, out):
    fidelity.require(out.parent == Path("/dev/shm") and not out.exists(), "new RAM replay required")
    reserve(250 * 1024 * 1024)
    route = out.with_name(out.name + "-route.txt")
    fidelity.require(not route.exists(), "replay route already exists")
    route.write_bytes(route_bytes())
    print(fidelity.record(exe, ROOT, route, out, original_intro_wait=True), flush=True)


def compare(native, cpp, out):
    fidelity.require(not (native / "failure.json").exists(), "native capture is incomplete")
    manifest = fidelity.strict_json((native / "extension-manifest.json").read_text())
    fidelity.require(manifest["status"] == "captured" and manifest["prefix_canonical_sha256"] == handoff.PREFIX_SHA256
                     and manifest["extension_sha256"] == fidelity.sha256(native / "extension.jsonl.gz"), "native provenance differs")
    fidelity.require((cpp / "route.txt").read_bytes() == (native / "extension-route.txt").read_bytes() == route_bytes(), "different routes")
    rows = handoff.load(native / "extension.jsonl.gz")
    fidelity.require(len(rows) == FRAMES + 2 and rows[-1]["patches_restored"] is True, "incomplete extension")
    fidelity.require(not out.exists(), "comparison output already exists")
    out.mkdir()
    manifest_cpp = fidelity.load_manifest(cpp)
    checkpoints = {(row["tick"], row["phase"]): row for row in fidelity.trace_rows(cpp, manifest_cpp)
                   if row["kind"] == "checkpoint" and row["phase"] in ("present", "post_update")}
    atlas, previous, first, pixels_changed = rows[0]["atlas"], bytes(192000), None, 0
    observed = []
    for index, row in enumerate(rows[1:-1]):
        fidelity.require(row["sample"] == index and row["cpp_tick"] == FIRST_TICK + index, "extension alignment differs")
        rgb = original.decode_frame(row["rgb_delta_zlib_hex"], previous, row["rgb_sha256"])
        previous = rgb
        for name, phase, pi in (("rendered", "present", 1), ("post", "post_update", 2)):
            state = checkpoints[row["cpp_tick"], phase]["state"]
            expected = handoff.native_boundary(row[name], row["dac"][pi], atlas)
            actual = handoff.boundary(state, bytes.fromhex(state["palette_rgb_hex"]))
            diff = fidelity.first_difference(expected, actual)
            if first is None and diff:
                first = {"sample": index, "tick": row["cpp_tick"], "native_frame": row[name]["frame"], "phase": phase, **diff}
        state = checkpoints[row["cpp_tick"], "present"]
        pixels = fidelity.read_ppm(cpp / state["frame"])
        changed = sum(rgb[i:i+3] != pixels[i:i+3] for i in range(0, 192000, 3))
        pixels_changed += changed
        if first is None and changed:
            first = {"sample": index, "tick": row["cpp_tick"], "path": "$.rgb", "differing_pixels": changed}
        if index in (0, 40, 80, 120, FRAMES - 1) or (first is not None and first["sample"] == index):
            from PIL import Image
            for name, data in (("original", rgb), ("cpp", pixels)):
                Image.frombytes("RGB", (320, 200), data).save(out / f"{name}_{index:03d}.png")
        observed.append({"sample": index, "native_frame": row["post"]["frame"], "cpp_tick": row["cpp_tick"],
                         "native_xy": row["post"]["players"][0]["xy"], "native_actors": row["post"]["actor_count"],
                         "native_inventory": row["post"]["inventory"], "differing_pixels": changed})
    report = {"status": "match" if first is None and pixels_changed == 0 else "diverged", "frames": FRAMES,
              "states": FRAMES * 2, "pixels": FRAMES * 64000, "differing_pixels": pixels_changed,
              "first_difference": first, "samples": observed, "private_exploration": True,
              "all_dac_entries_compared": False, **CLAIMS}
    (out / "comparison.json").write_bytes(original.json_bytes(report))
    print(original.json_bytes({key: value for key, value in report.items() if key != "samples"}).decode("ascii"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "record", "compare"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--native", type=Path)
    parser.add_argument("--cpp", type=Path)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    if args.command == "capture":
        fidelity.require(args.approve_procmem and args.approve_runtime_instrumentation, "capture approvals required")
        capture(args.out.resolve())
    elif args.command == "record":
        record(args.exe, args.out.resolve())
    else:
        compare(args.native.resolve(), args.cpp.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
