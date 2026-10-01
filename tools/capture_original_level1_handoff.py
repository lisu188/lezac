"""Observe natural Level 1 results acknowledgment and twelve Level 2 frames."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import struct
import tempfile
import time

import frame_compare
import level1_fidelity as fidelity
import level1_original as original
import level1_results as results
import capture_original_level1_typing as typing

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "tests/fixtures/level1_original/completion_gate"
ENTRY, INTRO_ENTRY, STAGE, FRAMES, DAC = 0x2049, 0x2C72, 5, 12, 0x500


def palette_trampoline(code):
    # Read DAC through VGA ports while the enclosing trampoline saves all registers/flags.
    reader = bytes.fromhex("bac70330c0ee83c202b90003bf") + struct.pack("<H", DAC) + bytes.fromhex("ec2e880547e2f9")
    fidelity.require(code[:2] == bytes.fromhex("9c60"), "trampoline save prologue changed")
    code = code[:2] + reader + code[2:]
    fidelity.require(len(code) < 0x80, "palette trampoline overlaps its neighbour")
    return code


def intro_trampoline(native):
    code = typing.trampoline(native)
    for old, new in ((b"\x2e\xc7\x06" + struct.pack("<HH", original.SCRATCH, STAGE),
                      b"\x2e\xc7\x06" + struct.pack("<HH", original.SCRATCH, 6)),
                     (b"\x2e\x83\x3e" + struct.pack("<H", original.SCRATCH + 14) + bytes((STAGE,)),
                      b"\x2e\x83\x3e" + struct.pack("<H", original.SCRATCH + 14) + b"\x06")):
        fidelity.require(code.count(old) == 1, "intro handshake instruction changed")
        code = code.replace(old, new)
    return palette_trampoline(code)


class HandoffSession(original.OriginalSession):
    ack_patched = False
    ack_restored = False
    intro_patched = False
    intro_restored = False

    def dac(self):
        data = self.read(self.resident + DAC, 768)
        fidelity.require(all(value <= 63 for value in data), "native DAC is not six-bit RGB")
        return data.hex()

    def screenshot(self):
        for attempt in range(3):
            try:
                return super().screenshot()
            except fidelity.EvidenceError as error:
                if str(error) != "original frame did not stabilize at presentation hook" or attempt == 2:
                    raise
                time.sleep(.05)

    def dynamic_state(self):
        state = self.state()
        data = self.read(self.ds, 65536)
        width = original.word(data, 0xC204)
        height = original.word(data, 0x2096) // 8 + 21
        fidelity.require((width, height) == (100, 53), "unexpected native Level 2 dimensions")
        for key, pointer, size in (("tiles", 0xC1E0, width * height), ("words", 0x6612, width * height * 2)):
            offset, segment = struct.unpack_from("<HH", data, pointer)
            fidelity.require(0 < segment < 0xA000 and offset + size <= 65536, "invalid native map pointer")
            state[key] = self.read(self.base + (segment << 4) + offset, size).hex()
        return state

    def frame(self, name):
        pixels = self.screenshot()
        frame_compare.write_ppm(self.output / (name + ".ppm"), (320, 200, bytearray(pixels)))
        return pixels

    def capture(self, emit):
        count = super().capture(emit)
        fidelity.require(count == 305, "ordinary gameplay prefix incomplete")
        with self.stopped():
            self.native = self.read(self.cs + ENTRY, 5)
            runtime_cs = (self.cs - self.base) >> 4
            fidelity.require(self.native[:3].hex() == "9a0f03" and
                             original.word(self.native, 3) == runtime_cs + 0x084A, "ack ReadKey relocation changed")
            at = original.TRAMPOLINES + 4 * 0x80
            code = palette_trampoline(typing.trampoline(self.native))
            fidelity.require(self.read(self.resident + at, len(code)) == bytes(len(code)), "ack slot occupied")
            for entry, signature in original.HOOKS:
                self.write(self.cs + entry, bytes.fromhex(signature))
            self.write(self.resident + at, code)
            self.ack_patched = True
            self.write(self.cs + ENTRY, original.far_call(at, self.resident_segment))
        self.release(4)
        self.wait(STAGE)
        baseline = self.state()
        baseline_dac = self.dac()
        _, native_results = results.fixture()
        last = native_results[-1]["state"]
        fidelity.require(all(baseline[key] == last[key] for key in results.FROZEN + ("scores", "rng")),
                         "natural final results differ from pinned reels")
        self.frame("results-before-ack")
        with self.stopped():
            self.intro_native = self.read(self.cs + INTRO_ENTRY, 5)
            fidelity.require(self.intro_native == self.native, "intro ReadKey relocation changed")
            intro_at = original.TRAMPOLINES + 5 * 0x80
            code = intro_trampoline(self.intro_native)
            fidelity.require(self.read(self.resident + intro_at, len(code)) == bytes(len(code)), "intro slot occupied")
            self.write(self.resident + intro_at, code)
            self.intro_patched = True
            self.write(self.cs + INTRO_ENTRY, original.far_call(intro_at, self.resident_segment))
            for stage, (entry, _) in enumerate(original.HOOKS, 1):
                if stage != 1:
                    self.write(self.resident + original.TRAMPOLINES + (stage - 1) * 0x80,
                               palette_trampoline(original.trampoline(stage, self.image)))
                    self.write(self.cs + entry, original.far_call(original.TRAMPOLINES + (stage - 1) * 0x80,
                                                                self.resident_segment))
        bios = self.read(self.base + 0x400, 0x40)
        fidelity.require(original.word(bios, 0x1A) == original.word(bios, 0x1C), "ack queue was not empty")
        self.xdo("key", "--clearmodifiers", "Return")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            bios = self.read(self.base + 0x400, 0x40)
            head, tail = original.word(bios, 0x1A), original.word(bios, 0x1C)
            if head != tail:
                break
            time.sleep(.01)
        fidelity.require(0x1E <= head < 0x3E and 0x1E <= tail < 0x3E and head != tail and
                         original.word(bios, head) == 0x1C0D, "fresh Return did not enter the BIOS queue")
        queued = {"head": head, "tail": tail, "key_word": original.word(bios, head), "bda_hex": bios.hex()}
        self.release(STAGE)
        self.wait(6)
        intro = self.dynamic_state()
        data = self.read(self.ds, 65536)
        fidelity.require(data[0x79B7] == 2 and intro["frame"] == 305 and intro["rng"] == 2497022769,
                         "native acknowledgment did not reach the expected next intro")
        (self.output / "level2-intro-ds.bin").write_bytes(data)
        self.frame("level2-intro-wait")
        self.handoff_emit({"kind": "header", "schema": "lezac-natural-level1-handoff-v1",
                           "exe_sha256": original.EXE_SHA256,
                           "observer_sha256": fidelity.sha256(Path(__file__)),
                           "base_observer_sha256": original.SOURCE_SHA256,
                           "typing_observer_sha256": fidelity.sha256(ROOT / "tools/capture_original_level1_typing.py"),
                           "prefix_route_sha256": fidelity.sha256(PREFIX / "route.txt"),
                           "entry": ENTRY, "intro_entry": INTRO_ENTRY, "signature": "9a0f034a08", "ack": queued,
                           "baseline": baseline, "baseline_dac": baseline_dac, "intro": intro,
                           "intro_dac": self.dac(), "dimensions": [100, 53],
                           "atlas": original.word(data, 0x2070), "frames": FRAMES,
                           "manual_input_claim": False, "wall_clock_claim": False,
                           "all_actor_fields_compared": False, "original_fidelity_claim": False})
        self.xdo("key", "--clearmodifiers", "Return")
        self.release(6)
        previous = bytes(192000)
        for index in range(FRAMES):
            pre_registers = self.wait(2)
            pre, sequence = self.dynamic_state(), self.sequence
            pre_dac = self.dac()
            self.release(2)
            rendered_registers = self.wait(3)
            rendered = self.dynamic_state()
            rendered_dac = self.dac()
            pixels = self.frame(f"level2-{index:02d}")
            self.release(3)
            post_registers = self.wait(4)
            post = self.dynamic_state()
            post_dac = self.dac()
            self.handoff_emit({"kind": "sample", "sample": index,
                               "registers": [pre_registers, rendered_registers, post_registers],
                               "sequences": [sequence, sequence + 1, sequence + 2],
                               "pre": pre, "rendered": rendered, "post": post,
                               "dac": [pre_dac, rendered_dac, post_dac],
                               "rgb_delta_zlib_hex": original.encode_frame(pixels, previous),
                               "rgb_sha256": hashlib.sha256(pixels).hexdigest()})
            previous = pixels
            print(f"original_level2_sample={index + 1}/{FRAMES} frame={post['frame']} rng={post['rng']}", flush=True)
            if index + 1 != FRAMES:
                self.release(4)
        return count

    def close(self):
        try:
            if self.ack_patched and self.child is not None and self.child.poll() is None:
                with self.stopped():
                    self.write(self.cs + ENTRY, self.native)
                    self.ack_restored = self.read(self.cs + ENTRY, 5) == self.native
                    fidelity.require(self.ack_restored, "ack hook restoration failed")
                    if self.intro_patched:
                        self.write(self.cs + INTRO_ENTRY, self.intro_native)
                        self.intro_restored = self.read(self.cs + INTRO_ENTRY, 5) == self.intro_native
                        fidelity.require(self.intro_restored, "intro hook restoration failed")
        finally:
            super().close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    fidelity.require(args.approve_procmem and args.approve_runtime_instrumentation, "explicit capture approvals required")
    fidelity.require(os.environ.get("DISPLAY"), "private display required")
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ.pop("SDL_VIDEODRIVER", None)
    args.route, args.startup_seconds, args.intro_seconds = PREFIX / "route.txt", 10, 3
    out = args.out.resolve()
    fidelity.require(out.parent == Path("/dev/shm") and not out.exists(), "new RAM output required")
    out.mkdir()
    shutil.copyfile(Path(__file__), out / "observer.py")
    shutil.copyfile(args.route, out / "route.txt")
    assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
    try:
        with tempfile.TemporaryDirectory(prefix="lezac-handoff-", dir="/dev/shm") as temporary:
            run = Path(temporary)
            for path in ROOT.iterdir():
                if path.suffix.upper() in {".EXE", ".DAT", ".SPR", ".PAL", ".SCH", ".SON", ".MST", ".CAR", ".ZBG", ".DOC"}:
                    shutil.copyfile(path, run / path.name)
            session = HandoffSession(args, run, out)
            with original.compressed_writer(out / "reference.jsonl.gz") as emit, \
                    original.compressed_writer(out / "handoff.jsonl.gz") as handoff_emit:
                session.handoff_emit = handoff_emit
                try:
                    count = session.capture(emit)
                finally:
                    session.close()
                fidelity.require(session.restored and session.ack_restored and session.intro_restored, "hooks not restored")
                emit({"kind": "complete", "samples": count, "frames": count,
                      "patches_restored": True, "original_fidelity_claim": False})
                handoff_emit({"kind": "complete", "frames": FRAMES, "patches_restored": True,
                              "manual_input_claim": False, "wall_clock_claim": False,
                              "original_fidelity_claim": False})
        fidelity.require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, "assets changed")
        files = {name: fidelity.sha256(out / name) for name in
                 ("reference.jsonl.gz", "route.txt", "initial-ds.bin", "backdrop.bin", "dosbox.conf", "L1ORACLE.COM")}
        (out / "manifest.json").write_bytes(original.json_bytes({"schema": original.SCHEMA, "status": "captured",
            "assets": assets, "files": files, "original_fidelity_claim": False}))
        prefix_hash = original.fingerprint(out)
        fidelity.require(prefix_hash == original.fingerprint(PREFIX), "handoff capture changed the prefix")
        report = {"status": "captured", "frames": FRAMES, "prefix_canonical_sha256": prefix_hash,
                  "handoff_sha256": fidelity.sha256(out / "handoff.jsonl.gz"), "original_fidelity_claim": False}
        (out / "handoff-manifest.json").write_bytes(original.json_bytes(report))
        print(original.json_bytes(report).decode("ascii"), flush=True)
    except BaseException as error:
        (out / "failure.json").write_bytes(original.json_bytes({"status": "incomplete", "error": str(error),
                                                              "original_fidelity_claim": False}))
        raise


if __name__ == "__main__":
    main()
