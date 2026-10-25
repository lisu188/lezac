"""Exercise bounded original-oracle failures without Unicorn or RAM exports."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import oracle_failure_report as failure


class CurrentMemory:
    def __init__(self,raw): self.raw=raw;self.calls=[]
    def mem_read(self,address,size):
        self.calls.append((address,size));return self.raw


class FailureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='lezac-oracle-failure-')
        self.addCleanup(self.temp.cleanup);self.out=Path(self.temp.name)
        self.raw=bytes(range(256))*4096
        self.arguments=dict(case=123,profile=dict(family='controlled',flags=0x202),
            sources={'producer.py':'a'*64},initial=self.raw)

    def test_complete_memory_is_hashed_not_exported(self):
        current=CurrentMemory(self.raw)
        result=failure.write_failure(self.out,ValueError('controlled failure'),**self.arguments,
            endpoints=[(tuple(range(14)),self.raw,None)],current=current,
            projection=b'compact projection')
        self.assertEqual(current.calls,[(0,1048576)])
        expected=dict(bytes=1048576,sha256=hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(result['initial'],expected);self.assertEqual(result['current'],expected)
        self.assertEqual(result['endpoints'][0]['memory'],expected)
        self.assertEqual(result['endpoints'][0]['registers'],list(range(14)))
        self.assertEqual(result['guest_memory_bytes_written'],0)
        self.assertEqual([p.name for p in self.out.iterdir()],['failed.json'])
        raw=(self.out/'failed.json').read_bytes()
        self.assertLess(len(raw),failure.MAX_BYTES);self.assertNotIn(self.raw,raw)
        self.assertEqual(json.loads(raw),result)

    def test_diagnostic_tails_and_endpoint_count_are_bounded(self):
        rows=[tuple(range(i,i+20)) for i in range(100)]
        result=failure.write_failure(self.out,RuntimeError('x'*100000),**self.arguments,
            trace=rows,writes=rows,endpoints=[(row,self.raw,None) for row in rows])
        self.assertEqual(len(result['trace_tail']),16);self.assertEqual(len(result['trace_tail'][0]),14)
        self.assertEqual(result['trace_tail'][-1],list(rows[-1][:14]))
        self.assertEqual(len(result['write_tail']),16);self.assertEqual(len(result['write_tail'][0]),3)
        self.assertEqual(len(result['endpoints']),2);self.assertEqual(len(result['error']),1024)

    def test_oversized_profile_and_source_metadata_are_digested(self):
        arguments=dict(self.arguments,profile={'large':'x'*100000},sources={'large':'y'*100000})
        result=failure.write_failure(self.out,RuntimeError('bounded'),**arguments)
        self.assertTrue(result['profile']['truncated']);self.assertTrue(result['source_sha256']['truncated'])
        self.assertLess((self.out/'failed.json').stat().st_size,failure.MAX_BYTES)

    def test_absent_memory_and_early_failure(self):
        result=failure.write_failure(self.out,KeyboardInterrupt(),case=-1,profile=None,sources={})
        self.assertIsNone(result['initial']);self.assertIsNone(result['current'])
        self.assertIsNone(result['projection']);self.assertEqual(result['endpoints'],[])

    def test_current_read_failure_keeps_original_error(self):
        class Unavailable:
            def mem_read(self,*unused): raise RuntimeError('unavailable')
        result=failure.write_failure(self.out,ValueError('original failure'),**self.arguments,current=Unavailable())
        self.assertEqual(result['error'],'original failure')
        self.assertEqual(result['current'],{'unavailable':'unavailable'})

    def test_existing_report_is_preserved(self):
        target=self.out/'failed.json';target.write_bytes(b'preserve existing failure')
        with self.assertRaises(FileExistsError):
            failure.write_failure(self.out,ValueError('new'),**self.arguments)
        self.assertEqual(target.read_bytes(),b'preserve existing failure')

    def test_total_reserve_rejects_before_creating_a_file(self):
        rows=[tuple([10**1000]*14)]*16
        with self.assertRaisesRegex(ValueError,'bounded reserve'):
            failure.write_failure(self.out,ValueError('oversized'),**self.arguments,trace=rows)
        self.assertEqual(list(self.out.iterdir()),[])

    def test_broken_link_is_preserved(self):
        target=self.out/'failed.json';missing=self.out/'missing'
        try: target.symlink_to(missing)
        except OSError as error: self.skipTest('Symbolic links unavailable: '+str(error))
        with self.assertRaises(FileExistsError):
            failure.write_failure(self.out,ValueError('new'),**self.arguments)
        self.assertTrue(target.is_symlink());self.assertFalse(missing.exists())

    def test_producer_failure_handler_only_uses_bounded_writer(self):
        source=Path(__file__).with_name('frame_actor_pass_oracle.py').read_text()
        tree=ast.parse(source)
        handlers=[node for node in ast.walk(tree) if isinstance(node,ast.ExceptHandler) and node.name=='error']
        self.assertEqual(len(handlers),1)
        calls=[node.func for node in ast.walk(handlers[0]) if isinstance(node,ast.Call)]
        self.assertEqual(sum(isinstance(call,ast.Name) and call.id=='write_failure' for call in calls),1)
        self.assertFalse(any(isinstance(call,ast.Attribute) and call.attr in ('write_bytes','mem_read','write_text') for call in calls))

    def test_producer_protects_initializer_and_case_setup(self):
        tree=ast.parse(Path(__file__).with_name('frame_actor_pass_oracle.py').read_text())
        generate=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='generate')
        protected=next(node for node in generate.body if isinstance(node,ast.Try))
        def setup_calls(node):
            return sorted(call.func.id if isinstance(call.func,ast.Name) else call.func.attr
                for call in ast.walk(node) if isinstance(call,ast.Call) and
                (isinstance(call.func,ast.Name) and call.func.id=='initial_case' or
                 isinstance(call.func,ast.Attribute) and call.func.attr=='sine_table'))
        self.assertEqual(setup_calls(generate),['initial_case','sine_table'])
        self.assertEqual(setup_calls(protected),setup_calls(generate))


if __name__=='__main__': unittest.main()
