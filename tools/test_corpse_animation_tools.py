"""Tool contracts only; these mocks do not establish compiled App parity."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import check_corpse_animation_skip_mutant as checker
import make_corpse_animation_skip_mutant as generator


class GeneratorTests(unittest.TestCase):
    def test_only_production_prologue_moves(self):
        source = ('prefix\n    void updateMonsters() {\n' + generator.PROLOGUE +
                  '            if (monster.behavior == 2) continue;\n' + generator.ANCHOR +
                  '    }\n    void other() {}\nsuffix')
        mutated = generator.generate(source)
        self.assertEqual(mutated.replace(generator.PROLOGUE, ''), source.replace(generator.PROLOGUE, ''))
        self.assertGreater(mutated.index(generator.PROLOGUE), mutated.index('continue;'))
        self.assertEqual(mutated.count(generator.PROLOGUE), 1)

    def test_missing_prologue_rejected(self):
        with self.assertRaises(ValueError):
            generator.generate('    void updateMonsters() {}\n    void next() {}')

    def test_already_old_order_rejected(self):
        source = ('    void updateMonsters() {\n            if (monster.behavior == 2) continue;\n' +
                  generator.ANCHOR + generator.PROLOGUE + '    }\n    void next() {}')
        with self.assertRaises(ValueError):
            generator.generate(source)


class CheckerTests(unittest.TestCase):
    def run_checker(self, out, result):
        argv = ['checker', '--exe', str(out / 'mock-not-executed'), '--fixture', str(out / 'fixture'),
                '--out', str(out / 'retained')]
        with patch.object(sys, 'argv', argv), patch.dict(os.environ, SDL_AUDIODRIVER='dummy'), \
             patch.object(checker.subprocess, 'run', side_effect=result if isinstance(result, BaseException) else None,
                          return_value=result):
            checker.main()

    def test_expected_failure_accepted_and_attempts_preserved(self):
        result = subprocess.CompletedProcess([], 1, b'', b'monster animation production boundary not reached\n')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.run_checker(root, result)
            first = (root / 'retained/attempt-001/result.json').read_bytes()
            self.run_checker(root, result)
            self.assertEqual(first, (root / 'retained/attempt-001/result.json').read_bytes())
            self.assertTrue(json.loads((root / 'retained/attempt-002/result.json').read_bytes())['passed'])

    def test_success_exit_rejected(self):
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(RuntimeError):
            self.run_checker(Path(temp), subprocess.CompletedProcess([], 0, b'ok', b''))

    def test_unrelated_failure_rejected_and_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(RuntimeError):
                self.run_checker(root, subprocess.CompletedProcess([], 1, b'', b'SDL load error'))
            self.assertEqual((root / 'retained/attempt-001/stderr.txt').read_bytes(), b'SDL load error')
            self.assertFalse(json.loads((root / 'retained/attempt-001/result.json').read_bytes())['passed'])

    def test_wrong_exit_code_rejected(self):
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(RuntimeError):
            self.run_checker(Path(temp), subprocess.CompletedProcess([], 2, b'',
                b'monster animation production boundary not reached'))

    def test_timeout_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(subprocess.TimeoutExpired):
                self.run_checker(root, subprocess.TimeoutExpired([], 30, output=b'partial', stderr=b'timed out'))
            self.assertEqual((root / 'retained/attempt-001/stdout.txt').read_bytes(), b'partial')
            self.assertIn('TimeoutExpired', json.loads((root / 'retained/attempt-001/result.json').read_bytes())['error'])


if __name__ == '__main__':
    unittest.main()
