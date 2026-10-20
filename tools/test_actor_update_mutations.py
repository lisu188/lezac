"""Compile complete-actor ownership, handoff, snapshot and IRQ counterexamples."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'src/core/actor_update.hpp'
FAULTS = (
    ('caller_sp', 'static_cast<uint16_t>(r.sp+6u),r.bp,idToggle',
        'static_cast<uint16_t>(r.sp+4u),r.bp,idToggle'),
    ('helper_entry_ownership', 'if (child.entry!=ActorMotionEntry::Behavior)', 'if (false)'),
    ('caller_bp', 'static_cast<uint16_t>(r.sp+6u),r.bp,idToggle',
        'static_cast<uint16_t>(r.sp+6u),static_cast<uint16_t>(r.bp+1u),idToggle'),
    ('caller_ss', 'FrameActorContactOperation(r,game,idToggle).snapshot(),game,r.ss,',
        'FrameActorContactOperation(r,game,idToggle).snapshot(),game,static_cast<uint16_t>(r.ss+1u),'),
    ('skip_player_terrain', 'if (child.outcome==PlayerMotionOutcome::Terrain) return ActorMotionSnapshot{child.cpu};',
        'if (child.outcome==PlayerMotionOutcome::Terrain) { auto cpu=child.cpu;cpu.registers.ip=0x73e5;return ActorMotionSnapshot{cpu}; }'),
    ('player_bypass', 'return PlayerMotionOperation(r,game,id).snapshot();',
        'return ActorMotionOperation(r,game,id).snapshot();'),
    ('expiry_bypass', 'if (child.outcome==ActorTileFlagsOutcome::Expiry) return ActorExpiryOperation(r,game,id).snapshot();',
        'if (child.outcome==ActorTileFlagsOutcome::Expiry) return ActorMotionOperation(r,game,id).snapshot();'),
    ('skip_integration', 'if (child.outcome==ActorMotionOutcome::MotionIntegration) return child.cpu;',
        'if (child.outcome==ActorMotionOutcome::MotionIntegration) { auto cpu=child.cpu;cpu.registers.ip=0x7780;return cpu; }'),
    ('dispatch_accounting', '++used;++state_.dispatchedInstructions;',
        '++used;state_.dispatchedInstructions+=2;'),
    ('timer_accounting', 'if (timer) ++state_.timerInstructions;', 'if (timer) (void)state_.timerInstructions;'),
    ('irq_delivery', 'auto active=operation(child);active.deliverTimerInterrupt(bus);child=active.snapshot();',
        'auto active=operation(child);(void)bus;child=active.snapshot();'),
    ('terminal_dispatch', 'while (used<budget && !finished()) {', 'while (used<budget) {'),
    ('snapshot_caller', 'explicit ActorUpdateOperation(ActorUpdateSnapshot state) : state_(std::move(state)) { validate(); }',
        'explicit ActorUpdateOperation(ActorUpdateSnapshot state) : state_(std::move(state)) { ++state_.callerSp;validate(); }'),
    ('runtime_outcome', 'state_.outcome=ActorUpdateOutcome::RuntimeError;',
        'state_.outcome=ActorUpdateOutcome::Returned;'),
    ('divide_outcome', 'state_.outcome=child.outcome==ActorMotionOutcome::DivideError ?\n'
        '                    ActorUpdateOutcome::DivideError : ActorUpdateOutcome::RuntimeError;',
        'state_.outcome=child.outcome==ActorMotionOutcome::DivideError ?\n'
        '                    ActorUpdateOutcome::Returned : ActorUpdateOutcome::RuntimeError;'),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=args.out))
    originals = {name: (ROOT / name).read_bytes() for name in (HEADER, 'tests/core/actor_update_test.cpp')}
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    results = []
    report = dict(status='failed', results=results,
        sources={name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()})
    try:
        for name, before, after in FAULTS:
            text = originals[HEADER].decode()
            if text.count(before) != 1:
                raise ValueError('Actor update mutation anchor differs: ' + name)
            stage = out / name
            altered = stage / HEADER
            altered.parent.mkdir(parents=True)
            altered.write_text(text.replace(before, after), encoding='utf-8')
            exe = stage / 'probe'
            build = subprocess.run([args.cxx, '-std=c++23', '-O1', '-Wall', '-Wextra', '-Werror', '-pedantic',
                '-I' + str(stage / 'src'), '-I' + str(ROOT / 'src'),
                str(ROOT / 'tests/core/actor_update_test.cpp'), '-o', str(exe)],
                env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            (stage / 'build.log').write_bytes(build.stdout)
            if build.returncode:
                raise ValueError('Actor update mutant did not compile: ' + name)
            rejected = False
            for label, arguments in (('unit', []), ('original', [str(args.fixture), str(ROOT)])):
                run = subprocess.run([str(exe), *arguments], env=environment,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
                (stage / (label + '.log')).write_bytes(run.stdout)
                if run.returncode:
                    if b'actor_update=failed' not in run.stdout:
                        raise ValueError('Actor update mutant failed outside assertions: ' + name)
                    rejected = True
                    results.append(dict(fault=name, rejected_by=label, exit_code=run.returncode))
                    break
            if not rejected:
                raise ValueError('Actor update fault escaped: ' + name)
            if any((ROOT / path).read_bytes() != raw for path, raw in originals.items()):
                raise ValueError('Actor update production/test source changed')
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('actor_update_mutations=ok faults=15 sources_preserved=1')


if __name__ == '__main__':
    main()
