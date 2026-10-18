"""Require the original link corpus to detect eight separately compiled faults."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns());out.mkdir(parents=True)
    header=ROOT/'src/core/boss_links.hpp'
    source=header.read_bytes()
    test=ROOT/'tests/core/boss_links_test.cpp'
    test_bytes=test.read_bytes()
    faults=(
        ('skip_later_links','case 0x4523:branch(flag(0x40),','case 0x4523:branch(true,'),
        ('unsigned_bias','std::bit_cast<int8_t>','std::bit_cast<uint8_t>'),
        ('wrong_phase_mask','case 0x4440:r.ax=logic(r.ax&127u);','case 0x4440:r.ax=logic(r.ax&255u);'),
        ('wrong_cosine_phase','case 0x4453:r.ax=arithmetic(r.ax,32);','case 0x4453:r.ax=arithmetic(r.ax,16);'),
        ('wrong_spring_y_offset','case 0x43d1:r.ax=read(9);','case 0x43d1:r.ax=read(7);'),
        ('lost_multiply_high_word','case 0x940:r.dx=arithmetic(r.dx,r.bx);','case 0x940:r.dx=arithmetic(r.dx,0);'),
        ('wrong_orbit_radius','case 0x4475:al(byte(4));','case 0x4475:al(byte(5));'),
        ('lost_phase_write','bus.writeByte(r.es,static_cast<uint16_t>(r.di+6u),static_cast<uint8_t>(r.ax));','(void)r.ax;'))
    report=dict(status='failed',source_sha256=hashlib.sha256(source).hexdigest(),faults=[])
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant=out/name;(variant/'core').mkdir(parents=True)
            text=source.decode('ascii')
            if before:
                if text.count(before)!=1:
                    raise ValueError('Link mutation location differs: '+name)
                text=text.replace(before,after)
            (variant/'core/boss_links.hpp').write_text(text,encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Link mutation did not compile: '+name)
            checked=subprocess.run([str(exe),str(fixture),str(ROOT)],stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,timeout=60)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name=='baseline':
                if checked.returncode!=0 or b'boss_links_original=ok' not in checked.stdout:
                    raise ValueError('Original link baseline failed')
            elif checked.returncode!=1 or b'boss_links=failed' not in checked.stdout:
                raise ValueError('Compiled link fault was not detected: '+name)
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
        raise ValueError('Link sources changed during mutation checks')
    print('boss_links_mutations=ok faults=8 source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    run(args.cxx,args.fixture,args.out)
