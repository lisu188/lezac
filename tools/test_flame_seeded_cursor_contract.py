"""Regression controls for the production seeded flame cursor branch."""
from pathlib import Path
import unittest

import check_flame_contact_word as checker

SEEDED = ('} else sound_.writeSharedCursor(static_cast<uint16_t>(debris ?\n'
          '                            kDebrisRecordIndexBase + debrisQueue_.size() : collapseQueue_.size()));')


class SeededCursorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = checker.production_source()
        cls.first, cls.last = checker.function_ranges(cls.source, ['updateFlameRecords'])['updateFlameRecords']
        lines = cls.source.splitlines(keepends=True)
        cls.prefix, cls.body, cls.suffix = ''.join(lines[:cls.first - 1]), ''.join(lines[cls.first - 1:cls.last]), ''.join(lines[cls.last:])

    def check_mutation(self, old, new):
        self.assertEqual(self.body.count(old), 1)
        changed = self.prefix + self.body.replace(old, new, 1) + self.suffix
        with self.assertRaises(ValueError):
            checker.check_source(changed)
        return changed

    def test_production_and_self_check_cover_seeded_branch(self):
        checker.check_source(self.source)
        self.assertIn(SEEDED, checker.CONTRACT)
        self.assertEqual(checker.source_self_check(self.source), 25)

    def test_missing_seeded_write_is_rejected_despite_decoys(self):
        changed = self.check_mutation(SEEDED, '}')
        for decoy in ('\n/* ' + SEEDED + ' */\n',
                      '\nvoid unrelatedSeededCursor() {\n' + SEEDED + '\n}\n'):
            with self.assertRaises(ValueError):
                checker.check_source(changed + decoy)

    def test_seeded_class_and_both_queue_addresses_are_bound(self):
        for old, new in (
            ('debris ?\n                            kDebrisRecordIndexBase', '!debris ?\n                            kDebrisRecordIndexBase'),
            ('kDebrisRecordIndexBase + debrisQueue_.size()', 'debrisQueue_.size()'),
            ('debrisQueue_.size() : collapseQueue_.size()', 'collapseQueue_.size() : debrisQueue_.size()'),
            (SEEDED, SEEDED.replace('} else ', '} '))):
            self.check_mutation(old, new)

    def test_seeded_write_precedes_cursor_consumption(self):
        statement = 'const uint16_t cursor = sound_.requestCursor();'
        self.assertEqual(self.body.count(statement), 1)
        moved = self.body.replace(statement, '', 1).replace(SEEDED, statement + '\n' + SEEDED, 1)
        with self.assertRaises(ValueError):
            checker.check_source(self.prefix + moved + self.suffix)


if __name__ == '__main__':
    unittest.main()
