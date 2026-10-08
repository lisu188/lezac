"""Check retained output for successful and failing mocked compiled probes."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import check_actor_constructor_velocity as checker


class ConstructorCheckerRetention(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = checker.fixture()

    def exercise(self, mode):
        with tempfile.TemporaryDirectory(prefix='lezac-constructor-checker-') as tmp:
            out = Path(tmp)

            def runner(command, **kwargs):
                self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
                self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
                self.assertEqual(kwargs['timeout'], 30)
                actual = Path(command[2])
                payload = self.expected if mode != 'truncated' else self.expected[:-1]
                if mode == 'corrupted':
                    payload = bytes((payload[0] ^ 1,)) + payload[1:]
                if mode == 'directory':
                    actual.mkdir()
                elif mode != 'missing':
                    actual.write_bytes(payload)
                if mode == 'timeout':
                    raise subprocess.TimeoutExpired(command, 30, output=b'partial output', stderr=b'timeout diagnostic')
                return subprocess.CompletedProcess(command, 7 if mode == 'nonzero' else 0,
                    'wrong banner' if mode == 'banner' else checker.BANNER, 'probe diagnostic')

            if mode == 'success':
                checker.run_binary(Path(__file__), out, self.expected, runner=runner)
            else:
                with self.assertRaises((RuntimeError, OSError, subprocess.TimeoutExpired)):
                    checker.run_binary(Path(__file__), out, self.expected, runner=runner)
            retained = list(out.glob('run-*'))
            self.assertEqual(len(retained), 1)
            folder = retained[0]
            self.assertEqual((folder / 'expected.bin').read_bytes(), self.expected)
            filename = 'result.json' if mode == 'success' else 'failure.json'
            report = json.loads((folder / filename).read_text(encoding='utf-8'))
            self.assertEqual(report['success'], mode == 'success')
            self.assertEqual(report['actual_exists'], mode != 'missing')
            self.assertEqual(Path(report['command'][2]).resolve(), (folder / 'actual.bin').resolve())
            self.assertEqual(report['audio'], 'dummy')
            self.assertFalse(report['whole_game_complete'])
            self.assertTrue((folder / 'stdout.txt').read_text(encoding='utf-8'))
            self.assertTrue((folder / 'stderr.txt').read_text(encoding='utf-8'))
            if mode == 'directory':
                self.assertIn('actual_read_error', report)
            if mode == 'timeout':
                self.assertTrue(report['timeout'])
                self.assertEqual((folder / 'stderr.txt').read_text(encoding='utf-8'), 'timeout diagnostic')

    def test_success(self):
        self.exercise('success')

    def test_nonzero(self):
        self.exercise('nonzero')

    def test_truncated(self):
        self.exercise('truncated')

    def test_missing(self):
        self.exercise('missing')

    def test_banner(self):
        self.exercise('banner')

    def test_timeout(self):
        self.exercise('timeout')

    def test_corrupted(self):
        self.exercise('corrupted')

    def test_directory(self):
        self.exercise('directory')


if __name__ == '__main__':
    unittest.main()
