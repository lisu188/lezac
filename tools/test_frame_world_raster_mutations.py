"""Reject isolated backdrop, mask, transparent-pixel and clipping faults."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from check_frame_world_raster_fixture import ROOT,FIXTURE,read_fixture


def run(cxx,out):
    header=ROOT/'src/core/frame_world_raster.hpp'
    original=header.read_bytes();source=original.decode('ascii')
    out=out/str(time.time_ns());out.mkdir(parents=True)
    corpus=out/'raster.bin';corpus.write_bytes(read_fixture(ROOT,FIXTURE))
    faults=(
        ('truthy_backdrop','case 0xf9:branch(!flag(0x40),0x15c,0xfb);','case 0xf9:branch(lo(r.ax)==0,0x15c,0xfb);'),
        ('lost_tile_mask','logic(bus.readWord(r.es,r.di)&r.ax)','logic(0)'),
        ('opaque_zero_sprite','case 0x2d2:branch(!flag(0x40),0x2d7,0x2d4);','case 0x2d2:branch(true,0x2d7,0x2d4);'),
        ('lost_clip_stride','case 0x3bd:r.si=arithmetic(r.si,bus.readWord(r.ds,0xc210));','case 0x3bd:r.si=arithmetic(r.si,0);'))
    report=dict(status='failed',original_sha256=hashlib.sha256(original).hexdigest(),faults=[])
    try:
        for name,before,after in faults:
            if source.count(before)!=1:
                raise ValueError('Fault location differs: '+name)
            variant=out/name;(variant/'core').mkdir(parents=True)
            (variant/'core/frame_world_raster.hpp').write_text(source.replace(before,after),encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic','-I',str(variant),
                '-I',str(ROOT/'src'),str(ROOT/'tests/core/frame_world_raster_test.cpp'),'-o',str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Fault did not compile: '+name)
            checked=subprocess.run([str(exe),str(corpus),str(ROOT)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'replay.log').write_bytes(checked.stdout)
            if checked.returncode!=1 or b'frame_world_raster=failed' not in checked.stdout:
                raise ValueError('Fault was not detected: '+name)
            report['faults'].append(dict(name=name,exit_code=checked.returncode,output=checked.stdout.decode()))
        report['status']='passed'
    finally:
        report['original_source_preserved']=header.read_bytes()==original
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['original_source_preserved']:
        raise ValueError('Actual source changed')
    print('frame_world_raster_mutations=ok faults=4 original_source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();run(args.cxx,args.out)
