"""Fixture/checker contracts; mocked runners do not establish gameplay parity."""
import gzip
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_monster_object_seeder as checker


class FixtureTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def test_native_fixture_and_complete_output_pins(self):
        packed, raw, expected = checker.fixtures(self.root)
        self.assertEqual(checker.sha(packed), checker.PACKED_SHA)
        self.assertEqual(checker.sha(raw), checker.RAW_SHA)
        self.assertEqual(len(expected), 5360784)
        self.assertEqual(checker.sha(expected), checker.OUTPUT_SHA)

    def test_fixture_uses_single_read_buffers(self):
        original = (self.root / 'LEZAC.EXE').read_bytes()
        packed = (self.root / 'tests/fixtures/monster_object_seeder_original.bin.gz').read_bytes()
        with patch.object(Path, 'read_bytes', side_effect=[original, packed]) as read:
            checker.fixtures(self.root)
        self.assertEqual(read.call_count, 2)

    def test_compressed_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, 'compressed seeder fixture hash mismatch'):
            checker.decode_fixture(b'wrong')

    def test_compressed_extent_rejected(self):
        with self.assertRaisesRegex(ValueError, 'exceeds limit'):
            checker.decode_fixture(bytes(128 * 1024))

    def test_raw_hash_rejected(self):
        packed = gzip.compress(b'wrong', mtime=0)
        with patch.object(checker, 'PACKED_SHA', checker.sha(packed)), \
             self.assertRaisesRegex(ValueError, 'decompressed seeder fixture hash mismatch'):
            checker.decode_fixture(packed)

    def test_decompression_is_bounded(self):
        packed = gzip.compress(bytes(6 * 1024**2 + 1), mtime=0)
        with patch.object(checker, 'PACKED_SHA', checker.sha(packed)), \
             self.assertRaisesRegex(ValueError, 'decompressed seeder fixture exceeds limit'):
            checker.decode_fixture(packed)

    def test_format_rejects_header_and_extent_changes(self):
        header = b'LZOS0001' + struct.pack('<II', checker.CASES, checker.RECORD_BYTES)
        for raw in (b'wrong', header[:-1], b'WRONG001' + header[8:], header,
                    b'LZOS0001' + struct.pack('<II', 0, checker.RECORD_BYTES)):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                checker.validate_format(raw)

    def test_original_pin_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'LEZAC.EXE').write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError, 'original executable hash mismatch'):
                checker.fixtures(root)


class CheckerTests(unittest.TestCase):
    expected = b'LZOT0001' + struct.pack('<II', checker.CASES, checker.STATE_BYTES) + b'state'

    def invoke(self, root, output=None, stdout=None, returncode=0, timeout=False, change_exe=False):
        exe = root / 'mock-not-executed'
        if not exe.exists():
            exe.write_bytes(b'original executable bytes')

        def runner(args, **kwargs):
            self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
            self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
            if timeout:
                raise subprocess.TimeoutExpired(args, 60, output=b'partial', stderr=b'timed out')
            Path(args[-1]).write_bytes(self.expected if output is None else output)
            if change_exe:
                exe.write_bytes(b'changed executable bytes')
            return subprocess.CompletedProcess(args, returncode,
                checker.MARKER + b'\n' if stdout is None else stdout, b'error' if returncode else b'')

        with patch.object(checker, 'fixtures', return_value=(b'packed', b'input', self.expected)), \
             patch.object(checker.subprocess, 'run', side_effect=runner):
            report, path = checker.check(root, exe, root / 'retained')
        self.assertEqual(json.loads(path.read_bytes())['passed'], report['passed'])
        return report, path

    def test_success_retained_with_executable_pins_and_dummy_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            report, path = self.invoke(Path(temp))
            self.assertTrue(report['passed'])
            self.assertEqual(report['executable_sha256_before'], report['executable_sha256_after'])
            self.assertEqual((path.parent / 'actual.bin').read_bytes(), self.expected)

    def test_difference_retained_with_precise_state_offset(self):
        with tempfile.TemporaryDirectory() as temp:
            changed = self.expected[:-1] + b'X'
            report, path = self.invoke(Path(temp), output=changed)
            self.assertFalse(report['passed'])
            self.assertEqual(report['first_difference']['case'], 0)
            self.assertEqual(report['first_difference']['state_offset'], 4)
            self.assertEqual((path.parent / 'actual.bin').read_bytes(), changed)

    def test_truncation_and_extra_output_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for output in (self.expected[:-1], self.expected + b'X'):
                report, _ = self.invoke(Path(temp), output=output)
                self.assertFalse(report['passed'])
                self.assertIsNotNone(report['first_difference'])

    def test_missing_marker_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            report, _ = self.invoke(Path(temp), stdout=b'other output')
            self.assertFalse(report['passed'])
            self.assertIn('missing seeder execution marker', report['error'])

    def test_nonzero_exit_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            report, path = self.invoke(Path(temp), returncode=1)
            self.assertFalse(report['passed'])
            self.assertEqual((path.parent / 'actual.stderr').read_bytes(), b'error')

    def test_timeout_preserves_partial_streams(self):
        with tempfile.TemporaryDirectory() as temp:
            report, path = self.invoke(Path(temp), timeout=True)
            self.assertFalse(report['passed'])
            self.assertTrue(report['timeout'])
            self.assertEqual((path.parent / 'actual.stdout').read_bytes(), b'partial')
            self.assertEqual((path.parent / 'actual.stderr').read_bytes(), b'timed out')

    def test_executable_change_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            report, _ = self.invoke(Path(temp), change_exe=True)
            self.assertFalse(report['passed'])
            self.assertIn('seeder executable changed', report['error'])

    def test_repeated_attempt_does_not_replace_previous_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, first = self.invoke(root, returncode=1)
            retained = first.read_bytes()
            report, second = self.invoke(root)
            self.assertTrue(report['passed'])
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), retained)


if __name__ == '__main__':
    unittest.main()
