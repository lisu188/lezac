"""Failure-retention controls for the original controlled view-copy fixture."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import check_frame_view_copy_fixture as checker


class FixtureTests(unittest.TestCase):
    def test_rejections_preserve_output_and_report(self):
        paths = ('LEZAC.EXE','tools/frame_view_copy_oracle.py',
            'tests/fixtures/frame_view_copy/manifest.json','tests/fixtures/frame_view_copy/oracle.bin.gz')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in paths:
                target = root / name
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(checker.ROOT / name,target)
            fixture = root / 'tests/fixtures/frame_view_copy'
            output, report = root/'output.bin', root/'report.json'
            expected = checker.read_fixture(root,fixture)
            self.assertEqual(checker.run(root,fixture,output,report)['status'],'passed')
            before = output.stat().st_mtime_ns
            checker.run(root,fixture,output,report)
            self.assertEqual(before,output.stat().st_mtime_ns)
            for name in paths:
                path = root / name
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
                            with self.assertRaises((ValueError,OSError)):
                                checker.run(root,fixture,output,report)
                            self.assertEqual(output.read_bytes(),expected)
                            self.assertEqual(json.loads(report.read_text())['status'],'failed')
                            missing_out = root/'not-created.bin'
                            with self.assertRaises((ValueError,OSError)):
                                checker.run(root,fixture,missing_out,report)
                            self.assertFalse(missing_out.exists())
                        finally:
                            if path.is_dir():
                                path.rmdir()
                            path.write_bytes(original)
            output.write_bytes(b'preserve me')
            with self.assertRaises(ValueError):
                checker.run(root,fixture,output,report)
            self.assertEqual(output.read_bytes(),b'preserve me')
            self.assertEqual(json.loads(report.read_text())['status'],'failed')


if __name__ == '__main__':
    unittest.main()
