"""Frozen clock-phase cases, production order and failure-report preservation."""
import contextlib
import gzip
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import capture_original_debris_wrap as wrap
import check_original_debris_phase as checker


class DebrisPhaseTests(unittest.TestCase):
    def test_fixture_gzip_is_platform_independent(self):
        frozen = checker.FIXTURE.read_bytes()
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb', filename='', mtime=0) as destination:
            destination.write(gzip.decompress(frozen))
        self.assertEqual(frozen, buffer.getvalue())
        self.assertEqual((frozen[3], frozen[4:8], frozen[9]), (0, bytes(4), 255))

    def test_frozen_domain_and_late_phase_counterexamples(self):
        cases = checker.read_cases()
        differences = 0
        for incoming, expected in cases:
            tick = struct.unpack_from('<H', incoming, 4)[0]
            count = struct.unpack_from('<H', incoming, 10)[0]
            after = struct.unpack_from('<H', expected)[0]
            self.assertEqual(after, (tick + 1) & 65535)
            glyph = expected[10 + 3 * 256 + (count - 1) * 11 + 9]
            differences += glyph != (0x76 if ((tick + 199 + count) & 65535) % 6 > 2 else 0x70)
        self.assertEqual((len(cases), differences), (360, 127))

    def test_source_order_and_consumer_mutations(self):
        source = (checker.ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
        checker.contract(source)
        changes = (('updateWithControls(FrameControls{}, 0.0f);', 'updateDebrisRecords();'),
            ('++logicTick_;\n        prepareHudObjectives();', 'prepareHudObjectives();'),
            ('updateFlashes();\n        updateCameraShake();', 'updateFlashes(); ++logicTick_;\n        updateCameraShake();'),
            ('if (debrisClockPhase) appendWord(result, static_cast<uint16_t>(logicTick_));', ''))
        for before, after in changes:
            with self.subTest(before=before), self.assertRaises(ValueError):
                self.assertIn(before, source)
                checker.contract(source.replace(before, after))

    def test_comparator_rejects_changed_or_truncated_output(self):
        checker.compare(b'abc', b'abc')
        for value in (b'abd', b'ab', b'abcd', b''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                checker.compare(value, b'abc')

    def test_fixture_and_metadata_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'changed'
            for name in ('META', 'FIXTURE'):
                raw = getattr(checker, name).read_bytes()
                path.write_bytes(bytes((raw[0] ^ 1,)) + raw[1:])
                with self.subTest(name=name), mock.patch.object(checker, name, path), self.assertRaises(ValueError):
                    checker.read_cases()

    def test_capture_destination_guards_preserve_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, metadata = root / 'capture', root / 'metadata'
            with self.assertRaises(ValueError):
                wrap.validate_destinations(target, target)
            target.write_bytes(b'preserve')
            with self.assertRaises(ValueError):
                wrap.validate_destinations(target, metadata)
            self.assertEqual(target.read_bytes(), b'preserve')
            self.assertFalse(metadata.exists())

    def test_missing_input_retains_a_failed_report(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'out'
            out.mkdir()
            with mock.patch.object(checker, 'META', Path(directory) / 'missing'), \
                    mock.patch.object(checker.tempfile, 'mkdtemp', return_value=str(out)), \
                    mock.patch('sys.argv', ['checker', '--oracle-only']), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                checker.main()
            report = json.loads((out / 'report.json').read_bytes())
            self.assertEqual((report['status'], report['phase']), ('failed', 'authenticate'))
            self.assertIn('FileNotFoundError', report['error'])


if __name__ == '__main__':
    unittest.main()
