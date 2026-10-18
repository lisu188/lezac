"""Require captured natural windows to reject isolated recovered-operation faults."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
FAULTS=(
    ('render_bypass','frame_active.hpp','state_.render=FrameRenderOperation(r,state_.foreground.pacing.gameSegment).snapshot();',
        'state_.render=FrameRenderOperation(r,state_.foreground.pacing.gameSegment).snapshot();state_.render->outcome=FrameRenderOutcome::Returned;'),
    ('irq_return_ip','frame_active.hpp','push(r.cs);push(r.ip);','push(r.cs);push(static_cast<uint16_t>(r.ip+1u));'),
    ('vga_destination','frame_render.hpp','r.ax=bus.readWord(r.ds,0x79f0);','r.ax=static_cast<uint16_t>(bus.readWord(r.ds,0x79f0)+1u);'))
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def check(cxx,cpu,clock,out):
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')):
        raise ValueError('Use RAM-only mutation outputs')
    out.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='active-live-mutations-',dir=out)).resolve()
    environment=dict(os.environ,TMPDIR=str(out),SDL_AUDIODRIVER='dummy',PYTHONDONTWRITEBYTECODE='1')
    sources={name:(ROOT/'src/core'/name).read_bytes() for name in {fault[1] for fault in FAULTS}}
    identities={name:hashlib.sha256(raw).hexdigest() for name,raw in sources.items()}
    report=dict(passed=False,cpu_sha256=sha(cpu),clock_sha256=sha(clock),controls=[],whole_game_parity=False)
    try:
        for name,header,old,new in (('baseline','','',''),*FAULTS):
            work=out/name;(work/'src/core').mkdir(parents=True)
            if header:
                source=sources[header].decode('utf-8')
                if source.count(old)!=1:
                    raise ValueError('Mutation anchor differs: '+name)
                (work/'src/core'/header).write_text(source.replace(old,new,1))
            exe=work/'replay'
            result=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I'+str(work/'src'),'-I'+str(ROOT/'src'),str(ROOT/'tests/core/frame_active_live_test.cpp'),'-o',str(exe)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120,env=environment)
            (work/'build.log').write_bytes(result.stdout)
            if result.returncode:
                raise ValueError('Mutation did not compile: '+name)
            result=subprocess.run([str(exe),str(cpu),str(clock)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,env=environment)
            (work/'replay.log').write_bytes(result.stdout)
            if result.returncode!=(0 if name=='baseline' else 1):
                raise ValueError('Natural mutation sensitivity differs: '+name)
            report['controls'].append(dict(name=name,exit_code=result.returncode,output=result.stdout.decode()))
        report['output_guards']=[]
        for kind in ('existing_ram','existing_palette','broken_symlink'):
            prefix=out/('guard-'+kind)
            ram=Path(str(prefix)+'-0.ram');palette=Path(str(prefix)+'-0.pal')
            missing=out/('must-not-create-'+kind)
            protected=palette if kind=='existing_palette' else ram
            if kind=='broken_symlink':
                ram.symlink_to(missing)
            else:
                protected.write_bytes(b'preserve owned evidence')
            result=subprocess.run([str(out/'baseline/replay'),str(cpu),str(clock),str(prefix)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,env=environment)
            (out/(kind+'.log')).write_bytes(result.stdout)
            if result.returncode!=1 or b'Active output already exists' not in result.stdout:
                raise ValueError('Output preservation guard differs: '+kind)
            if kind=='broken_symlink':
                if not ram.is_symlink() or missing.exists():
                    raise ValueError('Broken output symlink was followed')
            elif protected.read_bytes()!=b'preserve owned evidence':
                raise ValueError('Existing output was changed')
            if kind!='existing_palette' and palette.exists() or kind=='existing_palette' and ram.exists():
                raise ValueError('Rejected output created its companion')
            report['output_guards'].append(dict(kind=kind,preserved=True))
        if any(sha(ROOT/'src/core'/name)!=digest for name,digest in identities.items()):
            raise ValueError('Recovered operation source changed')
        report.update(passed=True,original_sources_preserved=True)
        print('active_live_mutations=ok faults=3 output_guards=3 original_sources_preserved=1')
    except BaseException as error:
        report['error']=repr(error)
        raise
    finally:
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    for name in ('cpu','clock','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();check(args.cxx,args.cpu,args.clock,args.out.resolve())
