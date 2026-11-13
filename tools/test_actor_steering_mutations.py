"""Detect compiled steering faults without editing the authenticated baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns());out.mkdir(parents=True)
    header=ROOT/'src/core/actor_steering.hpp';source=header.read_bytes()
    test=ROOT/'tests/core/actor_steering_test.cpp';test_bytes=test.read_bytes()
    faults=(
        ('unsigned_x','case 0x347f:r.dx=(r.ax&0x8000u) ? uint16_t{65535} : uint16_t{0};',
            'case 0x347f:r.dx=0;'),
        ('unsigned_y','case 0x3494:r.dx=(r.ax&0x8000u) ? uint16_t{65535} : uint16_t{0};',
            'case 0x3494:r.dx=0;'),
        ('signed_speed','case 0x3527:r.dx=logic(0);',
            'case 0x3527:r.dx=logic((r.ax&0x8000u) ? uint16_t{65535} : uint16_t{0});'),
        ('wrong_x_zero_gate','case 0x34b7:branch(!flag(0x40),','case 0x34b7:branch(flag(0x40),'),
        ('wrong_zero_factor','case 0x34cf:store(-6,0);','case 0x34cf:store(-6,0x81);'),
        ('wrong_square_operand','case 0x34ef:r.di=local(-14);','case 0x34ef:r.di=local(-8);'),
        ('sqrt_negative_gate','case 0xfd5:branch(!flag(0x40),','case 0xfd5:branch(flag(0x40),'),
        ('sqrt_logical_shift','(value>>1)|(value&128u)','(value>>1)'),
        ('sqrt_wrong_precision','arithmetic(r.ax&255u,20,true,true)','arithmetic(r.ax&255u,19,true,true)'),
        ('sqrt_wrong_halving','arithmetic(r.ax&255u,1,true,true)','arithmetic(r.ax&255u,1,false,true)'),
        ('sqrt_wrong_loop','case 0x100c:branch(!flag(1),','case 0x100c:branch(flag(1),'),
        ('wrong_output_x_reference','case 0x355b:les(8);','case 0x355b:les(4);'),
        ('short_vector_cleanup','r.sp+20u);if (state_.entry==ActorSteeringEntry::Vector)',
            'r.sp+18u);if (state_.entry==ActorSteeringEntry::Vector)'),
        ('wrong_caller_speed','case 0x7117:r.di=0x2074;','case 0x7117:r.di=0x2072;'),
        ('lost_irq_flags','state_.cpu=irq.snapshot();\n            } else {',
            'state_.cpu=irq.snapshot();if (!state_.cpu.timer) state_.cpu.registers.flags^=0x200;\n            } else {'),
        ('wrong_irq_accounting','ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();',
            'ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();++state_.cpu.timerDeliveries;'))
    report=dict(status='failed',source_sha256=hashlib.sha256(source).hexdigest(),
        instruction_grants=[1],full_grant_matrix_in_separate_original_test=True,faults=[])
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant=out/name;(variant/'core').mkdir(parents=True);text=source.decode('ascii')
            if before:
                if text.count(before)!=1:
                    raise ValueError('Steering mutation location differs: '+name)
                text=text.replace(before,after)
            (variant/'core/actor_steering.hpp').write_text(text,encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Steering mutation did not compile: '+name)
            checked=subprocess.run([str(exe),str(fixture),str(ROOT),'--one-grant'],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name=='baseline':
                if checked.returncode!=0 or b'actor_steering_original=ok cases=3736 replays=3736' not in checked.stdout or b'one_grant=1' not in checked.stdout:
                    raise ValueError('Steering mutation baseline failed')
            elif checked.returncode!=1 or b'actor_steering=failed' not in checked.stdout:
                raise ValueError('Steering compiled fault was not detected: '+name)
            else:
                report['faults'].append(dict(name=name,output=checked.stdout.decode()))
        report['status']='passed'
    except Exception as error:
        report['error']=str(error);raise
    finally:
        report['source_preserved']=header.read_bytes()==source and test.read_bytes()==test_bytes
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['source_preserved']:
        raise ValueError('Steering mutation changed original sources')
    print('actor_steering_mutations=ok faults='+str(len(faults))+' source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();run(args.cxx,args.fixture,args.out)
