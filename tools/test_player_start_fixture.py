"""Reject altered provenance, projections, exports and native App inputs."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import check_player_start_fixture as check

EXE = None
BOUND = ('LEZAC.EXE', 'tools/player_start_oracle.py', 'tools/frame_camera_oracle.py')
FROZEN = ('manifest.json', 'oracle.bin.gz', 'app.bin')


class Contract(unittest.TestCase):
    def clone(self, root):
        for relative in BOUND:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(check.ROOT / relative, target)
        fixture = root / 'tests/fixtures/player_start'
        shutil.copytree(check.FIXTURE, fixture)
        return fixture

    def test_authentic(self):
        decoded, app = check.read_fixture()
        self.assertEqual(len(decoded), 1985162)
        self.assertEqual(len(app), 17720)

    def test_frozen_files(self):
        for name in FROZEN:
            for mutation in ('missing', 'changed'):
                with self.subTest(name=name, mutation=mutation), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    fixture = self.clone(root)
                    target = fixture / name
                    if mutation == 'missing':
                        target.unlink()
                    else:
                        raw = bytearray(target.read_bytes())
                        raw[-1] ^= 1
                        target.write_bytes(raw)
                    with self.assertRaises((ValueError, OSError)):
                        check.read_fixture(root, fixture)

    def test_sources(self):
        for relative in BOUND:
            for mutation in ('missing', 'changed'):
                with self.subTest(relative=relative, mutation=mutation), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    fixture = self.clone(root)
                    target = root / relative
                    if mutation == 'missing':
                        target.unlink()
                    else:
                        target.write_bytes(target.read_bytes() + b'changed')
                    with self.assertRaises((ValueError, OSError)):
                        check.read_fixture(root, fixture)

    def test_export_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.clone(root)
            for target in [*(root / name for name in BOUND), *(fixture / name for name in FROZEN)]:
                before = target.read_bytes()
                with self.assertRaises(ValueError):
                    check.run(root, fixture, target)
                self.assertEqual(target.read_bytes(), before)
            out = root / 'decoded.bin'
            check.run(root, fixture, out)
            check.run(root, fixture, out)
            self.assertEqual(out.read_bytes(), check.read_fixture(root, fixture)[0])
            out.write_bytes(b'retain this evidence')
            with self.assertRaises(ValueError):
                check.run(root, fixture, out)
            self.assertEqual(out.read_bytes(), b'retain this evidence')

    def test_app_rejections(self):
        if EXE is None:
            self.skipTest('Native actual-App executable not supplied')
        raw = (check.FIXTURE / 'app.bin').read_bytes()
        import os
        environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
        positive = subprocess.run([str(EXE), '--debug-player-start-original', str(check.FIXTURE / 'app.bin')],
            cwd=check.ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        self.assertEqual(positive.returncode, 0, positive.stdout.decode())
        self.assertIn(b'cases=1040 startup_placement=1040 reentry=1040', positive.stdout)
        controls = [raw[:-1], raw + b'extra']
        for offset in (0, 8, 12, 14, 16, 18, 20, 22, len(raw)-1):
            altered = bytearray(raw)
            altered[offset] ^= 1
            controls.append(bytes(altered))
        with tempfile.TemporaryDirectory() as directory:
            for index, altered in enumerate(controls):
                target = Path(directory) / f'altered-{index}.bin'
                target.write_bytes(altered)
                result = subprocess.run([str(EXE), '--debug-player-start-original', str(target)], cwd=check.ROOT,
                    env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
                self.assertEqual(result.returncode, 1, result.stdout.decode())
                self.assertIn(b'player start fixture fingerprint differs', result.stdout)
        print('player_start_app_controls=ok rejected=11 immutable_fixture=1')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    args, extra = parser.parse_known_args()
    EXE = args.exe.resolve(strict=True) if args.exe else None
    unittest.main(argv=[__file__, *extra])
