"""Frozen rollover coverage, mutation detection and capture output safety."""
import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import capture_original_debris_wrap as producer
import check_original_debris_wrap as checker


class DebrisWrapTests(unittest.TestCase):
    def test_original_domain_and_counterexamples(self):
        cases = checker.read_cases()
        mismatches = 0
        for incoming, expected in cases:
            tick, count = struct.unpack_from('<H', incoming, 4)[0], struct.unpack_from('<H', incoming, 10)[0]
            slot = 199 + count
            glyph = expected[8 + 3 * 256 + (count - 1) * 11 + 9]
            self.assertEqual(glyph, 0x76 if ((tick + slot) & 65535) % 6 > 2 else 0x70)
            mismatches += glyph != (0x76 if (tick + slot) % 6 > 2 else 0x70)
        self.assertEqual((len(cases), mismatches), (276, 108))

    def test_comparator_rejects_changes_and_extents(self):
        checker.compare(b'abc', b'abc')
        for changed in (b'abd', b'ab', b'abcd', b''):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                checker.compare(changed, b'abc')

    def test_frozen_input_mutations_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'changed'
            for name in ('META', 'FIXTURE'):
                raw = getattr(checker, name).read_bytes()
                path.write_bytes(bytes((raw[0] ^ 1,)) + raw[1:])
                with self.subTest(name=name), mock.patch.object(checker, name, path), self.assertRaises(ValueError):
                    checker.read_cases()

    def test_fresh_capture_output_guards_preserve_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, meta = root / 'output', root / 'metadata'
            producer.validate_destinations(output, meta)
            with self.assertRaises(ValueError):
                producer.validate_destinations(output, output)
            for existing, other in ((output, meta), (meta, output)):
                existing.write_bytes(b'preserve')
                with self.assertRaises(ValueError):
                    producer.validate_destinations(output, meta)
                self.assertEqual(existing.read_bytes(), b'preserve')
                self.assertFalse(other.exists())
                existing.unlink()
            with self.assertRaises(ValueError):
                producer.validate_destinations(root / 'missing' / 'output', meta)

    def test_missing_canonical_input_retains_failure_report(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'report'
            out.mkdir()
            with mock.patch.object(checker.legacy, 'ROOT', Path(directory)), \
                    mock.patch.object(checker.tempfile, 'mkdtemp', return_value=str(out)), \
                    mock.patch('sys.argv', ['checker', '--oracle-only']), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                checker.main()
            report = json.loads((out / 'report.json').read_bytes())
            self.assertEqual((report['status'], report['phase']), ('failed', 'authenticate'))
            self.assertIn('FileNotFoundError', report['error'])


if __name__ == '__main__':
    unittest.main()
