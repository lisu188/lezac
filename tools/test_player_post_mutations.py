"""Compile player-post ownership, handoff, snapshot and IRQ counterexamples."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import check_player_post_fixture as checker

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'src/core/player_post.hpp'
TEST = 'tests/core/player_post_test.cpp'
FAULTS = (
    ('nested_return_boundary',
        'const bool returned=before.cs==library() && (before.ip==0x9ab || before.ip==0x4f0);',
        'const bool returned=state_.entry==PlayerPostEntry::ScoreDivide && before.cs==library() && before.ip==0x9ab;'),
    ('nested_return_targets',
        'if (state_.entry!=PlayerPostEntry::Caller || r.cs!=state_.gameSegment || !validTarget)',
        'if (false && !validTarget)'),
    ('caller_endpoint_origin',
        'if (before.cs!=state_.gameSegment || (before.ip!=0x8010 && before.ip!=0x1284))',
        'if (false)'),
    ('runtime_retf_precedence',
        'else if (r.cs==library() && r.ip==0xe2) state_.outcome=PlayerPostOutcome::RuntimeError;',
        'if (r.cs==library() && r.ip==0xe2) state_.outcome=PlayerPostOutcome::RuntimeError;'),
    ('live_ss_ownership', 'if (registers().ss!=state_.callerSs ||',
        'if (((state_.outcome==PlayerPostOutcome::Caller || state_.outcome==PlayerPostOutcome::Returned) && '
        'registers().ss!=state_.callerSs) ||'),
    ('caller_sp', 'entry==PlayerPostEntry::ScoreDivide ? 4u : 0u', 'entry==PlayerPostEntry::ScoreDivide ? 4u : 2u'),
    ('library_ds_ownership', '(r.ds!=static_cast<uint16_t>(state_.gameSegment+0xaa2) &&',
        '(r.cs==state_.gameSegment && r.ds!=static_cast<uint16_t>(state_.gameSegment+0xaa2) &&'),
    ('damage_subtract', 'r.ax&255u,true,true)));r.ip=0x7f79;', '0,true,true)));r.ip=0x7f79;'),
    ('life_scratch', 'case 0x30d9:wd(0x2074,r.dx);', 'case 0x30d9:wd(0x2074,100);'),
    ('zero_map_length', 'case 0x30c5:r.cx=word(0x78ba);', 'case 0x30c5:r.cx=word(0x78ba);if (!r.cx) r.cx=1;'),
    ('map_direction', 'r.si+(flag(0x400) ? -1 : 1)', 'r.si+1'),
    ('health_direction', 'r.di+(flag(0x400) ? -1 : 1)', 'r.di+1'),
    ('score_sign', 'case 0x95e:branch(!flag(0x80),0x96a,0x960);', 'case 0x95e:branch(true,0x96a,0x960);'),
    ('divide_iterations', 'case 0x972:r.bp=33;', 'case 0x972:r.bp=32;'),
    ('divide_zero', 'case 0x9b0:r.ip=0xe2;', 'case 0x9b0:r.ip=0x9ab;'),
    ('score_digit_limit', 'case 0x1227:arithmetic(local(-6),8,true);',
        'case 0x1227:arithmetic(local(-6),9,true);'),
    ('player_two_score', 'case 0x7ff5:r.ax=word(0x2084);', 'case 0x7ff5:r.ax=0;'),
    ('retf_precedence', 'if (state_.entry==PlayerPostEntry::ScoreDivide && before.ip==0x9ab)',
        'if (state_.entry==PlayerPostEntry::ScoreDivide && before.ip==0x9ab && r.ip!=0x8044)'),
    ('dispatch_accounting', '++used;++state_.dispatchedInstructions;', '++used;state_.dispatchedInstructions+=2;'),
    ('timer_accounting', '++state_.timerInstructions;', '(void)state_.timerInstructions;'),
    ('irq_delivery', '++state_.timerDeliveries;', '(void)state_.timerDeliveries;'),
    ('copy_accounting', 'state_.stringTransfers+=count;', '(void)state_.stringTransfers;'),
    ('font_accounting', 'state_.stringTransfers+=child.snapshot().stringTransfers;',
        '(void)child.snapshot().stringTransfers;'),
    ('terminal_dispatch', 'while (used<budget && !finished()) {', 'while (used<budget) {'),
    ('snapshot_caller', 'explicit PlayerPostOperation(PlayerPostSnapshot state) : state_(std::move(state)) { validate(); }',
        'explicit PlayerPostOperation(PlayerPostSnapshot state) : state_(std::move(state)) { ++state_.callerSp;validate(); }'),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=args.out))
    originals = {name: (ROOT / name).read_bytes() for name in (HEADER, TEST)}
    protected = {path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / 'src/core').glob('*')) if path.is_file()}
    protected[ROOT / TEST] = hashlib.sha256(originals[TEST]).hexdigest()
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    results = []
    report = dict(status='failed', results=results, positive_baseline_passed=False,
        sources={name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()},
        protected_sources={path.relative_to(ROOT).as_posix(): value for path, value in protected.items()})

    def compile_probe(stage):
        exe = stage / 'probe'
        build = subprocess.run([args.cxx, '-std=c++23', '-O1', '-Wall', '-Wextra', '-Werror', '-pedantic',
            '-I' + str(stage / 'src'), '-I' + str(ROOT / 'src'), str(ROOT / TEST), '-o', str(exe)],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        (stage / 'build.log').write_bytes(build.stdout)
        if build.returncode:
            raise ValueError('Player post probe did not compile: ' + stage.name)
        return exe

    def run_probe(exe, label, arguments):
        result = subprocess.run([str(exe), *arguments], env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        (exe.parent / (label + '.log')).write_bytes(result.stdout)
        return result

    try:
        payload = checker.read_fixture()
        if args.fixture.read_bytes() != payload:
            raise ValueError('Player post mutation input is not the authenticated frozen projection')
        baseline = out / 'baseline'
        baseline.mkdir()
        exe = compile_probe(baseline)
        for label, arguments in (('unit', []), ('original', [str(args.fixture), str(ROOT)])):
            run = run_probe(exe, label, arguments)
            if run.returncode or ('player_post_' + label + '=ok').encode() not in run.stdout:
                raise ValueError('Player post positive baseline failed: ' + label)
        report['positive_baseline_passed'] = True
        for name, before, after in FAULTS:
            text = originals[HEADER].decode()
            if text.count(before) != 1:
                raise ValueError('Player post mutation anchor differs: ' + name)
            stage = out / name
            altered = stage / HEADER
            altered.parent.mkdir(parents=True)
            altered.write_text(text.replace(before, after), encoding='utf-8')
            exe = compile_probe(stage)
            rejected = False
            for label, arguments in (('unit', []), ('original', [str(args.fixture), str(ROOT)])):
                run = run_probe(exe, label, arguments)
                if run.returncode:
                    if b'player_post=failed' not in run.stdout:
                        raise ValueError('Player post mutant failed outside assertions: ' + name)
                    rejected = True
                    results.append(dict(fault=name, rejected_by=label, exit_code=run.returncode))
                    break
            if not rejected:
                raise ValueError('Player post fault escaped: ' + name)
            if args.fixture.read_bytes() != payload or any(
                    hashlib.sha256(path.read_bytes()).hexdigest() != value for path, value in protected.items()):
                raise ValueError('Player post protected fixture or source changed')
        checker.read_fixture()
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('player_post_mutations=ok faults=' + str(len(FAULTS)) + ' positive_baseline=1 sources_preserved=1')


if __name__ == '__main__':
    main()
