"""Exercise the real C++ endpoint sender and strict in-memory receiver."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

from frame_iteration_live_probe.transport import HEADER, MEMORY_BYTES, receive
from frame_iteration_live_probe.build import observer_source
from frame_iteration_live_probe.build import BASE_PINS, VGA_PINS, frozen_text

ROOT = Path(__file__).resolve().parents[1]


class StreamTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != 'linux' or not shutil.which('g++'):
            raise unittest.SkipTest('Linux Unix-socket observer toolchain required')
        cls.temp = tempfile.TemporaryDirectory(prefix='lezac-stream-tests-', dir='/dev/shm')
        cls.exe = Path(cls.temp.name) / 'sender'
        subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-pedantic',
                        str(ROOT / 'tests/core/frame_memory_stream_test.cpp'), '-o', str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def malformed(self, payload):
        left, right = socket.socketpair()
        with left, right:
            right.sendall(payload);right.shutdown(socket.SHUT_WR)
            with self.assertRaises(ValueError):
                receive(left)

    def test_real_sender_and_receiver(self):
        left, right = socket.socketpair()
        with left, right, ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(receive, left)
            environment = dict(os.environ, LEZAC_ACTIVE_MEMORY_FD=str(right.fileno()))
            environment.pop('LEZAC_ACTIVE_MEMORY_PREFIX', None)
            result = subprocess.run([str(self.exe), 'pair'], env=environment, pass_fds=(right.fileno(),), timeout=10)
            right.shutdown(socket.SHUT_WR)
            endpoints = future.result(timeout=10)
        self.assertEqual(result.returncode, 0)
        expected = bytearray([0x5a]) * MEMORY_BYTES
        expected[0xa0000:0xb0000] = bytes(range(256)) * 256
        self.assertEqual(endpoints, [expected, expected])

    def test_header_controls(self):
        good = [b'LZMEMS01', 1, 0, b'\0' * 3, MEMORY_BYTES]
        for index, value in ((0, b'LZMEMS02'), (1, 2), (2, 1), (3, b'\0\1\0'), (4, 0), (4, MEMORY_BYTES + 1)):
            parts = good.copy();parts[index] = value
            with self.subTest(index=index, value=value):
                self.malformed(HEADER.pack(*parts))

    def test_truncation_controls(self):
        header = HEADER.pack(b'LZMEMS01', 1, 0, b'\0' * 3, MEMORY_BYTES)
        for payload in (b'', header[:8], header, header + b'x' * 127):
            self.malformed(payload)

    def test_cpp_rejects_non_socket_and_bad_descriptor(self):
        read, write = os.pipe()
        try:
            for descriptor in ('-1', '2', str(write), str(write) + 'x', '999999999999999999999999'):
                result = subprocess.run([str(self.exe), 'initial'], pass_fds=(write,),
                    env=dict(os.environ, LEZAC_ACTIVE_MEMORY_FD=descriptor), timeout=5)
                self.assertEqual(result.returncode, 1)
        finally:
            os.close(read);os.close(write)

    def test_cpp_rejects_mixed_dump_mode_and_unknown_phase(self):
        left, right = socket.socketpair()
        with left, right:
            for mode, extra in (('initial', {'LEZAC_ACTIVE_MEMORY_PREFIX': '/dev/shm/forbidden'}), ('other', {})):
                environment = dict(os.environ, LEZAC_ACTIVE_MEMORY_FD=str(right.fileno()), **extra)
                result = subprocess.run([str(self.exe), mode], env=environment, pass_fds=(right.fileno(),), timeout=5)
                self.assertEqual(result.returncode, 1)

    def test_cpp_closed_receiver_is_failure_not_sigpipe(self):
        left, right = socket.socketpair();left.close()
        with right:
            environment = dict(os.environ, LEZAC_ACTIVE_MEMORY_FD=str(right.fileno()))
            result = subprocess.run([str(self.exe), 'initial'], env=environment, pass_fds=(right.fileno(),), timeout=5)
            self.assertEqual(result.returncode, 1)

    def test_extra_data_after_two_endpoints_is_rejected(self):
        left, right = socket.socketpair()
        with left, right, ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(receive, left)
            environment = dict(os.environ, LEZAC_ACTIVE_MEMORY_FD=str(right.fileno()))
            environment.pop('LEZAC_ACTIVE_MEMORY_PREFIX', None)
            result = subprocess.run([str(self.exe), 'pair'], env=environment, pass_fds=(right.fileno(),), timeout=10)
            self.assertEqual(result.returncode, 0)
            right.sendall(b'x');right.shutdown(socket.SHUT_WR)
            with self.assertRaises(ValueError):
                future.result(timeout=10)

    def test_generated_probe_has_no_snapshot_file_sink(self):
        source = observer_source()
        self.assertIn('++p.measurements==4', source)
        self.assertIn('LezacStreamMemory("initial")', source)
        self.assertIn('LezacStreamMemory("final")', source)
        self.assertNotIn('.ram', source)
        self.assertNotIn('LezacActiveMemory(', source)

    def test_frozen_lf_and_crlf_forms_are_both_pinned(self):
        with tempfile.TemporaryDirectory(prefix='lezac-stream-text-', dir='/dev/shm') as directory:
            path = Path(directory) / 'input.h'
            for name, pins in (('lezac_work_probe.h', BASE_PINS), ('vga_frame_observation.inc', VGA_PINS)):
                raw = (ROOT / 'tools/frame_active_live_probe' / name).read_bytes().replace(b'\r\n', b'\n')
                for form in (raw, raw.replace(b'\n', b'\r\n')):
                    path.write_bytes(form)
                    self.assertEqual(frozen_text(path, pins), raw.decode())
                    path.write_bytes(form + b' ')
                    with self.assertRaises(ValueError):
                        frozen_text(path, pins)


if __name__ == '__main__':
    unittest.main()
