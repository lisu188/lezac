import gzip,itertools,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
import check_foreground_live_fixture as check
from frame_foreground_live_probe.trace import inspect_trace

class LiveForegroundFixtureTest(unittest.TestCase):
 def test_authentic(self):
  cpu,clock=check.read_fixture();self.assertEqual(cpu[:8],b'LZFFGD01');self.assertEqual(clock[:8],b'LZFGCL01')

 def test_each_file_rejects_corruption(self):
  for source in check.FIXTURE.iterdir():
   with self.subTest(name=source.name),tempfile.TemporaryDirectory(prefix='lezac-live-file-') as folder:
    root=Path(folder)
    for path in check.FIXTURE.iterdir():shutil.copyfile(path,root/path.name)
    path=root/source.name;raw=bytearray(path.read_bytes());raw[len(raw)//2]^=1;path.write_bytes(raw)
    with self.assertRaisesRegex(ValueError,'Frozen live foreground'):check.read_fixture(root)

 def test_sources_reject_before_outputs(self):
  manifest=json.loads((check.FIXTURE/'manifest.json').read_bytes())
  for name in manifest['sources']:
   for missing in (False,True):
    for existing in (False,True):
     with self.subTest(name=name,missing=missing,existing=existing),tempfile.TemporaryDirectory(prefix='lezac-live-source-') as folder:
      root=Path(folder)
      for relative in ['tools/check_foreground_live_fixture.py',*manifest['sources']]:
       path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(check.ROOT/relative,path)
      shutil.copytree(check.FIXTURE,root/'tests/fixtures/foreground_live');path=root/name
      if missing:path.unlink()
      else:path.write_bytes(path.read_bytes()+b'\nchanged retained source\n')
      outputs=[root/'cpu.bin',root/'clock.bin']
      if existing:
       for output in outputs:output.write_bytes(b'preserve projection')
      result=subprocess.run([sys.executable,'-S','-B',str(root/'tools/check_foreground_live_fixture.py'),
       '--cpu',str(outputs[0]),'--clock',str(outputs[1])],capture_output=True,text=True,
       env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=30)
      self.assertNotEqual(result.returncode,0)
      for output in outputs:
       if existing:self.assertEqual(output.read_bytes(),b'preserve projection')
       else:self.assertFalse(output.exists())

 def test_trace_requires_terminal_and_contiguous_dispatch(self):
  with gzip.open(check.FIXTURE/'natural.csv.gz','rb') as stream:lines=list(itertools.islice(stream,12))
  index=next(i for i,line in enumerate(lines) if line.startswith(b'instruction,'))
  controls=[b''.join(lines),b''.join(lines[:index]+lines[index+1:])+b'end\n',b''.join(lines)+b'end\nend\n']
  with tempfile.TemporaryDirectory(prefix='lezac-live-trace-') as folder:
   path=Path(folder)/'trace.gz'
   for control in controls:
    path.write_bytes(gzip.compress(control,mtime=0))
    with self.assertRaises(ValueError):inspect_trace(path)

if __name__=='__main__':unittest.main()
