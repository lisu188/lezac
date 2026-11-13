"""Check both motion readers reject malformed corpora without changing binaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api',type=Path,required=True)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    args.out=Path(tempfile.mkdtemp(prefix='run-',dir=args.out))
    original=args.fixture.read_bytes()
    mutations={'empty':b'','truncated':original[:-1],'trailing':original+b'\0'}
    for name,offset in (('header',0),('input',100),('output',650),('last',len(original)-1)):
        raw=bytearray(original)
        raw[offset]^=1
        mutations[name]=bytes(raw)
    environment=dict(os.environ,SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy')
    binaries={path:sha(path) for path in (args.api,args.app)}
    results=[]
    for label,exe,command,success in (('api',args.api,[],'nonplayer_motion_original=ok'),
            ('app',args.app,['--debug-nonplayer-motion-original'],'nonplayer_motion_app=ok')):
        run=subprocess.run([str(exe),*command,str(args.fixture)],cwd=ROOT,env=environment,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        (args.out/(label+'-positive.log')).write_bytes(run.stdout)
        if run.returncode or success.encode() not in run.stdout:
            raise ValueError('Positive motion CLI failed: '+label)
        for name,raw in mutations.items():
            path=args.out/(name+'.bin')
            path.write_bytes(raw)
            run=subprocess.run([str(exe),*command,str(path)],cwd=ROOT,env=environment,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            (args.out/(label+'-'+name+'.log')).write_bytes(run.stdout)
            if run.returncode==0 or success.encode() in run.stdout:
                raise ValueError('Malformed motion CLI was accepted: '+label+' '+name)
            results.append(dict(executable=label,mutation=name,exit_code=run.returncode))
    if any(sha(path)!=digest for path,digest in binaries.items()):
        raise ValueError('Motion CLI changed a binary')
    (args.out/'report.json').write_text(json.dumps(dict(status='passed',results=results),indent=2)+'\n')
    print('nonplayer_motion_cli=ok malformed=7 executables=2 binaries_preserved=1')


if __name__=='__main__':
    main()
