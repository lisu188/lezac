"""Frozen original-pacing fixture contract and malformed-trace controls."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import unittest

from analyze_original_frame_pacing import analyze

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


if __name__ == '__main__':
    unittest.main()
