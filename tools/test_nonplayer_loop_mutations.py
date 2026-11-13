"""Compile caller, lifetime, handoff and IRQ faults against the original loop."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
CALLER='src/core/frame_actor_entry.hpp'
LOOP='src/core/nonplayer_loop.hpp'
FAULTS=(
    ('caller_step',CALLER,'case 0x7ee4:increment(0x2082,false);',
        'case 0x7ee4:increment(0x2082,false);increment(0x2082,false);'),
    ('caller_backedge',CALLER,'case 0x7ee8:r.ip=0x7ecb;','case 0x7ee8:r.ip=0x7ec5;'),
    ('precontact',LOOP,'return ActorPrecontactOperation(r,game,id).snapshot();',
        'return ActorContactOperation(r,game,id).snapshot();'),
    ('fresh_y',LOOP,'++state_.actorCalls;',
        '{ ++state_.actorCalls;bus.writeWord(before.ss,static_cast<uint16_t>(before.sp-8u),0); }'),
    ('terminal',LOOP,'if (!active.interruptInProgress() && r.cs==game && r.ip==0x7eea)',
        'if (!active.interruptInProgress() && r.cs==game && r.ip==0x7ecb)'),
    ('returns',LOOP,'++state_.actorReturns;','state_.actorReturns+=2;'),
    ('irq_delivery',LOOP,'++state_.timerDeliveries;','state_.timerDeliveries+=0;'),
    ('irq_work',LOOP,'if (timer) ++state_.timerInstructions;','if (timer) state_.timerInstructions+=0;'),
    ('player_handoff',LOOP,'state_.outcome=NonplayerLoopOutcome::PlayerMotion;',
        'state_.outcome=NonplayerLoopOutcome::RuntimeError;'),
)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='run-',dir=args.out))
    originals={name:(ROOT/name).read_bytes() for name in (CALLER,LOOP)}
    environment=dict(os.environ,SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy')
    results=[]
    for name,relative,before,after in FAULTS:
        text=originals[relative].decode()
        if text.count(before)!=1:
            raise ValueError('Loop mutation anchor differs: '+name)
        stage=out/name
        altered=stage/relative
        altered.parent.mkdir(parents=True)
        altered.write_text(text.replace(before,after),encoding='utf-8')
        exe=stage/'probe'
        build=subprocess.run([args.cxx,'-std=c++23','-O1','-Wall','-Wextra','-Werror','-pedantic',
            '-I'+str(stage/'src'),'-I'+str(ROOT/'src'),str(ROOT/'tests/core/nonplayer_loop_test.cpp'),
            '-o',str(exe)],env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        (stage/'build.log').write_bytes(build.stdout)
        if build.returncode:
            raise ValueError('Loop mutant did not compile: '+name)
        rejected=False
        for label,arguments in (('unit',[]),('original',[str(args.fixture),str(ROOT)])):
            run=subprocess.run([str(exe),*arguments],env=environment,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            (stage/(label+'.log')).write_bytes(run.stdout)
            if run.returncode:
                if b'nonplayer_loop=failed' not in run.stdout:
                    raise ValueError('Loop mutant failed outside assertions: '+name)
                rejected=True
                results.append(dict(fault=name,rejected_by=label,exit_code=run.returncode))
                break
        if not rejected:
            raise ValueError('Loop fault escaped: '+name)
        if any((ROOT/path).read_bytes()!=raw for path,raw in originals.items()):
            raise ValueError('Loop production source changed')
    (out/'report.json').write_text(json.dumps(dict(status='passed',results=results,
        sources={name:hashlib.sha256(raw).hexdigest() for name,raw in originals.items()}),indent=2)+'\n')
    print('nonplayer_loop_mutations=ok faults=9 sources_preserved=1')


if __name__=='__main__':
    main()
