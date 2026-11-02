"""Check diagnostic terminal reports without launching or tracing a guest."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import actor_pass_hw_parent as hardware
import actor_pass_plain_parent as plain
import actor_pass_throw_parent as preload


class DiagnosticReports(unittest.TestCase):
    def plain_control(self, exit_code=0, stderr=b'', mutation=False):
        with tempfile.TemporaryDirectory(prefix='lezac-plain-', dir='/dev/shm') as directory:
            base = Path(directory)
            for name in ('exe', 'fixture', 'LEZAC.EXE'):
                (base / name).write_bytes(('test-only ' + name).encode())
            args = argparse.Namespace(exe=base / 'exe', fixture=base / 'fixture', root=base,
                                      out=base / 'out', attempts=1)

            def launch(*unused, **kwargs):
                if mutation:
                    args.fixture.write_bytes(b'changed after authentication')
                return plain.subprocess.CompletedProcess([], exit_code, plain.SUCCESS + b'test-only\n', stderr)

            with contextlib.ExitStack() as stack:
                for name, path in [('EXPECTED', args.exe), ('FIXTURE_SHA', args.fixture), ('MZ_SHA', base / 'LEZAC.EXE')]:
                    stack.enter_context(mock.patch.object(plain, name, plain.sha(path)))
                stack.enter_context(mock.patch.dict(os.environ, {}, clear=True))
                stack.enter_context(mock.patch.object(plain.resource, 'setrlimit'))
                stack.enter_context(mock.patch.object(plain.subprocess, 'run', side_effect=launch))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                if mutation or exit_code == -9:
                    with self.assertRaises(RuntimeError):
                        plain.run(args)
                else:
                    plain.run(args)
            report = json.loads((args.out / 'plain.json').read_bytes())
            self.assertFalse(report['intermittent_hold_cleared'])
            self.assertFalse(report['diagnosis_claim'])
            self.assertEqual(report['protected_inputs_preserved'], not mutation)
            return report

    def test_plain_control_bounded_scope(self):
        self.assertEqual(self.plain_control()['status'], 'bounded_non_reproduction')

    def test_plain_control_retains_failure(self):
        report = self.plain_control(exit_code=1, stderr=b'frame_actor_pass=failed test-only\n')
        self.assertEqual(report['status'], 'failure_reproduced')

    def test_plain_control_changed_input_fails(self):
        self.assertEqual(self.plain_control(mutation=True)['status'], 'failed')

    def test_plain_control_abnormal_exit_fails(self):
        self.assertEqual(self.plain_control(exit_code=-9)['status'], 'failed')

    def exercise(self, module, mutation=False, exit_code=0):
        with tempfile.TemporaryDirectory(prefix='lezac-diagnostic-', dir='/dev/shm') as directory:
            base = Path(directory)
            root = base / 'game'
            root.mkdir()
            (root / 'LEZAC.EXE').write_bytes(b'test-only MZ identity')
            paths = {}
            for name in ('exe', 'symbols', 'fixture', 'hook'):
                paths[name] = base / name
                paths[name].write_bytes(('test-only ' + name).encode())
            layout = base / 'layout.json'
            layout.write_text(json.dumps(dict(debug_offset=848, register_bytes=216, word_bytes=8)))
            args = argparse.Namespace(**paths, root=root, layout=layout, out=base / 'out',
                                      attempts=1, calibrate_unit=True, calibrate_cli=False)
            child = mock.Mock(pid=4242, returncode=None)
            child.communicate.return_value = (b'test-only output', b'')

            def launch(*unused, **kwargs):
                if mutation == 'delete':
                    args.fixture.unlink()
                elif mutation:
                    args.fixture.write_bytes(b'changed after input catalog')
                return child

            read_text = Path.read_text

            def read(path, *positional, **keywords):
                if str(path) == '/proc/4242/maps':
                    return '1000-2000 r-xp 00002000 00:00 1 ' + str(args.exe) + '\n'
                return read_text(path, *positional, **keywords)

            waits = [(4242, 0), (4242, exit_code << 8)] if module is hardware else [(4242, exit_code << 8)]
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(module, 'EXPECTED', module.sha(args.exe)))
                stack.enter_context(mock.patch.dict(os.environ, {}, clear=True))
                stack.enter_context(mock.patch.object(module.resource, 'setrlimit'))
                stack.enter_context(mock.patch.object(module.subprocess, 'Popen', side_effect=launch))
                stack.enter_context(mock.patch.object(module.os, 'waitpid', side_effect=waits))
                stack.enter_context(mock.patch.object(Path, 'read_text', read))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                if module is hardware:
                    stack.enter_context(mock.patch.object(module, 'ptrace', return_value=0))
                    stack.enter_context(mock.patch.object(module.platform, 'machine', return_value='x86_64'))
                if mutation or exit_code:
                    with self.assertRaises(RuntimeError):
                        module.run(args)
                else:
                    module.run(args)
            report = json.loads((args.out / ('hardware.json' if module is hardware else 'parent.json')).read_bytes())
            self.assertEqual(report['status'], 'failed' if mutation or exit_code else 'bounded_non_reproduction')
            self.assertEqual(report['protected_inputs_preserved'], not mutation)
            self.assertFalse(report['intermittent_hold_cleared'])
            self.assertEqual(report['attempts'], [dict(attempt=0, exit_code=exit_code)])
            child.kill.assert_not_called()

    def test_hardware_terminal_scope(self):
        self.exercise(hardware)

    def test_preload_terminal_scope(self):
        self.exercise(preload)

    def test_hardware_changed_input_fails(self):
        self.exercise(hardware, mutation=True)

    def test_preload_changed_input_fails(self):
        self.exercise(preload, mutation=True)

    def test_hardware_missing_input_fails(self):
        self.exercise(hardware, mutation='delete')

    def test_preload_missing_input_fails(self):
        self.exercise(preload, mutation='delete')

    def test_hardware_uncaptured_failure_fails(self):
        self.exercise(hardware, exit_code=3)

    def test_preload_uncaptured_failure_fails(self):
        self.exercise(preload, exit_code=3)


if __name__ == '__main__':
    unittest.main()
