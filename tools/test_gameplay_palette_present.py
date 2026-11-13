import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_gameplay_palette_present as subject


class FailedReportTests(unittest.TestCase):
    def run_failure(self, canonical, missing):
        with tempfile.TemporaryDirectory(prefix='lezac-palette-failure-') as temporary:
            out = Path(temporary)
            exe, observer = out / 'exe', out / 'observer.so'
            if missing != 'exe':
                exe.write_bytes(b'not executed')
            if missing != 'observer':
                observer.write_bytes(b'not loaded')
            with patch.object(subject, 'read_canonical_assets', **canonical):
                with self.assertRaises(FileNotFoundError):
                    subject.check(exe, observer, out)
            report = json.loads((out / 'report.json').read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertIn('FileNotFoundError', report['error'])
            self.assertFalse(report['natural_route'])
            self.assertFalse(report['whole_game_parity'])

    def test_missing_canonical_asset_preserves_failure(self):
        self.run_failure(dict(side_effect=FileNotFoundError('canonical asset unavailable')), None)

    def test_missing_binary_preserves_failure(self):
        self.run_failure(dict(return_value={}), 'exe')

    def test_missing_observer_preserves_failure(self):
        self.run_failure(dict(return_value={}), 'observer')


if __name__ == '__main__':
    unittest.main()
