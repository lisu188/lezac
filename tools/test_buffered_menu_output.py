#!/usr/bin/env python3
"""Check repeated live-menu output ownership without launching the game."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_buffered_menu_repeat_xdotool as harness


class BufferedMenuOutputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lezac-menu-output-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def observer(self, token, fail_choice=None):
        def observe(exe, output, choice, held, expected):
            output.mkdir(parents=True, exist_ok=False)
            result = dict(status="observed", token=token, choice=choice, held=held)
            (output / "capture.ppm").write_bytes(token.encode() + b"\x00\r\n")
            (output / "process.log").write_text(token)
            if choice == fail_choice:
                result["status"] = "failed"
            (output / "result.json").write_text(json.dumps(result))
            if choice == fail_choice:
                raise RuntimeError("retained partial observation")
            return result
        return observe

    def invoke(self, output, observer):
        stream = io.StringIO()
        argv = ["test_buffered_menu_repeat_xdotool.py", "--exe", str(self.root / "unused-exe"),
                "--out", str(output)]
        with patch.object(sys, "argv", argv), patch.dict(os.environ, DISPLAY=":test"), \
                patch.object(harness, "load_fixture", return_value=({}, {})), \
                patch.object(harness, "observe", side_effect=observer), redirect_stdout(stream):
            harness.main()
        return stream.getvalue()

    @staticmethod
    def snapshot(output):
        return {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}

    def assert_preserved(self, snapshot):
        for path, contents in snapshot.items():
            self.assertEqual(path.read_bytes(), contents, str(path))

    def test_first_run_keeps_existing_capture_layout(self):
        output = self.root / "new" / "captures"
        stdout = self.invoke(output, self.observer("first"))
        summary = json.loads((output / "result.json").read_text())
        self.assertEqual(summary["output"], str(output))
        self.assertEqual([(case["choice"], case["held"]) for case in summary["cases"]],
                         [(1, True), (2, True), (1, False)])
        self.assertEqual({path.name for path in output.iterdir()},
                         {"held-one", "held-two", "fresh-intro", "result.json"})
        self.assertIn("whole_game_parity=0 output=" + str(output), stdout)

    def test_completed_runs_keep_all_prior_evidence(self):
        output = self.root / "captures with spaces"
        self.invoke(output, self.observer("first"))
        first = self.snapshot(output)
        self.invoke(output, self.observer("second"))
        second = self.snapshot(output)
        self.invoke(output, self.observer("third"))
        self.assert_preserved(first)
        self.assert_preserved(second)
        runs = sorted(output.glob("run-*"))
        self.assertEqual(len(runs), 2)
        self.assertEqual({json.loads((run / "result.json").read_text())["cases"][0]["token"]
                          for run in runs}, {"second", "third"})
        for run in runs:
            self.assertEqual(json.loads((run / "result.json").read_text())["output"], str(run))

    def test_partial_failure_remains_unchanged_on_retry(self):
        output = self.root / "partial"
        with self.assertRaisesRegex(RuntimeError, "retained partial observation"):
            self.invoke(output, self.observer("failed", fail_choice=2))
        self.assertFalse((output / "result.json").exists())
        failed = self.snapshot(output)
        self.invoke(output, self.observer("retry"))
        self.assert_preserved(failed)
        runs = list(output.glob("run-*"))
        self.assertEqual(len(runs), 1)
        summary = json.loads((runs[0] / "result.json").read_text())
        self.assertEqual(summary["status"], "observed")
        self.assertEqual(len(summary["cases"]), 3)

    def test_existing_directory_is_not_reused_even_when_empty(self):
        output = self.root / "empty"
        output.mkdir()
        actual = harness.prepare_output(output)
        self.assertEqual(actual.parent, output)
        self.assertTrue(actual.name.startswith("run-"))
        entries = list(output.iterdir())
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].samefile(actual))

    def test_concurrent_allocations_have_distinct_directories(self):
        output = self.root / "concurrent"
        with ThreadPoolExecutor(max_workers=8) as pool:
            runs = list(pool.map(lambda _: harness.prepare_output(output), range(16)))
        self.assertEqual(len(set(runs)), 16)
        self.assertEqual(runs.count(output), 1)
        self.assertTrue(all(run.is_dir() for run in runs))
        self.assertTrue(all(run == output or run.parent == output for run in runs))

    def test_output_file_fails_without_overwriting_it(self):
        output = self.root / "not-a-directory"
        output.write_bytes(b"keep this file\x00")
        with self.assertRaises(OSError):
            harness.prepare_output(output)
        self.assertEqual(output.read_bytes(), b"keep this file\x00")

    def test_unrelated_creation_failure_is_not_hidden(self):
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(PermissionError, "denied"):
                harness.prepare_output(self.root / "denied")

    def test_default_output_stays_in_unique_temporary_directories(self):
        with patch.object(tempfile, "tempdir", str(self.root)):
            first = harness.prepare_output(None)
            second = harness.prepare_output(None)
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, self.root)
        self.assertEqual(second.parent, self.root)
        self.assertTrue(first.is_dir() and second.is_dir())


if __name__ == "__main__":
    unittest.main()
