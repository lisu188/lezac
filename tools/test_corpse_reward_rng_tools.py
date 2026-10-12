"""Generator/checker contracts; hosted tests separately execute the compiled App."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_corpse_reward_rng_mutant as checker
import make_corpse_reward_rng_mutant as generator


class RewardRngToolsTest(unittest.TestCase):
    def test_mutations_preserve_diagnostic_and_draw_count(self):
        source = (Path(__file__).resolve().parents[1] / 'src/app/app.cpp').read_text(encoding='utf-8')
        mutant = generator.generate(source)
        for text in (source, mutant):
            self.assertEqual(generator.function(text, 'spawnExpiryParticles')[2].count('randomRangeValue(0, 600)'), 2)
        self.assertEqual(generator.function(source, 'debugCorpseRewardAnimationMode')[2],
                         generator.function(mutant, 'debugCorpseRewardAnimationMode')[2])
        for mode in checker.CONTROLS:
            self.assertIn('rewardRngMutation("' + mode + '")', mutant)
        with self.assertRaises(ValueError):
            generator.generate(mutant)
        with self.assertRaises(ValueError):
            generator.generate(source.replace(generator.SOUND, '', 1))

    def invoke(self, root, result):
        with patch.object(checker.subprocess, 'run', side_effect=result if isinstance(result, BaseException) else None,
                          return_value=result) as run:
            value = checker.check(Path('not-executed'), root)
            for call in run.call_args_list:
                self.assertEqual(call.kwargs['env']['SDL_AUDIODRIVER'], 'dummy')
            return value

    def test_expected_failures_and_repeated_attempts(self):
        failures = [subprocess.CompletedProcess([], 1, b'', text.encode()) for text in checker.CONTROLS.values()]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(checker.subprocess, 'run', side_effect=failures):
                first = checker.check(Path('not-executed'), root)
            retained = (first / 'result.json').read_bytes()
            with patch.object(checker.subprocess, 'run', side_effect=failures):
                second = checker.check(Path('not-executed'), root)
            self.assertNotEqual(first, second)
            self.assertEqual(retained, (first / 'result.json').read_bytes())
            self.assertTrue(json.loads((second / 'result.json').read_text())['passed'])

    def test_success_wrong_exit_and_unrelated_failures_rejected(self):
        for code, error in ((0, next(iter(checker.CONTROLS.values()))), (2, next(iter(checker.CONTROLS.values()))),
                            (1, 'SDL loading failure')):
            with tempfile.TemporaryDirectory() as temp, self.assertRaises(RuntimeError):
                self.invoke(Path(temp), subprocess.CompletedProcess([], code, b'partial', error.encode()))

    def test_timeout_logs_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(subprocess.TimeoutExpired):
                self.invoke(root, subprocess.TimeoutExpired([], 30, output=b'partial output', stderr=b'partial error'))
            attempt = next(root.iterdir())
            self.assertEqual((attempt / 'sound_after_particles.stdout').read_bytes(), b'partial output')
            self.assertEqual((attempt / 'sound_after_particles.stderr').read_bytes(), b'partial error')
            self.assertFalse(json.loads((attempt / 'result.json').read_text())['passed'])


if __name__ == '__main__':
    unittest.main()
