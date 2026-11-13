"""Keep generated loader data exact across LF and CRLF checkouts."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import generate_initial_damage_data as generator

ROOT = Path(__file__).resolve().parents[1]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')


class InitialDamageDataTests(unittest.TestCase):
    def test_lf_and_crlf_preserve_every_non_newline_byte(self):
        expected = generator.render(ROOT)
        for actual in (expected, expected.replace(b'\n', b'\r\n')):
            with self.subTest(crlf=b'\r\n' in actual):
                generator.verify_generated(actual, expected)

    def test_payload_corruption_is_rejected_with_either_newline_style(self):
        expected = generator.render(ROOT)
        changed = expected.replace(b'0x00', b'0x01', 1)
        self.assertNotEqual(changed, expected)
        for actual in (changed, changed.replace(b'\n', b'\r\n')):
            with self.subTest(crlf=b'\r\n' in actual):
                with self.assertRaisesRegex(ValueError, 'differs from original loader'):
                    generator.verify_generated(actual, expected)

    def test_no_other_text_normalization_is_allowed(self):
        expected = generator.render(ROOT)
        mutants = (expected[:-1], expected + b'\n', b'\xef\xbb\xbf' + expected,
            expected.replace(b'\n', b'\r', 1), expected.replace(b'    ', b'\t', 1))
        for actual in mutants:
            with self.subTest(prefix=actual[:24]):
                with self.assertRaises(ValueError):
                    generator.verify_generated(actual, expected)

    def test_original_executable_pin_is_still_required(self):
        with tempfile.TemporaryDirectory(prefix='lezac-data-pin-') as directory:
            root = Path(directory)
            (root / 'LEZAC.EXE').write_bytes(b'MZ altered executable')
            with self.assertRaisesRegex(ValueError, 'original executable pin mismatch'):
                generator.render(root)

    def test_cli_accepts_crlf_header_and_rejects_changed_payload(self):
        with tempfile.TemporaryDirectory(prefix='lezac-data-cli-') as directory:
            root = Path(directory)
            shutil.copyfile(ROOT / 'LEZAC.EXE', root / 'LEZAC.EXE')
            header = root / 'src/gameplay/initial_damage_data.hpp'
            header.parent.mkdir(parents=True)
            expected = generator.render(ROOT)
            command = [sys.executable, '-S', '-B', str(Path(generator.__file__)), '--root', str(root)]
            for altered in (False, True):
                with self.subTest(altered=altered):
                    payload = expected.replace(b'0x00', b'0x01', 1) if altered else expected
                    header.write_bytes(payload.replace(b'\n', b'\r\n'))
                    result = subprocess.run(command, env=ENV, capture_output=True, timeout=20)
                    self.assertEqual(result.returncode == 0, not altered)
                    if not altered:
                        self.assertIn(b'damage_lane_initial_data=ok', result.stdout)
                        self.assertFalse(result.stderr)

    def test_cli_generation_remains_lf_only_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='lezac-data-output-') as directory:
            target = Path(directory) / 'initial.hpp'
            command = [sys.executable, '-S', '-B', str(Path(generator.__file__)),
                '--root', str(ROOT), '--output', str(target)]
            result = subprocess.run(command, env=ENV, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), generator.render(ROOT))
            before = target.read_bytes()
            result = subprocess.run(command, env=ENV, capture_output=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
