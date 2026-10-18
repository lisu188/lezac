"""Detect ten compiled precontact faults without modifying production sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns());out.mkdir(parents=True)
    header=ROOT/'src/core/actor_precontact.hpp';source=header.read_bytes()
    test=ROOT/'tests/core/actor_precontact_test.cpp';test_bytes=test.read_bytes()
    faults=(
        ('wrong_player_controls','case 0x6175:al(data(0x1b78));','case 0x6175:al(data(0x1b7d));'),
        ('unsigned_hotspot','case 0x62a4:r.ax=(r.ax&128u) ? static_cast<uint16_t>((r.ax&255u)|0xff00u) : r.ax&255u;',
            'case 0x62a4:r.ax&=255u;'),
        ('wrong_contact_boundary','case 0x63c6:arithmetic(r.ax,10,true);','case 0x63c6:arithmetic(r.ax,9,true);'),
        ('wrong_target_tie','case 0x6540:branch(flag(1)||flag(0x40),','case 0x6540:branch(flag(1),'),
        ('wrong_inverse_link','case 0x588f:store(-2,65535);','case 0x588f:store(-2,1);'),
        ('wrong_serial_boundary','case 0x5885:arithmetic(lb(6),128,true,true);','case 0x5885:arithmetic(lb(6),127,true,true);'),
        ('ignore_locked_link','case 0x58b0:branch(!flag(0x40),','case 0x58b0:branch(true,'),
        ('skip_pickup_rng','case 0x6449:farCall(0x13a8,0x644e);','case 0x6449:r.ip=0x644e;'),
        ('wrong_helper_return','case 0x5996:case 0x5afa:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+4u);',
            'case 0x5996:case 0x5afa:r.ip=pop();r.sp=static_cast<uint16_t>(r.sp+2u);'),
        ('lost_irq_flags','push(static_cast<uint16_t>(r.flags));push(r.cs);push(r.ip);',
            'push(0);push(r.cs);push(r.ip);'))
    report=dict(status='failed',source_sha256=hashlib.sha256(source).hexdigest(),faults=[])
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant=out/name;(variant/'core').mkdir(parents=True);text=source.decode('ascii')
            if before:
                if text.count(before)!=1:
                    raise ValueError('Precontact mutation location differs: '+name)
                text=text.replace(before,after)
            (variant/'core/actor_precontact.hpp').write_text(text,encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Precontact mutation did not compile: '+name)
            checked=subprocess.run([str(exe),str(fixture),str(ROOT)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name=='baseline':
                if checked.returncode!=0 or b'actor_precontact_original=ok' not in checked.stdout:
                    raise ValueError('Precontact baseline failed')
            elif checked.returncode!=1 or b'actor_precontact=failed' not in checked.stdout:
                raise ValueError('Precontact compiled fault was not detected: '+name)
            else:
                report['faults'].append(dict(name=name,output=checked.stdout.decode()))
        report['status']='passed'
    except Exception as error:
        report['error']=str(error);raise
    finally:
        report['source_preserved']=header.read_bytes()==source and test.read_bytes()==test_bytes
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['source_preserved']:
        raise ValueError('Precontact mutation changed original sources')
    print('actor_precontact_mutations=ok faults=10 source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();run(args.cxx,args.fixture,args.out)
