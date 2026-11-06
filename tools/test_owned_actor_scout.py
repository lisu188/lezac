"""Exercise the actual App's owned-storage scout without the legacy seed adapter."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

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

    def replay(self, name, start, flags=(), command="--replay-level1-owned-scout"):
        out = self.root / name
        result = subprocess.run([str(EXE), command, str(self.route), str(out), str(start), *flags],
            cwd=ROOT, env=dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy",
                LEZAC_LOAD_JSON_ASSETS="0", LEZAC_LOAD_ORIGINAL_ASSETS="1"),
            capture_output=True, text=True, timeout=60)
        return out, result

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
