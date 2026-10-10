"""Guard shipped-profile identities and retained failures without an executor."""
import argparse
import importlib.util
import json
import os
import py_compile
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import check_original_shipped_profile_native as checker

checker = checker.load_source_module(Path(checker.__file__))

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(checker.__file__).resolve()


class ShippedProfileNativeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = checker.read_file(ROOT, checker.FIXTURE)
        cls.levels = checker.read_file(ROOT, 'LIVELS.SCH')

    def read(self, blob, levels=None):
        with tempfile.TemporaryDirectory(prefix='lezac-profile-native-contract-') as directory:
            root = Path(directory)
            path = root / checker.FIXTURE
            path.parent.mkdir(parents=True)
            path.write_bytes(blob)
            (root / 'LIVELS.SCH').write_bytes(self.levels if levels is None else levels)
            return checker.read_native(root)

    def test_pinned_fixture_without_executor(self):
        result = self.read(self.blob)
        self.assertEqual(len(result['cases']), 45)
        self.assertEqual(len({case['profile'] for case in result['cases']}), 15)
        self.assertNotIn('unicorn', sys.modules)

    def test_mutated_record_rejected(self):
        changed = bytearray(self.blob)
        changed[checker.PREFIX + 48 + 112 + 6] ^= 1
        with self.assertRaisesRegex(ValueError, 'fixture hash mismatch'):
            self.read(changed)

    def test_truncation_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fixture hash mismatch'):
            self.read(self.blob[:-1])

    def test_trailing_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fixture hash mismatch'):
            self.read(self.blob + b'\x00')

    def test_mutated_shipped_bank_rejected(self):
        with self.assertRaisesRegex(ValueError, 'level bank hash mismatch'):
            self.read(self.blob, self.levels[:-1])

    def test_self_check_without_site_packages(self):
        result = subprocess.run([sys.executable, '-S', '-B', str(SCRIPT), '--root', str(ROOT), '--self-check'],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('profiles=15 constructors=45 updates=2880 executor_required=0 live=0', result.stdout)

    def test_equal_bytes_counted(self):
        report = dict(compared_bytes=0)
        checker.compare_bytes(report, b'\x01\x02', b'\x01\x02', 'control')
        self.assertEqual(report['compared_bytes'], 2)

    def test_mismatch_records_offsets(self):
        report = dict(compared_bytes=0)
        with self.assertRaisesRegex(ValueError, 'native shipped profile mismatch: actor'):
            checker.compare_bytes(report, b'\x01\x02', b'\x01\x03', 'actor')
        self.assertEqual(report['mismatch']['differing_offsets'], [1])
        self.assertEqual(report['compared_bytes'], 0)

    def test_length_mismatch_rejected(self):
        report = dict(compared_bytes=0)
        with self.assertRaises(ValueError):
            checker.compare_bytes(report, b'\x01', b'\x01\x02', 'record size')
        self.assertEqual(report['mismatch']['actual_bytes'], 1)
        self.assertEqual(report['mismatch']['expected_bytes'], 2)

    def test_failed_prerequisite_retained(self):
        with tempfile.TemporaryDirectory(prefix='lezac-profile-native-failure-') as directory:
            path = Path(directory)
            prerequisite, output = path / 'failed.json', path / 'diagnostic.json'
            raw = b'{"passed":false}'
            prerequisite.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'native prerequisite did not pass'):
                checker.run_analysis(ROOT, prerequisite, None, output)
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertFalse(report['passed'])
            self.assertIn('native prerequisite did not pass', report['failure'])
            self.assertEqual(report['native_fixture_sha256'], checker.FIXTURE_SHA)
            self.assertEqual(report['native_prerequisite_sha256'], checker.sha(raw))

    def test_malformed_prerequisite_identity_retained(self):
        with tempfile.TemporaryDirectory(prefix='lezac-profile-native-malformed-') as directory:
            path = Path(directory)
            prerequisite, output = path / 'malformed.json', path / 'diagnostic.json'
            raw = b'{"passed":true, invalid json'
            prerequisite.write_bytes(raw)
            with self.assertRaises(json.JSONDecodeError):
                checker.run_analysis(ROOT, prerequisite, None, output)
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(report['native_prerequisite_sha256'], checker.sha(raw))
            self.assertFalse(report['passed'])

    def test_single_prerequisite_buffer_bound_before_validation(self):
        first, replacement = b'{"passed":true,"version":1}', b'{"passed":false,"version":2}'

        class ChangingReport:
            def __init__(self):
                self.reads = 0

            def read_bytes(self):
                self.reads += 1
                return first if self.reads == 1 else replacement

        with tempfile.TemporaryDirectory(prefix='lezac-profile-native-single-read-') as directory:
            root = Path(directory)
            fixture = root / checker.FIXTURE
            fixture.parent.mkdir(parents=True)
            fixture.write_bytes(self.blob)
            (root / 'LIVELS.SCH').write_bytes(self.levels)
            tools = root / 'tools'
            tools.mkdir()
            (tools / 'original_bomb_cpu.py').write_bytes(b'contract helper identity')
            (tools / 'check_original_bomb_native.py').write_bytes(b'contract checker identity')
            prerequisite, output = ChangingReport(), root / 'diagnostic.json'
            validation = mock.Mock(side_effect=ValueError('validation negative control'))
            module = mock.Mock(validate_native_report=validation,
                native_checker=SimpleNamespace(__source_sha256__=checker.sha(b'contract checker identity')))
            with mock.patch.object(checker, 'load_source_module', return_value=module):
                with self.assertRaisesRegex(ValueError, 'validation negative control'):
                    checker.run_analysis(root, prerequisite, None, output)
            validation.assert_called_once_with(json.loads(first),
                checker.sha(b'contract helper identity'), checker.sha(b'contract checker identity'))
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(prerequisite.reads, 1)
            self.assertEqual(report['native_prerequisite_sha256'], checker.sha(first))

    def test_existing_report_preserved(self):
        with tempfile.TemporaryDirectory(prefix='lezac-profile-native-retention-') as directory:
            path = Path(directory) / 'retained.json'
            path.write_bytes(b'retained evidence')
            with self.assertRaises(FileExistsError):
                checker.run_analysis(ROOT, Path(directory) / 'missing.json', None, path)
            self.assertEqual(path.read_bytes(), b'retained evidence')

    def test_actual_executor_identity_recorded(self):
        with tempfile.TemporaryDirectory(prefix='lezac-profile-native-executor-') as directory:
            path = Path(directory) / 'executor.py'
            path.write_bytes(b'actual executor identity')
            report = {}
            checker.validate_executor_identity(checker.load_source_module(path, b'pass\n'),
                checker.sha(b'pass\n'), report)
            self.assertEqual(report['helper_path'], str(path.resolve()))
            self.assertEqual(report['helper_sha256'], checker.sha(b'pass\n'))

    def test_different_imported_executor_rejected(self):
        with tempfile.TemporaryDirectory(prefix='lezac-profile-native-executor-mismatch-') as directory:
            path = Path(directory) / 'executor.py'
            path.write_bytes(b'unvalidated imported executor')
            report = {}
            with self.assertRaisesRegex(ValueError, 'imported executor hash differs'):
                checker.validate_executor_identity(SimpleNamespace(__file__=str(path),
                    __source_sha256__=checker.sha(path.read_bytes())),
                    checker.sha(b'validated executor'), report)
            self.assertEqual(report['helper_sha256'], checker.sha(path.read_bytes()))

    def test_timestamp_valid_bytecode_is_bypassed(self):
        with tempfile.TemporaryDirectory(prefix='lezac-profile-stale-cache-') as directory:
            path = Path(directory) / 'executor.py'
            old, current = b"def value(): return 'old'\n", b"def value(): return 'new'\n"
            path.write_bytes(old)
            stamp = path.stat()
            py_compile.compile(str(path), doraise=True)
            path.write_bytes(current)
            os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            spec = importlib.util.spec_from_file_location('stale_executor_control', path)
            cached = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cached)
            self.assertEqual(cached.value(), 'old')
            actual = checker.load_source_module(path)
            self.assertEqual(actual.value(), 'new')
            self.assertEqual(actual.__source_sha256__, checker.sha(current))

    def test_executor_source_is_read_once(self):
        with tempfile.TemporaryDirectory(prefix='lezac-profile-source-buffer-') as directory:
            path = Path(directory) / 'executor.py'
            current, replacement = b"def value(): return 'new'\n", b"def value(): return 'old'\n"
            path.write_bytes(current)
            with mock.patch.object(Path, 'read_bytes', side_effect=[current, replacement]) as read:
                actual = checker.load_source_module(path)
            self.assertEqual(read.call_count, 1)
            self.assertEqual(actual.value(), 'new')
            self.assertEqual(actual.__source_sha256__, checker.sha(current))

    def test_executed_source_identity_survives_replacement(self):
        with tempfile.TemporaryDirectory(prefix='lezac-profile-source-replaced-') as directory:
            path = Path(directory) / 'executor.py'
            current = b"def value(): return 'new'\n"
            path.write_bytes(current)
            actual = checker.load_source_module(path)
            path.write_bytes(b"def value(): return 'old'\n")
            report = {}
            checker.validate_executor_identity(actual, checker.sha(current), report)
            self.assertEqual(actual.value(), 'new')
            self.assertEqual(report['helper_sha256'], checker.sha(current))

    def test_producer_source_identity_survives_replacement(self):
        with tempfile.TemporaryDirectory(prefix='lezac-profile-producer-replaced-') as directory:
            path = Path(directory) / SCRIPT.name
            current = SCRIPT.read_bytes()
            path.write_bytes(current)
            actual = checker.load_source_module(path)
            path.write_bytes(b"raise RuntimeError('replacement producer')\n")
            with mock.patch.object(Path, 'read_bytes', side_effect=RuntimeError('late producer read')):
                self.assertEqual(actual.producer_sha256(), checker.sha(current))

    def test_unbound_producer_is_rejected(self):
        actual = checker.load_source_module(SCRIPT)
        del actual.__source_sha256__
        with self.assertRaisesRegex(RuntimeError, 'producer must execute from a bound source buffer'):
            actual.producer_sha256()

    def test_optimized_cli_rejected(self):
        result = subprocess.run([sys.executable, '-O', '-S', '-B', str(SCRIPT), '--self-check'],
            capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('optimized Python is not supported', result.stderr)

    def test_optimized_env_rejected(self):
        result = subprocess.run([sys.executable, '-S', '-B', str(SCRIPT), '--help'],
            env=dict(os.environ, PYTHONOPTIMIZE='1'), capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('optimized Python is not supported', result.stderr)

    def test_optimized_comparison_still_rejects(self):
        result = subprocess.run([sys.executable, '-O', '-S', '-B', '-c',
            "from check_original_shipped_profile_native import compare_bytes;"
            "compare_bytes({'compared_bytes':0},b'one',b'two','negative control')"],
            cwd=SCRIPT.parent, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('native shipped profile mismatch', result.stderr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    ROOT = args.root.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ShippedProfileNativeContractTests))
    if result.wasSuccessful():
        print('original_shipped_profile_native_contract=ok tests=23 executor_required=0')
    raise SystemExit(0 if result.wasSuccessful() else 1)
