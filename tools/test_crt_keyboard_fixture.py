import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import check_crt_keyboard_fixture as check
from crt_keyboard_probe.trace import inspect_trace


class CrtKeyboardFixtureTest(unittest.TestCase):
    def test_authentic(self):
        cpu,classification,pending=check.read_fixture();self.assertEqual(cpu[:8],b'LZCKEY01');self.assertEqual(len(classification),196608)
        self.assertEqual(pending[:8],b'LZCKOR01')

    def test_every_file_rejects_corruption(self):
        for source in check.FIXTURE.iterdir():
            with self.subTest(name=source.name),tempfile.TemporaryDirectory(prefix='lezac-crt-keyboard-fixture-') as folder:
                root=Path(folder)
                for path in check.FIXTURE.iterdir():
                    shutil.copyfile(path,root/path.name)
                path=root/source.name;raw=bytearray(path.read_bytes());raw[len(raw)//2]^=1;path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError,'Frozen CRT keyboard'):
                    check.read_fixture(root)

    def test_all_sources_fail_before_any_output(self):
        manifest=json.loads((check.FIXTURE/'manifest.json').read_bytes())
        for name in manifest['sources']:
            for missing in (False,True):
                for existing in (False,True):
                    with self.subTest(name=name,missing=missing,existing=existing),tempfile.TemporaryDirectory(prefix='lezac-crt-keyboard-source-') as folder:
                        root=Path(folder)
                        for relative in ['tools/check_crt_keyboard_fixture.py',*manifest['sources']]:
                            path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(check.ROOT/relative,path)
                        shutil.copytree(check.FIXTURE,root/'tests/fixtures/crt_keyboard')
                        path=root/name
                        if missing:
                            path.unlink()
                        else:
                            path.write_bytes(path.read_bytes()+b'\nchanged retained source\n')
                        outputs=[root/'cpu.bin',root/'classification.bin',root/'pending.bin']
                        if existing:
                            for output in outputs:
                                output.write_bytes(b'preserve projection')
                        result=subprocess.run([sys.executable,'-S','-B',str(root/'tools/check_crt_keyboard_fixture.py'),
                            '--cpu',str(outputs[0]),'--classification',str(outputs[1]),'--pending',str(outputs[2])],capture_output=True,text=True,
                            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
                        self.assertNotEqual(result.returncode,0)
                        for output in outputs:
                            if existing:
                                self.assertEqual(output.read_bytes(),b'preserve projection')
                            else:
                                self.assertFalse(output.exists())

    def test_terminal_and_dispatch_controls(self):
        raw=gzip.decompress((check.FIXTURE/'natural.csv.gz').read_bytes());lines=raw.splitlines(keepends=True)
        index=next(i for i,line in enumerate(lines) if line.startswith(b'instruction,'))
        with tempfile.TemporaryDirectory(prefix='lezac-crt-keyboard-terminal-') as folder:
            path=Path(folder)/'trace.gz'
            for control in [raw[:-4],raw+b'end\n',b''.join(lines[:index]+lines[index+1:])]:
                path.write_bytes(gzip.compress(control,mtime=0))
                with self.assertRaises(ValueError):
                    inspect_trace(path)


if __name__=='__main__':
    unittest.main()
