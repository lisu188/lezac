"""Exercise collector admission, bounded output and process-scoped permission."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import actor_pass_supervision as supervision


class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lezac-supervision-', dir='/dev/shm')
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)

    def collect(self, returncode=0, report=None, stdout=b'', error=None):
        if report is not None:
            (self.out / 'guard').mkdir()
            (self.out / 'guard/guard.json').write_text(json.dumps(report))
        result = subprocess.CompletedProcess(['test-only'], returncode, stdout, b'')
        with mock.patch.object(supervision.subprocess, 'run', return_value=result, side_effect=error):
            return supervision.collect_guard(['test-only'], {}, self.out)

    def test_verified_capture(self):
        result = self.collect(report=dict(status='failure_throw_captured', protected_inputs_preserved=True))
        self.assertEqual(result['status'], 'failure_throw_captured')
        self.assertEqual(len(result['sha256']), 64)

    def test_nonzero_collector_fails(self):
        with self.assertRaises(RuntimeError):
            self.collect(returncode=1)

    def test_missing_receipt_fails(self):
        with self.assertRaises(FileNotFoundError):
            self.collect()

    def test_unverified_receipt_fails(self):
        with self.assertRaises(ValueError):
            self.collect(report=dict(status='failure_throw_captured', protected_inputs_preserved=False))

    def test_oversized_output_fails(self):
        with self.assertRaises(ValueError):
            self.collect(stdout=b'x' * 65537)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_timeout_propagates(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.collect(error=subprocess.TimeoutExpired(['test-only'], 90))

    def test_permission_is_limited_to_parent(self):
        libc = mock.Mock();libc.prctl.return_value = 0
        with mock.patch.object(supervision.ctypes, 'CDLL', return_value=libc):
            with mock.patch.object(supervision.os, 'getppid', return_value=1234):
                supervision.allow_parent_debugger()
        libc.prctl.assert_called_once_with(supervision.PR_SET_PTRACER, 1234, 0, 0, 0)

    def test_missing_parent_is_rejected(self):
        with mock.patch.object(supervision.os, 'getppid', return_value=1):
            with self.assertRaises(ValueError):
                supervision.allow_parent_debugger()


if __name__ == '__main__':
    unittest.main()
