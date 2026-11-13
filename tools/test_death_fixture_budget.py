"""Keep replay budgets bounded without accepting timeout or comparison failures."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import check_death_transients_fixture as checker


class BudgetTests(unittest.TestCase):
    def check_mode(self,name,option,timeout):
        error_name='monster-damage' if name=='monster_damage' else 'death-effects'
        case='right_delay3' if name=='monster_damage' else 'ground_even' if name=='corpse_lifecycle' else 'expiry_even' if name=='reward_lifecycle' else 'reward_even'
        responses=[
            subprocess.CompletedProcess([],0,stdout=name+'_original=ok',stderr=''),
            subprocess.CompletedProcess([],0,stdout=name+'_original=ok',stderr=''),
            subprocess.CompletedProcess([],1,stdout='',stderr='missing '+error_name+' completion'),
            subprocess.CompletedProcess([],1,stdout='',stderr='original '+error_name+' mismatch: '+case+' sample=0'),
        ]
        arguments=['checker','--exe',str(Path('unused-replay').resolve())]+([option] if option else [])
        with mock.patch.object(sys,'argv',arguments),redirect_stdout(io.StringIO()),mock.patch.object(
                checker.subprocess,'run',side_effect=responses) as replay:
            checker.main()
        self.assertEqual(replay.call_count,4)
        for call in replay.call_args_list:
            self.assertEqual(call.kwargs['timeout'],timeout)
            self.assertEqual(call.kwargs['env']['SDL_AUDIODRIVER'],'dummy')
            self.assertEqual(call.kwargs['env']['SDL_VIDEODRIVER'],'dummy')
            self.assertTrue(call.kwargs['capture_output'])
            self.assertTrue(call.kwargs['text'])
            self.assertEqual(call.args[0][1],'--debug-'+name.replace('_','-')+'-original')

    def test_corpse_budget(self):
        self.check_mode('corpse_lifecycle','--corpse-lifecycle',120)

    def test_other_budgets_unchanged(self):
        for name,option in (('death_transients',None),('reward_lifecycle','--reward-lifecycle'),
                ('monster_damage','--monster-damage')):
            with self.subTest(mode=name):
                self.check_mode(name,option,30)

    def test_timeout_remains_failure(self):
        arguments=['checker','--exe','unused-replay','--corpse-lifecycle']
        with mock.patch.object(sys,'argv',arguments),mock.patch.object(checker.subprocess,'run',
                side_effect=subprocess.TimeoutExpired(['unused-replay'],120)) as replay:
            with self.assertRaises(subprocess.TimeoutExpired):
                checker.main()
        replay.assert_called_once()
        self.assertEqual(replay.call_args.kwargs['timeout'],120)

    def test_comparison_failure_remains_failure(self):
        arguments=['checker','--exe','unused-replay','--corpse-lifecycle']
        failed=subprocess.CompletedProcess([],1,stdout='',stderr='render mismatch')
        with mock.patch.object(sys,'argv',arguments),mock.patch.object(checker.subprocess,'run',return_value=failed):
            with self.assertRaisesRegex(RuntimeError,'render mismatch'):
                checker.main()


if __name__=='__main__':
    unittest.main()
