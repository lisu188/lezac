import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import check_full_pacing_fixture as check
from full_pacing_probe.trace import inspect_trace


class FullPacingFixtureTest(unittest.TestCase):
    def test_authentic_corpus(self):
        full, gate, feedback, cpu = check.read_fixture()
        self.assertEqual([item[:8] for item in (full, gate, feedback, cpu)],
            [b'LZPWAIT1', b'LZPGATE1', b'LZPFEED1', b'LZFPAC01'])

    def test_every_frozen_file_rejects_corruption(self):
        for name in ('manifest.json', 'full.bin.gz', 'gate.bin.gz', 'feedback.bin.gz',
                     'oracle-manifest.json', 'natural.csv.gz', 'natural-recipe.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='lezac-pacing-fixture-') as folder:
                root = Path(folder)
                for source in check.FIXTURE.iterdir():
                    shutil.copyfile(source, root / source.name)
                path = root / name
                raw = bytearray(path.read_bytes()); raw[len(raw) // 2] ^= 1; path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'Frozen pacing'):
                    check.read_fixture(root)

    def test_every_source_is_required_before_any_output(self):
        manifest = json.loads((check.FIXTURE / 'manifest.json').read_bytes())
        for name in manifest['sources']:
            for missing in (False, True):
                for existing in (False, True):
                    with self.subTest(name=name, missing=missing, existing=existing), \
                            tempfile.TemporaryDirectory(prefix='lezac-pacing-source-') as folder:
                        root = Path(folder)
                        for relative in ['tools/check_full_pacing_fixture.py', *manifest['sources']]:
                            target = root / relative; target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(check.ROOT / relative, target)
                        shutil.copytree(check.FIXTURE, root / 'tests/fixtures/full_pacing')
                        source = root / name
                        if missing:
                            source.unlink()
                        else:
                            source.write_bytes(source.read_bytes() + b'\nchanged retained source\n')
                        paths = [root / (kind + '.bin') for kind in ('full', 'gate', 'feedback', 'cpu')]
                        if existing:
                            for path in paths:
                                path.write_bytes(b'preserve projection')
                        command = [sys.executable, '-S', '-B', str(root / 'tools/check_full_pacing_fixture.py')]
                        for kind, path in zip(('full', 'gate', 'feedback', 'cpu'), paths):
                            command.extend(['--' + kind, str(path)])
                        result = subprocess.run(command, capture_output=True, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
                        self.assertNotEqual(result.returncode, 0)
                        for path in paths:
                            if existing:
                                self.assertEqual(path.read_bytes(), b'preserve projection')
                            else:
                                self.assertFalse(path.exists())

    def test_incomplete_and_discontinuous_traces_are_rejected(self):
        raw = gzip.decompress((check.FIXTURE / 'natural.csv.gz').read_bytes())
        lines = raw.splitlines(keepends=True)
        missing = next(i for i, line in enumerate(lines) if line.startswith(b'instruction,'))
        controls = [raw[:-4], b''.join(lines[:missing] + lines[missing+1:]), raw + b'end\n']
        with tempfile.TemporaryDirectory(prefix='lezac-pacing-terminal-') as folder:
            path = Path(folder) / 'trace.csv.gz'
            for index, control in enumerate(controls):
                with self.subTest(control=index):
                    path.write_bytes(gzip.compress(control, mtime=0))
                    with self.assertRaises(ValueError):
                        inspect_trace(path)


if __name__ == '__main__':
    unittest.main()
