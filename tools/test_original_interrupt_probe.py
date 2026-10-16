"""Pinned IRQ trace contracts; no emulator or Pillow is required by CI."""
import ast
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
from types import SimpleNamespace
import unittest

from original_interrupt_probe.analyze import FLAGS, ROOT, analyze, trace_bytes

FIXTURE = ROOT / 'tests/fixtures/interrupt_dispatch'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


class OriginalInterruptProbeTests(unittest.TestCase):
    def setUp(self):
        self.raw = trace_bytes(FIXTURE / 'rank8.csv.gz')
        self.recipe = json.loads((FIXTURE / 'rank8-recipe.json').read_text())
        self.executable = (ROOT / 'LEZAC.EXE').read_bytes()

    def test_frozen_manifest(self):
        raw = (FIXTURE / 'manifest.json').read_bytes()
        self.assertEqual(SHA(raw), 'afeaaade936412fab208507cef4a2ad57146bceb92470819473a32bd4ea64d52')
        manifest = json.loads(raw)
        self.assertEqual((manifest['cases'], manifest['trace_rows']), (2, 1752))
        for key in ('raw_ram_published', 'raw_vga_published', 'screenshots_published',
                    'fixture_pixel_replay_claim', 'full_app_claim', 'whole_game_parity'):
            self.assertIs(manifest[key], False)
        for item in manifest['files']:
            value = (FIXTURE / item['name']).read_bytes()
            self.assertEqual((len(value), SHA(value)), (item['bytes'], item['sha256']))
        self.assertEqual(SHA(self.executable), manifest['original_executable_sha256'])
        self.assertEqual(manifest['capture_contract_sha256'], SHA((ROOT / 'tools/original_capture_contract.py').read_bytes()))
        for key, name in [('probe_sha256', 'lezac_work_probe.h'), ('producer_sha256', 'capture.py')]:
            self.assertEqual(manifest[key], SHA((ROOT / 'tools/original_interrupt_probe' / name).read_bytes()))

    def test_original_traces(self):
        results = []
        for case in ('rank8', 'rank7'):
            raw = trace_bytes(FIXTURE / (case + '.csv.gz'))
            recipe = json.loads((FIXTURE / (case + '-recipe.json')).read_text())
            result, _ = analyze(raw, recipe, self.executable)
            self.assertIs(result['vga_files_verified'], False)
            results.append(result)
        self.assertEqual(results, json.loads((FIXTURE / 'replays.json').read_text()))
        self.assertEqual(results[0]['destination'], 39578)
        self.assertEqual(results[0]['exception_entries'], 65)
        self.assertTrue(results[0]['bios_ticks_frozen'])
        self.assertFalse(results[1]['bios_ticks_frozen'])
        print('original_interrupt_trace=ok cases=2 rows=1752 exception_entries=65 raw_vga_verified=0 full_app_claim=0')

    def test_typed_capture_scope(self):
        for key, expected in FLAGS.items():
            missing = dict(self.recipe)
            del missing[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                analyze(self.raw, missing, self.executable)
            values = [not expected, None] if type(expected) is bool else [expected + 1, False, None]
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    analyze(self.raw, dict(self.recipe, **{key: value}), self.executable)

    def test_profile_and_input_rejections(self):
        controls = []
        for key in ('dosbox_sha256', 'producer_sha256', 'executable_sha256'):
            controls.append(dict(self.recipe, **{key: '0' * 64}))
        for value in [('sbtype=none', 'sbtype=sb16'), ('output=surface', 'output=opengl')]:
            controls.append(dict(self.recipe, dosbox_config=self.recipe['dosbox_config'].replace(*value)))
        changed = copy.deepcopy(self.recipe)
        changed['dosbox_environment']['SDL_VIDEODRIVER'] = 'dummy'
        controls.append(changed)
        changed = copy.deepcopy(self.recipe)
        changed['host_commands'].append(dict(changed['host_commands'][-1], command=['xdotool', 'key', 'Left']))
        controls.append(changed)
        changed = copy.deepcopy(self.recipe)
        changed['events'][0]['monotonic_after'] = changed['host_commands'][4]['monotonic_before']
        controls.append(changed)
        changed = copy.deepcopy(self.recipe)
        changed['samples'][0]['name'] = '../outside'
        controls.append(changed)
        changed = copy.deepcopy(self.recipe)
        changed['samples'][0]['ram_rgb_cpu_atomic'] = True
        controls.append(changed)
        changed = copy.deepcopy(self.recipe)
        changed['host_build']['probe_sha256'] = '0' * 64
        controls.append(changed)
        for key, value in [('dosbox_cwd', '/tmp/not-ram'), ('code_segment', True), ('data_segment', 0)]:
            controls.append(dict(self.recipe, **{key: value}))
        for key in ('HOME', 'TMPDIR', 'LEZAC_IRQ_TRACE'):
            changed = copy.deepcopy(self.recipe)
            changed['dosbox_environment'][key] += '-different-run'
            controls.append(changed)
        changed = copy.deepcopy(self.recipe)
        changed['dosbox_argv'].extend(['-c', 'other.exe'])
        controls.append(changed)
        changed = copy.deepcopy(self.recipe)
        changed['dosbox_argv'][4] += '-different-run'
        controls.append(changed)
        changed = copy.deepcopy(self.recipe)
        changed['host_commands'][2]['stdout'] = 'bogus'
        controls.append(changed)
        changed = copy.deepcopy(self.recipe)
        changed['assets']['LIVELS.SCH']['sha256'] = '0' * 64
        controls.append(changed)
        controls.append(dict(self.recipe, capture_contract_sha256='0' * 64))
        for index, changed in enumerate(controls):
            with self.subTest(control=index), self.assertRaises(ValueError):
                analyze(self.raw, changed, self.executable)

    def test_malformed_trace_rejections(self):
        rows = list(csv.DictReader(io.StringIO(self.raw[:-4].decode('ascii'))))
        controls = [('kind', 'unexpected'), ('opcode', '00'), ('opcode', '00' * 8),
                    ('stack', '00'), ('adjacent', '00'), ('dispatch', '-1'),
                    ('control_flags', '65535'), ('cycle_max', '5999')]
        for key, value in controls:
            changed = copy.deepcopy(rows)
            changed[0][key] = value
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(changed)
            raw = (buffer.getvalue() + 'end\n').encode('ascii')
            recipe = dict(self.recipe, trace_bytes=len(raw), trace_sha256=SHA(raw))
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                analyze(raw, recipe, self.executable)
        for raw in (self.raw[:-4], self.raw + b'cap\n'):
            with self.assertRaises(ValueError):
                analyze(raw, dict(self.recipe, trace_bytes=len(raw), trace_sha256=SHA(raw)), self.executable)
        with self.assertRaises(ValueError):
            analyze(trace_bytes(FIXTURE / 'rank7.csv.gz'), self.recipe, self.executable)

    def test_cli_failure_keeps_reports(self):
        with tempfile.TemporaryDirectory(prefix='lezac-irq-reject-') as temporary:
            root = Path(temporary)
            recipe = dict(self.recipe, host_commands=self.recipe['host_commands'] + [
                dict(self.recipe['host_commands'][-1], command=['xdotool', 'key', 'Left'])])
            bad = root / 'recipe.json'
            bad.write_text(json.dumps(recipe))
            output = root / 'report.json'
            command = [sys.executable, '-S', '-B', str(ROOT / 'tools/original_interrupt_probe/analyze.py'),
                '--trace', str(FIXTURE / 'rank8.csv.gz'), '--recipe', str(bad), '--out', str(output)]
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('IRQ input commands differ', result.stderr)
            self.assertFalse(output.exists())
            output.write_bytes(b'retained report\n')
            result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b'retained report\n')

    def test_capture_terminal_failure_persists_report(self):
        source = (ROOT / 'tools/original_interrupt_probe/capture.py').read_text()
        tree = ast.parse(source)
        finalizers = [node.finalbody for node in tree.body if isinstance(node, ast.Try) and
            any(isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name) and
                target.id == 'terminal_errors' for target in statement.targets)
                for statement in node.finalbody)]
        self.assertEqual(len(finalizers), 1)
        code = compile(ast.Module(body=finalizers[0], type_ignores=[]), '<capture-finalizer>', 'exec')
        for failure in ('missing-trace', 'missing-end', 'exit-code', 'asset-change', 'short-vga', None):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(prefix='lezac-irq-terminal-') as temporary:
                root = Path(temporary)
                output = root / 'capture'
                output.mkdir()
                (root / 'asset.dat').write_bytes(b'original')
                assets = {'asset.dat': {'sha256': SHA(b'original')}}
                if failure != 'missing-trace':
                    (output / 'guest-irq.csv').write_bytes(b'trace\n' if failure == 'missing-end' else b'trace\nend\n')
                if failure == 'asset-change':
                    (root / 'asset.dat').write_bytes(b'changed')
                if failure == 'short-vga':
                    (output / 'guest-irq.csv.vga-00.bin').write_bytes(b'incomplete')
                report = dict(status='observed', passed=True, samples=[])
                persisted = []

                def persist():
                    persisted.append(copy.deepcopy(report))
                    (output / 'report.json').write_text(json.dumps(report))

                namespace = dict(OUT=output, ROOT=root, assets=assets, report=report, sha=SHA,
                    child=SimpleNamespace(returncode=1 if failure == 'exit-code' else 0, poll=lambda: 0),
                    mem=None, log=None, persist=persist, json=json)
                if failure:
                    with self.assertRaises(RuntimeError):
                        exec(code, namespace)
                else:
                    exec(code, namespace)
                self.assertEqual(len(persisted), 1)
                saved = json.loads((output / 'report.json').read_text())
                self.assertEqual(saved, persisted[0])
                self.assertEqual(saved['status'], 'failed' if failure else 'observed')
                self.assertIs(saved['passed'], failure is None)
                if failure:
                    self.assertTrue(saved['terminal_validation_errors'])
                    self.assertTrue(saved['error'])


if __name__ == '__main__':
    unittest.main()
