"""Negative controls for full reward fixture integrity, routing and execution."""
import gzip
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_reward_storage_original as checker

ROOT = Path(__file__).resolve().parents[1]


class RewardCheckerTest(unittest.TestCase):
    def test_fixture_integrity_and_limits(self):
        for label, pins in checker.FIXTURES.items():
            packed = (ROOT / 'tests/fixtures/reward_storage' / (label + '.bin.gz')).read_bytes()
            self.assertEqual(checker.decode_fixture(packed, *pins), gzip.decompress(packed))
            with self.assertRaisesRegex(RuntimeError, 'compressed.*hash mismatch'):
                checker.decode_fixture(packed + b'x', *pins)
            with self.assertRaisesRegex(RuntimeError, 'decompressed.*hash mismatch'):
                checker.decode_fixture(packed, pins[0], '0' * 64)
            with self.assertRaisesRegex(RuntimeError, 'decompressed.*exceeds limit'):
                checker.decode_fixture(packed, *pins, limit=10)
        with self.assertRaisesRegex(RuntimeError, 'compressed.*exceeds limit'):
            checker.decode_fixture(bytes(256 * 1024), '0' * 64, '0' * 64)

    def test_unmasked_comparison(self):
        raw = b'LZRO0001' + bytes(4) + bytes(checker.STATE_BYTES * 2)
        self.assertIsNone(checker.difference(raw, raw))
        for offset in (0, 12, 12 + 3, 12 + 29, 12 + 37, 12 + 1178, 12 + 1182,
                       12 + 1442, 12 + 1570, 12 + 1573, 12 + 1575, 12 + 1579,
                       12 + 1581, 12 + 1583, len(raw) - 1):
            changed = bytearray(raw); changed[offset] ^= 1
            self.assertEqual(checker.difference(changed, raw)['output_offset'], offset)
        self.assertIsNotNone(checker.difference(raw[:-1], raw))
        self.assertIsNotNone(checker.difference(raw + b'!', raw))

    def test_source_routing(self):
        source = (ROOT / 'src/app/app.cpp').read_text(encoding='utf-8')
        models = (ROOT / 'src/gameplay/actor_models.hpp').read_text(encoding='utf-8')
        checker.check_routing(source, models)
        tokens = ('advanceBonusDrop(', 'conversionBackup(drop.actorOrder)',
            'actorSlots_.setSpriteDescriptor(drop.actorOrder, descriptor);',
            'actorSlots_.writeTransient(drop.actorOrder, step.conversion, false, {});',
            'actorSlots_.writeReward(drop.actorOrder, drop, step.animationAdvanced, descriptor);',
            'case SharedActorKind::Reward: updateBonusDrops(std::numeric_limits<size_t>::max(), entry.order); break;',
            'app.debugRewardStorageOriginal(argv[2], argv[3]);', 'reward pass changed fixture terrain')
        for token in tokens:
            self.assertEqual(source.count(token), 1)
            with self.assertRaises((RuntimeError, ValueError)):
                checker.check_routing(source.replace(token, '/* omitted reward route */'), models)
        start = source.index('    void debugRewardStorageOriginal(')
        end = source.index('    void debugCorpseRewardAnimationMode(', start)
        diagnostic = source[start:end]
        for token in ('legacyActorSeedsEnabled_ = false;', 'updateOrderedActors(0);'):
            with self.assertRaises(RuntimeError):
                checker.check_routing(source[:start] + diagnostic.replace(token, '/* omitted */') + source[end:], models)
        with self.assertRaises(RuntimeError):
            checker.check_routing(source[:start] + diagnostic.replace('updateOrderedActors(0);',
                'actorSlots_.restoreForFixture(seed.storage, orders); updateOrderedActors(0);') + source[end:], models)
        for token in ('drop.animation.advance(backup)', 'motion(x, y, drop.vx8'):
            with self.assertRaises((RuntimeError, ValueError)):
                checker.check_routing(source, models.replace(token, '/* missing reward phase */'))

    def test_mocked_execution_contract(self):
        expected = gzip.decompress((ROOT / 'tests/fixtures/reward_storage/expected.bin.gz').read_bytes())
        for app, mode in ((False, 'ok'), (True, 'ok'), (True, 'wrong-marker'), (False, 'nonzero'),
                          (False, 'mismatch'), (False, 'truncated'), (False, 'missing'), (False, 'timeout'), (False, 'changed-exe')):
            with self.subTest(app=app, mode=mode), tempfile.TemporaryDirectory(prefix='reward-checker-contract-') as tmp:
                directory = Path(tmp)
                exe = directory / 'mock-executable'; exe.write_bytes(b'mocked subprocess only')

                def execute(args, **kwargs):
                    self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
                    self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
                    self.assertEqual('--debug-reward-storage-original' in args, app)
                    if mode == 'timeout':
                        raise subprocess.TimeoutExpired(args, 30, output=b'timeout evidence', stderr=b'error evidence')
                    actual = expected
                    if mode == 'mismatch': actual = expected[:49] + bytes((expected[49] ^ 1,)) + expected[50:]
                    if mode == 'truncated': actual = expected[:-1]
                    if mode != 'missing': Path(args[-1]).write_bytes(actual)
                    if mode == 'changed-exe': exe.write_bytes(b'changed executable')
                    stdout = (b'reward_storage_original_app=ok operations=4982 seeds=87 updates=4895 '
                        b'legacy_adoptions=0 legacy_retirements=0 seeded=1 natural_route=0 whole_game_claim=0\n') if app \
                        else b'reward_storage_probe=ok operations=4982\n'
                    if mode == 'wrong-marker': stdout = b'generic success\n'
                    return subprocess.CompletedProcess(args, int(mode == 'nonzero'), stdout, b'')

                with patch.object(checker.subprocess, 'run', side_effect=execute):
                    report, path = checker.check(ROOT, exe, directory / 'out', app)
                self.assertEqual(report['passed'], mode == 'ok')
                self.assertTrue(path.is_file())
                for flag in ('masks_applied', 'natural_route', 'whole_game_claim', 'full_raw_record_owner',
                             'player_updates_executed', 'pending_bonus_application_executed', 'constructors_executed'):
                    self.assertFalse(report[flag])
                self.assertTrue((path.parent / 'actual.stdout').is_file())
                if mode == 'timeout':
                    self.assertTrue(report['timeout'])
                    self.assertEqual((path.parent / 'actual.stderr').read_bytes(), b'error evidence')


if __name__ == '__main__':
    unittest.main()
