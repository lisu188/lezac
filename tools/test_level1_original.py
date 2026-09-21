from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import level1_fidelity as fidelity
import level1_original as original

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/level1_original"
EXPECTED = {
    "walk": (41, "191010fa2371444334cfa67f208db50aeb15a5d07a721884fa1447b9dd651fcd"),
    "bomb": (297, "976f37c43b608d770d183d811893daa7ba12415b9382e7f89ecf24bedfdc3ca6"),
    "objective": (237, "57c305f8c8277e72419b473b62e2db3c4d2e90040e24e049241f0d876e6fec77"),
}
EXE: Path | None = None


def pinned_fixture(name: str, path: Path | None = None) -> None:
    path = path or FIXTURES / name
    pins = fidelity.strict_json((FIXTURES / "pins.json").read_text())
    fidelity.require(set(pins) == set(EXPECTED), "missing original route pin")
    expected = pins[name]
    fidelity.require(set(expected) == {"canonical_sha256", "source_sha256", "files"}, "invalid original route pin")
    manifest = fidelity.strict_json((path / "manifest.json").read_text())
    fidelity.require(manifest["files"] == expected["files"], "original bytes differ from the independently reviewed fixture")
    header = next(original.reference_rows(path))
    fidelity.require(header["source_sha256"] == expected["source_sha256"], "capture source provenance changed")
    fidelity.require(header["settings"]["ticks"] - original.PREFIX_TICKS == EXPECTED[name][0], "original route length changed")
    fidelity.require(original.fingerprint(path) == expected["canonical_sha256"] == EXPECTED[name][1], "original observations differ from pinned independent capture")


class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = FIXTURES / "walk"
        with gzip.open(cls.source / "reference.jsonl.gz", "rt", encoding="ascii") as stream:
            cls.rows = [fidelity.strict_json(line) for line in stream]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lezac-original-check-")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def clone(self, name: str = "reference") -> Path:
        target = self.root / name
        shutil.copytree(self.source, target)
        return target

    def resign(self, target: Path) -> None:
        manifest = json.loads((target / "manifest.json").read_text())
        manifest["files"] = {name: fidelity.sha256(target / name) for name in manifest["files"]}
        (target / "manifest.json").write_bytes(original.json_bytes(manifest))

    def rewrite(self, target: Path, rows: list[dict]) -> None:
        (target / "reference.jsonl.gz").unlink()
        with original.compressed_writer(target / "reference.jsonl.gz") as write:
            for row in rows:
                write(row)
        self.resign(target)

    def test_owned_instrumentation(self):
        image = original.check_executable(ROOT / "LEZAC.EXE")
        loader = original.resident_program()
        self.assertEqual(len(loader), original.RESIDENT_PARAGRAPHS * 16 - 256)
        self.assertIn(original.RESIDENT_MARKER, loader)
        for stage, (entry, window) in enumerate(original.HOOKS, 1):
            trampoline = original.trampoline(stage, image)
            self.assertTrue(trampoline.endswith(bytes.fromhex(window) + b"\xcb"))
            self.assertLess(len(trampoline), 128)
            self.assertEqual(original.far_call(0x200, 0x1234), bytes.fromhex("9a00023412"))

    def test_pinned_original_walk(self):
        pinned_fixture("walk")

    def test_capture_rejects_inconsistent_evidence(self):
        mutations = []
        def case(change):
            rows = copy.deepcopy(self.rows)
            change(rows)
            mutations.append(rows)
        case(lambda rows: rows.pop())
        case(lambda rows: rows.append(copy.deepcopy(rows[1])))
        case(lambda rows: rows[1]["post"].update(frame=99))
        case(lambda rows: rows[2].update(events=[{"action": "down", "key": "x"}]))
        case(lambda rows: rows[1]["registers"][0].__setitem__(0, 0))
        case(lambda rows: rows[2].__setitem__("sequences", [2, 3, 4]))
        case(lambda rows: rows[1]["post"]["players"][0]["xy"].__setitem__(0, 999))
        case(lambda rows: rows[1].__setitem__("rgb_delta_zlib_hex", "00"))
        case(lambda rows: rows[0].__setitem__("dimensions", [312, 152]))
        case(lambda rows: rows[0].__setitem__("resident_mcb", "00" * 16))
        case(lambda rows: rows[0].__setitem__("source_sha256", "not-a-hash"))
        case(lambda rows: rows[0].__setitem__("original_fidelity_claim", True))
        case(lambda rows: rows[-1].__setitem__("patches_restored", False))
        case(lambda rows: rows[-2]["post"].__setitem__("words", ""))
        case(lambda rows: rows[-1].__setitem__("samples", 1))
        case(lambda rows: rows[1].__setitem__("rgb_sha256", "0" * 64))
        for index, rows in enumerate(mutations):
            with self.subTest(index=index):
                target = self.clone(str(index))
                self.rewrite(target, rows)
                with self.assertRaises(ValueError):
                    list(original.reference_rows(target))

    def test_pin_rejects_rehashed_provenance(self):
        target = self.clone()
        rows = copy.deepcopy(self.rows)
        rows[0]["source_sha256"] = "0" * 64
        self.rewrite(target, rows)
        list(original.reference_rows(target))
        with self.assertRaises(ValueError):
            pinned_fixture("walk", target)

    def test_frame_delta_bounds(self):
        before = bytes(192000)
        frame = bytearray(before)
        frame[-1] = 1
        checksum = hashlib.sha256(frame).hexdigest()
        encoded = original.encode_frame(bytes(frame), before)
        self.assertEqual(original.decode_frame(encoded, before, checksum), bytes(frame))
        for invalid in (encoded + "00", "00", encoded[:-2], "x" * 12):
            with self.subTest(invalid=invalid[:20]), self.assertRaises(ValueError):
                original.decode_frame(invalid, before, checksum)

    def test_route_rejects_unimplemented_ui_events(self):
        path = self.root / "route.txt"
        path.write_text((self.source / "route.txt").read_text().replace("event 8 down x", "event 8 down p").replace("event 28 up x", "event 28 up p"))
        with self.assertRaises(ValueError):
            original.read_route(path)

    def test_comparator_detects_uncropped_pixels_and_late_corruption(self):
        if EXE is None:
            self.skipTest("--exe required")
        candidate = self.root / "cpp"
        fidelity.record(EXE, ROOT, self.source / "route.txt", candidate)
        report = original.compare(self.source, candidate)
        self.assertEqual((report["status"], report["frames"], report["states"], report["differing_pixels"]), ("match", 41, 82, 0))
        target = self.clone()
        rows = copy.deepcopy(self.rows)
        pixels = list(original.reference_rows(self.source))[1]["rgb"]
        changed = bytearray(pixels)
        changed[-1] ^= 1
        rows[1]["rgb_delta_zlib_hex"] = original.encode_frame(bytes(changed), bytes(192000))
        rows[1]["rgb_sha256"] = hashlib.sha256(changed).hexdigest()
        next_pixels = list(original.reference_rows(self.source))[2]["rgb"]
        rows[2]["rgb_delta_zlib_hex"] = original.encode_frame(next_pixels, bytes(changed))
        self.rewrite(target, rows)
        report = original.compare(target, candidate, self.root / "difference")
        self.assertEqual(report["status"], "diverged")
        self.assertEqual(report["differing_pixels"], 1)
        self.assertEqual((report["first_divergence"]["x"], report["first_divergence"]["y"]), (319, 199))
        self.assertEqual(len(fidelity.read_ppm(self.root / "difference/difference.ppm")), 192000)
        rows.pop()
        self.rewrite(target, rows)
        with self.assertRaises(ValueError):
            original.compare(target, candidate)


def main() -> int:
    global EXE
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--case", choices=EXPECTED)
    args = parser.parse_args()
    EXE = args.exe.resolve() if args.exe else None
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    if args.case:
        fidelity.require(EXE is not None, "--exe required for original replay")
        pinned_fixture(args.case)
        with tempfile.TemporaryDirectory(prefix="lezac-level1-parity-") as directory:
            output = Path(directory) / "cpp"
            fidelity.record(EXE, ROOT, FIXTURES / args.case / "route.txt", output)
            report = original.compare(FIXTURES / args.case, output)
            print(json.dumps(report, sort_keys=True))
            fidelity.require(report["status"] == "match", "original Level 1 divergence")
            print(f"level1_original=ok case={args.case} frames={report['frames']} pixels={report['pixels']} differing_pixels=0")
        return 0
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OriginalTests))
    if result.wasSuccessful() and not result.skipped:
        print(f"level1_original_guard=ok tests={result.testsRun} mutations=16 fullframe=1 late_validation=1")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
