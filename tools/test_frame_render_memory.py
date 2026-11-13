"""Check complete C++ memory dumps against original SHA256, not only fingerprints."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from check_frame_render_fixture import ROOT,FIXTURE,run


def check(exe,out):
    out.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='render-memory-',dir=out)).resolve()
    report=dict(passed=False,full_frame_claim=False)
    try:
        corpus=work/'oracle.bin'
        run(ROOT,FIXTURE,corpus,work/'fixture-report.json')
        result=subprocess.run([str(exe.resolve()),str(corpus),str(ROOT),str(work/'dumps')],
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        (work/'replay.log').write_bytes(result.stdout)
        if result.returncode:
            raise ValueError('Render replay failed: '+result.stdout.decode(errors='replace'))
        manifest=json.loads((FIXTURE/'manifest.json').read_bytes())
        expected_names=set()
        for case in manifest['cases']:
            for phase in ('initial','final'):
                name=str(case['index'])+'-'+phase+'.ram'
                expected_names.add(name)
                raw=(work/'dumps'/name).read_bytes()
                if len(raw)!=1048576 or hashlib.sha256(raw).hexdigest()!=case[phase+'_memory_sha256']:
                    raise ValueError('Complete original/C++ memory differs: '+name)
        if {path.name for path in (work/'dumps').iterdir()}!=expected_names:
            raise ValueError('Render memory dump set differs')
        report.update(passed=True,cases=len(manifest['cases']),full_memory_bytes=26*2*1048576,
            comparison='original SHA256 of each complete initial and final memory image')
        print('frame_render_memory=ok cases=26 images=52 bytes=54525952 full_frame_claim=0')
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    check(args.exe,args.out)
