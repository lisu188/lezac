"""Negative controls for corpse fixture integrity, production routing and execution."""
import gzip
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_corpse_storage_original as checker

ROOT = Path(__file__).resolve().parents[1]


class CorpseCheckerTest(unittest.TestCase):
    def test_fixture_integrity_and_limits(self):
        for label, pins in checker.FIXTURES.items():
            packed = (ROOT / 'tests/fixtures/corpse_storage' / (label + '.bin.gz')).read_bytes()
            self.assertEqual(checker.decode_fixture(packed, *pins), gzip.decompress(packed))
            with self.assertRaisesRegex(RuntimeError, 'compressed.*hash mismatch'):
                checker.decode_fixture(packed + b'x', *pins)
            with self.assertRaisesRegex(RuntimeError, 'decompressed.*hash mismatch'):
                checker.decode_fixture(packed, pins[0], '0' * 64)
            with self.assertRaisesRegex(RuntimeError, 'decompressed.*exceeds limit'):
                checker.decode_fixture(packed, *pins, limit=10)
        with self.assertRaisesRegex(RuntimeError, 'compressed.*exceeds limit'):
            checker.decode_fixture(bytes(512 * 1024), '0' * 64, '0' * 64)

    def test_unmasked_comparison(self):
        raw = b'LZCO0001' + bytes(4) + bytes(checker.STATE_BYTES * 2)
        self.assertIsNone(checker.difference(raw, raw))
        for at in (0, 3, 29, 37, 1178, 1182, 1442, 1570, 1573, 1575, 1579, 1581, 1583, 1585, 1586, 1588, 1589, 1590, 1592):
            offset = 12 + at
            changed = bytearray(raw); changed[offset] ^= 1
            self.assertEqual(checker.difference(changed, raw)['output_offset'], offset)
        self.assertIsNotNone(checker.difference(raw[:-1], raw))
        self.assertIsNotNone(checker.difference(raw + b'!', raw))

    def test_source_routing(self):
        source = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
        models = (ROOT / 'src/gameplay/actor_models.hpp').read_text(encoding='utf-8')
        checker.check_routing(source, models)
        for token in ('advanceCorpseMotion(monster, timer, logicTick_',
                      'actorSlots_.writeCorpse(monster.actorOrder, monster, timer, animationAdvanced,',
                      'actorSlots_.convertCorpse(monster.actorOrder, conversion, actorSpriteDescriptor(sprite));',
                      'corpse pass changed fixture terrain', 'app.debugCorpseStorageOriginal(argv[2], argv[3]);'):
            self.assertEqual(source.count(token), 1)
            with self.assertRaises((RuntimeError, ValueError)):
                checker.check_routing(source.replace(token, '/* omitted corpse route */'), models)
        start, end = source.index('    void debugCorpseStorageOriginal('), source.index('    void debugRewardStorageOriginal(')
        diagnostic = source[start:end]
        for token in ('legacyActorSeedsEnabled_ = false;', 'updateOrderedActors(0);', 'sound_.restoreLatchForFixture(seed.latch)'):
            with self.assertRaises(RuntimeError):
                checker.check_routing(source[:start] + diagnostic.replace(token, '/* omitted */') + source[end:], models)
        with self.assertRaises(RuntimeError):
            checker.check_routing(source[:start] + diagnostic.replace('updateOrderedActors(0);',
                'actorSlots_.restoreForFixture(seed.storage, orders); updateOrderedActors(0);') + source[end:], models)
        with self.assertRaises(RuntimeError):
            checker.check_routing(source, models.replace('timer == 0 || timer == 0xff', 'timer == 0'))

    def test_mocked_execution_contract(self):
        expected = gzip.decompress((ROOT / 'tests/fixtures/corpse_storage/expected.bin.gz').read_bytes())
        for app, mode in ((False, 'ok'), (True, 'ok'), (True, 'wrong-marker'), (False, 'nonzero'),
                          (False, 'mismatch'), (False, 'truncated'), (False, 'missing'), (False, 'timeout'), (False, 'changed-exe')):
            with self.subTest(app=app, mode=mode), tempfile.TemporaryDirectory(prefix='corpse-checker-contract-') as tmp:
                directory = Path(tmp)
                exe = directory / 'mock-executable'; exe.write_bytes(b'mocked subprocess only')

                def execute(args, **kwargs):
                    self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
                    self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
                    self.assertEqual('--debug-corpse-storage-original' in args, app)
                    if mode == 'timeout':
                        raise subprocess.TimeoutExpired(args, 30, output=b'timeout evidence', stderr=b'error evidence')
                    actual = expected
                    if mode == 'mismatch': actual = expected[:49] + bytes((expected[49] ^ 1,)) + expected[50:]
                    if mode == 'truncated': actual = expected[:-1]
                    if mode != 'missing': Path(args[-1]).write_bytes(actual)
                    if mode == 'changed-exe': exe.write_bytes(b'changed executable')
                    stdout = (b'corpse_storage_original_app=ok operations=3252 seeds=940 updates=2312 '
                        b'legacy_adoptions=0 legacy_retirements=0 seeded=1 natural_route=0 whole_game_claim=0\n') if app \
                        else b'corpse_storage_probe=ok operations=3252\n'
                    if mode == 'wrong-marker': stdout = b'generic success\n'
                    return subprocess.CompletedProcess(args, int(mode == 'nonzero'), stdout, b'')

                with patch.object(checker.subprocess, 'run', side_effect=execute):
                    report, path = checker.check(ROOT, exe, directory / 'out', app)
                self.assertEqual(report['passed'], mode == 'ok')
                self.assertTrue(path.is_file())
                for flag in ('masks_applied', 'natural_route', 'whole_game_claim', 'direct_reward_allocation_executed',
                             'natural_fatal_entry_executed', 'sound_interrupt_executed', 'rendered_pixels_claim'):
                    self.assertFalse(report[flag])
                self.assertTrue((path.parent / 'actual.stdout').is_file())
                if mode == 'timeout':
                    self.assertTrue(report['timeout'])
                    self.assertEqual((path.parent / 'actual.stderr').read_bytes(), b'error evidence')


if __name__ == '__main__':
    unittest.main()
