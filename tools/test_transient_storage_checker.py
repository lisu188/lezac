"""Fail-closed and failure-retention checks for original transient comparison."""
import gzip
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_transient_storage_original as checker


class TransientCheckerTest(unittest.TestCase):
    def test_fixture_hashes_and_size(self):
        raw = b'original state'
        packed = gzip.compress(raw, mtime=0)
        self.assertEqual(checker.decode_fixture(packed, checker.sha(packed), checker.sha(raw)), raw)
        for compressed_sha, raw_sha, limit in (('0' * 64, checker.sha(raw), 100),
                                               (checker.sha(packed), '0' * 64, 100),
                                               (checker.sha(packed), checker.sha(raw), 2)):
            with self.assertRaises(RuntimeError):
                checker.decode_fixture(packed, compressed_sha, raw_sha, limit)
        with self.assertRaises(RuntimeError):
            checker.decode_fixture(bytes(65536), '', '')

    def test_every_physical_area_and_extent(self):
        expected = bytes(12 + 1575 * 2)
        self.assertIsNone(checker.difference(expected, expected))
        for offset, area in ((0, 'header'), (12, 'actors'), (12 + 1178, 'visuals'),
                             (12 + 1442, 'links'), (12 + 1570, 'scalars'), (12 + 1575, 'actors')):
            actual = bytearray(expected)
            actual[offset] = 1
            result = checker.difference(bytes(actual), expected)
            self.assertEqual(result['output_offset'], offset)
            self.assertEqual(result['area'], area)
        self.assertIsNotNone(checker.difference(expected[:-1], expected))
        self.assertIsNotNone(checker.difference(expected + b'\0', expected))

    def test_timeout_retains_partial_output(self):
        with tempfile.TemporaryDirectory() as name:
            actual = Path(name) / 'actual.bin'
            actual.write_bytes(b'partial physical state')
            row = {}
            failure = subprocess.TimeoutExpired(['probe'], 30, output=b'partial log', stderr=b'partial error')
            with patch.object(checker.subprocess, 'run', side_effect=failure):
                with self.assertRaises(subprocess.TimeoutExpired):
                    checker.run_capture(Path('probe'), Path('requests'), actual, False, row)
            self.assertTrue(row['timeout'])
            self.assertEqual(actual.read_bytes(), b'partial physical state')
            self.assertEqual(actual.with_suffix('.stdout').read_bytes(), b'partial log')
            self.assertEqual(actual.with_suffix('.stderr').read_bytes(), b'partial error')

    def test_exit_and_marker_fail_closed_and_silent(self):
        with tempfile.TemporaryDirectory() as name:
            actual = Path(name) / 'actual.bin'
            for code, stdout in ((1, b'transient_storage_probe=ok operations=256\n'), (0, b'wrong marker\n')):
                result = subprocess.CompletedProcess(['probe'], code, stdout, b'error')
                with patch.object(checker.subprocess, 'run', return_value=result) as run:
                    with self.assertRaises(RuntimeError):
                        checker.run_capture(Path('probe'), Path('requests'), actual, False, {})
                self.assertEqual(run.call_args.kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
                self.assertEqual(actual.with_suffix('.stdout').read_bytes(), stdout)
                self.assertEqual(actual.with_suffix('.stderr').read_bytes(), b'error')


if __name__ == '__main__':
    unittest.main()
