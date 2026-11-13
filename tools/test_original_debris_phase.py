"""Frozen clock-phase cases, production order and failure-report preservation."""
import contextlib
import gzip
import io
import json
from gameplay_source import gameplay_source_text
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import capture_original_debris_wrap as wrap
import check_original_debris_phase as checker


def recompress(raw, compresslevel=9):
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb', filename='', mtime=0, compresslevel=compresslevel) as destination:
        destination.write(raw)
    return buffer.getvalue()


class DebrisPhaseTests(unittest.TestCase):
    def test_fixture_gzip_metadata_and_lossless_recompression(self):
        frozen = checker.FIXTURE.read_bytes()
        raw = gzip.decompress(frozen)
        metadata = json.loads(checker.META.read_bytes())
        self.assertEqual(checker.sha(frozen), metadata['fixture_sha256'])
        self.assertEqual((len(raw), checker.sha(raw)), (metadata['decoded_bytes'], metadata['decoded_sha256']))
        self.assertEqual(frozen[:10], bytes.fromhex('1f8b08000000000002ff'))
        # DEFLATE encoding can vary across runtimes; the frozen evidence may not.
        encoded = recompress(raw)
        self.assertEqual(encoded, recompress(raw))
        self.assertEqual(encoded[:10], frozen[:10])
        self.assertEqual(encoded[-8:], frozen[-8:])
        self.assertEqual(gzip.decompress(encoded), raw)

    def test_level_six_does_not_reproduce_frozen_fixture(self):
        frozen = checker.FIXTURE.read_bytes()
        encoded = recompress(gzip.decompress(frozen), compresslevel=6)
        self.assertNotEqual(frozen, encoded)
        self.assertEqual(gzip.decompress(frozen), gzip.decompress(encoded))
        self.assertEqual((frozen[8], encoded[8]), (2, 0))

    def test_lossless_reencoding_cannot_replace_frozen_evidence(self):
        frozen = checker.FIXTURE.read_bytes()
        raw = gzip.decompress(frozen)
        encoded = recompress(raw, compresslevel=0)
        self.assertNotEqual(frozen, encoded)
        self.assertEqual(gzip.decompress(encoded), raw)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'reencoded.gz'
            path.write_bytes(encoded)
            with mock.patch.object(checker, 'FIXTURE', path), self.assertRaisesRegex(ValueError, 'fixture differs'):
                checker.read_cases()

    def test_decoded_payload_hash_is_checked_after_container_hash(self):
        raw = gzip.decompress(checker.FIXTURE.read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for changed in (raw[:-1], raw + b'\0', raw[:100] + bytes((raw[100] ^ 1,)) + raw[101:]):
                encoded = recompress(changed)
                fixture, metadata = root / 'fixture.gz', root / 'metadata.json'
                fixture.write_bytes(encoded)
                value = json.loads(checker.META.read_bytes())
                value['fixture_sha256'] = checker.sha(encoded)
                metadata.write_bytes(json.dumps(value).encode('ascii'))
                with self.subTest(decoded_bytes=len(changed)), mock.patch.object(checker, 'FIXTURE', fixture), \
                        mock.patch.object(checker, 'META', metadata), \
                        mock.patch.object(checker, 'META_SHA', checker.sha(metadata.read_bytes())), \
                        self.assertRaisesRegex(ValueError, 'decoded extent differs'):
                    checker.read_cases()

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
        source = gameplay_source_text(checker.ROOT)
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
