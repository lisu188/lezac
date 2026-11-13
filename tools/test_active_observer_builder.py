"""Exercise pristine-observer preflight without extracting or compiling sources."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PATH=Path(__file__).with_name('active_frame_probe')/'build.py'
spec=importlib.util.spec_from_file_location('active_observer_builder',PATH)
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@unittest.skipUnless(Path('/dev/shm').is_dir(),'Linux RAM-only builder')
class BuilderPreflight(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='lezac-builder-controls-',dir='/dev/shm')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.inputs=[self.root/name for name in ('archive','descriptor','distribution','sdk','runtime','probe')]
        for path in self.inputs:
            path.write_bytes(b'preflight-only')
        self.hashes=dict(zip(self.inputs,(builder.ARCHIVE_SHA,builder.DSC_SHA,builder.DISTRIBUTION_SHA,
            builder.SDK_SHA,builder.SDL_SHA,builder.PROBE_SHA)))

    def reject(self,out,hashes=None,free=3*1024**3):
        hashes=self.hashes if hashes is None else hashes
        with patch.object(builder,'sha',side_effect=lambda path:hashes[path]), \
                patch.object(builder.shutil,'disk_usage',return_value=SimpleNamespace(free=free)), \
                patch.object(builder.subprocess,'run',side_effect=AssertionError('Preflight started a subprocess')):
            with self.assertRaises(ValueError):
                builder.build(*self.inputs[:5],out,self.inputs[5])

    def test_every_input_digest_is_required(self):
        for path in self.inputs:
            with self.subTest(input=path.name):
                hashes=dict(self.hashes);hashes[path]='0'*64
                out=self.root/('rejected-'+path.name)
                self.reject(out,hashes)
                self.assertFalse(out.exists())

    def test_non_ram_output_is_rejected(self):
        self.reject(Path('/usr/lezac-builder-must-not-write'))

    def test_existing_output_is_preserved(self):
        marker=self.root/'keep';marker.write_bytes(b'owned evidence')
        self.reject(self.root)
        self.assertEqual(marker.read_bytes(),b'owned evidence')

    def test_low_ram_reserve_is_rejected(self):
        out=self.root/'low-reserve'
        self.reject(out,free=2*1024**3-1)
        self.assertFalse(out.exists())

    def test_symlink_escape_is_rejected(self):
        link=self.root/'outside';link.symlink_to('/usr',target_is_directory=True)
        self.reject(link/'lezac-builder-must-not-write')


if __name__=='__main__':
    unittest.main()
