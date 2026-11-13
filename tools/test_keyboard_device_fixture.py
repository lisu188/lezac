"""Reject stale controller evidence without replacing output or source inputs."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_keyboard_device_fixture as checker


class FixtureTests(unittest.TestCase):
    def test_valid_reuse(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp) / 'device.bin'
            checker.export(path)
            self.assertEqual(path.stat().st_size, 8917540)
            before = path.stat().st_mtime_ns
            checker.export(path)
            self.assertEqual(path.stat().st_mtime_ns, before)
            self.assertEqual(set(Path(tmp).iterdir()), {path})

    def test_bound_inputs(self):
        manifest = json.loads((checker.FIXTURE / 'manifest.json').read_bytes())
        targets = [checker.FIXTURE / 'manifest.json'] + [checker.FIXTURE / item['name'] for item in manifest['files']]
        targets += [checker.ROOT / name for name in manifest['sources']]
        targets += [checker.irq.FIXTURE / name for name in ('manifest.json', 'natural-r5.csv.gz', 'natural-r6.csv.gz')]
        targets += [checker.ROOT / 'LEZAC.EXE']
        self.assertEqual(len(targets), 10)
        original, opened = Path.read_bytes, Path.open
        controls = 0
        for target in targets:
            raw = original(target)
            for missing in (False, True):
                def read(path):
                    if path == target:
                        if missing: raise FileNotFoundError(str(path))
                        return raw + b'\0'
                    return original(path)
                def open_path(path, *args, **kwargs):
                    if path == target and path.name == 'LEZAC.EXE':
                        if missing: raise FileNotFoundError(str(path))
                        return io.BytesIO(raw + b'\0')
                    return opened(path, *args, **kwargs)
                for existing in (False, True):
                    with self.subTest(target=str(target), missing=missing, existing=existing), tempfile.TemporaryDirectory() as tmp:
                        path = Path(tmp) / 'device.bin'
                        if existing: path.write_bytes(b'old-device')
                        with patch.object(Path, 'read_bytes', read), patch.object(Path, 'open', open_path), \
                                contextlib.redirect_stdout(io.StringIO()), self.assertRaises((ValueError, OSError)):
                            checker.export(path)
                        if existing: self.assertEqual(path.read_bytes(), b'old-device')
                        else: self.assertFalse(path.exists())
                        self.assertEqual(set(Path(tmp).iterdir()), {path} if existing else set())
                        controls += 1
        self.assertEqual(controls, 40)

    def test_export_failures(self):
        for existing in (False, True):
            for operation in ('fsync', 'replace'):
                with self.subTest(existing=existing, operation=operation), tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / 'device.bin'
                    if existing: path.write_bytes(b'old-device')
                    with patch.object(checker, 'read_fixture', return_value=b'new-device'), \
                            patch.object(checker.os, operation, side_effect=OSError('injected output failure')), self.assertRaises(OSError):
                        checker.export(path)
                    if existing: self.assertEqual(path.read_bytes(), b'old-device')
                    else: self.assertFalse(path.exists())
                    self.assertEqual(set(Path(tmp).iterdir()), {path} if existing else set())

    def test_source_output_aliases(self):
        for path in (checker.FIXTURE / 'manifest.json', checker.ROOT / 'LEZAC.EXE',
                     checker.ROOT / 'tools/keyboard_device_probe/port_steps.py'):
            before = path.read_bytes(), path.stat().st_mtime_ns
            with patch.object(checker, 'read_fixture', return_value=b'new-device'), self.assertRaises(ValueError):
                checker.export(path)
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)


if __name__ == '__main__':
    unittest.main()
