"""Strict prior-phase fixture, CLI routing and raw comparison regressions."""
from pathlib import Path
import struct
import tempfile
import unittest

import check_monster_object_seeder as checker
from check_damage_lane_history import FIXTURE
from check_original_debris_update import compact
from test_contact_staging_checker import body
import test_contact_staging_checker as contact
from test_debris_contact_pools_checker import direct_source_contract


def source_contract(source):
    direct_source_contract(source)
    diagnostic = compact(body(source, 'debugOriginalDebrisUpdate'))
    ingest = compact('if (laneHistory) { const auto history = take(3); '
        'damageLaneData_[0x661e] = history[0]; damageLaneData_[0x0a06] = history[1]; '
        'damageLaneData_[0x0a07] = history[2]; }')
    if diagnostic.count(ingest) != 1:
        raise ValueError('history input routing differs')
    if diagnostic.index(ingest) > diagnostic.index(compact('if (fractureStorage && !collapseLaneHistory) take(fractureStateBytes);')):
        raise ValueError('history input not consumed before expected bytes')
    cli = compact('if (argc > 3 && std::string(argv[1]) == "--debug-original-damage-lane-history") {'
        'app.debugOriginalDebrisUpdate(argv[2], argv[3], true, false, false, true, true, true); return 0; }')
    if compact(source).count(cli) != 1 or source.count('"--debug-original-damage-lane-history"') != 1:
        raise ValueError('history CLI routing differs')


class HistoryTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]
    invoke = contact.ContactTests.invoke

    def test_pins_and_extents(self):
        packed, raw, expected = checker.fixtures(self.root, FIXTURE)
        self.assertEqual(len(packed), 709630)
        self.assertEqual(len(raw), 16 + 112 * 53454)
        self.assertEqual(len(expected), 16 + 112 * 26724)
        self.assertEqual(checker.sha(expected), FIXTURE.output_sha)

    def test_prior_phase_and_low_data(self):
        _, raw, _ = checker.fixtures(self.root, FIXTURE)
        variants = set()
        for case in range(112):
            at = 16 + case * FIXTURE.record_bytes
            before = raw[at:at + FIXTURE.input_bytes]
            after = raw[at + FIXTURE.input_bytes:at + FIXTURE.record_bytes]
            self.assertEqual(before[-2:], bytes((0x5a, 0xa5)))
            if case >= 96:
                variants.add((case - 96) // 4)
                self.assertIn(before[-3], (156, 255, 1, 100))
                self.assertEqual(after[-3], before[-3])
                self.assertEqual(struct.unpack_from('<H', after, 26714)[0], 0x3e21)
                self.assertEqual(after[-2], 0x5a)
                self.assertNotEqual(after[-1], 0xa5)
        self.assertEqual(variants, {0, 1, 2, 3})

    def test_production_routing_and_expected_skip(self):
        source = (self.root / 'src/app/app.cpp').read_text(encoding='utf-8')
        source_contract(source)
        for old, new in (
            ('damageLaneData_[0x661e] = history[0];', ''),
            ('damageLaneData_[0x0a06] = history[1];', ''),
            ('damageLaneData_[0x0a07] = history[2];', ''),
            ('--debug-original-damage-lane-history', '--debug-other-history')):
            self.assertEqual(source.count(old), 1)
            with self.subTest(mutation=old), self.assertRaises(ValueError):
                source_contract(source.replace(old, new, 1))

    def test_all_history_and_physical_state_bytes_are_compared(self):
        with tempfile.TemporaryDirectory() as directory:
            for offset in (0, 4, 6, 21357, 26714, 26715, 26721, 26722, 26723):
                report = self.invoke(Path(directory), FIXTURE, offset=offset)
                self.assertFalse(report['passed'])
                self.assertFalse(report['masks_applied'])
                self.assertEqual(report['first_difference']['state_offset'], offset)

    def test_silent_runner_and_execution_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(self.invoke(Path(directory), FIXTURE)['passed'])
            self.assertFalse(self.invoke(Path(directory), FIXTURE, bad_marker=True)['passed'])


if __name__ == '__main__':
    unittest.main()
