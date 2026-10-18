"""Reject changed original link inputs while preserving exports and failed reports."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import check_boss_links_fixture as checker


class FixtureTests(unittest.TestCase):
    def test_rejections_and_retention(self):
        paths=[*checker.INPUTS,'tests/fixtures/boss_links/manifest.json','tests/fixtures/boss_links/oracle.bin.gz']
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in paths:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(checker.ROOT/name,target)
            fixture=root/'tests/fixtures/boss_links'
            output,report=root/'export.bin',root/'report.json'
            expected=checker.read_fixture(root,fixture)
            checker.run(root,fixture,output,report)
            before=output.stat().st_mtime_ns
            checker.run(root,fixture,output,report)
            self.assertEqual(before,output.stat().st_mtime_ns)
            for name in paths:
                path=root/name;original=path.read_bytes()
                for mutation in ('changed','missing','directory'):
                    with self.subTest(path=name,mutation=mutation):
                        if mutation=='changed':
                            altered=bytearray(original);altered[len(altered)//2]^=1;path.write_bytes(altered)
                        else:
                            path.unlink()
                            if mutation=='directory':
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
                for out,receipt in ((output,path),(path,report)):
                    with self.assertRaises(ValueError):
                        checker.run(root,fixture,out,receipt)
                    self.assertEqual(path.read_bytes(),original)
            output.write_bytes(b'preserve export')
            with self.assertRaises(ValueError):
                checker.run(root,fixture,output,report)
            self.assertEqual(output.read_bytes(),b'preserve export')
            with self.assertRaises(ValueError):
                checker.run(root,fixture,output,output)
            self.assertEqual(output.read_bytes(),b'preserve export')


if __name__=='__main__':
    unittest.main()
