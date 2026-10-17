"""Reject stale IRQ1 provenance and preserve both new and existing outputs."""
import contextlib
import errno
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_keyboard_irq_fixture as checker
from keyboard_irq_probe.contract import finalize_assets, require_success
from original_capture_contract import ASSET_PINS


class FixtureTests(unittest.TestCase):
    @staticmethod
    def prepare_outputs(tmp, existing):
        paths = Path(tmp) / 'cpu.bin', Path(tmp) / 'bios.bin'
        for path, present in zip(paths, existing):
            if present:
                path.write_bytes(b'old-' + path.stem.encode())
        return paths

    @staticmethod
    def snapshot(paths):
        return [(path.read_bytes(), path.stat().st_mtime_ns) if path.exists() else None for path in paths]

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

    def test_missing_second_parent(self):
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as tmp:
                cpu, _ = self.prepare_outputs(tmp, (existing, False))
                bios = Path(tmp) / 'missing/bios.bin'
                before = self.snapshot((cpu, bios))
                with patch.object(checker, 'read_fixture', return_value=(b'new-cpu', b'new-bios')), self.assertRaises(OSError):
                    checker.export(cpu, bios)
                self.assertEqual(self.snapshot((cpu, bios)), before)
                self.assertEqual(set(Path(tmp).iterdir()), {cpu} if existing else set())

    def test_staging_failures(self):
        controls = 0
        for existing, phase, failure_index, code in itertools.product(
                itertools.product((False, True), repeat=2), ('allocate', 'write', 'partial-write', 'flush', 'fsync'),
                (1, 2), (errno.EACCES, errno.ENOSPC)):
            with self.subTest(existing=existing, phase=phase, failure_index=failure_index, code=code), tempfile.TemporaryDirectory() as tmp:
                paths = self.prepare_outputs(tmp, existing)
                before = self.snapshot(paths)
                mkstemp, fdopen, fsync = checker.tempfile.mkstemp, checker.os.fdopen, checker.os.fsync
                counts = dict(allocate=0, write=0, **{'partial-write': 0}, flush=0, fsync=0)

                def fail(name):
                    counts[name] += 1
                    if phase == name and counts[name] == failure_index:
                        raise OSError(code, 'injected ' + name)

                def allocate(*args, **kwargs):
                    if kwargs.get('suffix') == '.stage': fail('allocate')
                    return mkstemp(*args, **kwargs)

                class Writer:
                    def __init__(self, fd, mode): self.stream = fdopen(fd, mode)
                    def __enter__(self): return self
                    def __exit__(self, *args): self.stream.close()
                    def write(self, raw):
                        fail('write')
                        if phase == 'partial-write':
                            if counts['partial-write'] + 1 == failure_index:
                                self.stream.write(raw[:3])
                                self.stream.flush()
                            fail('partial-write')
                        return self.stream.write(raw)
                    def flush(self):
                        fail('flush')
                        return self.stream.flush()
                    def fileno(self): return self.stream.fileno()

                def sync(fd):
                    fail('fsync')
                    return fsync(fd)

                with patch.object(checker, 'read_fixture', return_value=(b'new-cpu', b'new-bios')), \
                        patch.object(checker.tempfile, 'mkstemp', allocate), patch.object(checker.os, 'fdopen', Writer), \
                        patch.object(checker.os, 'fsync', sync), self.assertRaises(OSError):
                    checker.export(*paths)
                self.assertEqual(self.snapshot(paths), before)
                self.assertEqual(set(Path(tmp).iterdir()), {path for path, present in zip(paths, existing) if present})
                controls += 1
        self.assertEqual(controls, 80)

    def test_backup_allocation_failures(self):
        controls = 0
        for existing in itertools.product((False, True), repeat=2):
            for failure_index, code in itertools.product(range(1, sum(existing) + 1), (errno.EACCES, errno.ENOSPC)):
                with self.subTest(existing=existing, failure_index=failure_index, code=code), tempfile.TemporaryDirectory() as tmp:
                    paths = self.prepare_outputs(tmp, existing)
                    before = self.snapshot(paths)
                    mkstemp = checker.tempfile.mkstemp
                    backups = []

                    def allocate(*args, **kwargs):
                        if kwargs.get('suffix') == '.backup':
                            backups.append(kwargs)
                            if len(backups) == failure_index:
                                raise OSError(code, 'injected backup allocation')
                        return mkstemp(*args, **kwargs)

                    with patch.object(checker, 'read_fixture', return_value=(b'new-cpu', b'new-bios')), \
                            patch.object(checker.tempfile, 'mkstemp', allocate), self.assertRaises(OSError):
                        checker.export(*paths)
                    self.assertEqual(self.snapshot(paths), before)
                    self.assertEqual(set(Path(tmp).iterdir()), {path for path, present in zip(paths, existing) if present})
                    controls += 1
        self.assertEqual(controls, 8)

    def test_replacement_failures(self):
        controls = 0
        for existing, phase, code in itertools.product(itertools.product((False, True), repeat=2),
                ('backup-cpu', 'backup-bios', 'publish-cpu', 'publish-bios'), (errno.EACCES, errno.ENOSPC)):
            role, name = phase.split('-')
            if role == 'backup' and not existing[0 if name == 'cpu' else 1]: continue
            with self.subTest(existing=existing, phase=phase, code=code), tempfile.TemporaryDirectory() as tmp:
                paths = self.prepare_outputs(tmp, existing)
                before = self.snapshot(paths)
                replace = checker.os.replace
                failures = []

                def replace_file(source, destination):
                    source, destination = Path(source), Path(destination)
                    if (role == 'backup' and source.name == name + '.bin' and destination.suffix == '.backup') or \
                            (role == 'publish' and source.suffix == '.stage' and destination.name == name + '.bin'):
                        failures.append(phase)
                        raise OSError(code, 'injected ' + phase)
                    return replace(source, destination)

                with patch.object(checker, 'read_fixture', return_value=(b'new-cpu', b'new-bios')), \
                        patch.object(checker.os, 'replace', replace_file), self.assertRaises(OSError):
                    checker.export(*paths)
                self.assertEqual(failures, [phase])
                self.assertEqual(self.snapshot(paths), before)
                self.assertEqual(set(Path(tmp).iterdir()), {path for path, present in zip(paths, existing) if present})
                controls += 1
        self.assertEqual(controls, 24)

    def test_single_and_paired_export(self):
        for existing, requested in itertools.product(itertools.product((False, True), repeat=2),
                ((True, False), (False, True), (True, True))):
            with self.subTest(existing=existing, requested=requested), tempfile.TemporaryDirectory() as tmp:
                paths = self.prepare_outputs(tmp, existing)
                before = self.snapshot(paths)
                with patch.object(checker, 'read_fixture', return_value=(b'new-cpu', b'new-bios')):
                    checker.export(*(path if wanted else None for path, wanted in zip(paths, requested)))
                for index, (path, wanted) in enumerate(zip(paths, requested)):
                    if wanted: self.assertEqual(path.read_bytes(), b'new-' + path.stem.encode())
                    else: self.assertEqual(self.snapshot((path,))[0], before[index])
                self.assertEqual(set(Path(tmp).iterdir()), {path for path in paths if path.exists()})

    def test_matching_output_survives_partner_failure(self):
        for matching in (0, 1):
            with tempfile.TemporaryDirectory() as tmp:
                paths = self.prepare_outputs(tmp, (True, True))
                raw = (b'new-cpu', b'new-bios')
                paths[matching].write_bytes(raw[matching])
                before = self.snapshot(paths)
                with patch.object(checker, 'read_fixture', return_value=raw), \
                        patch.object(checker.tempfile, 'mkstemp', side_effect=OSError(errno.ENOSPC, 'injected')), self.assertRaises(OSError):
                    checker.export(*paths)
                self.assertEqual(self.snapshot(paths), before)
                self.assertEqual(set(Path(tmp).iterdir()), set(paths))

    def test_failed_rollback_retains_original_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpu, bios = self.prepare_outputs(tmp, (True, True))
            replace = checker.os.replace

            def replace_file(source, destination):
                if Path(destination) == bios and Path(source).suffix in ('.stage', '.backup'):
                    raise OSError(errno.EACCES, 'injected publication and rollback failure')
                return replace(source, destination)

            with patch.object(checker, 'read_fixture', return_value=(b'new-cpu', b'new-bios')), \
                    patch.object(checker.os, 'replace', replace_file), self.assertRaisesRegex(RuntimeError, 'rollback incomplete'):
                checker.export(cpu, bios)
            self.assertEqual(cpu.read_bytes(), b'old-cpu')
            self.assertFalse(bios.exists())
            backups = list(Path(tmp).glob('*.backup'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), b'old-bios')
            self.assertEqual(set(Path(tmp).iterdir()), {cpu, backups[0]})

    def test_directory_output_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpu, bios = self.prepare_outputs(tmp, (True, False))
            bios.mkdir()
            before = self.snapshot((cpu,))
            with patch.object(checker, 'read_fixture', return_value=(b'new-cpu', b'new-bios')), self.assertRaises(ValueError):
                checker.export(cpu, bios)
            self.assertEqual(self.snapshot((cpu,)), before)
            self.assertEqual(set(Path(tmp).iterdir()), {cpu, bios})

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
