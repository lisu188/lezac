"""Require continuous original traces and IRQ controls to detect nine compiled faults."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns());out.mkdir(parents=True)
    header=ROOT/'src/core/frame_actor_entry.hpp';source=header.read_bytes()
    test=ROOT/'tests/core/frame_actor_entry_test.cpp';test_bytes=test.read_bytes()
    faults=(
        ('skip_links','case 0x7ec2:push(0x7ec5);r.ip=0x432a;','case 0x7ec2:r.ip=0x7ec5;'),
        ('wrong_actor_base','case 0x7edb:r.di=arithmetic(r,r.di,0x1bae);','case 0x7edb:r.di=arithmetic(r,r.di,0x1b88);'),
        ('wrong_player_base','case 0x7f53:r.di=arithmetic(r,r.di,0x1b62);','case 0x7f53:r.di=arithmetic(r,r.di,0x1bae);'),
        ('wrong_restart_threshold','case 0x7efc:arithmetic(r,byte(0x79b9),0xe6,','case 0x7efc:arithmetic(r,byte(0x79b9),0xe5,'),
        ('reset_handoff_register','if (handoff==0) state_.callee=FrameActorCallerSnapshot{next};',
            'if (handoff==0) { next.ax=0;state_.callee=FrameActorCallerSnapshot{next}; }'),
        ('early_actor_handoff','if (operation.finished()) state_.outcome=operation.atBehaviorDispatch() ?',
            'if (true) state_.outcome=operation.atBehaviorDispatch() ?'),
        ('wrong_actor_return','case 0x7ee1:push(0x7ee4);','case 0x7ee1:push(0x7ec5);'),
        ('reversed_actor_gate','case 0x7ed4:branch(flag(1),','case 0x7ed4:branch(!flag(1),'),
        ('lost_irq_flags','push(static_cast<uint16_t>(r.flags));push(r.cs);push(r.ip);','push(0);push(r.cs);push(r.ip);'))
    report=dict(status='failed',source_sha256=hashlib.sha256(source).hexdigest(),faults=[])
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant=out/name;(variant/'core').mkdir(parents=True)
            text=source.decode('ascii')
            if before:
                if text.count(before)!=1:
                    raise ValueError('Frame actor mutation location differs: '+name)
                text=text.replace(before,after)
            (variant/'core/frame_actor_entry.hpp').write_text(text,encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Frame actor mutation did not compile: '+name)
            checked=subprocess.run([str(exe),str(fixture),str(ROOT)],stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,timeout=180)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name=='baseline':
                if checked.returncode!=0 or b'frame_actor_entry_original=ok' not in checked.stdout:
                    raise ValueError('Frame actor baseline failed')
            elif checked.returncode!=1 or b'frame_actor_entry=failed' not in checked.stdout:
                raise ValueError('Frame actor compiled fault was not detected: '+name)
            else:
                report['faults'].append(dict(name=name,output=checked.stdout.decode()))
        report['status']='passed'
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        report['source_preserved']=header.read_bytes()==source and test.read_bytes()==test_bytes
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['source_preserved']:
        raise ValueError('Frame actor mutation changed original sources')
    print('frame_actor_entry_mutations=ok faults=9 source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();run(args.cxx,args.fixture,args.out)
