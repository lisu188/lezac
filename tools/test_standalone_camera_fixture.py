"""Reject corrupted/missing camera inputs while preserving existing outputs."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import check_standalone_camera_fixture as checker


class FixtureTests(unittest.TestCase):
    def test_rejections_and_retention(self):
        manifest = json.loads((checker.FIXTURE/'manifest.json').read_bytes())
        paths = [*manifest['assets'],*('tools/'+name for name in manifest['sources']),
            'tests/fixtures/standalone_camera/manifest.json','tests/fixtures/standalone_camera/oracle.bin.gz']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in paths:
                target = root/name
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(checker.ROOT/name,target)
            fixture = root/'tests/fixtures/standalone_camera'
            output, report = root/'export.bin', root/'report.json'
            expected = checker.read_fixture(root,fixture)
            checker.run(root,fixture,output,report)
            before = output.stat().st_mtime_ns
            checker.run(root,fixture,output,report)
            self.assertEqual(before,output.stat().st_mtime_ns)
            for name in paths:
                path = root/name
                original = path.read_bytes()
                for mutation in ('changed','missing','directory'):
                    with self.subTest(path=name,mutation=mutation):
                        if mutation == 'changed':
                            changed = bytearray(original); changed[len(changed)//2] ^= 1
                            path.write_bytes(changed)
                        else:
                            path.unlink()
                            if mutation == 'directory':
                                path.mkdir()
                        try:
                            for candidate in (output,root/'absent.bin'):
                                with self.assertRaises((ValueError,OSError)):
                                    checker.run(root,fixture,candidate,report)
                                self.assertEqual(json.loads(report.read_text())['status'],'failed')
                            self.assertEqual(output.read_bytes(),expected)
                            self.assertFalse((root/'absent.bin').exists())
                        finally:
                            if path.is_dir():
                                path.rmdir()
                            path.write_bytes(original)
            output.write_bytes(b'preserve existing export')
            with self.assertRaises(ValueError):
                checker.run(root,fixture,output,report)
            self.assertEqual(output.read_bytes(),b'preserve existing export')
            for name in paths:
                path = root/name
                before = path.read_bytes()
                with self.subTest(protected=name):
                    with self.assertRaises(ValueError):
                        checker.run(root,fixture,output,path)
                    self.assertEqual(path.read_bytes(),before)
            with self.assertRaises(ValueError):
                checker.run(root,fixture,output,output)
            self.assertEqual(output.read_bytes(),b'preserve existing export')


if __name__ == '__main__':
    unittest.main()
