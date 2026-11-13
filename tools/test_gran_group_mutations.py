"""Require complete original GRAN storage outputs to reject eight compiled faults."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns())
    out.mkdir(parents=True)
    header=ROOT/'src/gameplay/gran_group.hpp'
    source=header.read_bytes()
    test=ROOT/'tests/gameplay/gran_group_original_test.cpp'
    test_bytes=test.read_bytes()
    faults=(
        ('lost_raw_record','next.actors[oldActors+i+1] = actor;','next.actors[oldActors+i+1] = {};'),
        ('actor_order_visuals','actor[1] = static_cast<uint8_t>(actor[1]+visualBase);',
            'actor[1] = static_cast<uint8_t>(i+visualBase);'),
        ('unrebased_segment_timer','actor[2] = static_cast<uint8_t>(actor[2]+visualBase);','actor[2] = actor[2];'),
        ('wrong_group_owner','const auto first = static_cast<uint16_t>(oldActors+1);',
            'const auto first = static_cast<uint16_t>(oldActors+2);'),
        ('unrebased_link_target','link[1] = static_cast<uint8_t>(link[1]+visualBase);','link[1] = link[1];'),
        ('wrong_animation_mode','limits[0],limits[1],actor[26],1','limits[0],limits[1],actor[26],2'),
        ('shifted_descriptor','image.end(),visual.begin()+4','image.end(),visual.begin()+3'),
        ('inactive_tail_write','state = next;','next.actors[ActorStorage::capacity][5] ^= 1; state = next;'))
    report=dict(status='failed',source_sha256=hashlib.sha256(source).hexdigest(),faults=[])
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant=out/name
            (variant/'gameplay').mkdir(parents=True)
            text=source.decode('ascii')
            if before:
                if text.count(before)!=1:
                    raise ValueError('GRAN mutation location differs: '+name)
                text=text.replace(before,after)
            (variant/'gameplay/gran_group.hpp').write_text(text,encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),str(ROOT/'src/resources/binary.cpp'),
                '-o',str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('GRAN mutation did not compile: '+name)
            checked=subprocess.run([str(exe),str(fixture),str(ROOT)],stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,timeout=30)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name=='baseline':
                if checked.returncode!=0 or b'gran_group_original=ok' not in checked.stdout:
                    raise ValueError('GRAN baseline failed')
            elif checked.returncode!=1 or b'gran_group=failed' not in checked.stdout:
                raise ValueError('GRAN fault was not detected: '+name)
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
        raise ValueError('GRAN sources changed during mutation checks')
    print('gran_group_mutations=ok faults=8 source_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    run(args.cxx,args.fixture,args.out)
