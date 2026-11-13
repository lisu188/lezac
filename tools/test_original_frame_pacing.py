"""Frozen original-pacing fixture contract and malformed-trace controls."""
import copy
import configparser
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

from analyze_original_frame_pacing import CAPTURE_CONFIG, CAPTURE_ENVIRONMENT, CAPTURE_HASHES, analyze
from original_capture_contract import ASSET_PINS

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/frame_pacing'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


class OriginalFramePacingTests(unittest.TestCase):
    def test_fixture_contract(self):
        raw = (FIXTURE / 'manifest.json').read_bytes()
        self.assertEqual(SHA(raw), '64fb11f77053cbcad274082c9d11122747573270dd09e42c80abc762d0cb91fe')
        manifest = json.loads(raw)
        for item in manifest['files']:
            value = (FIXTURE / item['name']).read_bytes()
            self.assertEqual((len(value), SHA(value)), (item['bytes'], item['sha256']))
        self.assertEqual(manifest['executable_sha256'], SHA((ROOT / 'LEZAC.EXE').read_bytes()))
        self.assertEqual(manifest['capture_producer_sha256'], SHA((ROOT / 'tools/frame_pacing_probe/capture.py').read_bytes()))
        self.assertEqual(manifest['host_probe_sha256'], SHA((ROOT / 'tools/frame_pacing_probe/lezac_work_probe.h').read_bytes()))
        self.assertEqual(manifest['capture_contract_sha256'], SHA((ROOT / 'tools/original_capture_contract.py').read_bytes()))
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
        self.assertEqual(sum(run['completed_frames'] for run in actual), 294)
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

    def test_complete_capture_profile(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        controls = []
        def configured(config):
            stream = io.StringIO()
            config.write(stream)
            return dict(recipe, dosbox_config=stream.getvalue())
        for section, settings in CAPTURE_CONFIG.items():
            for key in settings:
                for missing in (False, True):
                    config = configparser.ConfigParser()
                    config.read_string(recipe['dosbox_config'])
                    if missing:
                        del config[section][key]
                    else:
                        config[section][key] = 'contradiction'
                    controls.append(configured(config))
            config = configparser.ConfigParser()
            config.read_string(recipe['dosbox_config'])
            del config[section]
            controls.append(configured(config))
        for suffix in ('\n[extra]\nkey=value\n', '\n[DEFAULT]\nkey=value\n',
                       '\n[sdl]\noutput=opengl\n'):
            controls.append(dict(recipe, dosbox_config=recipe['dosbox_config'] + suffix))
        config = configparser.ConfigParser()
        config.read_string(recipe['dosbox_config'])
        config['cpu']['unrecognized'] = 'value'
        controls.append(configured(config))
        for key in CAPTURE_ENVIRONMENT:
            controls.append(dict(recipe, dosbox_environment=dict(recipe['dosbox_environment'], **{key: 'contradiction'})))
        for key in recipe['dosbox_environment']:
            for value in (None, False, 0, ''):
                controls.append(dict(recipe, dosbox_environment=dict(recipe['dosbox_environment'], **{key: value})))
            missing = dict(recipe['dosbox_environment'])
            del missing[key]
            controls.append(dict(recipe, dosbox_environment=missing))
        self.assertEqual(len(controls), 90)
        for index, changed in enumerate(controls):
            with self.subTest(control=index), self.assertRaises(ValueError):
                analyze(raw, changed)

    def test_input_command_sequence_binding(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        controls = []
        extra = dict(recipe['host_commands'][-1], command=['xdotool', 'key', '--clearmodifiers', 'Left'])
        for index in range(13):
            commands = copy.deepcopy(recipe['host_commands'])
            commands.insert(index, extra)
            controls.append(dict(recipe, host_commands=commands))
        for index in range(12):
            commands = copy.deepcopy(recipe['host_commands'])
            del commands[index]
            controls.append(dict(recipe, host_commands=commands))
        for index in range(11):
            commands = copy.deepcopy(recipe['host_commands'])
            commands[index], commands[index + 1] = commands[index + 1], commands[index]
            controls.append(dict(recipe, host_commands=commands))
        for index in (4, 7, 11):
            commands = copy.deepcopy(recipe['host_commands'])
            commands[index]['command'][-1] = 'Left'
            controls.append(dict(recipe, host_commands=commands))
        self.assertEqual(len(controls), 39)
        for index, changed in enumerate(controls):
            with self.subTest(control=index), self.assertRaises(ValueError):
                analyze(raw, changed)

    def test_input_command_targets_and_intervals(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        controls = []
        for key, values in [('child_pid', [True, 0, str(recipe['child_pid']), None])]:
            controls.extend(dict(recipe, **{key: value}) for value in values)
        for value in ['', 'not-a-window', '0', False]:
            changed = copy.deepcopy(recipe)
            changed['host_commands'][0]['stdout'] = value
            controls.append(changed)
        for key, value in [('exit_code', False), ('exit_code', 1), ('monotonic_before', False),
                           ('monotonic_before', -1), ('monotonic_before', float('nan')),
                           ('monotonic_after', float('inf')), ('monotonic_after', 0)]:
            changed = copy.deepcopy(recipe)
            changed['host_commands'][4][key] = value
            controls.append(changed)
        for key, value in [('monotonic_before', 1000), ('monotonic_after', 0)]:
            changed = copy.deepcopy(recipe)
            changed['events'][0][key] = value
            controls.append(changed)
        changed = copy.deepcopy(recipe)
        changed['events'][0]['monotonic_after'] = changed['host_commands'][4]['monotonic_before']
        controls.append(changed)
        changed = copy.deepcopy(recipe)
        changed['samples'][0]['monotonic_after'] = changed['host_commands'][2]['monotonic_before']
        controls.append(changed)
        self.assertEqual(len(controls), 19)
        for index, changed in enumerate(controls):
            with self.subTest(control=index), self.assertRaises(ValueError):
                analyze(raw, changed)

    def test_canonical_asset_recipe_controls(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        controls = []
        for name, (size, _) in ASSET_PINS.items():
            for key, value in [('sha256', '0' * 64), ('sha256', None), ('bytes', size + 1),
                               ('bytes', False), ('bytes', None)]:
                changed = copy.deepcopy(recipe)
                changed['assets'][name][key] = value
                controls.append(changed)
            changed = copy.deepcopy(recipe)
            del changed['assets'][name]
            controls.append(changed)
        self.assertEqual(len(controls), 84)
        for index, changed in enumerate(controls):
            with self.subTest(control=index), self.assertRaises(ValueError):
                analyze(raw, changed)
        for value in (None, False, '0' * 64):
            with self.subTest(contract=value), self.assertRaises(ValueError):
                analyze(raw, dict(recipe, capture_contract_sha256=value))

    def test_geometry_recipe_controls(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        controls = []
        for index in (2, 5, 8, 9, 10):
            original = recipe['host_commands'][index]['stdout']
            values = [None, '', 'bogus', original.replace('WIDTH=320', 'WIDTH=640'),
                original.replace('HEIGHT=200', 'HEIGHT=400'), original + 'WIDTH=320\n',
                original.replace('SCREEN=0', 'SCREEN=1'), original.replace('WINDOW=', 'WINDOW=1')]
            for value in values:
                changed = copy.deepcopy(recipe)
                changed['host_commands'][index]['stdout'] = value
                controls.append(changed)
        self.assertEqual(len(controls), 40)
        for index, changed in enumerate(controls):
            with self.subTest(control=index), self.assertRaises(ValueError):
                analyze(raw, changed)

    def test_launch_command_and_path_binding(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        controls = []
        for key in ('dosbox_argv', 'dosbox_cwd', 'capture_argv'):
            for value in (None, False, '', [], ['/tmp/evil'], '/unrelated'):
                controls.append(dict(recipe, **{key: value}))
            missing = dict(recipe)
            del missing[key]
            controls.append(missing)
        for index in range(len(recipe['dosbox_argv'])):
            changed = copy.deepcopy(recipe)
            changed['dosbox_argv'][index] = '/tmp/evil'
            controls.append(changed)
        for index in range(len(recipe['capture_argv'])):
            changed = copy.deepcopy(recipe)
            changed['capture_argv'][index] = '/tmp/evil'
            controls.append(changed)
        for key in ('HOME', 'TMPDIR', 'LEZAC_PACING_TRACE'):
            changed = copy.deepcopy(recipe)
            changed['dosbox_environment'][key] = '/dev/shm/unrelated'
            controls.append(changed)
        for value in ('/dev/shm/x/../run', '/dev/shm//run', '/dev/shm/x y', '/dev/shm/x/./run',
                      '/dev/shm/run/', '/dev/shm/run;evil', '/dev/shm/run\n'):
            controls.append(dict(recipe, dosbox_cwd=value))
        for key in ('dosbox_argv', 'capture_argv'):
            changed = copy.deepcopy(recipe)
            changed[key] = tuple(changed[key])
            controls.append(changed)
            changed = copy.deepcopy(recipe)
            changed[key].append('extra')
            controls.append(changed)
        self.assertEqual(len(controls), 54)
        for index, changed in enumerate(controls):
            with self.subTest(control=index), self.assertRaises(ValueError):
                analyze(raw, changed)

    @staticmethod
    def relocated_sources(recipe, repo, host):
        changed = copy.deepcopy(recipe)
        changed['capture_argv'][0] = repo + '/tools/frame_pacing_probe/capture.py'
        changed['capture_argv'][5] = repo
        changed['capture_argv'][7] = host
        changed['dosbox_argv'][0] = host
        return changed

    def test_documented_and_relocated_source_paths(self):
        for run in ('r2', 'r3'):
            raw = (FIXTURE / (run + '.csv')).read_bytes()
            recipe = json.loads((FIXTURE / (run + '-recipe.json')).read_text())
            expected = analyze(raw, recipe)
            for repo in ('/workspace/lezac', '/mnt/c/Users/andrz/git/LEZAC',
                         '/workspace/project with spaces'):
                for host in ('/dev/shm/pacing-host/src/dosbox', '/opt/observers/dosbox',
                             '/opt/custom probe/renamed-observer'):
                    with self.subTest(run=run, repo=repo, host=host):
                        self.assertEqual(analyze(raw, self.relocated_sources(recipe, repo, host)), expected)

    def test_noncanonical_source_paths_remain_rejected(self):
        raw = (FIXTURE / 'r2.csv').read_bytes()
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        for value in ('relative', '../relative', '/workspace/../other', '/workspace//other',
                      '/workspace/./other', '/workspace/other/', '//workspace/other',
                      '/workspace/other\n', '/workspace/other\0'):
            for kind in ('repo', 'host'):
                changed = self.relocated_sources(recipe,
                    value if kind == 'repo' else '/workspace/lezac',
                    value if kind == 'host' else '/dev/shm/pacing-host/src/dosbox')
                with self.subTest(kind=kind, value=value), self.assertRaises(ValueError):
                    analyze(raw, changed)

    def test_cli_accepts_documented_source_paths(self):
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        relocated = self.relocated_sources(recipe, '/workspace/lezac', '/dev/shm/pacing-host/src/dosbox')
        with tempfile.TemporaryDirectory(prefix='lezac-pacing-valid-source-') as temporary:
            folder = Path(temporary)
            recipe_path, output = folder / 'recipe.json', folder / 'report.json'
            recipe_path.write_text(json.dumps(relocated))
            result = subprocess.run([sys.executable, '-S', '-B', str(ROOT / 'tools/analyze_original_frame_pacing.py'),
                str(FIXTURE / 'r2.csv'), '--recipe', str(recipe_path), '--out', str(output)],
                capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text()), analyze((FIXTURE / 'r2.csv').read_bytes(), recipe))

    def test_cli_rejects_invalid_recipe_without_publishing_report(self):
        recipe = json.loads((FIXTURE / 'r2-recipe.json').read_text())
        extra = dict(recipe['host_commands'][-1], command=['xdotool', 'key', '--clearmodifiers', 'Left'])
        with tempfile.TemporaryDirectory(prefix='lezac-pacing-recipe-') as temporary:
            folder = Path(temporary)
            bad_recipe = folder / 'recipe.json'
            for index, (key, value, reason) in enumerate([
                    ('host_probe_guest_memory_writes', 1, 'Read-only guest provenance differs'),
                    ('host_instrumented', False, 'Capture mode claims differ'),
                    ('dosbox_sha256', '0' * 64, 'Capture host or producer differs'),
                    ('producer_sha256', None, 'Capture host or producer differs'),
                    ('dosbox_config', recipe['dosbox_config'].replace('sbtype=none', 'sbtype=sb16'), 'Wrong capture profile'),
                    ('dosbox_environment', dict(recipe['dosbox_environment'], SDL_VIDEODRIVER='dummy'),
                     'Unexpected emulator environment'),
                    ('host_commands', recipe['host_commands'] + [extra], 'Input command sequence differs'),
                    ('assets', dict(recipe['assets'], **{'LIVELS.SCH': dict(recipe['assets']['LIVELS.SCH'], sha256='0' * 64)}),
                     'Canonical original asset differs'),
                    ('host_commands', [dict(command, stdout='bogus') if command['command'][1] == 'getwindowgeometry'
                                      else command for command in recipe['host_commands']], 'Capture geometry output differs'),
                    ('dosbox_argv', ['/tmp/evil'], 'DOSBox launch command differs'),
                    ('dosbox_cwd', '/unrelated', 'DOSBox launch path differs')]):
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
