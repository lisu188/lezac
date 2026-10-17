import hashlib
from pathlib import Path
import tempfile
import unittest

from frame_foreground_probe.sdl_provenance import loaded_library,MARKER

class SdlRuntimeProvenanceTest(unittest.TestCase):
    def test_reported_runtime_identity(self):
        with tempfile.TemporaryDirectory(prefix='lezac-sdl-identity-') as folder:
            expected=Path(folder)/'sdk.so';expected.write_bytes(b'pinned SDL image')
            digest=hashlib.sha256(expected.read_bytes()).hexdigest();marker=(MARKER+str(expected)+'\n').encode()
            self.assertEqual(loaded_library(marker,expected,digest),dict(path=str(expected.resolve()),sha256=digest,verified=True))
            alias=Path(folder)/'alias.so'
            try:alias.symlink_to(expected)
            except OSError:pass
            else:self.assertEqual(loaded_library((MARKER+str(alias)+'\n').encode(),expected,digest)['sha256'],digest)

    def test_counterexamples_rejected(self):
        with tempfile.TemporaryDirectory(prefix='lezac-sdl-counterexample-') as folder:
            expected=Path(folder)/'sdk.so';expected.write_bytes(b'pinned SDL image')
            other=Path(folder)/'system.so';other.write_bytes(b'different SDL image')
            same=Path(folder)/'same-bytes-outside-sdk.so';same.write_bytes(expected.read_bytes())
            digest=hashlib.sha256(expected.read_bytes()).hexdigest();marker=(MARKER+str(expected)+'\n').encode()
            controls=[b'',b'diagnostic only\n',MARKER.encode()+b'\n',marker+marker,
                (MARKER+str(other)+'\n').encode(),(MARKER+str(same)+'\n').encode(),
                (MARKER+str(Path(folder)/'missing.so')+'\n').encode()]
            for control in controls:
                with self.subTest(control=control),self.assertRaises((ValueError,OSError)):
                    loaded_library(control,expected,digest)
            expected.write_bytes(b'changed after process start')
            with self.assertRaises(ValueError):loaded_library(marker,expected,digest)

if __name__=='__main__':unittest.main()
