"""Show which interrupt/glyph faults the earlier natural foreground corpus misses."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MUTATIONS={
 'irq_eligibility_disabled':('pic_work_clock.hpp','if ((flags & 0x200u) && state_.pending) {','if (false && (flags & 0x200u) && state_.pending) {'),
 'irq_snapshot_not_committed':('frame_foreground.hpp','FramePacingOperation operation(state_.pacing);operation.deliverTimerInterrupt(bus);state_.pacing=operation.snapshot();',
  'FramePacingOperation operation(state_.pacing);operation.deliverTimerInterrupt(bus);'),
 'hud_copy_width':('frame_hud.hpp','bus.writeWord(r.es,r.di,bus.readWord(r.ds,r.si))','bus.writeWord(r.es,r.di,bus.readByte(r.ds,r.si))'),
 'hud_scratch_alias':('frame_hud.hpp','case 0x3163:bus.writeWord(r.ds,0x2074,r.ax);','case 0x3163:bus.writeWord(r.ds,0x2076,r.ax);'),
}
def run(out,previous,current):
 out=out.resolve();assert out.is_relative_to(Path('/dev/shm')) and not out.exists() and shutil.disk_usage('/dev/shm').free>256*1024**2
 out.mkdir();sha=lambda raw:hashlib.sha256(raw).hexdigest();env=dict(os.environ,TMPDIR='/dev/shm',SDL_AUDIODRIVER='dummy',PYTHONDONTWRITEBYTECODE='1')
 for folder,fixture in [(previous,'frame_foreground'),(current,'foreground_live')]:
  manifest=json.loads((ROOT/'tests/fixtures'/fixture/'manifest.json').read_bytes())
  assert sha((folder/'cpu.bin').read_bytes())==manifest['cpu_sha256'] and sha((folder/'clock.bin').read_bytes())==manifest['clock_sha256']
 sources={name:(ROOT/'src/core'/name).read_bytes() for name in ('frame_foreground.hpp','frame_hud.hpp','pic_work_clock.hpp')}
 test=ROOT/'tests/core/frame_foreground_test.cpp';test_hash=sha(test.read_bytes())
 report=dict(source_hashes={name:sha(raw) for name,raw in sources.items()},test_sha256=test_hash,cases=[],detected=0,previous_corpus_survivors=0)
 for name,mutation in [('baseline',None),*MUTATIONS.items()]:
  folder=out/name;(folder/'core').mkdir(parents=True)
  for path,raw in sources.items():
   text=raw.decode()
   if mutation and path==mutation[0]:assert text.count(mutation[1])==1;text=text.replace(mutation[1],mutation[2])
   (folder/'core'/path).write_text(text)
  exe=folder/'foreground';built=subprocess.run(['g++','-std=c++23','-O2','-Wall','-Wextra','-Werror','-I',str(folder),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],
   capture_output=True,env=env,timeout=120);(folder/'build.log').write_bytes(built.stdout+built.stderr);built.check_returncode()
  codes=[]
  for label,args in [('previous',[str(previous/'cpu.bin'),str(previous/'clock.bin')]),('live',['--live',str(current/'cpu.bin'),str(current/'clock.bin')])]:
   result=subprocess.run([str(exe),*args],capture_output=True,env=env,timeout=120)
   (folder/(label+'.log')).write_bytes(result.stdout+result.stderr);codes.append(result.returncode)
  assert codes[0]==0,'Previous natural foreground fixture unexpectedly rejected a new isolated fault'
  if mutation:
   assert codes[1]!=0,'New natural foreground coverage missed a fault'
   report['detected']+=1;report['previous_corpus_survivors']+=1
  else:assert codes[1]==0
  report['cases'].append(dict(name=name,previous_exit=codes[0],live_exit=codes[1]));(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps(report['cases'][-1]),flush=True)
 assert all((ROOT/'src/core'/name).read_bytes()==raw for name,raw in sources.items()) and sha(test.read_bytes())==test_hash
 print('foreground_live_mutations=ok new_faults_detected=4 previous_natural_survivors=4 baseline_probes=2',flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('out','previous','current'):parser.add_argument('--'+name,type=Path,required=True)
 args=parser.parse_args();run(args.out,args.previous,args.current)
