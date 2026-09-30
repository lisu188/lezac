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

    def hooks(self, write=None, read=None):
        return capture.runtime_hooks(read or self.read, write or self.write, self.stop, self.resume,
                                     self.cs, self.recorder, self.segment, IMAGE)

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


if __name__ == "__main__":
    unittest.main()
