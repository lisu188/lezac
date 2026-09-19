from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import level1_fidelity as fidelity

ROOT = Path(__file__).resolve().parents[1]
EXE: Path | None = None
OUTPUT: Path | None = None
MODE = "single"
ORIGINAL_SHA256 = "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec"
GATE_OFFSET = 0x770 + 0x8283
GATE_BYTES = bytes.fromhex(
    "803ec579007425803ec67900741e833e8020007517e8c69a803eb779077705"
    "e937f5eb086a02e86898e913f5803e58201b7403e94af6"
)


def check_original_gate(data: bytes) -> None:
    fidelity.require(hashlib.sha256(data).hexdigest() == ORIGINAL_SHA256,
                     "original executable hash differs")
    fidelity.require(data[GATE_OFFSET:GATE_OFFSET + len(GATE_BYTES)] == GATE_BYTES,
                     "original completion gate differs")


def threshold_met(state: dict) -> bool:
    collected, destroyed, bonus_target, destruction_target, denominator = state["progress"][:5]
    return collected >= bonus_target and denominator > 0 and destroyed * 100 // denominator >= destruction_target


def state_without_score(player: dict) -> dict:
    return {key: value for key, value in player.items() if key != "score"}


def completed_rows(bundle: Path) -> tuple[list[dict], dict]:
    rows = [fidelity.strict_json(line) for line in (bundle / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    return rows, {row["tick"]: row for row in rows if row.get("phase") == "post_update"}


class CompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if EXE is None:
            raise RuntimeError("--exe is required")
        check_original_gate((ROOT / "LEZAC.EXE").read_bytes())
        cls.temporary = tempfile.TemporaryDirectory() if OUTPUT is None else None
        cls.artifacts = Path(cls.temporary.name) if cls.temporary else OUTPUT
        if not cls.temporary:
            cls.artifacts.mkdir(parents=True, exist_ok=False)
        cls.asset_hashes = {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}
        cls.bundle = cls.artifacts / MODE
        cls.route = ROOT / "tests/routes" / ("level1_complete_1p.route" if MODE == "single" else "level1_complete_2p.route")
        cls.summary = fidelity.record(EXE, ROOT, cls.route, cls.bundle)
        cls.rows, cls.post = completed_rows(cls.bundle)
        cls.manifest = fidelity.load_manifest(cls.bundle)
        cls.level1 = [row for row in cls.post.values() if row["state"]["level"] == 1]
        cls.outro = [row for row in cls.level1 if row["state"]["flow"][4]]
        cls.waiting = [row for row in cls.outro if row["state"]["flow"][5]]
        cls.level2 = [row for row in cls.post.values() if row["state"]["level"] == 2 and not any(row["state"]["flow"][i] for i in (0, 2, 3, 4))]
        cls.negative = None
        if MODE == "single":
            lines = cls.route.read_text(encoding="utf-8").splitlines()
            lines = [line.replace("ticks 1260", "ticks 800") for line in lines
                     if line != "end" and not (line.startswith("event ") and
                         (int(line.split()[1]) >= 1180 or line in {"event 350 down n", "event 351 up n"}))]
            negative_route = cls.artifacts / "one-bomb.route"
            negative_route.write_text("\n".join(lines + ["end"]) + "\n", encoding="utf-8")
            cls.negative_bundle = cls.artifacts / "one-bomb"
            fidelity.record(EXE, ROOT, negative_route, cls.negative_bundle)
            cls.negative, cls.negative_post = completed_rows(cls.negative_bundle)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.temporary:
            cls.temporary.cleanup()

    def test_original_static_gate_and_mutations(self) -> None:
        data = (ROOT / "LEZAC.EXE").read_bytes()
        check_original_gate(data)
        for offset in (GATE_OFFSET, GATE_OFFSET + 12, GATE_OFFSET + 17, GATE_OFFSET + 19):
            mutant = bytearray(data)
            mutant[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(fidelity.EvidenceError):
                check_original_gate(bytes(mutant))
        with self.assertRaises(fidelity.EvidenceError):
            check_original_gate(data[:-1])

    def test_normal_input_reaches_level_two(self) -> None:
        self.assertTrue(self.rows[-1]["level1_route_complete"])
        self.assertFalse(self.rows[-1]["original_fidelity_claim"])
        self.assertFalse(self.rows[-1]["port_functionally_complete"])
        self.assertTrue(self.outro)
        self.assertTrue(self.waiting)
        self.assertGreaterEqual(len(self.level2), 50)
        self.assertEqual(self.post[1]["state"]["flow"][:6], [0, 0, 0, 1, 0, 0])
        self.assertEqual(self.post[4]["state"]["flow"][:6], [0, 0, 0, 0, 0, 0])
        pickup = next(row for row in self.level1 if row["state"]["progress"][0] == 1)
        self.assertEqual(pickup["tick"], 84)
        self.assertTrue(all(row["state"]["players"][0]["health"][1:3] == [3, 0] for row in self.level1))
        bombs = {bomb["order"]: bomb for row in self.level1 for bomb in row["state"]["bombs"]}
        self.assertEqual(len(bombs), 2)
        self.assertTrue(all(bomb["type"] == 2 and bomb["owner"] == 1 for bomb in bombs.values()))
        self.assertEqual(self.outro[0]["state"]["players"][0]["inventory"], [200, 20, 4, 0, 2])
        if MODE == "two":
            self.assertEqual(self.post[4]["state"]["player_count"], 2)
            p2 = [row["state"]["players"][1]["x"] for row in self.level1]
            self.assertGreater(max(p2) - min(p2), 40)
            self.assertTrue(any(row["state"]["players"][1]["health"][2] for row in self.level1))
            self.assertEqual(self.level2[0]["state"]["players"][1]["health"][:3], [100, 3, 0])
        else:
            self.assertIsNotNone(self.negative)
            self.assertFalse(self.negative[-1]["level1_route_complete"])
            negative_states = [row["state"] for row in self.negative_post.values()]
            self.assertTrue(all(state["level"] == 1 and not state["flow"][4] for state in negative_states))
            self.assertEqual(negative_states[-1]["progress"][:5], [1, 29, 1, 50, 66])

    def test_completion_waits_for_collapse(self) -> None:
        pending = [row for row in self.level1 if threshold_met(row["state"]) and row["state"]["collapse"]]
        self.assertGreater(len(pending), 250)
        for row in pending:
            with self.subTest(tick=row["tick"]):
                self.assertFalse(row["state"]["flow"][4], "results began before collapse settled")
        self.assertTrue(self.outro)
        first = self.outro[0]
        self.assertFalse(first["state"]["collapse"])
        self.assertTrue(threshold_met(first["state"]))
        self.assertTrue(self.post[first["tick"] - 1]["state"]["collapse"])
        self.assertEqual(first["state"]["progress"][:5], [1, 50, 1, 50, 66])
        self.assertEqual(first["tick"], 755)

    def test_result_sequence_freezes_gameplay(self) -> None:
        self.assertTrue(self.outro)
        first = self.outro[0]
        initial = first["state"]
        immutable = set(initial) - {"players", "outro", "flow", "random_seed", "sound_latch"}
        for row in self.outro[1:]:
            state = row["state"]
            for key in sorted(immutable):
                if state[key] != initial[key]:
                    self.fail(f"gameplay changed behind results at tick {row['tick']}: {key}")
            for index, player in enumerate(state["players"]):
                if state_without_score(player) != state_without_score(initial["players"][index]):
                    self.fail(f"player {index + 1} changed behind results at tick {row['tick']}")
        outro_ticks = {row["tick"] for row in self.outro[1:]}
        self.assertFalse(any(row.get("phase") == "after_nonplayers" and row["tick"] in outro_ticks for row in self.rows))
        self.assertGreater(self.outro[-1]["time_ms"], first["time_ms"])
        self.assertGreater(self.outro[-1]["state"]["players"][0]["score"], initial["players"][0]["score"])

    def test_results_award_once_and_preserve_scores(self) -> None:
        self.assertTrue(self.outro and self.waiting and self.level2)
        start = self.outro[0]["state"]
        finish = self.waiting[-1]["state"]
        self.assertGreater(len(self.waiting), 200)
        active_players = 1 if MODE == "single" else 2
        self.assertEqual(start["outro"][1:4], [750, 4000, 5000])
        for index in range(active_players):
            expected = start["players"][index]["score"] + start["outro"][1] + start["outro"][2 + index]
            self.assertEqual(finish["players"][index]["score"], expected)
            scores = [row["state"]["players"][index]["score"] for row in self.outro]
            self.assertEqual(scores, sorted(scores))
            self.assertTrue(all(row["state"]["players"][index]["score"] == expected for row in self.waiting))
            self.assertEqual(self.level2[0]["state"]["players"][index]["score"], expected)
        self.assertEqual(self.level2[0]["state"]["logic_tick"], finish["logic_tick"] + 1)
        self.assertEqual(self.level2[0]["state"]["progress"][:2], [0, 0])
        self.assertTrue(all(row["state"]["players"][0]["score"] == 6050 for row in self.level2))

    def test_acknowledgement_and_full_frames(self) -> None:
        self.assertTrue(self.waiting and self.level2)
        ack = 1180 if MODE == "single" else 1480
        start = 1200 if MODE == "single" else 1500
        self.assertEqual(self.waiting[-1]["tick"], ack)
        self.assertEqual(self.post[ack + 1]["state"]["level"], 2)
        self.assertTrue(self.post[ack + 1]["state"]["flow"][3])
        self.assertEqual(self.level2[0]["tick"], start + 1)
        initial = fidelity.read_ppm(self.bundle / "frame_000000.ppm")
        self.assertGreater(len(set(initial)), 10)
        hashes = self.manifest["frames"]
        waiting_hashes = {hashes[f"frame_{row['tick']:06d}.ppm"] for row in self.waiting}
        self.assertEqual(len(waiting_hashes), 1)
        checkpoints = (0, 85, 220, 434, 755, self.waiting[0]["tick"], ack + 1, start + 1)
        self.assertEqual(len({hashes[f"frame_{tick:06d}.ppm"] for tick in checkpoints}), len(checkpoints))
        self.assertEqual(len(hashes), self.rows[-1]["ticks"] + 1)
        self.assertEqual(self.asset_hashes, {name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS})


def main() -> int:
    global ROOT, EXE, OUTPUT, MODE
    parser = argparse.ArgumentParser(description="Qualify natural C++ Level 1 completion, not DOS frame parity")
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mode", choices=("single", "two"), default="single")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    ROOT, EXE, MODE = args.root.resolve(), args.exe.resolve(), args.mode
    OUTPUT = args.out.resolve() if args.out else None
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CompletionTests))
    report = {"schema": "lezac.level1.completion-regression.v1", "mode": MODE, "tests": result.testsRun,
              "passed": result.wasSuccessful(), "failures": len(result.failures), "errors": len(result.errors),
              "evidence": "cpp-natural-route-and-original-static-gate", "original_fidelity_claim": False,
              "port_functionally_complete": False}
    if hasattr(CompletionTests, "post"):
        report.update({"ticks": len(CompletionTests.post),
                       "frames": CompletionTests.rows[-1]["frames"],
                       "route_sha256": fidelity.sha256(CompletionTests.route),
                       "executable_sha256": fidelity.sha256(EXE),
                       "outro_tick": CompletionTests.outro[0]["tick"] if CompletionTests.outro else None,
                       "level2_active_tick": CompletionTests.level2[0]["tick"] if CompletionTests.level2 else None})
    if OUTPUT is not None and OUTPUT.is_dir():
        (OUTPUT / "result.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if result.wasSuccessful():
        print(f"level1_completion_tests=ok mode={MODE} tests={result.testsRun} input_only=1 original_fidelity_claim=0")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
