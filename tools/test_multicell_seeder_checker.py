"""Native multi-cell fixture and checker contracts, separate from actual-App acceptance."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_monster_object_seeder as checker
from check_multicell_seeder import FIXTURE


class MulticellTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def test_native_pins_and_complete_output(self):
        packed, raw, output = checker.fixtures(self.root, FIXTURE)
        self.assertEqual(checker.sha(packed), FIXTURE.packed_sha)
        self.assertEqual(checker.sha(raw), FIXTURE.raw_sha)
        self.assertEqual(checker.sha(output), FIXTURE.output_sha)
        self.assertEqual((len(raw), len(output)), (4577680, 2293264))

    def test_signed_velocities_and_full_magnitude_word(self):
        _, raw, _ = checker.fixtures(self.root, FIXTURE)
        magnitudes = set()
        for index in range(FIXTURE.cases):
            at = 16 + index * FIXTURE.record_bytes
            vx, vy = struct.unpack_from('<bb', raw, at + 2)
            state = at + FIXTURE.input_bytes
            self.assertEqual(raw[at + 2:at + 4], raw[state + 5961:state + 5963])
            magnitude = struct.unpack_from('<H', raw, state + 5965)[0]
            self.assertEqual(magnitude, abs(vx) + abs(vy))
            magnitudes.add(magnitude)
        self.assertIn(256, magnitudes)
        self.assertIn(255, magnitudes)

    def test_affected_byte_wraps_and_complete_glyph_plane_is_preserved(self):
        _, raw, _ = checker.fixtures(self.root, FIXTURE)
        wrapped = cells = 0
        for index in range(FIXTURE.cases):
            at = 16 + index * FIXTURE.record_bytes
            state = at + FIXTURE.input_bytes
            seed = struct.unpack_from('<H', raw, at)[0]
            key = struct.unpack_from('<H', raw, at + 9 + 1980 + 2 * seed)[0]
            words = struct.unpack_from('<1980H', raw, state + 1980)
            flagged = sum(word == (key | 0x8000) for word in words)
            self.assertEqual(raw[state + 5969], (2 * flagged) & 255)
            self.assertEqual(raw[at + 9:at + 9 + 1980], raw[state:state + 1980])
            wrapped += flagged >= 128; cells += flagged
        self.assertEqual((wrapped, cells), (24, 7152))

    def test_unused_debris_candidate_and_counts_are_preserved(self):
        _, raw, _ = checker.fixtures(self.root, FIXTURE)
        salt = bytes((17 + i * 13) & 255 for i in range(11))
        for index in range(FIXTURE.cases):
            at = 16 + index * FIXTURE.record_bytes
            state = at + FIXTURE.input_bytes
            dc, cc = struct.unpack_from('<HH', raw, at + 4)
            self.assertEqual(struct.unpack_from('<HH', raw, state + 5940), (dc, cc + 1))
            self.assertEqual(raw[state + 5944:state + 5955], salt)
            self.assertEqual(raw[state + 5970:state + 5972], b'\x01\x00')

    def test_wrong_compressed_pin_and_protocol_are_rejected(self):
        with self.assertRaises(ValueError): checker.decode_fixture(b'wrong', FIXTURE)
        with self.assertRaises(ValueError): checker.validate_format(b'LZSC0001' + struct.pack('<II', 448, 5979), FIXTURE)

    def invoke(self, root, changed_offset=None, wrong_marker=False):
        expected = FIXTURE.output_magic + struct.pack('<II', 384, 5972) + bytes(5972 * 2)
        actual = bytearray(expected)
        if changed_offset is not None: actual[16 + 5972 + changed_offset] = 1
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

    def test_silent_success_uses_multicell_protocol(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertTrue(self.invoke(Path(temp))['passed'])

    def test_each_state_region_is_compared_without_masks(self):
        with tempfile.TemporaryDirectory() as temp:
            for offset in (0, 1980, 5940, 5944, 5955, 5961, 5965, 5969, 5970, 5971):
                report = self.invoke(Path(temp), changed_offset=offset)
                self.assertFalse(report['passed'])
                self.assertFalse(report['masks_applied'])
                self.assertEqual(report['first_difference']['case'], 1)
                self.assertEqual(report['first_difference']['state_offset'], offset)

    def test_other_suite_marker_cannot_accept_multicell_output(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertFalse(self.invoke(Path(temp), wrong_marker=True)['passed'])


if __name__ == '__main__':
    unittest.main()
