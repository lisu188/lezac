"""Check actor-oracle diagnostics with mocked probes, not game execution."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import check_original_collapse_actors as checker


class ActorCheckerTests(unittest.TestCase):
    def test_comparison_boundaries(self):
        content = b'a' * 389 + b'b' * 400
        with tempfile.TemporaryDirectory(prefix='lezac-actor-compare-') as directory:
            actual, expected = (Path(directory) / name for name in ('actual.bin', 'expected.bin'))
            expected.write_bytes(content)
            checker.compare(expected, expected, [389, 400])
            for offset, case, local in ((0, 0, 0), (388, 0, 388), (389, 1, 0), (788, 1, 399)):
                for truncated in (False, True):
                    with self.subTest(offset=offset, truncated=truncated):
                        changed = bytearray(content)
                        changed[offset] ^= 1
                        actual.write_bytes(changed[:offset] if truncated else changed)
                        with self.assertRaisesRegex(ValueError, f'byte {offset}; case={case} case_byte={local}'):
                            checker.compare(actual, expected, [389, 400])
            actual.write_bytes(content + b'x')
            with self.assertRaisesRegex(ValueError, 'byte 789; case=2 case_byte=0'):
                checker.compare(actual, expected, [389, 400])

    def test_probe_failure_retention(self):
        request, expected_bytes = b'actor request', b'a' * 389 + b'b' * 400
        modes = ('success', 'nonzero', 'stderr', 'wrong_stdout', 'missing_actual',
                 'first_case', 'second_case', 'truncate', 'append', 'timeout')
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='lezac-actor-retain-') as directory:
                root, produced = Path(directory), []
                output = io.StringIO()

                def probe(command, **kwargs):
                    self.assertEqual(kwargs['cwd'], root)
                    self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
                    self.assertEqual(kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
                    self.assertEqual(kwargs['timeout'], 90)
                    self.assertEqual(command[1], '--debug-original-collapse-actors')
                    incoming, actual = Path(command[2]), Path(command[3])
                    self.assertEqual(incoming.read_bytes(), request)
                    changed = bytearray(expected_bytes)
                    if mode in ('first_case', 'second_case'): changed[0 if mode == 'first_case' else 389] ^= 1
                    if mode == 'truncate': changed = changed[:-1]
                    if mode == 'append': changed += b'x'
                    if mode not in ('missing_actual', 'timeout'):
                        actual.write_bytes(changed)
                        produced.append(bytes(changed))
                    if mode == 'timeout':
                        raise subprocess.TimeoutExpired(command, 90, output=b'partial stdout', stderr=b'partial stderr')
                    return subprocess.CompletedProcess(command, int(mode == 'nonzero'),
                        'wrong' if mode == 'wrong_stdout' else 'original_collapse_actors=ok cases=2476\n',
                        'probe stderr' if mode == 'stderr' else '')

                with tempfile.TemporaryDirectory(prefix='inputs-', dir=root) as inputs:
                    incoming, actual, expected = (Path(inputs) / name for name in ('input.bin', 'actual.bin', 'expected.bin'))
                    incoming.write_bytes(request)
                    expected.write_bytes(expected_bytes)
                    with patch.object(checker, 'ROOT', root), patch.object(checker.subprocess, 'run', side_effect=probe), redirect_stdout(output):
                        if mode == 'success': checker.run_probe(root / 'mocked-exe', incoming, actual, expected, [389, 400])
                        else:
                            with self.assertRaises((RuntimeError, ValueError, FileNotFoundError, subprocess.TimeoutExpired)):
                                checker.run_probe(root / 'mocked-exe', incoming, actual, expected, [389, 400])
                self.assertFalse(incoming.exists())
                failures = root / 'build/collapse-actor-failures'
                if mode == 'success':
                    self.assertFalse(failures.exists())
                    continue
                retained = list(failures.iterdir())
                self.assertEqual(len(retained), 1)
                retained = retained[0]
                self.assertEqual((retained / 'input.bin').read_bytes(), request)
                self.assertEqual((retained / 'expected.bin').read_bytes(), expected_bytes)
                if produced: self.assertEqual((retained / 'actual.bin').read_bytes(), produced[0])
                else: self.assertFalse((retained / 'actual.bin').exists())
                diagnostic = json.loads((retained / 'failure.json').read_text())
                self.assertTrue(diagnostic['error'])
                self.assertEqual(diagnostic['case_sizes'], [389, 400])
                self.assertEqual(diagnostic['replay_command'][1], '--debug-original-collapse-actors')
                self.assertEqual(diagnostic['replay_command'][2], str(retained / 'input.bin'))
                self.assertEqual(diagnostic['replay_command'][3], str(retained / 'rerun-actual.bin'))
                prefix = 'collapse_actor_failure_retained='
                reported = [line.removeprefix(prefix) for line in output.getvalue().splitlines() if line.startswith(prefix)]
                self.assertEqual(len(reported), 1)
                self.assertTrue(Path(reported[0]).samefile(retained))
                if mode == 'second_case': self.assertIn('case=1 case_byte=0', diagnostic['error'])
                if mode == 'nonzero': self.assertEqual(diagnostic['returncode'], 1)
                if mode == 'stderr': self.assertEqual(diagnostic['stderr'], 'probe stderr')
                if mode == 'timeout':
                    self.assertEqual(diagnostic['stdout'], 'partial stdout')
                    self.assertEqual(diagnostic['stderr'], 'partial stderr')


if __name__ == '__main__':
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log).run(unittest.defaultTestLoader.loadTestsFromTestCase(ActorCheckerTests))
    if not result.wasSuccessful():
        print(log.getvalue(), file=sys.stderr)
        raise SystemExit(1)
    print('collapse_actor_checker=ok probe_modes=10 comparison_cases=9 mocked_probe=1 game_execution_claim=0')
