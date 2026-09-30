from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import capture_original_startup_rng as capture
import level1_fidelity as fidelity

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/startup_rng_original"
PINS = {
    "result.json": "286abe8191be48afda1f6fa2ac450384f45c3720c596092e69ae444255cd57f6",
    "backdrop.bin": "efc595da5bcbf13d96885862905f9808cf49028891ee6b54ef2d2dd7a44b1a05",
    "intro.ppm": "9f17e6418b55e780eba1ee5b16402b1b0d1866cc483c687232bb01655b917a8a",
    "first-present.ppm": "1b22e0f69e66b1c04de30587aee2a7a0e92a038b983222c2d8c11e8db8dcce3e",
}
EXE = OUT = None
require = fidelity.require


def advance(seed, draws):
    for _ in range(draws):
        seed = (seed * 0x08088405 + 1) & 0xFFFFFFFF
    return seed


def validate(result):
    require(result["schema"] == "lezac_startup_rng_v1" and result["status"] == "captured", "incomplete capture")
    require(result["exe_sha256"] == capture.oracle.EXE_SHA256 and
            result["source_sha256"] == "ff8a885bf42b8fbb0734b8fb0748d6b34817da831a4fb219cb63f7e24cf848b4", "capture identity changed")
    require(result["audio"] == "dummy" and result["gameplay_seeded"] is False and
            result["main_phase_gates"] is True and result["whole_game_parity"] is False and
            result["restored_hooks"] == 6 and result["error"] is None, "invalid capture evidence claims")
    cs, ds = result["code_segment"], result["data_segment"]
    require(ds - cs == 0xAA2 and cs >= result["resident_segment"] + 0x100, "segment ownership changed")
    mcb = bytes.fromhex(result["resident_mcb"])
    require(len(mcb) == 16 and mcb[0] in (77, 90) and int.from_bytes(mcb[1:3], "little") == result["resident_segment"] and
            int.from_bytes(mcb[3:5], "little") >= 0x100, "unowned resident allocation")
    require([(row["phase"], row["draws"]) for row in result["samples"]] ==
            [("before_menu", 0), ("before_intro", 0), ("before_first_update", 398),
             ("first_present", 398), ("second_game_before_intro", 406)], "startup draw boundary changed")
    seed = result["samples"][0]["initialized_rng"]
    for row in result["samples"]:
        cx, dx = row["clock_cx"], row["clock_dx"]
        require(0 <= cx <= 65535 and 0 <= dx <= 65535 and cx >> 8 < 24 and cx & 255 < 60 and
                dx >> 8 < 60 and dx & 255 < 100, "invalid clock fields")
        require(row["clock_calls"] == 1 and row["initialized_rng"] == seed == capture.clock_seed(cx, dx), "clock reseeded or packing changed")
        regs = row["clock_registers"]
        require(regs["cs"] == cs and regs["ds"] == ds and regs["return_ip"] == 0x25B6 and
                row["phase_registers"][:2] == [cs, ds], "clock/caller boundary changed")
        require(row["rng"] == advance(seed, row["draws"]), "RNG continuation changed")
        require(len(row["first_draws"]) == min(row["draws"], 32), "missing bounded draw records")
        for i, (low, high, ip, caller_cs, span, near_ip) in enumerate(row["first_draws"]):
            require(capture.clock_seed(low, high) == advance(seed, i) and caller_cs == cs and near_ip == 0x13AB,
                    "RNG caller or seed chain changed")
            if i < 8:
                require(span == (80, 80, 20, 20, 20, 30, 30, 30)[i] and
                        ip == (0x234, 0x23F, 0x14E, 0x158, 0x162, 0x16C, 0x176, 0x180)[i], "intro draw order changed")
            else:
                require(ip in (0x7806, 0x7810, 0x7826, 0x78BA, 0x78DC) and span > 0, "backdrop draw caller changed")
    return result


def pinned():
    for name, checksum in PINS.items():
        require(hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == checksum, "original fixture changed: " + name)
    require(len((FIXTURE / "backdrop.bin").read_bytes()) == 60000, "truncated backdrop")
    for name in ("intro.ppm", "first-present.ppm"):
        fidelity.read_ppm(FIXTURE / name)
    return validate(fidelity.strict_json((FIXTURE / "result.json").read_text()))


class StartupTests(unittest.TestCase):
    def test_pinned_original(self):
        pinned()

    def test_clock_pack_all_valid_components(self):
        for hour in range(24):
            for minute in range(60):
                self.assertEqual(capture.clock_seed((hour << 8) | minute, 0), (hour << 8) | minute)
        for second in range(60):
            for hundredth in range(100):
                self.assertEqual(capture.clock_seed(0, (second << 8) | hundredth), (second << 24) | (hundredth << 16))

    def test_recorder_layout_and_displaced_instructions(self):
        raw = capture.executable()
        self.assertEqual(len(capture.resident_program()), 3840)
        self.assertIn(capture.MARKER, capture.resident_program())
        self.assertEqual(capture.clock_stub(0xBC0)[:5], capture.oracle.far_call(0x142F, 0xBC0))
        code = capture.draw_stub(raw[capture.RNG_FILE:capture.RNG_FILE + 7])
        self.assertTrue(code.startswith(bytes.fromhex("5589e536c74602fe135d")))
        self.assertTrue(code.endswith(bytes.fromhex("a1fe1a8b1e001bcb")))
        for stage, (_, expected) in enumerate(capture.PHASES, 1):
            self.assertTrue(capture.phase_stub(stage, bytes.fromhex(expected)).endswith(bytes.fromhex(expected) + b"\xcb"))

    def test_mutations_rejected_without_resigning(self):
        original = pinned()
        mutations = [("status", "failed"), ("audio", "pulseaudio"), ("gameplay_seeded", True),
                     ("whole_game_parity", True), ("restored_hooks", 5), ("source_sha256", "0" * 64)]
        for field, value in mutations:
            altered = copy.deepcopy(original)
            altered[field] = value
            with self.subTest(field=field), self.assertRaises(fidelity.EvidenceError):
                validate(altered)
        for row_index in range(5):
            for field in ("clock_cx", "clock_dx", "initialized_rng", "rng", "draws", "clock_calls"):
                altered = copy.deepcopy(original)
                altered["samples"][row_index][field] ^= 1
                with self.subTest(row=row_index, field=field), self.assertRaises(fidelity.EvidenceError):
                    validate(altered)
        for draw in range(32):
            altered = copy.deepcopy(original)
            altered["samples"][2]["first_draws"][draw][0] ^= 1
            with self.subTest(draw=draw), self.assertRaises(fidelity.EvidenceError):
                validate(altered)

    def test_restoration_continues_after_one_failure(self):
        class FakeSession(capture.Session):
            @contextmanager
            def stopped(self):
                yield
            def write(self, address, value):
                if address == 1:
                    raise OSError("injected partial-write failure")
                self.memory[address] = value
            def read(self, address, count):
                return self.memory[address]
        session = FakeSession.__new__(FakeSession)
        session.patches, session.restored, session.memory = [(1, b"first"), (2, b"second")], [], {}
        with self.assertRaises(fidelity.EvidenceError):
            session.restore()
        self.assertEqual(session.restored, [2])
        self.assertEqual(session.memory[2], b"second")

    def test_production_startup_boundary_and_original_pixels(self):
        if EXE is None:
            self.skipTest("no compiled C++ executable supplied")
        original = pinned()
        root = Path(tempfile.mkdtemp(prefix="lezac-startup-rng-", dir=OUT))
        try:
            first = original["samples"][0]
            env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
            artifacts = []
            for name, clocks in (("original-clock", [str(first["clock_cx"]), str(first["clock_dx"])]), ("natural-clock", [])):
                output = root / name
                run = subprocess.run([str(EXE), "--debug-startup-rng", str(output), *clocks], cwd=ROOT,
                                     env=env, text=True, capture_output=True, timeout=30)
                (root / (name + ".log")).write_text(run.stdout + run.stderr)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                rows = [line for line in run.stdout.splitlines() if line.startswith("startup_rng=ok ")]
                self.assertEqual(len(rows), 1, run.stdout + run.stderr)
                fields = dict(token.split("=", 1) for token in rows[0].split()[1:])
                seed = int(fields["initial_seed"])
                self.assertEqual(fields["natural_clock"], "0" if clocks else "1")
                self.assertEqual(fields["clock_calls"], "1")
                self.assertEqual(int(fields["menu_seed"]), seed)
                self.assertEqual(int(fields["intro_seed"]), advance(seed, 8))
                self.assertEqual(int(fields["gameplay_seed"]), advance(seed, 398))
                self.assertEqual(int(fields["first_present_seed"]), advance(seed, 398))
                self.assertEqual(fields["whole_game_parity"], "0")
                self.assertEqual(fields["frame_inspection"], "1")
                self.assertLess(seed & 255, 60)
                self.assertLess((seed >> 8) & 255, 24)
                self.assertLess((seed >> 16) & 255, 100)
                self.assertLess(seed >> 24, 60)
                for frame in ("menu.ppm", "intro.ppm", "first-present.ppm"):
                    pixels = fidelity.read_ppm(output / frame)
                    self.assertGreater(len(set(pixels)), 8)
                if clocks:
                    self.assertEqual(seed, first["initialized_rng"])
                    self.assertEqual((output / "backdrop.bin").read_bytes(), (FIXTURE / "backdrop.bin").read_bytes())
                    for frame in ("intro.ppm", "first-present.ppm"):
                        actual, expected = fidelity.read_ppm(output / frame), fidelity.read_ppm(FIXTURE / frame)
                        differing = sum(actual[i:i + 3] != expected[i:i + 3] for i in range(0, len(actual), 3))
                        self.assertEqual(differing, 0, f"{frame}: differing_pixels={differing}")
                artifacts.append(dict(mode=name, summary=fields, stdout=run.stdout, stderr=run.stderr))
            (root / "comparison.json").write_text(json.dumps(dict(status="match", intro_pixels=64000,
                first_present_pixels=64000, backdrop_bytes=60000, controlled_original_clock=True,
                natural_clock_checked=True, whole_game_parity=False, runs=artifacts), indent=2) + "\n")
            print(f"startup_rng_original=ok menu_draws=0 intro_draws=8 initialization_draws=398 compared_pixels=128000 backdrop_bytes=60000 natural_clock=1 whole_game_parity=0 out={root}")
        except BaseException as error:
            (root / "failure.json").write_text(json.dumps(dict(status="failed", error=str(error),
                whole_game_parity=False), indent=2) + "\n")
            print(f"startup_rng_original=failed out={root}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    EXE = args.exe.resolve() if args.exe else None
    OUT = args.out.resolve() if args.out else None
    if OUT:
        OUT.mkdir(parents=True, exist_ok=True)
    unittest.main(argv=[__file__])
