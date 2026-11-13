"""Keep frozen observer and diagnostic contracts stable across Python versions."""
import ast
from contextlib import redirect_stdout
import copy
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import check_boss_extended_combat_evidence as boss
import check_collapse_history_repetition as repetition


class ObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads((boss.EVIDENCE / 'original.json').read_bytes())
        cls.proof = json.loads(gzip.decompress((boss.EVIDENCE / 'observer_ast.json.gz').read_bytes()))

    def validate_modern(self, proof=None):
        parse = ast.parse

        def modern_parse(*args, **kwargs):
            tree = parse(*args, **kwargs)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    node.is_lazy = 0
            return tree

        with patch.object(ast.Import, '_fields', ('names', 'is_lazy')), \
                patch.object(ast.ImportFrom, '_fields', ('module', 'names', 'level', 'is_lazy')), \
                patch.object(ast, 'parse', side_effect=modern_parse):
            if proof is None:
                boss.validate_observer_variant(self.original)
            else:
                with patch.object(boss.json, 'loads', return_value=proof):
                    boss.validate_observer_variant(self.original)

    def changed_import(self, key, value, remove=False):
        proof = copy.deepcopy(self.proof)

        def change(node):
            if isinstance(node, dict):
                if node.get('type') == 'Import':
                    if remove:
                        del node['fields'][key]
                    else:
                        node['fields'][key] = value
                    return True
                return any(change(value) for value in node.values())
            return isinstance(node, list) and any(change(value) for value in node)

        self.assertTrue(change(proof['tree']))
        return proof

    def test_native_schema(self):
        boss.validate_observer_variant(self.original)

    def test_python315_eager_import_schema(self):
        self.validate_modern()

    def test_lazy_import_not_equivalent(self):
        with self.assertRaises((RuntimeError, TypeError)):
            self.validate_modern(self.changed_import('is_lazy', 1))

    def test_unknown_field_rejected(self):
        with self.assertRaises((RuntimeError, TypeError)):
            self.validate_modern(self.changed_import('unexpected', 0))

    def test_missing_required_field_rejected(self):
        with self.assertRaises((RuntimeError, TypeError)):
            self.validate_modern(self.changed_import('names', None, remove=True))


class CompressionTests(unittest.TestCase):
    def test_two_runs_keep_explicit_compression_and_evidence(self):
        compress = gzip.compress
        levels = []

        def modern_compress(data, compresslevel=6, *, mtime=0):
            levels.append(compresslevel)
            return compress(data, compresslevel=compresslevel, mtime=mtime)

        with tempfile.TemporaryDirectory(prefix='lezac-python-compat-') as directory:
            root = Path(directory)
            previous = {}
            with patch.object(gzip, 'compress', side_effect=modern_compress):
                for attempt in range(2):
                    with patch.object(sys, 'argv', ['repetition', '--out', str(root)]), \
                            redirect_stdout(io.StringIO()):
                        repetition.main()
                    current = repetition.manifest(root)
                    self.assertTrue(all(current.get(path) == digest for path, digest in previous.items()))
                    reports = list(root.glob('attempt-*/result.json'))
                    self.assertEqual(len(reports), attempt + 1)
                    self.assertTrue(all(json.loads(path.read_bytes())['passed'] for path in reports))
                    previous = current
            self.assertEqual(len(levels), 90)
            self.assertEqual(set(levels), {9})
            self.assertLess(sum(path.stat().st_size for path in root.rglob('*') if path.is_file()), 8 * 1024**2)


if __name__ == '__main__':
    result = unittest.main(exit=False).result
    if result.testsRun != 6 or not result.wasSuccessful():
        raise SystemExit(1)
    print('recovery_python_compat=ok tests=6 schema_controls=5 compression_runs=2 retained_limit_bytes=8388608 production_app=0')
