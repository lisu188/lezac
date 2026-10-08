"""Contracts for byte comparison, fixture bounds, and retained failure evidence."""
import gzip
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from types import ModuleType
import unittest
from unittest import mock

SOURCE = Path(__file__).with_name('check_actor_storage_core.py')
checker = ModuleType('actor_storage_checker_contract_source')
checker.__file__ = str(SOURCE)
exec(compile(SOURCE.read_bytes(), str(SOURCE), 'exec', dont_inherit=True), vars(checker))


class StorageCheckerContracts(unittest.TestCase):
    def test_fixture_roundtrip(self):
        raw = bytes(range(256))
        packed = gzip.compress(raw, mtime=0)
        self.assertEqual(checker.decode_fixture(packed, checker.sha(packed), checker.sha(raw)), raw)

    def test_compressed_hash_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'compressed fixture hash mismatch'):
            checker.decode_fixture(gzip.compress(b'x'), 'wrong', 'wrong')

    def test_raw_hash_rejected(self):
        packed = gzip.compress(b'x')
        with self.assertRaisesRegex(RuntimeError, 'decompressed fixture hash mismatch'):
            checker.decode_fixture(packed, checker.sha(packed), 'wrong')

    def test_compressed_limit(self):
        with self.assertRaisesRegex(RuntimeError, 'compressed fixture exceeds limit'):
            checker.decode_fixture(bytes(512 * 1024), 'wrong', 'wrong')

    def test_decompressed_limit(self):
        packed = gzip.compress(bytes(33), mtime=0)
        with self.assertRaisesRegex(RuntimeError, 'decompressed fixture exceeds limit'):
            checker.decode_fixture(packed, checker.sha(packed), checker.sha(bytes(33)), limit=32)

    def test_truncated_gzip(self):
        packed = gzip.compress(bytes(32), mtime=0)[:-1]
        with self.assertRaises((EOFError, OSError)):
            checker.decode_fixture(packed, checker.sha(packed), checker.sha(bytes(32)))

    def test_every_table_and_scalar_offset_is_compared(self):
        expected = b'LZAR0001' + struct.pack('<I', 1) + bytes(checker.STATE_BYTES)
        self.assertIsNone(checker.difference(expected, expected))
        for at in range(checker.STATE_BYTES):
            actual = bytearray(expected)
            actual[12 + at] = 1
            difference = checker.difference(bytes(actual), expected)
            self.assertEqual(difference['state_offset'], at)
            self.assertEqual(difference['operation'], 1)
            self.assertEqual(difference['actual'], 1)
            self.assertEqual(difference['expected'], 0)

    def test_header_and_extent_mismatches(self):
        expected = b'LZAR0001' + struct.pack('<I', 1) + bytes(checker.STATE_BYTES)
        self.assertEqual(checker.difference(b'?' + expected[1:], expected)['area'], 'header')
        self.assertEqual(checker.difference(expected[:-1], expected)['actual'], None)
        self.assertEqual(checker.difference(expected + b'?', expected)['expected'], None)

    def test_probe_failure_and_timeout_buffers(self):
        buffers, row = {}, dict(name='case')
        with mock.patch.object(checker.subprocess, 'run', return_value=subprocess.CompletedProcess(
                ['probe'], 7, stdout=b'partial', stderr=b'reason')):
            with self.assertRaisesRegex(RuntimeError, 'probe failed'):
                checker.run_probe(Path('probe'), b'request', b'expected', buffers, row)
        self.assertEqual(buffers['case-actual'], b'partial')
        self.assertEqual(buffers['case-stderr'], b'reason')
        self.assertEqual(row['returncode'], 7)
        with mock.patch.object(checker.subprocess, 'run', side_effect=subprocess.TimeoutExpired(
                ['probe'], 30, output=b'timed-partial', stderr=b'timed-reason')):
            with self.assertRaises(subprocess.TimeoutExpired):
                checker.run_probe(Path('probe'), b'request', b'expected', buffers, row)
        self.assertEqual(buffers['case-actual'], b'timed-partial')
        self.assertEqual(buffers['case-stderr'], b'timed-reason')
        self.assertTrue(row['timeout'])

    def test_controller_retains_mismatch_and_process_failure(self):
        with tempfile.TemporaryDirectory(prefix='actor-storage-contract-') as temporary:
            root = Path(temporary)
            (root / 'LEZAC.EXE').write_bytes(b'original-contract-fixture')
            exe = root / 'probe'
            exe.write_bytes(b'probe-contract-fixture')
            fixtures = root / 'tests/fixtures/actor_storage'
            fixtures.mkdir(parents=True)
            request = b'LZAS0001' + struct.pack('<I', 1) + b'contract-request'
            expected = b'LZAR0001' + struct.pack('<I', 1) + bytes(checker.STATE_BYTES)
            packed_request, packed_expected = gzip.compress(request), gzip.compress(expected)
            (fixtures / 'case-requests.bin.gz').write_bytes(packed_request)
            (fixtures / 'case-expected.bin.gz').write_bytes(packed_expected)
            case = ('case', 1, checker.sha(packed_request), checker.sha(request),
                    checker.sha(packed_expected), checker.sha(expected))
            actual = expected[:-1] + b'!'
            paths = []
            for code in (0, 3):
                with mock.patch.object(checker, 'ORIGINAL_SHA', checker.sha((root / 'LEZAC.EXE').read_bytes())), \
                     mock.patch.object(checker, 'CASES', (case,)), \
                     mock.patch.object(checker.subprocess, 'run', return_value=subprocess.CompletedProcess(
                         ['probe'], code, stdout=actual, stderr=b'failure-details')):
                    report, path = checker.check(root, exe, root / 'checks')
                paths.append(path)
                self.assertFalse(report['passed'])
                self.assertEqual(report['cases'][0]['first_difference']['state_offset'], checker.STATE_BYTES - 1)
                retained = {Path(x['path']).name: x for x in report['retained_failure']}
                for name, data in (('case-requests', request), ('case-expected', expected),
                                   ('case-actual', actual), ('case-stderr', b'failure-details')):
                    entry = retained[name + '.bin.gz']
                    self.assertEqual(gzip.decompress(Path(entry['path']).read_bytes()), data)
                    self.assertEqual(entry['raw_sha256'], checker.sha(data))
                self.assertEqual(json.loads(path.read_text())['passed'], False)
            self.assertNotEqual(paths[0], paths[1])
            self.assertTrue(all(path.exists() for path in paths))

            def changed_probe(*args, **kwargs):
                exe.write_bytes(b'changed-executable')
                return subprocess.CompletedProcess(['probe'], 0, stdout=expected, stderr=b'')

            with mock.patch.object(checker, 'ORIGINAL_SHA', checker.sha((root / 'LEZAC.EXE').read_bytes())), \
                 mock.patch.object(checker, 'CASES', (case,)), \
                 mock.patch.object(checker.subprocess, 'run', side_effect=changed_probe):
                report, path = checker.check(root, exe, root / 'checks')
            self.assertFalse(report['passed'])
            self.assertIn('probe changed during comparison', report['error'])
            self.assertTrue(any(Path(x['path']).name == 'case-actual.bin.gz'
                                for x in report['retained_failure']))


if __name__ == '__main__':
    unittest.main()
