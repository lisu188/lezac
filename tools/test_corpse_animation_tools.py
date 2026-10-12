"""Tool contracts only; these mocks do not establish compiled App parity."""
import hashlib
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
    def assert_production_corpse_result_scope(self, mutated):
        start = mutated.index('    void updateMonsters(')
        end = mutated.index('\n    void ', start + 1)
        body = mutated[start:end]
        self.assertEqual(body.count(generator.DECLARATION), 1)
        self.assertLess(body.index(generator.DECLARATION), body.index('actorSlots_.writeCorpse('))
        self.assertLess(body.index('actorSlots_.writeCorpse('), body.index(generator.DEFERRED_PROLOGUE))
        self.assertNotIn('const bool animationAdvanced =', body)

    def test_only_production_prologue_moves(self):
        source = ('prefix\n    void updateMonsters() {\n' + generator.PROLOGUE +
                  '            if (monster.behavior == 2) continue;\n' + generator.ANCHOR +
                  '    }\n    void other() {}\nsuffix')
        mutated = generator.generate(source)
        self.assertEqual(mutated.replace(generator.DEFERRED_PROLOGUE, '').replace(generator.DECLARATION, ''),
                         source.replace(generator.PROLOGUE, ''))
        self.assertGreater(mutated.index(generator.DEFERRED_PROLOGUE), mutated.index('continue;'))
        self.assertLess(mutated.index(generator.DECLARATION), mutated.index('if (monster.behavior == 2)'))
        self.assertEqual(mutated.count(generator.DECLARATION), 1)
        self.assertEqual(mutated.count(generator.DEFERRED_PROLOGUE), 1)

    def test_current_production_source_retains_corpse_result_scope(self):
        source = Path(__file__).resolve().parents[1] / 'src/app/app.cpp'
        original = source.read_bytes()
        normalized = original.decode('utf-8').replace('\r\n', '\n')
        mutated = generator.generate(normalized)
        expected = normalized.replace(generator.PROLOGUE, generator.DECLARATION, 1).replace(
            generator.ANCHOR, generator.ANCHOR + generator.DEFERRED_PROLOGUE, 1)
        self.assertEqual(mutated, expected)
        self.assertEqual(generator.DECLARATION, '            bool animationAdvanced = false;\n')
        self.assert_production_corpse_result_scope(mutated)
        self.assertEqual(source.read_bytes(), original)

    def test_unrelated_corpse_writes_do_not_affect_production_scope(self):
        prefix = '    void debugFixture() { actorSlots_.writeCorpse(1); }\n'
        suffix = '\n    void other() { actorSlots_.writeCorpse(2); }\n'
        body = ('    void updateMonsters() {\n' + generator.PROLOGUE +
                '            if (monster.behavior == 2) {\n' +
                '                actorSlots_.writeCorpse(3);\n            }\n' + generator.ANCHOR + '    }')
        mutated = generator.generate(prefix + body + suffix)
        self.assertTrue(mutated.startswith(prefix) and mutated.endswith(suffix))
        self.assert_production_corpse_result_scope(mutated)

    def test_production_scope_rejects_wrong_order_and_missing_writeback(self):
        write = '            actorSlots_.writeCorpse(3);\n'
        for body in (write + generator.DECLARATION + generator.DEFERRED_PROLOGUE,
                     generator.DECLARATION + generator.DEFERRED_PROLOGUE + write,
                     generator.DECLARATION + generator.DEFERRED_PROLOGUE):
            with self.subTest(body=body), self.assertRaises((AssertionError, ValueError)):
                self.assert_production_corpse_result_scope(
                    '    void debugFixture() { actorSlots_.writeCorpse(1); }\n' +
                    '    void updateMonsters() {\n' + body + '    }\n    void other() {}\n')

    def test_cli_preserves_crlf_source_and_records_hashes(self):
        text = ('prefix\n    void updateMonsters() {\n' + generator.PROLOGUE +
                '            if (monster.behavior == 2) continue;\n' + generator.ANCHOR +
                '    }\n    void other() {}\nsuffix')
        original = text.replace('\n', '\r\n').encode('utf-8')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source.cpp'
            output = root / 'generated/app.cpp'
            source.write_bytes(original)
            with patch.object(sys, 'argv', ['generator', '--source', str(source), '--out', str(output)]):
                generator.main()
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(output.read_bytes(), generator.generate(text).encode('utf-8'))
            manifest = json.loads(output.with_suffix('.json').read_bytes())
            self.assertEqual(manifest['source_sha256'], hashlib.sha256(original).hexdigest())
            self.assertEqual(manifest['mutant_sha256'], hashlib.sha256(output.read_bytes()).hexdigest())

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
