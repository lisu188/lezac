"""Compile concrete prefix ownership, handoff and budget counterexamples."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from check_frame_prefix_fixture import ROOT, read_fixture

MUTATIONS = (
    ('active_handoff', 'next = 0; handoff = operation.registers();', 'state_.outcome = FramePrefixOutcome::ActorUpdate;'),
    ('spawner_handoff', 'next = 1; handoff = child.registers;', 'state_.outcome = FramePrefixOutcome::ActorUpdate;'),
    ('child_budget', 'operation.advance(1, bus, copies)', 'operation.advance(2, bus, copies)'),
    ('actor_handoff', '? FramePrefixOutcome::ActorUpdate', '? FramePrefixOutcome::EndRunUi'),
    ('ui_handoff', '? FramePrefixOutcome::EndRunUi :', '? FramePrefixOutcome::ActorUpdate :'),
    ('runtime_handoff', 'else state_.outcome = FramePrefixOutcome::RuntimeError;', 'else state_.outcome = FramePrefixOutcome::ActorUpdate;'),
    ('irq_segment', 'push(r.cs); push(r.ip);', 'push(state_.gameSegment); push(r.ip);'),
    ('irq_counter', '++state_.timerInstructions;', 'state_.timerInstructions += 2;'),
    ('rep_grants', 'operation.advance(1, bus, copies)', 'operation.advance(1, bus, [&](uint16_t n) { static_cast<void>(copies); return n; })'),
    ('zero_budget', 'while (used < budget &&', 'while (used <= budget &&'),
    ('dispatch_counter', '++used; ++state_.dispatchedInstructions;', '++used;'),
)


def run(compiler, fixture, out):
    if fixture.read_bytes() != read_fixture():
        raise ValueError('Mutation input is not the authenticated original frame-prefix corpus')
    if out.is_symlink():
        raise ValueError('Mutation output parent must not be a symbolic link')
    out.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    protected = [*sorted((ROOT / 'src/core').glob('*.hpp')), ROOT / 'tests/core/frame_prefix_test.cpp']
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    before = {str(path): sha(path) for path in protected}
    source = (ROOT / 'src/core/frame_prefix.hpp').read_text()
    results = []
    try:
        for name, old, new in (('control', '', ''), *MUTATIONS):
            case = folder / name
            shutil.copytree(ROOT / 'src/core', case / 'core')
            if old:
                if old not in source:
                    raise ValueError('Mutation target missing: ' + name)
                (case / 'core/frame_prefix.hpp').write_text(source.replace(old, new))
            executable = case / 'replay'
            environment = dict(os.environ, TMPDIR=str(case), TMP=str(case), TEMP=str(case),
                               SDL_AUDIODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
            compiled = subprocess.run([compiler, '-std=c++23', '-O2', '-Wall', '-Wextra', '-Werror',
                '-pedantic', '-I' + str(case), str(ROOT / 'tests/core/frame_prefix_test.cpp'), '-o', str(executable)],
                capture_output=True, text=True, timeout=120, env=environment)
            if compiled.returncode:
                raise ValueError('Mutation did not compile: ' + name + '\n' + compiled.stderr)
            unit = subprocess.run([str(executable)], capture_output=True, text=True, timeout=60, env=environment)
            original = subprocess.run([str(executable), str(fixture), str(ROOT / 'LEZAC.EXE')],
                capture_output=True, text=True, timeout=120, env=environment)
            passed = unit.returncode == 0 and original.returncode == 0
            if (name == 'control') != passed:
                raise ValueError('Unexpected mutation result: ' + name + unit.stderr + original.stderr)
            results.append(dict(name=name, unit_returncode=unit.returncode, original_returncode=original.returncode,
                unit_stdout=unit.stdout[-8192:], unit_stderr=unit.stderr[-8192:],
                original_stdout=original.stdout[-8192:], original_stderr=original.stderr[-8192:]))
        if before != {str(path): sha(path) for path in protected}:
            raise ValueError('Production frame-prefix sources changed during mutation testing')
    except BaseException as error:
        (folder / 'failed.json').write_text(json.dumps(dict(status='failed', error=repr(error), results=results), indent=2) + '\n')
        raise
    (folder / 'report.json').write_text(json.dumps(dict(status='passed', results=results), indent=2) + '\n')
    print('frame_prefix_mutations=ok compiled=12 rejected=11 production_source_unchanged=1')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.compiler, arguments.fixture, arguments.out)
