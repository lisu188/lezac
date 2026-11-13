"""Detect compiled finish faults without modifying production or test sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns());out.mkdir(parents=True)
    header=ROOT/'src/core/actor_finish.hpp';source=header.read_bytes()
    real_header=ROOT/'src/core/actor_real48.hpp';real_source=real_header.read_bytes()
    test=ROOT/'tests/core/actor_finish_test.cpp';test_bytes=test.read_bytes()
    faults=(
        ('vertical_fraction_carry','case 0x73fd:store(-46,arithmetic(local(-46),r.ax,false,false,true));','case 0x73fd:store(-46,arithmetic(local(-46),r.ax));'),
        ('horizontal_fraction_carry','case 0x741b:store(-44,arithmetic(local(-44),r.ax,false,false,true));','case 0x741b:store(-44,arithmetic(local(-44),r.ax));'),
        ('unsigned_hotspot','case 0x751e:cbw();','case 0x751e:zeroAh();'),
        ('truncated_fraction_write','case 0x7568:write(10,r.ax);','case 0x7568:wb(10,static_cast<uint8_t>(r.ax));'),
        ('wrong_expiry_parity','case 0x75aa:r.ax=logic(r.ax&1u);','case 0x75aa:r.ax=logic(r.ax&0u);'),
        ('lost_underflow_expiry','case 0x75c6:branch(flag(0x40),','case 0x75c6:branch(false,'),
        ('wrong_burst_capacity','case 0x403b:arithmetic(dw(0x2076),198,true);','case 0x403b:arithmetic(dw(0x2076),199,true);'),
        ('wrong_flame_lifetime','case 0x40e9:wb(9,117);','case 0x40e9:wb(9,116);'),
        ('first_owner_packet','case 0x4fd:sb(-9,static_cast<uint8_t>(r.ax));','case 0x4fd:if (lb(-9)>lb(-10)) sb(-9,static_cast<uint8_t>(r.ax));'),
        ('short_owner_copy','case 0x560:push(3);','case 0x560:push(2);'),
        ('wrong_return_cleanup','case 0x7780:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+4u);','case 0x7780:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+2u);'),
        ('wrong_pickup_selection','case 0x76b4:sb(-18,static_cast<uint8_t>(increment(lb(-18),true,true)));','case 0x76b4:sb(-18,static_cast<uint8_t>(increment(lb(-18),false,true)));'),
        ('wrong_debris_velocity','case 0x7738:r.ax=arithmetic(r.ax,300,true);','case 0x7738:r.ax=arithmetic(r.ax,299,true);'),
        ('lost_irq_flags','state_.registers=fromTimer(irq.snapshot().registers);state_.timer.reset();','state_.registers=fromTimer(irq.snapshot().registers);state_.registers.flags^=0x200;state_.timer.reset();'),
        ('real48_add_carry','case 0xc3f:r.bx=arithmetic(r.bx,r.si,false,false,true);','case 0xc3f:r.bx=arithmetic(r.bx,r.si);'),
        ('real48_rounding','case 0xc52:r.ax=arithmetic(r.ax,128);','case 0xc52:r.ax=arithmetic(r.ax,127);'),
        ('real48_multiply_carry','case 0xd1c:r.di=arithmetic(r.di,r.dx,false,false,true);','case 0xd1c:r.di=arithmetic(r.di,r.dx);'),
        ('real48_polynomial_stride','case 0x1395:r.di=arithmetic(r.di,6);','case 0x1395:r.di=arithmetic(r.di,5);'),
        ('real48_sine_flags','case 0x1068:push(static_cast<uint16_t>(r.flags));','case 0x1068:push(0);'),
        ('lost_borrowed_irq_ds','state_.registers=fromTimer(irq.snapshot().registers);state_.timer.reset();',
            'state_.registers=fromTimer(irq.snapshot().registers);state_.registers.ds=static_cast<uint16_t>(state_.gameSegment+0xaa2);state_.timer.reset();'))
    report=dict(status='failed',source_sha256=hashlib.sha256(source).hexdigest(),
        real48_source_sha256=hashlib.sha256(real_source).hexdigest(),
        instruction_grants=[1],string_grants=[65535],full_grant_matrix_in_separate_original_test=True,faults=[])
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant=out/name;(variant/'core').mkdir(parents=True)
            texts={'actor_finish.hpp':source.decode('ascii'),'actor_real48.hpp':real_source.decode('ascii')}
            if before:
                matches=[key for key,text in texts.items() if text.count(before)==1]
                if len(matches)!=1:
                    raise ValueError('Finish mutation location differs: '+name)
                key=matches[0];texts[key]=texts[key].replace(before,after)
            for key,text in texts.items():
                (variant/'core'/key).write_text(text,encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Finish mutation did not compile: '+name)
            checked=subprocess.run([str(exe),str(fixture),str(ROOT),'--one-grant'],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name=='baseline':
                if checked.returncode!=0 or b'actor_finish_original=ok cases=6136 replays=6136' not in checked.stdout or b'one_grant=1' not in checked.stdout:
                    raise ValueError('Finish baseline failed')
            elif checked.returncode!=1 or b'actor_finish=failed' not in checked.stdout:
                raise ValueError('Finish compiled fault was not detected: '+name)
            else:
                report['faults'].append(dict(name=name,output=checked.stdout.decode()))
        report['status']='passed'
    except Exception as error:
        report['error']=str(error);raise
    finally:
        report['source_preserved']=header.read_bytes()==source and real_header.read_bytes()==real_source and test.read_bytes()==test_bytes
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['source_preserved']:
        raise ValueError('Finish mutation changed original sources')
    print('actor_finish_mutations=ok faults=20 source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();run(args.cxx,args.fixture,args.out)
