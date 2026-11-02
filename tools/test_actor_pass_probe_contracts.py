"""Check source-mutation portability and bounded replay failure context."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import check_frame_actor_pass_cli as cli
import test_frame_actor_pass_mutations as mutations


class ProbeContracts(unittest.TestCase):
    def test_all_mutations_preserve_newline_independence(self):
        raw = (Path(__file__).resolve().parents[1] / mutations.HEADER).read_bytes()
        normalized = io.StringIO(raw.decode('utf-8'), newline=None).read()
        self.assertEqual(len(mutations.FAULTS), 45)
        for ending in ('\n', '\r\n', '\r'):
            original = normalized.replace('\n', ending).encode('utf-8')
            for name, before, after in mutations.FAULTS:
                with self.subTest(ending=repr(ending), mutation=name):
                    altered = mutations.altered_header(original, before, after, name)
                    self.assertEqual(altered, normalized.replace(before, after))
                    self.assertNotEqual(altered, normalized)

    def test_missing_and_duplicate_anchors_fail(self):
        for raw in (b'absent', b'anchor\nanchor'):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, 'Pass mutation anchor differs: synthetic'):
                    mutations.altered_header(raw, 'anchor', 'changed', 'synthetic')

    def test_failed_mutation_preflight_retains_report(self):
        with tempfile.TemporaryDirectory(prefix='lezac-probe-contract-') as temporary:
            root = Path(temporary)
            for name in (mutations.HEADER, mutations.TEST):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'synthetic missing anchor')
            fixture = root / 'fixture.bin'
            fixture.write_bytes(b'synthetic fixture')
            args = argparse.Namespace(cxx='must-not-run', fixture=fixture, out=root / 'out')
            with mock.patch.object(mutations, 'ROOT', root), \
                    mock.patch.object(mutations.argparse.ArgumentParser, 'parse_args', return_value=args), \
                    mock.patch.object(mutations.checker, 'read_fixture', return_value=fixture.read_bytes()), \
                    mock.patch.object(mutations.subprocess, 'run') as compiler:
                with self.assertRaisesRegex(ValueError, 'Pass mutation anchor differs: caller_ss'):
                    mutations.main()
                compiler.assert_not_called()
            reports = list(args.out.glob('run-*/report.json'))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_bytes())
            self.assertEqual(report['status'], 'failed')
            self.assertEqual(report['results'], [])
            self.assertEqual(report['error'], 'Pass mutation anchor differs: caller_ss')
            self.assertFalse(report.get('positive_baseline_passed', False))

    def test_positive_replay_retains_identity(self):
        output = b'frame_actor_pass_original=ok canonical_mz=1\n'
        report = {}
        cli.require_positive(subprocess.CompletedProcess([], 0, output), report)
        self.assertEqual(report['positive'], dict(exit_code=0, output_bytes=len(output),
            output_sha256=hashlib.sha256(output).hexdigest()))

    def test_failed_replay_surfaces_context_and_stays_failed(self):
        output = (b'frame_actor_pass_context case=722 mode=6 copy_limit=65535 budget=1 row=251 '
                  b'stage=advance dispatches=251 timer_instructions=0 timer_deliveries=0 callee=1\n'
                  b'frame_actor_pass=failed synthetic ownership differs\n')
        report = {}
        with self.assertRaisesRegex(ValueError, 'case=722 mode=6'):
            cli.require_positive(subprocess.CompletedProcess([], 1, output), report)
        self.assertEqual(report['positive']['exit_code'], 1)
        self.assertEqual(report['positive']['output_sha256'], hashlib.sha256(output).hexdigest())

    def test_success_marker_does_not_hide_nonzero_exit_or_missing_binding(self):
        controls = [(1, b'frame_actor_pass_original=ok canonical_mz=1'),
                    (0, b'frame_actor_pass_original=ok'), (0, b'canonical_mz=1')]
        for code, output in controls:
            with self.subTest(code=code, output=output):
                with self.assertRaisesRegex(ValueError, 'CLI positive control failed'):
                    cli.require_positive(subprocess.CompletedProcess([], code, output), {})

    def test_failure_console_is_bounded_and_decodes_arbitrary_bytes(self):
        output = b'not-in-tail' + b'x' * 8192 + b'\xffcontext-tail'
        report = {}
        with self.assertRaises(ValueError) as caught:
            cli.require_positive(subprocess.CompletedProcess([], -9, output), report)
        message = str(caught.exception)
        self.assertNotIn('not-in-tail', message)
        self.assertIn('context-tail', message)
        self.assertLessEqual(len(message), 4096 + 100)
        self.assertEqual(report['positive']['output_bytes'], len(output))


if __name__ == '__main__':
    unittest.main()
