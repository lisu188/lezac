"""Direct impact routing, physical guards and strict comparison controls."""
from pathlib import Path
import struct
import tempfile
import unittest

import check_monster_object_seeder as checker
from check_debris_contact_pools import FIXTURE
from check_original_debris_update import compact
import test_contact_staging_checker as contact
from test_contact_staging_checker import GUARD, body, source_contract


def direct_source_contract(source):
    source_contract(source)
    diagnostic = compact(body(source, 'debugOriginalDebrisUpdate'))
    required = (
        'bool physicalDebrisUpdate = false',
        'if (physicalDebrisUpdate && !completeFracturePools)',
        'if (fractureStorage && !collapseLaneHistory) take(fractureStateBytes);',
        'if (physicalDebrisUpdate || !collapseUpdate) updateDebrisRecords(); else if (collapseUpdate) updateCollapseRecords();',
        'physicalDebrisUpdate ? "debris_contact_pools_app=ok cases="')
    if any(diagnostic.count(compact(statement)) != 1 for statement in required):
        raise ValueError('complete physical fragment selector differs')
    cli = compact('if (argc > 3 && std::string(argv[1]) == "--debug-original-debris-contact-pools") {'
                  'app.debugOriginalDebrisUpdate(argv[2], argv[3], true, false, false, true, true); return 0; }')
    if compact(source).count(cli) != 1 or source.count('"--debug-original-debris-contact-pools"') != 1:
        raise ValueError('direct fragment CLI routing differs')
    if diagnostic.index(compact('if (fractureStorage && !collapseLaneHistory) take(fractureStateBytes);')) > diagnostic.index(
            compact('if (physicalDebrisUpdate || !collapseUpdate) updateDebrisRecords();')):
        raise ValueError('expected bytes are not skipped before production update')


class DebrisContactTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]
    invoke = contact.ContactTests.invoke

    def cases(self):
        _, raw, _ = checker.fixtures(self.root, FIXTURE)
        for index in range(FIXTURE.cases):
            at = 16 + index * FIXTURE.record_bytes
            yield raw[at:at + FIXTURE.input_bytes], raw[at + FIXTURE.input_bytes:at + FIXTURE.record_bytes]

    def test_pins_and_complete_physical_extents(self):
        packed, raw, expected = checker.fixtures(self.root, FIXTURE)
        self.assertEqual((len(packed), len(raw), len(expected)), (602410, 5131024, 2565232))
        self.assertEqual(checker.sha(expected), FIXTURE.output_sha)
        self.assertEqual(FIXTURE.packed_limit, 768 * 1024)
        self.assertEqual(checker.branch_fixture().packed_limit, 128 * 1024)
        with self.assertRaisesRegex(ValueError, 'exceeds limit'):
            checker.decode_fixture(bytes(FIXTURE.packed_limit), FIXTURE)

    def test_four_directions_four_targets_three_capacities_and_actor_occupancies(self):
        matrix = set()
        for index, (before, after) in enumerate(self.cases()):
            count, collapse_count = struct.unpack_from('<HH', before, 10)
            actor = before[25145 + 1570]
            direction, target = index // 24, (index // 6) % 4
            matrix.add((direction, target, count, actor))
            self.assertEqual(collapse_count, 2)
            self.assertEqual(before[25130:25145], after[25124:25139])
            self.assertEqual(struct.unpack_from('<H', after, 6)[0], 2)
        self.assertEqual(matrix, {(d, t, n, a) for d in range(4) for t in range(4)
                                 for n in (2, 1400, 1401) for a in (0, 30)})

    def test_direct_stages_preserve_nine_guard_tail_bytes_and_hard_blockers(self):
        staged, preserved = 0, 0
        for index, (before, after) in enumerate(self.cases()):
            initial, final = before[GUARD + 6:GUARD + 17], after[GUARD:GUARD + 11]
            target = (index // 6) % 4
            if target == 3:
                self.assertEqual(final, initial)
                preserved += 1
            else:
                word = (0xc001, 0x8001, 0xf001)[target]
                self.assertEqual(final, struct.pack('<H', word) + initial[2:])
                staged += 1
        self.assertEqual((staged, preserved), (72, 24))

    def test_updater_and_cli_binding_reject_source_mutants(self):
        source = (self.root / 'src/app/app.cpp').read_text(encoding='utf-8')
        direct_source_contract(source)
        for old, new in (
                ('bool physicalDebrisUpdate = false', 'bool physicalDebrisUpdate = true'),
                ('physicalDebrisUpdate && !completeFracturePools', 'physicalDebrisUpdate && completeFracturePools'),
                ('if (physicalDebrisUpdate || !collapseUpdate) updateDebrisRecords();', 'if (physicalDebrisUpdate || !collapseUpdate) updateCollapseRecords();'),
                ('if (fractureStorage && !collapseLaneHistory) take(fractureStateBytes);', ''),
                ('physicalDebrisUpdate ? "debris_contact_pools_app=ok cases="', 'false ? "debris_contact_pools_app=ok cases="'),
                ('argv[2], argv[3], true, false, false, true, true', 'argv[2], argv[3], true, false, false, true, false'),
                ('--debug-original-debris-contact-pools', '--debug-other-mode'),
                ('writeContactWordGuardAlias(0, word);', '')):
            self.assertEqual(source.count(old), 1)
            with self.subTest(mutation=old), self.assertRaises(ValueError):
                direct_source_contract(source.replace(old, new, 1))

    def test_silent_runner_and_distinct_execution_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(self.invoke(Path(directory), FIXTURE)['passed'])
            self.assertFalse(self.invoke(Path(directory), FIXTURE, bad_marker=True)['passed'])

    def test_all_guard_bytes_banks_and_shared_state_are_compared_without_masks(self):
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
