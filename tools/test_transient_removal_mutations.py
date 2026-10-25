"""Compile bounded faults against an authenticated removal replay baseline."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

import check_transient_removal_fixture as fixture

ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/core/transient_removal.hpp'
FAULTS=(
    ('record_width','r.bx=11;','r.bx=10;'),
    ('copy_direction','flag(0x400) ? uint16_t{65535}','false ? uint16_t{65535}'),
    ('copy_write','bus.writeByte(r.es,r.di,bus.readByte(r.ds,r.si));','(void)bus.readByte(r.ds,r.si);'),
    ('spark_metadata','r.bx+0x78d6u','r.bx+0x78d7u'),
    ('spark_count','increment(dw(0x2076),true)','dw(0x2076)'),
    ('debris_count','increment(dw(0x207e),true)','dw(0x207e)'),
    ('parent_cursor','increment(bus.readWord(r.ss,static_cast<uint16_t>(r.di-2u)),true)',
        'increment(bus.readWord(r.ss,static_cast<uint16_t>(r.di-2u)),false)'),
    ('parent_condition','branch(flag(1),0x45f2,0x45eb)','branch(false,0x45f2,0x45eb)'),
    ('ret_cleanup','r.sp=static_cast<uint16_t>(r.sp+4u);','r.sp=static_cast<uint16_t>(r.sp+2u);'),
    ('caller_frame','r.sp!=sp || r.bp!=bp','false && (r.sp!=sp || r.bp!=bp)'),
    ('instruction_boundary','!gameBoundary(r.ip)','false'),
    ('timer_delivery_balance',
        '(cpu.timerDeliveries>cpu.timerInstructions && cpu.timerDeliveries-cpu.timerInstructions>(cpu.timer ? 1u : 0u))',
        'false'),
)

def run(cxx,out):
    out.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='run-',dir=out))
    protected=[*sorted((ROOT/'src/core').glob('*.*')),ROOT/'tests/core/transient_removal_test.cpp',
        *[ROOT/name for name in fixture.INPUTS],fixture.FIXTURE/'manifest.json',fixture.FIXTURE/'oracle.bin.gz']
    before={str(p):fixture.sha(p.read_bytes()) for p in protected}
    source=HEADER.read_text();raw=fixture.read_fixture();oracle=work/'oracle.bin';oracle.write_bytes(raw)
    environment=dict(os.environ,SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy',TMPDIR=str(work),TMP=str(work),TEMP=str(work))
    report=dict(status='failed',faults=[],positive_baseline=False,protected_sha256=before)
    def command(args,name):
        result=subprocess.run(list(map(str,args)),cwd=work,env=environment,capture_output=True,timeout=180)
        (work/(name+'.stdout')).write_bytes(result.stdout);(work/(name+'.stderr')).write_bytes(result.stderr)
        return result
    def build(name,text):
        overlay=work/name/'core';overlay.mkdir(parents=True);(overlay/'transient_removal.hpp').write_text(text)
        exe=work/name/'probe'
        result=command([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic','-pipe',
            '-I'+str(overlay.parent),'-I'+str(ROOT/'src'),ROOT/'tests/core/transient_removal_test.cpp','-o',exe],name+'-build')
        if result.returncode:
            raise ValueError('Mutation compilation failed: '+name+' '+result.stderr.decode(errors='replace')[-2000:])
        return exe
    try:
        baseline=build('baseline',source)
        for name,args in (('unit',[baseline]),('original',[baseline,oracle,ROOT])):
            result=command(args,'baseline-'+name)
            if result.returncode or b'transient_removal_'+name.encode()+b'=ok' not in result.stdout:
                raise ValueError('Authenticated positive baseline failed: '+name)
        report['positive_baseline']=True
        for name,old,new in FAULTS:
            if source.count(old)!=1:
                raise ValueError('Mutation anchor differs: '+name)
            exe=build(name,source.replace(old,new))
            result=command([exe],name+'-unit')
            mode='unit'
            if not result.returncode:
                result=command([exe,oracle,ROOT],name+'-original');mode='original'
            if not result.returncode or b'transient_removal_error=' not in result.stderr:
                raise ValueError('Mutation survived or failed outside the probe: '+name)
            report['faults'].append(dict(name=name,detected_by=mode))
            print('detected '+name+' '+mode,flush=True)
        if any(fixture.sha(Path(p).read_bytes())!=v for p,v in before.items()):
            raise ValueError('Mutation run changed protected inputs')
        report.update(status='passed',sources_preserved=True)
    finally:
        (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'transient_removal_mutations=ok faults={len(FAULTS)} positive_baseline=1 sources_preserved=1')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();run(args.cxx,args.out)
