"""Shared path-alias preservation contract for the frame fixture exporters."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class ExportAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checkers={}
        for family in ('camera','world_raster','view_copy','render'):
            if (ROOT/'tests/fixtures'/('frame_'+family)).is_dir():
                module=importlib.import_module('check_frame_'+family+'_fixture')
                cls.checkers[family]=(module,module.read_fixture())
        if not {'camera','world_raster','view_copy'}<=set(cls.checkers):
            raise RuntimeError('Mandatory frame exporter families are missing')

    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='frame-export-alias-')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)

    def paths(self,family):
        root=self.root/family;root.mkdir();return root,root/'export.bin',root/'report.json'

    def reject(self,checker,out,report):
        before={path:(path.read_bytes(),path.stat().st_mtime_ns) for path in (out,report) if path.is_file()}
        with patch.object(checker,'read_fixture',side_effect=AssertionError('Overlap reached authentication')):
            with self.assertRaisesRegex(ValueError,'overlap'):
                checker.run(checker.ROOT,checker.FIXTURE,out,report)
        for path,(raw,modified) in before.items():
            self.assertEqual(path.read_bytes(),raw)
            self.assertEqual(path.stat().st_mtime_ns,modified)

    def test_missing_same_path_is_not_created(self):
        for family,(checker,_) in self.checkers.items():
            with self.subTest(family=family):
                _,out,_=self.paths(family);self.reject(checker,out,out);self.assertFalse(out.exists())

    def test_existing_same_path_is_preserved(self):
        for family,(checker,raw) in self.checkers.items():
            with self.subTest(family=family):
                _,out,_=self.paths(family)
                for value in (b'keep evidence',raw):
                    out.write_bytes(value);self.reject(checker,out,out)

    def test_normalized_alias_is_preserved(self):
        for family,(checker,raw) in self.checkers.items():
            with self.subTest(family=family):
                root,out,_=self.paths(family);(root/'child').mkdir();alias=root/'child/../export.bin'
                self.reject(checker,out,alias);self.assertFalse(out.exists())
                out.write_bytes(raw);self.reject(checker,out,alias)

    def test_hardlink_alias_is_preserved(self):
        for family,(checker,raw) in self.checkers.items():
            with self.subTest(family=family):
                _,out,report=self.paths(family);out.write_bytes(raw)
                try:
                    report.hardlink_to(out)
                except (OSError,NotImplementedError) as error:
                    self.skipTest('Hardlink creation unavailable: '+str(error))
                self.reject(checker,out,report);self.assertTrue(out.samefile(report))

    def test_symlink_alias_is_preserved(self):
        for family,(checker,raw) in self.checkers.items():
            with self.subTest(family=family):
                _,out,report=self.paths(family)
                try:
                    report.symlink_to(out)
                except (OSError,NotImplementedError) as error:
                    self.skipTest('Symlink creation unavailable: '+str(error))
                self.reject(checker,out,report);self.assertFalse(out.exists())
                out.write_bytes(raw);self.reject(checker,out,report);self.assertTrue(report.is_symlink())

    def test_distinct_output_and_report_still_pass(self):
        for family,(checker,raw) in self.checkers.items():
            with self.subTest(family=family):
                _,out,report=self.paths(family)
                self.assertEqual(checker.run(checker.ROOT,checker.FIXTURE,out,report)['status'],'passed')
                self.assertEqual(out.read_bytes(),raw)
                self.assertEqual(json.loads(report.read_text())['status'],'passed')


if __name__=='__main__':
    unittest.main()
