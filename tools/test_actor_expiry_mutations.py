"""Detect compiled expiry/compaction faults while preserving original sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns());out.mkdir(parents=True)
    header=ROOT/'src/core/actor_expiry.hpp';source=header.read_bytes()
    test=ROOT/'tests/core/actor_expiry_test.cpp';test_bytes=test.read_bytes()
    faults=(
        ('lost_tick_parity','case 0x65ab:r.ax=logic(r.ax&1u);','case 0x65ab:r.ax=logic(0);'),
        ('wrong_life_direction','arithmetic(byte(2),r.ax&255u,true,true)','arithmetic(byte(2),r.ax&255u,false,true)'),
        ('wrong_record_stride','std::bit_cast<int16_t>(value)}*38','std::bit_cast<int16_t>(value)}*37'),
        ('short_record_copy','case 0x33b9:push(38);','case 0x33b9:push(37);'),
        ('skip_record_compaction','case 0x3398:branch(!flag(0x40)&&!less(),','case 0x3398:branch(true,'),
        ('wrong_physical_count','increment(data(0x208d),true,true)','increment(data(0x208d),false,true)'),
        ('wrong_actor_rewind','increment(dw(0x2082),true)','increment(dw(0x2082),false)'),
        ('wrong_kind10_gate','case 0x65ca:arithmetic(lb(-15),10,true,true);','case 0x65ca:arithmetic(lb(-15),11,true,true);'),
        ('rewrite_equal_physical_link','case 0x33fb:branch(flag(1)||flag(0x40),','case 0x33fb:branch(flag(1),'),
        ('rewrite_equal_first_reference','case 0x3444:branch(flag(1)||flag(0x40),','case 0x3444:branch(flag(1),'),
        ('rewrite_equal_second_reference','case 0x3456:branch(flag(1)||flag(0x40),','case 0x3456:branch(flag(1),'),
        ('wrong_visual_last_slot','case 0x5ae:branch(flag(0x40)||less(),','case 0x5ae:branch(less(),'),
        ('wrong_visual_stride','case 0x5bb:r.bx=8;','case 0x5bb:r.bx=7;'),
        ('lost_visual_direction','flag(0x400) ? uint16_t{65535} : uint16_t{1}','false ? uint16_t{65535} : uint16_t{1}'),
        ('wrong_visual_count','increment(data(0xc496),true,true)','increment(data(0xc496),false,true)'),
        ('short_helper_cleanup','case 0x3468:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+2u);',
            'case 0x3468:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+0u);'),
        ('wrong_actor_cleanup','if (tail.snapshot().outcome==ActorFinishOutcome::Returned) state_.outcome=ActorExpiryOutcome::Returned;',
            'if (tail.snapshot().outcome==ActorFinishOutcome::Returned) { r.sp=static_cast<uint16_t>(r.sp+2u);state_.outcome=ActorExpiryOutcome::Returned; }'),
        ('lost_irq_flags','state_.cpu=irq.snapshot();\n            } else {',
            'state_.cpu=irq.snapshot();if (!state_.cpu.timer) state_.cpu.registers.flags^=0x200;\n            } else {'),
        ('wrong_irq_accounting','ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();',
            'ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();++state_.cpu.timerDeliveries;'),
        ('lost_reference_endpoint','case 0x3465:branch(!flag(0x40),0x3428,0x3467);',
            'case 0x3465:r.ip=0x3467;'))
    report=dict(status='failed',source_sha256=hashlib.sha256(source).hexdigest(),
        instruction_grants=[1],string_grants=[65535],full_grant_matrix_in_separate_original_test=True,faults=[])
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant=out/name;(variant/'core').mkdir(parents=True);text=source.decode('ascii')
            if before:
                if text.count(before)!=1:
                    raise ValueError('Expiry mutation location differs: '+name)
                text=text.replace(before,after)
            (variant/'core/actor_expiry.hpp').write_text(text,encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Expiry mutation did not compile: '+name)
            checked=subprocess.run([str(exe),str(fixture),str(ROOT),'--one-grant'],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name=='baseline':
                if checked.returncode!=0 or b'actor_expiry_original=ok cases=3258 replays=3258' not in checked.stdout or b'one_grant=1' not in checked.stdout:
                    raise ValueError('Expiry baseline failed')
            elif checked.returncode!=1 or b'actor_expiry=failed' not in checked.stdout:
                raise ValueError('Expiry compiled fault was not detected: '+name)
            else:
                report['faults'].append(dict(name=name,output=checked.stdout.decode()))
        report['status']='passed'
    except Exception as error:
        report['error']=str(error);raise
    finally:
        report['source_preserved']=header.read_bytes()==source and test.read_bytes()==test_bytes
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['source_preserved']:
        raise ValueError('Expiry mutation changed original sources')
    print('actor_expiry_mutations=ok faults='+str(len(faults))+' source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();run(args.cxx,args.fixture,args.out)
