"""Compile player-ordering, wrapping, snapshot and IRQ counterexamples."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'src/core/player_motion.hpp'
FAULTS = (
    ('gravity', 'case 0x6743:store(-14,arithmetic(local(-14),64));',
        'case 0x6743:store(-14,arithmetic(local(-14),63));'),
    ('landing_threshold', 'case 0x6768:arithmetic(local(-14),1600,true);',
        'case 0x6768:arithmetic(local(-14),1601,true);'),
    ('drop_y', 'case 0x6a68:store(-46,arithmetic(local(-46),2));',
        'case 0x6a68:store(-46,arithmetic(local(-46),3));'),
    ('walk_acceleration', 'case 0x6acd:store(-12,arithmetic(local(-12),64,true));',
        'case 0x6acd:store(-12,arithmetic(local(-12),63,true));'),
    ('super_bomb', 'case 0x6c0e:branch(flag(0x40),0x6c20,0x6c10);',
        'case 0x6c0e:branch(false,0x6c20,0x6c10);'),
    ('pickup_energy', 'case 0x6e64:wb(36,static_cast<uint8_t>(arithmetic(byte(36),33,false,true)));',
        'case 0x6e64:wb(36,static_cast<uint8_t>(arithmetic(byte(36),32,false,true)));'),
    ('score_carry', 'case 0x6f7e:ww(2,arithmetic(word(2),r.dx,false,false,true));',
        'case 0x6f7e:ww(2,arithmetic(word(2),r.dx,false,false,false));'),
    ('portal_key', 'case 0x59aa:r.ax=logic(r.ax&0x7fffu);',
        'case 0x59aa:r.ax=logic(r.ax&0xffffu);'),
    ('ammo_wrap', 'case 0x5725:wb(0,static_cast<uint8_t>(arithmetic(byte(0),r.ax&255u,false,true)));',
        'case 0x5725:wb(0,static_cast<uint8_t>(std::min<unsigned>(99u,byte(0)+(r.ax&255u))));'),
    ('terminal', 'if (r.cs==state_.cpu.gameSegment && r.ip==0x732c) state_.outcome=PlayerMotionOutcome::Terrain;',
        'if (r.cs==state_.cpu.gameSegment && r.ip==0x732d) state_.outcome=PlayerMotionOutcome::Terrain;'),
    ('irq_delivery', 'ActorFinishOperation irq(state_.cpu);irq.deliverTimerInterrupt(bus);state_.cpu=irq.snapshot();',
        'ActorFinishOperation irq(state_.cpu);(void)bus;state_.cpu=irq.snapshot();'),
    ('snapshot_flags', 'explicit PlayerMotionOperation(PlayerMotionSnapshot state) : state_(state) { validate(); }',
        'explicit PlayerMotionOperation(PlayerMotionSnapshot state) : state_(state) { state_.cpu.registers.flags^=0x400u;validate(); }'),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=args.out))
    originals = {name: (ROOT / name).read_bytes() for name in (HEADER, 'tests/core/player_motion_test.cpp')}
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    results = []
    report = dict(status='failed', results=results,
        sources={name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()})
    try:
        for name, before, after in FAULTS:
            text = originals[HEADER].decode()
            if text.count(before) != 1:
                raise ValueError('Player mutation anchor differs: ' + name)
            stage = out / name
            altered = stage / HEADER
            altered.parent.mkdir(parents=True)
            altered.write_text(text.replace(before, after), encoding='utf-8')
            exe = stage / 'probe'
            build = subprocess.run([args.cxx, '-std=c++23', '-O1', '-Wall', '-Wextra', '-Werror', '-pedantic',
                '-I' + str(stage / 'src'), '-I' + str(ROOT / 'src'),
                str(ROOT / 'tests/core/player_motion_test.cpp'), '-o', str(exe)],
                env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            (stage / 'build.log').write_bytes(build.stdout)
            if build.returncode:
                raise ValueError('Player mutant did not compile: ' + name)
            rejected = False
            for label, arguments in (('unit', []), ('original', [str(args.fixture), str(ROOT)])):
                run = subprocess.run([str(exe), *arguments], env=environment,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
                (stage / (label + '.log')).write_bytes(run.stdout)
                if run.returncode:
                    if b'player_motion=failed' not in run.stdout:
                        raise ValueError('Player mutant failed outside assertions: ' + name)
                    rejected = True
                    results.append(dict(fault=name, rejected_by=label, exit_code=run.returncode))
                    break
            if not rejected:
                raise ValueError('Player fault escaped: ' + name)
            if any((ROOT / name).read_bytes() != raw for name, raw in originals.items()):
                raise ValueError('Player production/test source changed')
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('player_motion_mutations=ok faults=12 sources_preserved=1')


if __name__ == '__main__':
    main()
