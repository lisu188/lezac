#!/usr/bin/env python3
"""Unit checks for recorder restoration, ring coherence and lifecycle rejection."""

import copy
import io
import hashlib
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import capture_original_held_fire as capture
import check_held_fire_capture as checker
import test_held_fire_xdotool as live


IMAGE = (capture.ROOT / "LEZAC.EXE").read_bytes()[0x770:]


def lifecycle(mode):
    """Synthetic rows for validator tests, not original-game evidence."""
    release = mode == "release_repress"
    death, waiting, resumed = 30, 90 if release else 0, 102 if release else 90
    events = [dict(after_seq=4, ack_seq=5, kind="keydown", reason="start")]
    if release:
        events += [dict(after_seq=30, ack_seq=31, kind="keyup", reason="death"),
                   dict(after_seq=100, ack_seq=101, kind="keydown", reason="waiting")]
    events.append(dict(after_seq=resumed + 4, ack_seq=resumed + 5, kind="keyup", reason="resumed"))
    rows = []
    for seq in range(1, resumed + 25):
        actor, flags, hardware = bytearray(38), bytearray(9), bytearray(10)
        actor[21] = 2 if death <= seq < resumed else 0
        flags[1] = 2 if release and waiting <= seq < resumed else 1
        flags[5] = 1 if seq >= death + 60 else 2
        held = seq >= 5 and not (release and 31 <= seq <= 100) and seq < resumed + 5
        hardware[3] = int(held)
        makes = max(0, min(seq, 30 if release else resumed + 4) - 4)
        if release and seq >= 101:
            makes += min(seq, resumed + 4) - 100
        breaks = int(release and seq >= 31) + int(seq >= resumed + 5)
        rows.append(dict(seq=seq, frame=(65520 + seq - 1) % 65536, makes=makes, breaks=breaks,
                         p1=bytes(actor), flags=bytes(flags), hardware=bytes(hardware),
                         regs=struct.pack("<6H", 0x2AD, 0xD4F, 0xA000, 0x19BE, 0x3FF6, 0x3FFE),
                         level=1, gate=1, fallback=seq - waiting + 1 if flags[1] == 2 else 0))
    return rows, events


class HookTests(unittest.TestCase):
    def setUp(self):
        self.cs, self.recorder, self.segment = 0x1000, 0x90000, 0x9000
        self.memory = bytearray(0xA0000)
        for at, original in capture.WINDOWS.items():
            self.memory[self.cs + at:self.cs + at + len(original)] = original
        for at, original in ((0x30C1, capture.CONTEXT_WINDOW), (0x30F6, IMAGE[0x30F6:0x30FB])):
            self.memory[self.cs + at:self.cs + at + len(original)] = original
        self.calls, self.stopped = [], False

    def read(self, at, size):
        return bytes(self.memory[at:at + size])

    def write(self, at, data):
        self.assertTrue(self.stopped)
        self.memory[at:at + len(data)] = data
        self.calls.append(at)

    def stop(self):
        self.stopped = True

    def resume(self):
        self.stopped = False

    def hooks(self, write=None, read=None, objective_context=False):
        return capture.runtime_hooks(read or self.read, write or self.write, self.stop, self.resume,
                                     self.cs, self.recorder, self.segment, IMAGE, objective_context)

    def assert_restored(self):
        for entry, length, _ in capture.HOOKS:
            self.assertEqual(self.read(self.cs + entry, length), IMAGE[entry:entry + length])
        self.assertFalse(self.stopped)

    def test_success_and_instruction_boundary(self):
        with self.hooks() as restored:
            self.assertFalse(self.stopped)
            self.assertEqual(len(restored), 0)
        self.assert_restored()
        self.assertEqual(len(restored), 2)
        stub = capture.irq_stub(IMAGE)
        self.assertEqual(stub[:10], bytes.fromhex("5589e536c74602a7105d"))
        self.assertEqual(stub[-3:], bytes.fromhex("3c2ccb"))
        self.assertIn(bytes.fromhex("a0b779aa"), capture.frame_stub(IMAGE))

    def test_every_partial_install_write_restores(self):
        for fail_index in range(4):
            with self.subTest(write=fail_index):
                self.setUp()
                counter = 0

                def partial(at, data):
                    nonlocal counter
                    index, counter = counter, counter + 1
                    if index == fail_index:
                        self.write(at, data[:2])
                        raise OSError("partial write")
                    self.write(at, data)

                with self.assertRaisesRegex(OSError, "partial write"):
                    with self.hooks(write=partial):
                        self.fail("incomplete installation reached observer")
                self.assert_restored()

    def test_body_failure_still_restores(self):
        for error in (RuntimeError("window lookup"), OSError("flush"), TimeoutError("keyup")):
            with self.subTest(error=str(error)):
                self.setUp()
                with self.assertRaises(type(error)):
                    with self.hooks():
                        raise error
                self.assert_restored()

    def test_restore_failure_does_not_skip_second_hook(self):
        restoring = False

        def fail_first(at, data):
            if restoring and at == self.cs + capture.HOOKS[0][0]:
                raise OSError("first hook")
            self.write(at, data)

        with self.assertRaisesRegex(RuntimeError, "hook cleanup failed"):
            with self.hooks(write=fail_first):
                restoring = True
        entry, length, _ = capture.HOOKS[1]
        self.assertEqual(self.read(self.cs + entry, length), IMAGE[entry:entry + length])
        self.assertFalse(self.stopped)

    def test_guard_failure_writes_nothing(self):
        self.memory[self.cs + 0x10A1] = 0
        with self.assertRaisesRegex(RuntimeError, "runtime guard"):
            with self.hooks():
                self.fail("guard accepted")
        self.assertEqual(self.calls, [])
        self.assertFalse(self.stopped)

    def test_ring_rejects_overrun_regression_and_torn_read(self):
        raw = struct.pack("<H", 1) + bytes(capture.STRIDE - 2)
        read = lambda at, size: raw[:size]
        self.assertEqual(capture.read_record(read, 0, 0, 1), raw)
        for sequence, total in ((0, 17), (2, 1), (1, 1)):
            with self.assertRaises(RuntimeError):
                capture.read_record(read, 0, sequence, total)
        for reader in (lambda at, size: raw[1:size + 1],
                       lambda at, size: raw if size == capture.STRIDE else b"\0\0"):
            with self.assertRaises(RuntimeError):
                capture.read_record(reader, 0, 0, 1)

    def test_context_hook_and_every_partial_write_restore(self):
        for fail_index in range(6):
            with self.subTest(write=fail_index):
                self.setUp()
                calls = 0

                def partial(at, data):
                    nonlocal calls
                    index, calls = calls, calls + 1
                    if index == fail_index:
                        self.write(at, data[:2])
                        raise OSError("partial context write")
                    self.write(at, data)

                with self.assertRaisesRegex(OSError, "partial context write"):
                    with self.hooks(write=partial, objective_context=True):
                        self.fail("partial hook reached observation")
                self.assert_restored()
                self.assertEqual(self.read(self.cs + 0x30F6, 5), IMAGE[0x30F6:0x30FB])
        self.setUp()
        with self.hooks(objective_context=True) as restored:
            self.assertFalse(self.stopped)
        self.assertEqual(len(restored), 3)
        self.assert_restored()

    def test_context_guard_is_checked_before_writes(self):
        for offset in (0x30C1, 0x30F6):
            self.setUp()
            self.memory[self.cs + offset] = 0
            with self.assertRaisesRegex(RuntimeError, "runtime objective guard"):
                with self.hooks(objective_context=True):
                    self.fail("invalid original gate accepted")
            self.assertEqual(self.calls, [])
            self.assertFalse(self.stopped)


class ObjectiveContextTests(unittest.TestCase):
    def rows(self):
        rows, _ = lifecycle("hold_through")
        for row in rows:
            death = row["seq"] >= 30
            row.update(rng=1234 + row["seq"], required=8, collected=1 if death else 0,
                       remaining=7 if death else 8, objective=108,
                       death_count=int(death), death_frame=rows[28]["frame"] if death else 0,
                       death_rng=5678 if death else 0, death_required=8 if death else 0,
                       death_collected=0, death_remaining=8 if death else 0,
                       death_objective=108 if death else 0, death_gate=int(death), death_player=int(death))
        return rows

    def test_binary_context_fits_existing_ring(self):
        row = self.rows()[29]
        raw = bytes(99) + struct.pack("<IHHHBHHIHHHBBB", *(row[key] for key in capture.CONTEXT_FIELDS)) + b"\0"
        self.assertEqual(len(raw), capture.STRIDE)
        self.assertEqual(capture.objective_context_from_record(raw), {key: row[key] for key in capture.CONTEXT_FIELDS})
        with self.assertRaises(RuntimeError):
            capture.objective_context_from_record(raw[:-1])
        self.assertLess(0x300 + len(capture.frame_stub(IMAGE, True)), 0x500)
        self.assertLess(0x500 + len(capture.death_stub(IMAGE)), capture.DEATH_CONTEXT)
        self.assertIn(bytes.fromhex("538a16b4798b0eba7831db1ec536e0c1ac38d0750143e2f81f89d8ab5b"), capture.frame_stub(IMAGE, True))

    def test_exact_boundary_not_recomputed_from_later_counts(self):
        rows = self.rows()
        rows[30]["remaining"] = 0
        capture.validate_objective_context(rows)

    def test_context_mutations_fail(self):
        for field, value in (("death_count", 2), ("death_gate", 0), ("death_player", 2),
                             ("death_required", 9), ("death_frame", 123), ("rng", -1),
                             ("remaining", 1981), ("death_rng", 0x100000000), ("collected", "1")):
            rows = self.rows()
            rows[30][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                capture.validate_objective_context(rows)
        rows = self.rows()
        rows[0]["death_remaining"] = 8
        with self.assertRaises(RuntimeError):
            capture.validate_objective_context(rows)

    def test_v4_parser_keeps_v3_fixture_unchanged(self):
        original = (capture.ROOT / "tests/fixtures/held_fire_original/hold_through.txt").read_text(encoding="ascii")
        records = checker.parse(original)
        header = records[0][1]
        header.update(schema="held_fire_irq_v4", hooks="10a1,7a57,30f6",
                      frame_sha256=hashlib.sha256(capture.frame_stub(IMAGE, True)).hexdigest(),
                      death_sha256=hashlib.sha256(capture.death_stub(IMAGE)).hexdigest())
        dying = next(fields for tag, fields in records if tag == "sample" and bytes.fromhex(fields["p1"])[21] == 2)
        death_seq, death_frame = int(dying["seq"]), int(dying["frame"])
        for tag, fields in records:
            if tag != "sample":
                continue
            death = int(fields["seq"]) >= death_seq
            context = dict(rng=1234, required=8, collected=0, remaining=8, objective=108,
                           death_count=int(death), death_frame=(death_frame - 1) % 65536 if death else 0,
                           death_rng=5678 if death else 0, death_required=8 if death else 0,
                           death_collected=0, death_remaining=8 if death else 0,
                           death_objective=108 if death else 0, death_gate=int(death), death_player=int(death))
            fields.update({key: str(value) for key, value in context.items()})
        records.insert(-1, ("restored", dict(hook="30f6", bytes=IMAGE[0x30F6:0x30FB].hex())))
        records[-1][1]["hooks_restored"] = "3"

        def text():
            return "\n".join(tag + " " + " ".join(f"{key}={value}" for key, value in fields.items()) for tag, fields in records)

        # Synthetic extension for parser coverage, not a new original capture.
        self.assertEqual(checker.validate_text(text())["objective_context"], 1)
        header["death_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "stub identity"):
            checker.validate_text(text())
        self.assertEqual(checker.validate_text(original)["objective_context"], 0)


class LifecycleTests(unittest.TestCase):
    def test_both_modes_and_clock_wrap(self):
        for mode in ("hold_through", "release_repress"):
            rows, events = lifecycle(mode)
            result = capture.validate_lifecycle(rows, events, mode)
            self.assertEqual(result["dying_seq"], 30)
            self.assertEqual(result["samples"], len(rows))

    def test_mutations_are_not_promoted(self):
        for mode in ("hold_through", "release_repress"):
            for field, value in (("seq", 3), ("frame", 3), ("level", 2), ("gate", 0),
                                 ("fallback", 230), ("regs", bytes(12)), ("p1", bytes(37)),
                                 ("flags", bytes(9)), ("makes", 0), ("breaks", 3)):
                with self.subTest(mode=mode, field=field):
                    rows, events = lifecycle(mode)
                    rows[35][field] = value
                    with self.assertRaises(RuntimeError):
                        capture.validate_lifecycle(rows, events, mode)
            for kind in ("missing_ack", "late_ack", "missing_release", "truncated", "duplicate"):
                with self.subTest(mode=mode, mutation=kind):
                    rows, events = lifecycle(mode)
                    if kind == "missing_ack": events[-1]["ack_seq"] = 0
                    if kind == "late_ack": events[0]["ack_seq"] = 29
                    if kind == "missing_release": events.pop()
                    if kind == "truncated": rows.pop()
                    if kind == "duplicate": rows.insert(3, copy.deepcopy(rows[2]))
                    with self.assertRaises(RuntimeError):
                        capture.validate_lifecycle(rows, events, mode)


class CompletionTests(unittest.TestCase):
    def test_success_after_outer_cleanup_only(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "trace.txt"
            output.touch()
            observations = []

            def run():
                observations.append(dict(samples=120, hooks_restored=2))
                self.assertNotIn("complete", output.read_text())
                return 0

            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(capture.complete_capture(run, output, observations), 0)
            self.assertIn("game_process_exited=1", output.read_text())
            self.assertIn("held_fire_capture=ok", stdout.getvalue())

    def test_late_outer_failure_has_no_success(self):
        for failure in ("post_snapshot", "screenshot", "process_wait", "missing_restore", "exit_code"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "trace.txt"
                output.touch()
                observations = [dict(hooks_restored=1 if failure == "missing_restore" else 2)]

                def run():
                    if failure in ("post_snapshot", "screenshot", "process_wait"):
                        raise RuntimeError(failure)
                    return 1 if failure == "exit_code" else 0

                with redirect_stdout(io.StringIO()) as stdout, self.assertRaises(RuntimeError):
                    capture.complete_capture(run, output, observations)
                self.assertNotIn("complete ", output.read_text())
                self.assertNotIn("held_fire_capture=ok", stdout.getvalue())
                self.assertIn("failed ", output.read_text())


class SeederBoundaryTests(unittest.TestCase):
    def test_resident_loader_and_silent_child_environment(self):
        for inherited in ("pulseaudio", "wasapi", ""):
            with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, SDL_AUDIODRIVER=inherited):
                root = Path(directory)
                (root / "LEZAC.EXE").touch()
                (root / "L1ORACLE.COM").touch()

                def child(command, **kwargs):
                    self.assertEqual(kwargs["env"]["SDL_AUDIODRIVER"], "dummy")
                    self.assertLess(command.index("L1ORACLE.COM"), command.index("LEZAC.EXE"))
                    raise RuntimeError("child intercepted; no game launched")

                with patch.object(capture.seeder.subprocess, "Popen", side_effect=child), self.assertRaisesRegex(RuntimeError, "child intercepted"):
                    capture.seeder.run_live(SimpleNamespace(run_dir=directory, resident_loader="L1ORACLE.COM"))
                self.assertEqual(os.environ["SDL_AUDIODRIVER"], inherited)

    def test_loader_cannot_escape_temporary_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "LEZAC.EXE").touch()
            for loader in ("../evil.com", "C:/evil.com", "MISSING.COM", "bad.exe", "bad;name.com"):
                with self.subTest(loader=loader), patch.object(capture.seeder.subprocess, "Popen") as child:
                    with self.assertRaises(RuntimeError):
                        capture.seeder.run_live(SimpleNamespace(run_dir=directory, resident_loader=loader))
                    child.assert_not_called()


class OriginalObservationTests(unittest.TestCase):
    def test_pinned_captures_and_newlines(self):
        root = capture.ROOT / "tests/fixtures/held_fire_original"
        pins = json.loads((root / "pins.json").read_text())
        self.assertFalse(pins["whole_game_parity"])
        for name, digest in pins["captures"].items():
            text = (root / name).read_text(encoding="ascii")
            self.assertEqual(hashlib.sha256(text.encode("ascii")).hexdigest(), digest)
            for newline in ("\n", "\r\n"):
                result = checker.validate_text(text.replace("\n", newline))
                self.assertEqual(result["mode"], Path(name).stem)

    def test_persisted_record_mutations(self):
        root = capture.ROOT / "tests/fixtures/held_fire_original"
        for name in ("hold_through", "release_repress"):
            original = checker.parse((root / f"{name}.txt").read_text())
            mutations = [("capture", "schema", "held_fire_irq_v2"),
                         ("capture", "exe_sha256", "0" * 64),
                         ("capture", "irq_sha256", "0" * 64),
                         ("capture", "frame_sha256", "0" * 64),
                         ("capture", "mcb", "0" * 32),
                         ("capture", "gameplay_seeded", "1"),
                         ("sample", "seq", "2"), ("sample", "level", "2"),
                         ("sample", "ammo", "00"), ("sample", "regs", "0" * 24),
                         ("event", "after_seq", "0"), ("event", "key", "space"),
                         ("ack", "seq", "0"), ("ack", "makes", "9999"),
                         ("screenshot", "frame_alignment", "1"),
                         ("observed", "samples", "1"), ("restored", "bytes", "00"),
                         ("complete", "game_process_exited", "0"),
                         ("complete", "hooks_restored", "1"),
                         ("complete", "whole_game_parity", "1")]
            for tag, key, value in mutations:
                with self.subTest(capture=name, tag=tag, key=key):
                    records = copy.deepcopy(original)
                    next(fields for record, fields in records if record == tag)[key] = value
                    text = "\n".join(record + " " + " ".join(f"{k}={v}" for k, v in fields.items())
                                     for record, fields in records)
                    with self.assertRaises(RuntimeError):
                        checker.validate_text(text)
            for tag in ("sample", "event", "ack", "observed", "restored", "complete"):
                records = copy.deepcopy(original)
                del records[next(i for i, (record, _) in enumerate(records) if record == tag)]
                text = "\n".join(record + " " + " ".join(f"{k}={v}" for k, v in fields.items())
                                 for record, fields in records)
                with self.subTest(capture=name, removed=tag), self.assertRaises(RuntimeError):
                    checker.validate_text(text)


class LiveValidationTests(unittest.TestCase):
    def converted(self, mode):
        rows, events = lifecycle(mode)
        reference = dict(capture.validate_lifecycle(rows, events, mode), mode=mode)
        converted = [dict(seq=r["seq"], frame=r["seq"], makes=r["makes"], breaks=r["breaks"],
                          repeats=max(0, r["makes"] - 1), key=r["hardware"][3], latch=r["hardware"][3],
                          dead=int(r["p1"][21] == 2), state=r["flags"][1], lives=r["flags"][5],
                          countdown=max(0, 90 - r["seq"]) if r["p1"][21] == 2 else 0,
                          gate=r["gate"], level=1, reset=2, fallback=r["fallback"]) for r in rows]
        return converted, events, reference

    def test_real_input_lifecycle_validator(self):
        for mode in ("hold_through", "release_repress"):
            rows, events, reference = self.converted(mode)
            result = live.validate_live(rows, events, reference)
            self.assertEqual(result["death_updates"], 60)
            self.assertEqual(result["whole_game_parity"], 0)

    def test_rejects_restart_missing_updates_and_input(self):
        for mode in ("hold_through", "release_repress"):
            for field, value in (("reset", 3), ("frame", 0), ("seq", 0), ("lives", 0),
                                 ("gate", 0), ("fallback", 230), ("dead", 0), ("state", 0)):
                rows, events, reference = self.converted(mode)
                rows[31][field] = value
                with self.subTest(mode=mode, field=field), self.assertRaises(RuntimeError):
                    live.validate_live(rows, events, reference)
            rows, events, reference = self.converted(mode)
            events.pop()
            with self.assertRaises(RuntimeError):
                live.validate_live(rows, events, reference)

    def context(self, gate=1):
        rows, _, _ = self.converted("hold_through")
        for row in rows:
            row.update(rng=1234, collected=0, remaining=8 if gate else 7, required=8, objective=108)
            if row["seq"] >= 30:
                row["gate"] = gate
        death = dict(after_seq=29, frame=30, player=1, gate=gate, level=1, reset=2,
                     rng=5678, collected=0, remaining=8 if gate else 7, required=8, objective=108)
        return rows, [death], [dict(menu=1, rng=91011)]

    def test_live_context_reports_open_and_closed_gates_without_parity(self):
        for gate in (0, 1):
            rows, deaths, statuses = self.context(gate)
            rows[30]["remaining"] = 0
            result = live.summarize_objective_context(rows, deaths, statuses)
            self.assertEqual(result["death_boundaries"][0]["gate"], gate)
            self.assertEqual(result["startup_menu_rng"], 91011)
            self.assertEqual(result["whole_game_parity"], 0)
            self.assertTrue(result["gate_formula_match"])

    def test_live_context_rejects_missing_or_detached_boundaries(self):
        for field, value in (("after_seq", 30), ("frame", 31), ("gate", 0),
                             ("remaining", 7), ("player", 2), ("reset", 3), ("rng", -1)):
            rows, deaths, statuses = self.context()
            deaths[0][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                live.summarize_objective_context(rows, deaths, statuses)
        rows, _, statuses = self.context()
        with self.assertRaisesRegex(RuntimeError, "exact gate boundary"):
            live.summarize_objective_context(rows, [], statuses)
        rows[0].pop("remaining")
        with self.assertRaisesRegex(RuntimeError, "objective context"):
            live.summarize_objective_context(rows, [], statuses)
        rows, deaths, _ = self.context()
        for statuses in ([], [dict(menu=1, rng=-1)], [dict(menu=1)], [dict(menu=0, rng=123)]):
            with self.subTest(statuses=statuses), self.assertRaisesRegex(RuntimeError, "startup menu RNG"):
                live.summarize_objective_context(rows, deaths, statuses)


if __name__ == "__main__":
    unittest.main()
