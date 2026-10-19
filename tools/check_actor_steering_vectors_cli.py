"""Check real typed/App consumers and reject modified derived fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from export_actor_steering_vectors import VECTORS_SHA


def run(api,app,vectors,out):
    raw=vectors.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=VECTORS_SHA:
        raise ValueError('Canonical vector CLI input differs')
    out=out/str(time.time_ns());out.mkdir(parents=True)
    programs=[('api',api)]
    if app:
        programs.append(('app',app))
    before={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in programs}
    report=dict(status='failed',fixture_sha256=VECTORS_SHA,binary_sha256=before,actual_App_invoked=bool(app),checks=[])
    env=dict(os.environ,SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy',
        LEZAC_LOAD_ORIGINAL_ASSETS='1',LEZAC_LOAD_JSON_ASSETS='0',PYTHONDONTWRITEBYTECODE='1')
    def changed(offset):
        copy=bytearray(raw);copy[offset]^=1;return bytes(copy)
    variants=(('baseline',raw),('truncated',raw[:-1]),('appended',raw+b'\0'),('magic',changed(0)),
        ('parent',changed(12)),('component',changed(48)),('expected',changed(54)),('count',changed(8)))
    try:
        for label,data in variants:
            path=out/(label+'.bin');path.write_bytes(data)
            for name,program in programs:
                args=[str(program.resolve())]
                if name=='app': args.append('--debug-actor-steering-vectors')
                args.append(str(path.resolve()))
                result=subprocess.run(args,cwd=Path(__file__).resolve().parents[1],env=env,
                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
                (out/(name+'-'+label+'.log')).write_bytes(result.stdout)
                if label=='baseline':
                    expected=b'actor_steering_app_original=ok cases=2136 homing_calls=2097' if name=='app' else b'actor_steering_vector_original=ok cases=2136'
                    if result.returncode!=0 or expected not in result.stdout:
                        raise ValueError('Original steering CLI baseline failed: '+name)
                elif result.returncode!=1 or b'Steering vector fixture' not in result.stdout:
                    raise ValueError('Changed steering CLI fixture was not rejected: '+name+'/'+label)
                report['checks'].append(dict(program=name,case=label,returncode=result.returncode))
        report['status']='passed'
    except Exception as error:
        report['error']=str(error);raise
    finally:
        report['binaries_preserved']=before=={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in programs}
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['binaries_preserved']:
        raise ValueError('Steering CLI binary changed during checks')
    print('actor_steering_vectors_cli=ok original_cases=2136 admitted=2097 malformed=7 executables='+
        str(len(programs))+' binaries_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--api',required=True,type=Path)
    parser.add_argument('--app',type=Path);parser.add_argument('--vectors',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();run(args.api,args.app,args.vectors,args.out)
