from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import tempfile
import unittest
from unittest import mock

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
ISOLATED_PACKAGE = False
require = fidelity.require


def startup_environment(isolated, windows=None, inherited=None):
    env = dict(os.environ if inherited is None else inherited)
    env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    if isolated:
        for key in list(env):
            if key.casefold() in ("path", "ld_library_path", "ld_preload", "lezac_load_json_assets"):
                del env[key]
        is_windows = os.name == "nt" if windows is None else windows
        if is_windows:
            root = next((value for key, value in env.items() if key.casefold() == "systemroot"), "")
            require(PureWindowsPath(root).is_absolute(), "SystemRoot is required for isolated Windows validation")
            env["PATH"] = str(PureWindowsPath(root) / "System32") + ";" + root
        else:
            env["PATH"] = "/usr/bin:/bin"
    return env


def validate_package_assets(directory):
    originals = ("BOMOMIMK.SPR", "BOMPAL.PAL", "CARO.CAR", "FONTS.SPR", "GRAN.MST",
                 "LIVELS.SCH", "PROEFS.SON", "PROVA.SPR", "RECS.DAT", "SFONLEF.ZBG")
    checksums = {}
    for name in originals:
        for relative in (Path(name), Path("src") / (name + ".json")):
            installed = directory / relative.name
            require(installed.is_file(), "packaged asset missing: " + relative.name)
            actual, expected = installed.read_bytes(), (ROOT / relative).read_bytes()
            if relative.suffix == ".json":
                matches = fidelity.strict_json(actual.decode("utf-8")) == fidelity.strict_json(expected.decode("utf-8"))
            else:
                matches = actual == expected
            require(matches, "packaged asset changed: " + relative.name)
            checksums[relative.name] = dict(sha256=hashlib.sha256(actual).hexdigest(),
                source_sha256=hashlib.sha256(expected).hexdigest(),
                comparison="json-values" if relative.suffix == ".json" else "original-bytes")
    return checksums


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


def validate_intro_caption(pixels, original_pixels):
    require(len(pixels) == len(original_pixels) == 320 * 200 * 3, "intro pixel extent changed")
    original_colors = {original_pixels[index:index + 3] for index in range(0, len(original_pixels), 3)}
    foreground = max(original_colors, key=sum)
    expected = {index for index in range(0, len(original_pixels), 3)
                if original_pixels[index:index + 3] == foreground}
    actual = {index for index in range(0, len(pixels), 3) if pixels[index:index + 3] == foreground}
    # The caption is fixed; random intro colors can legitimately share channels.
    require(expected and actual == expected, "intro caption pixels differ from the original")


class StartupTests(unittest.TestCase):
    def test_low_palette_intro_retains_exact_original_caption(self):
        pinned()
        original_pixels = fidelity.read_ppm(FIXTURE / "intro.ppm")
        foreground = max({original_pixels[index:index + 3] for index in range(0, len(original_pixels), 3)}, key=sum)
        positions = [index for index in range(0, len(original_pixels), 3)
                     if original_pixels[index:index + 3] == foreground]
        low_palette = bytearray(bytes((8, 8, 16)) * (320 * 200))
        for index in positions:
            low_palette[index:index + 3] = foreground
        self.assertLessEqual(len(set(low_palette)), 8)
        validate_intro_caption(bytes(low_palette), original_pixels)
        missing = bytearray(low_palette)
        missing[positions[0]:positions[0] + 3] = bytes((8, 8, 16))
        extra = bytearray(low_palette)
        extra[:3] = foreground
        moved = bytearray(missing)
        moved[:3] = foreground
        for changed in (bytes(len(low_palette)), bytes(missing), bytes(extra), bytes(moved)):
            with self.assertRaises(fidelity.EvidenceError):
                validate_intro_caption(changed, original_pixels)

    def test_package_assets_reject_missing_or_changed_copies(self):
        with mock.patch.object(Path, "is_file", return_value=True), \
                mock.patch.object(Path, "read_bytes", side_effect=[b"raw", b"raw", b'{"asset":1}\r\n', b'{"asset":1}\n'] * 10):
            self.assertEqual(len(validate_package_assets(Path("package"))), 20)
        with mock.patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(fidelity.EvidenceError, "packaged asset missing"):
                validate_package_assets(Path("package"))
        with mock.patch.object(Path, "is_file", return_value=True), \
                mock.patch.object(Path, "read_bytes", side_effect=[b"changed", b"original"]):
            with self.assertRaisesRegex(fidelity.EvidenceError, "packaged asset changed"):
                validate_package_assets(Path("package"))
        with mock.patch.object(Path, "is_file", return_value=True), \
                mock.patch.object(Path, "read_bytes", side_effect=[b"raw", b"raw", b'{"asset":2}', b'{"asset":1}']):
            with self.assertRaisesRegex(fidelity.EvidenceError, "packaged asset changed"):
                validate_package_assets(Path("package"))

    def test_package_environment_cannot_inherit_compiler_paths_or_audio(self):
        inherited = dict(SystemRoot=r"C:\Windows", Path=r"C:\msys64\mingw64\bin", PATH="compiler-bin",
                         LD_LIBRARY_PATH="compiler-lib", LD_PRELOAD="compiler-preload", LEZAC_LOAD_JSON_ASSETS="1",
                         SDL_AUDIODRIVER="wasapi", SDL_VIDEODRIVER="windows")
        for windows in (False, True):
            env = startup_environment(True, windows, inherited)
            self.assertEqual(env["PATH"], r"C:\Windows\System32;C:\Windows" if windows else "/usr/bin:/bin")
            self.assertNotIn("Path", env)
            self.assertNotIn("LD_LIBRARY_PATH", env)
            self.assertNotIn("LD_PRELOAD", env)
            self.assertNotIn("LEZAC_LOAD_JSON_ASSETS", env)
            self.assertEqual(env["SDL_AUDIODRIVER"], "dummy")
            self.assertEqual(env["SDL_VIDEODRIVER"], "dummy")
        self.assertEqual(inherited["SDL_AUDIODRIVER"], "wasapi")
        self.assertEqual(startup_environment(False, False, inherited)["PATH"], "compiler-bin")
        with self.assertRaises(fidelity.EvidenceError):
            startup_environment(True, True, {})

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
        working_directory = EXE.parent if ISOLATED_PACKAGE else ROOT
        identity = dict(executable=str(EXE), executable_sha256=hashlib.sha256(EXE.read_bytes()).hexdigest(),
                        working_directory=str(working_directory), isolated_package=ISOLATED_PACKAGE)
        try:
            first = original["samples"][0]
            env = startup_environment(ISOLATED_PACKAGE)
            package_assets = {}
            if ISOLATED_PACKAGE:
                package_assets = validate_package_assets(EXE.parent)
                run = subprocess.run([str(EXE), "--validate"], cwd=working_directory,
                                     env=env, text=True, capture_output=True, timeout=30)
                (root / "package-validate.log").write_text(run.stdout + run.stderr)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn("level_7=140x52 objective_tile=106 required_bonus=1 destruction=10 spawners=0 portals=2 triggers=1",
                              run.stdout)
            artifacts = []
            for name, clocks in (("original-clock", [str(first["clock_cx"]), str(first["clock_dx"])]), ("natural-clock", [])):
                output = root / name
                run = subprocess.run([str(EXE), "--debug-startup-rng", str(output), *clocks], cwd=working_directory,
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
                    if frame == "intro.ppm":
                        validate_intro_caption(pixels, fidelity.read_ppm(FIXTURE / frame))
                    else:
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
                natural_clock_checked=True, whole_game_parity=False, runs=artifacts,
                **identity,
                child_path=env.get("PATH", ""), audio=env["SDL_AUDIODRIVER"], package_assets=package_assets), indent=2) + "\n")
            print(f"startup_rng_original=ok menu_draws=0 intro_draws=8 initialization_draws=398 compared_pixels=128000 backdrop_bytes=60000 natural_clock=1 whole_game_parity=0 out={root}")
            if ISOLATED_PACKAGE:
                print(f"isolated_package=ok resources={len(package_assets)} validate=1 compared_pixels=128000 audio=dummy whole_game_parity=0 out={root}")
        except BaseException as error:
            (root / "failure.json").write_text(json.dumps(dict(status="failed", error=str(error),
                whole_game_parity=False, **identity), indent=2) + "\n")
            print(f"startup_rng_original=failed out={root}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--isolated-package", action="store_true")
    args = parser.parse_args()
    if args.isolated_package and not args.exe:
        parser.error("--isolated-package requires --exe")
    ISOLATED_PACKAGE = args.isolated_package
    EXE = args.exe.resolve() if args.exe else None
    OUT = args.out.resolve() if args.out else None
    if OUT:
        OUT.mkdir(parents=True, exist_ok=True)
    unittest.main(argv=[__file__])
