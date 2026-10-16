"""Exercise the actual producer preflight/finalizer without launching DOSBox."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from original_capture_contract import read_canonical_assets

ROOT = Path(__file__).resolve().parents[1]
PRODUCER = ROOT / 'tools/timer_irq_probe/capture.py'


class TimerIrqCaptureTests(unittest.TestCase):
    def test_canonical_preflight_precedes_output_creation(self):
        tree = ast.parse(PRODUCER.read_text())
        at = next(index for index, node in enumerate(tree.body) if isinstance(node, ast.Assign) and
                  any(isinstance(target, ast.Name) and target.id == 'ROOT' for target in node.targets))
        self.assertEqual(tree.body[at + 1].targets[0].id, 'canonical')
        self.assertEqual(tree.body[at + 2].targets[0].id, 'OUT')
        code = compile(ast.Module(body=tree.body[at:at + 2], type_ignores=[]), '<actual-preflight>', 'exec')
        assets = read_canonical_assets(ROOT)
        with tempfile.TemporaryDirectory(prefix='lezac-dos-time-preflight-') as directory:
            root = Path(directory)
            for name, raw in assets.items():
                (root / name).write_bytes(raw)
            for name, raw in assets.items():
                (root / name).write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
                with self.subTest(asset=name), self.assertRaises(ValueError):
                    exec(code, dict(args=SimpleNamespace(repo=root), read_canonical_assets=read_canonical_assets))
                (root / name).write_bytes(raw)

    def finalizer(self, failure):
        tree = ast.parse(PRODUCER.read_text())
        finalizers = [node.finalbody for node in tree.body if isinstance(node, ast.Try) and node.finalbody]
        self.assertEqual(len(finalizers), 1)
        code = compile(ast.Module(body=finalizers[0], type_ignores=[]), '<actual-finalizer>', 'exec')
        with tempfile.TemporaryDirectory(prefix='lezac-dos-time-finalizer-') as directory:
            root = Path(directory)
            output = root / 'capture'
            output.mkdir()
            asset = root / 'asset.DAT'
            asset.write_bytes(b'canonical')
            if failure == 'deleted':
                asset.unlink()
            if failure == 'renamed':
                asset.rename(root / 'renamed.DAT')
            if failure != 'no-trace':
                (output / 'guest-timer.csv').write_bytes(b'trace\n' if failure == 'no-end' else b'trace\nend\n')
            sha = lambda raw: hashlib.sha256(raw).hexdigest()
            report, saved = dict(status='observed', passed=True, samples=[]), []
            original_read = Path.read_bytes

            def read(path):
                if failure == 'unreadable' and path == asset:
                    raise PermissionError('controlled unreadable original asset')
                return original_read(path)

            namespace = dict(ROOT=root, OUT=output, assets={'asset.DAT': {'sha256': sha(b'canonical')}},
                report=report, sha=sha, child=SimpleNamespace(returncode=-11 if failure == 'child-exit' else 0, poll=lambda: 0),
                mem=None, log=None, persist=lambda: saved.append(copy.deepcopy(report)), json=json)
            with mock.patch.object(Path, 'read_bytes', read), self.assertRaises(RuntimeError):
                exec(code, namespace)
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]['status'], 'failed')
            self.assertIs(saved[0]['passed'], False)
            if failure in ('deleted', 'renamed', 'unreadable'):
                self.assertIs(saved[0]['canonical_assets_unchanged'], False)
                self.assertIn('Error', saved[0]['canonical_asset_check_error'])

    def test_missing_and_unreadable_assets_persist_failure(self):
        for failure in ('deleted', 'renamed', 'unreadable'):
            with self.subTest(failure=failure):
                self.finalizer(failure)

    def test_missing_trace_marker_and_child_failure_persist(self):
        for failure in ('no-trace', 'no-end', 'child-exit'):
            with self.subTest(failure=failure):
                self.finalizer(failure)


if __name__ == '__main__':
    unittest.main()
