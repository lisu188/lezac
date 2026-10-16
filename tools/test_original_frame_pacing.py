"""Frozen original-pacing fixture contract and malformed-trace controls."""
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from analyze_original_frame_pacing import CAPTURE_HASHES, analyze

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_pacing'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


class OriginalFramePacingTests(unittest.TestCase):
    def test_fixture_contract(self):
        raw = (FIXTURE / 'manifest.json').read_bytes()
        self.assertEqual(SHA(raw), '4a600ebb500bce5f63363bca7842166794e5ba96078aeea69094e1d5ce0761d1')
        manifest = json.loads(raw)
        for item in manifest['files']:
            value = (FIXTURE / item['name']).read_bytes()
            self.assertEqual((len(value), SHA(value)), (item['bytes'], item['sha256']))
        self.assertEqual(manifest['executable_sha256'], SHA((ROOT / 'LEZAC.EXE').read_bytes()))
        self.assertEqual(manifest['capture_producer_sha256'], SHA((ROOT / 'tools/frame_pacing_probe/capture.py').read_bytes()))
        self.assertEqual(manifest['host_probe_sha256'], SHA((ROOT / 'tools/frame_pacing_probe/lezac_work_probe.h').read_bytes()))
        self.assertEqual(CAPTURE_HASHES, dict(dosbox_sha256=manifest['host_binary_sha256'],
                                            producer_sha256=manifest['capture_producer_sha256']))
        oracle = json.loads((FIXTURE / 'oracle.json').read_text())
        self.assertEqual(oracle['producer_sha256'], SHA((ROOT / 'tools/capture_original_frame_delay.py').read_bytes()))
        self.assertEqual(oracle['counter_bits_sha256'], SHA((FIXTURE / 'counter-bits.bin').read_bytes()))
        self.assertEqual(oracle['delay_words_sha256'], SHA((FIXTURE / 'delay-words.bin').read_bytes()))
        self.assertEqual(oracle['original_code_bytes_verified'], 43552)
        self.assertEqual(oracle['original_code_writes'], 0)
        self.assertFalse(oracle['original_calls_stubbed'])
        self.assertEqual(oracle['instruction_patches'], 0)
        for key in ('source_images_or_ram_published', 'synchronized_frame_parity', 'whole_game_parity'):
            self.assertIs(manifest[key], False)

    def test_original_replays(self):
        expected = json.loads((FIXTURE / 'replays.json').read_text())['runs']
        actual = []
        for name in ('r2', 'r3'):
            recipe = json.loads((FIXTURE / (name + '-recipe.json')).read_text())
            manifest = json.loads((FIXTURE / 'manifest.json').read_text())
            self.assertEqual(recipe['dosbox_sha256'], manifest['host_binary_sha256'])
            self.assertEqual(recipe['producer_sha256'], manifest['capture_producer_sha256'])
            actual.append(analyze((FIXTURE / (name + '.csv')).read_bytes(), recipe))
        self.assertEqual(actual, expected)
        self.assertEqual(sum(run['completed_frames'] for run in actual), 289)
        self.assertEqual([run['character'] for run in actual], [81, 82])
        self.assertEqual([run['final_delay'] for run in actual], [8, 8])

    def test_cross_run_recipe_rejected(self):
        for trace, recipe in [('r2', 'r3'), ('r3', 'r2')]:
            with self.subTest(trace=trace), self.assertRaisesRegex(ValueError, 'bind'):
                analyze((FIXTURE / (trace + '.csv')).read_bytes(),
                        json.loads((FIXTURE / (recipe + '-recipe.json')).read_text()))

    def test_structured_trace_rejections(self):
        original = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        rows = list(csv.DictReader(io.StringIO(original[:-4].decode())))
        controls = [('frame_before', 'frame_counter', '1'), ('delay_before', 'delay', '42'),
                    ('measurement', 'measured_word', '0'), ('adjust_end', 'delay', '16'),
                    ('time_result', 'current_minute', '60'), ('delay_after', 'minimum', '3'),
                    ('delay_after', 'character', '80'), ('time_result', 'ds', '0'),
                    ('adjust_begin', 'previous_minute', '0'), ('delay_after', 'clock', '0')]
        for kind, key, value in controls:
            mutated = copy.deepcopy(rows)
            next(row for row in mutated if row['kind'] == kind)[key] = value
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(mutated)
            raw = (buffer.getvalue() + 'end\n').encode()
            bound = dict(recipe, trace_bytes=len(raw), trace_sha256=SHA(raw))
            with self.subTest(kind=kind, key=key), self.assertRaises(ValueError):
                analyze(raw, bound)
        for raw in (original[:-4], original + b'cap\n', original.replace(b'adjust_end', b'unknown', 1)):
            bound = dict(recipe, trace_bytes=len(raw), trace_sha256=SHA(raw))
            with self.subTest(malformed=len(raw)), self.assertRaises(ValueError):
                analyze(raw, bound)

    def test_recipe_rejections(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        for key, value in [('passed', False), ('child_exit_code', -11), ('trace_end_marker', False),
                           ('process_memory_writes', 1), ('canonical_assets_unchanged', False),
                           ('host_commands', []), ('events', []), ('record_file_fixture_seeded', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze(raw, dict(recipe, **{key: value}))
        changed = copy.deepcopy(recipe)
        changed['dosbox_environment']['SDL_AUDIODRIVER'] = 'alsa'
        with self.assertRaises(ValueError):
            analyze(raw, changed)

    def test_read_only_guest_recipe_fields(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        fields = [('host_probe_guest_register_writes', [1, -1, False, '0']),
                  ('host_probe_guest_memory_writes', [1, -1, False, '0']),
                  ('original_executable_changed', [True, 0, 'false']),
                  ('process_memory_opened_read_only', [False, 1, 'true'])]
        for key, values in fields:
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'Read-only'):
                    analyze(raw, dict(recipe, **{key: value}))
            missing = dict(recipe)
            del missing[key]
            with self.subTest(missing=key), self.assertRaisesRegex(ValueError, 'Read-only'):
                analyze(raw, missing)

    def test_capture_host_and_producer_hashes(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        controls = 0
        for key, expected in CAPTURE_HASHES.items():
            for value in ['0' * 64, recipe['executable_sha256'], '', None, False, 0, expected.upper(), {}, []]:
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'host or producer'):
                    analyze(raw, dict(recipe, **{key: value}))
                controls += 1
            missing = dict(recipe)
            del missing[key]
            with self.subTest(missing=key), self.assertRaisesRegex(ValueError, 'host or producer'):
                analyze(raw, missing)
            controls += 1
        self.assertEqual(controls, 20)

    def test_cli_rejects_mutated_guest_without_publishing_report(self):
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        with tempfile.TemporaryDirectory(prefix='lezac-pacing-recipe-') as temporary:
            folder = Path(temporary)
            bad_recipe = folder / 'recipe.json'
            for index, (key, value, reason) in enumerate([
                    ('host_probe_guest_memory_writes', 1, 'Read-only guest provenance differs'),
                    ('host_instrumented', False, 'Capture mode claims differ'),
                    ('dosbox_sha256', '0' * 64, 'Capture host or producer differs'),
                    ('producer_sha256', None, 'Capture host or producer differs')]):
                output = folder / ('report' + str(index) + '.json')
                bad_recipe.write_text(json.dumps(dict(recipe, **{key: value})))
                command = [sys.executable, '-S', '-B', str(ROOT / 'tools/analyze_original_frame_pacing.py'),
                           str(FIXTURE / 'r2.csv'), '--recipe', str(bad_recipe), '--out', str(output)]
                environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
                result = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(reason, result.stderr)
                self.assertFalse(output.exists())
                output.write_bytes(b'preserved existing report\n')
                result = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output.read_bytes(), b'preserved existing report\n')

    def test_capture_mode_claims_and_profile(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        flags = dict(host_instrumented=True, natural_wall_clock_fidelity_claim=False,
                     complete_frame_sequence_claim=False, whole_game_complete=False,
                     cpu_memory_frame_atomic=False, private_xvfb_autorepeat_disabled=True)
        controls = []
        for key, expected in flags.items():
            for value in [not expected, 0, 1, str(expected).lower(), None]:
                controls.append((key, dict(recipe, **{key: value})))
            missing = dict(recipe)
            del missing[key]
            controls.append((key + '-missing', missing))
        for key, values in [('audio', ['alsa', False, None]),
                            ('configured_players', [2, True, '1', None]),
                            ('trace_clock', ['wall clock', False, None]),
                            ('trace_dispatch', ['cycles', False, None])]:
            controls.extend((key, dict(recipe, **{key: value})) for value in values)
            missing = dict(recipe)
            del missing[key]
            controls.append((key + '-missing', missing))
        for value in [True, 0, 'false', None, 'missing']:
            changed = copy.deepcopy(recipe)
            if value == 'missing':
                del changed['samples'][0]['ram_rgb_cpu_atomic']
            else:
                changed['samples'][0]['ram_rgb_cpu_atomic'] = value
            controls.append(('checkpoint-atomic', changed))
        for key, value in [('exit_code', 1), ('exit_code', False), ('command', ['xset', 'r', 'on'])]:
            changed = copy.deepcopy(recipe)
            changed['private_display_autorepeat_command'][key] = value
            controls.append(('autorepeat-command', changed))
        missing = dict(recipe)
        del missing['private_display_autorepeat_command']
        controls.append(('autorepeat-command-missing', missing))
        self.assertEqual(len(controls), 62)
        for name, changed in controls:
            with self.subTest(name=name, recipe=changed), self.assertRaises(ValueError):
                analyze(raw, changed)


if __name__ == '__main__':
    unittest.main()
