"""Check diagnostic terminal reports without launching or tracing a guest."""
import argparse
import contextlib
import ctypes
import io
import json
import os
import signal
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

    def exercise(self, module, mutation=False, exit_code=0, collector_mode=None, validation_only=False,
                 bank=None, attempts=1, unit_calibration=False):
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
                                      attempts=attempts, calibrate_unit=bank is None or unit_calibration, calibrate_cli=False,
                                      validation_only=validation_only, contact_guard_bank=bank)
            child = mock.Mock(pid=4242, returncode=None)
            child.poll.return_value = None
            child.communicate.return_value = (b'test-only output', b'frame_actor_pass=failed test-only\n' if validation_only or bank else b'')

            def launch(*unused, **kwargs):
                child.returncode = None
                if mutation == 'delete':
                    args.fixture.unlink()
                elif mutation:
                    args.fixture.write_bytes(b'changed after input catalog')
                if collector_mode:
                    kwargs['stderr'].write(b'LEZAC_THROW_STOP:Frame actor test-only ownership differs\n')
                    kwargs['stderr'].flush()
                return child

            read_text = Path.read_text

            def read(path, *positional, **keywords):
                if str(path) == '/proc/4242/maps':
                    return '1000-2000 r-xp 00002000 00:00 1 ' + str(args.exe) + '\n'
                return read_text(path, *positional, **keywords)

            waits = ([(4242, 0), (4242, exit_code << 8)] if module is hardware else
                     [(4242, exit_code << 8)]) * attempts
            if collector_mode:
                waits = [(4242, (int(signal.SIGSTOP) << 8) | 0x7f)]
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(module, 'EXPECTED', module.sha(args.exe)))
                stack.enter_context(mock.patch.dict(os.environ, {}, clear=True))
                stack.enter_context(mock.patch.object(module.resource, 'setrlimit'))
                stack.enter_context(mock.patch.object(module.subprocess, 'Popen', side_effect=launch))
                stack.enter_context(mock.patch.object(module.os, 'waitpid', side_effect=waits))
                stack.enter_context(mock.patch.object(Path, 'read_text', read))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                if collector_mode:
                    stack.enter_context(mock.patch.object(module, 'collect_guard',
                        side_effect=RuntimeError('controlled collector failure') if collector_mode == 'failure' else None,
                        return_value={'status': 'failure_throw_captured'}))
                if module is hardware:
                    stack.enter_context(mock.patch.object(module, 'ptrace', return_value=0))
                    stack.enter_context(mock.patch.object(module.platform, 'machine', return_value='x86_64'))
                    stack.enter_context(mock.patch.object(module.time, 'sleep'))
                if mutation or exit_code or collector_mode == 'failure':
                    with self.assertRaises(RuntimeError):
                        module.run(args)
                else:
                    module.run(args)
            report = json.loads((args.out / ('hardware.json' if module is hardware else 'parent.json')).read_bytes())
            expected = 'failed' if mutation or exit_code or collector_mode == 'failure' else (
                'throw_captured' if collector_mode else 'bounded_non_reproduction')
            if (validation_only or bank) and exit_code:
                expected = 'other_failures_without_target_capture'
            self.assertEqual(report['status'], expected)
            self.assertEqual(report['protected_inputs_preserved'], not mutation)
            self.assertFalse(report['intermittent_hold_cleared'])
            self.assertEqual(report['attempts'], [] if collector_mode else
                             [dict(attempt=i, exit_code=exit_code) for i in range(attempts)])
            if collector_mode:
                child.kill.assert_called_once();child.wait.assert_called_once()
            else:
                child.kill.assert_not_called()
            return report

    def test_contact_stop_witness_agreement_and_fail_closed_cleanup(self):
        for fault in (None, 'memory', 'registers', 'peek_error', 'proc_second_error'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(
                    prefix='lezac-stop-witness-', dir='/dev/shm') as directory:
                base = Path(directory)
                for name in ('exe', 'symbols', 'fixture', 'LEZAC.EXE'):
                    (base / name).write_bytes(('test-only ' + name).encode())
                layout = base / 'layout.json'
                layout.write_text(json.dumps(dict(debug_offset=848, register_bytes=216, word_bytes=8)))
                args = argparse.Namespace(exe=base / 'exe', symbols=base / 'symbols',
                    fixture=base / 'fixture', root=base, layout=layout, out=base / 'out',
                    attempts=1, calibrate_unit=True, calibrate_cli=False,
                    validation_only=False, contact_guard_bank='updates')
                child = mock.Mock(pid=4242, returncode=None)
                child.communicate.return_value = (b'', b'')
                original_read = Path.read_text
                register_reads = 0
                proc_reads = 0
                value = 0x20000000001000

                def read_text(path, *positional, **keywords):
                    if str(path) == '/proc/4242/maps':
                        return '1000-2000 r-xp 00001000 00:00 1 ' + str(args.exe) + '\n'
                    if str(path) == '/proc/4242/status':
                        return 'State:\tT (stopped)\nTracerPid:\t0\n'
                    return original_read(path, *positional, **keywords)

                def ptrace(request, pid, address=0, data=0):
                    nonlocal register_reads
                    if request == 12:
                        register_reads += 1
                        live = ctypes.cast(data, ctypes.POINTER(hardware.Registers)).contents
                        live.rip, live.rsp = 0x9fcbc, 0x200000
                        if fault == 'registers' and register_reads == 2:
                            live.rcx = 1
                    if request == 3:
                        return 4
                    if request == 2:
                        if fault == 'peek_error':
                            raise OSError('test-only failed peek')
                        return (0 if address == 0x201018 else value) ^ (1 if fault == 'memory' else 0)
                    return 0

                def pread(fd, size, address):
                    nonlocal proc_reads
                    proc_reads += 1
                    if fault == 'proc_second_error' and proc_reads == 2:
                        raise OSError('test-only failed second proc read')
                    return (0 if address == 0x201018 else value).to_bytes(8, 'little')[:size]

                collector = mock.Mock(return_value=dict(status='failure_throw_captured'))
                with contextlib.ExitStack() as stack:
                    stack.enter_context(mock.patch.object(hardware, 'EXPECTED', hardware.sha(args.exe)))
                    stack.enter_context(mock.patch.dict(os.environ, {}, clear=True))
                    stack.enter_context(mock.patch.object(hardware.resource, 'setrlimit'))
                    stack.enter_context(mock.patch.object(hardware.platform, 'machine', return_value='x86_64'))
                    stack.enter_context(mock.patch.object(hardware.subprocess, 'Popen', return_value=child))
                    stack.enter_context(mock.patch.object(hardware.os, 'waitpid', side_effect=[
                        (4242, 0), (4242, (int(signal.SIGTRAP) << 8) | 0x7f)]))
                    stack.enter_context(mock.patch.object(Path, 'read_text', read_text))
                    stack.enter_context(mock.patch.object(hardware, 'ptrace', side_effect=ptrace))
                    stack.enter_context(mock.patch.object(hardware.os, 'pread', side_effect=pread))
                    stack.enter_context(mock.patch('builtins.open', mock.mock_open()))
                    stack.enter_context(mock.patch.object(hardware, 'verify_pinned_contact_sites'))
                    stack.enter_context(mock.patch.object(hardware, 'collect_guard', collector))
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    if fault:
                        with self.assertRaises(OSError if fault in ('peek_error', 'proc_second_error') else ValueError):
                            hardware.run(args)
                    else:
                        hardware.run(args)
                report = json.loads((args.out / 'hardware.json').read_bytes())
                self.assertEqual(report['message'], 'Frame actor contact ID-toggle/callee ownership differs')
                self.assertTrue(report['protected_inputs_preserved'])
                self.assertFalse(report['intermittent_hold_cleared'])
                child.kill.assert_called_once()
                child.wait.assert_called_once()
                if fault:
                    self.assertEqual(report['status'], 'failed')
                    self.assertNotEqual(report['stop_read_witness']['status'], 'cross_reader_agreement')
                    collector.assert_not_called()
                    if fault in ('peek_error', 'proc_second_error'):
                        sample, = report['stop_read_witness']['samples']
                        self.assertEqual(sample['status'], 'incomplete')
                        self.assertEqual(sample['proc_first_hex'], value.to_bytes(8, 'little').hex())
                        self.assertEqual('ptrace_hex' in sample, fault == 'proc_second_error')
                else:
                    self.assertEqual(report['status'], 'hardware_guard_captured')
                    self.assertEqual(report['native_validation']['host_metadata_bytes_read'], 33)
                    self.assertEqual(report['stop_read_witness']['host_memory_bytes_returned'], 106)
                    self.assertEqual(report['stop_read_witness']['status'], 'cross_reader_agreement')
                    collector.assert_called_once()

    def test_preload_failed_collector_reaps_child(self):
        self.exercise(preload, collector_mode='failure')

    def test_preload_successful_collector_reaps_child(self):
        self.exercise(preload, collector_mode='success')

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

    def test_targeted_observation_does_not_hide_other_failures(self):
        self.exercise(hardware, exit_code=1, validation_only=True)

    def test_contact_banks_rotate_without_hiding_uncaptured_failures(self):
        report = self.exercise(hardware, exit_code=1, bank='all', attempts=2)
        self.assertTrue(report['validation_only'])
        self.assertEqual([item['bank'] for item in report['watch_history']], ['queries', 'updates'])
        for item in report['watch_history']:
            self.assertEqual(item['offsets'], list(hardware.GUARD_BANKS[item['bank']]))
            self.assertEqual(item['enabled_slots'], [0, 1, 2, 3])
        self.assertEqual(len(report['uncaptured_failures']), 2)

    def test_fixed_contact_bank_keeps_all_four_guards_enabled(self):
        for bank in hardware.GUARD_BANKS:
            report = self.exercise(hardware, bank=bank, attempts=2)
            self.assertEqual(report['status'], 'bounded_non_reproduction')
            self.assertEqual([item['bank'] for item in report['watch_history']], [bank, bank])
            self.assertTrue(all(item['enabled_slots'] == [0, 1, 2, 3] for item in report['watch_history']))

    def test_contact_unit_calibration_is_explicit_not_natural_replay(self):
        report = self.exercise(hardware, bank='queries', unit_calibration=True)
        self.assertTrue(report['calibration'])
        self.assertEqual(report['calibration_kind'], 'unit_negative_controls_contact_guards')
        self.assertFalse(report['late_attach'])
        self.assertFalse(report['intermittent_hold_cleared'])

    def test_preload_uncaptured_failure_fails(self):
        self.exercise(preload, exit_code=3)


if __name__ == '__main__':
    unittest.main()
