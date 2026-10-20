"""Reject changed/unavailable frame-actor-pass inputs while preserving evidence."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import check_frame_actor_pass_fixture as checker


class FixtureTests(unittest.TestCase):
    def test_catalog(self):
        manifest = json.loads((checker.FIXTURE / 'manifest.json').read_text())
        expected = set(manifest['asset_sha256']) | {'tools/' + name for name in manifest['source_sha256']}
        self.assertEqual(set(checker.INPUTS), expected)
        self.assertEqual(len(checker.INPUTS), len(expected))

    def test_rejections_and_retention(self):
        paths = [*checker.INPUTS, 'tests/fixtures/frame_actor_pass/manifest.json',
            'tests/fixtures/frame_actor_pass/oracle.bin.gz']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in paths:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(checker.ROOT / name, target)
            fixture = root / 'tests/fixtures/frame_actor_pass'
            output, report = root / 'export.bin', root / 'report.json'
            checker.run(root, fixture, output, report)
            self.assertEqual(checker.sha(output.read_bytes()),
                json.loads((fixture / 'manifest.json').read_text())['projection_sha256'])
            before = output.stat().st_mtime_ns
            checker.run(root, fixture, output, report)
            self.assertEqual(before, output.stat().st_mtime_ns)
            retained = b'preserve original frame actor pass evidence'
            output.write_bytes(retained)
            for name in paths:
                path = root / name
                original = path.read_bytes()
                for mutation in ('changed', 'missing', 'directory'):
                    with self.subTest(path=name, mutation=mutation):
                        if mutation == 'changed':
                            altered = bytearray(original)
                            altered[len(altered) // 2] ^= 1
                            path.write_bytes(altered)
                        else:
                            path.unlink()
                            if mutation == 'directory':
                                path.mkdir()
                        try:
                            for candidate in (output, root / 'absent.bin'):
                                with self.assertRaises((ValueError, OSError)):
                                    checker.run(root, fixture, candidate, report)
                                self.assertEqual(json.loads(report.read_text())['status'], 'failed')
                            self.assertEqual(output.read_bytes(), retained)
                            self.assertFalse((root / 'absent.bin').exists())
                        finally:
                            if path.is_dir():
                                path.rmdir()
                            path.write_bytes(original)
                for export, receipt in ((output, path), (path, report)):
                    with self.assertRaises(ValueError):
                        checker.run(root, fixture, export, receipt)
                    self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(ValueError):
                checker.run(root, fixture, output, report)
            self.assertEqual(output.read_bytes(), retained)
            with self.assertRaises(ValueError):
                checker.run(root, fixture, output, output)
            self.assertEqual(output.read_bytes(), retained)


if __name__ == '__main__':
    unittest.main()
