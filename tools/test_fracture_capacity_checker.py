"""Complete-pool native contracts and strict raw checker negative controls."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_monster_object_seeder as checker
from check_fracture_capacity import FIXTURE
from check_fracture_retirement import FIXTURE as RETIREMENT

DEBRIS_AT = 5952
COLLAPSE_AT = DEBRIS_AT + 1402 * 11
ACTORS_AT = COLLAPSE_AT + 251 * 15


class CapacityTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def cases(self):
        _, raw, _ = checker.fixtures(self.root, FIXTURE)
        for index in range(FIXTURE.cases):
            at = 16 + index * FIXTURE.record_bytes
            yield raw[at:at + 26727], raw[at + 26727:at + 53448]

    def test_pins_extent_and_full_physical_banks(self):
        packed, raw, expected = checker.fixtures(self.root, FIXTURE)
        self.assertEqual((len(packed), len(raw), len(expected)), (207262, 5131024, 2565232))
        self.assertEqual(checker.sha(expected), FIXTURE.output_sha)
        self.assertEqual(ACTORS_AT + 1575 + 7, 26721)

    def test_existing_live_fragments_and_both_capacity_guards_survive(self):
        for before, after in self.cases():
            count = struct.unpack_from('<H', before, 10)[0]
            self.assertEqual(before[DEBRIS_AT + 6:DEBRIS_AT + 6 + count * 11], after[DEBRIS_AT:DEBRIS_AT + count * 11])
            self.assertEqual(before[COLLAPSE_AT - 5:COLLAPSE_AT + 6], after[COLLAPSE_AT - 11:COLLAPSE_AT])
            self.assertEqual(before[ACTORS_AT - 9:ACTORS_AT + 6], after[ACTORS_AT - 15:ACTORS_AT])

    def test_admission_counts_at_all_debris_edges(self):
        seen, fractures = set(), 0
        for before, after in self.cases():
            incoming_debris, incoming_collapse = struct.unpack_from('<HH', before, 10)
            expected = sum(before[COLLAPSE_AT + 6 + slot * 15 + 7] == 64 for slot in range(incoming_collapse))
            debris, collapse, destroyed, fragment = struct.unpack_from('<4H', after, 4)
            self.assertEqual((debris, collapse, destroyed, fragment), (min(1401, incoming_debris + expected * 2),
                incoming_collapse - expected, expected * 2, 0x4000 + expected * 2))
            seen.add(incoming_debris); fractures += expected
        self.assertEqual(seen, {0, 1399, 1400, 1401})
        self.assertEqual(fractures, 120)

    def test_complete_actor_capacity_results(self):
        seen = set()
        for before, after in self.cases():
            initial = before[ACTORS_AT + 6 + 1570]
            count = struct.unpack_from('<H', before, 12)[0]
            fractures = sum(before[COLLAPSE_AT + 6 + slot * 15 + 7] == 64 for slot in range(count))
            self.assertEqual(after[ACTORS_AT + 1570], min(30, initial + fractures))
            self.assertEqual(after[ACTORS_AT + 1571], min(30, initial + fractures) + 2)
            self.assertEqual(before[ACTORS_AT + 6:ACTORS_AT + 6 + 38], after[ACTORS_AT:ACTORS_AT + 38])
            seen.add(initial)
        self.assertEqual(seen, {0, 30})

    def test_normal_record_compaction_updates_all_live_timers(self):
        seen = set()
        for before, after in self.cases():
            count = struct.unpack_from('<H', after, 6)[0]
            seen.add(struct.unpack_from('<H', before, 12)[0])
            for slot in range(count):
                record = after[COLLAPSE_AT + slot * 15:COLLAPSE_AT + (slot + 1) * 15]
                self.assertEqual((record[7], record[12], record[13]), (0, 0x80, 1))
        self.assertEqual(seen, {1, 2, 249, 250})

    def test_larger_compressed_allowance_is_explicit_and_bounded(self):
        self.assertEqual((RETIREMENT.packed_limit, FIXTURE.packed_limit), (128 * 1024, 256 * 1024))
        with self.assertRaisesRegex(ValueError, 'exceeds limit'):
            checker.decode_fixture(bytes(128 * 1024), RETIREMENT)
        with self.assertRaisesRegex(ValueError, 'exceeds limit'):
            checker.decode_fixture(bytes(256 * 1024), FIXTURE)
        with self.assertRaises(ValueError):
            checker.validate_format(b'LZFR0001' + struct.pack('<II', 288, 15334), FIXTURE)

    def invoke(self, root, offset=None, wrong_marker=False):
        expected = FIXTURE.output_magic + struct.pack('<II', 96, 26721) + bytes(26721 * 2)
        actual = bytearray(expected)
        if offset is not None:
            actual[16 + 26721 + offset] = 1
        exe = root / 'not-a-game-mocked-runner'
        exe.write_bytes(b'executable pin')

        def runner(args, **kwargs):
            self.assertEqual(args[1], FIXTURE.option)
            self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
            self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
            Path(args[-1]).write_bytes(actual)
            return subprocess.CompletedProcess(args, 0, RETIREMENT.app_marker if wrong_marker else FIXTURE.app_marker, b'')

        with patch.object(checker, 'fixtures', return_value=(b'packed', b'inputs', expected)), \
             patch.object(checker.subprocess, 'run', side_effect=runner):
            report, path = checker.check(root, exe, root / 'retained', FIXTURE)
        self.assertEqual((path.parent / 'actual.bin').read_bytes(), actual)
        return report

    def test_silent_runner_requires_capacity_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertTrue(self.invoke(Path(temp))['passed'])
            self.assertFalse(self.invoke(Path(temp), wrong_marker=True)['passed'])

    def test_full_pool_edges_guards_and_sound_bytes_are_compared_without_masks(self):
        with tempfile.TemporaryDirectory() as temp:
            for offset in (0, 4, 6, 8, 10, 12, 1992, DEBRIS_AT, DEBRIS_AT + 1399 * 11,
                           DEBRIS_AT + 1401 * 11, COLLAPSE_AT - 1, COLLAPSE_AT,
                           COLLAPSE_AT + 125 * 15, COLLAPSE_AT + 249 * 15,
                           COLLAPSE_AT + 250 * 15, ACTORS_AT - 1, ACTORS_AT,
                           ACTORS_AT + 1570, ACTORS_AT + 1573, 26714, 26716, 26717, 26718, 26720):
                report = self.invoke(Path(temp), offset=offset)
                self.assertFalse(report['passed'])
                self.assertFalse(report['masks_applied'])
                self.assertEqual((report['first_difference']['case'], report['first_difference']['state_offset']), (1, offset))


if __name__ == '__main__':
    unittest.main()
