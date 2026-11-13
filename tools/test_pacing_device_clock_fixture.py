import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import check_pacing_device_clock_fixture as check
from pacing_clock_probe.trace import inspect_trace


class PacingDeviceClockFixtureTest(unittest.TestCase):
    def test_authentic(self):
        cpu,clock=check.read_fixture()
        self.assertEqual(cpu[:8],b'LZFPAC01')
        self.assertEqual(clock[:8],b'LZPDCL01')

    def test_every_file_rejects_corruption(self):
        for name in ('manifest.json','r1.csv.gz','r1-recipe.json','r2.csv.gz','r2-recipe.json'):
            with self.subTest(name=name),tempfile.TemporaryDirectory(prefix='lezac-device-clock-fixture-') as folder:
                root=Path(folder)
                for path in check.FIXTURE.iterdir():
                    shutil.copyfile(path,root/path.name)
                path=root/name;raw=bytearray(path.read_bytes());raw[len(raw)//2]^=1;path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError,'Frozen device-clock'):
                    check.read_fixture(root)

    def test_every_source_before_output(self):
        manifest=json.loads((check.FIXTURE/'manifest.json').read_bytes())
        for name in manifest['sources']:
            for missing in (False,True):
                for existing in (False,True):
                    with self.subTest(name=name,missing=missing,existing=existing), \
                            tempfile.TemporaryDirectory(prefix='lezac-device-clock-source-') as folder:
                        root=Path(folder)
                        for relative in ['tools/check_pacing_device_clock_fixture.py',*manifest['sources']]:
                            path=root/relative;path.parent.mkdir(parents=True,exist_ok=True)
                            shutil.copyfile(check.ROOT/relative,path)
                        shutil.copytree(check.FIXTURE,root/'tests/fixtures/pacing_device_clock')
                        path=root/name
                        if missing:
                            path.unlink()
                        else:
                            path.write_bytes(path.read_bytes()+b'\nchanged retained source\n')
                        outputs=[root/'cpu.bin',root/'clock.bin']
                        if existing:
                            for output in outputs:
                                output.write_bytes(b'preserve projection')
                        result=subprocess.run([sys.executable,'-S','-B',str(root/'tools/check_pacing_device_clock_fixture.py'),
                            '--cpu',str(outputs[0]),'--clock',str(outputs[1])],capture_output=True,text=True,
                            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
                        self.assertNotEqual(result.returncode,0)
                        for output in outputs:
                            if existing:
                                self.assertEqual(output.read_bytes(),b'preserve projection')
                            else:
                                self.assertFalse(output.exists())

    def test_terminal_and_dispatch_gap(self):
        raw=gzip.decompress((check.FIXTURE/'r1.csv.gz').read_bytes())
        lines=raw.splitlines(keepends=True)
        index=next(i for i,line in enumerate(lines) if line.startswith(b'instruction,'))
        controls=[raw[:-4],raw+b'end\n',b''.join(lines[:index]+lines[index+1:])]
        with tempfile.TemporaryDirectory(prefix='lezac-device-clock-trace-') as folder:
            path=Path(folder)/'trace.gz'
            for control in controls:
                path.write_bytes(gzip.compress(control,mtime=0))
                with self.assertRaises(ValueError):
                    inspect_trace(path)


if __name__=='__main__':
    unittest.main()
