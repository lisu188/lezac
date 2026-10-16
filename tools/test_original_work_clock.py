#!/usr/bin/env python3
"""Original-backed trace replay and adversarial timing-checker regressions."""
import copy
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from analyze_original_work_clock import analyze, COLUMNS, read_rows

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/original_work_clock'
MANIFEST_SHA = '729d360941ba14c2d3bed3ae2b5c0b124dfbfa598967fbd0c79a1858292000b0'
sha = lambda raw: hashlib.sha256(raw).hexdigest()

class WorkClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (FIXTURES / 'manifest.json').read_bytes()
        if sha(raw) != MANIFEST_SHA:
            raise ValueError('Original timing manifest changed')
        cls.manifest = json.loads(raw)
        cls.rows, cls.raw = read_rows(FIXTURES / 'r1.csv.gz')

    def test_original_runs(self):
        manifest = self.manifest
        self.assertTrue(manifest['host_instrumented'])
        self.assertFalse(manifest['natural_wall_clock_fidelity_claim'])
        self.assertFalse(manifest['full_ram_or_images_published'])
        self.assertEqual(sha((ROOT / 'LEZAC.EXE').read_bytes()), manifest['original_executable_sha256'])
        self.assertEqual(sha((ROOT / 'tools/original_work_probe/lezac_work_probe.h').read_bytes()), manifest['probe_sha256'])
        profiles = []
        for run in manifest['runs']:
            with self.subTest(run=run['name']):
                source = FIXTURES / run['trace']
                packed = source.read_bytes()
                self.assertEqual(len(packed), run['compressed_bytes'])
                self.assertEqual(sha(packed), run['compressed_sha256'])
                raw = gzip.decompress(packed)
                self.assertEqual(len(raw), run['trace_bytes'])
                self.assertEqual(sha(raw), run['trace_sha256'])
                result = analyze(source)
                self.assertEqual(result, run['profile'])
                self.assertEqual(len(result['pages']), 4)
                self.assertEqual(len(result['row_work_dispatches_without_vertical_carry']), 200)
                self.assertFalse(result['dispatches_are_cycle_clock'])
                self.assertFalse(result['natural_wall_clock_fidelity_claim'])
                self.assertEqual(result['unfinished_delays_at_host_exit'], 1)
                self.assertTrue(all(item['code_bytes_verified'] == 43552 and item['code_differences'] == 0
                                    for item in run['observations']))
                profiles.append(result)
        self.assertEqual(profiles[0]['row_work_dispatches_without_vertical_carry'],
                         profiles[1]['row_work_dispatches_without_vertical_carry'])
        self.assertNotEqual([(page['horizontal'], page['vertical']) for page in profiles[0]['pages']],
                            [(page['horizontal'], page['vertical']) for page in profiles[1]['pages']])
        self.assertEqual({item['calibrated_delay_word'] for item in manifest['runs'][0]['observations']}, {81})
        self.assertEqual({item['calibrated_delay_word'] for item in manifest['runs'][1]['observations']}, {82})

    def test_raw_and_compressed_profiles_match(self):
        with tempfile.TemporaryDirectory(prefix='lezac-work-clock-') as directory:
            path = Path(directory) / 'trace.csv'
            path.write_bytes(self.raw)
            self.assertEqual(analyze(path), self.manifest['runs'][0]['profile'])

    def test_trace_rejection_controls(self):
        cases = []

        def alter(label, kind, field, value):
            rows = copy.deepcopy(self.rows)
            row = next(item for item in rows if item['kind'] == kind)
            row[field] = value(row[field]) if callable(value) else value
            cases.append((label, rows))

        alter('unknown marker', 'horizontal', 'kind', 'cap')
        alter('wrong budget', 'horizontal', 'cycle_max', 5999)
        alter('negative dispatch', 'identified', 'dispatch', -1)
        alter('bad DAC', 'identified', 'dac', 'x' * 42)
        alter('word overflow', 'horizontal', 'phase', 65536)
        alter('fraction overflow', 'horizontal', 'fraction', 32768)
        alter('missing frame', 'horizontal', 'frame_valid', 0)
        alter('wrong pixel instruction', 'horizontal', 'ip', 0x252)
        alter('post-color cursor', 'write', 'phase', lambda value: value + 1)
        alter('horizontal cost', 'row_check', 'exclusive_dispatch', lambda value: value + 1)
        alter('horizontal cursor', 'row_check', 'fraction', lambda value: value + 1)
        alter('color cost', 'write', 'exclusive_dispatch', lambda value: value + 1)
        alter('write cost', 'after_write', 'exclusive_dispatch', lambda value: value + 1)
        alter('tail cost', 'tail', 'exclusive_dispatch', lambda value: value + 1)
        alter('row software work', 'row_work', 'exclusive_dispatch', lambda value: value + 1)
        alter('wrong finish instruction', 'finish', 'ip', 0x30a)
        alter('unfinished destination', 'finish', 'destination', 63999)
        alter('bad parameters', 'finish', 'h', 81)
        alter('IRQ leak', 'irq8_return', 'exclusive_dispatch', lambda value: value + 1)
        alter('IRQ mismatch', 'irq8_return', 'kind', 'irq9_return')
        alter('IRQ depth', 'irq8_enter', 'irq_depth', 2)
        alter('delay input', 'delay_end', 'delay_argument', lambda value: value + 1)
        alter('delay dispatch', 'delay_end', 'exclusive_dispatch', lambda value: value + 1)
        cases.append(('missing clean exit', copy.deepcopy(self.rows[:-1])))
        cases.append(('missing identification', copy.deepcopy(self.rows[1:])))
        cases.append(('duplicate exit', copy.deepcopy(self.rows + [self.rows[-1]])))
        rows = copy.deepcopy(self.rows)
        row = next(item for item in rows if item['kind'] == 'horizontal')
        rows.insert(rows.index(row), copy.deepcopy(row))
        cases.append(('duplicate pixel', rows))
        rows = copy.deepcopy(self.rows)
        rows.remove(next(item for item in rows if item['kind'] == 'horizontal'))
        cases.append(('missing pixel', rows))
        cases.append(('cycles used as dispatches', [dict(row, exclusive_dispatch=row['exclusive_clock']) for row in self.rows]))
        with tempfile.TemporaryDirectory(prefix='lezac-work-mutants-') as directory:
            for index, (label, rows) in enumerate(cases):
                with self.subTest(label=label):
                    path = Path(directory) / f'{index}.csv'
                    with path.open('w', newline='') as stream:
                        writer = csv.DictWriter(stream, COLUMNS, lineterminator='\n')
                        writer.writeheader()
                        writer.writerows(rows)
                    with self.assertRaises(ValueError):
                        analyze(path)
        self.assertEqual(len(cases), 29)

    def test_malformed_streams(self):
        cases = [self.raw.replace(b'kind,page,', b'kind,pages,', 1),
                 self.raw + b'cap\n', self.raw[:-30], b'\xff' + self.raw,
                 self.raw.replace(b'identified,0,', b'identified,no,', 1)]
        with tempfile.TemporaryDirectory(prefix='lezac-work-malformed-') as directory:
            for index, raw in enumerate(cases):
                path = Path(directory) / f'{index}.csv'
                path.write_bytes(raw)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    analyze(path)

    def test_decompression_reserve(self):
        with tempfile.TemporaryDirectory(prefix='lezac-work-reserve-') as directory:
            path = Path(directory) / 'oversized.csv.gz'
            path.write_bytes(gzip.compress(b'x' * (6 * 1024 * 1024 + 1), mtime=0))
            with self.assertRaisesRegex(ValueError, 'Expanded trace exceeds size limit'):
                analyze(path)

if __name__ == '__main__':
    unittest.main()
