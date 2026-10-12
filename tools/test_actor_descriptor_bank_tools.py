"""Tool contracts; hosted CI separately executes the compiled production App."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_actor_descriptor_bank_mutant as checker
import make_actor_descriptor_bank_mutant as generator


class DescriptorBankToolsTest(unittest.TestCase):
    def test_generator_changes_only_production_bank_selection(self):
        source = (Path(__file__).resolve().parents[1] / 'src/app/app.cpp').read_text(encoding='utf-8')
        mutant = generator.generate(source)
        old_start, old_end, body = generator.function(source)
        new_start, new_end, changed = generator.function(mutant)
        self.assertEqual(source[:old_start], mutant[:new_start])
        self.assertEqual(source[old_end:], mutant[new_end:])
        self.assertEqual(changed, body.replace(generator.SELECTION, '        const auto& bank = sprites_;\n'))
        with self.assertRaises(ValueError):
            generator.generate(mutant)
        with self.assertRaises(ValueError):
            generator.generate(source.replace(generator.SELECTION, '', 1))

    def test_expected_failure_and_attempt_retention(self):
        result = subprocess.CompletedProcess([], 1, b'', checker.FAILURE)
        with tempfile.TemporaryDirectory() as temp, patch.object(checker.subprocess, 'run', return_value=result) as run:
            root = Path(temp)
            first = checker.check(Path('not-executed'), root)
            retained = (first / 'result.json').read_bytes()
            second = checker.check(Path('not-executed'), root)
            self.assertNotEqual(first, second)
            self.assertEqual(retained, (first / 'result.json').read_bytes())
            self.assertTrue(json.loads((second / 'result.json').read_text())['passed'])
            for call in run.call_args_list:
                self.assertEqual(call.kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
                self.assertEqual(call.kwargs['env']['SDL_VIDEODRIVER'], 'dummy')

    def test_success_wrong_exit_and_unrelated_error_rejected(self):
        for code, error in ((0, checker.FAILURE), (2, checker.FAILURE), (1, b'cannot load assets')):
            with tempfile.TemporaryDirectory() as temp, patch.object(checker.subprocess, 'run',
                    return_value=subprocess.CompletedProcess([], code, b'partial', error)), self.assertRaises(RuntimeError):
                checker.check(Path('not-executed'), Path(temp))

    def test_timeout_preserves_partial_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(checker.subprocess, 'run', side_effect=subprocess.TimeoutExpired([], 30,
                    output=b'partial output', stderr=b'partial error')), self.assertRaises(subprocess.TimeoutExpired):
                checker.check(Path('not-executed'), root)
            attempt = next(root.iterdir())
            self.assertEqual((attempt / 'app.stdout').read_bytes(), b'partial output')
            self.assertEqual((attempt / 'app.stderr').read_bytes(), b'partial error')
            self.assertFalse(json.loads((attempt / 'result.json').read_text())['passed'])


if __name__ == '__main__':
    unittest.main()
