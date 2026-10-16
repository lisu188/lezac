import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import check_pic_work_clock_fixture as check


def copy_checker(root):
    script = root / 'tools/check_pic_work_clock_fixture.py'
    script.parent.mkdir()
    for name in ('check_pic_work_clock_fixture.py', 'check_interruptible_dos_time_fixture.py',
                 'check_dos_time_fixture.py', 'original_capture_contract.py'):
        shutil.copyfile(Path(check.__file__).parent / name, script.parent / name)
    shutil.copytree(Path(check.__file__).parent / 'pic_clock_probe', script.parent / 'pic_clock_probe')
    shutil.copytree(check.FIXTURE, root / 'tests/fixtures/pic_work_clock')
    return script


class FrozenPicFixtureTest(unittest.TestCase):
    def test_authentic_corpus(self):
        cpu, clock = check.read_fixture()
        self.assertTrue(cpu.startswith(b'LZDTIR01'))
        self.assertTrue(clock.startswith(b'LZPCLK01'))

    def test_retained_identities_reject_changes(self):
        for name in ('manifest.json', 'r2-recipe.json', 'r2.csv.gz'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='lezac-pic-fixture-') as folder:
                root = Path(folder)
                for source in check.FIXTURE.iterdir():
                    shutil.copyfile(source, root / source.name)
                path = root / name
                raw = bytearray(path.read_bytes())
                raw[len(raw) // 2] ^= 1
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'Frozen PIC'):
                    check.read_fixture(root)

    def test_sample_claim_cannot_change_with_trace_unchanged(self):
        with tempfile.TemporaryDirectory(prefix='lezac-pic-sample-') as folder:
            root = Path(folder)
            for source in check.FIXTURE.iterdir():
                shutil.copyfile(source, root / source.name)
            path = root / 'r2-recipe.json'
            recipe = json.loads(path.read_text())
            recipe['samples'][0]['ram_sha256'] = '0' * 64
            path.write_text(json.dumps(recipe))
            with self.assertRaisesRegex(ValueError, 'Frozen PIC observation'):
                check.read_fixture(root)

    def test_cli_does_not_replace_projection_on_source_rejection(self):
        with tempfile.TemporaryDirectory(prefix='lezac-pic-cli-') as folder:
            root = Path(folder)
            script = copy_checker(root)
            (script.parent / 'pic_clock_probe/capture.py').write_bytes(b'changed producer')
            output = root / 'cpu.bin'
            output.write_bytes(b'preserve this projection')
            result = subprocess.run([sys.executable, '-S', '-B', str(script), '--cpu-projection', str(output)],
                capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Retained capture source differs', result.stderr)
            self.assertEqual(output.read_bytes(), b'preserve this projection')

    def test_all_observer_sources_reject_changed_or_missing_files(self):
        for name in ('lezac_work_probe.h', 'dos_time_hook.patch', 'clock_hook.patch', 'lezac_clock_observation.h'):
            for missing in (False, True):
                for existing in (False, True):
                    with self.subTest(name=name, missing=missing, existing=existing), \
                            tempfile.TemporaryDirectory(prefix='lezac-pic-observer-') as folder:
                        root = Path(folder)
                        script = copy_checker(root)
                        source = script.parent / 'pic_clock_probe' / name
                        if missing:
                            source.unlink()
                        else:
                            source.write_bytes(source.read_bytes() + b'\nchanged observer source\n')
                        outputs = [root / 'cpu.bin', root / 'clock.bin']
                        if existing:
                            for output in outputs:
                                output.write_bytes(b'preserve projection')
                        result = subprocess.run([sys.executable, '-S', '-B', str(script),
                            '--cpu-projection', str(outputs[0]), '--clock-projection', str(outputs[1])],
                            capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
                        self.assertNotEqual(result.returncode, 0)
                        if not missing:
                            self.assertIn('Retained observer source differs', result.stderr)
                        for output in outputs:
                            if existing:
                                self.assertEqual(output.read_bytes(), b'preserve projection')
                            else:
                                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
