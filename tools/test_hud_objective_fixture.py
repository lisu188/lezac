"""Reject changed original objective evidence before creating or replacing output."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_hud_objective_fixture as checker


class FixtureTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(len(checker.read_fixture()), 28453)

    def test_manifest_evidence_and_producers(self):
        paths = [checker.FIXTURE / 'manifest.json', checker.FIXTURE / 'oracle.bin.gz',
                 checker.ROOT / 'tools/hud_objective_oracle.py', checker.ROOT / 'tools/frame_hud_probe/oracle.py',
                 checker.ROOT / 'tools/check_frame_hud_fixture.py',
                 checker.ROOT / 'tests/fixtures/frame_hud/oracle.bin.gz']
        original = Path.read_bytes
        controls = 0
        for target in paths:
            for missing in (False, True):
                def read(path):
                    if path == target:
                        if missing:
                            raise FileNotFoundError(str(path))
                        return original(path) + b'\0'
                    return original(path)
                for existing in (False, True):
                    with self.subTest(target=str(target), missing=missing, existing=existing), tempfile.TemporaryDirectory() as tmp:
                        output = Path(tmp) / 'oracle.bin'
                        if existing:
                            output.write_bytes(b'retained-output')
                        with patch.object(Path, 'read_bytes', read), self.assertRaises((ValueError, FileNotFoundError)), contextlib.redirect_stdout(io.StringIO()):
                            checker.export(output)
                        if existing:
                            self.assertEqual(output.read_bytes(), b'retained-output')
                        else:
                            self.assertFalse(output.exists())
                        controls += 1
        self.assertEqual(controls, 24)


if __name__ == '__main__':
    unittest.main()
