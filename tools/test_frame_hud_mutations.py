"""Retain isolated HUD/REP faults and check independent original-backed detection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
MUTATIONS={
    'scratch_alias': ('frame_hud.hpp','case 0x3163:bus.writeWord(r.ds,0x2074,r.ax);','case 0x3163:bus.writeWord(r.ds,0x2076,r.ax);'),
    'pixel_row_stride': ('frame_hud.hpp','arithmetic(r.di,0x138,false)','arithmetic(r.di,0x139,false)'),
    'palette_capacity': ('frame_hud.hpp','arithmetic(bus.readByte(r.ss,stackOffset(-9)),3,true,8)','arithmetic(bus.readByte(r.ss,stackOffset(-9)),4,true,8)'),
    'completion_flag': ('frame_hud.hpp','case 0x31e1:bus.writeByte(r.ds,0x79c5,1);','case 0x31e1:bus.writeByte(r.ds,0x79c5,0);'),
    'word_copy_width': ('frame_hud.hpp','bus.writeWord(r.es,r.di,bus.readWord(r.ds,r.si))','bus.writeWord(r.es,r.di,bus.readByte(r.ds,r.si))'),
    'near_return_cleanup': ('frame_hud.hpp','r.sp=static_cast<uint16_t>(r.sp+2u);if(state_.hudOnly)','r.sp=static_cast<uint16_t>(r.sp+0u);if(state_.hudOnly)'),
    'shift_adjust_flag': ('frame_hud.hpp','|flags(result,16)|0x10u|','|flags(result,16)|0u|'),
    'rep_decode_credit': ('pic_work_clock.hpp','state_.cycles = available - requested;','state_.cycles = available - requested - 1;'),
}


def run(out):
    out=out.resolve();assert out.is_relative_to(Path('/dev/shm')) and not out.exists();out.mkdir()
    environment=dict(os.environ,TMPDIR='/dev/shm',PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run(['python3','-S','-B',str(ROOT/'tools/check_frame_hud_fixture.py'),
        '--cpu',str(out/'cpu.bin'),'--clock',str(out/'clock.bin'),'--oracle',str(out/'oracle.bin')],
        capture_output=True,env=environment,timeout=60);(out/'fixture.log').write_bytes(result.stdout+result.stderr);result.check_returncode()
    sources={name:(ROOT/'src/core'/name).read_bytes() for name in ('frame_hud.hpp','pic_work_clock.hpp')}
    test=ROOT/'tests/core/frame_hud_test.cpp';testHash=hashlib.sha256(test.read_bytes()).hexdigest()
    report=dict(source_hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in sources.items()},test_sha256=testHash,
        cases=[],detected=0,equivalent=0)
    for name,mutation in [('baseline',None),*MUTATIONS.items()]:
        folder=out/name;(folder/'core').mkdir(parents=True)
        for path,raw in sources.items():
            text=raw.decode()
            if mutation and path==mutation[0]:
                assert text.count(mutation[1])==1;text=text.replace(mutation[1],mutation[2])
            (folder/'core'/path).write_text(text)
        exe=folder/'hud';built=subprocess.run(['g++','-std=c++23','-O2','-Wall','-Wextra','-Werror','-I',str(folder),
            '-I',str(ROOT/'src'),str(ROOT/'tests/core/frame_hud_test.cpp'),'-o',str(exe)],capture_output=True,env=environment,timeout=180)
        (folder/'build.log').write_bytes(built.stdout+built.stderr);built.check_returncode();failures=[]
        for index,args in enumerate([[],['--original',str(out/'cpu.bin'),str(out/'clock.bin')],['--oracle',str(out/'oracle.bin')]]):
            checked=subprocess.run([str(exe),*args],capture_output=True,env=environment,timeout=60)
            (folder/('probe-'+str(index)+'.log')).write_bytes(checked.stdout+checked.stderr)
            if checked.returncode:
                failures.append(dict(probe=args,exit=checked.returncode))
        assert mutation or not failures
        if mutation:
            report['detected' if failures else 'equivalent']+=1
        report['cases'].append(dict(name=name,failures=failures));(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(name=name,rejected=bool(failures))),flush=True)
    assert all((ROOT/'src/core'/name).read_bytes()==raw for name,raw in sources.items())
    assert hashlib.sha256(test.read_bytes()).hexdigest()==testHash
    assert report['detected']==len(MUTATIONS),'Surviving fault retained for inspection'
    print('frame_hud_mutations=ok detected=8 baseline_probes=3',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
