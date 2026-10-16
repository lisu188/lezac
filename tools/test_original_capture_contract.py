"""Canonical asset preflight and private-display output rejection controls."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from original_capture_contract import ASSET_PINS, read_canonical_assets, validate_geometry

ROOT = Path(__file__).resolve().parents[1]


class OriginalCaptureContractTests(unittest.TestCase):
    def test_shipped_asset_pins(self):
        actual = read_canonical_assets(ROOT)
        self.assertEqual(set(actual), set(ASSET_PINS))
        self.assertEqual(len(actual), 14)

    def test_all_asset_mutations_reject_before_output_creation(self):
        with tempfile.TemporaryDirectory(prefix='lezac-canonical-assets-') as temporary:
            root = Path(temporary)
            original = read_canonical_assets(ROOT)
            for name, raw in original.items():
                (root / name).write_bytes(raw)
            producer = next(path for path in [ROOT / 'tools/frame_pacing_probe/capture.py',
                ROOT / 'tools/original_interrupt_probe/capture.py'] if path.exists())
            tree = ast.parse(producer.read_text())
            root_index = next(index for index, node in enumerate(tree.body) if isinstance(node, ast.Assign) and
                any(isinstance(target, ast.Name) and target.id == 'ROOT' for target in node.targets))
            canonical_index = root_index + 1
            self.assertIsInstance(tree.body[canonical_index], ast.Assign)
            self.assertEqual(tree.body[canonical_index].targets[0].id, 'canonical')
            self.assertEqual(tree.body[canonical_index + 1].targets[0].id, 'OUT')
            code = compile(ast.Module(body=tree.body[root_index:canonical_index+1], type_ignores=[]),
                           '<actual-capture-preflight>', 'exec')
            for name, raw in original.items():
                for changed in (raw + b'changed', bytes([raw[0] ^ 1]) + raw[1:]):
                    with self.subTest(asset=name, bytes=len(changed)):
                        (root / name).write_bytes(changed)
                        with self.assertRaisesRegex(ValueError, 'Canonical original asset differs'):
                            exec(code, dict(args=SimpleNamespace(repo=root), read_canonical_assets=read_canonical_assets))
                    (root / name).write_bytes(raw)
            (root / 'unexpected.DAT').write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError, 'asset domain differs'):
                read_canonical_assets(root)
            (root / 'unexpected.DAT').unlink()
            (root / 'LIVELS.SCH').unlink()
            with self.assertRaisesRegex(ValueError, 'asset domain differs'):
                read_canonical_assets(root)

    def test_geometry_rejection_controls(self):
        valid = 'WINDOW=123\nX=192\nY=184\nWIDTH=320\nHEIGHT=200\nSCREEN=0\n'
        self.assertEqual(validate_geometry(valid, '123')['WIDTH'], 320)
        controls = [None, '', 'bogus', 'x' * 2049, valid + 'WIDTH=320\n', valid + 'EXTRA=1\n',
                    valid.replace('SCREEN=0\n', ''), valid + '[other]\nX=0\n']
        for old, replacements in [('WINDOW=123', ['WINDOW=1', 'WINDOW=0', 'WINDOW=abc']),
                ('X=192', ['X=-1', 'X=705', 'X=1.5']), ('Y=184', ['Y=-1', 'Y=569']),
                ('WIDTH=320', ['WIDTH=640', 'WIDTH=0', 'WIDTH=True']),
                ('HEIGHT=200', ['HEIGHT=400', 'HEIGHT=0']), ('SCREEN=0', ['SCREEN=1', 'SCREEN=-1'])]:
            controls.extend(valid.replace(old, value) for value in replacements)
        for index, stdout in enumerate(controls):
            with self.subTest(control=index), self.assertRaisesRegex(ValueError, 'geometry output differs'):
                validate_geometry(stdout, '123')

    def test_missing_terminal_assets_persist_failed_report(self):
        producers = [path for path in [ROOT / 'tools/frame_pacing_probe/capture.py',
            ROOT / 'tools/original_interrupt_probe/capture.py'] if path.exists()]
        for producer in producers:
            tree = ast.parse(producer.read_text())
            finalizers = [node.finalbody for node in tree.body if isinstance(node, ast.Try) and node.finalbody]
            self.assertEqual(len(finalizers), 1)
            code = compile(ast.Module(body=finalizers[0], type_ignores=[]), '<actual-terminal-finalizer>', 'exec')
            for failure in ('deleted', 'renamed', 'unreadable'):
                with self.subTest(producer=producer.name, failure=failure), tempfile.TemporaryDirectory(
                        prefix='lezac-terminal-asset-') as temporary:
                    root = Path(temporary)
                    output = root / 'capture'
                    output.mkdir()
                    asset = root / 'asset.DAT'
                    asset.write_bytes(b'canonical')
                    if failure == 'deleted':
                        asset.unlink()
                    elif failure == 'renamed':
                        asset.rename(root / 'renamed.DAT')
                    trace = 'guest-pacing.csv' if producer.parent.name == 'frame_pacing_probe' else 'guest-irq.csv'
                    (output / trace).write_bytes(b'trace\nend\n')
                    sha = lambda raw: hashlib.sha256(raw).hexdigest()
                    report, saved = dict(status='observed', passed=True, samples=[]), []

                    def persist():
                        saved.append(copy.deepcopy(report))

                    original_read = Path.read_bytes

                    def checked_read(path):
                        if failure == 'unreadable' and path == asset:
                            raise PermissionError('controlled unreadable canonical asset')
                        return original_read(path)

                    namespace = dict(ROOT=root, OUT=output, assets={'asset.DAT': {'sha256': sha(b'canonical')}},
                        report=report, sha=sha, child=SimpleNamespace(returncode=0, poll=lambda: 0),
                        mem=None, log=None, persist=persist, json=json)
                    with mock.patch.object(Path, 'read_bytes', checked_read), self.assertRaises(RuntimeError):
                        exec(code, namespace)
                    self.assertEqual(len(saved), 1)
                    self.assertEqual(saved[0]['status'], 'failed')
                    self.assertIs(saved[0]['passed'], False)
                    self.assertIs(saved[0]['canonical_assets_unchanged'], False)
                    self.assertIn('Error', saved[0]['canonical_asset_check_error'])


if __name__ == '__main__':
    unittest.main()
