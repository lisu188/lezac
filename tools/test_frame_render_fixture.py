"""Reject altered, missing or unreadable render evidence and preserve failed exports."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from check_frame_render_fixture import ROOT,FIXTURE,read_fixture,run


class FrozenRenderTest(unittest.TestCase):
    def test_contract_and_rejections(self):
        raw=read_fixture()
        with tempfile.TemporaryDirectory(prefix='render-fixture-') as temporary:
            root=Path(temporary)/'repo'
            fixture=root/'tests/fixtures/frame_render'
            fixture.mkdir(parents=True)
            (root/'tools').mkdir()
            manifest=json.loads((FIXTURE/'manifest.json').read_bytes())
            relatives=[Path(name) for name in manifest['assets']]
            relatives.extend(Path('tools')/name for name in manifest['sources'])
            relatives.extend(Path('tests/fixtures/frame_render')/name for name in ('manifest.json','oracle.bin.gz'))
            for relative in relatives:
                shutil.copyfile(ROOT/relative,root/relative)
            out=Path(temporary)/'export.bin'
            report=Path(temporary)/'report.json'
            self.assertEqual(run(root,fixture,out,report)['status'],'passed')
            before=out.stat().st_mtime_ns
            self.assertEqual(run(root,fixture,out,report)['status'],'passed')
            self.assertEqual(out.stat().st_mtime_ns,before)
            for relative in relatives:
                path=root/relative
                original=path.read_bytes()
                for fault in ('changed','deleted','renamed','unreadable'):
                    for existing in (False,True):
                        with self.subTest(path=str(relative),fault=fault,existing=existing):
                            if existing:
                                out.write_bytes(raw)
                            elif out.exists():
                                out.unlink()
                            if fault=='changed':
                                path.write_bytes(original+b'!')
                            elif fault=='deleted':
                                path.unlink()
                            elif fault=='renamed':
                                path.rename(path.with_name(path.name+'.moved'))
                            else:
                                path.unlink()
                                path.mkdir()
                            with self.assertRaises((ValueError,OSError)):
                                run(root,fixture,out,report)
                            self.assertEqual(json.loads(report.read_text())['status'],'failed')
                            self.assertEqual(out.read_bytes() if existing else out.exists(),raw if existing else False)
                            if path.is_dir():
                                path.rmdir()
                            if fault=='renamed':
                                path.with_name(path.name+'.moved').rename(path)
                            path.write_bytes(original)
            out.write_bytes(b'preserve foreign output')
            with self.assertRaises(ValueError):
                run(root,fixture,out,report)
            self.assertEqual(out.read_bytes(),b'preserve foreign output')


if __name__=='__main__':
    unittest.main()
