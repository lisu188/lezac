"""Observe original menu pixels and arguments in an owned silent DOSBox.

Delay-call gates preserve the original clock, RNG and gameplay state. Captures
prove loop phases and pixels, not unmodified wall-clock timing.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import capture_original_startup_rng as startup

GATE_IP = 0x1611
CONTROL = 0x700
RECORD = 0x710
FADE_IP, FADE_CONTROL, FADE_RECORD = 0x480, 0x760, 0x770
require = startup.require


def source_hash(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def fade_zero_pixels():
    raw = (startup.ROOT / "SFONLEF.ZBG").read_bytes()
    end = 770 + int.from_bytes(raw[768:770], "little")
    require(end <= len(raw) and (end - 770) % 3 == 0, "title RLE header changed")
    indices = bytearray()
    for at in range(770, end, 3):
        count, first, second = raw[at:at + 3]
        indices.extend(bytes([first]) * ((count >> 4) + 1))
        indices.extend(bytes([second]) * ((count & 15) + 1))
    # The last nibble pair crosses the 64000-byte screen end by 15 bytes.
    require(len(indices) == 64015, "title RLE size changed")
    white = bytes((v << 2) | (v >> 4) for v in raw[30:33])
    return b"".join(white if index == 10 else b"\0\0\0" for index in indices[:64000])


def gate_stub(original):
    code = bytearray.fromhex("9c60")
    for i, offset in enumerate((0x06, 0x0a, 0x0c, 0x0e, 0x10, 0x16, 0x18, -0x10c, -0x10a)):
        code += bytes.fromhex("8b86") + struct.pack("<h", offset)
        code += bytes.fromhex("2ea3") + struct.pack("<H", RECORD + i * 2)
    code += bytes.fromhex("2eff06") + struct.pack("<H", CONTROL)
    code += bytes.fromhex("2ec706") + struct.pack("<HH", CONTROL + 2, 1)
    code += bytes.fromhex("2e833e") + struct.pack("<H", CONTROL + 2) + bytes.fromhex("0075f8")
    return bytes(code + bytes.fromhex("619d") + original + b"\xcb")


def fade_stub(original):
    code = bytearray.fromhex("9c608b866cf82ea3") + struct.pack("<H", FADE_RECORD)
    code += bytes.fromhex("2eff06") + struct.pack("<H", FADE_CONTROL)
    code += bytes.fromhex("2ec706") + struct.pack("<HH", FADE_CONTROL + 2, 1)
    code += bytes.fromhex("2e833e") + struct.pack("<H", FADE_CONTROL + 2) + bytes.fromhex("0075f8")
    return bytes(code + bytes.fromhex("619d") + original + b"\xcb")


class Session(startup.Session):
    def __init__(self, output):
        super().__init__(output)
        self.installed = False

    def screenshot(self, name):
        if not name.endswith("-fade0"):
            return super().screenshot(name)
        from PIL import Image, ImageGrab
        geometry = dict(x.split("=", 1) for x in self.xdo("getwindowgeometry", "--shell", self.window).splitlines())
        x, y, w, h = (int(geometry[k]) for k in ("X", "Y", "WIDTH", "HEIGHT"))
        require((w, h) == (320, 200), "original frame dimensions changed")
        time.sleep(.1)
        frame = ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).crop((x, y, x + w, y + h)).convert("RGB")
        expected = fade_zero_pixels()
        require(any(expected) and frame.tobytes() == expected, "fade-zero title pixels differ")
        frame.save(self.output / (name + ".png"))
        frame.resize((960, 600), Image.Resampling.NEAREST).save(self.output / (name + "-preview.png"))

    @contextmanager
    def stopped(self):
        with super().stopped():
            yield
            if self.patches and not self.installed:
                at = self.base + (self.code_segment << 4) + GATE_IP
                original = bytes.fromhex("ff76069a9c02") + struct.pack("<H", self.code_segment + 0x84a)
                require(self.read(at, 8) == original, "menu delay window changed")
                require(self.raw[0x770 + GATE_IP:0x770 + GATE_IP + 8] == bytes.fromhex("ff76069a9c024a08"), "static delay call changed")
                stub = gate_stub(original)
                require(0x400 + len(stub) < CONTROL, "menu stub overflow")
                self.write(self.recorder + 0x400, stub)
                self.patches.append((at, original))
                self.write(at, startup.oracle.far_call(0x400, self.segment) + b"\x90" * 3)
                fade_at = self.base + (self.code_segment << 4) + FADE_IP
                fade_original = bytes.fromhex("6a169a9c02") + struct.pack("<H", self.code_segment + 0x84a)
                require(self.read(fade_at, 7) == fade_original, "fade delay window changed")
                self.write(self.recorder + 0x600, fade_stub(fade_original))
                self.patches.append((fade_at, fade_original))
                self.write(fade_at, startup.oracle.far_call(0x600, self.segment) + b"\x90" * 2)
                self.installed = True

    def menu_step(self, sequence):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            require(self.child.poll() is None, "owned DOSBox exited")
            seq, pending = struct.unpack("<2H", self.read(self.recorder + CONTROL, 4))
            if seq == sequence and pending == 1:
                values = struct.unpack("<9H", self.read(self.recorder + RECORD, 18))
                return dict(zip(("delay_word", "cell", "shadow", "color_last", "color_first", "y", "x", "iteration", "window_x"), values))
            time.sleep(.001)
        raise RuntimeError(f"menu step {sequence} timeout: {seq}, {pending}")

    def release_step(self):
        self.write(self.recorder + CONTROL + 2, b"\x00\x00")

    def fade_step(self, sequence):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            require(self.child.poll() is None, "owned DOSBox exited")
            seq, pending = struct.unpack("<2H", self.read(self.recorder + FADE_CONTROL, 4))
            if seq == sequence and pending == 1:
                return int.from_bytes(self.read(self.recorder + FADE_RECORD, 2), "little")
            time.sleep(.001)
        raise RuntimeError(f"fade step {sequence} timeout: {seq}, {pending}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    raw = startup.executable()
    require(raw[0x770 + GATE_IP:0x770 + GATE_IP + 8] == bytes.fromhex("ff76069a9c024a08"), "static menu gate changed")
    require(raw[0x770 + FADE_IP:0x770 + FADE_IP + 7] == bytes.fromhex("6a169a9c024a08"), "static fade gate changed")
    require(0x400 + len(gate_stub(raw[0x770 + GATE_IP:0x770 + GATE_IP + 8])) < CONTROL, "menu stub overflow")
    require(0x600 + len(fade_stub(raw[0x770 + FADE_IP:0x770 + FADE_IP + 7])) < FADE_CONTROL, "fade stub overflow")
    require(any(fade_zero_pixels()), "fade-zero oracle blank")
    if args.self_check:
        print("main_menu_capture_self_check=ok windows=2 arena=4096 fade_zero=1 live=0")
        return
    if args.out is None:
        parser.error("--out is required")
    require(os.environ.get("SDL_AUDIODRIVER") == "dummy", "dummy audio required")
    output = args.out.resolve()
    require(not output.exists() and os.environ.get("DISPLAY"), "fresh output/private display required")
    output.mkdir(parents=True)
    session = Session(output)
    result = dict(status="capturing", audio="dummy", clock_forced=False, gameplay_seeded=False,
                  text_loop_gated=True, fade_loop_gated=True, natural_wall_clock_timing=False,
                  original_exe_sha256=hashlib.sha256(raw).hexdigest(),
                  background_sha256=hashlib.sha256((startup.ROOT / "SFONLEF.ZBG").read_bytes()).hexdigest(),
                  sources={str(path.relative_to(startup.ROOT)): source_hash(path) for path in
                           (Path(__file__).resolve(), Path(startup.__file__), Path(startup.oracle.__file__), Path(startup.seeder.__file__))},
                  samples=[], captures=[], menu_rng_samples=[], fade_samples=[])
    try:
        result.update(session.launch(clock_only=True))
        lengths = [25, 26, 16, 14, 16, 11, 15]
        sequence = fade_sequence = 0
        for language in ("italian", "english"):
            for factor in range(64):
                fade_sequence += 1
                observed = session.fade_step(fade_sequence)
                require(observed == factor, "fade factor order changed")
                result["fade_samples"].append(dict(language=language, sequence=fade_sequence, factor=observed))
                if factor in (0, 31, 63):
                    name = language + "-fade" + str(factor)
                    session.screenshot(name)
                    result["captures"].append(dict(name=name, fade_factor=factor,
                        sha256=hashlib.sha256((output / (name + ".png")).read_bytes()).hexdigest()))
                session.write(session.recorder + FADE_CONTROL + 2, b"\x00\x00")
            for line, length in enumerate(lengths):
                for iteration in range(1, length + 6):
                    sequence += 1
                    row = session.menu_step(sequence)
                    row.update(language=language, line=line, sequence=sequence)
                    require(row["iteration"] == iteration and row["y"] == 77 + 10 * line and
                            row["cell"] == 9 and row["color_first"] == 6 and row["color_last"] == 10,
                            f"unexpected menu arguments: {row}")
                    result["samples"].append(row)
                    if line == 0 and iteration in (1, 2, 6, length + 5):
                        name = f"{language}-line0-step{iteration:02d}"
                        session.screenshot(name)
                        result["captures"].append(dict(name=name, sequence=sequence,
                            sha256=hashlib.sha256((output / (name + ".png")).read_bytes()).hexdigest()))
                    session.release_step()
            time.sleep(.2)
            name = language + "-full"
            session.screenshot(name)
            result["captures"].append(dict(name=name, sequence=sequence,
                sha256=hashlib.sha256((output / (name + ".png")).read_bytes()).hexdigest()))
            sample = session.sample(name)
            require(sample["rng"] == sample["initialized_rng"], "menu consumed RNG")
            result["menu_rng_samples"].append(sample)
            if language == "italian":
                session.key("l")
                lengths = [28, 29, 9, 16, 16, 12, 10]
        result["status"] = "observed"
        print(json.dumps({k: v for k, v in result.items() if k not in ("samples", "captures")}), flush=True)
    except Exception as error:
        result.update(status="failed", error=str(error))
        raise
    finally:
        try:
            session.close()
        finally:
            result["hooks_restored"] = len(session.restored)
            result["child_exit_code"] = session.child.returncode if session.child else None
            (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
