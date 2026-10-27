"""Negative controls for frozen frame iteration inputs and protected outputs."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import check_frame_iteration_fixture as checker

class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='lezac-frame-iteration-fixture-')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for name in checker.INPUTS:
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(checker.ROOT/name,target)
        self.fixture=self.root/'tests/fixtures/frame_iteration'
        shutil.copytree(checker.FIXTURE,self.fixture)
        self.protected=[self.root/n for n in checker.INPUTS]+[self.fixture/'manifest.json',self.fixture/'oracle.bin.gz']

    def test_valid_export_and_identical_reuse(self):
        out=self.root/'export.bin';report=self.root/'report.json'
        result=checker.run(self.root,self.fixture,out,report)
        self.assertEqual(result['status'],'passed');self.assertEqual(len(out.read_bytes()),checker.PROJECTION_BYTES)
        self.assertEqual(checker.run(self.root,self.fixture,out,report),result)

    def test_every_modified_input_fails_with_retained_report(self):
        for target in self.protected:
            with self.subTest(path=target.relative_to(self.root)):
                before=target.read_bytes();target.write_bytes(before+b'!')
                report=self.root/'failed.json';out=self.root/'rejected.bin'
                with self.assertRaises(ValueError): checker.run(self.root,self.fixture,out,report)
                self.assertEqual(json.loads(report.read_text())['status'],'failed')
                self.assertFalse(out.exists());target.write_bytes(before)

    def test_deleted_inputs_retain_failed_reports(self):
        for target in self.protected:
            with self.subTest(path=target.relative_to(self.root)):
                before=target.read_bytes();target.unlink();report=self.root/'failed.json'
                with self.assertRaises(OSError): checker.run(self.root,self.fixture,None,report)
                self.assertEqual(json.loads(report.read_text())['status'],'failed');target.write_bytes(before)

    def test_unreadable_inputs_retain_failed_reports(self):
        original=Path.open
        for target in self.protected:
            def read(path,*args,**kwargs):
                if path==target: raise PermissionError('Controlled unreadable input')
                return original(path,*args,**kwargs)
            with self.subTest(path=target.relative_to(self.root)),patch.object(Path,'open',read):
                report=self.root/'failed.json'
                with self.assertRaises(PermissionError): checker.run(self.root,self.fixture,None,report)
                self.assertEqual(json.loads(report.read_text())['status'],'failed')

    def test_protected_output_aliases_preserve_inputs(self):
        for target in self.protected+[Path(checker.__file__).resolve()]:
            before=target.read_bytes()
            for report in (False,True):
                with self.assertRaisesRegex(ValueError,'protected input'):
                    checker.run(self.root,self.fixture,None if report else target,target if report else None)
                self.assertEqual(target.read_bytes(),before)

    def test_hardlink_aliases_preserve_inputs(self):
        target=self.protected[0];alias=self.root/'alias.bin';before=target.read_bytes()
        try: os.link(target,alias)
        except OSError as error: self.skipTest('Hardlinks unavailable: '+str(error))
        with self.assertRaisesRegex(ValueError,'protected input'): checker.run(self.root,self.fixture,alias,None)
        self.assertEqual(target.read_bytes(),before)

    def test_export_report_overlap_and_existing_output(self):
        target=self.root/'existing.bin';target.write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError,'overlap'): checker.run(self.root,self.fixture,target,target)
        report=self.root/'failed.json'
        with self.assertRaisesRegex(ValueError,'Existing frame iteration export differs'): checker.run(self.root,self.fixture,target,report)
        self.assertEqual(target.read_bytes(),b'preserve');self.assertEqual(json.loads(report.read_text())['status'],'failed')

if __name__=='__main__': unittest.main()
