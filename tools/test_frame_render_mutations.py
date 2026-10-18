"""Demonstrate sensitivity to isolated caller faults without changing repo sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from check_frame_render_fixture import ROOT,FIXTURE,run

FAULTS=(
    ('active_only', 'compareByte(bus.readByte(r.ds,0x79e6));',
        'compareByte(bus.readByte(r.ds,0x79e6)==1?1:0);'),
    ('second_view_destination', 'r.ax=bus.readWord(r.ds,0x79f2);',
        'r.ax=bus.readWord(r.ds,0x79f0);'),
    ('late_destination_store', 'case 0x7a2d:bus.writeWord(r.ds,0xc1f4,r.ax);',
        'case 0x7a2d:;'),
    ('camera_argument_order', 'case 0x7a1a:push(bus.readWord(r.ds,0xc21e));',
        'case 0x7a1a:push(bus.readWord(r.ds,0xc220));'))


def check(cxx,out):
    out.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='render-mutations-',dir=out)).resolve()
    header=ROOT/'src/core/frame_render.hpp'
    source=header.read_bytes()
    digest=hashlib.sha256(source).hexdigest()
    report=dict(passed=False,original_source_preserved=False,full_frame_claim=False,controls=[])
    try:
        corpus=out/'oracle.bin'
        run(ROOT,FIXTURE,corpus,out/'fixture-report.json')
        for name,old,new in (('baseline','',''),*FAULTS):
            work=out/name
            target=work/'src/core/frame_render.hpp'
            target.parent.mkdir(parents=True)
            text=source.decode('utf-8')
            if old:
                if text.count(old)!=1:
                    raise ValueError('Mutation anchor differs: '+name)
                text=text.replace(old,new,1)
            target.write_bytes(text.encode('utf-8'))
            executable=work/'replay'
            command=[cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I'+str(work/'src'),'-I'+str(ROOT/'src'),str(ROOT/'tests/core/frame_render_test.cpp'),'-o',str(executable)]
            built=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            (work/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Mutation failed to compile: '+name)
            result=subprocess.run([str(executable),str(corpus),str(ROOT)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            (work/'replay.log').write_bytes(result.stdout)
            expected=(result.returncode==0) if name=='baseline' else (
                result.returncode==1 and b'frame_render=failed' in result.stdout)
            if not expected:
                raise ValueError('Mutation sensitivity differs: '+name)
            report['controls'].append(dict(name=name,exit_code=result.returncode,expected=True))
        report.update(passed=True,original_source_preserved=hashlib.sha256(header.read_bytes()).hexdigest()==digest)
        if not report['original_source_preserved']:
            raise ValueError('Original caller source changed')
        print('frame_render_mutations=ok faults=4 original_source_preserved=1')
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    check(args.cxx,args.out.resolve())
