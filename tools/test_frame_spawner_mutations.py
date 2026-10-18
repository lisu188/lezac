"""Compile concrete spawner counterexamples without changing production source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from check_frame_spawner_fixture import read_fixture

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = {
    'reset_destination': ('bus.writeByte(r.ds,0x79ae,0)', 'bus.writeByte(r.ds,0x79ad,0)'),
    'last_spawner': ('case 0x7a84:branch(!flag(1),', 'case 0x7a84:branch(!flag(1)&&!flag(0x40),'),
    'actor_capacity': ('arithmetic(bus.readByte(r.ds,0x208d),30,true,true)',
                       'arithmetic(bus.readByte(r.ds,0x208d),29,true,true)'),
    'visual_capacity': ('arithmetic(bus.readByte(r.ds,0xc496),32,true,true)',
                        'arithmetic(bus.readByte(r.ds,0xc496),31,true,true)'),
    'random_multiplier': ('bus.readWord(r.cs,0x142d)', 'bus.readWord(r.cs,0x142f)'),
    'animation_delay': ('case 0x6e5:write(4,r.ax)', 'case 0x6e5:write(4,0)'),
}


def run(compiler, fixture, out):
    if fixture.read_bytes() != read_fixture():
        raise ValueError('Mutation input is not the authenticated original corpus')
    source = ROOT / 'src/core/frame_spawner.hpp'
    original = source.read_bytes()
    if out.is_symlink():
        raise ValueError('Mutation output parent must not be a symbolic link')
    out.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    report = dict(status='failed', production_sha256=hashlib.sha256(original).hexdigest(), variants=[])
    try:
        variants = dict(control=None, **MUTANTS)
        for name, replacement in variants.items():
            target = folder / name
            (target / 'core').mkdir(parents=True)
            text = original.decode('ascii')
            if replacement is not None:
                before, after = replacement
                if text.count(before) != 1:
                    raise ValueError('Mutation anchor differs: ' + name)
                text = text.replace(before, after, 1)
            (target / 'core/frame_spawner.hpp').write_text(text)
            binary = target / 'replay'
            built = subprocess.run([compiler, '-std=c++23', '-O1', '-Wall', '-Wextra', '-Werror', '-pedantic',
                '-I', str(target), '-I', str(ROOT / 'src'), str(ROOT / 'tests/core/frame_spawner_test.cpp'),
                '-o', str(binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            (target / 'compile.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Counterexample compilation failed: ' + name)
            result = subprocess.run([str(binary), str(fixture), str(ROOT / 'LEZAC.EXE')],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
            (target / 'replay.log').write_bytes(result.stdout)
            expected = result.returncode == 0 if replacement is None else (
                result.returncode == 1 and b'frame_spawner=failed' in result.stdout)
            if not expected:
                raise ValueError('Counterexample result differs: ' + name)
            report['variants'].append(dict(name=name, exit_code=result.returncode))
        if source.read_bytes() != original:
            raise ValueError('Production source changed during mutation tests')
        report.update(status='passed', compiled=7, rejected=6, production_source_unchanged=True)
        print('frame_spawner_mutations=ok compiled=7 rejected=6 production_source_unchanged=1', flush=True)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (folder / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.compiler, args.fixture.resolve(strict=True), args.out.absolute())
