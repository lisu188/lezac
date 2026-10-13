"""Verify independent capture cleanup without executing the original game."""
import ast
from collections import Counter
import gzip
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import capture_original_collapse_contact_continuity as capture

retain_failure = capture.retain_failure


class Cpu:
    def __init__(self, label, failure):
        self.label, self.failure = label, failure

    def mem_read(self, address, size):
        if self.failure == 'ram':
            raise OSError('RAM reader failed')
        return bytes([len(self.label)]) * size

    def reg_read(self, register):
        if self.failure == 'registers':
            raise ValueError('register reader failed')
        return register + len(self.label)


class CaptureFailureTests(unittest.TestCase):
    def check_main_cleanup(self, legacy):
        path = Path(capture.__file__)
        if legacy:
            path = path.with_name('capture_original_collapse_contact_continuity_legacy.py')
        tree = ast.parse(path.read_bytes())
        main, = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main']
        handler, = [node for node in ast.walk(main) if isinstance(node, ast.ExceptHandler)]
        cleanup = compile(ast.Module(body=handler.body, type_ignores=[]), str(path), 'exec')
        initial = RuntimeError('first serialization failure')
        executors = {label: SimpleNamespace(cpu=Cpu(label, None)) for label in ('observed', 'neutral', 'fresh')}

        def output(executor):
            if executor is executors['observed']:
                raise ValueError('secondary serialization failure')
            return executor.cpu.label.encode()

        with tempfile.TemporaryDirectory(prefix='lezac-main-cleanup-') as directory:
            out = Path(directory)
            environment = dict(vars(capture), **executors, out=out, tracked=(1, 2, 3),
                output=output, report={}, error=initial, observations=[], visits=Counter(), incoming=b'input')
            try:
                try:
                    raise initial
                except BaseException:
                    exec(cleanup, environment)
            except BaseException as caught:
                if legacy:
                    self.assertIsInstance(caught, ValueError)
                    self.assertEqual(str(caught), 'secondary serialization failure')
                else:
                    self.assertIs(caught, initial)
            else:
                self.fail('capture cleanup swallowed the initial failure')
            if legacy:
                self.assertFalse((out / 'failure-fresh-ram.bin.gz').exists())
            else:
                for label in executors:
                    self.assertTrue((out / ('failure-' + label + '-ram.bin.gz')).is_file())
                    self.assertTrue((out / ('failure-' + label + '-registers.json')).is_file())

    def test_legacy_cleanup_reproduces_exception_replacement(self):
        self.check_main_cleanup(True)

    def test_active_main_cleanup_preserves_initial_failure(self):
        self.check_main_cleanup(False)

    def exercise(self, failed_label, failure):
        labels = ('observed', 'neutral', 'fresh')
        executors = [(label, SimpleNamespace(cpu=Cpu(label, failure if label == failed_label else None)))
                     for label in labels]
        initial = RuntimeError('initial capture failure')
        report = dict(passed=False, error=str(initial), error_type=type(initial).__name__)
        incoming = b'original incoming state'

        def serialize(executor):
            if executor.cpu.label == failed_label and failure == 'state':
                raise ValueError('state serializer failed')
            return executor.cpu.label.encode()

        original_write = Path.write_bytes

        def write(path, raw):
            if failure == 'write' and path.name == 'failure-' + failed_label + '-ram.bin.gz':
                raise OSError('artifact write failed')
            return original_write(path, raw)

        with tempfile.TemporaryDirectory(prefix='lezac-capture-cleanup-') as directory:
            out = Path(directory)
            with patch.object(Path, 'write_bytes', write):
                try:
                    try:
                        raise initial
                    except BaseException:
                        retain_failure(out, executors, (1, 2, 3), serialize, report, incoming)
                        raise
                except BaseException as caught:
                    self.assertIs(caught, initial)
            self.assertEqual(report['error'], 'initial capture failure')
            self.assertEqual(gzip.decompress((out / 'failure-input.bin.gz').read_bytes()), incoming)
            for label in labels:
                for kind, suffix in (('ram', 'bin.gz'), ('state', 'bin.gz'), ('registers', 'json')):
                    name = 'failure-' + label + '-' + kind + '.' + suffix
                    failed = label == failed_label and (failure == kind or (failure == 'write' and kind == 'ram'))
                    self.assertIs(report['failure_artifacts'][name]['passed'], not failed)
                    if failed:
                        self.assertIn('failed', report['failure_artifacts'][name]['error'])
                        self.assertFalse((out / name).exists())
                    elif kind == 'registers':
                        self.assertEqual(json.loads((out / name).read_bytes()), [r + len(label) for r in (1, 2, 3)])
                    else:
                        expected = label.encode() if kind == 'state' else bytes([len(label)]) * 1024**2
                        self.assertEqual(gzip.decompress((out / name).read_bytes()), expected)

    def test_artifact_failures_preserve_initial_error_and_other_executors(self):
        for label in ('observed', 'neutral', 'fresh'):
            for failure in ('state', 'ram', 'registers', 'write'):
                with self.subTest(label=label, failure=failure):
                    self.exercise(label, failure)


if __name__ == '__main__':
    unittest.main()
