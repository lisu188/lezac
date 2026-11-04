"""Synthetic schema controls and existing seeded record slices; no guest launch."""
import copy
from pathlib import Path
import struct
import unittest

import flame_state_projection as flames
from level1_fidelity import EvidenceError


def fixture():
    data = bytearray(65536)
    struct.pack_into('<H', data, 0x2076, 2)
    first = bytes.fromhex('3412efbe807fff00087505')
    second = bytes.fromhex('cdababcd7f8000ff00ff00')
    data[0x209e:0x209e + 11] = first
    data[0x20a9:0x20a9 + 11] = second
    data[0x78d6:0x78d8] = bytes((1, 221))
    expected = [[0x1234, -128, 127, -1, 0, 8, 117, 5, 1],
                [0xabcd, 127, -128, 0, -1, 0, 255, 0, 221]]
    return data, expected


class FlameStateProjectionTests(unittest.TestCase):
    def test_one_based_record_and_mass_layout(self):
        data, expected = fixture()
        data[0x2093:0x209e] = bytes([255]) * 11
        data[0x78d5] = 255
        self.assertEqual(flames.native_flames(data), expected)
        self.assertEqual(flames.native_flames(bytes(data)), expected)
        flames.compare(dict(flames=expected), expected)

    def test_full_capacity_and_last_slot(self):
        data = bytearray(65536)
        struct.pack_into('<H', data, 0x2076, 198)
        struct.pack_into('<H2xbbbbBBB', data, 0x2093 + 11 * 198,
                         65535, 127, -128, -1, 1, 255, 117, 255)
        data[0x78d5 + 198] = 255
        rows = flames.native_flames(data)
        self.assertEqual(len(rows), 198)
        self.assertEqual(rows[-1], [65535, 127, -128, -1, 1, 255, 117, 255, 255])
        flames.compare(dict(flames=rows), rows)

    def test_zero_count_ignores_inactive_records(self):
        data = bytearray([255]) * 65536
        struct.pack_into('<H', data, 0x2076, 0)
        self.assertEqual(flames.native_flames(data), [])
        flames.compare(dict(flames=[]), [])

    def test_excluded_stale_word_and_inactive_slots_do_not_change_projection(self):
        data, expected = fixture()
        for offset in (0x209e + 2, 0x209e + 3, 0x20b4, 0x78d8):
            with self.subTest(offset=offset):
                changed = bytearray(data)
                changed[offset] ^= 255
                self.assertEqual(flames.native_flames(changed), expected)
        self.assertIn('retained word at record +2..3', flames.EXCLUDED)

    def test_original_extent_and_type_rejected(self):
        for data in (None, '', '0' * 65536, [], [0] * 65536, b'', bytes(65535), bytes(65537)):
            with self.subTest(kind=type(data).__name__), self.assertRaises(EvidenceError):
                flames.native_flames(data)

    def test_count_is_a_word_and_capacity_is_not_clamped(self):
        for count in (199, 255, 256, 65535):
            data = bytearray(65536)
            struct.pack_into('<H', data, 0x2076, count)
            with self.subTest(count=count), self.assertRaises(EvidenceError):
                flames.native_flames(data)

    def test_cpp_projection_copies_live_rows(self):
        _, expected = fixture()
        state = dict(flames=copy.deepcopy(expected), unrelated=1)
        actual = flames.cpp_flames(state)
        self.assertEqual(actual, expected)
        actual[0][0] ^= 1
        actual.pop()
        self.assertEqual(state['flames'], expected)

    def test_missing_cpp_field_rejected(self):
        for state in (None, [], {}, dict(flame=[])):
            with self.subTest(state=state), self.assertRaises(EvidenceError):
                flames.cpp_flames(state)

    def test_malformed_shapes_rejected(self):
        for rows in (None, {}, (), [None], [()], [{}], [[0] * 8], [[0] * 10], [[0] * 9] * 199):
            with self.subTest(rows=rows), self.assertRaises(EvidenceError):
                flames.cpp_flames(dict(flames=rows))

    def test_each_numeric_domain_and_boolean_rejected_on_both_sides(self):
        _, expected = fixture()
        for index, (low, high) in enumerate(flames.DOMAINS):
            for value in (low - 1, high + 1, True, False, 0.0, '0', None):
                changed = copy.deepcopy(expected)
                changed[0][index] = value
                for actual, wanted in ((changed, expected), (expected, changed)):
                    with self.subTest(field=flames.FIELDS[index], value=value), self.assertRaises(EvidenceError):
                        flames.compare(dict(flames=actual), wanted)

    def test_every_declared_field_mutation_rejected(self):
        _, expected = fixture()
        for index, name in enumerate(flames.FIELDS):
            changed = copy.deepcopy(expected)
            changed[0][index] ^= 1
            with self.subTest(field=name), self.assertRaises(EvidenceError):
                flames.compare(dict(flames=changed), expected)

    def test_slot_order_missing_and_extra_records_rejected(self):
        _, expected = fixture()
        for changed in (list(reversed(expected)), expected[:1], expected + expected[:1]):
            with self.subTest(changed=changed), self.assertRaises(EvidenceError):
                flames.compare(dict(flames=changed), expected)

    def test_no_inputs_mutated(self):
        data, expected = fixture()
        before = bytes(data), copy.deepcopy(expected)
        state = dict(flames=copy.deepcopy(expected))
        flames.native_flames(data)
        flames.compare(state, expected)
        self.assertEqual((bytes(data), expected), before)
        self.assertEqual(state, dict(flames=before[1]))

    def test_existing_seeded_original_slices(self):
        root = Path(__file__).resolve().parent.parent / 'tests/fixtures'
        for name, expected_count in (('flame_lifecycle', 3666), ('flame_fatal_lifecycle', 3666),
                                     ('flame_stress_lifecycle', 3492)):
            samples = total = 0
            for line in (root / (name + '_original.txt')).read_text(encoding='ascii').splitlines():
                if not line.startswith('flames '):
                    continue
                fields = dict(token.split('=', 1) for token in line.split()[1:])
                records = [] if fields['records'] == '-' else fields['records'].split(',')
                self.assertEqual(len(records), int(fields['count']))
                data, expected = bytearray(65536), []
                struct.pack_into('<H', data, 0x2076, len(records))
                for slot, token in enumerate(records, 1):
                    raw_hex, mass_hex = token.split(':')
                    raw, mass = bytes.fromhex(raw_hex), int(mass_hex, 16)
                    self.assertEqual(len(raw), 11)
                    start = 0x2093 + 11 * slot
                    data[start:start + 11] = raw
                    data[0x78d5 + slot] = mass
                    signed = [value - 256 if value >= 128 else value for value in raw[4:8]]
                    expected.append([int.from_bytes(raw[:2], 'little'), *signed, *raw[8:11], mass])
                with self.subTest(fixture=name, sample=samples):
                    self.assertEqual(flames.native_flames(data), expected)
                    flames.compare(dict(flames=expected), expected)
                samples += 1
                total += len(records)
            self.assertEqual((samples, total), (520, expected_count))


if __name__ == '__main__':
    unittest.main()
