"""Reject changed or missing width evidence without replacing an output."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_viewport_width_fixture as checker
from original_capture_contract import ASSET_PINS


class FixtureTests(unittest.TestCase):
    def test_valid_and_reused_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'width.bin'
            checker.export(output)
            self.assertEqual(output.stat().st_size, 6721438)
            previous = output.stat().st_mtime_ns
            checker.export(output)
            self.assertEqual(output.stat().st_mtime_ns, previous)

    def test_bound_inputs(self):
        paths = [checker.FIXTURE / 'manifest.json', checker.FIXTURE / 'oracle.bin.gz',
                 checker.ROOT / 'tools/viewport_width_oracle.py', checker.ROOT / 'tools/render_view_gate_oracle.py',
                 checker.ROOT / 'tools/render_view_gate_origin.py',
                 checker.ROOT / 'tests/fixtures/foreground_live/manifest.json',
                 checker.ROOT / 'tests/fixtures/foreground_live/natural-recipe.json',
                 checker.ROOT / 'tools/frame_foreground_live_probe/lezac_work_probe.h']
        paths.extend(checker.ROOT / name for name in ASSET_PINS)
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
                    if path == target and target.name in ASSET_PINS:
                        if missing:
                            raise FileNotFoundError(str(path))
                        return io.BytesIO(target_bytes + b'\0')
                    return original_open(path, *args, **kwargs)
                for existing in (False, True):
                    with self.subTest(target=str(target), missing=missing, existing=existing), tempfile.TemporaryDirectory() as tmp:
                        output = Path(tmp) / 'width.bin'
                        if existing:
                            output.write_bytes(b'retained-output')
                        with patch.object(Path, 'read_bytes', read), patch.object(Path, 'open', opened), \
                                self.assertRaises((ValueError, OSError)), contextlib.redirect_stdout(io.StringIO()):
                            checker.export(output)
                        if existing:
                            self.assertEqual(output.read_bytes(), b'retained-output')
                        else:
                            self.assertFalse(output.exists())
                        controls += 1
        self.assertEqual(controls, 88)


if __name__ == '__main__':
    unittest.main()
