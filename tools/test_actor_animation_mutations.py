"""Require the original instruction corpus to reject eight compiled animation faults."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out = out/str(time.time_ns())
    out.mkdir(parents=True)
    header = ROOT/'src/core/actor_animation.hpp'
    source = header.read_bytes()
    test = ROOT/'tests/core/actor_animation_test.cpp'
    test_bytes = test.read_bytes()
    faults = (
        ('disabled_mode_runs','branch(!flag(1)&&!flag(0x40),0x6085,0x6082)','branch(true,0x6085,0x6082)'),
        ('delay_equality_advances','branch(!flag(1)&&!flag(0x40),0x609f,0x609c)','branch(!flag(1),0x609f,0x609c)'),
        ('unsigned_step','std::bit_cast<int8_t>','std::bit_cast<uint8_t>'),
        ('short_backup','case 0x6103:push(7)','case 0x6103:push(6)'),
        ('direction_not_cleared','r.flags&=~uint32_t{0x400}','r.flags|=uint32_t{0x400}'),
        ('eager_copy','const auto grant = r.cx ? copies(r.cx) : 0;','(void)copies; const auto grant = r.cx;'),
        ('wrong_descriptor_word','r.di+0xc224u','r.di+0xc226u'),
        ('borrowed_ds_not_restored','case 0x921:r.ds=r.dx','case 0x921:r.ds=r.es'))
    report = dict(status='failed',faults=[],source_sha256=hashlib.sha256(source).hexdigest())
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant = out/name
            (variant/'core').mkdir(parents=True)
            text = source.decode('ascii')
            if before:
                if text.count(before) != 1:
                    raise ValueError('Animation mutation location differs: '+name)
                text = text.replace(before,after)
            (variant/'core/actor_animation.hpp').write_text(text,encoding='ascii')
            exe = variant/'test'
            built = subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Animation mutant did not compile: '+name)
            checked = subprocess.run([str(exe),str(fixture),str(ROOT)],stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,timeout=30)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name == 'baseline':
                if checked.returncode != 0 or b'actor_animation_original=ok' not in checked.stdout:
                    raise ValueError('Animation baseline failed')
            elif checked.returncode != 1 or b'actor_animation=failed' not in checked.stdout:
                raise ValueError('Animation fault was not detected: '+name)
            else:
                report['faults'].append(dict(name=name,exit_code=checked.returncode,output=checked.stdout.decode()))
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        report['source_preserved'] = header.read_bytes() == source and test.read_bytes() == test_bytes
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['source_preserved']:
        raise ValueError('Animation sources changed during mutation checks')
    print('actor_animation_mutations=ok faults=8 original_source_preserved=1 report='+str(out/'report.json'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    run(args.cxx,args.fixture,args.out)
