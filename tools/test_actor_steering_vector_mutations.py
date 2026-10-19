"""Detect compiled typed-boundary faults against original-derived outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns());out.mkdir(parents=True)
    source=ROOT/'src/core/actor_steering_vector.cpp';original=source.read_bytes()
    test=ROOT/'tests/core/actor_steering_vector_test.cpp';test_bytes=test.read_bytes()
    parser=ROOT/'src/diagnostics/actor_steering_fixture.hpp';parser_bytes=parser.read_bytes()
    faults=(
        ('negated_x_input','writeWord(stackSegment,bp-4,static_cast<uint16_t>(dx));','writeWord(stackSegment,bp-4,static_cast<uint16_t>(-dx));'),
        ('negated_y_input','writeWord(stackSegment,bp-6,static_cast<uint16_t>(dy));','writeWord(stackSegment,bp-6,static_cast<uint16_t>(-dy));'),
        ('narrow_unsigned_speed','static_cast<uint8_t>(speed>>8);','static_cast<uint8_t>((speed>>8)&127u);'),
        ('wrong_speed_low_byte','static_cast<uint8_t>(speed);','static_cast<uint8_t>(speed+1u);'),
        ('wrong_output_axis','std::bit_cast<int16_t>(word(stackSegment,bp-12))','std::bit_cast<int16_t>(word(stackSegment,bp-14))'),
        ('wrong_instruction_reserve','dispatchedInstructions>=65536','dispatchedInstructions>=1'))
    report=dict(status='failed',source_sha256=hashlib.sha256(original).hexdigest(),faults=[])
    try:
        for name,before,after in (('baseline','',''),*faults):
            variant=out/name;variant.mkdir();text=original.decode('ascii')
            if before:
                if text.count(before)!=1: raise ValueError('Vector mutation location differs: '+name)
                text=text.replace(before,after)
            cpp=variant/'vector.cpp';cpp.write_text(text,encoding='ascii');exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic','-I',str(ROOT/'src'),
                str(test),str(cpp),'-o',str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode: raise ValueError('Vector fault did not compile: '+name)
            checked=subprocess.run([str(exe),str(fixture)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            (variant/'replay.log').write_bytes(checked.stdout)
            if name=='baseline':
                if checked.returncode!=0 or b'actor_steering_vector_original=ok cases=2136' not in checked.stdout:
                    raise ValueError('Vector mutation baseline failed')
            elif checked.returncode!=1 or b'actor_steering_vector=failed' not in checked.stdout:
                raise ValueError('Vector compiled fault was not detected: '+name)
            else: report['faults'].append(dict(name=name,output=checked.stdout.decode()))
        report['status']='passed'
    except Exception as error:
        report['error']=str(error);raise
    finally:
        report['sources_preserved']=source.read_bytes()==original and test.read_bytes()==test_bytes and parser.read_bytes()==parser_bytes
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['sources_preserved']: raise ValueError('Vector mutations changed baseline sources')
    print('actor_steering_vector_mutations=ok faults=6 sources_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cxx',required=True)
    parser.add_argument('--fixture',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();run(args.cxx,args.fixture,args.out)
