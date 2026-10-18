"""Failure-retention controls for the original controlled view-copy fixture."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import check_frame_view_copy_fixture as checker


class FixtureTests(unittest.TestCase):
    def reject_overlap(self, output, report):
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in (output, report) if path.is_file()}
        with patch.object(checker, 'read_fixture', side_effect=AssertionError('Overlap reached fixture read')):
            with self.assertRaisesRegex(ValueError, 'output and report paths overlap'):
                checker.run(checker.ROOT, checker.FIXTURE, output, report)
        for path, (raw, modified) in before.items():
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(path.stat().st_mtime_ns, modified)

    def test_same_missing_path_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'same.bin'
            self.reject_overlap(output, output)
            self.assertFalse(output.exists())

    def test_same_existing_path_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'same.bin'
            for raw in (b'keep evidence', checker.read_fixture()):
                with self.subTest(bytes=len(raw)):
                    output.write_bytes(raw)
                    self.reject_overlap(output, output)

    def test_normalized_paths_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'child').mkdir()
            output, report = root / 'same.bin', root / 'child/../same.bin'
            for existing in (False, True):
                with self.subTest(existing=existing):
                    if existing:
                        output.write_bytes(b'keep normalized evidence')
                    self.reject_overlap(output, report)
                    self.assertEqual(output.exists(), existing)

    def test_symlink_aliases_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, report = root / 'same.bin', root / 'alias.bin'
            try:
                report.symlink_to(output)
            except (OSError, NotImplementedError) as error:
                self.skipTest('Symlink creation unavailable: ' + str(error))
            for existing in (False, True):
                with self.subTest(existing=existing):
                    if existing:
                        output.write_bytes(b'keep linked evidence')
                    self.reject_overlap(output, report)
                    self.assertEqual(output.exists(), existing)
                    self.assertTrue(report.is_symlink())

    def test_hardlink_aliases_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, report = root / 'same.bin', root / 'alias.bin'
            output.write_bytes(b'keep hardlinked evidence')
            try:
                report.hardlink_to(output)
            except (OSError, NotImplementedError) as error:
                self.skipTest('Hardlink creation unavailable: ' + str(error))
            self.reject_overlap(output, report)
            self.assertTrue(output.samefile(report))

    def test_distinct_outputs_still_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, report = root / 'output.bin', root / 'report.json'
            self.assertEqual(checker.run(checker.ROOT, checker.FIXTURE, output, report)['status'], 'passed')
            expected = checker.read_fixture()
            self.assertEqual(output.read_bytes(), expected)
            self.assertEqual(json.loads(report.read_text())['status'], 'passed')

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
