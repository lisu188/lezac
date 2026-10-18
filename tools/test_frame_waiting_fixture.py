"""Frozen waiting-window provenance and non-destructive export controls."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from check_frame_waiting_fixture import FIXTURE, ROOT, read_fixture, run
from test_frame_waiting_mutations import run as run_mutations

EXE = None


class WaitingFixtureTests(unittest.TestCase):
    def test_frozen_corpus(self):
        raw = read_fixture()
        self.assertEqual((raw[:8], len(raw)), (b'LZWAIT01', 27514428))
        self.assertEqual(run()['cases'], 238)

    def test_manifest_and_stream_corruption(self):
        with tempfile.TemporaryDirectory(prefix='lezac-waiting-fixture-') as temporary:
            fixture = Path(temporary)
            for path in FIXTURE.iterdir():
                shutil.copyfile(path, fixture / path.name)
            for name in ('manifest.json', 'oracle.bin.gz', 'app.bin'):
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
        with tempfile.TemporaryDirectory(prefix='lezac-waiting-source-') as temporary:
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
        with tempfile.TemporaryDirectory(prefix='lezac-waiting-export-') as temporary:
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
        for path in (FIXTURE / 'manifest.json', FIXTURE / 'oracle.bin.gz', FIXTURE / 'app.bin', ROOT / 'LEZAC.EXE',
                     ROOT / 'CARO.CAR', ROOT / 'BOMOMIMK.SPR', ROOT / 'tools/frame_waiting_oracle.py'):
            before = path.read_bytes(), path.stat().st_mtime_ns
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'preserved'):
                run(path)
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_live_and_dangling_links_preserved(self):
        with tempfile.TemporaryDirectory(prefix='lezac-waiting-link-') as temporary:
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
        with tempfile.TemporaryDirectory(prefix='lezac-waiting-untrusted-') as temporary:
            folder = Path(temporary)
            corpus, output = folder / 'bad.bin', folder / 'output'
            corpus.write_bytes(b'not an original corpus\n')
            with self.assertRaisesRegex(ValueError, 'authenticated original waiting corpus'):
                run_mutations('/not-a-compiler', corpus, output)
            self.assertFalse(output.exists())

    def test_cli_export_twice(self):
        with tempfile.TemporaryDirectory(prefix='lezac-waiting-cli-') as temporary:
            output = Path(temporary) / 'corpus.bin'
            command = [sys.executable, '-S', '-B', str(ROOT / 'tools/check_frame_waiting_fixture.py'), '--out', str(output)]
            for _ in range(2):
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['bytes'], 27514428)
            self.assertEqual(output.read_bytes(), read_fixture())

    def test_actual_app_binding(self):
        if EXE is None:
            self.skipTest('Actual App executable was not supplied')
        environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                           LEZAC_LOAD_ORIGINAL_ASSETS='1', LEZAC_LOAD_JSON_ASSETS='0')
        raw = (FIXTURE / 'app.bin').read_bytes()
        with tempfile.TemporaryDirectory(prefix='lezac-waiting-app-') as temporary:
            path = Path(temporary) / 'app.bin'
            def invoke(data):
                path.write_bytes(data)
                return subprocess.run([str(EXE), '--debug-frame-waiting-original', str(path)], cwd=ROOT,
                    env=environment, capture_output=True, text=True, timeout=60)
            result = invoke(raw)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('frame_waiting_app=ok cases=68 active=40 waiting=28', result.stdout)
            controls = [raw[:-1], raw + b'\0', b'']
            for offset in (0, 8, 12, 14, 15, 17, 21, 25, 29, 45, 75):
                changed = bytearray(raw)
                changed[offset] ^= 1
                controls.append(bytes(changed))
            for index, changed in enumerate(controls):
                result = invoke(changed)
                with self.subTest(control=index):
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn('fixture fingerprint differs', result.stderr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--exe', type=Path)
    arguments, remainder = parser.parse_known_args()
    EXE = arguments.exe.resolve(strict=True) if arguments.exe else None
    unittest.main(argv=[sys.argv[0], *remainder])
