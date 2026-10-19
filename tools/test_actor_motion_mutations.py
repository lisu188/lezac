"""Detect compiled movement/terrain faults without changing authenticated sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def run(cxx,fixture,out):
    out=out/str(time.time_ns());out.mkdir(parents=True)
    names=('actor_motion.hpp','actor_terrain.hpp')
    headers={name:(ROOT/'src/core'/name).read_bytes() for name in names}
    test=ROOT/'tests/core/actor_motion_test.cpp';test_bytes=test.read_bytes()
    faults=(
        ('helper_return_precedence','actor_motion.hpp',
            'else if (r.cs==state_.cpu.gameSegment && r.ip==0x73e5)',
            'if (r.cs==state_.cpu.gameSegment && r.ip==0x73e5)'),
        ('gravity','actor_motion.hpp','case 0x7028:store(-14,arithmetic(local(-14),64));',
            'case 0x7028:store(-14,arithmetic(local(-14),63));'),
        ('period_remainder','actor_motion.hpp','case 0x70e3:branch(!flag(0x40),','case 0x70e3:branch(flag(0x40),'),
        ('target_distance_signed_high','actor_motion.hpp','case 0x7105:branch(less(),','case 0x7105:branch(!less(),'),
        ('wandering_rng_entry','actor_motion.hpp','case 0x7131:farCall(0x13a8,','case 0x7131:farCall(0x13a9,'),
        ('facing_table_byte','actor_motion.hpp','case 0x72ac:al(data(static_cast<uint16_t>(r.di+0x58u)));',
            'case 0x72ac:al(data(static_cast<uint16_t>(r.di+0x59u)));'),
        ('reflection_divisor','actor_motion.hpp','case 0x73cf:r.cx=2;','case 0x73cf:r.cx=3;'),
        ('negative_reflection_position','actor_motion.hpp','case 0x73dd:store(-44,increment(local(-44),true));',
            'case 0x73dd:store(-44,increment(local(-44)));'),
        ('tile_queue_cap','actor_terrain.hpp','arithmetic(dw(0x207e),1600,true)','arithmetic(dw(0x207e),1599,true)'),
        ('rectangle_cap','actor_terrain.hpp','arithmetic(dw(0x2080),250,true)','arithmetic(dw(0x2080),249,true)'),
        ('rectangle_stride','actor_terrain.hpp','case 0x3a3d:r.di=imul(dw(0x2080),15);',
            'case 0x3a3d:r.di=imul(dw(0x2080),14);'),
        ('damage_tile_limit','actor_terrain.hpp','case 0x5b26:arithmetic(r.ax&255u,115,true,true);',
            'case 0x5b26:arithmetic(r.ax&255u,114,true,true);'),
        ('damage_amount_table','actor_terrain.hpp','case 0x5b37:r.ax=dw(static_cast<uint16_t>(r.bx+0x1au));',
            'case 0x5b37:r.ax=dw(static_cast<uint16_t>(r.bx+2u));'),
        ('above_cell_marker','actor_terrain.hpp','case 0x5b5b:branch(flag(0x40),','case 0x5b5b:branch(!flag(0x40),'),
        ('friction_zero_threshold','actor_terrain.hpp','case 0x5b9c:arithmetic(r.ax,43,true);',
            'case 0x5b9c:arithmetic(r.ax,42,true);'),
        ('friction_step','actor_terrain.hpp','arithmetic(bus.readWord(r.ss,static_cast<uint16_t>(r.di-12u)),42));',
            'arithmetic(bus.readWord(r.ss,static_cast<uint16_t>(r.di-12u)),41));'),
        ('irq_accounting','actor_motion.hpp',
            'ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();',
            'ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();++state_.cpu.timerDeliveries;'))
    report=dict(status='failed',source_sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in headers.items()},
        instruction_grants=[1],full_grant_matrix_in_separate_original_test=True,faults=[])
    try:
        for fault,changed,before,after in (('baseline','','',''),*faults):
            variant=out/fault;(variant/'core').mkdir(parents=True)
            for name,source in headers.items():
                text=source.decode('ascii')
                if name==changed:
                    if text.count(before)!=1:
                        raise ValueError('Motion mutation location differs: '+fault)
                    text=text.replace(before,after)
                (variant/'core'/name).write_text(text,encoding='ascii')
            exe=variant/'test'
            built=subprocess.run([cxx,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-pedantic',
                '-I',str(variant),'-I',str(ROOT/'src'),str(test),'-o',str(exe)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            (variant/'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Motion mutation did not compile: '+fault)
            unit=subprocess.run([str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
            (variant/'unit.log').write_bytes(unit.stdout)
            if fault=='baseline':
                if unit.returncode or b'helper_return_boundaries=6 behavior_handoff_control=1' not in unit.stdout:
                    raise ValueError('Motion mutation unit baseline failed')
            elif unit.returncode:
                if unit.returncode!=1 or b'actor_motion=failed' not in unit.stdout:
                    raise ValueError('Motion mutation unit did not reach a regression assertion: '+fault)
                report['faults'].append(dict(name=fault,unit_output=unit.stdout.decode(),replay_skipped_after_unit_failure=True))
                continue
            checked=subprocess.run([str(exe),str(fixture),str(ROOT),'--one-grant'],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            (variant/'replay.log').write_bytes(checked.stdout)
            if fault=='baseline':
                if checked.returncode!=0 or b'actor_motion_original=ok cases=78927 replays=78927' not in checked.stdout or b'one_grant=1' not in checked.stdout:
                    raise ValueError('Motion mutation baseline failed')
            elif checked.returncode!=1 or b'actor_motion=failed' not in checked.stdout:
                raise ValueError('Motion compiled fault was not detected: '+fault)
            else:
                report['faults'].append(dict(name=fault,output=checked.stdout.decode()))
        report['status']='passed'
    except Exception as error:
        report['error']=str(error);raise
    finally:
        report['sources_preserved']=test.read_bytes()==test_bytes and all(
            (ROOT/'src/core'/name).read_bytes()==raw for name,raw in headers.items())
        (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if not report['sources_preserved']:
        raise ValueError('Motion mutation changed original sources')
    print('actor_motion_mutations=ok faults='+str(len(faults))+' sources_preserved=1 report='+str(out/'report.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx',required=True);parser.add_argument('--fixture',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path);args=parser.parse_args();run(args.cxx,args.fixture,args.out)
