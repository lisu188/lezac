"""Waiting-placement provenance and actual-App malformed-input controls."""
import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

from check_waiting_placement_fixture import ROOT, FIXTURE, read_fixture

EXE = None


class WaitingPlacementTests(unittest.TestCase):
    def test_original_corpus(self):
        raw = read_fixture()
        self.assertEqual((raw[:8], struct.unpack_from('<I', raw, 8)[0]), (b'LZWMAP01', 320))
        rows = list(struct.iter_unpack('<18H', raw[12:]))
        self.assertEqual({row[1] for row in rows}, {0, 1, 2, 3})
        self.assertEqual({row[2] for row in rows}, {0, 1, 2, 3})
        self.assertEqual({row[3] for row in rows}, {0, 1})
        self.assertEqual({row[4] for row in rows}, {0, 1})

    def test_manifest_and_endpoint_corruption(self):
        with tempfile.TemporaryDirectory(prefix='lezac-waiting-fixture-') as temporary:
            fixture = Path(temporary)
            for path in FIXTURE.iterdir():
                shutil.copyfile(path, fixture / path.name)
            for name in ('manifest.json', 'oracle.bin'):
                path = fixture / name
                raw = path.read_bytes()
                for changed in (raw[:-1], raw + b'\n', bytes((raw[0] ^ 1,)) + raw[1:]):
                    path.write_bytes(changed)
                    with self.subTest(file=name), self.assertRaises(ValueError):
                        read_fixture(fixture=fixture)
                path.write_bytes(raw)
            (fixture / 'oracle.bin').unlink()
            with self.assertRaises(FileNotFoundError):
                read_fixture(fixture=fixture)

    def test_sources_and_missing_assets(self):
        with tempfile.TemporaryDirectory(prefix='lezac-waiting-sources-') as temporary:
            root = Path(temporary)
            (root / 'tools').mkdir()
            names = ('tools/waiting_placement_oracle.py', 'tools/frame_camera_oracle.py', 'LEZAC.EXE')
            for name in names:
                shutil.copyfile(ROOT / name, root / name)
            for name in names:
                path = root / name
                raw = path.read_bytes()
                path.write_bytes(raw + b'\n')
                with self.subTest(source=name), self.assertRaisesRegex(ValueError, 'source differs'):
                    read_fixture(root=root)
                path.unlink()
                with self.subTest(missing=name), self.assertRaises(FileNotFoundError):
                    read_fixture(root=root)
                path.write_bytes(raw)

    def test_actual_app_and_rejections(self):
        if EXE is None:
            self.skipTest('Actual App executable was not supplied')
        raw = read_fixture()
        environment = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
        with tempfile.TemporaryDirectory(prefix='lezac-waiting-app-') as temporary:
            path = Path(temporary) / 'input.bin'
            def replay(value):
                path.write_bytes(value)
                return subprocess.run([str(EXE), '--debug-waiting-map-original', str(path)],
                    cwd=ROOT, env=environment, capture_output=True, timeout=30)
            control = replay(raw)
            self.assertEqual(control.returncode, 0, control.stderr.decode(errors='replace'))
            self.assertIn(b'waiting_map_original=ok cases=320', control.stdout)
            controls = [raw[:-1], raw + b'\0', b'BADMAGIC' + raw[8:]]
            for offset, value in [(8, 319), (12, 1), (14, 4), (16, 4), (18, 2), (20, 2), (30, 256), (32, 256)]:
                changed = bytearray(raw)
                struct.pack_into('<H', changed, offset, value)
                controls.append(bytes(changed))
            for field in range(11, 18):
                changed = bytearray(raw)
                offset = 12 + field * 2
                value = struct.unpack_from('<H', changed, offset)[0]
                struct.pack_into('<H', changed, offset, value ^ 1)
                controls.append(bytes(changed))
            self.assertEqual(len(controls), 18)
            for index, value in enumerate(controls):
                result = replay(value)
                with self.subTest(control=index):
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(b'fatal:', result.stderr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--exe', type=Path)
    args, remaining = parser.parse_known_args()
    EXE = args.exe.resolve(strict=True) if args.exe else None
    unittest.main(argv=[sys.argv[0], *remaining])
