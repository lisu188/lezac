"""Guard a combined clock/route contract; synthetic joins are not captures."""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import struct
import unittest

import capture_original_startup_held_fire as capture
import check_held_fire_capture as checker
from level1_fidelity import EvidenceError


def synthetic_join():
    # Reuse the real lifecycle rows, but deliberately synthesize all startup
    # context and relocated segment identities for validator coverage only.
    path = capture.held.ROOT / "tests/fixtures/held_fire_objectives_original/hold_through.txt.gz"
    records = checker.parse(gzip.decompress(path.read_bytes()).decode("ascii"))
    cs, ds, resident, other = 0x390, 0xE32, 0x180, 0x281
    mcb = bytearray(16)
    mcb[0] = ord("M")
    struct.pack_into("<HH", mcb, 1, other, 0x100)
    records[0][1].update(resident=f"{other:04x}", mcb=mcb.hex())
    first_frame = int(next(row for tag, row in records if tag == "sample")["frame"])
    cx, dx, ss, ip = 0x172B, 0x3B63, 0x1000, capture.startup.CLOCK_IP + 5
    seed = capture.startup.clock_seed(cx, dx)
    for tag, row in records:
        if tag == "sample":
            regs = list(struct.unpack("<6H", bytes.fromhex(row["regs"])))
            regs[:2] = [cs, ds]
            row["regs"] = struct.pack("<6H", *regs).hex()
            row["frame"] = str((int(row["frame"]) - first_frame + 1) % 65536)
            if int(row["death_count"]):
                row["death_frame"] = str((int(row["death_frame"]) - first_frame + 1) % 65536)
            if row["seq"] == "1":
                row["rng"] = str(capture.initialization_rng(seed))
    text = "\n".join(tag + " " + " ".join(f"{key}={value}" for key, value in row.items()) for tag, row in records) + "\n"
    struct.pack_into("<H", mcb, 1, resident)
    clock = struct.pack("<8H", cx, dx, cx, dx, ds, ss, ip, cs).hex()
    result = dict(schema="lezac_startup_held_fire_v1", status="captured", mode="hold_through",
                  exe_sha256=capture.held.EXE_SHA256, audio="dummy", gameplay_seeded=False,
                  main_phase_gates=False, rng_draw_hook=False, temporary_preclock_gate=True,
                  whole_game_parity=False, frame_alignment=False, clock_hooks_restored=1,
                  child_exit_code=0, final_clock_calls=1, error=None,
                  trace_sha256=hashlib.sha256(text.encode("ascii")).hexdigest(),
                  initial_clock_record=clock, final_clock_record=clock,
                  code_segment=cs, data_segment=ds, resident_segment=resident, resident_mcb=mcb.hex(),
                  clock_stub_sha256=hashlib.sha256(capture.startup.clock_stub(cs + 0x920)).hexdigest(),
                  dosbox_sha256=records[0][1]["dosbox_sha256"], held_source_sha256=records[0][1]["source_sha256"],
                  clock=dict(clock_cx=cx, clock_dx=dx, clock_calls=1, initialized_rng=seed, rng=seed,
                             clock_registers=dict(cs=cs, ds=ds, ss=ss, return_ip=ip)))
    return result, text


class CombinedTests(unittest.TestCase):
    def test_pinned_natural_clock_and_physical_route(self):
        root = capture.held.ROOT / "tests/fixtures/startup_held_fire_original"
        compressed = (root / "hold_through.txt.gz").read_bytes()
        raw = (root / "hold_through.json").read_bytes()
        self.assertEqual(hashlib.sha256(compressed).hexdigest(), "809e7bf01622fc97b1ecd313f7ea9ea35bc368cfbd45eba8ff707ee6f494da39")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), "37a20b6414f30cf9d031711821940a5625acdc199d2daf2ce3d4f1cd6c440c11")
        result = json.loads(raw)
        text = gzip.decompress(compressed).decode("ascii")
        self.assertEqual(hashlib.sha256(text.encode("ascii")).hexdigest(), "3df12c8484fc780c0d4c90f9506915d38be00c2ad6cb92f7dbe159010a0452a0")
        for newline in ("\n", "\r\n"):
            summary = capture.validate_context(result, text.replace("\n", newline))
            self.assertEqual(summary["startup_rng"], 85791767)
            self.assertEqual(summary["first_gameplay_rng"], 1932475625)
            self.assertEqual(summary["first_gameplay_frame"], 1)
            self.assertEqual((summary["samples"], summary["dying_seq"], summary["resumed_seq"]), (290, 206, 266))
            self.assertEqual(summary["total_hooks_restored"], 4)

    def test_synthetic_join_and_newlines(self):
        result, text = synthetic_join()
        for newline in ("\n", "\r\n"):
            summary = capture.validate_context(result, text.replace("\n", newline))
            self.assertEqual(summary["startup_rng"], 0x3B63172B)
            self.assertEqual(summary["total_hooks_restored"], 4)
            self.assertEqual(summary["samples"], 599)
            self.assertEqual(summary["first_gameplay_frame"], 1)

    def test_evidence_claims_and_cleanup_mutations_fail(self):
        result, text = synthetic_join()
        for key, value in (("status", "incomplete"), ("audio", "wasapi"), ("gameplay_seeded", True),
                           ("main_phase_gates", True), ("rng_draw_hook", True), ("temporary_preclock_gate", False),
                           ("whole_game_parity", True), ("frame_alignment", True), ("clock_hooks_restored", 0),
                           ("child_exit_code", -15), ("final_clock_calls", 2), ("error", "failure"),
                           ("trace_sha256", "0" * 64), ("clock_stub_sha256", "0" * 64),
                           ("final_clock_record", "0" * 32), ("initial_clock_record", "0" * 30),
                           ("resident_segment", 0x280), ("data_segment", 0xE33), ("mode", "release_repress"),
                           ("dosbox_sha256", "0" * 64), ("held_source_sha256", "0" * 64),
                           ("child_exit_code", False), ("clock_hooks_restored", True)):
            altered = copy.deepcopy(result)
            altered[key] = value
            with self.subTest(field=key), self.assertRaises(EvidenceError):
                capture.validate_context(altered, text)
        altered = copy.deepcopy(result)
        altered["resident_segment"] = 0x181
        mcb = bytearray.fromhex(altered["resident_mcb"])
        struct.pack_into("<H", mcb, 1, 0x181)
        altered["resident_mcb"] = mcb.hex()
        with self.assertRaisesRegex(EvidenceError, "arenas overlap"):
            capture.validate_context(altered, text)

    def test_clock_sample_mutations_fail(self):
        result, text = synthetic_join()
        for key in ("clock_cx", "clock_dx", "clock_calls", "initialized_rng", "rng"):
            altered = copy.deepcopy(result)
            altered["clock"][key] ^= 1
            with self.subTest(field=key), self.assertRaises(EvidenceError):
                capture.validate_context(altered, text)
        for key in ("cs", "ds", "ss", "return_ip"):
            altered = copy.deepcopy(result)
            altered["clock"]["clock_registers"][key] ^= 1
            with self.subTest(register=key), self.assertRaises(EvidenceError):
                capture.validate_context(altered, text)

    def test_extra_resident_loader_is_guarded_before_writes(self):
        for name, payload in (("../BAD.COM", b"x"), ("RNGWATCH.COM", b"x"), ("BAD.EXE", b"x"),
                              ("BAD.COM", b""), ("BAD.COM", bytearray(b"x"))):
            session = capture.startup.Session(Path("never-created-startup-held-test"))
            with self.subTest(name=name), self.assertRaises(EvidenceError):
                session.launch(clock_only=True, resident_loader=(name, payload))
            self.assertIsNone(session.child)

    def test_first_gameplay_seed_cannot_be_detached_from_natural_clock(self):
        result, text = synthetic_join()
        records = checker.parse(text)
        first = next(row for tag, row in records if tag == "sample")
        for key, value in (("rng", "1"), ("frame", "86")):
            original = first[key]
            first[key] = value
            mutated = "\n".join(tag + " " + " ".join(f"{k}={v}" for k, v in row.items()) for tag, row in records) + "\n"
            result["trace_sha256"] = hashlib.sha256(mutated.encode("ascii")).hexdigest()
            with self.subTest(field=key), self.assertRaisesRegex(EvidenceError, "398-draw startup chain"):
                capture.validate_context(result, mutated)
            first[key] = original


if __name__ == "__main__":
    unittest.main()
