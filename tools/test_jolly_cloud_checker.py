"""Failure contracts for the rain checker, separate from compiled/original parity."""
import argparse
import copy
import gzip
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / 'tools/check_jolly_cloud_original.py'
# Execute the same source buffer we read, without consulting cached bytecode.
CHECKER = types.ModuleType('jolly_cloud_checker_contract')
CHECKER.__file__ = str(CHECKER_PATH)
exec(compile(CHECKER_PATH.read_bytes(), str(CHECKER_PATH), 'exec'), CHECKER.__dict__)
PROBE = None


class RainCheckerContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packed = (ROOT / 'tests/fixtures/jolly_cloud_original.json.gz').read_bytes()
        cls.fixture = CHECKER.decode_fixture(cls.packed)
        cls.request, cls.expected, cls.boundaries = CHECKER.streams(cls.fixture)

    def test_pinned_fixture_and_coverage(self):
        self.assertEqual(len(self.boundaries), 293)
        self.assertEqual(self.request[:8], b'LZJC0001')
        self.assertEqual(self.expected[:8], b'LZJO0001')

    def test_compressed_identity(self):
        with self.assertRaisesRegex(RuntimeError, 'compressed fixture hash'):
            CHECKER.decode_fixture(self.packed + b'x')

    def test_raw_identity(self):
        with self.assertRaisesRegex(RuntimeError, 'decompressed fixture hash'):
            CHECKER.decode_fixture(self.packed, raw_sha='0' * 64)

    def test_compressed_size_limit(self):
        with self.assertRaisesRegex(RuntimeError, 'compressed fixture exceeds'):
            CHECKER.decode_fixture(bytes(1024**2))

    def test_bounded_decompression(self):
        packed = gzip.compress(bytes(1025), mtime=0)
        with self.assertRaisesRegex(RuntimeError, 'decompressed fixture exceeds'):
            CHECKER.decode_fixture(packed, CHECKER.sha(packed), limit=1024)

    def test_schema_and_provenance(self):
        for key, value in [('schema', 'other'), ('natural', True), ('patched_instructions', True),
                           ('stubbed_original_calls', True), ('executable_sha256', '0' * 64)]:
            with self.subTest(key=key):
                fixture = dict(self.fixture, **{key: value})
                with self.assertRaises(RuntimeError):
                    CHECKER.streams(fixture)

    def test_case_extents_and_continuity(self):
        mutations = [('width', 0), ('index', 1), ('remaining', 45), ('initial_tiles', ''),
                     ('samples', self.fixture['cases'][0]['samples'][:-1])]
        for key, value in mutations:
            with self.subTest(key=key):
                fixture = copy.deepcopy(self.fixture)
                fixture['cases'][0][key] = value
                with self.assertRaises(RuntimeError):
                    CHECKER.streams(fixture)

    def test_initial_extents(self):
        for key, value in [('tiles', ''), ('words', ''), ('debris_records', ''), ('debris_count', 1402)]:
            with self.subTest(key=key):
                fixture = copy.deepcopy(self.fixture)
                fixture['cases'][0]['initial'][key] = value
                with self.assertRaises(RuntimeError):
                    CHECKER.streams(fixture)

    def test_sample_extents(self):
        for key, value in [('tiles', ''), ('words', ''), ('debris_records', ''), ('debris_count', 1402)]:
            with self.subTest(key=key):
                fixture = copy.deepcopy(self.fixture)
                fixture['cases'][0]['samples'][0][key] = value
                with self.assertRaises(RuntimeError):
                    CHECKER.streams(fixture)

    def test_first_difference_localizes_each_plane(self):
        row = self.boundaries[0]
        for key, area in [('start', 'scalars'), ('tiles_start', 'tiles'), ('words_start', 'words'),
                          ('records_start', 'active_debris_records')]:
            with self.subTest(area=area):
                actual = bytearray(self.expected)
                actual[row[key]] ^= 1
                diff = CHECKER.difference(actual, self.expected, self.boundaries)
                self.assertEqual((diff['case'], diff['tick'], diff['area']), (0, 0, area))
        self.assertIsNone(CHECKER.difference(self.expected, self.expected, self.boundaries))

    def test_missing_and_trailing_output(self):
        self.assertIsNone(CHECKER.difference(self.expected[:-1], self.expected, self.boundaries)['actual'])
        self.assertIsNone(CHECKER.difference(self.expected + b'x', self.expected, self.boundaries)['expected'])

    def run_checker(self, callback):
        with tempfile.TemporaryDirectory(prefix='rain-checker-contract-') as scratch:
            scratch = Path(scratch)
            exe = scratch / 'probe.bin'
            exe.write_bytes(b'contract-only-not-executed')
            with patch.object(CHECKER.subprocess, 'run', side_effect=lambda *a, **kw: callback(exe, a, kw)):
                report, path = CHECKER.check(ROOT, exe, scratch / 'out', app=True)
            self.assertTrue(path.is_file())
            if not report['passed']:
                self.assertTrue(report['retained_failure'])
                for retained in report['retained_failure']:
                    data = gzip.decompress(Path(retained['path']).read_bytes())
                    self.assertEqual(CHECKER.sha(data), retained['sha256'])
            return report

    def test_comparison_routes_app_and_silent_environment(self):
        def run(exe, args, kwargs):
            self.assertEqual(args[0], [str(exe), '--debug-jolly-cloud-probe'])
            self.assertEqual(kwargs['input'], self.request)
            self.assertEqual(kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
            return subprocess.CompletedProcess(args[0], 0, self.expected, b'')
        report = self.run_checker(run)
        self.assertTrue(report['passed'])
        self.assertFalse(report['full_frame_loop'])
        self.assertFalse(report['natural_pickup_claim'])

    def test_nonzero_exit_retains_failure(self):
        report = self.run_checker(lambda *a: subprocess.CompletedProcess([], 3, self.expected, b'failed'))
        self.assertFalse(report['passed'])
        self.assertEqual(report['returncode'], 3)

    def test_mismatch_retains_failure(self):
        report = self.run_checker(lambda *a: subprocess.CompletedProcess([], 0, self.expected[:-1], b''))
        self.assertFalse(report['passed'])
        self.assertIsNotNone(report['first_difference'])

    def test_timeout_retains_partial_output(self):
        def timeout(*args):
            raise subprocess.TimeoutExpired(['contract'], 30, output=b'partial', stderr=b'blocked')
        report = self.run_checker(timeout)
        self.assertFalse(report['passed'])
        self.assertTrue(report['timeout'])
        self.assertTrue(any(row['bytes'] == 7 for row in report['retained_failure']))

    def test_changed_probe_is_rejected(self):
        def changed(exe, args, kwargs):
            exe.write_bytes(b'changed')
            return subprocess.CompletedProcess([], 0, self.expected, b'')
        self.assertFalse(self.run_checker(changed)['passed'])

    def test_compiled_protocol_rejects_malformed_requests(self):
        if PROBE is None:
            self.skipTest('compiled probe not supplied')
        cases = [b'', b'wrongmagic', b'LZJC0001\0\0', self.request[:-1], self.request + b'x']
        for offset, value in [(10, b'\0\0'), (16, b'\xff\xff')]:
            cases.append(self.request[:offset] + value + self.request[offset + 2:])
        for data in cases:
            with self.subTest(bytes=len(data)):
                result = subprocess.run([str(PROBE)], input=data, capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    args, rest = parser.parse_known_args()
    PROBE = args.exe.resolve() if args.exe else None
    unittest.main(argv=[sys.argv[0]] + rest)
