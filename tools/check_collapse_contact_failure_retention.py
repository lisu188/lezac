"""Exercise contact-checker diagnostics with mocked probes, not game execution."""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import check_collapse_contacts_original as checker


class ContactFailureRetention(unittest.TestCase):
    def test_compare_across_read_chunk_boundaries(self):
        expected_bytes = b'a' * 85000
        with tempfile.TemporaryDirectory(prefix='lezac-contact-chunks-') as directory:
            actual, expected = (Path(directory) / name for name in ('actual.bin', 'expected.bin'))
            expected.write_bytes(expected_bytes)
            for offset in (65535, 65536):
                for truncated in (False, True):
                    with self.subTest(offset=offset, truncated=truncated):
                        mutated = bytearray(expected_bytes)
                        mutated[offset] ^= 1
                        actual.write_bytes(mutated[:offset] if truncated else mutated)
                        with self.assertRaisesRegex(ValueError,
                                f'byte_offset={offset} case_index=3 case_byte={offset - 51000}'):
                            checker.compare((actual, expected), (17000,) * 5)

    def test_compare_reports_expected_record_boundaries(self):
        expected_bytes = b'a' * 389 + b'b' * 400
        with tempfile.TemporaryDirectory(prefix='lezac-contact-compare-') as directory:
            actual, expected = (Path(directory) / name for name in ('actual.bin', 'expected.bin'))
            expected.write_bytes(expected_bytes)
            for offset, case, local in ((0, '0', 0), (388, '0', 388),
                                        (389, '1', 0), (788, '1', 399)):
                with self.subTest(offset=offset):
                    mutated = bytearray(expected_bytes)
                    mutated[offset] ^= 1
                    actual.write_bytes(mutated)
                    with self.assertRaisesRegex(ValueError,
                            f'byte_offset={offset} case_index={case} case_byte={local}'):
                        checker.compare((actual, expected), (389, 400))
            for size, case, local in ((388, '0', 388), (389, '1', 0),
                                      (788, '1', 399), (789, 'after_last', 0)):
                with self.subTest(size=size):
                    actual.write_bytes(expected_bytes[:size] if size < 789 else expected_bytes + b'x')
                    with self.assertRaisesRegex(ValueError,
                            f'byte_offset={size} case_index={case} case_byte={local}'):
                        checker.compare((actual, expected), (389, 400))

    def test_main_retains_real_failures_but_not_negative_controls(self):
        input_bytes = b'mocked contact request'
        expected_bytes = b'a' * 389 + b'b' * 400
        modes = ('success', 'nonzero', 'stderr', 'wrong_stdout', 'missing_actual',
                 'first_case', 'second_case', 'truncate', 'append', 'timeout')
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='lezac-contact-retain-test-') as directory:
                root = Path(directory)
                temporary_inputs = []
                produced = []

                def unpack(data, incoming, expected):
                    incoming.write(input_bytes)
                    expected.write(expected_bytes)
                    return (389, 400)

                def probe(command, **kwargs):
                    self.assertEqual(kwargs['cwd'], root)
                    self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
                    self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
                    self.assertEqual(kwargs['timeout'], 60)
                    incoming, actual = Path(command[2]), Path(command[3])
                    temporary_inputs.append(incoming)
                    self.assertEqual(incoming.read_bytes(), input_bytes)
                    content = bytearray(expected_bytes)
                    if mode in ('first_case', 'second_case'):
                        content[0 if mode == 'first_case' else 389] ^= 1
                    if mode == 'truncate':
                        content = content[:-1]
                    if mode == 'append':
                        content += b'x'
                    if mode not in ('missing_actual', 'timeout'):
                        actual.write_bytes(content)
                        produced.append(bytes(content))
                    if mode == 'timeout':
                        raise subprocess.TimeoutExpired(command, 60, output=b'partial stdout', stderr=b'partial stderr')
                    return subprocess.CompletedProcess(command, int(mode == 'nonzero'),
                        'wrong' if mode == 'wrong_stdout' else
                        'collapse_contacts_probe=ok cases=9184 original_fidelity_claim=0\n',
                        'probe stderr' if mode == 'stderr' else '')

                output = io.StringIO()
                with ExitStack() as stack:
                    stack.enter_context(patch.object(checker, 'ROOT', root))
                    stack.enter_context(patch.object(checker, 'metadata', return_value={'cases': 9184}))
                    stack.enter_context(patch.object(checker, 'source_files', return_value=[]))
                    stack.enter_context(patch.object(checker, 'check_source'))
                    stack.enter_context(patch.object(checker, 'unpack', side_effect=unpack))
                    stack.enter_context(patch.object(checker.subprocess, 'run', side_effect=probe))
                    stack.enter_context(patch.object(sys, 'argv', ['check', '--exe', str(root / 'mocked-exe')]))
                    stack.enter_context(redirect_stdout(output))
                    if mode == 'success':
                        checker.main()
                    else:
                        with self.assertRaises((ValueError, RuntimeError, FileNotFoundError, subprocess.TimeoutExpired)):
                            checker.main()
                self.assertTrue(temporary_inputs)
                self.assertFalse(temporary_inputs[0].exists())
                failures = root / 'build/collapse-contact-failures'
                if mode == 'success':
                    self.assertFalse(failures.exists(), 'intentional output mutants were retained as real failures')
                    self.assertIn('output_mutants=4', output.getvalue())
                    continue
                retained = list(failures.iterdir())
                self.assertEqual(len(retained), 1)
                retained = retained[0]
                self.assertEqual((retained / 'input.bin').read_bytes(), input_bytes)
                self.assertEqual((retained / 'expected.bin').read_bytes(), expected_bytes)
                if produced:
                    self.assertEqual((retained / 'actual.bin').read_bytes(), produced[0])
                else:
                    self.assertFalse((retained / 'actual.bin').exists())
                diagnostic = json.loads((retained / 'failure.json').read_text())
                self.assertEqual(diagnostic['case_sizes'], [389, 400])
                self.assertTrue(diagnostic['error'])
                self.assertEqual(diagnostic['command'][1], '--debug-collapse-contacts-original')
                self.assertEqual(diagnostic['replay_command'][2], str(retained / 'input.bin'))
                self.assertEqual(diagnostic['replay_command'][3], str(retained / 'rerun-actual.bin'))
                prefix = 'collapse_contact_failure_retained='
                reported = [line.removeprefix(prefix) for line in output.getvalue().splitlines()
                            if line.startswith(prefix)]
                self.assertEqual(len(reported), 1)
                self.assertTrue(Path(reported[0]).samefile(retained))
                if mode == 'second_case':
                    self.assertIn('byte_offset=389 case_index=1 case_byte=0', diagnostic['error'])
                if mode == 'nonzero':
                    self.assertEqual(diagnostic['returncode'], 1)
                if mode == 'stderr':
                    self.assertEqual(diagnostic['stderr'], 'probe stderr')
                if mode == 'timeout':
                    self.assertEqual(diagnostic['stdout'], 'partial stdout')
                    self.assertEqual(diagnostic['stderr'], 'partial stderr')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ContactFailureRetention)
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log).run(suite)
    if not result.wasSuccessful():
        print(log.getvalue(), file=sys.stderr)
        raise SystemExit(1)
    print('collapse_contact_failure_retention=ok probe_modes=10 comparison_cases=12 mocked_probe=1 original_game_claim=0')
