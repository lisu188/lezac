"""Reject stale IRQ1 provenance and preserve both new and existing outputs."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_keyboard_irq_fixture as checker
from keyboard_irq_probe.contract import finalize_assets, require_success
from original_capture_contract import ASSET_PINS


class FixtureTests(unittest.TestCase):
    def test_valid_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpu, bios = Path(tmp) / 'cpu.bin', Path(tmp) / 'bios.bin'
            checker.export(cpu, bios)
            self.assertEqual((cpu.stat().st_size, bios.stat().st_size), (3213886, 20251540))
            previous = cpu.stat().st_mtime_ns, bios.stat().st_mtime_ns
            checker.export(cpu, bios)
            self.assertEqual((cpu.stat().st_mtime_ns, bios.stat().st_mtime_ns), previous)

    def test_bound_inputs(self):
        manifest = json.loads((checker.FIXTURE / 'manifest.json').read_bytes())
        targets = [checker.FIXTURE / 'manifest.json'] + [checker.FIXTURE / item['name'] for item in manifest['files']]
        targets += [checker.ROOT / name for name in manifest['sources']] + [checker.ROOT / name for name in ASSET_PINS]
        self.assertEqual(len(targets), 43)
        original, opened = Path.read_bytes, Path.open
        controls = 0
        for target in targets:
            before = original(target)
            for missing in (False, True):
                def read(path):
                    if path == target:
                        if missing: raise FileNotFoundError(str(path))
                        return before + b'\0'
                    return original(path)
                def open_path(path, *args, **kwargs):
                    if path == target and path.name in ASSET_PINS:
                        if missing: raise FileNotFoundError(str(path))
                        return io.BytesIO(before + b'\0')
                    return opened(path, *args, **kwargs)
                for existing in (False, True):
                    with self.subTest(target=str(target), missing=missing, existing=existing), tempfile.TemporaryDirectory() as tmp:
                        cpu, bios = Path(tmp) / 'cpu.bin', Path(tmp) / 'bios.bin'
                        if existing:
                            cpu.write_bytes(b'old-cpu'); bios.write_bytes(b'old-bios')
                        with patch.object(Path, 'read_bytes', read), patch.object(Path, 'open', open_path), \
                                contextlib.redirect_stdout(io.StringIO()), self.assertRaises((ValueError, OSError)):
                            checker.export(cpu, bios)
                        if existing:
                            self.assertEqual(cpu.read_bytes(), b'old-cpu'); self.assertEqual(bios.read_bytes(), b'old-bios')
                        else:
                            self.assertFalse(cpu.exists()); self.assertFalse(bios.exists())
                        controls += 1
        self.assertEqual(controls, 172)

    def test_alias_outputs(self):
        for existing in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'shared.bin'
                if existing: path.write_bytes(b'retained')
                with self.assertRaises(ValueError): checker.export(path, path)
                if existing: self.assertEqual(path.read_bytes(), b'retained')
                else: self.assertFalse(path.exists())

    def test_capture_terminal_asset_failures(self):
        for error in (FileNotFoundError('deleted'), PermissionError('unreadable'), ValueError('changed')):
            report = dict(status='observed', passed=True)
            with patch('keyboard_irq_probe.contract.read_canonical_assets', side_effect=error):
                finalize_assets(checker.ROOT, {}, report)
            self.assertFalse(report['canonical_assets_unchanged']); self.assertFalse(report['passed'])
            self.assertEqual(report['status'], 'failed'); self.assertIn('canonical_asset_check_error', report)
        report = dict(status='observed', passed=True)
        with patch('keyboard_irq_probe.contract.read_canonical_assets', return_value={'asset': b'changed'}):
            finalize_assets(checker.ROOT, {}, report)
        self.assertEqual(report['status'], 'failed'); self.assertFalse(report['passed'])

    def test_capture_exit_contract(self):
        valid = dict(status='observed', passed=True, canonical_assets_unchanged=True, child_exit_code=0)
        require_success(valid)
        for name, value in (('status', 'failed'), ('passed', False), ('canonical_assets_unchanged', False), ('child_exit_code', 1)):
            with self.subTest(field=name), self.assertRaises(RuntimeError):
                require_success(dict(valid, **{name: value}))


if __name__ == '__main__':
    unittest.main()
