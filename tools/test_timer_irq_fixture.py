import copy
import gzip
import json
import unittest

from check_timer_irq_fixture import FIXTURE, read_fixture, validate
from check_timer_irq_natural_fixture import read_fixture as read_natural


class TimerIrqFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=json.loads(gzip.decompress((FIXTURE/'original.json.gz').read_bytes()))

    def test_frozen_controlled_pair(self):
        read_fixture()

    def test_frozen_natural_pair(self):
        read_natural()

    def test_scope_rejections(self):
        fields=dict(original_calls_stubbed=False,original_instruction_patches=0,inputs_seeded=True,
                    io_ports_scripted=True,bios_wrapper_executed=False,natural_timing=False,
                    whole_game_parity=False,stack_reads_hooked=False)
        for key,expected in fields.items():
            for value in (None,str(expected),not expected):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    validate(dict(self.original,**{key:value}))

    def test_cpu_stack_and_work_rejections(self):
        for key,value in [('dispatch',1),('defined',0xffffffff),('stack','00'),('globals','00')]:
            changed=copy.deepcopy(self.original)
            changed['cases'][0]['snapshots'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(changed)
        changed=copy.deepcopy(self.original)
        changed['cases'][0]['snapshots'][-1]['registers']['sp']-=2
        with self.assertRaises(ValueError):validate(changed)

    def test_producer_and_profile_rejections(self):
        for key,value in [('producer_sha256','0'*64),('unicorn','unknown'),('memory_read_provider','none')]:
            with self.subTest(key=key),self.assertRaises(ValueError):validate(dict(self.original,**{key:value}))


if __name__=='__main__':
    unittest.main()
