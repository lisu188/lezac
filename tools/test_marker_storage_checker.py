"""Negative controls for marker fixture integrity, routing and comparisons."""
import gzip
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_marker_storage_original as checker

ROOT = Path(__file__).resolve().parents[1]


class MarkerCheckerTest(unittest.TestCase):
    def test_fixture_pins(self):
        for label, pins in checker.FIXTURES.items():
            packed = (ROOT / 'tests/fixtures/marker_storage' / (label + '.bin.gz')).read_bytes()
            self.assertEqual(checker.decode_fixture(packed, *pins), gzip.decompress(packed))
            with self.assertRaisesRegex(RuntimeError, 'compressed.*hash mismatch'):
                checker.decode_fixture(packed + b'x', *pins)
            with self.assertRaisesRegex(RuntimeError, 'decompressed.*hash mismatch'):
                checker.decode_fixture(packed, pins[0], '0' * 64)

    def test_decompression_limit(self):
        raw = b'x' * 100
        packed = gzip.compress(raw, mtime=0)
        with self.assertRaisesRegex(RuntimeError, 'decompressed.*exceeds limit'):
            checker.decode_fixture(packed, checker.sha(packed), checker.sha(raw), limit=99)
        with self.assertRaisesRegex(RuntimeError, 'compressed.*exceeds limit'):
            checker.decode_fixture(bytes(256 * 1024), '0' * 64, '0' * 64)

    def test_full_comparison_has_no_masks(self):
        raw = b'LZMO0001' + bytes(4) + bytes(checker.STATE_BYTES * 2)
        self.assertIsNone(checker.difference(raw, raw))
        for offset in (0, 12, 12 + 3, 12 + 29, 12 + 37, 12 + 1178, 12 + 1182,
                       12 + 1442, 12 + 1570, 12 + 1573, len(raw) - 1):
            mutant = bytearray(raw)
            mutant[offset] ^= 1
            with self.subTest(offset=offset):
                self.assertEqual(checker.difference(mutant, raw)['output_offset'], offset)
        self.assertIsNotNone(checker.difference(raw[:-1], raw))
        self.assertIsNotNone(checker.difference(raw + b'x', raw))

    def test_source_routing_controls(self):
        source = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
        checker.check_routing(source)
        tokens = (
            'spawnLaunchPadMarker(static_cast<int>(player.x), localY);',
            'actorSlots_.disableAnimation(marker.actorOrder);',
            'marker.animation = actorSlots_.activeAnimation(marker.actorOrder);',
            'actorSlots_.setActiveAnimation(marker.actorOrder, marker.animation);',
            'spawnPortalMarker(x, y);',
            'actorSlots_.writeMarker(marker.actorOrder, marker, advanced, descriptor);',
            'case SharedActorKind::Marker: updateLaunchPadMarkers(entry.order); break;',
            'spawnLaunchPadMarker(position.x, position.y);',
            'spawnPortalMarker(position.x, position.y);',
            'app.debugMarkerStorageOriginal(argv[2], argv[3]);',
        )
        for token in tokens:
            with self.subTest(token=token):
                self.assertEqual(source.count(token), 1)
                with self.assertRaises(RuntimeError):
                    checker.check_routing(source.replace(token, '/* missing marker route */'))
        start = source.index('    void debugMarkerStorageOriginal(')
        end = source.index('    void debugProductionActorLifecycle(', start)
        diagnostic = source[start:end]
        for old, new in (
            ('legacyActorSeedsEnabled_ = false;', 'legacyActorSeedsEnabled_ = true;'),
            ('updateOrderedActors(0);', '/* bypass dispatcher */'),
            ('actorSlots_.restoreForFixture(state, orders);', '/* bypass seed */'),
        ):
            self.assertEqual(diagnostic.count(old), 1)
            with self.assertRaises(RuntimeError):
                checker.check_routing(source[:start] + diagnostic.replace(old, new) + source[end:])
        for name in ('spawnLaunchPadMarker', 'spawnPortalMarker'):
            start = source.index('    void ' + name + '(')
            at = source.index('        LaunchPadMarker marker;', start)
            mutant = source[:at] + '        if (sharedActorCount() >= 30) return;\n' + source[at:]
            with self.assertRaises(RuntimeError):
                checker.check_routing(mutant)
        retirement = '(!onlyOrder || marker.actorOrder == onlyOrder) && marker.timer == 0'
        self.assertEqual(source.count(retirement), 2)
        for count in (1, 2):
            with self.assertRaises(RuntimeError):
                checker.check_routing(source.replace(retirement, 'marker.timer == 0', count))

    def test_mocked_execution_contract(self):
        expected = gzip.decompress((ROOT / 'tests/fixtures/marker_storage/expected.bin.gz').read_bytes())
        for app, mode in ((False, 'ok'), (True, 'ok'), (True, 'wrong-marker'), (False, 'nonzero'),
                          (False, 'mismatch'), (False, 'truncated'), (False, 'missing'), (False, 'timeout')):
            with self.subTest(app=app, mode=mode), tempfile.TemporaryDirectory(prefix='marker-checker-contract-') as tmp:
                directory = Path(tmp)
                exe = directory / 'mock-executable'
                exe.write_bytes(b'not a game binary; mocked subprocess only')

                def execute(args, **kwargs):
                    self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
                    self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
                    self.assertEqual('--debug-marker-storage-original' in args, app)
                    if mode == 'timeout':
                        raise subprocess.TimeoutExpired(args, 30, output=b'timeout evidence', stderr=b'error evidence')
                    actual = expected
                    if mode == 'mismatch':
                        actual = expected[:49] + bytes((expected[49] ^ 1,)) + expected[50:]
                    if mode == 'truncated':
                        actual = expected[:-1]
                    if mode != 'missing':
                        Path(args[-1]).write_bytes(actual)
                    stdout = (b'marker_storage_original_app=ok operations=1008 seeds=44 updates=644 launches=160 portals=160 '
                        b'legacy_adoptions=0 legacy_retirements=0 seeded=1 natural_route=0 whole_game_claim=0\n') if app \
                        else b'marker_storage_probe=ok operations=1008\n'
                    if mode == 'wrong-marker':
                        stdout = b'generic success\n'
                    return subprocess.CompletedProcess(args, int(mode == 'nonzero'), stdout, b'')

                with patch.object(checker.subprocess, 'run', side_effect=execute):
                    report, path = checker.check(ROOT, exe, directory / 'out', app)
                self.assertEqual(report['passed'], mode == 'ok')
                self.assertTrue(path.is_file())
                self.assertFalse(report['masks_applied'])
                self.assertFalse(report['natural_route'])
                self.assertFalse(report['whole_game_claim'])
                self.assertTrue(report['constructor_tails_only'])
                self.assertFalse(report['input_gate_and_sound_prefix_executed'])
                self.assertTrue((path.parent / 'actual.stdout').is_file())
                if mode == 'timeout':
                    self.assertTrue(report['timeout'])
                    self.assertEqual((path.parent / 'actual.stderr').read_bytes(), b'error evidence')


if __name__ == '__main__':
    unittest.main()
