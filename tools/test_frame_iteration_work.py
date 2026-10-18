"""Original iteration-work partitions and preservation counterexamples."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import analyze_frame_iteration_work as work


class FrameIterationWorkTests(unittest.TestCase):
    def test_authenticated_original_totals(self):
        result = work.report()
        self.assertEqual(result['schema'], 'lezac-historical-iteration-work-v1')
        self.assertEqual(result['cycles_per_profile_millisecond'], 6000)
        expected = [('r2', 47300383, 54511720, 10595740, 43915980),
                    ('r3', 47300313, 54511667, 10595651, 43916016)]
        for run, (name, dispatches, credits, prefix, remainder) in zip(result['runs'], expected):
            self.assertEqual(run['run'], name)
            self.assertEqual(run['completed_iterations'], 147)
            self.assertEqual(run['completed_pacing_prefixes'], 147)
            self.assertEqual(run['unclosed_frame_entries'], 1)
            self.assertEqual(run['terminal_delay_without_next_entry'], 0)
            self.assertEqual(run['dispatch']['total']['total'], dispatches)
            self.assertEqual(run['work_clock']['total'], dict(min=346543, max=397122, total=credits))
            self.assertEqual(run['work_clock']['pacing']['total'], prefix)
            self.assertEqual(run['work_clock']['after_delay']['total'], remainder)
            self.assertEqual(prefix + remainder, credits)
            for interval in run['intervals']:
                for key in ('dispatch', 'work_clock'):
                    values = interval[key]
                    self.assertEqual(values['pacing'] + values['after_delay'], values['total'])
                self.assertGreater(interval['work_clock']['total'], interval['dispatch']['total'])
        for key in ('dispatches_are_work_clock_credits', 'after_delay_is_only_gameplay',
                    'physical_hardware_timing_claim', 'production_app_clock_integrated', 'whole_game_parity'):
            self.assertIs(result[key], False)
        self.assertIs(result['interrupts_included'], True)

    @staticmethod
    def rows(counter=0):
        return [dict(kind='frame_before', frame_counter=counter, dispatch=10, clock=20),
                dict(kind='delay_after', frame_counter=(counter + 1) % 65536,
                     dispatch=15, clock=27, delay=8),
                dict(kind='frame_before', frame_counter=(counter + 1) % 65536,
                     dispatch=30, clock=50)]

    def test_terminal_prefix_is_not_an_iteration(self):
        rows = self.rows()
        rows.append(dict(kind='delay_after', frame_counter=2, dispatch=35, clock=57, delay=7))
        intervals, unclosed, terminal_delay = work.partition(rows)
        self.assertEqual((len(intervals), unclosed, terminal_delay), (1, 1, 1))
        self.assertEqual(intervals[0]['dispatch'], dict(pacing=5, after_delay=15, total=20))
        self.assertEqual(intervals[0]['work_clock'], dict(pacing=7, after_delay=23, total=30))

    def test_synthetic_counter_wrap(self):
        intervals, _, _ = work.partition(self.rows(65535))
        self.assertEqual((intervals[0]['counter'], intervals[0]['next_counter']), (65535, 0))

    def test_invalid_partitions_rejected(self):
        controls = [[], self.rows()[:2], self.rows()[1:],
                    [self.rows()[0], self.rows()[2]],
                    self.rows()[:2] + [self.rows()[1], self.rows()[2]]]
        for index, key, value in [(2, 'frame_counter', 2), (1, 'frame_counter', 2), (1, 'dispatch', 10),
                                  (1, 'clock', 20), (2, 'dispatch', 15), (2, 'clock', 27)]:
            rows = copy.deepcopy(self.rows())
            rows[index][key] = value
            controls.append(rows)
        for index, rows in enumerate(controls):
            with self.subTest(control=index), self.assertRaises(ValueError):
                work.partition(rows)

    def test_fixture_mutations_and_missing_bytes_rejected(self):
        with tempfile.TemporaryDirectory(prefix='lezac-iteration-fixture-') as temporary:
            fixture = Path(temporary)
            for source in work.FIXTURE.iterdir():
                if source.is_file():
                    shutil.copyfile(source, fixture / source.name)
            with mock.patch.object(work, 'FIXTURE', fixture):
                for name in ('manifest.json', 'r2.csv', 'r3.csv', 'r2-recipe.json',
                             'r3-recipe.json', 'counter-bits.bin', 'delay-words.bin'):
                    path = fixture / name
                    original = path.read_bytes()
                    path.write_bytes(original + b'\n')
                    with self.subTest(file=name), self.assertRaisesRegex(ValueError, 'differs'):
                        work.report()
                    path.write_bytes(original)
                target = fixture / 'r2.csv'
                target.unlink()
                with self.assertRaises(FileNotFoundError):
                    work.report()

    def test_recipe_rebinding_does_not_bypass_original_validation(self):
        raw = (work.FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((work.FIXTURE / 'r2-recipe.json').read_bytes())
        for key, value in [('dosbox_sha256', '0' * 64), ('process_memory_writes', 1),
                           ('trace_clock', 'wall clock'), ('audio', 'alsa')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                work.analyze_run(raw, dict(recipe, **{key: value}))

    def test_cli_and_existing_output_preserved(self):
        with tempfile.TemporaryDirectory(prefix='lezac-iteration-cli-') as temporary:
            output = Path(temporary) / 'report.json'
            command = [sys.executable, '-S', '-B', str(Path(work.__file__)), '--out', str(output)]
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            result = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_bytes()), work.report())
            original, timestamp = output.read_bytes(), output.stat().st_mtime_ns
            result = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Output already exists', result.stderr)
            self.assertEqual((output.read_bytes(), output.stat().st_mtime_ns), (original, timestamp))

    def test_cli_preserves_output_links(self):
        with tempfile.TemporaryDirectory(prefix='lezac-iteration-links-') as temporary:
            folder = Path(temporary)
            target = folder / 'target.json'
            target.write_bytes(b'preserve target\n')
            output = folder / 'output.json'
            try:
                output.symlink_to(target)
            except OSError as error:
                self.skipTest('This platform does not permit temporary symbolic links: ' + str(error))
            command = [sys.executable, '-S', '-B', str(Path(work.__file__)), '--out', str(output)]
            for dangling in (False, True):
                if dangling:
                    target.unlink()
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Output already exists', result.stderr)
                self.assertTrue(output.is_symlink())
                if not dangling:
                    self.assertEqual(target.read_bytes(), b'preserve target\n')
                else:
                    self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
