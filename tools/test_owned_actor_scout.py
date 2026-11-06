"""Exercise the actual App's owned-storage scout without the legacy seed adapter."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

import level1_fidelity as fidelity
import level1_original as original

ROOT = Path(__file__).resolve().parents[1]
EXE: Path | None = None
OUTPUT: Path | None = None


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


class OwnedScoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=OUTPUT)
        cls.root = Path(cls.temp.name)
        cls.route = ROOT / "tests/routes/level1_input_smoke.route"
        cls.assets = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in ROOT.iterdir() if path.is_file() and path.suffix in
                      (".EXE", ".DAT", ".SPR", ".PAL", ".SCH", ".SON", ".MST", ".CAR", ".ZBG")}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def replay(self, name, start, flags=(), command="--replay-level1-owned-scout", route=None):
        out = self.root / name
        result = subprocess.run([str(EXE), command, str(route or self.route), str(out), str(start), *flags],
            cwd=ROOT, env=dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy",
                LEZAC_LOAD_JSON_ASSETS="0", LEZAC_LOAD_ORIGINAL_ASSETS="1"),
            capture_output=True, text=True, timeout=60)
        return out, result

    def test_original_two_player_fire_stress_window(self):
        self.check_original_window("two_player_fire_stress", 4, 604,
            "3f286b06b12670110a167ceeafc08dea356e68bf3bbbfe23fdc6fafcf3500352")

    def test_original_two_player_reentry_window(self):
        self.check_original_window("two_player_reentry", 604, 1204,
            "e2d5562294d6d131d452a601df8a802b3fe8cf926292e6087a1c8a4db84bcca9")

    def test_original_two_player_second_reentry_window(self):
        points = self.check_original_window("two_player_second_reentry", 1204, 1804,
            "db209007ec54a3f442c127795cc3290e2d286d7783dfdc20b6202956534fbcfe")
        def players(tick):
            return points[tick, "post_update"][0]["state"]["players"]
        self.assertEqual(players(1253)[1]["health"][:3], [100, 1, 1])
        self.assertEqual(players(1301)[1]["health"][:3], [100, 1, 0])
        for tick, player, selection in ((1311, 1, 0), (1321, 0, 2)):
            self.assertEqual(players(tick)[player]["inventory"][selection],
                             players(tick - 1)[player]["inventory"][selection] - 1)
        # Original 6CA9/6CAE consumes BOTH banks after P1's constructor attempt.
        for tick in (1441, 1541):
            self.assertEqual(players(tick)[0]["inventory"][2], players(tick - 1)[0]["inventory"][2] - 1)
            self.assertEqual(players(tick)[1]["inventory"], players(tick - 1)[1]["inventory"])
            self.assertEqual([player["waiting"][3] for player in players(tick)], [0, 0])

    def check_original_window(self, name, first, last, fixture_sha256):
        fixture = ROOT / f"tests/fixtures/{name}_original.json"
        raw_fixture = fixture.read_bytes()
        self.assertEqual(hashlib.sha256(raw_fixture).hexdigest(), fixture_sha256)
        oracle = json.loads(raw_fixture)
        self.assertEqual(oracle["schema"], "lezac.two-player-original-window.v1")
        self.assertEqual([oracle[key] for key in ("first", "last", "frames", "boundaries", "backing_bytes")],
                         [first, last, 601, 1202, 1612])
        for asset_name, digest in oracle["assets"].items():
            self.assertEqual(hashlib.sha256((ROOT / asset_name).read_bytes()).hexdigest(), digest, asset_name)
        route = ROOT / f"tests/routes/{name}.route"
        self.assertEqual(hashlib.sha256(route.read_bytes()).hexdigest(), oracle["route_sha256"])
        out, result = self.replay("original-" + name, first,
            ("--original-intro-wait", "--result-reels"), route=route)
        self.assertEqual(result.returncode, 0, result.stderr)
        main, backing = rows(out / "trace.jsonl"), rows(out / "actor_storage.jsonl")
        self.assertEqual(len(main), 2406)
        self.assertEqual(len(backing), len(main))
        for header in (main[0], backing[0]):
            self.assertEqual(header["actor_storage_mode"], "production-owned")
            self.assertIs(header["legacy_actor_seed_adapter"], False)
            self.assertIs(header["candidate_only"], True)
            self.assertIs(header["original_fidelity_claim"], False)
        self.assertEqual(backing[0]["separate_player1_layout"], [1, 38])
        checkpoints = {}
        for normal, stored in zip(main[1:-1], backing[1:-1]):
            self.assertEqual([normal[key] for key in ("seq", "tick", "phase")],
                             [stored[key] for key in ("seq", "tick", "phase")])
            key = normal["tick"], normal["phase"]
            self.assertNotIn(key, checkpoints)
            checkpoints[key] = normal, stored
        self.assertEqual(len(checkpoints), 2404)
        self.assertEqual(len(oracle["samples"]), 601)
        for tick, expected in enumerate(oracle["samples"], first):
            self.assertEqual(expected["tick"], tick)
            for phase in ("present", "post_update"):
                normal, stored = checkpoints[tick, phase]
                payload = b""
                for field, size in (("player1", 38), ("actors", 1178), ("visuals", 264), ("links", 128)):
                    part = bytes.fromhex(stored[field + "_hex"])
                    self.assertEqual(len(part), size)
                    payload += part
                payload += bytes((stored["count"], stored["visual_count"])) + struct.pack("<H", stored["success"])
                self.assertEqual(len(payload), 1612)
                self.assertEqual(hashlib.sha256(payload).hexdigest(), expected[phase]["backing_sha256"],
                                 f"physical backing at {tick}:{phase}")
                projection = original.json_bytes(original.project_cpp(normal["state"], 2))
                self.assertEqual(hashlib.sha256(projection).hexdigest(), expected[phase]["projection_sha256"],
                                 f"typed projection at {tick}:{phase}")
                if phase == "present":
                    pixels = fidelity.read_ppm(out / f"frame_{tick:06d}.ppm")
                    self.assertEqual(hashlib.sha256(pixels).hexdigest(), expected["rgb_sha256"], f"RGB at {tick}")
        self.assertEqual(len(list(out.glob("frame_*.ppm"))), 601)
        self.assertEqual(backing[-1]["retained_checkpoints"], 2404)
        self.assertEqual(main[-1]["retained_checkpoints"], 2404)
        self.assertIs(main[-1]["level1_route_complete"], False)
        self.assertEqual(self.assets, {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                     for name in self.assets})
        self.assertEqual(fixture.read_bytes(), raw_fixture)
        return checkpoints

    def test_owned_window_is_deterministic_read_only_and_complete(self):
        full, result = self.replay("owned-full", 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        window, result = self.replay("owned-window", 12)
        self.assertEqual(result.returncode, 0, result.stderr)
        original = rows(full / "actor_storage.jsonl")
        retained = rows(window / "actor_storage.jsonl")
        main = rows(window / "trace.jsonl")
        self.assertEqual(retained[1:-1], [row for row in original[1:-1] if row["tick"] >= 12])
        self.assertEqual(len(retained[1:-1]), retained[-1]["retained_checkpoints"])
        self.assertEqual(retained[-1]["retained_checkpoints"], main[-1]["retained_checkpoints"])
        for header in (retained[0], main[0]):
            self.assertEqual(header["actor_storage_mode"], "production-owned")
            self.assertIs(header["legacy_actor_seed_adapter"], False)
            self.assertIs(header["candidate_only"], True)
            self.assertIs(header["original_fidelity_claim"], False)
        self.assertEqual(retained[0]["schema"], "lezac.actor-storage.scout.v1")
        self.assertEqual(retained[0]["actor_layout"], [31, 38])
        self.assertEqual(retained[0]["visual_layout"], [33, 8])
        self.assertEqual(retained[0]["link_layout"], [8, 16])
        self.assertIs(retained[0]["inactive_tails_included"], True)
        self.assertIs(retained[0]["visual_guard_included"], True)
        self.assertEqual(len(retained), len(main))
        self.assertGreater(max(row["count"] for row in retained[1:-1]), 0)
        for raw, normal in zip(retained[1:-1], main[1:-1]):
            self.assertEqual([raw[key] for key in ("seq", "tick", "phase")],
                             [normal[key] for key in ("seq", "tick", "phase")])
            self.assertEqual(len(bytes.fromhex(raw["actors_hex"])), 31 * 38)
            self.assertEqual(len(bytes.fromhex(raw["visuals_hex"])), 33 * 8)
            self.assertEqual(len(bytes.fromhex(raw["links_hex"])), 8 * 16)
            self.assertEqual(raw["visual_count"], raw["count"] + 2)
            self.assertEqual(len(raw["orders"]), raw["count"])
            self.assertEqual(len(set(raw["orders"])), raw["count"])
            self.assertTrue(all(order > 0 for order in raw["orders"]))
            if "frame" in normal:
                self.assertEqual((window / normal["frame"]).read_bytes(), (full / normal["frame"]).read_bytes())
        self.assertEqual(self.assets, {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                     for name in self.assets})

    def test_legacy_scout_has_no_owned_sidecar_or_mode_claim(self):
        out, result = self.replay("legacy", 180, command="--replay-level1-scout")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((out / "actor_storage.jsonl").exists())
        self.assertNotIn("actor_storage_mode", rows(out / "trace.jsonl")[0])

    def test_invalid_windows_and_flags_create_no_output(self):
        cases = [(value, ()) for value in (0, -1, 181, 20001, "+1", "1.0")]
        cases += [(12, ("--result-reels",)), (12, ("--original-intro-wait", "--unknown")),
                  (12, ("--original-intro-wait", "--result-typing", "--result-typing"))]
        for index, (start, flags) in enumerate(cases):
            with self.subTest(start=start, flags=flags):
                out, result = self.replay(f"invalid-{index}", start, flags)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(out.exists())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    EXE, OUTPUT = args.exe.resolve(), args.out.resolve() if args.out else None
    if OUTPUT is not None:
        OUTPUT.mkdir(parents=True, exist_ok=True)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OwnedScoutTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    print(f"owned_actor_scout_tests=ok tests={result.testsRun} candidate_only=1 original_fidelity_claim=0")
