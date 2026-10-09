"""Original retirement fixture contracts, separate from actual-App acceptance."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_monster_object_seeder as checker
from check_collapse_retirement import FIXTURE


class RetirementTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def fixture_cases(self):
        _, raw, _ = checker.fixtures(self.root, FIXTURE)
        for index in range(FIXTURE.cases):
            at = 16 + index * FIXTURE.record_bytes
            yield raw[at:at + 6033], raw[at + 6033:at + 12060]

    def test_native_pins_and_complete_output(self):
        packed, raw, expected = checker.fixtures(self.root, FIXTURE)
        self.assertEqual((len(packed), len(raw), len(expected)), (7750, 2122576, 1060768))
        self.assertEqual(checker.sha(expected), FIXTURE.output_sha)

    def test_timer_equality_wrap_and_compaction_counts(self):
        removals = retired_cases = 0
        for before, after in self.fixture_cases():
            count = struct.unpack_from('<H', before, 12)[0]
            after_count = struct.unpack_from('<H', after, 6)[0]
            expected = sum(before[5958 + slot * 15 + 13] == 94 for slot in range(count))
            self.assertEqual(count - after_count, expected)
            removals += expected
            retired_cases += expected != 0
            self.assertEqual(after[:4], struct.pack('<I', 0x12345678))
            self.assertEqual(after[8:12], struct.pack('<HH', 0, 0x4000))
        self.assertEqual((removals, retired_cases), (144, 96))

    def test_inactive_slots_beyond_live_bank_are_preserved(self):
        for before, after in self.fixture_cases():
            self.assertEqual(before[-30:], after[-30:])

    def test_final_writeback_precedes_single_record_retirement(self):
        retired = 0
        for before, after in self.fixture_cases():
            if struct.unpack_from('<H', before, 12)[0] != 1:
                continue
            incoming, outgoing = before[5958:5973], after[5952:5967]
            vx = incoming[6]
            self.assertEqual(outgoing[6], max(0, vx - 1))
            self.assertEqual(outgoing[8], vx)
            self.assertEqual(outgoing[12], incoming[12] & 0xfc if vx < 30 else incoming[12])
            self.assertEqual(outgoing[13], (incoming[13] + 1) & 255)
            self.assertEqual(struct.unpack_from('<H', outgoing, 10)[0], max(0, vx - 1))
            if incoming[13] == 94:
                self.assertNotEqual(incoming, outgoing)
                self.assertEqual(struct.unpack_from('<H', after, 6)[0], 0)
                retired += 1
        self.assertEqual(retired, 16)

    def test_source_commits_normal_record_before_timer_erase(self):
        source = (self.root / 'src/app/app.cpp').read_text(encoding='utf-8')
        body = source[source.index('    void updateCollapseRecords() {'):source.index('    void updateFlashes() {')]
        commit = body.index('collapseQueue_[slot] = record;')
        remove = body.index('if (fracture || record.restTicks == 95)')
        self.assertLess(commit, remove)
        self.assertIn('if (!fracture)', body[:commit])

    def test_wrong_fixture_pin_and_protocol_are_rejected(self):
        with self.assertRaises(ValueError):
            checker.decode_fixture(b'wrong', FIXTURE)
        with self.assertRaises(ValueError):
            checker.validate_format(b'LZMG0001' + struct.pack('<II', 384, 11921), FIXTURE)

    def invoke(self, root, offset=None, wrong_marker=False):
        expected = FIXTURE.output_magic + struct.pack('<II', 176, 6027) + bytes(6027 * 2)
        actual = bytearray(expected)
        if offset is not None:
            actual[16 + 6027 + offset] = 1
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

    def test_silent_success_uses_retirement_protocol(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertTrue(self.invoke(Path(temp))['passed'])

    def test_each_state_region_and_retired_tail_is_compared_without_masks(self):
        with tempfile.TemporaryDirectory() as temp:
            for offset in (0, 4, 6, 8, 10, 12, 1992, 5952, 5958, 5960, 5962, 5964, 5965, 5997, 6026):
                report = self.invoke(Path(temp), offset=offset)
                self.assertFalse(report['passed'])
                self.assertFalse(report['masks_applied'])
                self.assertEqual(report['first_difference']['case'], 1)
                self.assertEqual(report['first_difference']['state_offset'], offset)

    def test_other_suite_marker_cannot_accept_retirement_output(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertFalse(self.invoke(Path(temp), wrong_marker=True)['passed'])


if __name__ == '__main__':
    unittest.main()
