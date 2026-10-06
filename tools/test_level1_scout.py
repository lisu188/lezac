"""A candidate-only capture window must not change replay state or pixels."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import level1_fidelity as fidelity

ROOT = Path(__file__).resolve().parents[1]
EXE: Path | None = None
OUTPUT: Path | None = None


class ScoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if OUTPUT is None:
            cls.temp = tempfile.TemporaryDirectory()
            cls.root = Path(cls.temp.name)
        else:
            cls.temp = None
            cls.root = OUTPUT / f"run-{os.getpid()}"
            cls.root.mkdir(parents=True, exist_ok=False)
        cls.route = ROOT / "tests/routes/level1_input_smoke.route"
        cls.full = cls.root / "full"
        cls.assets_before = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
        fidelity.record(EXE, ROOT, cls.route, cls.full)
        cls.rows = list(fidelity.trace_rows(cls.full))

    @classmethod
    def tearDownClass(cls):
        if cls.temp is not None:
            cls.temp.cleanup()

    def scout(self, name, start, route=None, flags=()):
        out = self.root / name
        command = [str(EXE), "--replay-level1-scout", str(route or self.route), str(out), str(start), *flags]
        result = subprocess.run(command, cwd=ROOT,
            env=dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy",
                     LEZAC_LOAD_JSON_ASSETS="0", LEZAC_LOAD_ORIGINAL_ASSETS="1"),
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return out, result

    def compare_window(self, full, rows, out, start):
        candidate = [fidelity.strict_json(line) for line in (out / "trace.jsonl").read_text().splitlines()]
        header, footer = candidate[0], candidate[-1]
        self.assertEqual(header["schema"], "lezac.level1.scout.v1")
        self.assertTrue(header["candidate_only"])
        self.assertEqual(header["capture_from_tick"], start)
        self.assertFalse(header["original_fidelity_claim"])
        expected_header = dict(rows[0], schema="lezac.level1.scout.v1",
                               candidate_only=True, capture_from_tick=start)
        self.assertEqual(header, expected_header)
        expected = [row for row in rows[1:-1] if row["tick"] >= start]
        self.assertEqual(candidate[1:-1], expected)
        self.assertEqual(footer["checkpoints"], rows[-1]["checkpoints"])
        self.assertEqual(footer["events"], rows[-1]["events"])
        self.assertEqual(footer["level1_route_complete"], rows[-1]["level1_route_complete"])
        self.assertEqual(footer["retained_checkpoints"], len(expected))
        self.assertEqual(footer["capture_from_tick"], start)
        self.assertTrue(footer["candidate_only"])
        self.assertFalse(footer["original_fidelity_claim"])
        self.assertFalse(footer["port_functionally_complete"])
        frames = {row["frame"] for row in expected if "frame" in row}
        self.assertEqual({path.name for path in out.glob("frame_*.ppm")}, frames)
        self.assertEqual(footer["frames"], len(frames))
        for row in expected:
            fidelity.validate_state(row["state"])
            if "frame" in row:
                self.assertEqual((out / row["frame"]).read_bytes(), (full / row["frame"]).read_bytes())
        with self.assertRaises(fidelity.EvidenceError):
            list(fidelity.trace_rows(out))

    def test_held_key_prefix_and_all_retained_states_pixels(self):
        out, result = self.scout("held-prefix", 12)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.compare_window(self.full, self.rows, out, 12)
        self.assertEqual(self.assets_before, {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS})

    def test_first_and_last_tick_windows(self):
        for start in (1, 180):
            with self.subTest(start=start):
                out, result = self.scout(f"edge-{start}", start)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.compare_window(self.full, self.rows, out, start)

    def test_original_intro_and_result_observers(self):
        route = self.root / "original-prelude.route"
        settings, events = fidelity.read_route(self.route)
        events[1] = [{"action": "up", "key": "1"}]
        del events[2]
        lines = ["LEZAC_LEVEL1_ROUTE_V1", f"seed {settings['seed']}",
                 f"ticks {settings['ticks']}", f"step_us {settings['step_us']}"]
        for tick, items in sorted(events.items()):
            lines.extend(f"event {tick} {item['action']} {item['key']}" for item in items)
        route.write_text("\n".join([*lines, "end"]) + "\n", encoding="ascii")
        full = self.root / "original-full"
        fidelity.record(EXE, ROOT, route, full, original_intro_wait=True, result_reels=True, result_typing=True)
        out, result = self.scout("original-window", 12, route,
                                ("--original-intro-wait", "--result-typing", "--result-reels"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.compare_window(full, list(fidelity.trace_rows(full)), out, 12)
        for name in ("result_reels.jsonl", "result_typing.jsonl"):
            self.assertEqual((out / name).read_bytes(), (full / name).read_bytes())

    def test_invalid_window_and_flags_create_no_output(self):
        cases = [(start, ()) for start in (0, -1, 181, 20001, "1.0", "+1", "", "4294967296")]
        cases += [(12, ("--result-reels",)), (12, ("--original-intro-wait", "--result-reels", "--result-reels")),
                  (12, ("--original-intro-wait", "--unknown"))]
        for index, (start, flags) in enumerate(cases):
            with self.subTest(start=start, flags=flags):
                out, result = self.scout(f"invalid-{index}", start, flags=flags)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(out.exists())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    EXE, OUTPUT = args.exe.resolve(), args.out.resolve() if args.out else None
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ScoutTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print(f"level1_scout_tests=ok tests={result.testsRun} candidate_only=1 original_fidelity_claim=0")
