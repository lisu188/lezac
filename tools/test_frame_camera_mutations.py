"""Require the frozen camera trace to reject four isolated C++ implementation faults."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from check_frame_camera_fixture import ROOT, FIXTURE, read_fixture


def run(cxx,out):
    header=ROOT/'src/core/frame_camera.hpp'
    original=header.read_bytes()
    source=original.decode('ascii')
    out=out/str(time.time_ns())
    out.mkdir(parents=True)
    corpus=out/'camera.bin'
    corpus.write_bytes(read_fixture(ROOT,FIXTURE))
    faults=(
        ('unsigned_remainder','r.dx=static_cast<uint16_t>(dividend%divisor);','r.dx=static_cast<uint16_t>(dividend & 7);'),
        ('right_clamp_zero','bus.writeWord(r.ds,0xc20a,7);','bus.writeWord(r.ds,0xc20a,0);'),
        ('omit_shake','case 0x36f6:r.ax=bus.readWord(r.ds,0x2098);','case 0x36f6:r.ax=0;'),
        ('skip_stack_limit','case 0x4ee:branch(flag(1),0x4f1,0x4f0);','case 0x4ee:branch(false,0x4f1,0x4f0);'))
    report=dict(status='failed',original_sha256=hashlib.sha256(original).hexdigest(),faults=[])
    try:
        for name,before,after in faults:
            if source.count(before)!=1:
                raise ValueError('Mutation location differs: '+name)
            variant=out/name
            (variant/'core').mkdir(parents=True)
            (variant/'core/frame_camera.hpp').write_text(source.replace(before,after),encoding='ascii')
            exe=variant/'test'
            command=[cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic','-I',str(variant),
                '-I',str(ROOT/'src'),str(ROOT/'tests/core/frame_camera_test.cpp'),'-o',str(exe)]
            built=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Mutant did not compile: '+name)
            checked=subprocess.run([str(exe),str(corpus)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'replay.log').write_bytes(checked.stdout)
            if checked.returncode!=1 or b'frame_camera=failed' not in checked.stdout:
                raise ValueError('Camera fault was not detected: '+name)
            report['faults'].append(dict(name=name,exit_code=checked.returncode,output=checked.stdout.decode()))
        report['status']='passed'
    finally:
        report['original_source_preserved']=header.read_bytes()==original
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['original_source_preserved']:
        raise ValueError('Original camera source changed')
    print('frame_camera_mutations=ok faults=4 original_source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    run(args.cxx,args.out)
