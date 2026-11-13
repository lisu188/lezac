"""Original integrity, host recipes and synthetic parser/failure controls."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import natural_level4_bridge_escape as recovered


class BridgeEscapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = recovered.fixture()
        cls.metadata = recovered.manifest()
        cls.audit = json.loads(gzip.decompress((recovered.EVIDENCE / 'native-audit.json.gz').read_bytes()))
        cls.capture = json.loads(gzip.decompress((recovered.EVIDENCE / 'capture-report.json.gz').read_bytes()))
        cls.binding = json.loads(gzip.decompress((recovered.EVIDENCE / 'host-binding.json.gz').read_bytes()))
        cls.stimulus = recovered.handoff.load(recovered.FIXTURE / 'guard-inputs.jsonl.gz')[-1]['state']

    def test_original_window_and_endpoint(self):
        self.assertEqual(len(self.rows), 1524)
        self.assertEqual(self.rows[-2]['projection']['mapped']['players'][0]['xy'], [770.0, 360.0])
        self.assertFalse(self.rows[0]['level4_completion_claim'])
        self.assertTrue(all(gzip.decompress((recovered.FIXTURE / 'reference.jsonl.gz').read_bytes()).splitlines()))

    def test_reference_mutations_rejected(self):
        for control in ('missing', 'duplicate', 'phase', 'tick', 'projection', 'rgb', 'footer', 'sequence'):
            rows, audit = list(self.rows), copy.deepcopy(self.audit)
            rows[1] = copy.deepcopy(rows[1])
            if control == 'missing':
                rows.pop(1)
            elif control == 'duplicate':
                rows.insert(1, copy.deepcopy(rows[1]))
            elif control == 'phase':
                rows[1]['phase'] = 'post_update'
            elif control == 'tick':
                rows[1]['index'] += 1
            elif control == 'projection':
                rows[1]['projection']['mapped']['players'][0]['energy'] += 1
            elif control == 'rgb':
                rows[1]['rgb_sha256'] = '0' * 64
            elif control == 'footer':
                rows[-1] = dict(rows[-1], patches_restored=False)
            else:
                audit['records'][1]['native_sequence'] += 1
            with self.subTest(control=control), self.assertRaises(ValueError):
                recovered.validate(rows, self.metadata, audit)

    def test_scope_inflation_rejected(self):
        for field in (*recovered.CLAIMS, 'cpp_expectations_used', 'gameplay_state_injections', 'full_ds_snapshots_published'):
            rows, metadata = list(self.rows), copy.deepcopy(self.metadata)
            rows[0] = copy.deepcopy(rows[0])
            rows[0][field] = True
            metadata['reference_header'] = rows[0]
            with self.subTest(field=field), self.assertRaises(ValueError):
                recovered.validate(rows, metadata, self.audit)

    def test_host_recipe_mutations_rejected(self):
        for control in ('host', 'actual_host', 'argv', 'cwd', 'config', 'loader', 'asset', 'asset_domain',
                        'prefix_guest', 'prefix_source', 'prefix_settings', 'prefix_rng', 'prefix_scope',
                        'prefix_draws', 'prefix_ticks', 'geometry', 'audio', 'scratch', 'closure',
                        'injections', 'producer', 'handoff', 'window'):
            binding, capture = copy.deepcopy(self.binding), copy.deepcopy(self.capture)
            if control == 'host':
                binding['host']['sha256'] = '0' * 64
            elif control == 'actual_host':
                binding['actual_host_sha256'] = '0' * 64
            elif control == 'argv':
                binding['argv'].append('unexpected')
            elif control == 'cwd':
                binding['cwd'] = '/tmp'
            elif control in ('config', 'loader'):
                binding[control + '_sha256'] = '0' * 64
            elif control == 'asset':
                binding['copied_assets']['LIVELS.SCH']['sha256'] = '0' * 64
            elif control == 'asset_domain':
                binding['canonical_source_assets'].pop('SETUP.LOG')
            elif control == 'prefix_guest':
                binding['prefix_header']['exe_sha256'] = '0' * 64
            elif control == 'prefix_source':
                binding['prefix_header']['source_sha256'] = '0' * 64
            elif control == 'prefix_settings':
                binding['prefix_header']['settings']['seed'] ^= 1
            elif control == 'prefix_rng':
                binding['prefix_header']['initial_rng'] ^= 1
            elif control == 'prefix_scope':
                binding['prefix_header']['original_fidelity_claim'] = True
            elif control == 'prefix_draws':
                binding['prefix_header']['preview_draws'] += 1
            elif control == 'prefix_ticks':
                binding['prefix_header']['prefix_ticks'] += 1
            elif control == 'geometry':
                binding['geometry']['WIDTH'] = '319'
            elif control == 'audio':
                binding['environment']['SDL_AUDIODRIVER'] = 'default'
            elif control == 'scratch':
                binding['environment']['TMPDIR'] = '/tmp'
            elif control == 'closure':
                capture['owned_child_terminal'] = False
            elif control == 'injections':
                capture['gameplay_state_injections'] = True
            elif control == 'producer':
                capture['observer_sha256'] = '0' * 64
            elif control == 'handoff':
                capture['handoffs'][0]['intro_rng'] ^= 1
            else:
                capture['first_full_frame_tick'] += 1
            with self.subTest(control=control), self.assertRaises(ValueError):
                recovered.validate_capture(self.metadata, capture, binding)

    def test_pinned_bytes_rejected(self):
        for field, directory in (('FIXTURE', recovered.FIXTURE), ('EVIDENCE', recovered.EVIDENCE)):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for path in directory.iterdir():
                    shutil.copyfile(path, root / path.name)
                names = ('route.txt', 'reference.jsonl.gz', 'guard-inputs.jsonl.gz') if field == 'FIXTURE' else (
                    'native-audit.json.gz', 'capture-level4-final-t302.py.gz', 'rea-byte-checks.json.gz')
                with mock.patch.object(recovered, field, root):
                    for name in names:
                        path = root / name
                        raw = path.read_bytes()
                        for damaged in (raw[:-1], raw + b'\0', bytes([raw[0] ^ 1]) + raw[1:]):
                            path.write_bytes(damaged)
                            with self.subTest(name=name), self.assertRaises(ValueError):
                                recovered.fixture()
                        path.write_bytes(raw)

    def test_cpp_stimuli_never_change_reference(self):
        path = recovered.FIXTURE / 'reference.jsonl.gz'
        before = path.read_bytes()
        result = recovered.guard()
        self.assertEqual((result['stimuli'], result['typed_mutations_rejected']), (4, 66))
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(self.metadata['guard_input_source']['expected_bytes_source'])

    def parser_case(self, control=None):
        # Synthetic frames isolate parser behavior without generating original expectations.
        pixels = b'pixel'
        seed, step = 305441741, 40800
        with tempfile.TemporaryDirectory() as temporary:
            case = Path(temporary)
            run = case / 'run'
            run.mkdir()
            (case / 'route.txt').write_bytes(b'synthetic parser control')
            header = dict(kind='header', schema='lezac.level1.scout.v1', source='cpp', capture_from_tick=1, ticks=2,
                phase_model='cpp-pre-actors-v2', state_scope='level1-observations-v2',
                input_model='sdl-events-original-intro-wait-v1', seed=seed, step_us=step,
                route_fnv1a64=recovered.fidelity.fnv1a64((case / 'route.txt').read_bytes()),
                asset_fnv1a64={}, width=320, height=200, candidate_only=True, original_fidelity_claim=False)
            trace, expected = [header], [{}]
            for tick in (1, 2):
                for phase in ('input', 'present', 'after_nonplayers', 'post_update'):
                    state = copy.deepcopy(self.stimulus)
                    state['logic_tick'] = tick
                    row = dict(kind='checkpoint', seq=len(trace) - 1, tick=tick, phase=phase,
                               time_ms=(tick - 1) * step // 1000, events=[], state=state)
                    if phase in ('present', 'post_update'):
                        projection = recovered.support.recovered.cpp_projection(state, self.rows[-2]['projection'])
                        expected.append(dict(section='level4', index=tick, phase=phase, projection=projection,
                            rgb_sha256=hashlib.sha256(pixels).hexdigest() if phase == 'present' else None))
                    if phase == 'present':
                        row.update(frame=f'frame_{tick:06d}.ppm', rgb_fnv1a64=recovered.fidelity.fnv1a64(pixels))
                        (run / row['frame']).write_bytes(b'placeholder frame')
                    trace.append(row)
            trace.append(dict(kind='complete', ticks=2, frames=2, retained_checkpoints=8, checkpoints=8,
                events=0, capture_from_tick=1, candidate_only=True, level1_route_complete=True,
                original_fidelity_claim=False, port_functionally_complete=False))
            expected.append({})
            if control in ('missing_actor', 'missing_present', 'missing_post'):
                trace.pop({'missing_actor': 3, 'missing_present': 2, 'missing_post': 4}[control])
                for index, row in enumerate(trace[1:-1]):
                    row['seq'] = index
                trace[-1].update(retained_checkpoints=7, checkpoints=7)
            elif control == 'phase':
                trace[3]['phase'] = 'input'
            elif control == 'time':
                trace[5]['time_ms'] += 1
            elif control == 'input':
                trace[5]['events'] = [dict(action='down', key='n')]
            elif control == 'sequence':
                trace[5]['seq'] += 1
            elif control == 'extra_key':
                trace[5]['unqualified'] = True
            elif control == 'header':
                header['whole_game_fidelity_claim'] = True
            elif control == 'header_seed':
                header['seed'] ^= 1
            elif control == 'header_source':
                header['source'] = 'original'
            elif control == 'route':
                header['route_fnv1a64'] = '0' * 16
            elif control == 'footer':
                trace[-1]['events'] = 1
            elif control == 'footer_count':
                trace[-1]['retained_checkpoints'] -= 1
            elif control == 'extra_footer_key':
                trace[-1]['whole_game_fidelity_claim'] = True
            elif control == 'after_footer':
                trace.append(copy.deepcopy(trace[-2]))
            elif control == 'health':
                trace[8]['state']['players'][0]['health'][0] += 1
            elif control == 'rgb_updated_checksum':
                trace[6]['rgb_fnv1a64'] = recovered.fidelity.fnv1a64(b'wrong')
            elif control == 'rgb_filename':
                trace[6]['frame'] = 'frame_000001.ppm'
            (run / 'trace.jsonl').write_text('\n'.join(json.dumps(row) for row in trace) + '\n')
            with mock.patch.object(recovered, 'FIRST', 1), mock.patch.object(recovered, 'LAST', 2), \
                 mock.patch.object(recovered, 'FRAMES', 2), mock.patch.object(recovered, 'fixture', return_value=expected), \
                 mock.patch.object(recovered, 'check_route', return_value=(dict(seed=seed, step_us=step), {})), \
                 mock.patch.object(recovered.fidelity, 'ASSETS', ()), \
                 mock.patch.object(recovered.fidelity, 'read_ppm', side_effect=lambda path:
                     b'wrong' if control == 'rgb_updated_checksum' and path.name == 'frame_000002.ppm' else pixels):
                return recovered.compare(case)

    def test_parser_positive(self):
        result = self.parser_case()
        self.assertEqual((result['frames'], result['boundaries'], result['checkpoints']), (2, 4, 8))

    def test_parser_mutations(self):
        for control in ('missing_actor', 'missing_present', 'missing_post', 'phase', 'time', 'input', 'sequence',
                        'extra_key', 'header', 'header_seed', 'header_source', 'route', 'footer', 'footer_count',
                        'extra_footer_key', 'after_footer', 'health', 'rgb_updated_checksum', 'rgb_filename'):
            with self.subTest(control=control), self.assertRaises(ValueError):
                self.parser_case(control)

    def test_failed_and_timed_out_children_keep_reports(self):
        for timeout in (False, True):
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                exe = root / 'stub.exe'
                exe.write_bytes(b'never executed: child is mocked')
                child = mock.Mock(returncode=3, stdout='kept stdout', stderr='kept stderr')
                error = subprocess.TimeoutExpired('mocked', 550, output=b'kept stdout', stderr=b'kept stderr')
                with mock.patch.object(recovered.subprocess, 'run', side_effect=error if timeout else None,
                    return_value=child), self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                    recovered.replay(exe, root / 'out')
                case = next((root / 'out').glob('run-*'))
                self.assertEqual(json.loads((case / 'comparison.json').read_bytes())['status'], 'failed')
                self.assertEqual((case / 'stdout.txt').read_text(), 'kept stdout')
                self.assertEqual((case / 'stderr.txt').read_text(), 'kept stderr')
                result = json.loads((case / 'child-result.json').read_bytes())
                self.assertEqual(result, dict(exit_code=None, timed_out=True) if timeout else dict(exit_code=3))

    def test_preflight_failures_keep_reports_without_child(self):
        original_hash = recovered.fidelity.sha256
        for control in ('missing_executable', 'missing_asset', 'unreadable_asset'):
            with self.subTest(control=control), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                exe = root / 'stub.exe'
                if control != 'missing_executable':
                    exe.write_bytes(b'never executed')
                def checked_hash(path):
                    if control == 'unreadable_asset' and Path(path).name == 'LEZAC.EXE':
                        raise PermissionError('unreadable canonical asset')
                    return original_hash(path)
                assets = ('missing-asset.bin',) if control == 'missing_asset' else recovered.fidelity.ASSETS
                with mock.patch.object(recovered.fidelity, 'ASSETS', assets), \
                     mock.patch.object(recovered.fidelity, 'sha256', side_effect=checked_hash), \
                     mock.patch.object(recovered.subprocess, 'run') as child, self.assertRaises((ValueError, OSError)):
                    recovered.replay(exe, root / 'out')
                child.assert_not_called()
                case = next((root / 'out').glob('run-*'))
                self.assertEqual(json.loads((case / 'comparison.json').read_bytes())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
