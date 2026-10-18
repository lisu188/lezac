"""Corrupted/missing input and output-retention controls for camera evidence."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import check_frame_camera_fixture as checker


class FixtureTests(unittest.TestCase):
    def test_rejections_and_retention(self):
        paths=('LEZAC.EXE','tools/frame_camera_oracle.py',
            'tests/fixtures/frame_camera/manifest.json','tests/fixtures/frame_camera/oracle.bin.gz')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in paths:
                target=root/name
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(checker.ROOT/name,target)
            fixture=root/'tests/fixtures/frame_camera'
            output,report=root/'export.bin',root/'report.json'
            expected=checker.read_fixture(root,fixture)
            self.assertEqual(checker.run(root,fixture,output,report)['status'],'passed')
            before=output.stat().st_mtime_ns
            checker.run(root,fixture,output,report)
            self.assertEqual(before,output.stat().st_mtime_ns)
            for name in paths:
                path=root/name
                original=path.read_bytes()
                for mutation in ('changed','missing','directory'):
                    with self.subTest(path=name,mutation=mutation):
                        if mutation=='changed':
                            changed=bytearray(original);changed[len(changed)//2]^=1
                            path.write_bytes(changed)
                        else:
                            path.unlink()
                            if mutation=='directory':
                                path.mkdir()
                        try:
                            for candidate in (output,root/'not-created.bin'):
                                with self.assertRaises((ValueError,OSError)):
                                    checker.run(root,fixture,candidate,report)
                                self.assertEqual(json.loads(report.read_text())['status'],'failed')
                            self.assertEqual(output.read_bytes(),expected)
                            self.assertFalse((root/'not-created.bin').exists())
                        finally:
                            if path.is_dir():
                                path.rmdir()
                            path.write_bytes(original)
            output.write_bytes(b'keep existing output')
            with self.assertRaises(ValueError):
                checker.run(root,fixture,output,report)
            self.assertEqual(output.read_bytes(),b'keep existing output')
            self.assertEqual(json.loads(report.read_text())['status'],'failed')
            with self.assertRaises(ValueError):
                checker.run(root,fixture,output,output)
            self.assertEqual(output.read_bytes(),b'keep existing output')


if __name__=='__main__':
    unittest.main()
