#!/usr/bin/env python3
"""Observe original clock seeding and startup draws in an owned silent DOSBox.

A temporary executable waits at Randomize until its DOS-owned recorder is
installed. The original clock function is then called without replacing its
result. Phase gates pause the main routine; hardware interrupts keep running.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import time

import level1_original as oracle
import seed_original_level as seeder

ROOT = Path(__file__).resolve().parents[1]
CS = 0x01ED
RTL = CS + 0x0920
CLOCK_FILE = 0x2D21
CLOCK_IP = CLOCK_FILE - 0x770
RNG_IP = 0x13F7
RNG_FILE = 0xAD67
PHASES = ((0x77BD, "c606582030"), (0x77D2, "31c0a3c278"),
          (0x7A13, "803ee67900"), (0x7A57, "c606e87900"))
SCRATCH, CLOCK_RECORD, COUNTERS, DRAWS = 0x800, 0x840, 0x870, 0x900
DRAW_LIMIT, DRAW_STRIDE = 32, 12
MARKER = b"LEZAC-STARTUP-RNG-RECORDER-V1\0"
require = oracle.require


def clock_seed(cx, dx):
    return cx | (dx << 16)


def resident_program():
    image = bytearray(0x1000 - 0x100)
    code = bytes.fromhex("0e58a36001ba0001b80031cd21")
    image[:len(code)] = code
    image[0x20:0x20 + len(MARKER)] = MARKER
    return bytes(image)


def clock_stub(rtl=RTL):
    code = bytearray(oracle.far_call(0x142F, rtl))
    code += bytes.fromhex("9cfa6089e5")
    for i, operation in enumerate(("8b460c", "8b460a", "a1fe1a", "a1001b",
                                   "8cd8", "8cd0", "8b4612", "8b4614")):
        code += bytes.fromhex(operation) + b"\x2e\xa3" + struct.pack("<H", CLOCK_RECORD + i * 2)
    code += b"\x2e\xff\x06" + struct.pack("<H", COUNTERS)
    return bytes(code + bytes.fromhex("619dcb"))


def draw_stub(original):
    # Return past both complete displaced MOVs, even if restored in flight.
    code = bytearray.fromhex("5589e536c74602")
    code += struct.pack("<H", RNG_IP + len(original)) + bytes.fromhex("5d9cfa6089e5")
    code += b"\x2e\xa1" + struct.pack("<H", COUNTERS + 2)
    code += b"\x83\xf8" + bytes([DRAW_LIMIT])
    branch = len(code)
    code += b"\x73\x00"
    code += bytes.fromhex("066bf80c") + b"\x81\xc7" + struct.pack("<H", DRAWS)
    code += bytes.fromhex("0e07fc")
    for operation in ("a1fe1a", "a1001b", "8b4618", "8b461a", "8b461c", "8b4616"):
        code += bytes.fromhex(operation) + b"\xab"
    code += b"\x07"
    code[branch + 1] = len(code) - branch - 2
    code += b"\x2e\xff\x06" + struct.pack("<H", COUNTERS + 2)
    return bytes(code + bytes.fromhex("619d") + original + b"\xcb")


def phase_stub(stage, original):
    code = bytearray.fromhex("9c6089e5")
    for i, operation in enumerate(("8b4614", "8cd8", "8cc0", "8cd0", "89e883c016", "8b4604")):
        code += bytes.fromhex(operation) + b"\x2e\xa3" + struct.pack("<H", SCRATCH + 2 + i * 2)
    code += b"\x2e\x66\xff\x06" + struct.pack("<H", SCRATCH + 16)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, stage)
    code += b"\x2e\x83\x3e" + struct.pack("<H", SCRATCH + 14) + bytes([stage]) + b"\x75\xf8"
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH, 0)
    code += b"\x2e\xc7\x06" + struct.pack("<HH", SCRATCH + 14, 0)
    return bytes(code + bytes.fromhex("619d") + original + b"\xcb")


def executable():
    raw = (ROOT / "LEZAC.EXE").read_bytes()
    require(hashlib.sha256(raw).hexdigest() == oracle.EXE_SHA256, "unsupported original executable")
    require(raw[CLOCK_FILE:CLOCK_FILE + 5] == bytes.fromhex("9a2f142009"), "Randomize call changed")
    require(raw[0xAD9F:0xADAC] == bytes.fromhex("b42ccd21890efe1a8916001bcb"), "clock packing changed")
    require(raw[RNG_FILE:RNG_FILE + 7] == bytes.fromhex("a1fe1a8b1e001b"), "generator entry changed")
    for at, expected in PHASES:
        require(raw[0x770 + at:0x770 + at + 5].hex() == expected, "phase window changed")
    return raw


class Session:
    def __init__(self, output):
        self.output, self.run = output, output / "run"
        self.raw = executable()
        self.child = self.mem = None
        self.base = self.recorder = self.segment = 0
        self.code_segment = self.data_segment = self.rtl_segment = 0
        self.sequence = 0
        self.patches, self.restored = [], []

    def read(self, at, count):
        value = os.pread(self.mem.fileno(), count, at)
        require(len(value) == count, "short owned-child memory read")
        return value

    def write(self, at, value):
        require(os.pwrite(self.mem.fileno(), value, at) == len(value), "short owned-child memory write")

    @contextmanager
    def stopped(self):
        require(self.child.poll() is None, "owned DOSBox exited")
        os.kill(self.child.pid, signal.SIGSTOP)
        try:
            deadline = time.monotonic() + 3
            while "State:\tT" not in Path(f"/proc/{self.child.pid}/status").read_text():
                require(time.monotonic() < deadline, "owned DOSBox failed to stop")
                time.sleep(.001)
            yield
        finally:
            if self.child.poll() is None:
                os.kill(self.child.pid, signal.SIGCONT)

    def xdo(self, *args):
        return subprocess.check_output(["xdotool", *args], text=True, timeout=5).strip()

    def key(self, key):
        self.xdo("windowfocus", self.window)
        self.xdo("key", "--clearmodifiers", key)

    def wait(self, stage):
        deadline, values = time.monotonic() + 15, None
        while time.monotonic() < deadline:
            require(self.child.poll() is None, "owned DOSBox exited while waiting")
            values = struct.unpack("<8HI", self.read(self.recorder + SCRATCH, 20))
            if values[0] == stage and values[7] == 0 and values[8] == self.sequence + 1:
                require(values[1] == self.code_segment and values[2] == self.data_segment, "phase register identity changed")
                self.sequence = values[8]
                return values[1:7]
            time.sleep(.001)
        raise RuntimeError(f"phase {stage} timeout: {values}")

    def release(self, stage):
        self.write(self.recorder + SCRATCH + 14, struct.pack("<H", stage))

    def sample(self, name, registers=None):
        cx, dx, low, high, ds, ss, ip, cs = struct.unpack("<8H", self.read(self.recorder + CLOCK_RECORD, 16))
        clocks, draws = struct.unpack("<2H", self.read(self.recorder + COUNTERS, 4))
        seed = int.from_bytes(self.read(self.base + (ds << 4) + 0x1AFE, 4), "little")
        records = [list(struct.unpack("<6H", self.read(self.recorder + DRAWS + i * DRAW_STRIDE, DRAW_STRIDE)))
                   for i in range(min(draws, DRAW_LIMIT))]
        row = dict(phase=name, clock_calls=clocks, draws=draws, rng=seed,
                   clock_cx=cx, clock_dx=dx, initialized_rng=clock_seed(low, high),
                   clock_registers=dict(cs=cs, ds=ds, ss=ss, return_ip=ip),
                   phase_registers=list(registers or ()), first_draws=records)
        require(clocks == 1 and cs == self.code_segment and ds == self.data_segment and ip == CLOCK_IP + 5,
                "unexpected original clock boundary")
        require(clock_seed(cx, dx) == row["initialized_rng"], "clock bytes differ from initialized RNG")
        hour, minute, second, hundredth = cx >> 8, cx & 255, dx >> 8, dx & 255
        require(hour < 24 and minute < 60 and second < 60 and hundredth < 100, "invalid DOS clock bytes")
        expected = row["initialized_rng"]
        for i in range(draws):
            if i < len(records):
                require(clock_seed(records[i][0], records[i][1]) == expected, "first-draw seed chain differs")
                require(records[i][5] == 0x13AB, "unexpected RNG near caller")
            expected = (expected * 0x08088405 + 1) & 0xFFFFFFFF
        require(seed == expected, "unobserved RNG mutation or reseed")
        return row

    def screenshot(self, name):
        from PIL import Image, ImageGrab
        geometry = dict(x.split("=", 1) for x in self.xdo("getwindowgeometry", "--shell", self.window).splitlines())
        x, y, w, h = (int(geometry[k]) for k in ("X", "Y", "WIDTH", "HEIGHT"))
        require((w, h) == (320, 200), "original frame dimensions changed")
        time.sleep(.1)
        frame = ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).crop((x, y, x + w, y + h)).convert("RGB")
        require(len(set(frame.tobytes())) > 8, "blank original frame")
        frame.save(self.output / (name + ".png"))
        frame.resize((960, 600), Image.Resampling.NEAREST).save(self.output / (name + "-preview.png"))

    def launch(self, *, clock_only=False, resident_loader=None):
        if resident_loader is not None:
            name, payload = resident_loader
            require(Path(name).name == name and name != "RNGWATCH.COM" and name.endswith(".COM") and len(name) <= 12 and
                    all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_." for c in name) and
                    isinstance(payload, bytes) and 0 < len(payload) <= 65536,
                    "invalid additional resident loader")
        self.run.mkdir()
        for path in ROOT.iterdir():
            if path.suffix.upper() in {".EXE", ".DAT", ".SPR", ".PAL", ".SCH", ".SON", ".MST", ".CAR", ".ZBG", ".DOC"}:
                shutil.copyfile(path, self.run / path.name)
        gate = bytearray(self.raw)
        gate[CLOCK_FILE:CLOCK_FILE + 5] = bytes.fromhex("ebfe909090")
        (self.run / "LEZAC.EXE").write_bytes(gate)
        (self.run / "RNGWATCH.COM").write_bytes(resident_program())
        additional = []
        if resident_loader is not None:
            (self.run / name).write_bytes(payload)
            additional = ["-c", name]
        conf = self.output / "dosbox.conf"
        conf.write_text("[sdl]\nfullscreen=false\noutput=surface\n[render]\nframeskip=0\naspect=false\nscaler=none\n[cpu]\ncore=normal\ncycles=fixed 6000\n")
        self.log = (self.output / "dosbox.log").open("xb")
        self.child = subprocess.Popen(["dosbox", "-conf", str(conf), "-c", f"mount c {self.run}",
                                       "-c", "c:", "-c", "RNGWATCH.COM", *additional, "-c", "LEZAC.EXE"],
                                      env=dict(os.environ, SDL_AUDIODRIVER="dummy"), stdout=self.log, stderr=self.log)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            require(self.child.poll() is None, "owned DOSBox exited at startup")
            matches = seeder.scan_process(self.child.pid, seeder.DATA_SIGNATURE)
            residents = seeder.scan_process(self.child.pid, MARKER)
            if len(matches) == 1 and len(residents) == 1:
                break
            time.sleep(.05)
        require(len(matches) == len(residents) == 1, "ambiguous original/recorder memory")
        self.mem = open(f"/proc/{self.child.pid}/mem", "r+b", buffering=0)
        self.recorder = residents[0] - 0x120
        self.segment = int.from_bytes(self.read(self.recorder + 0x160, 2), "little")
        mcb = self.read(self.recorder - 16, 16)
        require(mcb[0] in (ord("M"), ord("Z")) and int.from_bytes(mcb[1:3], "little") == self.segment and
                int.from_bytes(mcb[3:5], "little") >= 0x100,
                "recorder is not a verified DOS allocation")
        self.base = self.recorder - (self.segment << 4)
        ds_address = matches[0] - seeder.DATA_STRING_OFFSET
        require((ds_address - self.base) % 16 == 0, "unaligned original data segment")
        self.data_segment = (ds_address - self.base) >> 4
        self.code_segment = self.data_segment - (seeder.RUNTIME_DS - CS)
        self.rtl_segment = self.code_segment + 0x920
        require(0 < self.segment < self.code_segment < self.data_segment < 0xA000 and
                self.code_segment >= self.segment + 0x100, "original overlaps resident allocation")
        expected_gate = bytes.fromhex("ebfe90") + struct.pack("<H", (0x9090 + self.code_segment) & 65535)
        require(self.read(self.base + (self.code_segment << 4) + CLOCK_IP, 5) == expected_gate, "startup gate/relocation changed")
        self.window = self.xdo("search", "--pid", str(self.child.pid), "--name", "DOSBox").splitlines()[-1]
        with self.stopped():
            require(self.read(self.recorder + 0x200, 0xE00) == bytes(0xE00), "recorder arena is occupied")
            hooks = [(self.code_segment, CLOCK_IP, self.raw[CLOCK_FILE:CLOCK_FILE + 3] + struct.pack("<H", self.rtl_segment), 0x200, clock_stub(self.rtl_segment), expected_gate)]
            if not clock_only:
                hooks += [(self.rtl_segment, RNG_IP, self.raw[RNG_FILE:RNG_FILE + 7], 0x300, draw_stub(self.raw[RNG_FILE:RNG_FILE + 7]), None)]
                hooks += [(self.code_segment, at, bytes.fromhex(raw), 0x300 + stage * 0x100, phase_stub(stage, bytes.fromhex(raw)), None)
                          for stage, (at, raw) in enumerate(PHASES, 1)]
            for seg, ip, original, target, code, expected in hooks:
                address = self.base + (seg << 4) + ip
                require(self.read(address, len(original)) == (expected or original), "runtime hook window changed")
                require(target + len(code) <= SCRATCH, "recorder code exceeds allocation")
                self.write(self.recorder + target, code)
                require(self.read(self.recorder + target, len(code)) == code, "stub write failed")
                self.patches.append((address, original))
                patch = oracle.far_call(target, self.segment) + bytes([0x90]) * (len(original) - 5)
                self.write(address, patch)
                require(self.read(address, len(patch)) == patch, "hook write failed")
        (self.run / "LEZAC.EXE").write_bytes(self.raw)
        return dict(resident_segment=self.segment, resident_mcb=mcb.hex(), code_segment=self.code_segment,
                    data_segment=self.data_segment,
                    temporary_gate_sha256=hashlib.sha256(gate).hexdigest(),
                    dosbox_sha256=hashlib.sha256(Path(f"/proc/{self.child.pid}/exe").read_bytes()).hexdigest())

    def restore(self, addresses=None):
        errors = []
        with self.stopped():
            for address, original in self.patches:
                if address in self.restored or (addresses is not None and address not in addresses):
                    continue
                try:
                    self.write(address, original)
                    require(self.read(address, len(original)) == original, "hook restoration failed")
                    self.restored.append(address)
                except Exception as error:
                    errors.append(str(error))
        require(not errors, "; ".join(errors))

    def close(self):
        try:
            if self.child is not None and self.child.poll() is None and self.mem is not None and self.patches:
                self.restore()
        finally:
            if self.child is not None and self.child.poll() is None:
                os.kill(self.child.pid, signal.SIGCONT)
                self.child.terminate()
                try:
                    self.child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.child.kill()
                    self.child.wait(timeout=3)
            if self.mem is not None:
                self.mem.close()
            if hasattr(self, "log"):
                self.log.close()


def capture(args):
    require(args.approve_procmem and args.approve_runtime_instrumentation, "capture approvals required")
    require(sys.platform.startswith("linux"), "startup capture requires Linux/WSL")
    if not args.private_xvfb:
        env = dict(os.environ, SDL_AUDIODRIVER="dummy", PYTHONDONTWRITEBYTECODE="1")
        env.pop("SDL_VIDEODRIVER", None)
        subprocess.run(["xvfb-run", "-a", sys.executable, "-B", str(Path(__file__).resolve()),
                        *sys.argv[1:], "--private-xvfb"], env=env, timeout=120, check=True)
        return
    require(os.environ.get("DISPLAY"), "missing private display")
    output = args.out.resolve()
    require(not output.exists() and output != ROOT and ROOT not in output.parents, "use a fresh output outside the checkout")
    output.mkdir(parents=True)
    session, samples = Session(output), []
    metadata = dict(schema="lezac_startup_rng_v1", exe_sha256=oracle.EXE_SHA256,
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    audio="dummy", gameplay_seeded=False, main_phase_gates=True, whole_game_parity=False)
    def persist(status, error=None):
        (output / "result.json").write_text(json.dumps(dict(metadata, status=status, samples=samples,
            restored_hooks=len(session.restored), error=error), indent=2) + "\n")
    try:
        metadata.update(session.launch())
        samples.append(session.sample("before_menu", session.wait(1)))
        persist("capturing")
        session.release(1)
        time.sleep(5)
        session.screenshot("menu")
        session.key("1")
        time.sleep(.5)
        session.key("1")
        samples.append(session.sample("before_intro", session.wait(2)))
        persist("capturing")
        session.release(2)
        time.sleep(4)
        session.screenshot("intro")
        session.key("Return")
        samples.append(session.sample("before_first_update", session.wait(3)))
        persist("capturing")
        session.release(3)
        samples.append(session.sample("first_present", session.wait(4)))
        persist("capturing")
        session.screenshot("first-present")
        d = session.base + (session.data_segment << 4)
        off, segment = struct.unpack("<HH", session.read(d + 0xC498, 4))
        (output / "backdrop.bin").write_bytes(session.read(session.base + (segment << 4) + off, 60000))
        session.restore({session.base + (session.code_segment << 4) + PHASES[i][0] for i in (2, 3)})
        session.release(4)
        session.key("Escape")
        time.sleep(5)
        session.key("Return")
        time.sleep(2)
        session.key("1")
        time.sleep(.5)
        session.key("1")
        samples.append(session.sample("second_game_before_intro", session.wait(2)))
        require(samples[0]["draws"] == samples[1]["draws"] == 0, "pre-game initialization consumed RNG")
        require(samples[2]["draws"] == 398, "unexpected intro/backdrop draw count")
        session.close()
        require(len(session.restored) == 6, "not all original hooks were restored")
        require(hashlib.sha256((ROOT / "LEZAC.EXE").read_bytes()).hexdigest() == oracle.EXE_SHA256, "shipped executable changed")
        persist("captured")
        print("startup_rng_capture=ok clock_calls=1 menu_draws=0 initialization_draws=398 games=2 hooks_restored=6 audio=dummy whole_game_parity=0")
    except BaseException as error:
        try:
            if session.mem is not None and session.child.poll() is None and session.sequence:
                try:
                    with session.stopped():
                        samples.append(session.sample("failed_boundary"))
                    session.screenshot("failed-boundary")
                except Exception as diagnostic_error:
                    metadata["failure_diagnostic_error"] = str(diagnostic_error)
        finally:
            try:
                session.close()
            finally:
                persist("failed", str(error))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    parser.add_argument("--private-xvfb", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_check:
        raw = executable()
        require(clock_seed(0x172B, 0x3B63) == 0x3B63172B, "clock packing self-check")
        require(len(clock_stub()) < 256 and len(draw_stub(raw[RNG_FILE:RNG_FILE + 7])) < 256, "oversized recorder")
        for i, (_, raw) in enumerate(PHASES, 1):
            require(len(phase_stub(i, bytes.fromhex(raw))) < 256, "oversized phase recorder")
        print("startup_rng_self_check=ok hooks=6 first_draws=32 resident_bytes=4096 live=0")
    else:
        require(args.out is not None, "--out is required")
        capture(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
