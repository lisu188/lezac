import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import check_game_keyboard_fixture as check
from game_keyboard_probe.trace import inspect_trace


class GameKeyboardFixtureTest(unittest.TestCase):
    def test_authentic(self):
        self.assertEqual(check.read_fixture()[:8],b'LZGKEY01')

    def test_every_file_rejects_corruption(self):
        for source in check.FIXTURE.iterdir():
            with self.subTest(name=source.name),tempfile.TemporaryDirectory(prefix='lezac-game-keyboard-fixture-') as folder:
                root=Path(folder)
                for path in check.FIXTURE.iterdir():
                    shutil.copyfile(path,root/path.name)
                path=root/source.name;raw=bytearray(path.read_bytes());raw[len(raw)//2]^=1;path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError,'Frozen game keyboard'):
                    check.read_fixture(root)

    def test_all_sources_fail_before_output(self):
        manifest=json.loads((check.FIXTURE/'manifest.json').read_bytes())
        for name in manifest['sources']:
            for missing in (False,True):
                for existing in (False,True):
                    with self.subTest(name=name,missing=missing,existing=existing),tempfile.TemporaryDirectory(prefix='lezac-game-keyboard-source-') as folder:
                        root=Path(folder)
                        for relative in ['tools/check_game_keyboard_fixture.py',*manifest['sources']]:
                            path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(check.ROOT/relative,path)
                        shutil.copytree(check.FIXTURE,root/'tests/fixtures/game_keyboard')
                        path=root/name
                        if missing:
                            path.unlink()
                        else:
                            path.write_bytes(path.read_bytes()+b'\nchanged retained source\n')
                        output=root/'cpu.bin'
                        if existing:
                            output.write_bytes(b'preserve projection')
                        result=subprocess.run([sys.executable,'-S','-B',str(root/'tools/check_game_keyboard_fixture.py'),
                            '--cpu',str(output)],capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
                        self.assertNotEqual(result.returncode,0)
                        if existing:
                            self.assertEqual(output.read_bytes(),b'preserve projection')
                        else:
                            self.assertFalse(output.exists())

    def test_terminal_and_dispatch_controls(self):
        raw=gzip.decompress((check.FIXTURE/'natural.csv.gz').read_bytes());lines=raw.splitlines(keepends=True)
        index=next(i for i,line in enumerate(lines) if line.startswith(b'instruction,'))
        with tempfile.TemporaryDirectory(prefix='lezac-game-keyboard-terminal-') as folder:
            path=Path(folder)/'trace.gz'
            for control in [raw[:-4],raw+b'end\n',b''.join(lines[:index]+lines[index+1:])]:
                path.write_bytes(gzip.compress(control,mtime=0))
                with self.assertRaises(ValueError):
                    inspect_trace(path)


if __name__=='__main__':
    unittest.main()
