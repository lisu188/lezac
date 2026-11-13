import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import check_frame_elapsed_oracle as check


class FrameElapsedOracleTest(unittest.TestCase):
    def test_authentic_controlled_oracle(self):
        self.assertTrue(check.read_fixture().startswith(b'LZFEL001'))

    def test_each_frozen_identity_rejects_changes(self):
        for name in ('manifest.json', 'original.bin.gz'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='lezac-elapsed-fixture-') as folder:
                root = Path(folder)
                for source in check.FIXTURE.iterdir():
                    shutil.copyfile(source, root / source.name)
                path = root / name
                raw = bytearray(path.read_bytes())
                raw[len(raw) // 2] ^= 1
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'Controlled elapsed'):
                    check.read_fixture(root)

    def test_oracle_source_rejection_preserves_or_avoids_output(self):
        for missing in (False, True):
            for existing in (False, True):
                with self.subTest(missing=missing, existing=existing), \
                        tempfile.TemporaryDirectory(prefix='lezac-elapsed-source-') as folder:
                    root = Path(folder)
                    script = root / 'tools/check_frame_elapsed_oracle.py'
                    script.parent.mkdir()
                    shutil.copyfile(check.__file__, script)
                    oracle = script.parent / 'frame_clock_probe/oracle.py'
                    oracle.parent.mkdir()
                    if not missing:
                        oracle.write_bytes(b'changed oracle')
                    shutil.copytree(check.FIXTURE, root / 'tests/fixtures/frame_elapsed')
                    output = root / 'projection.bin'
                    if existing:
                        output.write_bytes(b'preserve projection')
                    result = subprocess.run([sys.executable, '-S', '-B', str(script), '--projection', str(output)],
                        capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
                    self.assertNotEqual(result.returncode, 0)
                    if existing:
                        self.assertEqual(output.read_bytes(), b'preserve projection')
                    else:
                        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
