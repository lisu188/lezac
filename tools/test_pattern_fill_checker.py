import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import check_pattern_fill_original as checker

FIXTURE = Path(__file__).resolve().parent.parent / 'tests/fixtures/pattern_fill_original.json'

class PatternCheckerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='lezac-pattern-checker-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.original = json.loads(FIXTURE.read_text())

    def fixture(self, data):
        path = self.root / 'fixture.json'
        path.write_text(json.dumps(data))
        return path

    def test_fixture_and_field_controls(self):
        self.assertEqual(len(checker.load_fixture(FIXTURE)), 3)
        controls = []
        for field, value in [('name', '../escape'), ('name', ''), ('rgb_sha256', 'f' * 63),
            ('horizontal_step', 0), ('horizontal_step', 81), ('horizontal_step', True),
            ('vertical_step', -1), ('vertical_step', 81), ('destination_offset', -1),
            ('destination_offset', 64001), ('ram_cursor_destination', 64000),
            ('ram_cursor_fraction', -9), ('ram_cursor_phase', 65536),
            ('ram_phase_stage', 'unknown'), ('ram_phase_stage', 'Vertical'), ('ram_rgb_atomic', True)]:
            data = copy.deepcopy(self.original)
            data['cases'][0][field] = value
            controls.append(data)
        for key, value in [('masks', 1), ('full_game_parity', True), ('instruction_alignment_claim', True)]:
            data = copy.deepcopy(self.original)
            data[key] = value
            controls.append(data)
        data = copy.deepcopy(self.original)
        data['cases'][0]['colors'][0]['r'] = 256
        controls.append(data)
        data = copy.deepcopy(self.original)
        data['cases'][1]['name'] = data['cases'][0]['name']
        controls.append(data)
        for data in controls:
            with self.assertRaises(RuntimeError):
                checker.load_fixture(self.fixture(data))

    def test_complete_frame_controls(self):
        path = self.root / 'frame.ppm'
        pixels = bytes(192000)
        raw = checker.HEADER + pixels
        case = dict(rgb_sha256=checker.sha(pixels))
        path.write_bytes(raw)
        checker.check_frame(path, case)
        for mutant in [raw[:-1], raw + b'\0', b'P3' + raw[2:],
                       raw[:len(checker.HEADER)] + b'\1' + pixels[1:], raw[:-1] + b'\1']:
            path.write_bytes(mutant)
            with self.assertRaises(RuntimeError):
                checker.check_frame(path, case)

    def test_second_failure_keeps_first_frames_and_diagnostics(self):
        data = copy.deepcopy(self.original)
        for case in data['cases']:
            case['rgb_sha256'] = checker.sha(bytes(192000))
        fixture = self.fixture(data)
        exe = self.root / 'fake-app'
        exe.write_bytes(b'fixture fake, not an original execution')
        calls = []
        first = {}
        def invoke(command, **kwargs):
            calls.append(command)
            self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
            if len(calls) == 2:
                return subprocess.CompletedProcess(command, 9, b'', b'deliberate second failure')
            frames = Path(command[-1]) / 'run-0'
            frames.mkdir(parents=True)
            for case in data['cases']:
                path = frames / (case['name'] + '.ppm')
                path.write_bytes(checker.HEADER + bytes(192000))
                first[path] = checker.sha(path.read_bytes())
            return subprocess.CompletedProcess(command, 0, checker.MARKER + b'\n', b'')
        out = self.root / 'evidence'
        with patch.object(checker.subprocess, 'run', side_effect=invoke):
            with self.assertRaisesRegex(RuntimeError, 'deliberate second failure'):
                checker.replay(exe, fixture, out)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(checker.sha(path.read_bytes()) == digest for path, digest in first.items()))
        report = json.loads(next(out.rglob('report.json')).read_text())
        self.assertFalse(report['passed'])
        self.assertEqual(len(report['native_runs']), 2)
        self.assertEqual(next(out.rglob('1.stderr')).read_bytes(), b'deliberate second failure')

    def test_zero_exit_without_native_marker_is_rejected(self):
        exe = self.root / 'fake-app'
        exe.write_bytes(b'fake')
        result = subprocess.CompletedProcess([], 0, b'wrong marker', b'')
        with patch.object(checker.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError):
                checker.replay(exe, FIXTURE, self.root / 'wrong-marker')
        self.assertFalse(json.loads(next(self.root.rglob('report.json')).read_text())['passed'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
