"""Exercise the mutation runner's baseline gate without replacing CPU proof."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_frame_tail_mutations as runner


class BaselineGateTests(unittest.TestCase):
    def exercise(self, failure=None, wrong_fixture=False):
        with tempfile.TemporaryDirectory(prefix='lezac-tail-baseline-gate-') as directory:
            root=Path(directory)
            originals={runner.HEADER:b'protected header\n',runner.TEST:b'protected test\n'}
            for name,raw in originals.items():
                path=root/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(raw)
            fixture=root/'fixture.bin'
            fixture.write_bytes(b'wrong' if wrong_fixture else b'authenticated projection')
            out=root/'runs'
            calls=[]

            def execute(command,**kwargs):
                del kwargs
                calls.append(command)
                label='build' if command[0]=='mock-cxx' else 'unit' if len(command)==1 else 'original'
                status=1 if failure==label else 0
                text=('compiled' if label=='build' else 'frame_tail_'+label+'=ok')+'\n'
                if failure==label+'_marker':
                    text='not a successful replay\n'
                return subprocess.CompletedProcess(command,status,stdout=text.encode())

            argv=['runner','--cxx','mock-cxx','--fixture',str(fixture),'--out',str(out)]
            with patch.object(runner,'ROOT',root),patch.object(runner,'FAULTS',()), \
                    patch.object(runner.checker,'read_fixture',return_value=b'authenticated projection'), \
                    patch.object(runner.subprocess,'run',side_effect=execute),patch('sys.argv',argv):
                with contextlib.redirect_stdout(io.StringIO()):
                    if failure or wrong_fixture:
                        with self.assertRaises(ValueError):
                            runner.main()
                    else:
                        runner.main()
            report=json.loads(next(out.glob('run-*/report.json')).read_text())
            self.assertEqual(report['results'],[])
            for name,raw in originals.items():
                self.assertEqual((root/name).read_bytes(),raw)
                self.assertEqual(report['sources'][name],hashlib.sha256(raw).hexdigest())
            return report,calls

    def test_unit_failure(self):
        report,calls=self.exercise('unit')
        self.assertEqual(len(calls),2)
        self.assertEqual(report['error'],'Frame tail positive baseline failed: unit')
        self.assertFalse(report['positive_baseline_passed'])
        self.assertEqual(report['status'],'failed')

    def test_original_failure(self):
        report,calls=self.exercise('original')
        self.assertEqual(len(calls),3)
        self.assertEqual(report['error'],'Frame tail positive baseline failed: original')
        self.assertFalse(report['positive_baseline_passed'])

    def test_unit_marker_failure(self):
        report,calls=self.exercise('unit_marker')
        self.assertEqual(len(calls),2)
        self.assertEqual(report['error'],'Frame tail positive baseline failed: unit')
        self.assertFalse(report['positive_baseline_passed'])

    def test_original_marker_failure(self):
        report,calls=self.exercise('original_marker')
        self.assertEqual(len(calls),3)
        self.assertEqual(report['error'],'Frame tail positive baseline failed: original')
        self.assertFalse(report['positive_baseline_passed'])

    def test_wrong_projection(self):
        report,calls=self.exercise(wrong_fixture=True)
        self.assertEqual(calls,[])
        self.assertEqual(report['error'],'Frame tail mutation input is not the authenticated frozen projection')
        self.assertFalse(report['positive_baseline_passed'])

    def test_positive_baseline(self):
        report,calls=self.exercise()
        self.assertEqual(len(calls),3)
        self.assertEqual(report['status'],'passed')
        self.assertTrue(report['positive_baseline_passed'])


if __name__=='__main__':
    unittest.main()
