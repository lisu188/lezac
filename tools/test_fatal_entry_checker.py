"""Exercise checker failure retention with a fake runner, not game-parity evidence."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_fatal_entry_original as checker


class CheckerTests(unittest.TestCase):
    def run_case(self, mode):
        with tempfile.TemporaryDirectory(prefix='fatal-checker-test-') as name:
            root = Path(name)
            exe = root / 'fake-executable'
            exe.write_bytes(b'checker test double only')
            expected = b'LZFO0001' + bytes(4) + bytes(checker.STATE_BYTES)

            def fake_run(args, **kwargs):
                self.assertEqual(args[1], '--debug-fatal-entry-original')
                self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
                actual = expected if mode not in ('mismatch', 'nonzero') else expected[:-1]
                Path(args[3]).write_bytes(actual)
                if mode == 'timeout':
                    raise subprocess.TimeoutExpired(args, 60, output=b'partial stdout', stderr=b'partial stderr')
                if mode == 'changed-executable':
                    exe.write_bytes(b'changed checker test double')
                stdout = b'' if mode == 'missing-marker' else checker.MARKER + b'\n'
                return subprocess.CompletedProcess(args, 7 if mode == 'nonzero' else 0, stdout, b'runner stderr')

            with patch.object(checker, 'fixtures', return_value={'requests': b'test request', 'expected': expected}), \
                 patch.object(checker.subprocess, 'run', side_effect=fake_run):
                fixtures = root / 'tests/fixtures/fatal_entry'
                fixtures.mkdir(parents=True)
                for label in checker.FIXTURES:
                    (fixtures / (label + '.bin.gz')).write_bytes(b'test packed fixture')
                report, path = checker.check(root, exe, root / 'outputs')
            self.assertEqual(report['passed'], mode == 'positive')
            self.assertEqual(json.loads(path.read_text())['passed'], report['passed'])
            output = Path(report['output_directory'])
            self.assertTrue((output / 'actual.bin').is_file())
            self.assertTrue((output / 'actual.stdout').is_file())
            self.assertTrue((output / 'actual.stderr').is_file())
            if mode in ('mismatch', 'nonzero'):
                self.assertIsNotNone(report['first_difference'])
            if mode == 'timeout':
                self.assertTrue(report['timeout'])
                self.assertEqual((output / 'actual.stderr').read_bytes(), b'partial stderr')

    def test_positive_checker_control(self):
        self.run_case('positive')

    def test_mismatch_retained(self):
        self.run_case('mismatch')

    def test_nonzero_retained(self):
        self.run_case('nonzero')

    def test_timeout_retained(self):
        self.run_case('timeout')

    def test_missing_marker_rejected(self):
        self.run_case('missing-marker')

    def test_changed_executable_rejected(self):
        self.run_case('changed-executable')


if __name__ == '__main__':
    unittest.main(verbosity=2)
