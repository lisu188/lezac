"""Frozen ammunition evidence, export preservation and actual-App binding controls."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from check_ammo_hud_fixture import FIXTURE, ROOT, read_fixture, run
from test_ammo_hud_mutations import run as run_mutations

EXE = None


class AmmoHudFixtureTests(unittest.TestCase):
    def test_frozen_corpus(self):
        raw = read_fixture()
        self.assertEqual((raw[:8], len(raw)), (b'LZAMMO02', 93486961))
        self.assertEqual(run()['cases'], 2226)

    def test_manifest_and_stream_mutations(self):
        with tempfile.TemporaryDirectory(prefix='lezac-ammo-fixture-') as temporary:
            fixture = Path(temporary)
            for path in FIXTURE.iterdir():
                shutil.copyfile(path, fixture / path.name)
            for name in ('manifest.json', 'oracle.bin.gz', 'app.bin'):
                target = fixture / name
                raw = target.read_bytes()
                for mutated in (raw[:-1], raw + b'\n', bytes((raw[0] ^ 1,)) + raw[1:]):
                    target.write_bytes(mutated)
                    with self.subTest(file=name, size=len(mutated)), self.assertRaises(ValueError):
                        read_fixture(fixture=fixture)
                target.write_bytes(raw)
                target.unlink()
                with self.subTest(missing=name), self.assertRaises(FileNotFoundError):
                    read_fixture(fixture=fixture)
                target.write_bytes(raw)

    def test_canonical_sources_and_missing_files(self):
        with tempfile.TemporaryDirectory(prefix='lezac-ammo-source-') as temporary:
            root = Path(temporary)
            (root / 'tools').mkdir()
            paths = ['tools/ammo_hud_oracle.py', 'tools/frame_camera_oracle.py', 'LEZAC.EXE', 'CARO.CAR', 'BOMOMIMK.SPR']
            for name in paths:
                shutil.copyfile(ROOT / name, root / name)
            for name in paths:
                path = root / name
                raw = path.read_bytes()
                path.write_bytes(raw + b'\n')
                with self.subTest(source=name), self.assertRaisesRegex(ValueError, 'source differs'):
                    read_fixture(root=root)
                path.unlink()
                with self.subTest(missing=name), self.assertRaises(FileNotFoundError):
                    read_fixture(root=root)
                path.write_bytes(raw)

    def test_repeat_export_and_mismatch_preserved(self):
        with tempfile.TemporaryDirectory(prefix='lezac-ammo-export-') as temporary:
            output = Path(temporary) / 'oracle.bin'
            result = run(output)
            raw, timestamp = output.read_bytes(), output.stat().st_mtime_ns
            self.assertEqual(run(output), result)
            self.assertEqual((output.read_bytes(), output.stat().st_mtime_ns), (raw, timestamp))
            output.write_bytes(b'preserve existing bytes\n')
            before = output.read_bytes(), output.stat().st_mtime_ns
            with self.assertRaisesRegex(ValueError, 'preserved'):
                run(output)
            self.assertEqual((output.read_bytes(), output.stat().st_mtime_ns), before)

    def test_input_aliases_preserved(self):
        for path in (FIXTURE / 'manifest.json', FIXTURE / 'oracle.bin.gz', FIXTURE / 'app.bin',
                     ROOT / 'LEZAC.EXE', ROOT / 'CARO.CAR', ROOT / 'BOMOMIMK.SPR', ROOT / 'tools/ammo_hud_oracle.py'):
            before = path.read_bytes(), path.stat().st_mtime_ns
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'preserved'):
                run(path)
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_links_preserved(self):
        with tempfile.TemporaryDirectory(prefix='lezac-ammo-link-') as temporary:
            folder = Path(temporary)
            target, output = folder / 'target', folder / 'output'
            target.write_bytes(b'preserved\n')
            corpus = folder / 'corpus.bin'
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
                if not dangling:
                    self.assertEqual(target.read_bytes(), b'preserved\n')
                else:
                    self.assertFalse(target.exists())

    def test_mutations_reject_unauthenticated_input(self):
        with tempfile.TemporaryDirectory(prefix='lezac-ammo-mutation-input-') as temporary:
            folder = Path(temporary)
            corpus, output = folder / 'bad.bin', folder / 'output'
            corpus.write_bytes(b'not an original corpus\n')
            with self.assertRaisesRegex(ValueError, 'authenticated original corpus'):
                run_mutations('/not-a-compiler', corpus, output)
            self.assertFalse(output.exists())

    def test_cli_export_twice(self):
        with tempfile.TemporaryDirectory(prefix='lezac-ammo-cli-') as temporary:
            output = Path(temporary) / 'oracle.bin'
            command = [sys.executable, '-S', '-B', str(ROOT / 'tools/check_ammo_hud_fixture.py'), '--out', str(output)]
            for _ in range(2):
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['bytes'], 93486961)
            self.assertEqual(output.read_bytes(), read_fixture())

    def test_actual_app_binding(self):
        if EXE is None:
            self.skipTest('Actual App executable was not supplied')
        environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
                           LEZAC_LOAD_ORIGINAL_ASSETS='1', LEZAC_LOAD_JSON_ASSETS='0')
        raw = (FIXTURE / 'app.bin').read_bytes()
        with tempfile.TemporaryDirectory(prefix='lezac-ammo-app-') as temporary:
            path = Path(temporary) / 'app.bin'
            def invoke(data):
                path.write_bytes(data)
                return subprocess.run([str(EXE), '--debug-ammo-hud-original', str(path)], cwd=ROOT,
                    env=environment, capture_output=True, text=True, timeout=60)
            valid = invoke(raw)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertIn('ammo_hud_app=ok cases=2048 admitted=1536 no_call_controls=512', valid.stdout)
            controls = [raw[:-1], raw + b'\0', b'']
            for offset in (0, 8, 12, 13, 14, 15, 16, 17, 18, 19, 20):
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
    options, remainder = parser.parse_known_args()
    EXE = options.exe.resolve(strict=True) if options.exe else None
    unittest.main(argv=[sys.argv[0], *remainder])
