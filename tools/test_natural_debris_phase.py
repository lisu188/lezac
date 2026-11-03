"""Natural original debris clock continuity and phase-sensitive landing witnesses."""
import copy
import unittest

import natural_level2 as level2


class NaturalDebrisPhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = level2.fixture()

    def changed_pair(self, tick):
        rows = list(self.rows)
        at = 1 + 2 * (tick - level2.FIRST_TICK)
        rows[at:at + 2] = copy.deepcopy(rows[at:at + 2])
        return rows, rows[at], rows[at + 1]

    def test_four_original_phase_sensitive_landings(self):
        witnesses = level2.landing_phase_witnesses(self.rows)
        self.assertEqual([(row['tick'], row['frame'], row['slot']) for row in witnesses],
                         list(level2.LANDING_PHASE_ANCHORS))
        self.assertTrue(all(row['current_remainder'] == 3 and row['previous_remainder'] == 2 for row in witnesses))
        self.assertEqual(sum(len(row['tables']['debris']) for row in self.rows[1:-1]), 6050)

    def test_counter_mutations_at_both_boundaries(self):
        for tick, unused_frame, unused_slot in level2.LANDING_PHASE_ANCHORS:
            for boundary in ('present', 'post_update'):
                rows, before, after = self.changed_pair(tick)
                (before if boundary == 'present' else after)['mapped']['frame'] -= 1
                with self.subTest(tick=tick, boundary=boundary), self.assertRaises(ValueError):
                    level2.landing_phase_witnesses(rows)

    def test_landing_field_mutations(self):
        for tick, unused_frame, slot in level2.LANDING_PHASE_ANCHORS:
            for boundary, field, value in (('present', 7, 0x66), ('present', 3, 0x3c),
                    ('post_update', 7, 0x75), ('post_update', 1, 0)):
                rows, before, after = self.changed_pair(tick)
                (before if boundary == 'present' else after)['tables']['debris'][slot - 200][field] = value
                with self.subTest(tick=tick, boundary=boundary, field=field), self.assertRaises(ValueError):
                    level2.landing_phase_witnesses(rows)

    def test_phase_extent_and_slot_mutations(self):
        for mutation in ('missing_boundary', 'wrong_phase', 'wrong_tick', 'wrong_bound', 'shifted_slot'):
            rows, before, after = self.changed_pair(992)
            if mutation == 'missing_boundary':
                rows.pop()
            elif mutation == 'wrong_phase':
                after['phase'] = 'present'
            elif mutation == 'wrong_tick':
                after['tick'] += 1
            elif mutation == 'wrong_bound':
                after['tables']['last_live_debris'] -= 1
            else:
                for row in (before, after):
                    row['tables']['debris'].insert(0, [0] * 9)
                    row['tables']['last_live_debris'] += 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                level2.landing_phase_witnesses(rows)

    def test_fixture_is_unchanged(self):
        self.assertEqual(level2.fidelity.sha256(level2.FIXTURE / 'reference.jsonl.gz'), level2.REFERENCE_SHA256)
        self.assertEqual(level2.fidelity.sha256(level2.FIXTURE / 'route.txt'), level2.ROUTE_SHA256)
        self.assertEqual(level2.fixture(), self.rows)


if __name__ == '__main__':
    unittest.main()
