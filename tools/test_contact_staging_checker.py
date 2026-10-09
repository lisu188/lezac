"""Original contact staging, physical alias and strict comparison contracts."""
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_monster_object_seeder as checker
from check_collapse_contact_pools import FIXTURE as POOLS
from check_contact_staging import FIXTURE as MULTI
from check_original_debris_update import compact
from source_guardrails import function_ranges

GUARD = 21363
MAPPINGS = (
    'case 0: guard.tileIndex = word; break;',
    'case 1: guard.flaggedWord = word; break;',
    'case 2: guard.velocityX = static_cast<int8_t>(word); '
    'guard.velocityY = static_cast<int8_t>(word >> 8); break;',
    'case 3: guard.subX = static_cast<int8_t>(word); '
    'guard.subY = static_cast<int8_t>(word >> 8); break;',
    'case 4: guard.restTicks = static_cast<uint8_t>(word); '
    'guard.lookup = static_cast<uint8_t>(word >> 8); break;',
    'case 5: guard.aux = static_cast<uint8_t>(word); break;')


def body(source, name):
    ranges = function_ranges(source, [name])
    if name not in ranges:
        raise ValueError('missing source function: ' + name)
    first, last = ranges[name]
    return '\n'.join(source.splitlines()[first - 1:last])


def source_contract(source):
    alias = compact(body(source, 'writeContactWordGuardAlias'))
    required = ('if (index > 5) return;',
                'auto& guard = debrisQueue_.retainedSlot(kDebrisCapacity - kDebrisRecordIndexBase);',
                *MAPPINGS)
    if any(alias.count(compact(statement)) != 1 for statement in required):
        raise ValueError('physical contact guard mapping differs')
    collapse = compact(body(source, 'updateCollapseRecords'))
    required = ('auto scan = [&](int delta, bool collectContacts = false)',
                'if (collectContacts && word != 0 && std::none_of(result.contacts.begin(), result.contacts.end(),',
                'writeContactWordGuardAlias(result.contacts.size(), word);',
                'result.contacts.push_back({target, word});',
                'scan(-width, true).contacts', 'Scan result = scan(delta, true);',
                'const auto support = scan(width);', '!scan(-1).blocked', '!scan(1).blocked')
    if any(collapse.count(compact(statement)) != 1 for statement in required):
        raise ValueError('contact collection roles differ')
    if collapse.index(compact('writeContactWordGuardAlias(result.contacts.size(), word);')) > collapse.index(
            compact('result.contacts.push_back({target, word});')):
        raise ValueError('contact index is not the zero-based staging slot')
    impact = compact(body(source, 'blendDebrisImpactLane'))
    stage = compact('writeContactWordGuardAlias(0, word);')
    gate = compact('if ((word & kDamagedWordBit) == 0)')
    if impact.count(stage) != 1 or impact.index(stage) > impact.index(gate):
        raise ValueError('single-target staging is not before seeder admission')


class ContactTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def cases(self, spec):
        _, raw, _ = checker.fixtures(self.root, spec)
        for index in range(spec.cases):
            at = 16 + index * spec.record_bytes
            yield raw[at:at + spec.input_bytes], raw[at + spec.input_bytes:at + spec.record_bytes]

    def test_pins_all_state_bytes_and_capacity_guards(self):
        for spec, packed_size in ((POOLS, 468635), (MULTI, 83577)):
            packed, raw, expected = checker.fixtures(self.root, spec)
            self.assertEqual((len(packed), len(raw), len(expected)), (packed_size, 5131024, 2565232))
            self.assertEqual(checker.sha(expected), spec.output_sha)
            for before, after in self.cases(spec):
                self.assertLessEqual(struct.unpack_from('<H', before, 10)[0], 1401)
                self.assertLessEqual(struct.unpack_from('<H', after, 4)[0], 1401)
                self.assertEqual(before[25130:25145], after[25124:25139])

    def test_unique_words_fill_each_guard_byte_without_clearing_the_tail(self):
        covered = set()
        for index, (before, after) in enumerate(self.cases(MULTI)):
            count, pattern = (index // 4) % 6 + 1, index % 4
            initial = before[GUARD + 6:GUARD + 17]
            final = after[GUARD:GUARD + 11]
            words = b''.join(struct.pack('<H', 0xc001 + slot) for slot in range(count))
            if pattern == 0:
                extent = min(11, 2 * count)
                self.assertEqual(final, words[:extent] + initial[extent:])
                covered.update(range(extent))
            elif pattern == 1:
                self.assertEqual(final, b'\x01\xc0' + initial[2:])
            else:
                self.assertEqual(final, initial)
        self.assertEqual(covered, set(range(11)))

    def test_support_only_and_zero_word_blockers_do_not_stage(self):
        preserved = 0
        for index, (before, after) in enumerate(self.cases(MULTI)):
            if index % 4 in (2, 3):
                self.assertEqual(before[GUARD + 6:GUARD + 17], after[GUARD:GUARD + 11])
                preserved += 1
        self.assertEqual(preserved, 48)

    def test_full_pool_frontier_keeps_original_alias_and_capacity_matrix(self):
        seen, changed = set(), 0
        for before, after in self.cases(POOLS):
            seen.add(struct.unpack_from('<HH', before, 10))
            changed += before[GUARD + 6:GUARD + 17] != after[GUARD:GUARD + 11]
            self.assertEqual(before[GUARD + 8:GUARD + 17], after[GUARD + 2:GUARD + 11])
        self.assertEqual(seen, {(1, 2), (1400, 249), (1401, 250)})
        self.assertEqual(changed, 72)

    def test_compressed_allowances_are_fixture_specific(self):
        self.assertEqual(checker.branch_fixture().packed_limit, 128 * 1024)
        self.assertEqual((POOLS.packed_limit, MULTI.packed_limit), (512 * 1024, 128 * 1024))
        for spec in (POOLS, MULTI):
            with self.assertRaisesRegex(ValueError, 'exceeds limit'):
                checker.decode_fixture(bytes(spec.packed_limit), spec)

    def test_original_instruction_pins(self):
        raw = (self.root / 'LEZAC.EXE').read_bytes()
        for at, expected in ((0x4ecd, '89975e65'), (0x4ed1, '89879a65'),
                             (0x4c8c, 'a35e65'), (0x4c9f, 'a35e65')):
            self.assertEqual(raw[0x770 + at:0x770 + at + len(expected) // 2], bytes.fromhex(expected))

    def test_production_source_binding_and_alias_mutations(self):
        source = (self.root / 'src/app/app.cpp').read_text(encoding='utf-8')
        source_contract(source)
        original = body(source, 'writeContactWordGuardAlias')
        for statement in MAPPINGS:
            pattern = r'\s*'.join(re.escape(token) for token in statement.split())
            changed, replacements = re.subn(pattern, '', original, count=1)
            self.assertEqual(replacements, 1)
            with self.assertRaisesRegex(ValueError, 'guard mapping'):
                source_contract(source.replace(original, changed))
        with self.assertRaisesRegex(ValueError, 'missing source function'):
            source_contract(source.replace(original, ''))
        for old, new in (('index > 5', 'index > 4'),
                         ('kDebrisCapacity - kDebrisRecordIndexBase', 'kDebrisCapacity'),
                         ('scan(-width, true)', 'scan(-width)'),
                         ('scan(delta, true)', 'scan(delta)'),
                         ('scan(width);', 'scan(width, true);'),
                         ('scan(-1).blocked', 'scan(-1, true).blocked'),
                         ('scan(1).blocked', 'scan(1, true).blocked'),
                         ('collectContacts && word != 0', 'word != 0'),
                         ('writeContactWordGuardAlias(result.contacts.size(), word);', ''),
                         ('writeContactWordGuardAlias(0, word);', '')):
            with self.assertRaises(ValueError):
                source_contract(source.replace(old, new, 1))

    def invoke(self, root, spec, offset=None, bad_marker=False):
        expected = spec.output_magic + struct.pack('<II', 96, 26721) + bytes(26721 * 2)
        actual = bytearray(expected)
        if offset is not None:
            actual[16 + 26721 + offset] = 1
        exe = root / 'mocked-not-a-game'
        exe.write_bytes(b'executable pin')

        def runner(args, **kwargs):
            self.assertEqual(args[1], spec.option)
            self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
            self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
            Path(args[-1]).write_bytes(actual)
            return subprocess.CompletedProcess(args, 0, b'wrong marker' if bad_marker else spec.app_marker, b'')

        with patch.object(checker, 'fixtures', return_value=(b'packed', b'inputs', expected)), \
                patch.object(checker.subprocess, 'run', side_effect=runner):
            report, path = checker.check(root, exe, root / 'retained', spec)
        self.assertEqual((path.parent / 'actual.bin').read_bytes(), actual)
        return report

    def test_silent_runner_and_required_execution_marker(self):
        for spec in (POOLS, MULTI):
            with tempfile.TemporaryDirectory() as temp:
                self.assertTrue(self.invoke(Path(temp), spec)['passed'])
                self.assertFalse(self.invoke(Path(temp), spec, bad_marker=True)['passed'])

    def test_every_guard_byte_and_adjacent_state_is_compared_without_masks(self):
        offsets = (0, 4, 6, 8, 10, 12, 1992, 5952, *range(GUARD, GUARD + 12),
                   21374, 25124, 25139, 26709, 26714, 26716, 26717, 26718, 26720)
        for spec in (POOLS, MULTI):
            with tempfile.TemporaryDirectory() as temp:
                for offset in offsets:
                    report = self.invoke(Path(temp), spec, offset=offset)
                    self.assertFalse(report['passed'])
                    self.assertFalse(report['masks_applied'])
                    self.assertEqual((report['first_difference']['case'],
                                      report['first_difference']['state_offset']), (1, offset))


if __name__ == '__main__':
    unittest.main()
