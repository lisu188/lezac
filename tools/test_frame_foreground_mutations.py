"""Retain isolated foreground/palette faults and require original-backed detection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
MUTATIONS={
 'dirty_modified_not_cleared':('pacing_device_clock.hpp','p.modified.fill(0);d[16]=0;','d[16]=0;'),
 'dirty_flag_not_cleared':('pacing_device_clock.hpp','p.modified.fill(0);d[16]=0;','p.modified.fill(0);'),
 'single_entry_skipped':('pacing_device_clock.hpp','if(p.first>p.last) return;','if(p.first>=p.last) return;'),
 'lut_not_written':('pacing_device_clock.hpp','p.lut[i]=value;p.modified[i]=1;','p.modified[i]=1;'),
 'opaque_alpha_lost':('pacing_device_clock.hpp','|p.format[5];','|0u;'),
 'clear_cache_not_cleared':('pacing_device_clock.hpp','d[15]=0; d[12] = 1;','d[12] = 1;'),
 'handoff_work_duplicated':('frame_foreground.hpp','++consumed;++state_.dispatchedInstructions;','++consumed;state_.dispatchedInstructions+=2;'),
 'keyboard_dos_base_conflated':('frame_foreground.hpp','FrameHudOperation(r,state_.keyboardBase,','FrameHudOperation(r,state_.pacing.callbackBase,'),
}

def run(out,corpus):
 out=out.resolve();assert out.is_relative_to(Path('/dev/shm')) and not out.exists() and shutil.disk_usage('/dev/shm').free>256*1024**2
 out.mkdir();env=dict(os.environ,TMPDIR='/dev/shm',PYTHONDONTWRITEBYTECODE='1',SDL_AUDIODRIVER='dummy')
 check=subprocess.run(['python3','-S','-B',str(ROOT/'tools/check_frame_foreground_fixture.py')],capture_output=True,env=env,timeout=60)
 (out/'fixture.log').write_bytes(check.stdout+check.stderr);check.check_returncode()
 manifest=json.loads((ROOT/'tests/fixtures/frame_foreground/manifest.json').read_bytes());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 cpu=corpus/'frame-foreground-cpu.bin';clock=corpus/'frame-foreground-clock.bin';palette=corpus/'frame-foreground-palette.bin'
 assert sha(cpu)==manifest['cpu_sha256'] and sha(clock)==manifest['clock_sha256']
 origin=json.loads((ROOT/'tests/fixtures/frame_foreground/palette-origin.json').read_bytes());assert sha(palette)==origin['oracle_sha256']
 sources={name:(ROOT/'src/core'/name).read_bytes() for name in ('frame_foreground.hpp','pacing_device_clock.hpp')}
 report=dict(source_hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in sources.items()},cases=[],detected=0)
 for name,mutation in [('baseline',None),*MUTATIONS.items()]:
  folder=out/name;(folder/'core').mkdir(parents=True)
  for path,raw in sources.items():
   text=raw.decode()
   if mutation and path==mutation[0]:assert text.count(mutation[1])==1;text=text.replace(mutation[1],mutation[2])
   (folder/'core'/path).write_text(text)
  exe=folder/'foreground';built=subprocess.run(['g++','-std=c++23','-O2','-Wall','-Wextra','-Werror','-I',str(folder),
   '-I',str(ROOT/'src'),str(ROOT/'tests/core/frame_foreground_test.cpp'),'-o',str(exe)],capture_output=True,env=env,timeout=120)
  (folder/'build.log').write_bytes(built.stdout+built.stderr);built.check_returncode();failures=[]
  for index,args in enumerate([['--palette-oracle',str(palette)],[str(cpu),str(clock)]]):
   checked=subprocess.run([str(exe),*args],capture_output=True,env=env,timeout=120)
   (folder/('probe-'+str(index)+'.log')).write_bytes(checked.stdout+checked.stderr)
   if checked.returncode:failures.append(dict(probe=args,exit=checked.returncode))
  assert mutation or not failures
  if mutation and failures:report['detected']+=1
  report['cases'].append(dict(name=name,failures=failures));(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps(dict(name=name,rejected=bool(failures))),flush=True)
 assert all((ROOT/'src/core'/name).read_bytes()==raw for name,raw in sources.items())
 assert report['detected']==len(MUTATIONS),'Surviving fault retained for inspection'
 print('frame_foreground_mutations=ok detected=8 baseline_probes=2',flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--corpus',type=Path,required=True)
 args=parser.parse_args();run(args.out,args.corpus)
