"""Detect compiled classifier faults without changing production or test sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns());out.mkdir(parents=True)
    header=ROOT/'src/core/actor_tile_flags.hpp';source=header.read_bytes()
    test=ROOT/'tests/core/actor_tile_flags_test.cpp';test_bytes=test.read_bytes()
    faults=(
        ('wrong_kind_gate','case 0x65da:compare(lb(-15),13);','case 0x65da:compare(lb(-15),12);'),
        ('exclusive_floor_upper','case 0x65e7:compare(data(0x2055),82);','case 0x65e7:compare(data(0x2055),81);'),
        ('exclusive_side_upper','case 0x65ff:compare(data(0x2050),76);','case 0x65ff:compare(data(0x2050),75);'),
        ('wrong_single_right','case 0x6610:compare(data(0x2052),1);','case 0x6610:compare(data(0x2053),1);'),
        ('wrong_single_top','case 0x6628:compare(data(0x204d),1);','case 0x6628:compare(data(0x2049),1);'),
        ('lost_floor_pair','case 0x6657:compare(data(0x2056),1);','case 0x6657:compare(data(0x2055),1);'),
        ('lost_left_pair','case 0x6683:compare(data(0x2050),1);','case 0x6683:compare(data(0x204c),1);'),
        ('wrong_flag_slot','case 0x65ee:sb(-33,1);','case 0x65ee:sb(-34,1);'),
        ('inverted_left_edge','case 0x670f:branch(!flag(1)&&!flag(0x40),','case 0x670f:branch(flag(1)||flag(0x40),'),
        ('lost_behavior_dispatch','case 0x66f8:branch(flag(0x40),','case 0x66f8:branch(!flag(0x40),'),
        ('lost_high_accumulator','(r.ax&0xff00u)|value','value'),
        ('lost_auxiliary_carry','|((a^b^value)&16u)',''),
        ('lost_irq_flags','else { state_.registers=irq.registers();state_.interrupt.reset(); }',
            'else { state_.registers=irq.registers();state_.registers.flags^=0x200;state_.interrupt.reset(); }'),
        ('wrong_irq_accounting','++state_.timerDeliveries;','state_.timerDeliveries+=2;'))
    report=dict(status='failed',source_sha256=hashlib.sha256(source).hexdigest(),
        instruction_grants=[1],string_grants=[65535],full_grant_matrix_in_separate_original_test=True,faults=[])
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant=out/name;(variant/'core').mkdir(parents=True);text=source.decode('ascii')
            if before:
                if text.count(before)!=1:
                    raise ValueError('Tile mutation location differs: '+name)
                text=text.replace(before,after)
            (variant/'core/actor_tile_flags.hpp').write_text(text,encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Tile mutation did not compile: '+name)
            checked=subprocess.run([str(exe),str(fixture),str(ROOT),'--one-grant'],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name=='baseline':
                if checked.returncode!=0 or b'actor_tile_flags_original=ok cases=5972 replays=5972' not in checked.stdout or b'one_grant=1' not in checked.stdout:
                    raise ValueError('Tile baseline failed')
            elif checked.returncode!=1 or b'actor_tile_flags=failed' not in checked.stdout:
                raise ValueError('Tile compiled fault was not detected: '+name)
            else:
                report['faults'].append(dict(name=name,output=checked.stdout.decode()))
        report['status']='passed'
    except Exception as error:
        report['error']=str(error);raise
    finally:
        report['source_preserved']=header.read_bytes()==source and test.read_bytes()==test_bytes
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['source_preserved']:
        raise ValueError('Tile mutation changed original sources')
    print('actor_tile_flags_mutations=ok faults=14 source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();run(args.cxx,args.fixture,args.out)
