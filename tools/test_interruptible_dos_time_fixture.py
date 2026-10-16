import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import check_interruptible_dos_time_fixture as check


class InterruptibleDosTimeFixtureTests(unittest.TestCase):
    def test_frozen_corpus_and_scope(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cases = check.read_fixture()
        self.assertEqual(len(cases), 21)
        self.assertEqual(sum(len(case['states']) for case in cases), 6882)
        self.assertEqual(sum(len(case['deliveries']) for case in cases), 1)
        self.assertTrue(cases[0]['legacy'])
        self.assertEqual(cases[0]['deliveries'], [118])
        self.assertTrue(all(not case['legacy'] and len(case['states'][0]['stack']) == 128 for case in cases[1:]))
        self.assertTrue(check.projection(cases).startswith(b'LZDTIR01'))

    def test_all_frozen_file_mutations_rejected(self):
        for original in check.FIXTURE.iterdir():
            with self.subTest(file=original.name), tempfile.TemporaryDirectory(prefix='lezac-dos-timer-fixture-') as temporary:
                folder = Path(temporary)
                for path in check.FIXTURE.iterdir():
                    (folder / path.name).write_bytes(path.read_bytes())
                (folder / original.name).write_bytes(original.read_bytes() + b'changed')
                with mock.patch.object(check, 'FIXTURE', folder), self.assertRaisesRegex(ValueError, 'Frozen'):
                    check.read_fixture()

    def test_published_producer_binding(self):
        original_read = Path.read_bytes
        for path in ('tools/dos_timer_probe/capture.py', 'tools/dos_timer_probe/lezac_work_probe.h',
                     'tools/dos_timer_probe/dos_time_hook.patch'):
            target = check.ROOT / path

            def changed_read(item):
                raw = original_read(item)
                return raw + b'changed' if item == target else raw

            with self.subTest(file=path), mock.patch.object(Path, 'read_bytes', changed_read), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'producer or observer'):
                check.read_fixture()

    def test_terminal_and_instruction_window_rejections(self):
        import gzip
        import json
        raw = gzip.decompress((check.FIXTURE / 'r1-trace.csv.gz').read_bytes())
        recipe = json.loads((check.FIXTURE / 'r1-recipe.json').read_text())
        for value in (raw[:-4], raw.replace(b'instruction,', b'unknown,', 1), raw[:100]):
            with self.subTest(bytes=len(value)), self.assertRaises((ValueError, IndexError)):
                check.parse(value, recipe)
        rows = raw.splitlines()
        index = next(i for i, row in enumerate(rows) if row.startswith(b'instruction,'))
        del rows[index]
        with self.assertRaisesRegex(ValueError, 'Dispatch gap'):
            check.parse(b'\n'.join(rows) + b'\n', recipe)


if __name__ == '__main__':
    unittest.main()
