"""Synthetic format controls; these are not original execution observations."""
import copy
import csv
import gzip
import io
import json
import os
from itertools import islice
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from frame_active_live_probe.trace import rows,inspect_trace
from frame_active_live_probe import project as projector
from frame_foreground_probe.trace import rows as foreground_rows

ROOT=Path(__file__).resolve().parents[1]


class ActiveTraceTests(unittest.TestCase):
    def setUp(self):
        source=foreground_rows(ROOT/'tests/fixtures/foreground_live/natural.csv.gz',{})
        self.samples=list(islice(source,6));source.close()
        self.header=list(self.samples[0])
        self.temporary=tempfile.TemporaryDirectory(prefix='active-format-')
        self.addCleanup(self.temporary.cleanup)
        self.path=Path(self.temporary.name)/'trace.csv.gz'

    def write(self,records,marker=True,end=True,sparse=True):
        stream=io.StringIO();writer=csv.writer(stream,lineterminator='\n')
        if marker:
            writer.writerow(['active-sparse-v1'])
        writer.writerow(self.header);previous=None
        for record in records:
            values=[record[key] for key in self.header]
            encoded=[('~' if sparse and previous is not None and record['kind']!='keyboard_enter' and
                value==old else value) for value,old in zip(values,previous)] if previous else values
            writer.writerow(encoded);previous=values
        if end:
            writer.writerow(['end'])
        self.path.write_bytes(gzip.compress(stream.getvalue().encode('ascii'),mtime=0))

    def windows(self):
        records=[dict(self.samples[0])];entry=next(row for row in self.samples if row['kind']=='keyboard_enter')
        for category in (0,1):
            base=dict(entry,call=str(category+1),keyboard_class=str(category),return_ip=str(0x7a57),target_completed='0')
            start=1000*(category+1)
            records.append(dict(base,kind='keyboard_enter',dispatch=str(start),ip=str(0x7903)))
            ips=[0x7903,0x3184,0x7a13]+([0xfea5] if category else [])+[0x7a57]
            for index,ip in enumerate(ips):
                records.append(dict(base,kind='keyboard_return' if ip==0x7a57 else 'instruction',
                    cs=str(0xf000) if ip==0xfea5 else base['return_cs'],ip=str(ip),dispatch=str(start+index),
                    target_completed='1' if category and ip==0x7a57 else '0'))
        return records

    def test_sparse_rows_roundtrip_without_loss(self):
        self.write(self.samples)
        metadata={};actual=list(rows(self.path,metadata))
        self.assertEqual(actual,self.samples)
        self.assertTrue(metadata['trace_end_marker'])

    def test_complete_synthetic_windows(self):
        self.write(self.windows())
        details=inspect_trace(self.path)
        self.assertTrue(details['validated_target_completed'])
        self.assertEqual([case['render_irq_entries'] for case in details['active_live_windows']],[0,1])

    def test_marker_and_end_are_required(self):
        for marker,end in ((False,True),(True,False)):
            with self.subTest(marker=marker,end=end):
                self.write(self.samples,marker=marker,end=end)
                with self.assertRaises(ValueError):
                    list(rows(self.path,{}))

    def test_inheritance_without_previous_row_is_rejected(self):
        records=copy.deepcopy(self.samples);records[0]['cs']='~';self.write(records)
        with self.assertRaises(ValueError):
            list(rows(self.path,{}))

    def test_dispatch_gap_is_rejected(self):
        records=self.windows();records[3]['dispatch']=str(int(records[3]['dispatch'])+1);self.write(records)
        with self.assertRaises(ValueError):
            inspect_trace(self.path)

    def test_irq_before_render_does_not_prove_render_irq(self):
        records=self.windows()
        render=next(i for i,row in enumerate(records) if row['call']=='2' and row['ip']==str(0x7a13))
        records[render]['ip'],records[render+1]['ip']=records[render+1]['ip'],records[render]['ip']
        records[render]['cs'],records[render+1]['cs']=records[render+1]['cs'],records[render]['cs']
        self.write(records)
        self.assertFalse(inspect_trace(self.path)['validated_target_completed'])

    def test_missing_render_boundary_is_rejected(self):
        records=self.windows()
        for row in records:
            if row['ip']==str(0x7a13):
                row['ip']=str(0x7a18)
        self.write(records)
        with self.assertRaises(ValueError):
            inspect_trace(self.path)


@unittest.skipUnless(os.name=='posix' and Path('/dev/shm').is_dir(),'RAM-only Linux projector')
class ProjectRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='active-project-',dir='/dev/shm')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)

    def test_missing_capture_retains_failed_report(self):
        out=self.root/'out'
        with self.assertRaises(FileNotFoundError):
            projector.project(self.root/'missing',out)
        report=json.loads((out/'report.json').read_text())
        self.assertEqual(report['status'],'failed')
        self.assertFalse((out/'cpu.bin').exists())

    def test_existing_output_is_untouched(self):
        marker=self.root/'keep';marker.write_bytes(b'owned evidence')
        with self.assertRaises(ValueError):
            projector.project(self.root/'missing',self.root)
        self.assertEqual(marker.read_bytes(),b'owned evidence')
        self.assertFalse((self.root/'report.json').exists())

    def test_partial_failure_is_not_reported_as_success(self):
        out=self.root/'out'
        def failed(capture,destination,repo):
            (destination/'partial.bin').write_bytes(b'failed evidence')
            raise ValueError('Canonical asset unreadable')
        with patch.object(projector,'_project',side_effect=failed):
            with self.assertRaisesRegex(ValueError,'Canonical asset unreadable'):
                projector.project(self.root/'missing',out)
        report=json.loads((out/'report.json').read_text())
        self.assertEqual(report['status'],'failed')
        self.assertIn('Canonical asset unreadable',report['error'])
        self.assertEqual((out/'partial.bin').read_bytes(),b'failed evidence')


if __name__=='__main__':
    unittest.main()
