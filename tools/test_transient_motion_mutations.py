"""Compile motion faults against the authenticated exhaustive original corpus."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

import check_transient_motion_fixture as fixture

ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/core/transient_motion.hpp'
FAULTS=(
    ('horizontal_sign','r.ip=!less() ? 0x3eeb : 0x3ee8','r.ip=less() ? 0x3eeb : 0x3ee8'),
    ('horizontal_step','case 0x3ee1:r.bx=1;','case 0x3ee1:r.bx=2;'),
    ('horizontal_overflow','r.ip=!flag(0x800) ? 0x3efc : 0x3eef','r.ip=true ? 0x3efc : 0x3eef'),
    ('phase_correction','arithmetic(r.ax>>8,128,true,true)','arithmetic(r.ax>>8,127,true,true)'),
    ('vertical_width','r.bx=bus.readWord(r.ds,0xc204);','r.bx=1;'),
    ('vertical_negation','r.bx=arithmetic(0,r.bx,true);','(void)r.bx;'),
    ('vertical_overflow','r.ip=!flag(0x800) ? 0x3f22 : 0x3f15','r.ip=true ? 0x3f22 : 0x3f15'),
    ('vertical_phase_write','bus.writeByte(r.ds,0x78d5,','bus.writeByte(r.ds,0x78d4,'),
    ('half_register_preservation','(r.ax&0xff00u)|value','uint16_t{value}'),
    ('caller_sp','r.sp!=(finished() ? state_.callerSp : static_cast<uint16_t>(state_.callerSp-2u))','false'),
    ('instruction_boundary','!boundary(r.ip)','false'),
    ('timer_delivery_balance',
        '(cpu.timerDeliveries>cpu.timerInstructions && cpu.timerDeliveries-cpu.timerInstructions>(cpu.timer ? 1u : 0u))','false'),
    ('auxiliary_flags','|((a^b^value)&16u)','|0u'),
    ('foreign_copy_history','cpu.transferredBytes ||','false ||'),
)

def run(cxx,out):
    out.mkdir(parents=True,exist_ok=True);work=Path(tempfile.mkdtemp(prefix='run-',dir=out))
    protected=[*sorted((ROOT/'src/core').glob('*.*')),ROOT/'tests/core/transient_motion_test.cpp',
        *[ROOT/name for name in fixture.INPUTS],fixture.FIXTURE/'manifest.json',fixture.FIXTURE/'oracle.bin.gz']
    before={str(p):fixture.sha(p.read_bytes()) for p in protected}
    source=HEADER.read_text();oracle=work/'oracle.bin';oracle.write_bytes(fixture.read_fixture())
    environment=dict(os.environ,SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy',TMPDIR=str(work),TMP=str(work),TEMP=str(work))
    report=dict(status='failed',faults=[],positive_baseline=False,protected_sha256=before)
    def command(args,name):
        result=subprocess.run(list(map(str,args)),cwd=work,env=environment,capture_output=True,timeout=300)
        (work/(name+'.stdout')).write_bytes(result.stdout);(work/(name+'.stderr')).write_bytes(result.stderr)
        return result
    def build(name,text):
        overlay=work/name/'core';overlay.mkdir(parents=True);(overlay/'transient_motion.hpp').write_text(text)
        exe=work/name/'probe'
        result=command([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic','-pipe',
            '-I'+str(overlay.parent),'-I'+str(ROOT/'src'),ROOT/'tests/core/transient_motion_test.cpp','-o',exe],name+'-build')
        if result.returncode:
            raise ValueError('Motion mutation compilation failed: '+name+' '+result.stderr.decode(errors='replace')[-2000:])
        return exe
    try:
        baseline=build('baseline',source)
        for name,args in (('unit',[baseline]),('original',[baseline,oracle,ROOT])):
            result=command(args,'baseline-'+name)
            if result.returncode or b'transient_motion_'+name.encode()+b'=ok' not in result.stdout:
                raise ValueError('Authenticated motion baseline failed: '+name)
        report['positive_baseline']=True
        for name,old,new in FAULTS:
            if source.count(old)!=1:
                raise ValueError('Motion mutation anchor differs: '+name)
            exe=build(name,source.replace(old,new));result=command([exe],name+'-unit');mode='unit'
            if not result.returncode:
                result=command([exe,oracle,ROOT],name+'-original');mode='original'
            if not result.returncode or b'transient_motion_error=' not in result.stderr:
                raise ValueError('Motion mutation survived or failed outside probe: '+name)
            report['faults'].append(dict(name=name,detected_by=mode));print('detected '+name+' '+mode,flush=True)
        if any(fixture.sha(Path(p).read_bytes())!=v for p,v in before.items()):
            raise ValueError('Motion mutations changed protected inputs')
        report.update(status='passed',sources_preserved=True)
    finally:
        (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'transient_motion_mutations=ok faults={len(FAULTS)} positive_baseline=1 sources_preserved=1')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();run(args.cxx,args.out)
