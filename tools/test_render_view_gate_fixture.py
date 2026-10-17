"""Reject changed/missing original view evidence without replacing output."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_render_view_gate_fixture as checker


class FixtureTests(unittest.TestCase):
    def test_valid_and_reused_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'view.bin'
            checker.export(output)
            self.assertEqual(output.stat().st_size, 2561856)
            previous = output.stat().st_mtime_ns
            checker.export(output)
            self.assertEqual(output.stat().st_mtime_ns, previous)

    def test_bound_inputs(self):
        paths = [checker.FIXTURE / 'manifest.json', checker.FIXTURE / 'oracle.bin.gz', checker.FIXTURE / 'initialization.bin.gz',
            checker.ROOT / 'tools/render_view_gate_oracle.py', checker.ROOT / 'tools/render_view_gate_origin.py',
            checker.ROOT / 'tests/fixtures/foreground_live/manifest.json',
            checker.ROOT / 'tests/fixtures/foreground_live/natural-recipe.json',
            checker.ROOT / 'tools/frame_foreground_live_probe/lezac_work_probe.h', checker.ROOT / 'LEZAC.EXE']
        original = Path.read_bytes
        original_open = Path.open
        controls = 0
        for target in paths:
            target_bytes = original(target)
            for missing in (False, True):
                def read(path):
                    if path == target:
                        if missing:
                            raise FileNotFoundError(str(path))
                        return target_bytes + b'\0'
                    return original(path)
                def opened(path, *args, **kwargs):
                    if path == target and target.name == 'LEZAC.EXE':
                        if missing:
                            raise FileNotFoundError(str(path))
                        return io.BytesIO(target_bytes + b'\0')
                    return original_open(path, *args, **kwargs)
                for existing in (False, True):
                    with self.subTest(target=str(target), missing=missing, existing=existing), tempfile.TemporaryDirectory() as tmp:
                        output = Path(tmp) / 'view.bin'
                        if existing:
                            output.write_bytes(b'retained-output')
                        with patch.object(Path, 'read_bytes', read), patch.object(Path, 'open', opened), self.assertRaises((ValueError, OSError)), contextlib.redirect_stdout(io.StringIO()):
                            checker.export(output)
                        if existing:
                            self.assertEqual(output.read_bytes(), b'retained-output')
                        else:
                            self.assertFalse(output.exists())
                        controls += 1
        self.assertEqual(controls, 36)


if __name__ == '__main__':
    unittest.main()
