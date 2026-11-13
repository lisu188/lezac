"""Integrity, scope, byte-comparison and failure controls for the original cases."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest import mock

import check_collapse_magnitude_wrap as recovered


class CollapseMagnitudeWrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = json.loads(gzip.decompress(recovered.FIXTURE.read_bytes()))

    def test_original_observations(self):
        incoming, expected = recovered.fixture()
        self.assertEqual((len(incoming), len(expected)), (13629, 13585))
        self.assertEqual([r['destroyed'] for r in self.value['native_report']['records'][-3:]], [0, 0, 0])

    def test_scope_and_binding_mutations_rejected(self):
        for field, changed in (('natural_route', True), ('full_frame_claim', True),
                ('whole_game_fidelity_claim', True), ('instruction_patches', 1), ('calls_stubbed', 1),
                ('full_guest_ram_exports', 1), ('observer_control_passed', False), ('helper_sha256', '0' * 64)):
            value = copy.deepcopy(self.value)
            value['native_report'][field] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                recovered.validate(value)
        for field, changed in (('cpp_expectations_used', True), ('expected_bytes_source', 'cpp')):
            value = copy.deepcopy(self.value)
            value[field] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                recovered.validate(value)

    def test_case_mutations_rejected(self):
        for kind in ('missing', 'duplicate', 'previous', 'input', 'output', 'registers', 'instruction', 'source', 'closure'):
            value = copy.deepcopy(self.value)
            if kind == 'missing':
                value['cases'].pop()
            elif kind == 'duplicate':
                value['cases'][1] = copy.deepcopy(value['cases'][0])
            elif kind == 'previous':
                value['cases'][-1]['previous'] -= 1
            elif kind in ('input', 'output'):
                row = value['cases'][-1]
                row[kind + '_hex'] = '00' + row[kind + '_hex'][2:]
            elif kind == 'registers':
                value['native_report']['records'][-1]['registers'].pop()
            elif kind == 'instruction':
                value['rea']['byte_checks'][0]['decoded']['bytes'] = '90'
            elif kind == 'source':
                value['producers']['original_bomb_cpu.py']['text'] += '\n'
            else:
                value['rea']['report']['session_closed'] = False
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                recovered.validate(value)

    def test_fixture_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'fixture.gz'
            raw = recovered.FIXTURE.read_bytes()
            with mock.patch.object(recovered, 'FIXTURE', path):
                for damaged in (raw[:-1], raw + b'\0', bytes([raw[0] ^ 1]) + raw[1:]):
                    path.write_bytes(damaged)
                    with self.assertRaises(ValueError):
                        recovered.fixture()

    def test_byte_comparison_mutations_rejected(self):
        _, expected = recovered.fixture()
        recovered.compare(expected, expected)
        for actual in (expected[:-1], expected + b'\0', expected[:11200] + bytes([expected[11200] ^ 1]) + expected[11201:]):
            with self.assertRaises(ValueError):
                recovered.compare(actual, expected)

    def test_preflight_failure_retained(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(recovered, 'fixture', side_effect=ValueError('bad oracle')), \
                mock.patch.object(recovered.subprocess, 'run') as child:
            with self.assertRaises(ValueError):
                recovered.replay(Path('missing'), Path(temporary))
            child.assert_not_called()
            report = json.loads(next(Path(temporary).glob('run-*/report.json')).read_bytes())
            self.assertEqual(report['status'], 'failed')
            self.assertFalse(report['natural_route'])

    def test_failed_and_timed_out_children_retained(self):
        for timed_out in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                exe = root / 'fake.exe'
                exe.write_bytes(b'not executed')
                with mock.patch.object(recovered.subprocess, 'run') as child:
                    if timed_out:
                        child.side_effect = subprocess.TimeoutExpired('fake', 90, output=b'partial', stderr=b'diagnostics')
                    else:
                        child.return_value = subprocess.CompletedProcess('fake', 9, b'partial', b'diagnostics')
                    with self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                        recovered.replay(exe, root / 'out')
                case = next((root / 'out').glob('run-*'))
                self.assertEqual((case / 'stdout.log').read_bytes(), b'partial')
                self.assertEqual((case / 'stderr.log').read_bytes(), b'diagnostics')
                report = json.loads((case / 'report.json').read_bytes())
                self.assertEqual(report['status'], 'failed')
                self.assertTrue(report['owned_child_terminal'])
                self.assertTrue((case / 'input.bin').is_file())


if __name__ == '__main__':
    unittest.main()
