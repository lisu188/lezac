"""Native fracture contracts and checker negative controls, not App acceptance."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_monster_object_seeder as checker
from check_fracture_retirement import FIXTURE


class FractureTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def cases(self):
        _, raw, _ = checker.fixtures(self.root, FIXTURE)
        for index in range(FIXTURE.cases):
            at = 16 + index * FIXTURE.record_bytes
            yield raw[at:at + 7670], raw[at + 7670:at + 15334]

    def test_native_pins_and_complete_state(self):
        packed, raw, expected = checker.fixtures(self.root, FIXTURE)
        self.assertEqual((len(packed), len(raw), len(expected)), (120593, 4416208, 2207248))
        self.assertEqual(checker.sha(expected), FIXTURE.output_sha)

    def test_fracture_changes_only_early_fields_in_single_retired_record(self):
        seen = set()
        singles = 0
        for before, after in self.cases():
            if struct.unpack_from('<H', before, 12)[0] != 1:
                continue
            incoming, outgoing = before[6013:6028], after[6007:6022]
            self.assertEqual(outgoing[:12], incoming[:12])
            self.assertEqual(outgoing[14:], incoming[14:])
            self.assertEqual(outgoing[12], 0x80)
            self.assertEqual(outgoing[13], (incoming[13] + 1) & 255)
            self.assertEqual(struct.unpack_from('<H', after, 6)[0], 0)
            seen.add((incoming[12], incoming[13]))
            singles += 1
        self.assertEqual(singles, 72)
        self.assertEqual(seen, {(flags, timer) for flags in (0, 0x83) for timer in (0, 94, 255)})

    def test_compaction_counts_and_debris_creation(self):
        fractures = 0
        for before, after in self.cases():
            count = struct.unpack_from('<H', before, 12)[0]
            expected = sum(before[6013 + slot * 15 + 7] == 64 for slot in range(count))
            self.assertEqual(struct.unpack_from('<4H', after, 4),
                (expected * 2, count - expected, expected * 2, 0x4000 + expected * 2))
            fractures += expected
        self.assertEqual(fractures, 360)

    def test_complete_actor_bank_capacity_and_shared_result(self):
        admissions = set()
        for before, after in self.cases():
            count = struct.unpack_from('<H', before, 12)[0]
            fractures = sum(before[6013 + slot * 15 + 7] == 64 for slot in range(count))
            initial = before[6088 + 1570]
            final = after[6082 + 1570]
            self.assertEqual(final, min(30, initial + fractures))
            self.assertEqual(after[6082 + 1571], final + 2)
            self.assertEqual(before[6088:6088 + 38], after[6082:6082 + 38])
            admissions.add((initial, final - initial))
            success = struct.unpack_from('<H', after, 6082 + 1573)[0]
            self.assertEqual(success, int(initial + fractures <= 30) if before[6013 + 7] == 64 else 0)
        self.assertTrue({(0, 1), (0, 2), (29, 1), (30, 0)} <= admissions)

    def test_untouched_physical_tails_and_links_are_unmasked(self):
        for before, after in self.cases():
            self.assertEqual(before[6013 + 45:6088], after[6007 + 45:6082])
            self.assertEqual(before[5958 + 44:6013], after[5952 + 44:6007])
            self.assertEqual(before[6088 + 1442:6088 + 1570], after[6082 + 1442:6082 + 1570])

    def test_sound_priority_acceptance_and_rejection(self):
        priorities = set()
        for before, after in self.cases():
            priority = before[-4]
            priorities.add(priority)
            self.assertEqual(after[-4], 3 if priority == 0 else 5)
            self.assertEqual(after[-3:-1], struct.pack('<H', 0xea74 if priority == 0 else 0xbeef))
            self.assertEqual(after[-1], 1)
        self.assertEqual(priorities, {0, 5})

    def test_source_commits_only_early_fields_before_fracture(self):
        source = (self.root / 'src/app/app.cpp').read_text(encoding='utf-8')
        body = source[source.index('    void updateCollapseRecords() {'):source.index('    void updateFlashes() {')]
        fracture = body.index('if (fracture)')
        for statement in ('collapseQueue_[slot].flags = record.flags;',
                          'collapseQueue_[slot].restTicks = record.restTicks;',
                          'sound_.writeSharedCursor(static_cast<uint16_t>(magnitude));',
                          'actorSlots_.setSharedResult('):
            self.assertIn(statement, body[:fracture])
        commit = body.index('collapseQueue_[slot] = record;')
        self.assertGreater(commit, fracture)
        self.assertIn('if (!fracture)', body[fracture:commit])

    def invoke(self, root, offset=None, wrong_marker=False):
        expected = FIXTURE.output_magic + struct.pack('<II', 288, 7664) + bytes(7664 * 2)
        actual = bytearray(expected)
        if offset is not None:
            actual[16 + 7664 + offset] = 1
        exe = root / 'not-a-game-mocked-runner'
        exe.write_bytes(b'executable pin')

        def runner(args, **kwargs):
            self.assertEqual(args[1], FIXTURE.option)
            self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
            self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
            Path(args[-1]).write_bytes(actual)
            return subprocess.CompletedProcess(args, 0, checker.MARKER if wrong_marker else FIXTURE.app_marker, b'')

        with patch.object(checker, 'fixtures', return_value=(b'packed', b'inputs', expected)), \
             patch.object(checker.subprocess, 'run', side_effect=runner):
            report, path = checker.check(root, exe, root / 'retained', FIXTURE)
        self.assertEqual((path.parent / 'actual.bin').read_bytes(), actual)
        return report

    def test_silent_runner_success_requires_fracture_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertTrue(self.invoke(Path(temp))['passed'])
            self.assertFalse(self.invoke(Path(temp), wrong_marker=True)['passed'])

    def test_each_output_bank_and_shared_field_is_compared_without_masks(self):
        with tempfile.TemporaryDirectory() as temp:
            for offset in (0, 4, 6, 8, 10, 12, 1992, 5952, 6006, 6007, 6019, 6020, 6081,
                           6082, 6120, 7260, 7524, 7652, 7653, 7654, 7655, 7656, 7657, 7659, 7660, 7661, 7663):
                report = self.invoke(Path(temp), offset=offset)
                self.assertFalse(report['passed'])
                self.assertFalse(report['masks_applied'])
                self.assertEqual((report['first_difference']['case'], report['first_difference']['state_offset']), (1, offset))

    def test_wrong_fixture_pin_and_protocol_are_rejected(self):
        with self.assertRaises(ValueError):
            checker.decode_fixture(b'wrong', FIXTURE)
        with self.assertRaises(ValueError):
            checker.validate_format(b'LZRT0001' + struct.pack('<II', 176, 12060), FIXTURE)


if __name__ == '__main__':
    unittest.main()
