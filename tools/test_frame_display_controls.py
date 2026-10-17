import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import check_frame_display_controls as check


def copy_checker(root):
    script = root / 'tools/check_frame_display_controls.py'
    script.parent.mkdir()
    shutil.copyfile(check.__file__, script)
    shutil.copyfile(Path(check.__file__).parent / 'original_capture_contract.py', script.parent / 'original_capture_contract.py')
    shutil.copytree(Path(check.__file__).parent / 'frame_display_probe', script.parent / 'frame_display_probe')
    shutil.copytree(check.FIXTURE, root / 'tests/fixtures/frame_display_controls')
    return script


class FrameDisplayControlFixtureTest(unittest.TestCase):
    def test_authentic_corpus(self):
        cpu, clock = check.read_fixture()
        self.assertTrue(cpu.startswith(b'LZFDSP01'))
        self.assertTrue(clock.startswith(b'LZPCLK01'))

    def test_each_retained_identity_rejects_changes(self):
        for name in ('manifest.json', 'r1-recipe.json', 'r1.csv.gz', 'r2-recipe.json', 'r2.csv.gz'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='lezac-frame-fixture-') as folder:
                root = Path(folder)
                for source in check.FIXTURE.iterdir():
                    shutil.copyfile(source, root / source.name)
                path = root / name
                raw = bytearray(path.read_bytes())
                raw[len(raw) // 2] ^= 1
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'Frozen display-control'):
                    check.read_fixture(root)

    def test_sample_claim_cannot_change_without_reauthenticating_recipe(self):
        with tempfile.TemporaryDirectory(prefix='lezac-frame-sample-') as folder:
            root = Path(folder)
            for source in check.FIXTURE.iterdir():
                shutil.copyfile(source, root / source.name)
            path = root / 'r1-recipe.json'
            recipe = json.loads(path.read_text())
            recipe['samples'][0]['ram_sha256'] = '0' * 64
            path.write_text(json.dumps(recipe))
            with self.assertRaisesRegex(ValueError, 'Frozen display-control observation'):
                check.read_fixture(root)

    def test_all_capture_and_observer_sources_fail_before_output_publication(self):
        paths = ['original_capture_contract.py'] + ['frame_display_probe/' + name for name in (
            'capture.py', 'input_route.py', 'lezac_work_probe.h', 'dos_time_hook.patch',
            'clock_hook.patch', 'lezac_clock_observation.h')]
        for name in paths:
            for missing in (False, True):
                for existing in (False, True):
                    with self.subTest(name=name, missing=missing, existing=existing), \
                            tempfile.TemporaryDirectory(prefix='lezac-frame-source-') as folder:
                        root = Path(folder)
                        script = copy_checker(root)
                        source = script.parent / name
                        if missing:
                            source.unlink()
                        else:
                            source.write_bytes(source.read_bytes() + b'\nchanged retained source\n')
                        outputs = [root / 'cpu.bin', root / 'clock.bin']
                        if existing:
                            for output in outputs:
                                output.write_bytes(b'preserve projection')
                        result = subprocess.run([sys.executable, '-S', '-B', str(script),
                            '--cpu-projection', str(outputs[0]), '--clock-projection', str(outputs[1])],
                            capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
                        self.assertNotEqual(result.returncode, 0)
                        for output in outputs:
                            if existing:
                                self.assertEqual(output.read_bytes(), b'preserve projection')
                            else:
                                self.assertFalse(output.exists())

    def test_failed_target_cannot_be_promoted(self):
        for field, value in (('status', 'observed'), ('passed', True), ('target_completed', True)):
            with self.subTest(field=field), tempfile.TemporaryDirectory(prefix='lezac-display-target-') as folder:
                root = Path(folder)
                for source in check.FIXTURE.iterdir():
                    shutil.copyfile(source, root / source.name)
                path = root / 'r1-recipe.json'
                recipe = json.loads(path.read_text())
                recipe[field] = value
                path.write_text(json.dumps(recipe))
                with self.assertRaisesRegex(ValueError, 'Frozen display-control observation'):
                    check.read_fixture(root)

    def test_projection_rejects_incomplete_or_discontinuous_windows(self):
        raw = gzip.decompress((check.FIXTURE / 'r1.csv.gz').read_bytes())
        recipe = json.loads((check.FIXTURE / 'r1-recipe.json').read_bytes())
        with self.assertRaises(AssertionError):
            check.projections(raw[:-4], recipe)
        lines = raw.splitlines(keepends=True)
        position = next(index for index, line in enumerate(lines) if line.startswith(b'instruction,') and b',6,1,' in line)
        del lines[position]
        with self.assertRaises(AssertionError):
            check.projections(b''.join(lines), recipe)


if __name__ == '__main__':
    unittest.main()
