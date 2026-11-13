"""Compile isolated continuation faults and require the focused tests to reject them."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
FAULTS=(
    ('callee_register_restore','child.registers=r;','(void)child;'),
    ('irq_return_ip','push(r.cs);push(r.ip);','push(r.cs);push(static_cast<uint16_t>(r.ip+1u));'),
    ('finished_irq','finished() || interruptInProgress()','interruptInProgress()'),
    ('zero_budget','used<budget && !finished()','used<=budget && !finished()'))


def check(cxx,out):
    out.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='active-mutations-',dir=out)).resolve()
    header=ROOT/'src/core/frame_active.hpp'
    source=header.read_bytes();digest=hashlib.sha256(source).hexdigest()
    report=dict(passed=False,original_source_preserved=False,full_frame_claim=False,controls=[])
    try:
        for name,old,new in (('baseline','',''),*FAULTS):
            work=out/name;target=work/'src/core/frame_active.hpp';target.parent.mkdir(parents=True)
            text=source.decode('utf-8')
            if old:
                if text.count(old)!=1:
                    raise ValueError('Mutation anchor differs: '+name)
                text=text.replace(old,new,1)
            target.write_bytes(text.encode('utf-8'))
            exe=work/'unit'
            result=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I'+str(work/'src'),'-I'+str(ROOT/'src'),str(ROOT/'tests/core/frame_active_test.cpp'),'-o',str(exe)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            (work/'build.log').write_bytes(result.stdout)
            if result.returncode:
                raise ValueError('Mutation did not compile: '+name)
            result=subprocess.run([str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (work/'test.log').write_bytes(result.stdout)
            if (result.returncode==0)!=(name=='baseline') or result.returncode not in (0,1):
                raise ValueError('Mutation sensitivity differs: '+name)
            report['controls'].append(dict(name=name,exit_code=result.returncode,output=result.stdout.decode()))
        report.update(passed=True,original_source_preserved=hashlib.sha256(header.read_bytes()).hexdigest()==digest)
        if not report['original_source_preserved']:
            raise ValueError('Original continuation source changed')
        print('frame_active_mutations=ok faults=4 original_source_preserved=1')
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();check(args.cxx,args.out.resolve())
