#!/usr/bin/env python3
"""Original-backed trace replay and adversarial timing-checker regressions."""
import copy
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from analyze_original_work_clock import analyze, CAPTURE_HASHES, COLUMNS, read_rows, validate_capture_recipe

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/original_work_clock'
MANIFEST_SHA = '89b94118713a8c73e22c32cd4e7115e3fc8f3ef86ae30ff54afb1a1daef99dc1'
sha = lambda raw: hashlib.sha256(raw).hexdigest()

class WorkClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (FIXTURES / 'manifest.json').read_bytes()
        if sha(raw) != MANIFEST_SHA:
            raise ValueError('Original timing manifest changed')
        cls.manifest = json.loads(raw)
        cls.rows, cls.raw = read_rows(FIXTURES / 'r1.csv.gz')

    def test_original_runs(self):
        manifest = self.manifest
        self.assertTrue(manifest['host_instrumented'])
        self.assertFalse(manifest['natural_wall_clock_fidelity_claim'])
        self.assertFalse(manifest['full_ram_or_images_published'])
        self.assertEqual(sha((ROOT / 'LEZAC.EXE').read_bytes()), manifest['original_executable_sha256'])
        self.assertEqual(sha((ROOT / 'tools/original_work_probe/lezac_work_probe.h').read_bytes()), manifest['probe_sha256'])
        self.assertEqual(sha((ROOT / 'tools/original_work_probe/capture.py').read_bytes()), manifest['audit_capture_producer_sha256'])
        profiles = []
        for run in manifest['runs']:
            with self.subTest(run=run['name']):
                source = FIXTURES / run['trace']
                packed = source.read_bytes()
                self.assertEqual(len(packed), run['compressed_bytes'])
                self.assertEqual(sha(packed), run['compressed_sha256'])
                raw = gzip.decompress(packed)
                self.assertEqual(len(raw), run['trace_bytes'])
                self.assertEqual(sha(raw), run['trace_sha256'])
                result = analyze(source)
                self.assertEqual(result, run['profile'])
                self.assertEqual(len(result['pages']), 4)
                self.assertEqual(len(result['row_work_dispatches_without_vertical_carry']), 200)
                self.assertFalse(result['dispatches_are_cycle_clock'])
                self.assertFalse(result['natural_wall_clock_fidelity_claim'])
                self.assertEqual(result['unfinished_delays_at_host_exit'], 1)
                self.assertTrue(all(item['code_bytes_verified'] == 43552 and item['code_differences'] == 0
                                    for item in run['observations']))
                profiles.append(result)
        self.assertEqual(profiles[0]['row_work_dispatches_without_vertical_carry'],
                         profiles[1]['row_work_dispatches_without_vertical_carry'])
        self.assertTrue(all(profile['row_work_dispatches_without_vertical_carry'] ==
            profiles[0]['row_work_dispatches_without_vertical_carry'] for profile in profiles))
        self.assertNotEqual([(page['horizontal'], page['vertical']) for page in profiles[0]['pages']],
                            [(page['horizontal'], page['vertical']) for page in profiles[1]['pages']])
        self.assertEqual({item['calibrated_delay_word'] for item in manifest['runs'][0]['observations']}, {81})
        self.assertEqual({item['calibrated_delay_word'] for item in manifest['runs'][1]['observations']}, {82})

    def test_capture_recipes_and_rejection_controls(self):
        recipes = {}
        for run in self.manifest['runs']:
            raw = (FIXTURES / run['recipe']).read_bytes()
            self.assertEqual(sha(raw), run['recipe_sha256'])
            recipe = json.loads(raw)
            _, trace_raw = read_rows(FIXTURES / run['trace'])
            recipes[run['name']] = recipe
            if run['name'] in self.manifest['auditable_capture_runs']:
                validate_capture_recipe(recipe, trace_raw)
                self.assertEqual(recipe['producer_sha256'], self.manifest['audit_capture_producer_sha256'])
            else:
                self.assertTrue(recipe['inherited_environment_was_not_recorded'])
                with self.assertRaisesRegex(ValueError, 'Incomplete capture environment'):
                    validate_capture_recipe(recipe, trace_raw)
        for name in ('r3', 'r4'):
            result = analyze(FIXTURES / (name + '.csv.gz'), recipe=recipes[name])
            self.assertTrue(result['capture_recipe_verified'])
            self.assertEqual(result['capture_recipe_run'], name)
            other = 'r4' if name == 'r3' else 'r3'
            with self.assertRaisesRegex(ValueError, 'Recipe does not match analyzed trace'):
                analyze(FIXTURES / (other + '.csv.gz'), recipe=recipes[name])
        controls = []
        recipe = copy.deepcopy(recipes['r3'])
        recipe['environment_is_complete'] = False
        controls.append(recipe)
        recipe = copy.deepcopy(recipes['r3'])
        recipe['dosbox_environment'].pop('HOME')
        controls.append(recipe)
        recipe = copy.deepcopy(recipes['r3'])
        recipe['dosbox_argv'].pop()
        controls.append(recipe)
        recipe = copy.deepcopy(recipes['r3'])
        next(item for item in recipe['host_commands'] if item['command'][:2] == ['xdotool', 'key'])['command'][-1] = '2'
        controls.append(recipe)
        recipe = copy.deepcopy(recipes['r3'])
        recipe['host_commands'][0]['exit_code'] = 1
        controls.append(recipe)
        recipe = copy.deepcopy(recipes['r3'])
        recipe['events'].pop()
        controls.append(recipe)
        recipe = copy.deepcopy(recipes['r3'])
        recipe['input_injection_failures'].append({'error': 'injected test failure'})
        controls.append(recipe)
        recipe = copy.deepcopy(recipes['r3'])
        recipe['trace_sha256'] = '0' * 64
        controls.append(recipe)
        recipe = copy.deepcopy(recipes['r3'])
        recipe['trace_bytes'] += 1
        controls.append(recipe)
        _, trace_raw = read_rows(FIXTURES / 'r3.csv.gz')
        for index, recipe in enumerate(controls):
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_capture_recipe(recipe, trace_raw)

    def test_recipe_cli_binding_and_retention(self):
        with tempfile.TemporaryDirectory(prefix='lezac-work-cli-') as directory:
            directory = Path(directory)
            recipe = FIXTURES / 'r3-recipe.json'
            script = ROOT / 'tools/analyze_original_work_clock.py'
            output = directory / 'matched.json'
            result = subprocess.run([sys.executable, '-S', '-B', str(script),
                str(FIXTURES / 'r3.csv.gz'), str(output), '--recipe', str(recipe)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(output.read_text())['capture_recipe_verified'])
            retained = output.read_bytes()
            mismatch = directory / 'mismatched.json'
            result = subprocess.run([sys.executable, '-S', '-B', str(script),
                str(FIXTURES / 'r4.csv.gz'), str(mismatch), '--recipe', str(recipe)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Recipe does not match analyzed trace', result.stderr)
            self.assertFalse(mismatch.exists())
            result = subprocess.run([sys.executable, '-S', '-B', str(script),
                str(FIXTURES / 'r3.csv.gz'), str(output), '--recipe', str(recipe)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), retained)

    def test_full_original_producer_reports(self):
        pins = dict(r3='15492f9157ad8d58c1ede604b47d767e82ca2640143e8e2a57e387a4f3aab8b4',
                    r4='df5f0afa3efc27aad15e6a03040b8b23fadb272047c6243476bb23245d5d33db')
        for run, pin in pins.items():
            raw = (FIXTURES / (run + '-full-recipe.json')).read_bytes()
            self.assertEqual(sha(raw), pin)
            recipe = json.loads(raw)
            legacy = json.loads((FIXTURES / (run + '-recipe.json')).read_text())
            self.assertEqual({key: recipe[key] for key in CAPTURE_HASHES}, CAPTURE_HASHES)
            self.assertEqual(analyze(FIXTURES / (run + '.csv.gz'), recipe),
                             analyze(FIXTURES / (run + '.csv.gz'), legacy))

    def test_provenance_mutations_rejected(self):
        _, trace = read_rows(FIXTURES / 'r3.csv.gz')
        for suffix in ('-recipe.json', '-full-recipe.json'):
            original = json.loads((FIXTURES / ('r3' + suffix)).read_text())
            controls = []
            for key in CAPTURE_HASHES:
                for value in ('0' * 64, None, False, 0, original[key].upper()):
                    controls.append(dict(original, **{key: value}))
                changed = dict(original)
                del changed[key]
                controls.append(changed)
            for name in original['assets']:
                for key, value in (('bytes', 0), ('bytes', True), ('sha256', '0' * 64)):
                    changed = copy.deepcopy(original)
                    changed['assets'][name][key] = value
                    controls.append(changed)
                changed = copy.deepcopy(original)
                del changed['assets'][name]
                controls.append(changed)
            for value in (None, False, {}, dict(original['assets'], unknown={})):
                controls.append(dict(original, assets=value))
            fields = ['process_memory_writes', 'process_pauses', 'gameplay_state_seeded',
                'clock_rng_or_heap_seeded', 'record_file_fixture_seeded', 'child_exit_code',
                'canonical_assets_unchanged', 'audio', 'fixture_scores']
            fields += [key for key in ('schema', 'passed', 'host_instrumented',
                'host_probe_guest_register_writes', 'host_probe_guest_memory_writes',
                'original_executable_changed', 'natural_wall_clock_fidelity_claim',
                'injected_instructions', 'configured_players', 'process_memory_opened_read_only',
                'cpu_memory_frame_atomic', 'complete_frame_sequence_claim', 'whole_game_complete',
                'trace_end_marker', 'private_xvfb_autorepeat_disabled', 'trace_clock', 'trace_dispatch')
                if key in original]
            for key in fields:
                expected = original[key]
                bad = not expected if type(expected) is bool else 'contradiction'
                for value in (bad, None, 0 if type(expected) is bool else False):
                    controls.append(dict(original, **{key: value}))
                changed = dict(original)
                del changed[key]
                controls.append(changed)
            for index, changed in enumerate(controls):
                with self.subTest(suffix=suffix, control=index), self.assertRaises(ValueError):
                    validate_capture_recipe(changed, trace)

    def test_full_report_command_and_profile_controls(self):
        original = json.loads((FIXTURES / 'r3-full-recipe.json').read_text())
        _, trace = read_rows(FIXTURES / 'r3.csv.gz')
        controls = []
        for index in range(len(original['host_commands'])):
            changed = copy.deepcopy(original)
            del changed['host_commands'][index]
            controls.append(changed)
        for index in (2, 5, 8, 11, 14, 17, 20):
            changed = copy.deepcopy(original)
            changed['host_commands'][index]['stdout'] = 'bogus'
            controls.append(changed)
        for key, value in (('dosbox_config', original['dosbox_config'].replace('sbtype=none', 'sbtype=sb16')),
                           ('dosbox_config', original['dosbox_config'] + '\n[extra]\nx=y\n'),
                           ('capture_argv', ['/tmp/evil']), ('child_pid', True)):
            controls.append(dict(original, **{key: value}))
        for key, value in (('monotonic_before', float('nan')), ('monotonic_after', float('inf')),
                           ('exit_code', False)):
            changed = copy.deepcopy(original)
            changed['host_commands'][4][key] = value
            controls.append(changed)
        changed = copy.deepcopy(original)
        changed['host_commands'].append(dict(changed['host_commands'][-1], command=['xdotool', 'key', 'Left']))
        controls.append(changed)
        changed = copy.deepcopy(original)
        changed['dosbox_environment']['SDL_AUDIODRIVER'] = 'alsa'
        controls.append(changed)
        changed = copy.deepcopy(original)
        changed['samples'][0]['code_differences'] = 1
        controls.append(changed)
        changed = copy.deepcopy(original)
        changed['events'][0]['monotonic_after'] = 0
        controls.append(changed)
        for key, value in (('unrecognized_claim', True), ('code_segment', original['code_segment'] + 1),
                           ('data_segment', 0), ('ram_base', False)):
            controls.append(dict(original, **{key: value}))
        for index, changed in enumerate(controls):
            with self.subTest(control=index), self.assertRaises(ValueError):
                validate_capture_recipe(changed, trace)

    def test_full_report_relocated_sources(self):
        recipe = json.loads((FIXTURES / 'r3-full-recipe.json').read_text())
        _, trace = read_rows(FIXTURES / 'r3.csv.gz')
        recipe['capture_argv'][0] = '/workspace/project with spaces/tools/original_work_probe/capture.py'
        recipe['capture_argv'][5] = '/workspace/project with spaces'
        recipe['capture_argv'][7] = '/opt/observer/dosbox'
        recipe['dosbox_argv'][0] = '/opt/observer/dosbox'
        validate_capture_recipe(recipe, trace)

    def test_provenance_cli_failure_preserves_reports(self):
        original = json.loads((FIXTURES / 'r3-recipe.json').read_text())
        controls = [(key, '0' * 64) for key in CAPTURE_HASHES]
        controls += [('assets', {}), ('process_memory_writes', 1)]
        with tempfile.TemporaryDirectory(prefix='lezac-work-provenance-cli-') as temporary:
            folder = Path(temporary)
            recipe, output = folder / 'recipe.json', folder / 'report.json'
            command = [sys.executable, '-S', '-B', str(ROOT / 'tools/analyze_original_work_clock.py'),
                       str(FIXTURES / 'r3.csv.gz'), str(output), '--recipe', str(recipe)]
            for key, value in controls:
                recipe.write_text(json.dumps(dict(original, **{key: value})))
                result = subprocess.run(command, capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())
                output.write_bytes(b'retained provenance report\n')
                result = subprocess.run(command, capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output.read_bytes(), b'retained provenance report\n')
                output.unlink()

    def test_raw_and_compressed_profiles_match(self):
        with tempfile.TemporaryDirectory(prefix='lezac-work-clock-') as directory:
            path = Path(directory) / 'trace.csv'
            path.write_bytes(self.raw)
            self.assertEqual(analyze(path), self.manifest['runs'][0]['profile'])

    def test_trace_rejection_controls(self):
        cases = []

        def alter(label, kind, field, value):
            rows = copy.deepcopy(self.rows)
            row = next(item for item in rows if item['kind'] == kind)
            row[field] = value(row[field]) if callable(value) else value
            cases.append((label, rows))

        alter('unknown marker', 'horizontal', 'kind', 'cap')
        alter('wrong budget', 'horizontal', 'cycle_max', 5999)
        alter('negative dispatch', 'identified', 'dispatch', -1)
        alter('bad DAC', 'identified', 'dac', 'x' * 42)
        alter('word overflow', 'horizontal', 'phase', 65536)
        alter('fraction overflow', 'horizontal', 'fraction', 32768)
        alter('missing frame', 'horizontal', 'frame_valid', 0)
        alter('wrong pixel instruction', 'horizontal', 'ip', 0x252)
        alter('post-color cursor', 'write', 'phase', lambda value: value + 1)
        alter('horizontal cost', 'row_check', 'exclusive_dispatch', lambda value: value + 1)
        alter('horizontal cursor', 'row_check', 'fraction', lambda value: value + 1)
        alter('color cost', 'write', 'exclusive_dispatch', lambda value: value + 1)
        alter('write cost', 'after_write', 'exclusive_dispatch', lambda value: value + 1)
        alter('tail cost', 'tail', 'exclusive_dispatch', lambda value: value + 1)
        alter('row software work', 'row_work', 'exclusive_dispatch', lambda value: value + 1)
        alter('wrong finish instruction', 'finish', 'ip', 0x30a)
        alter('unfinished destination', 'finish', 'destination', 63999)
        alter('bad parameters', 'finish', 'h', 81)
        alter('IRQ leak', 'irq8_return', 'exclusive_dispatch', lambda value: value + 1)
        alter('IRQ mismatch', 'irq8_return', 'kind', 'irq9_return')
        alter('IRQ depth', 'irq8_enter', 'irq_depth', 2)
        alter('delay input', 'delay_end', 'delay_argument', lambda value: value + 1)
        alter('delay dispatch', 'delay_end', 'exclusive_dispatch', lambda value: value + 1)
        cases.append(('missing clean exit', copy.deepcopy(self.rows[:-1])))
        cases.append(('missing identification', copy.deepcopy(self.rows[1:])))
        cases.append(('duplicate exit', copy.deepcopy(self.rows + [self.rows[-1]])))
        rows = copy.deepcopy(self.rows)
        row = next(item for item in rows if item['kind'] == 'horizontal')
        rows.insert(rows.index(row), copy.deepcopy(row))
        cases.append(('duplicate pixel', rows))
        rows = copy.deepcopy(self.rows)
        rows.remove(next(item for item in rows if item['kind'] == 'horizontal'))
        cases.append(('missing pixel', rows))
        cases.append(('cycles used as dispatches', [dict(row, exclusive_dispatch=row['exclusive_clock']) for row in self.rows]))
        rows = copy.deepcopy(self.rows)
        clear = next(row for row in rows if row['kind'] == 'clear_return')
        ready = next(row for row in rows if row['kind'] == 'palette_ready')
        clear['kind'], ready['kind'] = ready['kind'], clear['kind']
        clear['ip'], ready['ip'] = ready['ip'], clear['ip']
        cases.append(('swapped fill boundaries', rows))
        with tempfile.TemporaryDirectory(prefix='lezac-work-mutants-') as directory:
            for index, (label, rows) in enumerate(cases):
                with self.subTest(label=label):
                    path = Path(directory) / f'{index}.csv'
                    with path.open('w', newline='') as stream:
                        writer = csv.DictWriter(stream, COLUMNS, lineterminator='\n')
                        writer.writeheader()
                        writer.writerows(rows)
                    with self.assertRaises(ValueError):
                        analyze(path)
        self.assertEqual(len(cases), 30)

    def test_malformed_streams(self):
        cases = [self.raw.replace(b'kind,page,', b'kind,pages,', 1),
                 self.raw + b'cap\n', self.raw[:-30], b'\xff' + self.raw,
                 self.raw.replace(b'identified,0,', b'identified,no,', 1)]
        with tempfile.TemporaryDirectory(prefix='lezac-work-malformed-') as directory:
            for index, raw in enumerate(cases):
                path = Path(directory) / f'{index}.csv'
                path.write_bytes(raw)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    analyze(path)

    def test_decompression_reserve(self):
        with tempfile.TemporaryDirectory(prefix='lezac-work-reserve-') as directory:
            path = Path(directory) / 'oversized.csv.gz'
            path.write_bytes(gzip.compress(b'x' * (6 * 1024 * 1024 + 1), mtime=0))
            with self.assertRaisesRegex(ValueError, 'Expanded trace exceeds size limit'):
                analyze(path)
            path = Path(directory) / 'oversized.csv'
            path.write_bytes(b'x' * (6 * 1024 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, 'Trace file exceeds size limit'):
                analyze(path)

if __name__ == '__main__':
    unittest.main()
