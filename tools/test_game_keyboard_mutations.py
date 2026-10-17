"""Retain isolated game-drain faults and verify original-backed detection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
MUTATIONS={
    'skip_caller_or': ('call(bus, 0x2fd, 0x7a05)', 'call(bus, 0x2fd, 0x7a07)'),
    'status_zero_flag': ('value == 0 ? 0x40u : 0u', 'value == 0 ? 0u : 0x40u'),
    'far_call_push_order': ('push(bus, r.cs); push(bus, next);', 'push(bus, next); push(bus, r.cs);'),
    'store_scan_instead_of_ascii': ('bus.writeByte(r.ds, 0x2058, static_cast<uint8_t>(r.ax))',
        'bus.writeByte(r.ds, 0x2058, static_cast<uint8_t>(r.ax >> 8))'),
    'drop_extended_prefix_write': ('case 0x7a0e: bus.writeByte', 'case 0x7a0e: if (static_cast<uint8_t>(r.ax)) bus.writeByte'),
    'exit_after_first_read': ('case 0x7a11: r.ip = 0x7a00;',
        'case 0x7a11: r.ip = 0x7a13; state_.outcome = GameKeyboardOutcome::Drained;'),
    'clear_last_byte_when_empty': ('if (r.ip == 0x7a13) state_.outcome = GameKeyboardOutcome::Drained;',
        'if (r.ip == 0x7a13) { bus.writeByte(r.ds, 0x2058, 0); state_.outcome = GameKeyboardOutcome::Drained; }'),
    'timer_si_restore': ('state_.timer.reset();', 'state_.registers.si = 0; state_.timer.reset();'),
}


def run(compiler,out):
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a fresh RAM-only mutation output directory')
    if shutil.disk_usage('/dev/shm').free<256*1024**2:
        raise RuntimeError('Insufficient RAM-only mutation reserve')
    source=ROOT/'src/core/game_keyboard.hpp';raw=source.read_bytes();original=raw.decode();out.mkdir()
    environment=dict(os.environ,TMPDIR='/dev/shm',PYTHONDONTWRITEBYTECODE='1')
    checked=subprocess.run(['python3','-S','-B',str(ROOT/'tools/check_game_keyboard_fixture.py'),
        '--cpu',str(out/'cpu.bin')],capture_output=True,env=environment,timeout=60)
    (out/'fixture.log').write_bytes(checked.stdout+checked.stderr);checked.check_returncode()
    report=dict(source_sha256=hashlib.sha256(raw).hexdigest(),cases=[],detected=0,equivalent=0)
    for name,change in [('baseline',None),*MUTATIONS.items()]:
        folder=out/name;(folder/'core').mkdir(parents=True);text=original
        if change:
            before,after=change
            if text.count(before)!=1:
                raise ValueError('Mutation no longer identifies one expression: '+name)
            text=text.replace(before,after)
        (folder/'core/game_keyboard.hpp').write_text(text);exe=folder/'keyboard'
        built=subprocess.run([compiler,'-std=c++23','-O2','-Wall','-Wextra','-Werror','-I',str(folder),
            '-I',str(ROOT/'src'),str(ROOT/'tests/core/game_keyboard_test.cpp'),'-o',str(exe)],
            capture_output=True,env=environment,timeout=180)
        (folder/'build.log').write_bytes(built.stdout+built.stderr);built.check_returncode();failures=[]
        for index,arguments in enumerate([[],['--original',str(out/'cpu.bin')]]):
            checked=subprocess.run([str(exe),*arguments],capture_output=True,env=environment,timeout=60)
            (folder/('probe-'+str(index)+'.log')).write_bytes(checked.stdout+checked.stderr)
            if checked.returncode:
                failures.append(dict(probe=arguments,exit=checked.returncode))
        if not change and failures:
            raise RuntimeError('Unmodified game keyboard regression failed')
        if change:
            report['detected' if failures else 'equivalent']+=1
        report['cases'].append(dict(name=name,failures=failures));(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(name=name,rejected=bool(failures))),flush=True)
    if source.read_bytes()!=raw:
        raise RuntimeError('Game keyboard source changed during fault checks')
    if report['detected']!=len(MUTATIONS):
        raise RuntimeError('A behavioral mutation survived; retained for inspection')
    print('game_keyboard_mutations=ok detected=8 baseline_probes=2',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--compiler',default='g++')
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();run(args.compiler,args.out)
