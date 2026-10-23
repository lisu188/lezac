"""Compile full-pass counterexamples after an authenticated positive baseline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import check_frame_actor_pass_fixture as checker

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'src/core/frame_actor_pass.hpp'
TEST = 'tests/core/frame_actor_pass_test.cpp'
FAULTS = (
    ('caller_ss', 'snapshot(),game,r.ss,r.sp,r.bp,idToggle',
        'snapshot(),game,static_cast<uint16_t>(r.ss+1u),r.sp,r.bp,idToggle'),
    ('caller_sp', 'snapshot(),game,r.ss,r.sp,r.bp,idToggle',
        'snapshot(),game,r.ss,static_cast<uint16_t>(r.sp+2u),r.bp,idToggle'),
    ('caller_bp', 'snapshot(),game,r.ss,r.sp,r.bp,idToggle',
        'snapshot(),game,r.ss,r.sp,static_cast<uint16_t>(r.bp+1u),idToggle'),
    ('return_target', 'state_.actorKind==FrameActorPassKind::Nonplayer ? 0x7ee4 : 0x7f5c',
        'state_.actorKind==FrameActorPassKind::Nonplayer ? 0x7f5c : 0x7ee4'),
    ('skip_player_post', 'state_.callee=PlayerPostOperation(r,state_.gameSegment,state_.idToggleMask).snapshot();',
        '{ auto skipped=r;skipped.ip=0x8044;caller(skipped);++state_.postReturns; }'),
    ('skip_nonplayer_loop', 'if (state_.actorKind==FrameActorPassKind::Nonplayer) caller(r);',
        'if (state_.actorKind==FrameActorPassKind::Nonplayer) { auto skipped=r;skipped.ip=0x7f34;caller(skipped); }'),
    ('caller_phase_ownership', '} else invalid();\n                if (child.timer',
        '} else (void)child;\n                if (child.timer'),
    ('standalone_post_ownership', 'child.entry!=PlayerPostEntry::Caller', 'false'),
    ('caller_instruction_scope',
        '!callerAddress(cpu->registers.ip)', 'false'),
    ('caller_operand_range', '!callerAddress(cpu->registers.ip)',
        '!((cpu->registers.ip>=0x7ebb && cpu->registers.ip<=0x7f59) || '
        '(cpu->registers.ip>=0x8044 && cpu->registers.ip<=0x804b))'),
    ('caller_post_balance', 'state_.playerCalls!=state_.postCalls ||', 'false ||'),
    ('boss_game_instruction_scope', '!bossGameAddress(r.ip)', 'false'),
    ('boss_library_instruction_scope', '!bossLibraryAddress(r.ip)', 'false'),
    ('nonplayer_return_ownership',
        '((cpu->registers.ip==0x7ee4 || cpu->registers.ip==0x7ee8) && !state_.nonplayerCalls) ||', 'false ||'),
    ('boss_actor_history', 'state_.actorCalls || links->dispatchedInstructions>child.dispatchedInstructions',
        'links->dispatchedInstructions>child.dispatchedInstructions'),
    ('caller_preloop_history',
        'cpu->registers.ip>=0x7ebb && cpu->registers.ip<=0x7ec5 && state_.actorCalls', 'false'),
    ('caller_player_history',
        '(cpu->registers.ip<=0x7f3a || cpu->registers.ip==0x77dc) && state_.playerCalls', 'false'),
    ('player_loop_entry_history', 'cpu->registers.ip<=0x7f3a', 'cpu->registers.ip<=0x7f34'),
    ('player_call_limit', 'state_.playerCalls>2 ||', 'false ||'),
    ('player_setup_history',
        '(((cpu->registers.ip>=0x7f3c && cpu->registers.ip<=0x7f59) ||\n'
        '                            cpu->registers.ip==0x804b) && state_.playerCalls>1) ||', 'false ||'),
    ('nonplayer_player_history', 'state_.actorKind==FrameActorPassKind::Nonplayer && state_.playerCalls', 'false'),
    ('running_boss_terminal',
        '(child.outcome==FrameActorEntryOutcome::Running &&\n'
        '                            r.cs==static_cast<uint16_t>(state_.gameSegment+0x920) && r.ip==0xe2) ||',
        'false ||'),
    ('boss_finished_ownership', 'child.outcome==FrameActorEntryOutcome::Running ? links->outcome!=BossLinksOutcome::Running :',
        'child.outcome==FrameActorEntryOutcome::Running ? false :'),
    ('boss_error_ownership', 'child.outcome!=FrameActorEntryOutcome::RuntimeError || links->outcome!=BossLinksOutcome::RuntimeError',
        'child.outcome!=FrameActorEntryOutcome::RuntimeError'),
    ('timer_data_ownership',
        'child.timer->dataSegment!=static_cast<uint16_t>(state_.gameSegment+0xaa2)',
        'false'),
    ('child_caller_sp', 'child.callerSp!=state_.callerSp', 'false'),
    ('child_caller_bp', 'child.callerBp!=state_.callerBp', 'false'),
    ('root_ss', 'r.ss!=state_.callerSs ||', 'false ||'),
    ('actor_calls', '++state_.actorCalls;', '(void)state_.actorCalls;'),
    ('actor_returns', '++state_.actorReturns;', '(void)state_.actorReturns;'),
    ('post_calls', '++state_.postCalls;', '(void)state_.postCalls;'),
    ('post_returns', '++state_.postReturns;caller(r);', '(void)state_.postReturns;caller(r);'),
    ('nonplayer_calls', '++state_.nonplayerCalls;', '(void)state_.nonplayerCalls;'),
    ('player_calls', '++state_.playerCalls;', '(void)state_.playerCalls;'),
    ('dispatch_accounting', '++used;++state_.dispatchedInstructions;', '++used;state_.dispatchedInstructions+=2;'),
    ('timer_accounting', 'if (timer) ++state_.timerInstructions;', 'if (timer) (void)state_.timerInstructions;'),
    ('irq_delivery', '++state_.timerDeliveries;', '(void)state_.timerDeliveries;'),
    ('terminal_dispatch', 'while (used<budget && !finished()) {', 'while (used<budget) {'),
    ('runtime_outcome', 'else if (actor->outcome==ActorUpdateOutcome::RuntimeError) state_.outcome=FrameActorPassOutcome::RuntimeError;',
        'else if (actor->outcome==ActorUpdateOutcome::RuntimeError) state_.outcome=FrameActorPassOutcome::DivideError;'),
    ('divide_outcome', 'else if (actor->outcome==ActorUpdateOutcome::DivideError) state_.outcome=FrameActorPassOutcome::DivideError;',
        'else if (actor->outcome==ActorUpdateOutcome::DivideError) state_.outcome=FrameActorPassOutcome::RuntimeError;'),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    payload = checker.read_fixture()
    if args.fixture.read_bytes() != payload:
        raise ValueError('Pass mutation input is not the authenticated frozen projection')
    args.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=args.out))
    originals = {name: (ROOT / name).read_bytes() for name in (HEADER, TEST)}
    protected = {path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / 'src/core').glob('*')) if path.is_file()}
    protected[ROOT / TEST] = hashlib.sha256(originals[TEST]).hexdigest()
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    results = []
    report = dict(status='failed', results=results,
        sources={name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()},
        protected_sources={path.relative_to(ROOT).as_posix(): value for path, value in protected.items()})

    def compile_probe(stage):
        exe = stage / 'probe'
        built = subprocess.run([args.cxx, '-std=c++23', '-O1', '-Wall', '-Wextra', '-Werror', '-pedantic',
            '-I' + str(stage / 'src'), '-I' + str(ROOT / 'src'), str(ROOT / TEST), '-o', str(exe)],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        (stage / 'build.log').write_bytes(built.stdout)
        if built.returncode:
            raise ValueError('Pass probe did not compile: ' + stage.name)
        return exe

    def run_probe(exe, label, arguments):
        run = subprocess.run([str(exe), *arguments], env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
        (exe.parent / (label + '.log')).write_bytes(run.stdout)
        return run

    try:
        baseline = out / 'baseline'
        baseline.mkdir()
        exe = compile_probe(baseline)
        for label, arguments in (('unit', []), ('original', [str(args.fixture), str(ROOT)])):
            run = run_probe(exe, label, arguments)
            if run.returncode or ('frame_actor_pass_' + label + '=ok').encode() not in run.stdout:
                raise ValueError('Pass positive baseline failed: ' + label)
        report['positive_baseline_passed'] = True
        for name, before, after in FAULTS:
            text = originals[HEADER].decode()
            if text.count(before) != 1:
                raise ValueError('Pass mutation anchor differs: ' + name)
            stage = out / name
            altered = stage / HEADER
            altered.parent.mkdir(parents=True)
            altered.write_text(text.replace(before, after), encoding='utf-8')
            exe = compile_probe(stage)
            rejected = False
            for label, arguments in (('unit', []), ('original', [str(args.fixture), str(ROOT)])):
                run = run_probe(exe, label, arguments)
                if run.returncode:
                    if b'frame_actor_pass=failed' not in run.stdout:
                        raise ValueError('Pass mutant failed outside assertions: ' + name)
                    rejected = True
                    results.append(dict(fault=name, rejected_by=label, exit_code=run.returncode))
                    break
            if not rejected:
                raise ValueError('Pass fault escaped: ' + name)
            if args.fixture.read_bytes() != payload or any(
                    hashlib.sha256(path.read_bytes()).hexdigest() != value for path, value in protected.items()):
                raise ValueError('Pass protected fixture or source changed')
        checker.read_fixture()
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('frame_actor_pass_mutations=ok faults=' + str(len(FAULTS)) + ' positive_baseline=1 sources_preserved=1')


if __name__ == '__main__':
    main()
