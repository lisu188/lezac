"""Compile independent waiting-window faults against authenticated original evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from check_frame_waiting_fixture import ROOT, read_fixture

MUTATIONS = (
    ('hud_gate', 'branch(flag(1)||flag(0x40),0x7c77,0x7c54)', 'branch(true,0x7c77,0x7c54)'),
    ('countdown', 'increment(bus.readWord(r.es,a),true));r.ip=0x7c9a', 'increment(bus.readWord(r.es,a),false));r.ip=0x7c9a'),
    ('reserve_address', 'r.di+0x79e9', 'r.di+0x79e8'),
    ('shared_cursor', 'bus.writeWord(r.ds,0x2074,r.ax)', 'bus.writeWord(r.ds,0x2072,r.ax)'),
    ('shared_latches', 'bus.writeByte(r.ds,r.ip==0x7e9d?0x1b7b:0x1b80,0)', 'bus.writeByte(r.ds,r.ip==0x7e9d?0x1b7b:0x1b80,1)'),
    ('large_minimum', 'bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x1b6a),2)', 'bus.writeByte(r.ds,static_cast<uint16_t>(r.di+0x1b6a),3)'),
    ('second_player', 'case 0x7eb1:arithmetic(player(),2,true)', 'case 0x7eb1:arithmetic(player(),1,true)'),
    ('ui_return_stack', 'case 0x7d08:call(0x1b14,0x7d0b)', 'case 0x7d08:call(0x1b14,0x7d0e)'),
    ('runtime_handoff', 'if (!returned) state_.outcome = FrameWaitingOutcome::RuntimeError', 'if (!returned) state_.outcome = FrameWaitingOutcome::Completed'),
    ('child_budget', 'operation.advance(1, bus, copies)', 'operation.advance(2, bus, copies)'),
)


def run(compiler, fixture, out):
    if fixture.read_bytes() != read_fixture():
        raise ValueError('Use the authenticated original waiting corpus')
    if out.is_symlink():
        raise ValueError('Mutation output must not be a symbolic link')
    out.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    header = ROOT / 'src/core/frame_waiting.hpp'
    source = header.read_text()
    protected = [*sorted((ROOT / 'src/core').glob('*.hpp')), ROOT / 'tests/core/frame_waiting_test.cpp']
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    results = []
    try:
        for name, old, new in (('control', '', ''), *MUTATIONS):
            case = directory / name
            shutil.copytree(ROOT / 'src/core', case / 'core')
            if old:
                if old not in source:
                    raise ValueError('Mutation target missing: ' + name)
                (case / 'core/frame_waiting.hpp').write_text(source.replace(old, new))
            executable = case / 'replay'
            compile_result = subprocess.run([compiler, '-std=c++23', '-O2', '-Wall', '-Wextra', '-Werror',
                '-I' + str(case), str(ROOT / 'tests/core/frame_waiting_test.cpp'), '-o', str(executable)],
                capture_output=True, text=True, timeout=120)
            if compile_result.returncode:
                raise ValueError('Mutation did not compile: ' + name + '\n' + compile_result.stderr)
            replay = subprocess.run([str(executable), str(fixture), str(ROOT / 'LEZAC.EXE')],
                capture_output=True, text=True, timeout=120)
            if (name == 'control') != (replay.returncode == 0):
                raise ValueError('Unexpected mutation replay result: ' + name + replay.stdout + replay.stderr)
            results.append(dict(name=name, returncode=replay.returncode,
                stdout=replay.stdout[-8192:], stderr=replay.stderr[-8192:]))
        if before != {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}:
            raise ValueError('Production waiting sources changed during mutation testing')
    except Exception as error:
        (directory / 'failed.json').write_text(json.dumps(dict(status='failed', error=str(error), results=results), indent=2) + '\n')
        raise
    (directory / 'report.json').write_text(json.dumps(dict(status='passed', results=results), indent=2) + '\n')
    print('frame_waiting_mutations=ok compiled=11 rejected=10 production_source_unchanged=1')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.compiler, arguments.fixture, arguments.out)
