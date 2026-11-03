"""Original integrity and isolated synthetic parser/failure controls."""
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

import natural_level4_left_return as recovered


class LeftReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = recovered.fixture()
        cls.metadata = recovered.manifest()
        load = lambda name: json.loads(gzip.decompress((recovered.EVIDENCE / name).read_bytes()))
        cls.audit = load('native-audit.json.gz')
        cls.capture = load('capture-report.json.gz')
        cls.binding = load('host-binding.json.gz')
        cls.retained = recovered.handoff.load(recovered.EVIDENCE / 'lossless-retention.jsonl.gz')
        cls.stimulus = recovered.handoff.load(recovered.FIXTURE / 'guard-inputs.jsonl.gz')[-1]['state']

    def validate(self, rows=None, audit=None, capture=None, retained=None):
        recovered.validate(self.rows if rows is None else rows, self.metadata,
            self.audit if audit is None else audit, self.capture if capture is None else capture,
            self.retained if retained is None else retained)

    def test_original_window_and_endpoint(self):
        self.assertEqual(len(self.rows), 3524)
        self.assertEqual(self.rows[-2]['projection']['mapped']['players'][0]['xy'], [13.0, 344.0])
        self.assertFalse(self.rows[0]['level4_completion_claim'])
        self.assertEqual((len(self.capture['checkpoints']), len(self.retained)), (3528, 7056))

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
                self.validate(rows=rows, audit=audit)

    def test_live_and_lossless_receipt_mutations_rejected(self):
        tick, phase = recovered.LAST, 'present'
        for control in ('live_rgb', 'live_ds', 'live_sequence', 'live_player', 'boundary_hash', 'boundary_length',
                        'ds_hash', 'ds_length', 'readback', 'encoded_extent', 'duplicate', 'missing'):
            capture, retained = copy.deepcopy(self.capture), copy.deepcopy(self.retained)
            live = next(row for row in capture['checkpoints'] if (row['tick'], row['phase']) == (tick, phase))
            boundary = next(row for row in retained if row['path'] == f'boundary-{tick}-{phase}.json.gz')
            ds = next(row for row in retained if row['path'] == f'ds-{tick}-{phase}.bin.gz')
            if control == 'live_rgb':
                live['rgb_sha256'] = '0' * 64
            elif control == 'live_ds':
                live['ds_sha256'] = '0' * 64
            elif control == 'live_sequence':
                live['sequence'] += 1
            elif control == 'live_player':
                live['mapped']['players'][0]['energy'] += 1
            elif control == 'boundary_hash':
                boundary['source_sha256'] = '0' * 64
            elif control == 'boundary_length':
                boundary['source_bytes'] += 1
            elif control == 'ds_hash':
                ds['source_sha256'] = '0' * 64
            elif control == 'ds_length':
                ds['source_bytes'] -= 1
            elif control == 'readback':
                ds['readback_equal'] = False
            elif control == 'encoded_extent':
                ds['encoded_bytes'] = ds['source_bytes'] + 129
            elif control == 'duplicate':
                retained.append(copy.deepcopy(retained[-1]))
            else:
                retained.pop()
            with self.subTest(control=control), self.assertRaises(ValueError):
                self.validate(capture=capture, retained=retained)

    def test_scope_inflation_rejected(self):
        for field in (*recovered.CLAIMS, 'cpp_expectations_used', 'gameplay_state_injections', 'full_ds_snapshots_published'):
            rows, metadata = list(self.rows), copy.deepcopy(self.metadata)
            rows[0] = copy.deepcopy(rows[0])
            rows[0][field] = True
            metadata['reference_header'] = rows[0]
            with self.subTest(field=field), self.assertRaises(ValueError):
                recovered.validate(rows, metadata, self.audit, self.capture, self.retained)

    def test_capture_recipe_mutations_rejected(self):
        for control in ('host', 'argv', 'cwd', 'config', 'loader', 'asset', 'prefix_rng', 'prefix_source',
                        'geometry', 'audio', 'video', 'scratch', 'closure', 'producer', 'window', 'storage', 'full_frame'):
            capture, binding = copy.deepcopy(self.capture), copy.deepcopy(self.binding)
            if control == 'host':
                binding['actual_host_sha256'] = '0' * 64
            elif control == 'argv':
                binding['argv'].append('unexpected')
            elif control == 'cwd':
                binding['cwd'] = '/tmp'
            elif control in ('config', 'loader'):
                binding[control + '_sha256'] = '0' * 64
            elif control == 'asset':
                binding['copied_assets']['LIVELS.SCH']['sha256'] = '0' * 64
            elif control == 'prefix_rng':
                binding['prefix_header']['initial_rng'] ^= 1
            elif control == 'prefix_source':
                binding['prefix_header']['source_sha256'] = '0' * 64
            elif control == 'geometry':
                binding['geometry']['WIDTH'] = '319'
            elif control == 'audio':
                binding['environment']['SDL_AUDIODRIVER'] = 'default'
            elif control == 'video':
                binding['environment']['SDL_VIDEODRIVER'] = 'dummy'
            elif control == 'scratch':
                binding['environment']['TMPDIR'] = '/tmp'
            elif control == 'closure':
                capture['owned_child_terminal'] = False
            elif control == 'producer':
                capture['observer_sha256'] = '0' * 64
            elif control == 'window':
                capture['last_full_frame_tick'] -= 1
            elif control == 'storage':
                capture['snapshot_storage'] = 'unverified'
            else:
                capture['full_frame_claim'] = True
            with self.subTest(control=control), self.assertRaises(ValueError):
                recovered.validate_capture(self.metadata, capture, binding)

    def test_pinned_bytes_rejected(self):
        for field, directory in (('FIXTURE', recovered.FIXTURE), ('EVIDENCE', recovered.EVIDENCE)):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for path in directory.iterdir():
                    shutil.copyfile(path, root / path.name)
                names = ('route.txt', 'reference.jsonl.gz', 'guard-inputs.jsonl.gz') if field == 'FIXTURE' else (
                    'native-audit.json.gz', 'lossless-retention.jsonl.gz', 'capture-left-return-t305.py.gz')
                with mock.patch.object(recovered, field, root):
                    for name in names:
                        path = root / name
                        raw = path.read_bytes()
                        for damaged in (raw[:-1], raw + b'\0', bytes((raw[0] ^ 1,)) + raw[1:]):
                            path.write_bytes(damaged)
                            with self.subTest(name=name), self.assertRaises(ValueError):
                                recovered.fixture()
                        path.write_bytes(raw)

    def test_cpp_stimuli_never_change_original_expectations(self):
        path = recovered.FIXTURE / 'reference.jsonl.gz'
        before = path.read_bytes()
        report = recovered.guard()
        self.assertEqual((report['stimuli'], report['typed_mutations_rejected']), (2, 28))
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(self.metadata['guard_input_source']['expected_bytes_source'])

    def parser_case(self, control=None):
        pixels = b'isolated synthetic parser pixels'
        seed, step = 305441741, 40800
        with tempfile.TemporaryDirectory() as temporary:
            case = Path(temporary)
            run = case / 'run'
            run.mkdir()
            (case / 'route.txt').write_bytes(b'synthetic parser route')
            header = dict(kind='header', schema='lezac.level1.scout.v1', source='cpp', capture_from_tick=1, ticks=2,
                phase_model='cpp-pre-actors-v2', state_scope='level1-observations-v2', input_model='sdl-events-original-intro-wait-v1',
                seed=seed, step_us=step, route_fnv1a64=recovered.fidelity.fnv1a64((case / 'route.txt').read_bytes()),
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
                        (run / row['frame']).write_bytes(b'placeholder')
                    trace.append(row)
            trace.append(dict(kind='complete', ticks=2, frames=2, retained_checkpoints=8, checkpoints=8, events=0,
                capture_from_tick=1, candidate_only=True, level1_route_complete=True,
                original_fidelity_claim=False, port_functionally_complete=False))
            expected.append({})
            if control in ('missing_actor', 'missing_present', 'missing_post'):
                trace.pop({'missing_actor': 3, 'missing_present': 2, 'missing_post': 4}[control])
            elif control == 'phase':
                trace[3]['phase'] = 'input'
            elif control == 'time':
                trace[5]['time_ms'] += 1
            elif control == 'input':
                trace[5]['events'] = [dict(action='down', key='n')]
            elif control == 'sequence':
                trace[5]['seq'] += 1
            elif control == 'extra_key':
                trace[5]['unexpected'] = True
            elif control == 'header':
                header['original_fidelity_claim'] = True
            elif control == 'route':
                header['route_fnv1a64'] = '0' * 16
            elif control == 'footer':
                trace[-1]['frames'] -= 1
            elif control == 'after_footer':
                trace.append(copy.deepcopy(trace[-2]))
            elif control == 'health':
                trace[8]['state']['players'][0]['health'][0] += 1
            elif control == 'rgb_updated_checksum':
                trace[6]['rgb_fnv1a64'] = recovered.fidelity.fnv1a64(b'wrong')
            (run / 'trace.jsonl').write_text('\n'.join(json.dumps(row) for row in trace) + '\n')
            with mock.patch.object(recovered, 'FIRST', 1), mock.patch.object(recovered, 'LAST', 2), \
                    mock.patch.object(recovered, 'fixture', return_value=expected), \
                    mock.patch.object(recovered, 'check_route', return_value=(dict(seed=seed, step_us=step, ticks=2), {})), \
                    mock.patch.object(recovered.fidelity, 'read_route', return_value=(dict(seed=seed, step_us=step, ticks=2), {})), \
                    mock.patch.object(recovered.fidelity, 'ASSETS', ()), \
                    mock.patch.object(recovered.fidelity, 'read_ppm', side_effect=lambda path:
                        b'wrong' if control == 'rgb_updated_checksum' and path.name == 'frame_000002.ppm' else pixels):
                return recovered.compare(case, first=1, last=2)

    def test_parser_positive(self):
        report = self.parser_case()
        self.assertEqual((report['frames'], report['boundaries'], report['checkpoints']), (2, 4, 8))

    def test_parser_mutations_rejected(self):
        for control in ('missing_actor', 'missing_present', 'missing_post', 'phase', 'time', 'input', 'sequence',
                        'extra_key', 'header', 'route', 'footer', 'after_footer', 'health', 'rgb_updated_checksum'):
            with self.subTest(control=control), self.assertRaises(ValueError):
                self.parser_case(control)

    def test_failed_and_timed_out_children_keep_reports(self):
        for timeout in (False, True):
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                exe = root / 'stub.exe'
                exe.write_bytes(b'not executed')
                child = mock.Mock(returncode=3, stdout='kept stdout', stderr='kept stderr')
                error = subprocess.TimeoutExpired('mocked', 600, output=b'kept stdout', stderr=b'kept stderr')
                with mock.patch.object(recovered, 'fixture', return_value=[]), \
                        mock.patch.object(recovered.subprocess, 'run', side_effect=error if timeout else None, return_value=child), \
                        self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                    recovered.replay(exe, root / 'out')
                case = next((root / 'out').iterdir())
                self.assertEqual(json.loads((case / 'comparison.json').read_bytes())['status'], 'failed')
                self.assertIn(b'kept stdout', (case / 'stdout.txt').read_bytes())
                self.assertIn(b'kept stderr', (case / 'stderr.txt').read_bytes())


if __name__ == '__main__':
    unittest.main()
