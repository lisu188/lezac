"""Original integrity and synthetic parser controls; never original expectations."""
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

import natural_level4_outside_column as recovered


class OutsideColumnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = recovered.fixture()
        cls.metadata = recovered.manifest()
        cls.audit = json.loads(gzip.decompress((recovered.EVIDENCE / 'native-audit.json.gz').read_bytes()))
        cls.stimulus = recovered.handoff.load(recovered.FIXTURE / 'guard-inputs.jsonl.gz')[-1]['state']
        cls.repeat_binding = json.loads(gzip.decompress((recovered.EVIDENCE / 'repeat-host-binding.json.gz').read_bytes()))
        cls.repeat_capture = json.loads(gzip.decompress((recovered.EVIDENCE / 'repeat-capture-report.json.gz').read_bytes()))
        cls.repeat_audit = json.loads(gzip.decompress((recovered.EVIDENCE / 'repeat-audit.json.gz').read_bytes()))
        cls.repeat_config = (recovered.EVIDENCE / 'repeat-dosbox.conf').read_bytes()

    def test_original_window_and_scope(self):
        self.assertEqual(len(self.rows), 1604)
        self.assertEqual(self.rows[-2]['projection']['mapped']['progress'], [3, 261])
        self.assertEqual(self.metadata['raw_ds_snapshot_retention'], 'RAM-only; not claimed durably retained')
        self.assertFalse(self.rows[0]['full_ds_snapshots_published'])
        self.assertFalse(self.rows[0]['all_actor_fields_compared'])
        self.assertTrue(all(gzip.decompress((recovered.FIXTURE / 'reference.jsonl.gz').read_bytes()).splitlines()))

    def test_native_reference_mutations_rejected(self):
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

    def test_scope_inflation_rejected_even_with_matching_header(self):
        for field in (*recovered.CLAIMS, 'cpp_expectations_used', 'gameplay_state_injections', 'full_ds_snapshots_published'):
            rows, metadata = list(self.rows), copy.deepcopy(self.metadata)
            rows[0] = copy.deepcopy(rows[0])
            rows[0][field] = True
            metadata['reference_header'] = rows[0]
            with self.subTest(field=field), self.assertRaises(ValueError):
                recovered.validate(rows, metadata, self.audit)

    def test_fixture_byte_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in recovered.FIXTURE.iterdir():
                shutil.copyfile(path, root / path.name)
            for name in self.metadata['fixture_pins']:
                raw = (root / name).read_bytes()
                for damaged in (raw[:-1], raw + b'\0', bytes([raw[0] ^ 1]) + raw[1:]):
                    (root / name).write_bytes(damaged)
                    with self.subTest(name=name), self.assertRaises(ValueError):
                        recovered.fixture(root)
                (root / name).write_bytes(raw)

    def test_cpp_stimuli_are_separate_and_reference_unchanged(self):
        self.assertFalse(self.metadata['guard_input_source']['expected_bytes_source'])
        self.assertFalse(set(self.metadata['producer_pins']) & set(self.metadata['guard_producer_pins']))
        before = recovered.fidelity.sha256(recovered.FIXTURE / 'reference.jsonl.gz')
        report = recovered.guard()
        self.assertEqual((report['stimuli'], report['typed_mutations_rejected']), (3, 53))
        self.assertEqual(before, recovered.fidelity.sha256(recovered.FIXTURE / 'reference.jsonl.gz'))

    def test_frozen_evidence_byte_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in recovered.EVIDENCE.iterdir():
                shutil.copyfile(path, root / path.name)
            with mock.patch.object(recovered, 'EVIDENCE', root):
                for name in ('native-audit.json.gz', 'capture-level4-outside-pillar-t299.py.gz', 'rea-byte-checks.json.gz'):
                    path = root / name
                    raw = path.read_bytes()
                    path.write_bytes(raw + b'\0')
                    with self.subTest(name=name), self.assertRaises(ValueError):
                        recovered.fixture()
                    path.write_bytes(raw)

    def test_host_bound_repeat_recipe_mutations_rejected(self):
        for control in ('host', 'actual_host', 'argv', 'cwd', 'config', 'loader', 'asset', 'asset_domain',
                        'prefix_guest', 'prefix_producer', 'prefix_settings', 'prefix_rng', 'prefix_scope',
                        'geometry', 'audio', 'scratch', 'closure',
                        'injections', 'producer', 'rgb', 'projection', 'sequence', 'extent'):
            binding, capture, audit = (copy.deepcopy(value) for value in
                                       (self.repeat_binding, self.repeat_capture, self.repeat_audit))
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
            elif control == 'prefix_producer':
                binding['prefix_header']['source_sha256'] = '0' * 64
            elif control == 'prefix_settings':
                binding['prefix_header']['settings']['seed'] ^= 1
            elif control == 'prefix_rng':
                binding['prefix_header']['initial_rng'] ^= 1
            elif control == 'prefix_scope':
                binding['prefix_header']['original_fidelity_claim'] = True
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
            elif control == 'rgb':
                audit['records'][0]['rgb_sha256'] = '0' * 64
            elif control == 'projection':
                audit['records'][0]['projection_sha256'] = '0' * 64
            elif control == 'sequence':
                audit['records'][1]['native_sequence'] += 1
            else:
                audit['records'].pop()
            with self.subTest(control=control), self.assertRaises(ValueError):
                recovered.validate_repeat(binding, capture, audit, self.metadata, self.rows, self.repeat_config)

    def test_failed_child_keeps_diagnostics(self):
        self.check_failed_child(False)

    def test_timed_out_child_keeps_diagnostics(self):
        self.check_failed_child(True)

    def test_preflight_failures_keep_report_without_launching(self):
        real_sha256 = recovered.fidelity.sha256
        for control in ('missing_executable', 'missing_asset', 'unreadable_asset'):
            with self.subTest(control=control), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                exe = root / 'stub.exe'
                if control != 'missing_executable':
                    exe.write_bytes(b'never executed')

                def checked_hash(path):
                    if control == 'unreadable_asset' and Path(path).name == 'LEZAC.EXE':
                        raise PermissionError('unreadable original asset')
                    return real_sha256(path)

                names = ('missing-original-asset.bin',) if control == 'missing_asset' else recovered.fidelity.ASSETS
                with mock.patch.object(recovered.fidelity, 'ASSETS', names), \
                     mock.patch.object(recovered.fidelity, 'sha256', side_effect=checked_hash), \
                     mock.patch.object(recovered.subprocess, 'run') as child, \
                     self.assertRaises((ValueError, OSError)):
                    recovered.replay(exe, root / 'output')
                child.assert_not_called()
                case = next((root / 'output').glob('run-*'))
                report = json.loads((case / 'comparison.json').read_text())
                self.assertEqual(report['status'], 'failed')
                self.assertFalse(report['original_fidelity_claim'])
                self.assertTrue(report['error'])

    def check_failed_child(self, timed_out):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exe = root / 'stub.exe'
            exe.write_bytes(b'not executed: subprocess mocked')
            result = mock.Mock(returncode=3, stdout='kept stdout', stderr='kept stderr')
            timeout = subprocess.TimeoutExpired('mocked', 550, output=b'kept stdout', stderr=b'kept stderr')
            with mock.patch.object(recovered.subprocess, 'run', side_effect=timeout if timed_out else None,
                                   return_value=result) as run, self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                recovered.replay(exe, root / 'output')
            case = next((root / 'output').glob('run-*'))
            self.assertEqual((case / 'stdout.txt').read_text(), 'kept stdout')
            self.assertEqual((case / 'stderr.txt').read_text(), 'kept stderr')
            self.assertEqual(json.loads((case / 'comparison.json').read_text())['status'], 'failed')
            child = json.loads((case / 'child-result.json').read_text())
            self.assertEqual(child, dict(exit_code=None, timed_out=True) if timed_out else dict(exit_code=3))
            self.assertEqual(run.call_args.kwargs['env']['SDL_AUDIODRIVER'], 'dummy')

    def parser_case(self, control=None):
        # Two synthetic frames isolate parser contracts. No fixture bytes are generated.
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
            if control in ('missing_actor', 'missing_present'):
                trace.pop(3 if control == 'missing_actor' else 2)
                for index, row in enumerate(trace[1:-1]):
                    row['seq'] = index
                trace[-1].update(retained_checkpoints=7, checkpoints=7)
            elif control == 'extra_after_footer':
                trace.append(copy.deepcopy(trace[-2]))
            elif control == 'wrong_phase':
                trace[3]['phase'] = 'input'
            elif control == 'wrong_time':
                trace[5]['time_ms'] += 1
            elif control == 'wrong_input':
                trace[5]['events'] = [dict(action='down', key='n')]
            elif control == 'extra_field':
                trace[5]['unqualified'] = True
            elif control == 'wrong_sequence':
                trace[5]['seq'] += 1
            elif control == 'footer':
                trace[-1]['events'] = 1
            elif control == 'route':
                header['route_fnv1a64'] = '0' * 16
            elif control == 'header_claim':
                header['original_fidelity_claim'] = True
            elif control == 'header_extra_claim':
                header['gameplay_state_injections'] = True
            elif control == 'footer_extra_claim':
                trace[-1]['whole_game_fidelity_claim'] = True
            elif control == 'health':
                trace[8]['state']['players'][0]['health'][0] += 1
            elif control == 'counter':
                trace[8]['state']['logic_tick'] += 1
            elif control == 'rgb_updated_checksum':
                trace[6]['rgb_fnv1a64'] = recovered.fidelity.fnv1a64(b'wrong')
            (run / 'trace.jsonl').write_text('\n'.join(json.dumps(row) for row in trace) + '\n')
            with mock.patch.object(recovered, 'FIRST', 1), mock.patch.object(recovered, 'LAST', 2), \
                 mock.patch.object(recovered, 'FRAMES', 2), mock.patch.object(recovered, 'fixture', return_value=expected), \
                 mock.patch.object(recovered, 'check_route', return_value=(dict(seed=seed, step_us=step), {})), \
                 mock.patch.object(recovered.fidelity, 'ASSETS', ()), \
                 mock.patch.object(recovered.fidelity, 'read_ppm', side_effect=lambda path:
                     b'wrong' if control == 'rgb_updated_checksum' and path.name == 'frame_000002.ppm' else pixels):
                return recovered.compare(case)

    def test_synthetic_parser_positive(self):
        report = self.parser_case()
        self.assertEqual((report['frames'], report['boundaries'], report['checkpoints']), (2, 4, 8))
        self.assertFalse(report['original_fidelity_claim'])

    def test_missing_and_reordered_boundaries_rejected(self):
        for control in ('missing_actor', 'missing_present', 'wrong_phase', 'wrong_sequence', 'extra_after_footer'):
            with self.subTest(control=control), self.assertRaises(ValueError):
                self.parser_case(control)

    def test_inputs_provenance_and_footer_rejected(self):
        for control in ('wrong_time', 'wrong_input', 'extra_field', 'footer', 'route', 'header_claim',
                        'header_extra_claim', 'footer_extra_claim'):
            with self.subTest(control=control), self.assertRaises(ValueError):
                self.parser_case(control)

    def test_projected_state_mutations_rejected(self):
        for control in ('health', 'counter'):
            with self.subTest(control=control), self.assertRaisesRegex(ValueError, 'projection differs'):
                self.parser_case(control)

    def test_changed_pixel_with_updated_frame_checksum_rejected(self):
        with self.assertRaisesRegex(ValueError, 'original RGB differs'):
            self.parser_case('rgb_updated_checksum')


if __name__ == '__main__':
    unittest.main()
