"""Compile frame-tail ownership, handoff, snapshot and IRQ counterexamples."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import check_frame_tail_fixture as checker

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'src/core/frame_tail.hpp'
TEST = 'tests/core/frame_tail_test.cpp'
FAULTS = (
    ('phantom_timer_work', '(!state_.timerDeliveries && state_.timerInstructions) ||', 'false ||'),
    ('caller_sp', ': state_{r,game,r.ss,r.sp,r.bp,id}', ': state_{r,game,r.ss,static_cast<uint16_t>(r.sp+2u),r.bp,id}'),
    ('running_ss', 'if (r.ss!=state_.callerSs || registers().ss!=state_.callerSs ||', 'if ((finished() && r.ss!=state_.callerSs) || registers().ss!=state_.callerSs ||'),
    ('live_irq_ss', 'registers().ss!=state_.callerSs ||', '(finished() && registers().ss!=state_.callerSs) ||'),
    ('phase_stack', '((main || video) && (r.sp!=expectedSp || r.bp!=expectedBp))', '((main || video) && !state_.dispatchedInstructions && (r.sp!=expectedSp || r.bp!=expectedBp))'),
    ('rng_return', 'FrameTailReturn{r.cs,r.ip,r.sp,r.bp}!=*state_.rngReturn', 'r.ss!=state_.callerSs'),
    ('stack_return', 'FrameTailReturn{r.cs,r.ip,r.sp,r.bp}!=*state_.stackReturn', 'r.ss!=state_.callerSs'),
    ('graphics_return', 'before.cs==graphics() && before.ip==0x1f', 'before.cs==graphics() && before.ip==0xffff'),
    ('palette_return', 'before.ip==0x7c4 &&', 'before.ip==0xffff &&'),
    ('tile_return', 'if (before.cs==state_.gameSegment && before.ip==0x3a53)', 'if (before.cs==state_.gameSegment && before.ip==0xffff)'),
    ('countdown_direction', 'increment(byte(0x79b2),true,true)', 'increment(byte(0x79b2),false,true)'),
    ('excluded_tile', 'case 0x3f69:branch(!flag(0x40),0x3f6f,0x3f6b);break;', 'case 0x3f69:r.ip=0x3f6f;break;'),
    ('view_player_gate', 'case 0x825c:branch(!flag(0x40),0x8283,0x825e);break;', 'case 0x825c:r.ip=0x825e;break;'),
    ('completion_gate', 'case 0x8296:branch(!flag(0x40),0x82af,0x8298);break;', 'case 0x8296:r.ip=0x8298;break;'),
    ('escape_gate', 'case 0x82b4:branch(flag(0x40),0x82b9,0x82b6);break;', 'case 0x82b4:r.ip=0x82b6;break;'),
    ('dac_value', 'case 13:al(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+12u)));', 'case 13:al(static_cast<uint16_t>(bus.readByte(r.ss,static_cast<uint16_t>(r.bp+12u))+1u));'),
    ('dispatch_accounting', '++used;++state_.dispatchedInstructions;', '++used;state_.dispatchedInstructions+=2;'),
    ('timer_accounting', '++state_.timerInstructions;', '(void)state_.timerInstructions;'),
    ('irq_delivery', '++state_.timerDeliveries;', '(void)state_.timerDeliveries;'),
    ('terminal_dispatch', 'while (used<budget && !finished()) {', 'while (used<budget) {'),
    ('snapshot_caller', 'explicit FrameTailOperation(FrameTailSnapshot state) : state_(std::move(state)) { validate(); }', 'explicit FrameTailOperation(FrameTailSnapshot state) : state_(std::move(state)) { ++state_.callerSp;validate(); }'),
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
            raise ValueError('Frame tail probe did not compile: ' + stage.name)
        return exe

    def run_probe(exe, label, arguments):
        result = subprocess.run([str(exe), *arguments], env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        (exe.parent / (label + '.log')).write_bytes(result.stdout)
        return result

    try:
        payload = checker.read_fixture()
        if args.fixture.read_bytes() != payload:
            raise ValueError('Frame tail mutation input is not the authenticated frozen projection')
        baseline = out / 'baseline'
        baseline.mkdir()
        exe = compile_probe(baseline)
        for label, arguments in (('unit', []), ('original', [str(args.fixture), str(ROOT)])):
            run = run_probe(exe, label, arguments)
            if run.returncode or ('frame_tail_' + label + '=ok').encode() not in run.stdout:
                raise ValueError('Frame tail positive baseline failed: ' + label)
        report['positive_baseline_passed'] = True
        for name, before, after in FAULTS:
            text = originals[HEADER].decode()
            if text.count(before) != 1:
                raise ValueError('Frame tail mutation anchor differs: ' + name)
            stage = out / name
            altered = stage / HEADER
            altered.parent.mkdir(parents=True)
            altered.write_text(text.replace(before, after), encoding='utf-8')
            exe = compile_probe(stage)
            rejected = False
            for label, arguments in (('unit', []), ('original', [str(args.fixture), str(ROOT)])):
                run = run_probe(exe, label, arguments)
                if run.returncode:
                    if b'frame_tail=failed' not in run.stdout:
                        raise ValueError('Frame tail mutant failed outside assertions: ' + name)
                    rejected = True
                    results.append(dict(fault=name, rejected_by=label, exit_code=run.returncode))
                    break
            if not rejected:
                raise ValueError('Frame tail fault escaped: ' + name)
            if args.fixture.read_bytes() != payload or any(
                    hashlib.sha256(path.read_bytes()).hexdigest() != value for path, value in protected.items()):
                raise ValueError('Frame tail protected fixture or source changed')
        checker.read_fixture()
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('frame_tail_mutations=ok faults=' + str(len(FAULTS)) + ' positive_baseline=1 sources_preserved=1')


if __name__ == '__main__':
    main()
