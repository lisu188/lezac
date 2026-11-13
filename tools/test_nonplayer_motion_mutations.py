"""Compile boundary faults and require the original corpus to reject each."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
FAULTS=(
    ('tick','input.tick>>','(input.tick+1u)>>'),
    ('rng','auto randomSeed=input.randomSeed;','auto randomSeed=input.randomSeed^1u;'),
    ('dx','static_cast<uint16_t>(input.dx)','static_cast<uint16_t>(input.dx+1)'),
    ('velocity','static_cast<uint16_t>(input.vx8)','static_cast<uint16_t>(input.vx8+1)'),
    ('tile','input.tiles[offset-0x2054u]','input.tiles[(offset-0x2054u+1u)%4u]'),
    ('animation','animationBytes[offset-0x58u]','animationBytes[(offset-0x58u+1u)%512u]'),
    ('scratch','auto shared=input.shared;','auto shared=input.shared;shared[1]^=1;'),
    ('fault','outcome=ActorMotionPrefixOutcome::DivideError','outcome=ActorMotionPrefixOutcome::Terrain'),
    ('terrain','operation.registers().ip==0x732c','operation.registers().ip==0x732e'),
)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    args.out=Path(tempfile.mkdtemp(prefix='run-',dir=args.out))
    source=ROOT/'src/core/actor_motion_prefix.cpp'
    original=source.read_bytes()
    environment=dict(os.environ,SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy')
    results=[]
    for name,before,after in FAULTS:
        text=original.decode()
        if text.count(before)!=1:
            raise ValueError('Motion fault anchor differs: '+name)
        altered=args.out/(name+'.cpp')
        altered.write_text(text.replace(before,after),encoding='utf-8')
        exe=args.out/name
        build=subprocess.run([args.cxx,'-std=c++23','-O1','-Wall','-Wextra','-Werror','-pedantic',
            '-I'+str(ROOT/'src'),str(ROOT/'tests/core/actor_motion_prefix_test.cpp'),
            str(altered),'-o',str(exe)],env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        (args.out/(name+'-build.log')).write_bytes(build.stdout)
        if build.returncode:
            raise ValueError('Motion mutant did not compile: '+name)
        run=subprocess.run([str(exe),str(args.fixture)],env=environment,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        (args.out/(name+'-run.log')).write_bytes(run.stdout)
        if run.returncode==0 or b'nonplayer_motion=failed' not in run.stdout:
            raise ValueError('Motion fault was not rejected: '+name)
        results.append(dict(fault=name,exit_code=run.returncode))
        if source.read_bytes()!=original:
            raise ValueError('Production motion source changed')
    (args.out/'report.json').write_text(json.dumps(dict(status='passed',results=results,
        original_sha256=hashlib.sha256(original).hexdigest()),indent=2)+'\n')
    print('nonplayer_motion_mutations=ok faults=9 sources_preserved=1')


if __name__=='__main__':
    main()
