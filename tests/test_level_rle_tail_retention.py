"""Exercise decoder comparison evidence lifetime without running an emulator."""
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_level_rle_tail as checker


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lezac-rle-retention-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.exe = self.root / 'fake-executable'
        self.exe.write_bytes(b'test executable identity')
        self.out = self.root / 'evidence'
        self.value = dict(cases=[dict(name='unit', target=1, tail_bytes=1, output_hex='1122',
            buffer_before_hex=bytes(60000).hex(), encoded_hex='001122')])
        self.good = b'LZRO0001' + struct.pack('<III', 1, 1, 1) + bytes.fromhex('1122')

    def invoke(self, code=0, actual=None, error=None, mutate=False):
        def native(command, **kwargs):
            self.command, self.kwargs = command, kwargs
            Path(command[-1]).write_bytes(self.good if actual is None else actual)
            if mutate:
                self.exe.write_bytes(b'changed executable')
            if error:
                raise error
            return SimpleNamespace(returncode=code, stdout=b'native stdout', stderr=b'native stderr')
        with mock.patch.object(checker.subprocess, 'run', side_effect=native):
            return checker.compare_executable(self.value, self.exe, self.out)

    def evidence(self):
        directory, = self.out.iterdir()
        return directory, json.loads((directory / 'report.json').read_bytes())

    def test_success_retains_verified_compressed_bytes(self):
        self.assertEqual(self.invoke(), (1, 1))
        directory, report = self.evidence()
        self.assertTrue(report['passed'])
        self.assertEqual(gzip.decompress((directory / 'actual.bin.gz').read_bytes()), self.good)
        self.assertEqual(gzip.decompress((directory / 'input.bin.gz').read_bytes()), checker.input_bytes(self.value))
        self.assertFalse((directory / 'input.bin').exists())
        self.assertFalse((directory / 'actual.bin').exists())

    def test_nonzero_exit_preserves_failure_and_raw_files(self):
        with self.assertRaisesRegex(RuntimeError, 'compiled decoder failed'):
            self.invoke(code=7)
        directory, report = self.evidence()
        self.assertFalse(report['passed'])
        self.assertEqual(report['exit_code'], 7)
        self.assertEqual((directory / 'actual.bin').read_bytes(), self.good)
        self.assertEqual((directory / 'stderr.txt').read_bytes(), b'native stderr')

    def test_corrupt_output_remains_available(self):
        with self.assertRaisesRegex(RuntimeError, 'compiled decoder header'):
            self.invoke(actual=b'bad output')
        directory, report = self.evidence()
        self.assertFalse(report['passed'])
        self.assertEqual(gzip.decompress((directory / 'actual.bin.gz').read_bytes()), b'bad output')

    def test_timeout_preserves_original_exception_and_partial_streams(self):
        error = subprocess.TimeoutExpired('native', 60, output=b'partial stdout', stderr=b'partial stderr')
        with self.assertRaises(subprocess.TimeoutExpired) as raised:
            self.invoke(actual=b'partial output', error=error)
        self.assertIs(raised.exception, error)
        directory, report = self.evidence()
        self.assertFalse(report['passed'])
        self.assertEqual((directory / 'stdout.txt').read_bytes(), b'partial stdout')
        self.assertEqual((directory / 'stderr.txt').read_bytes(), b'partial stderr')
        self.assertEqual((directory / 'actual.bin').read_bytes(), b'partial output')

    def test_launch_failure_preserves_input(self):
        error = OSError('injected launch failure')
        with mock.patch.object(checker.subprocess, 'run', side_effect=error):
            with self.assertRaises(OSError) as raised:
                checker.compare_executable(self.value, self.exe, self.out)
        self.assertIs(raised.exception, error)
        directory, report = self.evidence()
        self.assertEqual(report['error_type'], 'OSError')
        self.assertTrue((directory / 'input.bin.gz').exists())

    def test_missing_output_is_a_retained_failure(self):
        with mock.patch.object(checker.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')):
            with self.assertRaises(FileNotFoundError):
                checker.compare_executable(self.value, self.exe, self.out)
        directory, report = self.evidence()
        self.assertFalse(report['passed'])
        self.assertTrue((directory / 'input.bin').exists())

    def test_retention_error_does_not_mask_native_failure(self):
        original = Path.write_bytes
        def write(path, raw):
            if path.name == 'actual.bin.gz':
                raise OSError('injected archive failure')
            return original(path, raw)
        with mock.patch.object(Path, 'write_bytes', write):
            with self.assertRaisesRegex(RuntimeError, 'compiled decoder failed'):
                self.invoke(code=9)
        directory, report = self.evidence()
        self.assertIn('actual.bin.gz', report['artifact_errors'])
        self.assertTrue((directory / 'input.bin.gz').exists())
        self.assertTrue((directory / 'actual.bin').exists())

    def test_success_cannot_hide_retention_failure(self):
        original = Path.write_bytes
        def write(path, raw):
            if path.name == 'actual.bin.gz':
                raise OSError('injected archive failure')
            return original(path, raw)
        with mock.patch.object(Path, 'write_bytes', write):
            with self.assertRaisesRegex(RuntimeError, 'decoder evidence retention failed'):
                self.invoke()
        _, report = self.evidence()
        self.assertFalse(report['passed'])

    def test_repeated_runs_preserve_first_evidence(self):
        self.invoke()
        first, _ = self.evidence()
        hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in first.iterdir()}
        self.invoke()
        self.assertEqual(len(list(self.out.iterdir())), 2)
        self.assertEqual(hashes, {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in first.iterdir()})

    def test_native_contract_is_silent_and_input_only(self):
        self.invoke()
        self.assertEqual(self.command[1], '--replay')
        self.assertEqual(len(self.command), 4)
        self.assertEqual(self.kwargs['timeout'], 60)
        self.assertEqual(self.kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
        self.assertEqual(self.kwargs['env']['SDL_VIDEODRIVER'], 'dummy')
        incoming = gzip.decompress((Path(self.command[-2]).parent / 'input.bin.gz').read_bytes())
        poisoned = dict(cases=[dict(self.value['cases'][0], output_hex='3344')])
        self.assertEqual(incoming, checker.input_bytes(self.value))
        self.assertEqual(incoming, checker.input_bytes(poisoned))

    def test_executable_change_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'compiled decoder executable changed'):
            self.invoke(mutate=True)
        _, report = self.evidence()
        self.assertFalse(report['passed'])


if __name__ == '__main__':
    unittest.main()
