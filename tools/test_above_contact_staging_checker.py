"""Above-cell staging, constructor ownership and complete-state comparison controls."""
from pathlib import Path
import struct
import tempfile
import unittest

import check_monster_object_seeder as checker
from check_above_contact_staging import FIXTURE
from check_original_debris_update import compact
import test_contact_staging_checker as contact
from test_contact_staging_checker import GUARD, body, source_contract

ABOVE_STATEMENTS = (
    'if ((record.flags & 0x80) == 0) seedAbove();',
    'if (dy > 0 && (record.flags & 0x80) == 0)',
    'record.flags |= 0x80;',
    'if (contact.word < kDamagedWordBit)',
    'queueTileDamage(contact.cell % width, contact.cell / width, 0, 1, true);')


def above_source_contract(source):
    source_contract(source)
    collapse = compact(body(source, 'updateCollapseRecords'))
    if any(collapse.count(compact(statement)) != 1 for statement in ABOVE_STATEMENTS):
        raise ValueError('above-cell seeder routing differs')


class AboveContactTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]
    invoke = contact.ContactTests.invoke

    def cases(self):
        _, raw, _ = checker.fixtures(self.root, FIXTURE)
        for index in range(96):
            at = 16 + index * FIXTURE.record_bytes
            yield raw[at:at + FIXTURE.input_bytes], raw[at + FIXTURE.input_bytes:at + FIXTURE.record_bytes]

    def test_pins_and_complete_physical_extents(self):
        packed, raw, expected = checker.fixtures(self.root, FIXTURE)
        self.assertEqual((len(packed), len(raw), len(expected)), (85120, 5131024, 2565232))
        self.assertEqual(FIXTURE.packed_limit, 128 * 1024)
        for before, after in self.cases():
            self.assertEqual(struct.unpack_from('<HH', before, 10), (0, 2))
            self.assertEqual(before[25130:25145], after[25124:25139])
            self.assertIn(before[25145 + 1570], (0, 30))

    def test_all_guard_bytes_duplicates_and_gated_tail_preservation(self):
        covered, writing, preserved = set(), 0, 0
        for index, (before, after) in enumerate(self.cases()):
            initial = before[GUARD + 6:GUARD + 17]
            if index >= 72:
                self.assertEqual(after[GUARD:GUARD + 11], initial)
                preserved += 1
                continue
            count, pattern = (index // 4) % 6 + 1, index % 4
            base = (0x1001, 0x1001, 0x4001, 0x9001)[pattern]
            words = [base + slot for slot in range(1 if pattern == 1 else count)]
            staged = b''.join(struct.pack('<H', word) for word in words)[:11]
            self.assertEqual(after[GUARD:GUARD + 11], staged + initial[len(staged):])
            covered.update(range(len(staged)))
            writing += 1
        self.assertEqual(covered, set(range(11)))
        self.assertEqual((writing, preserved), (72, 24))

    def test_above_words_seed_once_and_flagged_words_are_not_reseeded(self):
        changed, untouched = 0, 0
        for index, (before, after) in enumerate(self.cases()):
            count = (index // 4) % 6 + 1 if index < 72 else (index - 72) % 6 + 1
            for slot in range(count):
                cell = 19 * 60 + 20 + slot
                old = struct.unpack_from('<H', before, 18 + 1980 + 2 * cell)[0]
                new = struct.unpack_from('<H', after, 12 + 1980 + 2 * cell)[0]
                should_seed = index < 72 and index % 4 != 3
                self.assertEqual(new, old | 0x8000 if should_seed else old)
                changed += should_seed
                untouched += not should_seed
        self.assertEqual((changed, untouched), (189, 147))

    def test_production_seed_phases_and_flag_gates_are_bound(self):
        source = (self.root / 'src/app/app.cpp').read_text(encoding='utf-8')
        above_source_contract(source)
        original = body(source, 'updateCollapseRecords')
        for old, new in (
                ('if ((record.flags & 0x80) == 0) seedAbove();', 'seedAbove();'),
                ('dy > 0 && (record.flags & 0x80) == 0', 'dy > 0'),
                ('record.flags |= 0x80;', 'record.flags &= 0x7f;'),
                ('contact.word < kDamagedWordBit', 'contact.word <= kDamagedWordBit'),
                ('contact.cell / width, 0, 1, true', 'contact.cell / width, 0, 0, true'),
                ('scan(-width, true)', 'scan(-width)')):
            self.assertIn(old, original)
            with self.assertRaises(ValueError):
                above_source_contract(source.replace(original, original.replace(old, new, 1)))

    def test_silent_runner_and_execution_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(self.invoke(Path(directory), FIXTURE)['passed'])
            self.assertFalse(self.invoke(Path(directory), FIXTURE, bad_marker=True)['passed'])

    def test_guard_and_other_physical_state_are_not_masked(self):
        offsets = (0, 4, 6, 8, 10, 12, 1992, 5952, *range(GUARD, GUARD + 12),
                   25124, 25139, 26709, 26714, 26716, 26717, 26718, 26720)
        with tempfile.TemporaryDirectory() as directory:
            for offset in offsets:
                report = self.invoke(Path(directory), FIXTURE, offset=offset)
                self.assertFalse(report['passed'])
                self.assertFalse(report['masks_applied'])
                self.assertEqual((report['first_difference']['case'],
                                  report['first_difference']['state_offset']), (1, offset))


if __name__ == '__main__':
    unittest.main()
