import gzip
from pathlib import Path
import unittest

import check_damage_lane_bytes as checker


class CheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.packed = (root / 'tests/fixtures/damage_lane_bytes_original.bin.gz').read_bytes()
        cls.incoming, cls.expected = checker.decode(cls.packed)

    def test_exact_fixture(self):
        self.assertEqual(len(self.incoming), 16 + 176 * 65540)
        self.assertEqual(len(self.expected), 16 + 176 * 65536)

    def test_expected_not_installed(self):
        raw = gzip.decompress(self.packed)
        for index in range(176):
            at = 16 + index * checker.STRIDE
            incoming = 16 + index * (checker.STATE + 4)
            self.assertEqual(self.incoming[incoming:incoming + 65540], raw[at:at + 65540])

    def test_packed_mutation(self):
        raw = bytearray(self.packed)
        raw[-8] ^= 1
        with self.assertRaises(ValueError):
            checker.decode(bytes(raw))

    def test_truncated_fixture(self):
        with self.assertRaises(ValueError):
            checker.decode(self.packed[:-1])

    def test_appended_fixture(self):
        with self.assertRaises(ValueError):
            checker.decode(self.packed + b'\0')

    def test_success(self):
        self.assertIsNone(checker.compare(self.expected, self.expected))

    def test_raw_mismatch(self):
        raw = bytearray(self.expected)
        raw[16 + 0x0a07] ^= 1
        difference = checker.compare(bytes(raw), self.expected)
        self.assertEqual((difference['case'], difference['ds_offset']), (0, 0x0a07))

    def test_short_output(self):
        self.assertEqual(checker.compare(self.expected[:-1], self.expected)['actual_bytes'], len(self.expected) - 1)

    def test_trailing_output(self):
        self.assertIsNotNone(checker.compare(self.expected + b'\0', self.expected))

    def test_header_mismatch(self):
        self.assertIsNone(checker.compare(b'', b''))
        self.assertIsNone(checker.compare(self.expected, self.expected))
        raw = b'?' + self.expected[1:]
        self.assertIsNone(checker.compare(raw, self.expected)['case'])


if __name__ == '__main__':
    unittest.main()
