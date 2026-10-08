"""Exercise pickup checker diagnostics with mocked processes, not compiled game claims."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import check_pickup_post_init as checker


class PickupCheckerRetention(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected, cls.rows = checker.fixture()

    def exercise(self, mode):
        with tempfile.TemporaryDirectory(prefix='lezac-pickup-checker-') as tmp:
            out = Path(tmp)

            def runner(command, **kwargs):
                self.assertEqual(command[1], '--debug-original-pickup-post-init')
                self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
                self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
                self.assertEqual(kwargs['timeout'], 30)
                actual = Path(command[2])
                payload = self.expected
                if mode == 'truncated':
                    payload = payload[:-1]
                elif mode == 'extended':
                    payload += b'\0'
                elif mode == 'corrupted':
                    payload = bytes((payload[0] ^ 1,)) + payload[1:]
                if mode == 'directory':
                    actual.mkdir()
                elif mode != 'missing':
                    actual.write_bytes(payload)
                if mode == 'timeout':
                    raise subprocess.TimeoutExpired(command, 30, output=b'partial output', stderr=b'timeout diagnostic')
                if mode == 'launch':
                    raise OSError('mock launch failure')
                return subprocess.CompletedProcess(command, 7 if mode == 'nonzero' else 0,
                    'wrong banner' if mode == 'banner' else checker.BANNER, 'probe diagnostic')

            if mode == 'success':
                checker.run_binary(Path(__file__), out, self.expected, self.rows, runner=runner)
            else:
                with self.assertRaises((RuntimeError, OSError, subprocess.TimeoutExpired)):
                    checker.run_binary(Path(__file__), out, self.expected, self.rows, runner=runner)
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
            self.assertFalse(report['compiled_execution'])
            self.assertFalse(report['whole_game_complete'])
            self.assertFalse(report['natural_full_pool_pickup_reachability_proven'])
            self.assertTrue((folder / 'stdout.txt').exists())
            self.assertTrue((folder / 'stderr.txt').exists())
            if mode == 'directory':
                self.assertIn('actual_read_error', report)
            if mode == 'timeout':
                self.assertTrue(report['timeout'])
                self.assertEqual((folder / 'stderr.txt').read_text(encoding='utf-8'), 'timeout diagnostic')
            if mode == 'corrupted':
                self.assertIn('case=0', report['error'])

    def test_process_results_and_retention(self):
        for mode in ('success', 'nonzero', 'truncated', 'extended', 'missing', 'banner',
                     'timeout', 'corrupted', 'directory', 'launch'):
            with self.subTest(mode=mode):
                self.exercise(mode)

    def test_repeated_runs_preserve_prior_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix='lezac-pickup-reruns-') as tmp:
            out = Path(tmp)

            def runner(command, **kwargs):
                Path(command[2]).write_bytes(self.expected)
                return subprocess.CompletedProcess(command, 0, checker.BANNER, '')

            first = checker.run_binary(Path(__file__), out, self.expected, self.rows, runner=runner)
            before = (first / 'result.json').read_bytes()
            second = checker.run_binary(Path(__file__), out, self.expected, self.rows, runner=runner)
            self.assertNotEqual(first, second)
            self.assertEqual((first / 'result.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
