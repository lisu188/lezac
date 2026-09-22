from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

import level1_fidelity as fidelity

ROOT = Path(__file__).resolve().parents[1]
EXE: Path | None = None
ARTIFACTS: Path | None = None


def write_json(path: Path, data) -> None:
    temporary = path.with_suffix(path.suffix + ".new")
    temporary.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_strict_route_parsing(self):
        valid = "LEZAC_LEVEL1_ROUTE_V1\nseed 0\nticks 2\nstep_us 40800\nevent 0 down 1\nevent 1 up 1\nend\n"
        path = self.root / "route.txt"
        for data in (valid, valid.replace("\n", "\r\n")):
            path.write_bytes(data.encode())
            settings, events = fidelity.read_route(path)
            self.assertEqual(settings, {"seed": 0, "ticks": 2, "step_us": 40800})
            self.assertEqual(events[0], [{"action": "down", "key": "1"}])
        invalid = [valid.replace("seed 0", "seed -1"), valid.replace("ticks 2", "ticks 0"),
                   valid.replace("ticks 2", "ticks 20001"), valid.replace("step_us 40800", "step_us 0"),
                   valid.replace("seed 0", "seed 4294967296"), valid.replace("seed 0", "seed 0\nseed 1"),
                   valid.replace("event 0 down 1", "event 0 up 1"), valid.replace("event 0 down 1", "event 0 repeat 1"),
                   valid.replace("event 1 up 1", "event 1 down 1"), valid.replace("event 1 up 1", "event 2 up 1"),
                   valid.replace("event 0 down 1", "event 0 down pageup"), valid.replace("end\n", ""),
                   valid + "event 0 down x\n", valid.replace("event 1 up 1", "event -1 up 1"),
                   valid.replace("event 0 down 1", "event 0 tap 1"), valid.replace("step_us 40800", "step_us 40.8")]
        for index, data in enumerate(invalid):
            with self.subTest(case=index):
                path.write_text(data, encoding="utf-8")
                with self.assertRaises((fidelity.EvidenceError, ValueError)):
                    fidelity.read_route(path)
                if EXE is not None:
                    output = self.root / f"invalid-{index}"
                    result = subprocess.run([str(EXE), "--replay-level1", str(path), str(output)], cwd=ROOT,
                        env=dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy"),
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists())

    def test_duplicate_json_and_nonfinite_numbers(self):
        for data in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                fidelity.strict_json(data)

    def test_fingerprint_and_first_difference(self):
        self.assertEqual(fidelity.fnv1a64(b""), "cbf29ce484222325")
        self.assertEqual(fidelity.fnv1a64(b"a"), "af63dc4c8601ec8c")
        self.assertEqual(fidelity.first_difference({"tiles_hex": "001122"}, {"tiles_hex": "00ff22"})["byte_offset"], 1)
        self.assertIsNotNone(fidelity.first_difference(True, 1))


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if EXE is None:
            raise unittest.SkipTest("--exe required for production integration")
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.assets_before = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
        cls.a, cls.b = cls.root / "a", cls.root / "b"
        route = ROOT / "tests/routes/level1_input_smoke.route"
        fidelity.record(EXE, ROOT, route, cls.a)
        fidelity.record(EXE, ROOT, route, cls.b)
        cls.rows = [json.loads(line) for line in (cls.a / "trace.jsonl").read_text().splitlines()]
        cls.post = {row["tick"]: row for row in cls.rows if row.get("phase") == "post_update"}

    @classmethod
    def tearDownClass(cls):
        if ARTIFACTS is not None:
            ARTIFACTS.mkdir(parents=True, exist_ok=False)
            shutil.copytree(cls.a, ARTIFACTS / "smoke")
            if (cls.root / "pixel-report").exists():
                shutil.copytree(cls.root / "pixel-report", ARTIFACTS / "pixel-mutation")
        cls.temp.cleanup()

    def clone(self, name: str) -> Path:
        path = self.root / name
        shutil.copytree(self.a, path, copy_function=os.link)
        return path

    def set_rows(self, bundle: Path, rows: list[dict], resign: bool = True) -> None:
        temporary = bundle / "trace.new"
        temporary.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        temporary.replace(bundle / "trace.jsonl")
        if resign:
            manifest = json.loads((bundle / "manifest.json").read_text())
            manifest["trace_sha256"] = fidelity.sha256(bundle / "trace.jsonl")
            write_json(bundle / "manifest.json", manifest)

    def test_independent_full_frame_determinism(self):
        report = fidelity.compare(self.a, self.b)
        self.assertEqual(report["status"], "match")
        self.assertEqual(report["frames"], 181)
        self.assertEqual(report["pixels"], 11584000)
        self.assertFalse(report["original_fidelity_claim"])

    def test_production_input_fire_pause_and_clock(self):
        self.assertEqual(self.post[6]["state"]["players"][0]["vx8"], 64)
        self.assertEqual(len(self.post[24]["state"]["bombs"]), 1)
        self.assertEqual(len(self.post[25]["state"]["bombs"]), 2)
        self.assertEqual(self.post[25]["state"]["players"][0]["inventory"][0], 198)
        self.assertEqual(self.post[51]["state"]["logic_tick"], self.post[54]["state"]["logic_tick"])
        self.assertGreater(self.post[55]["state"]["logic_tick"], self.post[54]["state"]["logic_tick"])
        self.assertEqual([self.post[t]["time_ms"] for t in (1, 2, 3, 4)], [0, 40, 81, 122])
        self.assertFalse(self.rows[-1]["level1_route_complete"])
        self.assertEqual(self.assets_before, {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS})

    def test_first_state_divergence(self):
        bundle = self.clone("motion-mutated")
        rows = copy.deepcopy(self.rows)
        row = next(row for row in rows if row.get("phase") == "post_update" and row["tick"] == 8)
        row["state"]["players"][0]["vx8"] += 1
        self.set_rows(bundle, rows)
        report = fidelity.compare(self.a, bundle)
        self.assertEqual(report["status"], "diverged")
        self.assertEqual(report["first_divergence"]["tick"], 8)
        self.assertEqual(report["first_divergence"]["phase"], "post_update")
        self.assertEqual(report["first_divergence"]["path"], "$.state.players[0].vx8")
        self.set_rows(bundle, rows[:-1])
        with self.assertRaises(fidelity.EvidenceError):
            fidelity.compare(self.a, bundle)

    def test_full_frame_pixel_divergence_and_images(self):
        bundle = self.clone("pixel-mutated")
        name = "frame_000010.ppm"
        data = bytearray((bundle / name).read_bytes())
        data[-1] ^= 1
        temporary = bundle / "frame.new"
        temporary.write_bytes(data)
        temporary.replace(bundle / name)
        rows = copy.deepcopy(self.rows)
        row = next(row for row in rows if row.get("frame") == name)
        row["rgb_fnv1a64"] = fidelity.fnv1a64(fidelity.read_ppm(bundle / name))
        self.set_rows(bundle, rows)
        manifest = json.loads((bundle / "manifest.json").read_text())
        manifest["frames"][name] = fidelity.sha256(bundle / name)
        write_json(bundle / "manifest.json", manifest)
        report = fidelity.compare(self.a, bundle, self.root / "pixel-report")
        self.assertEqual(report["first_divergence"]["tick"], 10)
        self.assertEqual(report["frame_differing_pixels"], 1)
        self.assertTrue((self.root / "pixel-report/difference.ppm").is_file())

    def test_optional_phase_divergence_is_not_parse_failure(self):
        bundle = self.clone("phase-diverged")
        rows = copy.deepcopy(self.rows)
        index = next(i for i, row in enumerate(rows) if row.get("phase") == "after_nonplayers")
        removed = rows.pop(index)
        sequence = 0
        for row in rows:
            if row["kind"] == "checkpoint":
                row["seq"] = sequence
                sequence += 1
        rows[-1]["checkpoints"] = sequence
        self.set_rows(bundle, rows)
        report = fidelity.compare(self.a, bundle)
        self.assertEqual(report["status"], "diverged")
        self.assertEqual(report["first_divergence"]["tick"], removed["tick"])

    def test_trace_guard_mutations(self):
        mutations = {
            "missing-footer": lambda rows: rows.pop(),
            "after-footer": lambda rows: rows.append(copy.deepcopy(rows[-1])),
            "duplicate-sequence": lambda rows: rows[2].update(seq=0),
            "incorrect-phase": lambda rows: rows[2].update(phase="present"),
            "clock-shift": lambda rows: rows[2].update(time_ms=1),
            "wrong-event": lambda rows: rows[2].update(events=[]),
            "crop-frame": lambda rows: rows[0].update(width=312),
            "pretend-original": lambda rows: rows[0].update(source="original"),
            "reference-phase": lambda rows: rows[0].update(phase_model="original-before-update"),
            "claim-parity": lambda rows: rows[0].update(original_fidelity_claim=True),
            "claim-level-complete": lambda rows: rows[-1].update(level1_route_complete=True),
            "claim-port-complete": lambda rows: rows[-1].update(port_functionally_complete=True),
            "unsafe-frame": lambda rows: rows[1].update(frame="../outside.ppm"),
            "bad-fraction": lambda rows: rows[1]["state"]["players"][0].update(frac_x=256),
            "short-map": lambda rows: rows[1]["state"].update(tiles_hex="00"),
        }
        for name, mutation in mutations.items():
            with self.subTest(case=name):
                bundle = self.clone(name)
                rows = copy.deepcopy(self.rows)
                mutation(rows)
                self.set_rows(bundle, rows)
                with self.assertRaises((fidelity.EvidenceError, ValueError, KeyError)):
                    list(fidelity.trace_rows(bundle, fidelity.load_manifest(bundle)))
                shutil.rmtree(bundle)

    def test_digest_and_missing_frame_guards(self):
        bundle = self.clone("bad-digest")
        rows = copy.deepcopy(self.rows)
        rows[0]["seed"] += 1
        self.set_rows(bundle, rows, resign=False)
        with self.assertRaises(fidelity.EvidenceError):
            fidelity.load_manifest(bundle)
        missing = self.clone("missing-frame")
        (missing / "frame_000000.ppm").unlink()
        with self.assertRaises(fidelity.EvidenceError):
            list(fidelity.trace_rows(missing, fidelity.load_manifest(missing)))
        with self.assertRaises(fidelity.EvidenceError):
            fidelity.record(EXE, ROOT, ROOT / "tests/routes/level1_input_smoke.route", self.a)

    def test_manifest_provenance_guards(self):
        mutations = {
            "missing-executable": lambda data: data.pop("executable_sha256"),
            "invalid-executable": lambda data: data.update(executable_sha256="unknown"),
            "untrusted-environment": lambda data: data["environment"].update(SDL_AUDIODRIVER="default"),
            "invalid-source": lambda data: data["source"].update(revision="current"),
            "claim-parity": lambda data: data.update(original_fidelity_claim=True),
            "unsafe-frame": lambda data: data["frames"].update({"../frame.ppm": "a"*64}),
        }
        for name, mutation in mutations.items():
            with self.subTest(case=name):
                bundle = self.clone("manifest-"+name)
                manifest = json.loads((bundle / "manifest.json").read_text())
                mutation(manifest)
                write_json(bundle / "manifest.json", manifest)
                with self.assertRaises(fidelity.EvidenceError):
                    fidelity.load_manifest(bundle)
                shutil.rmtree(bundle)

    def test_two_player_event_ownership_and_tap(self):
        route = self.root / "two-player.route"
        route.write_text("LEZAC_LEVEL1_ROUTE_V1\nseed 305441741\nticks 30\nstep_us 40800\n"
            "event 0 down 2\nevent 1 up 2\nevent 3 down return\nevent 4 up return\n"
            "event 5 down x\nevent 5 down left\nevent 8 down n\nevent 8 up n\n"
            "event 21 up x\nevent 21 up left\nend\n", encoding="utf-8")
        bundle = self.root / "two-player"
        fidelity.record(EXE, ROOT, route, bundle)
        rows = [json.loads(line) for line in (bundle / "trace.jsonl").read_text().splitlines()]
        post = {row["tick"]: row["state"] for row in rows if row.get("phase") == "post_update"}
        self.assertGreater(post[20]["players"][0]["x"], post[5]["players"][0]["x"])
        self.assertLess(post[20]["players"][1]["x"], post[5]["players"][1]["x"])
        self.assertEqual(post[20]["players"][0]["inventory"][0], 200)
        self.assertEqual(post[20]["bombs"], [])

    def test_original_motion_streams_through_event_adapter(self):
        keysets = {"idle": set(), "left": {"z"}, "right": {"x"}, "jump_right": {"m", "x"}, "both": {"z", "x"}}
        samples = 0
        fixtures = {
            "braking": "644ffbd8501ca7a3141e59bb274778fd1d7f7632b62f489ce899d00070516b25",
            "reversal": "58f565b7ab66d799dbadc26c29bc73b69c71fe4c0dfe245e9affae8b8ffbbc85",
            "reaccelerate": "053e02098fa388b990106ac3274046ba7f60ae3fe2556e8d1f61f5622755ee1b",
            "air_coast": "45ec41a96efc1f55bddc4f455fe6a582c0cd0a665fa9a0bdba79f29da94aaf51",
            "switch_coast": "c530c90bc05af578d7717b1d3ea6330b481fceb132f7d312483edd5e5d6a8fb7",
        }
        for name, expected_digest in fixtures.items():
            with self.subTest(route=name):
                fixture = ROOT / "tests/fixtures/player_walk_original" / f"{name}.txt"
                self.assertEqual(hashlib.sha256(fixture.read_bytes().replace(b"\r\n", b"\n")).hexdigest(), expected_digest)
                original = [dict(token.split("=", 1) for token in line.split()[1:])
                            for line in fixture.read_text().splitlines() if line.startswith("tick ")]
                lines = ["LEZAC_LEVEL1_ROUTE_V1", "seed 305441741", f"ticks {len(original)+5}", "step_us 40800",
                         "event 0 down 1", "event 1 up 1", "event 3 down return", "event 4 up return"]
                held = set()
                for index, row in enumerate(original):
                    desired = keysets[row["phase"]]
                    lines += [f"event {index+5} up {key}" for key in sorted(held-desired)]
                    lines += [f"event {index+5} down {key}" for key in sorted(desired-held)]
                    held = desired
                lines.append("end")
                route = self.root / f"{name}.route"
                route.write_text("\n".join(lines)+"\n", encoding="utf-8")
                bundle = self.root / f"original-motion-{name}"
                fidelity.record(EXE, ROOT, route, bundle)
                rows = [json.loads(line) for line in (bundle / "trace.jsonl").read_text().splitlines()]
                post = {row["tick"]: row["state"]["players"][0] for row in rows if row.get("phase") == "post_update"}
                for index, expected in enumerate(original):
                    raw = bytes.fromhex(expected["post"])
                    actual = post[index+6]
                    expected_motion = [struct.unpack_from("<h", raw, offset)[0] for offset in (14, 12, 46, 44)] + [raw[42], raw[41]]
                    actual_motion = [actual[key] for key in ("x", "y", "vx8", "vy8", "frac_x", "frac_y")]
                    self.assertEqual(actual_motion, expected_motion, f"{name}: original motion sample {index}")
                    samples += 1
                shutil.rmtree(bundle)
        self.assertEqual(samples, 445)


def main() -> int:
    global ROOT, EXE, ARTIFACTS
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    ROOT = args.root.resolve()
    EXE = args.exe.resolve() if args.exe else None
    ARTIFACTS = args.artifacts.resolve() if args.artifacts else None
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print(f"level1_replay_tests=ok tests={result.testsRun} integration={int(EXE is not None)} original_fidelity_claim=0")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
