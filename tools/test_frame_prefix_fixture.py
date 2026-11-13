"""Frozen frame-prefix-window provenance and non-destructive export controls."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from check_frame_prefix_fixture import FIXTURE, ROOT, read_fixture, run
from test_frame_prefix_mutations import run as run_mutations


class FramePrefixFixtureTests(unittest.TestCase):
    def test_frozen_corpus(self):
        raw = read_fixture()
        self.assertEqual((raw[:8], len(raw)), (b'LZPRFX01', 30982063))
        self.assertEqual(run()['cases'], 238)

    def test_manifest_and_stream_corruption(self):
        with tempfile.TemporaryDirectory(prefix='lezac-frame-prefix-fixture-') as temporary:
            fixture = Path(temporary)
            for path in FIXTURE.iterdir():
                shutil.copyfile(path, fixture / path.name)
            for name in ('manifest.json', 'oracle.bin.gz'):
                path = fixture / name
                raw = path.read_bytes()
                for changed in (raw[:-1], raw + b'\n', bytes((raw[0] ^ 1,)) + raw[1:]):
                    path.write_bytes(changed)
                    with self.subTest(file=name, size=len(changed)), self.assertRaises(ValueError):
                        read_fixture(fixture=fixture)
                path.write_bytes(raw)
                path.unlink()
                with self.assertRaises(FileNotFoundError):
                    read_fixture(fixture=fixture)
                path.write_bytes(raw)

    def test_canonical_source_corruption_and_deletion(self):
        m = json.loads((FIXTURE / 'manifest.json').read_bytes())
        names = [*m['asset_sha256'], *('tools/' + name for name in m['dependency_sha256'])]
        with tempfile.TemporaryDirectory(prefix='lezac-frame-prefix-source-') as temporary:
            root = Path(temporary)
            (root / 'tools').mkdir()
            for name in names:
                shutil.copyfile(ROOT / name, root / name)
            for name in names:
                path = root / name
                raw = path.read_bytes()
                path.write_bytes(raw + b'\n')
                with self.subTest(source=name), self.assertRaisesRegex(ValueError, 'canonical source differs'):
                    read_fixture(root=root)
                path.unlink()
                with self.subTest(missing=name), self.assertRaises(FileNotFoundError):
                    read_fixture(root=root)
                path.write_bytes(raw)

    def test_repeat_export_and_existing_bytes_preserved(self):
        with tempfile.TemporaryDirectory(prefix='lezac-frame-prefix-export-') as temporary:
            output = Path(temporary) / 'corpus.bin'
            expected = run(output)
            before = output.read_bytes(), output.stat().st_mtime_ns
            self.assertEqual(run(output), expected)
            self.assertEqual((output.read_bytes(), output.stat().st_mtime_ns), before)
            output.write_bytes(b'preserve these bytes\n')
            before = output.read_bytes(), output.stat().st_mtime_ns
            with self.assertRaisesRegex(ValueError, 'preserved'):
                run(output)
            self.assertEqual((output.read_bytes(), output.stat().st_mtime_ns), before)

    def test_input_aliases_preserved(self):
        for path in (FIXTURE / 'manifest.json', FIXTURE / 'oracle.bin.gz', ROOT / 'LEZAC.EXE',
                     ROOT / 'CARO.CAR', ROOT / 'BOMOMIMK.SPR', ROOT / 'tools/frame_prefix_oracle.py'):
            before = path.read_bytes(), path.stat().st_mtime_ns
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'preserved'):
                run(path)
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_live_and_dangling_links_preserved(self):
        with tempfile.TemporaryDirectory(prefix='lezac-frame-prefix-link-') as temporary:
            folder = Path(temporary)
            target, output, corpus = folder / 'target', folder / 'output', folder / 'corpus.bin'
            target.write_bytes(b'preserved\n')
            corpus.write_bytes(read_fixture())
            try:
                output.symlink_to(target)
            except OSError as error:
                self.skipTest('Temporary symbolic links are not permitted: ' + str(error))
            for dangling in (False, True):
                if dangling:
                    target.unlink()
                with self.assertRaisesRegex(ValueError, 'link preserved'):
                    run(output)
                with self.assertRaisesRegex(ValueError, 'must not be a symbolic link'):
                    run_mutations('/not-a-compiler', corpus, output)
                self.assertTrue(output.is_symlink())
                self.assertEqual(target.exists(), not dangling)
                if not dangling:
                    self.assertEqual(target.read_bytes(), b'preserved\n')

    def test_mutations_reject_unauthenticated_input(self):
        with tempfile.TemporaryDirectory(prefix='lezac-frame-prefix-untrusted-') as temporary:
            folder = Path(temporary)
            corpus, output = folder / 'bad.bin', folder / 'output'
            corpus.write_bytes(b'not an original corpus\n')
            with self.assertRaisesRegex(ValueError, 'authenticated original frame-prefix corpus'):
                run_mutations('/not-a-compiler', corpus, output)
            self.assertFalse(output.exists())

    def test_cli_export_twice(self):
        with tempfile.TemporaryDirectory(prefix='lezac-frame-prefix-cli-') as temporary:
            output = Path(temporary) / 'corpus.bin'
            command = [sys.executable, '-S', '-B', str(ROOT / 'tools/check_frame_prefix_fixture.py'), '--out', str(output)]
            for _ in range(2):
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['bytes'], 30982063)
            self.assertEqual(output.read_bytes(), read_fixture())



if __name__ == '__main__':
    unittest.main()
