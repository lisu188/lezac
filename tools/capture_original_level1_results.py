"""Capture the ordinary-input Level 1 prefix and native score-reel boundaries.

Run under a private Xvfb display with dummy audio. No gameplay state is seeded
other than the original oracle's controlled initial RNG/control-bank input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import level1_original as original
import level1_fidelity as fidelity

ENTRY, SIGNATURE, STAGE = 0x2000, "26807d2c02", 5
FROZEN = ("frame", "players", "inventory", "destruction", "actor_count",
          "actors", "visuals", "progress", "spawners", "tiles", "words")


def result_trampoline() -> bytes:
    code = bytearray.fromhex("9c6089e5")
    for i, operation in enumerate(("8b4614", "8cd8", "8cc0", "8cd0", "89e883c016", "8b4604")):
        code += bytes.fromhex(operation) + b"\x2e\xa3" + struct.pack("<H", original.SCRATCH + 2 + i * 2)
    code += b"\x2e\x66\xff\x06" + struct.pack("<H", original.SCRATCH + 16)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", original.SCRATCH, STAGE)
    code += b"\x2e\x83\x3e" + struct.pack("<H", original.SCRATCH + 14) + bytes([STAGE]) + b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", original.SCRATCH, 0)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", original.SCRATCH + 14, 0)
    code += bytes.fromhex("619d" + SIGNATURE + "cb")
    fidelity.require(len(code) < 0x80, "results trampoline overlaps scratch")
    return bytes(code)


class ResultsSession(original.OriginalSession):
    result_patched = False
    result_restored = False

    def capture(self, write_record):
        count = super().capture(write_record)
        baseline = self.state()
        fidelity.require(count == 305 and baseline["frame"] == 305, "known natural gate not reached")
        raw = bytes.fromhex(baseline["globals"])
        fidelity.require(raw[0x25:0x27] == b"\x01\x01" and original.word(bytes.fromhex(baseline["progress"]), 10) == 0,
                         "native completion gate not eligible")
        with self.stopped():
            fidelity.require(self.read(self.cs + ENTRY, 5).hex() == SIGNATURE, "results hook signature changed")
            at = original.TRAMPOLINES + 4 * 0x80
            trampoline = result_trampoline()
            fidelity.require(self.read(self.resident + at, len(trampoline)) == bytes(len(trampoline)), "extra trampoline occupied")
            for entry, signature in original.HOOKS:
                self.write(self.cs + entry, bytes.fromhex(signature))
            self.write(self.resident + at, trampoline)
            self.result_patched = True
            self.write(self.cs + ENTRY, original.far_call(at, self.resident_segment))
        self.release(4)
        previous = bytes(192000)
        samples, previous_rng = [], None
        with original.compressed_writer(self.output / "results.jsonl.gz") as emit:
            emit({"kind": "header", "schema": "lezac-natural-result-reels-v1",
                  "exe_sha256": original.EXE_SHA256, "base_observer_sha256": original.SOURCE_SHA256,
                  "observer_sha256": fidelity.sha256(Path(__file__)), "entry": ENTRY, "signature": SIGNATURE,
                  "route_sha256": fidelity.sha256(self.args.route), "baseline": baseline,
                  "atlas": original.word(self.read(self.ds + 0x2070, 2), 0),
                  "scope": "ordinary-input-prefix-then-native-reel-loop-boundaries",
                  "original_fidelity_claim": False, "level2_handoff_claim": False})
            for index in range(100):
                registers = self.wait(STAGE)
                player = original.word(self.read(self.base + (registers[3] << 4) + registers[5] - 4, 2), 0)
                fidelity.require(player == 1, "unexpected active results player")
                state = self.state()
                changed = [key for key in FROZEN if state[key] != baseline[key]]
                fidelity.require(not changed, "native results advanced gameplay: " + str(changed))
                scores = bytes.fromhex(state["scores"])
                score = struct.unpack_from("<I", scores)[0]
                phase = scores[44]
                current = list(struct.unpack_from("<9H", scores, 4))
                target = list(struct.unpack_from("<9H", scores, 24))
                if previous_rng is not None:
                    fidelity.require(state["rng"] == (previous_rng * 0x08088405 + 1) & 0xFFFFFFFF,
                                     "native loop did not make exactly one RNG draw")
                pixels = self.screenshot()
                emit({"kind": "sample", "sample": index, "player": player, "registers": registers,
                      "sequence": self.sequence, "state": state,
                      "rgb_delta_zlib_hex": original.encode_frame(pixels, previous),
                      "rgb_sha256": hashlib.sha256(pixels).hexdigest()})
                samples.append({"sample": index, "score": score, "phase": phase, "rng": state["rng"],
                                "current": current, "target": target})
                if index in (0, 1, 20) or phase == 2:
                    from PIL import Image
                    Image.frombytes("RGB", (320, 200), pixels).save(self.output / f"original_reels_{index:02d}.png")
                    print(f"native_reel_sample={index} score={score} phase={phase} rng={state['rng']}", flush=True)
                previous, previous_rng = pixels, state["rng"]
                if phase == 2:
                    break
                self.release(STAGE)
            else:
                raise fidelity.EvidenceError("native reels did not settle")
            emit({"kind": "complete", "samples": len(samples), "steps": len(samples) - 1,
                  "gameplay_frozen": True, "original_fidelity_claim": False})
        self.summary = {"status": "observed", "samples": samples, "steps": len(samples) - 1,
                        "initial_score": struct.unpack_from("<I", bytes.fromhex(baseline["scores"]))[0],
                        "final_score": score, "gameplay_frozen": True, "phase_alignment": "native-loop-boundary",
                        "typing_timing_claim": False, "level2_handoff_claim": False, "original_fidelity_claim": False}
        return count

    def close(self):
        try:
            if self.result_patched and self.child is not None and self.child.poll() is None:
                with self.stopped():
                    self.write(self.cs + ENTRY, bytes.fromhex(SIGNATURE))
                    self.result_restored = self.read(self.cs + ENTRY, 5).hex() == SIGNATURE
                    fidelity.require(self.result_restored, "results hook restoration failed")
        finally:
            super().close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    fidelity.require(args.approve_procmem and args.approve_runtime_instrumentation, "explicit capture approvals required")
    fidelity.require(sys.platform.startswith("linux") and os.environ.get("DISPLAY"), "private Linux display required")
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ.pop("SDL_VIDEODRIVER", None)
    args.route = ROOT / "tests/fixtures/level1_original/completion_gate/route.txt"
    args.startup_seconds, args.intro_seconds = 10, 3
    output = args.out.resolve()
    fidelity.require(output.parent == Path("/dev/shm") and not output.exists(), "new RAM output required")
    output.mkdir()
    shutil.copyfile(Path(__file__), output / "observer.py")
    image = original.check_executable(ROOT / "LEZAC.EXE")
    fidelity.require(image[ENTRY:ENTRY + 5].hex() == SIGNATURE, "native results loop signature changed")
    assets = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
    shutil.copyfile(args.route, output / "route.txt")
    session = None
    try:
        with tempfile.TemporaryDirectory(prefix="lezac-result-reels-") as temporary:
            run = Path(temporary)
            for path in ROOT.iterdir():
                if path.suffix.upper() in {".EXE", ".DAT", ".SPR", ".PAL", ".SCH", ".SON", ".MST", ".CAR", ".ZBG", ".DOC"}:
                    shutil.copyfile(path, run / path.name)
            session = ResultsSession(args, run, output)
            with original.compressed_writer(output / "reference.jsonl.gz") as emit:
                try:
                    count = session.capture(emit)
                finally:
                    session.close()
                fidelity.require(session.restored and session.result_restored, "all hooks were not restored")
                emit({"kind": "complete", "samples": count, "frames": count,
                      "patches_restored": True, "original_fidelity_claim": False})
        fidelity.require(assets == {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, "original assets changed")
        files = {name: fidelity.sha256(output / name) for name in
                 ("reference.jsonl.gz", "route.txt", "initial-ds.bin", "backdrop.bin", "dosbox.conf", "L1ORACLE.COM")}
        (output / "manifest.json").write_bytes(original.json_bytes({"schema": original.SCHEMA, "status": "captured",
            "assets": assets, "files": files, "original_fidelity_claim": False}))
        sum(1 for _ in original.reference_rows(output))
        (output / "results_summary.json").write_bytes(original.json_bytes(session.summary))
        print(json.dumps({key: value for key, value in session.summary.items() if key != "samples"}, sort_keys=True), flush=True)
    except BaseException as error:
        (output / "failure.json").write_bytes(original.json_bytes({"status": "incomplete", "error": str(error),
                                                                  "original_fidelity_claim": False}))
        raise


if __name__ == "__main__":
    main()
