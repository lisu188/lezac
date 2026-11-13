import copy
import gzip
import json
import unittest

from check_dos_time_fixture import FIXTURE, check_fixture, parse_trace, projection


class DosTimeFixtureTests(unittest.TestCase):
    def setUp(self):
        self.raw = gzip.decompress((FIXTURE / 'r3-trace.csv.gz').read_bytes())
        self.recipe = json.loads((FIXTURE / 'r3-recipe.json').read_text())

    def test_corpus(self):
        corpora = check_fixture()
        self.assertEqual(projection(corpora)[:12], b'LZDOST01\x14\x00\x00\x00')

    def mutate(self, field, value, kind):
        lines = self.raw.decode().splitlines()
        header = lines[0].split(',')
        for index, line in enumerate(lines[1:-1], 1):
            row = line.split(',')
            if row[0] == kind:
                row[header.index(field)] = value
                lines[index] = ','.join(row)
                return ('\n'.join(lines) + '\n').encode()
        self.fail('Mutation boundary missing')

    def test_cpu_memory_work_mutations(self):
        controls = [('ip', '30594', 'identified'), ('ax', '0', 'callback_enter'),
                    ('psp_stack', '0', 'service_after'), ('cx', '0', 'service_after'),
                    ('dx', '0', 'service_after'), ('sp', '0', 'returned'),
                    ('defined_flags', '4294967295', 'instruction'),
                    ('vector_stub', '00' * 15, 'callback_enter'),
                    ('dispatch', '0', 'returned'), ('windowed', '0', 'callback_enter'),
                    ('stack', '00', 'instruction'), ('kind', 'window_exhausted', 'instruction')]
        for field, value, kind in controls:
            with self.subTest(field=field, kind=kind), self.assertRaises(ValueError):
                parse_trace(self.mutate(field, value, kind), self.recipe)

    def test_terminal_and_column_controls(self):
        for raw in (self.raw[:-4], self.raw.replace(b'kind,dispatch', b'kind,other', 1),
                    self.raw.replace(b',6000,', b',06000,', 1)):
            with self.assertRaises(ValueError):
                parse_trace(raw, self.recipe)

    def test_startup_scope_cannot_use_late_identity(self):
        recipe = copy.deepcopy(self.recipe)
        recipe['run'] = 'r2'
        with self.assertRaises(ValueError):
            parse_trace(self.raw, recipe)


if __name__ == '__main__':
    unittest.main()
