"""Detect compiled contact faults without modifying production or test sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns());out.mkdir(parents=True)
    header=ROOT/'src/core/actor_contact.hpp';source=header.read_bytes()
    test=ROOT/'tests/core/actor_contact_test.cpp';test_bytes=test.read_bytes()
    faults=(
        ('wrong_tile_anchor','case 0x6562:r.ax=arithmetic(r.ax,4);','case 0x6562:r.ax=arithmetic(r.ax,0);'),
        ('wrong_bottom_range','case 0x5d99:arithmetic(lb(-3),82,true,true);','case 0x5d99:arithmetic(lb(-3),76,true,true);'),
        ('wrong_periodic_modulo','case 0x5e5e:r.cx=29;','case 0x5e5e:r.cx=28;'),
        ('unsigned_flame_gate','case 0x5f64:branch(flag(0x40)||less(),','case 0x5f64:branch(flag(0x40),'),
        ('wrong_flame_step','case 0x5f4a:store(-6,arithmetic(local(-6),2));','case 0x5f4a:store(-6,arithmetic(local(-6),1));'),
        ('skip_mass_double','case 0x5f72:branch(flag(1)||flag(0x40),','case 0x5f72:branch(true,'),
        ('first_bomb_attribution','case 0x3a59:r.ax=increment(r.ax,true);','case 0x3a59:r.ax=0;'),
        ('truncate_head_owner','case 0x5be5:r.ax=read(18);','case 0x5be5:r.ax=read(18)&255u;'),
        ('first_trigger_match','case 0x57a5:store(-6,r.ax);','case 0x57a5:if (local(-6)==0) store(-6,r.ax);'),
        ('exclusive_trigger_upper','case 0x5810:branch(!flag(1)&&!flag(0x40),','case 0x5810:branch(!flag(1),'),
        ('stop_mapping_after_first','case 0x585d:arithmetic(local(-4),4,true);','case 0x585d:arithmetic(4,4,true);'),
        ('unsigned_sound_priority','case 0x166a:branch(!less(),','case 0x166a:branch(!flag(1),'),
        ('lost_irq_flags','else { state_.registers=irq.registers();state_.interrupt.reset(); }',
            'else { state_.registers=irq.registers();state_.registers.flags^=0x200;state_.interrupt.reset(); }'))
    report=dict(status='failed',source_sha256=hashlib.sha256(source).hexdigest(),
        instruction_grants=[1],string_grants=[65535],full_grant_matrix_in_separate_original_test=True,faults=[])
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant=out/name;(variant/'core').mkdir(parents=True);text=source.decode('ascii')
            if before:
                if text.count(before)!=1:
                    raise ValueError('Contact mutation location differs: '+name)
                text=text.replace(before,after)
            (variant/'core/actor_contact.hpp').write_text(text,encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Contact mutation did not compile: '+name)
            checked=subprocess.run([str(exe),str(fixture),str(ROOT),'--one-grant'],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name=='baseline':
                if checked.returncode!=0 or b'actor_contact_original=ok cases=5570 replays=5570' not in checked.stdout or b'one_grant=1' not in checked.stdout:
                    raise ValueError('Contact baseline failed')
            elif checked.returncode!=1 or b'actor_contact=failed' not in checked.stdout:
                raise ValueError('Contact compiled fault was not detected: '+name)
            else:
                report['faults'].append(dict(name=name,output=checked.stdout.decode()))
        report['status']='passed'
    except Exception as error:
        report['error']=str(error);raise
    finally:
        report['source_preserved']=header.read_bytes()==source and test.read_bytes()==test_bytes
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['source_preserved']:
        raise ValueError('Contact mutation changed original sources')
    print('actor_contact_mutations=ok faults=13 source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();run(args.cxx,args.fixture,args.out)
