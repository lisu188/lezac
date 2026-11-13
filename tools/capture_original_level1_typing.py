"""Observe the natural Level 1 results typing at every draw-before-delay boundary."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import frame_compare
import level1_original as original
import level1_fidelity as fidelity

ENTRY, STAGE = 0x1611, 5
FROZEN = ("frame", "players", "inventory", "destruction", "actor_count",
          "actors", "visuals", "progress", "spawners", "tiles", "words", "scores", "rng")


def trampoline(native: bytes) -> bytes:
    code = bytearray.fromhex("9c6089e5")
    for i, operation in enumerate(("8b4614", "8cd8", "8cc0", "8cd0", "89e883c016", "8b4604")):
        code += bytes.fromhex(operation) + b"\x2e\xa3" + struct.pack("<H", original.SCRATCH + 2 + i * 2)
    code += b"\x2e\x66\xff\x06" + struct.pack("<H", original.SCRATCH + 16)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", original.SCRATCH, STAGE)
    code += b"\x2e\x83\x3e" + struct.pack("<H", original.SCRATCH + 14) + bytes([STAGE]) + b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", original.SCRATCH, 0)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", original.SCRATCH + 14, 0)
    # Replay the push and relocated far call together, preserving its argument.
    code += bytes.fromhex("619d") + native + b"\xcb"
    fidelity.require(len(code) < 0x80, "typing trampoline overlaps another slot")
    return bytes(code)


class TypingSession(original.OriginalSession):
    typing_patched = False
    typing_restored = False

    def capture(self, emit):
        count = super().capture(emit)
        baseline = self.state()
        fidelity.require(count == 305 and baseline["frame"] == 305, "natural prefix incomplete")
        with self.stopped():
            self.native = self.read(self.cs + ENTRY, 8)
            fidelity.require(self.native[:6].hex() == "ff76069a9c02", "typing boundary signature changed")
            runtime_cs = (self.cs - self.base) >> 4
            fidelity.require(original.word(self.native, 6) == runtime_cs + 0x084A, "delay relocation changed")
            at = original.TRAMPOLINES + 4 * 0x80
            code = trampoline(self.native)
            fidelity.require(self.read(self.resident + at, len(code)) == bytes(len(code)), "typing trampoline occupied")
            for entry, signature in original.HOOKS:
                self.write(self.cs + entry, bytes.fromhex(signature))
            self.write(self.resident + at, code)
            self.typing_patched = True
            self.write(self.cs + ENTRY, original.far_call(at, self.resident_segment) + b"\x90" * 3)
        self.release(4)
        previous, samples = bytes(192000), []
        with original.compressed_writer(self.output / "typing.jsonl.gz") as write:
            write({"kind": "header", "schema": "lezac-natural-result-typing-v1", "entry": ENTRY,
                   "exe_sha256": original.EXE_SHA256, "native_loaded_bytes": self.native.hex(),
                   "baseline": baseline, "atlas": original.word(self.read(self.ds + 0x2070, 2), 0),
                   "observer_sha256": fidelity.sha256(Path(__file__)), "base_observer_sha256": original.SOURCE_SHA256,
                   "route_sha256": fidelity.sha256(self.args.route), "original_fidelity_claim": False})
            for index in range(150):
                registers = self.wait(STAGE)
                stack, bp = self.base + (registers[3] << 4), registers[5]
                fidelity.require(bp >= 0x316, "typing stack local wraps")
                length = self.read(stack + bp - 0x100, 1)[0]
                text = self.read(stack + bp - 0xFF, length).decode("ascii")
                word = lambda offset: original.word(self.read(stack + bp + offset, 2), 0)
                byte = lambda offset: self.read(stack + bp + offset, 1)[0]
                character, limit, span = word(-0x10C), word(-0x114), word(-0x110)
                delay, y = word(6), word(0x16)
                fidelity.require(1 <= character <= limit <= length and delay == 81 and y in (60, 81, 99, 120),
                                 "unexpected typing boundary")
                state = self.state()
                fidelity.require(all(state[key] == baseline[key] for key in FROZEN), "typing advanced gameplay or RNG")
                pixels = self.screenshot()
                row = {"sample": index, "text": text, "character": character, "limit": limit,
                       "color_span": span, "delay_ms": delay, "y": y, "x": word(0x18),
                       "cell": byte(0x0A), "font_base": byte(8), "shadow_color": byte(0x0C),
                       "high_color": byte(0x0E), "low_color": byte(0x10)}
                write({"kind": "sample", **row, "sequence": self.sequence, "registers": registers,
                       "state": state, "rgb_delta_zlib_hex": original.encode_frame(pixels, previous),
                       "rgb_sha256": hashlib.sha256(pixels).hexdigest()})
                if character in (1, 6, limit):
                    frame_compare.write_ppm(self.output / f"original_y{y}_char{character}.ppm", (320, 200, bytearray(pixels)))
                    print(original.json_bytes(row).decode("ascii"), flush=True)
                samples.append(row)
                previous = pixels
                if y == 120 and character == limit:
                    break
                self.release(STAGE)
            else:
                raise fidelity.EvidenceError("typing observation did not finish")
            write({"kind": "complete", "samples": len(samples), "gameplay_frozen": True,
                   "typing_skip_claim": False, "level2_handoff_claim": False, "original_fidelity_claim": False})
        self.summary = {"status": "observed", "samples": samples, "boundary": "draw-before-delay",
                        "wall_clock_claim": False, "typing_skip_claim": False,
                        "level2_handoff_claim": False, "original_fidelity_claim": False}
        return count

    def close(self):
        try:
            if self.typing_patched and self.child is not None and self.child.poll() is None:
                with self.stopped():
                    self.write(self.cs + ENTRY, self.native)
                    self.typing_restored = self.read(self.cs + ENTRY, len(self.native)) == self.native
                    fidelity.require(self.typing_restored, "typing hook restoration failed")
        finally:
            super().close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    fidelity.require(args.approve_procmem and args.approve_runtime_instrumentation, "explicit capture approvals required")
    fidelity.require(os.environ.get("DISPLAY") and sys.platform.startswith("linux"), "private display required")
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ.pop("SDL_VIDEODRIVER", None)
    args.route = ROOT / "tests/fixtures/level1_original/completion_gate/route.txt"
    args.startup_seconds, args.intro_seconds = 10, 3
    out = args.out.resolve()
    fidelity.require(out.parent == Path("/dev/shm") and not out.exists(), "new RAM output required")
    out.mkdir()
    shutil.copyfile(Path(__file__), out / "observer.py")
    shutil.copyfile(args.route, out / "route.txt")
    assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
    try:
        with tempfile.TemporaryDirectory(prefix="lezac-typing-", dir="/dev/shm") as temporary:
            run = Path(temporary)
            for path in ROOT.iterdir():
                if path.suffix.upper() in {".EXE", ".DAT", ".SPR", ".PAL", ".SCH", ".SON", ".MST", ".CAR", ".ZBG", ".DOC"}:
                    shutil.copyfile(path, run / path.name)
            session = TypingSession(args, run, out)
            with original.compressed_writer(out / "reference.jsonl.gz") as emit:
                try:
                    count = session.capture(emit)
                finally:
                    session.close()
                fidelity.require(session.restored and session.typing_restored, "hooks not restored")
                emit({"kind": "complete", "samples": count, "frames": count,
                      "patches_restored": True, "original_fidelity_claim": False})
        fidelity.require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, "assets changed")
        files = {name: fidelity.sha256(out / name) for name in
                 ("reference.jsonl.gz", "route.txt", "initial-ds.bin", "backdrop.bin", "dosbox.conf", "L1ORACLE.COM")}
        (out / "manifest.json").write_bytes(original.json_bytes({"schema": original.SCHEMA, "status": "captured",
            "assets": assets, "files": files, "original_fidelity_claim": False}))
        fidelity.require(original.fingerprint(out) == original.fingerprint(ROOT / "tests/fixtures/level1_original/completion_gate"),
                         "typing observer changed gameplay prefix")
        (out / "typing_summary.json").write_bytes(original.json_bytes(session.summary))
        print(original.json_bytes({key: value for key, value in session.summary.items() if key != "samples"}).decode("ascii"), flush=True)
    except BaseException as error:
        (out / "failure.json").write_bytes(original.json_bytes({"status": "incomplete", "error": str(error),
                                                              "original_fidelity_claim": False}))
        raise


if __name__ == "__main__":
    main()
