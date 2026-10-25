"""Compile updater and ownership faults against the authenticated original corpus."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

import check_transient_update_fixture as fixture

ROOT=Path(__file__).resolve().parents[1]
FAULTS=(
    ('terminal_validation','transient_update.hpp','if (finished()) validate();','if (false) validate();'),
    ('spark_lifetime','transient_queue_instructions.hpp',
        'case 0x48f4:bus.writeByte(r.es,static_cast<uint16_t>(r.di+0x8u),static_cast<uint8_t>(increment(bus.readByte(r.es,static_cast<uint16_t>(r.di+0x8u)),true,true)))',
        'case 0x48f4:bus.writeByte(r.es,static_cast<uint16_t>(r.di+0x8u),static_cast<uint8_t>(increment(bus.readByte(r.es,static_cast<uint16_t>(r.di+0x8u)),false,true)))'),
    ('spark_motion','transient_queue_instructions.hpp',
        'case 0x4635:bus.writeByte(r.ds,static_cast<uint16_t>(0x78d2u),static_cast<uint8_t>((r.ax&255u)))',
        'case 0x4635:bus.writeByte(r.ds,static_cast<uint16_t>(0x78d2u),static_cast<uint8_t>(0))'),
    ('collision_velocity','transient_queue_instructions.hpp',
        'case 0x4795:r.ax=static_cast<uint16_t>((r.ax&0xff00u)|((bus.readByte(r.ds,static_cast<uint16_t>(0x661eu)))&255u))',
        'case 0x4795:r.ax=static_cast<uint16_t>((r.ax&0xff00u)|0u)'),
    ('debris_gravity','transient_queue_instructions.hpp',
        'arithmetic(bus.readByte(r.ds,static_cast<uint16_t>(0x78d4u)),0x4u,false,true,false)',
        'arithmetic(bus.readByte(r.ds,static_cast<uint16_t>(0x78d4u)),0x3u,false,true,false)'),
    ('signed_divide_fault','transient_queue_instructions.hpp',
        'if (!factor || value/factor < -32768 || value/factor > 32767) throw TransientQueueDivideFault();',
        'if (!factor || value/factor < -32768 || value/factor > 32767) {r.ax=0;r.dx=0;return;}'),
    ('foreground_sp','transient_update.hpp','r.sp!=stack(frame,*p)','false'),
    ('foreground_bp','transient_update.hpp','(p->bpKind!=2 && r.bp!=base(frame,*p))','false'),
    ('root_stack_anchor','transient_update.hpp','root.sp!=static_cast<uint16_t>(state_.callerSp-2u)','false'),
    ('counter_conservation','transient_update.hpp','state_.dispatchedInstructions!=instructions','false'),
    ('helper_balance','transient_update.hpp',
        'state_.helperCalls[i]-state_.helperReturns[i]!=(state_.helper && state_.helper->index()==i ? 1u : 0u)',
        'false'),
)

def run(cxx,out,corpus=fixture,faults=FAULTS,family='transient_update',
        test_source='tests/core/transient_update_test.cpp',unit=False,error_marker=b'transient_update_error='):
    out.mkdir(parents=True,exist_ok=True);work=Path(tempfile.mkdtemp(prefix='run-',dir=out))
    protected=[*sorted((ROOT/'src/core').glob('*.*')),ROOT/test_source,
        *[ROOT/name for name in corpus.INPUTS],corpus.FIXTURE/'manifest.json',corpus.FIXTURE/'oracle.bin.gz']
    before={str(p):fixture.sha(p.read_bytes()) for p in protected}
    headers={'transient_update.hpp','transient_queue_instructions.hpp'}|{row[1] for row in faults}
    source={name:(ROOT/'src/core'/name).read_text() for name in headers}
    oracle=work/'oracle.bin';oracle.write_bytes(corpus.read_fixture())
    environment=dict(os.environ,SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy',TMPDIR=str(work),TMP=str(work),TEMP=str(work))
    report=dict(status='failed',faults=[],positive_baseline=False,protected_sha256=before)
    def command(args,name):
        result=subprocess.run(list(map(str,args)),cwd=work,env=environment,capture_output=True,timeout=300)
        (work/(name+'.stdout')).write_bytes(result.stdout);(work/(name+'.stderr')).write_bytes(result.stderr)
        return result
    def build(name,changes):
        overlay=work/name/'core';overlay.mkdir(parents=True)
        for header,text in changes.items(): (overlay/header).write_text(text)
        exe=work/name/'probe'
        result=command([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic','-pipe',
            '-I'+str(overlay.parent),'-I'+str(ROOT/'src'),ROOT/test_source,'-o',exe],name+'-build')
        if result.returncode: raise ValueError('Updater mutation compilation failed: '+name+' '+result.stderr.decode(errors='replace')[-2000:])
        return exe
    try:
        baseline=build('baseline',source)
        if unit:
            result=command([baseline],'baseline-unit')
            if result.returncode or (family+'_unit=ok').encode() not in result.stdout:
                raise ValueError('Authenticated updater unit baseline failed')
        result=command([baseline,oracle,ROOT],'baseline-original')
        if result.returncode or (family+'_original=ok').encode() not in result.stdout: raise ValueError('Authenticated updater baseline failed')
        report['positive_baseline']=True
        for name,header,old,new in faults:
            if source[header].count(old)!=1: raise ValueError('Updater mutation anchor differs: '+name)
            changed=dict(source);changed[header]=source[header].replace(old,new)
            exe=build(name,changed);mode='original'
            result=command([exe],name+'-unit') if unit else None
            if result is not None and result.returncode:
                mode='unit'
            else:
                result=command([exe,oracle,ROOT],name+'-original')
            if not result.returncode or error_marker not in result.stderr:
                raise ValueError('Updater mutation survived or failed outside probe: '+name)
            report['faults'].append(dict(name=name,detected_by=mode));print('detected '+name,flush=True)
        if any(fixture.sha(Path(p).read_bytes())!=v for p,v in before.items()): raise ValueError('Updater mutations changed protected inputs')
        report.update(status='passed',sources_preserved=True)
    finally: (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{family}_mutations=ok faults={len(faults)} positive_baseline=1 sources_preserved=1')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();run(args.cxx,args.out)
