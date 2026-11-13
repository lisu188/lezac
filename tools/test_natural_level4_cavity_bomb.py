"""Original fixture integrity and isolated synthetic bomb/trace failure controls."""
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

import natural_level4_cavity_bomb as recovered


class CavityBombTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = recovered.fixture()
        cls.metadata = recovered.manifest()
        cls.load = staticmethod(lambda name: json.loads(gzip.decompress(
            (recovered.EVIDENCE / (name + '.gz')).read_bytes())))
        cls.sources = recovered.handoff.load(recovered.EVIDENCE / 'original-reference.jsonl.gz')
        cls.capture = cls.load('capture-report.json')
        cls.audit = cls.load('native-audit.json')
        cls.readback = cls.load('complete-readback.json')
        cls.retained = recovered.handoff.load(recovered.EVIDENCE / 'lossless-retention.jsonl.gz')
        # These records are parser stimuli only, never original expectations.
        cls.stimulus = recovered.handoff.load(recovered.ROOT /
            'tests/fixtures/natural_level4_left_return/guard-inputs.jsonl.gz')[-1]['state']

    def validate(self, **changes):
        values = {key: getattr(self, key) for key in
            ('rows', 'metadata', 'sources', 'capture', 'audit', 'retained', 'readback')}
        values.update(changes)
        recovered.validate(**values)

    def test_original_extent_and_scope(self):
        self.assertEqual(len(self.rows), 2004)
        active = [row for row in self.rows[1:-1] if row['projection']['bombs']]
        self.assertEqual(len(active), 118)
        self.assertEqual((active[0]['index'], active[-1]['index']), (14503, 14562))
        self.assertEqual(self.rows[-2]['projection']['mapped']['progress'], [3, 280])
        self.assertTrue(all(self.rows[0][key] is False for key in recovered.CLAIMS))
        self.assertFalse(self.metadata['raw_ds_snapshots_published'])
        self.assertFalse(self.metadata['screenshots_published'])
        self.assertFalse(self.metadata['route_planning_stimulus']['expected_bytes_source'])
        self.assertFalse(any(path.suffix in ('.png', '.ppm', '.bin') for directory in
            (recovered.FIXTURE, recovered.EVIDENCE) for path in directory.iterdir()))

    def test_reference_mutations_rejected(self):
        for control in ('missing', 'duplicate', 'phase', 'tick', 'projection', 'rgb', 'ds', 'footer', 'bomb_birth'):
            rows = list(self.rows)
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
            elif control in ('rgb', 'ds'):
                rows[1]['rgb_sha256' if control == 'rgb' else 'native_ds_sha256'] = '0' * 64
            elif control == 'footer':
                rows[-1] = dict(rows[-1], patches_restored=False)
            else:
                index = next(i for i, row in enumerate(rows[1:-1], 1) if row['projection']['bombs'])
                rows[index] = copy.deepcopy(rows[index])
                rows[index]['projection']['bombs'][0]['counter'] -= 1
            with self.subTest(control=control), self.assertRaises(ValueError):
                self.validate(rows=rows)

    def test_scope_inflation_rejected(self):
        for field in (*recovered.CLAIMS, 'cpp_expectations_used', 'gameplay_state_injections',
                      'raw_ds_snapshots_published', 'screenshots_published'):
            rows, metadata = list(self.rows), copy.deepcopy(self.metadata)
            rows[0] = dict(rows[0], **{field: True})
            metadata['reference_header'] = rows[0]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(rows=rows, metadata=metadata)

    def test_original_source_role_and_binding_rejected(self):
        for control in ('source_role', 'source_projection', 'audit_sequence', 'audit_ds', 'audit_closure',
                        'capture_rgb', 'capture_sequence', 'capture_player', 'capture_closure', 'capture_observer'):
            sources, audit, capture = list(self.sources), copy.deepcopy(self.audit), copy.deepcopy(self.capture)
            sources[0], sources[1] = copy.deepcopy(sources[0]), copy.deepcopy(sources[1])
            if control == 'source_role':
                sources[0]['cpp_expectations_used'] = True
            elif control == 'source_projection':
                sources[1]['projection']['mapped']['rng'] ^= 1
            elif control == 'audit_sequence':
                audit['records'][0]['sequence'] += 1
            elif control == 'audit_ds':
                audit['records'][0]['ds_sha256'] = '0' * 64
            elif control == 'audit_closure':
                audit['capture_request_complete'] = False
            elif control == 'capture_closure':
                capture['owned_child_terminal'] = False
            elif control == 'capture_observer':
                capture['observer_sha256'] = '0' * 64
            else:
                live = next(row for row in capture['checkpoints'] if
                    (row['tick'], row['phase']) == (recovered.FIRST, 'present'))
                if control == 'capture_rgb':
                    live['rgb_sha256'] = '0' * 64
                elif control == 'capture_sequence':
                    live['sequence'] += 1
                else:
                    live['mapped']['players'][0]['energy'] += 1
            with self.subTest(control=control), self.assertRaises(ValueError):
                self.validate(sources=sources, audit=audit, capture=capture)

    def test_complete_private_readback_receipts_rejected(self):
        for control in ('missing', 'duplicate', 'ds_length', 'encoded_length', 'readback', 'hash', 'proof', 'proof_role'):
            retained, readback = copy.deepcopy(self.retained), copy.deepcopy(self.readback)
            ds = next(row for row in retained if row['path'].startswith('ds-'))
            if control == 'missing':
                retained.pop()
            elif control == 'duplicate':
                retained.append(copy.deepcopy(ds))
            elif control == 'ds_length':
                ds['source_bytes'] -= 1
            elif control == 'encoded_length':
                ds['encoded_bytes'] = ds['source_bytes'] + 129
            elif control == 'readback':
                ds['readback_equal'] = False
            elif control == 'hash':
                ds['source_sha256'] = '0' * 64
            elif control == 'proof':
                readback['members'][0]['complete_byte_readback'] = False
            else:
                readback['cpp_expected_values_used'] = True
            with self.subTest(control=control), self.assertRaises(ValueError):
                self.validate(retained=retained, readback=readback)

    def test_pinned_files_deleted_or_changed_rejected(self):
        for field, directory, names in (
            ('FIXTURE', recovered.FIXTURE, ('route.txt', 'reference.jsonl.gz')),
            ('EVIDENCE', recovered.EVIDENCE, ('manifest.json', 'native-audit.json.gz',
                'complete-readback.json.gz', 'bomb_state_projection.py.gz'))):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for path in directory.iterdir():
                    shutil.copyfile(path, root / path.name)
                with mock.patch.object(recovered, field, root):
                    for name in names:
                        path, raw = root / name, (root / name).read_bytes()
                        for damaged in (None, raw[:-1], raw + b'\0'):
                            if damaged is None:
                                path.unlink()
                            else:
                                path.write_bytes(damaged)
                            with self.subTest(name=name, missing=damaged is None), self.assertRaises((ValueError, OSError)):
                                recovered.fixture()
                        path.write_bytes(raw)

    def test_host_binding_mutations_rejected(self):
        original_decompress = gzip.decompress
        raw = original_decompress((recovered.EVIDENCE / 'host-binding.json.gz').read_bytes())
        for control in ('host', 'argv', 'cwd', 'geometry', 'audio', 'config', 'loader', 'source', 'asset'):
            binding = json.loads(raw)
            if control == 'host':
                binding['actual_host_sha256'] = '0' * 64
            elif control == 'argv':
                binding['argv'].append('unexpected')
            elif control == 'cwd':
                binding['cwd'] = '/tmp'
            elif control == 'geometry':
                binding['geometry']['WIDTH'] = '319'
            elif control == 'audio':
                binding['environment']['SDL_AUDIODRIVER'] = 'default'
            elif control in ('config', 'loader'):
                binding[control + '_sha256'] = '0' * 64
            elif control == 'source':
                binding['prefix_header']['source_sha256'] = '0' * 64
            else:
                binding['copied_assets']['LIVELS.SCH']['sha256'] = '0' * 64

            def decompress(value):
                decoded = original_decompress(value)
                return json.dumps(binding).encode() if decoded == raw else decoded

            with self.subTest(control=control), mock.patch.object(gzip, 'decompress', side_effect=decompress), \
                    self.assertRaises(ValueError):
                recovered.fixture()

    def test_canonical_asset_failure_rejected_and_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(recovered, 'ROOT', root), self.assertRaises(ValueError):
                recovered.replay(root / 'missing.exe', root / 'out')
            report = next((root / 'out').glob('run-*/comparison.json'))
            self.assertEqual(json.loads(report.read_bytes())['status'], 'failed')

    def test_bomb_mutations_and_odd_fuse_mapping(self):
        before = (recovered.FIXTURE / 'reference.jsonl.gz').read_bytes()
        self.assertEqual(len(recovered.bombs.guard()), 14)
        bomb = dict(order=1, visual_order=0, owner=1, type=1,
            position=[0, 0, 210, 360, 0], motion=[0, -500, 0, 0, 1], fuse=[59, 60])
        self.assertEqual(recovered.bombs.cpp_bombs(dict(bombs=[bomb]))[0]['counter'], 30)
        for mutate in (lambda b: b.__setitem__('order', True),
                       lambda b: b['motion'].__setitem__(0, False),
                       lambda b: b['fuse'].__setitem__(0, 0),
                       lambda b: b['motion'].__setitem__(2, 65536)):
            changed = copy.deepcopy(bomb)
            mutate(changed)
            with self.assertRaises(ValueError):
                recovered.bombs.cpp_bombs(dict(bombs=[changed]))
        with self.assertRaises(ValueError):
            recovered.bombs.cpp_bombs(dict(bombs=[bomb, bomb]))
        self.assertEqual((recovered.FIXTURE / 'reference.jsonl.gz').read_bytes(), before)

    def parser_case(self, control=None):
        pixels, seed, step = b'isolated synthetic RGB', 305441741, 40800
        with tempfile.TemporaryDirectory() as temporary:
            case = Path(temporary)
            (case / 'run').mkdir()
            (case / 'route.txt').write_bytes(b'isolated parser route')
            header = dict(kind='header', schema='lezac.level1.scout.v1', source='cpp', capture_from_tick=1, ticks=2,
                phase_model='cpp-pre-actors-v2', state_scope='level1-observations-v2', input_model='sdl-events-original-intro-wait-v1',
                seed=seed, step_us=step, route_fnv1a64=recovered.fidelity.fnv1a64((case / 'route.txt').read_bytes()),
                asset_fnv1a64={}, width=320, height=200, candidate_only=True, original_fidelity_claim=False)
            trace, expected = [header], {}
            for tick in (1, 2):
                for phase in ('input', 'present', 'after_nonplayers', 'post_update'):
                    state = copy.deepcopy(self.stimulus)
                    state['logic_tick'] = tick
                    row = dict(kind='checkpoint', seq=len(trace) - 1, tick=tick, phase=phase,
                        time_ms=(tick - 1) * step // 1000, events=[], state=state)
                    if phase in ('present', 'post_update'):
                        expected[tick, phase] = dict(bombs=recovered.bombs.cpp_bombs(state),
                            rgb_sha256=hashlib.sha256(pixels).hexdigest() if phase == 'present' else None)
                    if phase == 'present':
                        row.update(frame=f'frame_{tick:06d}.ppm', rgb_fnv1a64=recovered.fidelity.fnv1a64(pixels))
                        (case / 'run' / row['frame']).write_bytes(b'placeholder')
                    trace.append(row)
            trace.append(dict(kind='complete', ticks=2, frames=2, retained_checkpoints=8, checkpoints=8, events=0,
                capture_from_tick=1, candidate_only=True, level1_route_complete=True,
                original_fidelity_claim=False, port_functionally_complete=False))
            if control in ('missing_input', 'missing_present', 'missing_actor', 'missing_post'):
                trace.pop(dict(missing_input=1, missing_present=2, missing_actor=3, missing_post=4)[control])
            elif control in ('phase', 'time', 'input', 'sequence', 'first_sequence', 'extra_key'):
                if control == 'phase':
                    trace[3]['phase'] = 'input'
                elif control == 'time':
                    trace[5]['time_ms'] += 1
                elif control == 'input':
                    trace[5]['events'] = [dict(action='down', key='n')]
                elif control == 'sequence':
                    trace[5]['seq'] += 1
                elif control == 'first_sequence':
                    trace[1]['seq'] = False
                else:
                    trace[5]['unexpected'] = True
            elif control == 'header':
                header['original_fidelity_claim'] = True
            elif control == 'header_bool':
                header['capture_from_tick'] = True
            elif control == 'tick_bool':
                trace[1]['tick'] = True
            elif control == 'time_bool':
                trace[1]['time_ms'] = False
            elif control == 'route':
                header['route_fnv1a64'] = '0' * 16
            elif control == 'footer':
                trace[-1]['frames'] -= 1
            elif control == 'footer_type':
                trace[-1]['events'] = False
            elif control == 'after_footer':
                trace.append(copy.deepcopy(trace[-2]))
            elif control == 'no_footer':
                trace.pop()
            elif control == 'non_object':
                trace[3] = []
            elif control == 'rgb_updated_checksum':
                trace[6]['rgb_fnv1a64'] = recovered.fidelity.fnv1a64(b'wrong')
            raw = '\n'.join(json.dumps(row) for row in trace) + '\n'
            if control == 'empty':
                raw = ''
            (case / 'run/trace.jsonl').write_text(raw)
            with mock.patch.object(recovered.fidelity, 'ASSETS', ()), \
                    mock.patch.object(recovered.fidelity, 'read_ppm', side_effect=lambda path:
                        b'wrong' if control == 'rgb_updated_checksum' and path.name == 'frame_000002.ppm' else pixels):
                return recovered.compare_window(case, first=1, last=2, settings=dict(seed=seed, step_us=step),
                    events={}, expected=expected, asset_root=case,
                    compare_state=lambda state, row: recovered.bombs.compare(state, row['bombs']))

    def test_parser_positive(self):
        report = self.parser_case()
        self.assertEqual((report['frames'], report['boundaries'], report['checkpoints']), (2, 4, 8))

    def test_parser_mutations_rejected(self):
        for control in ('missing_input', 'missing_present', 'missing_actor', 'missing_post', 'phase', 'time', 'input',
                        'sequence', 'first_sequence', 'extra_key', 'header', 'header_bool', 'tick_bool', 'time_bool',
                        'route', 'footer', 'footer_type',
                        'after_footer', 'no_footer', 'non_object', 'rgb_updated_checksum', 'empty'):
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
