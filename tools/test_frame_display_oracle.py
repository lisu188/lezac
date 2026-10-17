import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import check_frame_display_oracle as check


class FrameDisplayOracleTest(unittest.TestCase):
    def test_authentic_controlled_corpus(self):
        instructions, endpoints = check.read_fixture()
        self.assertTrue(instructions.startswith(b'LZFDIR01'))
        self.assertTrue(endpoints.startswith(b'LZFDEN01'))

    def test_each_frozen_identity_rejects_changes(self):
        for name in ('manifest.json', 'instructions.bin.gz', 'endpoints.bin.gz'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='lezac-display-fixture-') as folder:
                root = Path(folder)
                for source in check.FIXTURE.iterdir():
                    shutil.copyfile(source, root / source.name)
                path = root / name
                raw = bytearray(path.read_bytes())
                raw[len(raw) // 2] ^= 1
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'Controlled display'):
                    check.read_fixture(root)

    def test_producer_rejection_preserves_or_avoids_both_outputs(self):
        for missing in (False, True):
            for existing in (False, True):
                with self.subTest(missing=missing, existing=existing), \
                        tempfile.TemporaryDirectory(prefix='lezac-display-producer-') as folder:
                    root = Path(folder)
                    script = root / 'tools/check_frame_display_oracle.py'
                    script.parent.mkdir()
                    shutil.copyfile(check.__file__, script)
                    producer = script.parent / 'frame_display_probe/oracle.py'
                    producer.parent.mkdir()
                    if not missing:
                        producer.write_bytes(b'changed original oracle')
                    shutil.copytree(check.FIXTURE, root / 'tests/fixtures/frame_display')
                    outputs = [root / 'instructions.bin', root / 'endpoints.bin']
                    if existing:
                        for output in outputs:
                            output.write_bytes(b'preserve projection')
                    result = subprocess.run([sys.executable, '-S', '-B', str(script),
                        '--instructions', str(outputs[0]), '--endpoints', str(outputs[1])],
                        capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
                    self.assertNotEqual(result.returncode, 0)
                    for output in outputs:
                        if existing:
                            self.assertEqual(output.read_bytes(), b'preserve projection')
                        else:
                            self.assertFalse(output.exists())

    def test_second_fixture_rejection_does_not_publish_first_output(self):
        with tempfile.TemporaryDirectory(prefix='lezac-display-second-fixture-') as folder:
            root = Path(folder)
            script = root / 'tools/check_frame_display_oracle.py'
            script.parent.mkdir()
            shutil.copyfile(check.__file__, script)
            producer = script.parent / 'frame_display_probe/oracle.py'
            producer.parent.mkdir()
            shutil.copyfile(Path(check.__file__).parent / 'frame_display_probe/oracle.py', producer)
            fixture = root / 'tests/fixtures/frame_display'
            shutil.copytree(check.FIXTURE, fixture)
            (fixture / 'endpoints.bin.gz').write_bytes(b'changed second fixture')
            outputs = [root / 'instructions.bin', root / 'endpoints.bin']
            result = subprocess.run([sys.executable, '-S', '-B', str(script),
                '--instructions', str(outputs[0]), '--endpoints', str(outputs[1])], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(all(not output.exists() for output in outputs))


if __name__ == '__main__':
    unittest.main()
