"""Capacity fixture and checker contracts; mocked execution is not game acceptance."""
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_monster_object_seeder as checker
from check_seeder_capacity import FIXTURE


class CapacityTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def test_original_fixture_and_complete_output_pins(self):
        packed, raw, expected = checker.fixtures(self.root, FIXTURE)
        self.assertEqual(checker.sha(packed), FIXTURE.packed_sha)
        self.assertEqual(checker.sha(raw), FIXTURE.raw_sha)
        self.assertEqual(checker.sha(expected), FIXTURE.output_sha)
        self.assertEqual(len(expected), 2675472)

    def test_flagged_and_full_rejections_preserve_salted_candidates(self):
        _, raw, _ = checker.fixtures(self.root, FIXTURE)
        debris = bytes((17 + i * 13) & 255 for i in range(11))
        collapse = bytes((31 + i * 19) & 255 for i in range(15))
        rejected = flagged = accepted = 0
        for index in range(FIXTURE.cases):
            at = 16 + index * FIXTURE.record_bytes
            word, dc, cc, previous = struct.unpack_from('<HHHB', raw, at)
            state = raw[at + 7:at + FIXTURE.record_bytes]
            inserted = word < 0x8000 and (dc < 1600 if word >= 0x4000 else cc < 250)
            self.assertEqual(state[-2], previous if word >= 0x8000 else int(inserted))
            self.assertEqual(state[-1], 0xa5 if word >= 0x8000 else int(word >= 0x4000))
            if not inserted:
                self.assertEqual(state[5944:5970], debris + collapse)
                rejected += 1
            accepted += inserted
            flagged += word >= 0x8000
        self.assertEqual((accepted, rejected, flagged), (128, 320, 192))

    def test_branch_protocol_is_rejected_as_capacity_input(self):
        for raw in (b'LZOS0001' + struct.pack('<II', 448, 5979), b'LZSC0001' + struct.pack('<II', 448, 5979)):
            with self.assertRaises(ValueError): checker.validate_format(raw, FIXTURE)

    def test_capacity_compressed_and_decompressed_pins_are_independent(self):
        with self.assertRaisesRegex(ValueError, 'compressed seeder fixture hash mismatch'):
            checker.decode_fixture(b'wrong', FIXTURE)
        packed = (self.root / FIXTURE.fixture_path).read_bytes()
        with self.assertRaisesRegex(ValueError, 'decompressed seeder fixture hash mismatch'):
            checker.decode_fixture(packed, FIXTURE._replace(raw_sha='0' * 64))

    def invoke(self, root, altered=False, wrong_marker=False, timeout=False):
        expected = FIXTURE.output_magic + struct.pack('<II', 448, 5972) + bytes(5972 * 2)
        actual = bytearray(expected)
        if altered: actual[16 + 5972 + 5944] = 255
        exe = root / 'not-a-game-mocked-runner'
        exe.write_bytes(b'executable pin')

        def runner(args, **kwargs):
            self.assertEqual(args[1], FIXTURE.option)
            self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
            self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
            if timeout: raise subprocess.TimeoutExpired(args, 60, output=b'partial', stderr=b'timeout')
            Path(args[-1]).write_bytes(actual)
            return subprocess.CompletedProcess(args, 0, checker.MARKER if wrong_marker else FIXTURE.app_marker, b'')

        with patch.object(checker, 'fixtures', return_value=(b'packed', b'inputs', expected)), \
             patch.object(checker.subprocess, 'run', side_effect=runner):
            report, path = checker.check(root, exe, root / 'retained', FIXTURE)
        self.assertEqual(json.loads(path.read_bytes())['passed'], report['passed'])
        return report, path, bytes(actual)

    def test_capacity_success_uses_own_protocol_and_silent_child(self):
        with tempfile.TemporaryDirectory() as temp:
            report, path, actual = self.invoke(Path(temp))
            self.assertTrue(report['passed'])
            self.assertEqual(report['compared_bytes'], 2675456)
            self.assertEqual((path.parent / 'actual.bin').read_bytes(), actual)

    def test_changed_inactive_byte_is_retained_and_rejected_without_masking(self):
        with tempfile.TemporaryDirectory() as temp:
            report, path, actual = self.invoke(Path(temp), altered=True)
            self.assertFalse(report['passed'])
            self.assertFalse(report['masks_applied'])
            self.assertEqual(report['first_difference']['case'], 1)
            self.assertEqual(report['first_difference']['state_offset'], 5944)
            self.assertEqual((path.parent / 'actual.bin').read_bytes(), actual)

    def test_branch_marker_does_not_accept_capacity_output(self):
        with tempfile.TemporaryDirectory() as temp:
            report, _, _ = self.invoke(Path(temp), wrong_marker=True)
            self.assertFalse(report['passed'])

    def test_capacity_timeout_retains_partial_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            report, path, _ = self.invoke(Path(temp), timeout=True)
            self.assertFalse(report['passed'])
            self.assertEqual((path.parent / 'actual.stdout').read_bytes(), b'partial')
            self.assertEqual((path.parent / 'actual.stderr').read_bytes(), b'timeout')


if __name__ == '__main__':
    unittest.main()
