"""Keep repeated startup checks isolated without executing a game or emulator."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_startup_map_memory as checker


class RerunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lezac-startup-rerun-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'evidence'
        self.exe = self.root / 'fake-executable'
        self.window = bytes(131072)
        self.calls = []

    def invoke(self, code=0, corrupt=False):
        def native(command, **kwargs):
            self.calls.append((command, kwargs))
            target = Path(command[2])
            target.mkdir()
            actual = b'partial output' if corrupt else self.window
            for boundary in ('intro', 'first-present'):
                (target / ('map-' + boundary + '.bin')).write_bytes(actual)
            return SimpleNamespace(returncode=code, stdout=b'startup_map_memory=ok menu_allocated=0 '
                b'intro_bytes=131072 first_present_bytes=131072\n', stderr=b'failed' if code else b'')
        with mock.patch.object(checker.subprocess, 'run', side_effect=native):
            checker.replay(self.exe, self.out, [self.window] * 3)

    @staticmethod
    def snapshot(directory):
        return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in directory.rglob('*') if path.is_file()}

    def test_two_successful_runs_keep_first_evidence_unchanged(self):
        self.invoke()
        first, = self.out.iterdir()
        before = self.snapshot(first)
        self.invoke()
        self.assertEqual(len(list(self.out.iterdir())), 2)
        self.assertEqual(self.snapshot(first), before)
        for directory in self.out.iterdir():
            self.assertTrue(directory.name.startswith('run-'))
            report = json.loads((directory / 'report.json').read_bytes())
            self.assertTrue(report['passed'])
            self.assertEqual(report['compiled_boundaries'], 6)

    def test_failed_native_run_is_preserved_when_retried(self):
        with self.assertRaisesRegex(RuntimeError, 'full App startup failed'):
            self.invoke(code=7)
        first, = self.out.iterdir()
        before = self.snapshot(first)
        self.assertEqual((first / 'fixed-a.stderr').read_bytes(), b'failed')
        self.invoke()
        self.assertEqual(self.snapshot(first), before)
        self.assertEqual(len(list(self.out.iterdir())), 2)

    def test_bad_output_is_preserved_when_retried(self):
        with self.assertRaisesRegex(RuntimeError, 'compiled map view size'):
            self.invoke(corrupt=True)
        first, = self.out.iterdir()
        before = self.snapshot(first)
        self.assertEqual((first / 'fixed-a/map-intro.bin').read_bytes(), b'partial output')
        self.invoke()
        self.assertEqual(self.snapshot(first), before)

    def test_preexisting_parent_files_are_not_modified(self):
        self.out.mkdir()
        marker = self.out / 'earlier-diagnostics.txt'
        marker.write_bytes(b'preserve')
        self.invoke()
        self.assertEqual(marker.read_bytes(), b'preserve')

    def test_commands_are_silent_and_never_receive_expected_state(self):
        self.invoke()
        self.assertEqual(len(self.calls), 3)
        for command, kwargs in self.calls:
            self.assertEqual(command[:2], [str(self.exe.resolve()), '--debug-startup-map-memory'])
            self.assertEqual(len(command), 3 if Path(command[2]).name == 'natural' else 5)
            self.assertTrue(Path(command[2]).resolve().is_relative_to(self.out.resolve()))
            self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
            self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
            self.assertEqual(kwargs['timeout'], 60)


if __name__ == '__main__':
    unittest.main()
