"""Compile concrete reserve-HUD counterexamples without changing production source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from check_reserve_hud_fixture import read_fixture

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = {
    'player_reserve_byte': ('r.di+0x79e9', 'r.di+0x79ea'),
    'strict_slot_compare': ('case 0x2a27:branch(flag(0x80)==flag(0x800),',
                            'case 0x2a27:branch(!flag(0x40)&&flag(0x80)==flag(0x800),'),
    'filled_glyph': ('case 0x2a02:r.ax=arithmetic(r.ax,0x1cc0,false)',
                     'case 0x2a02:r.ax=arithmetic(r.ax,0x1c80,false)'),
    'slot_stride': ('case 0x2a32:bus.writeWord(r.ds,0x2072,arithmetic(bus.readWord(r.ds,0x2072),9,false))',
                    'case 0x2a32:bus.writeWord(r.ds,0x2072,arithmetic(bus.readWord(r.ds,0x2072),8,false))'),
    'pascal_cleanup': ('case 0x2a3e:r.ip=pop(bus);r.sp=static_cast<uint16_t>(r.sp+2u)',
                       'case 0x2a3e:r.ip=pop(bus);r.sp=static_cast<uint16_t>(r.sp+4u)'),
    'direction_flag': ('const int step=(flag(0x400)?-1:1)*(word?2:1);',
                       'const int step=(word?2:1);'),
}


def run(compiler, fixture, out):
    if fixture.read_bytes() != read_fixture():
        raise ValueError('Mutation input is not the authenticated original corpus')
    source = ROOT / 'src/core/frame_hud.hpp'
    original = source.read_bytes()
    if out.is_symlink():
        raise ValueError('Mutation output parent must not be a symbolic link')
    out.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    report = dict(status='failed', production_sha256=hashlib.sha256(original).hexdigest(), variants=[])
    try:
        for name, replacement in dict(control=None, **MUTANTS).items():
            target = folder / name
            (target / 'core').mkdir(parents=True)
            text = original.decode('ascii')
            if replacement is not None:
                before, after = replacement
                if text.count(before) != 1:
                    raise ValueError('Mutation anchor differs: ' + name)
                text = text.replace(before, after, 1)
            (target / 'core/frame_hud.hpp').write_text(text)
            binary = target / 'replay'
            built = subprocess.run([compiler, '-std=c++23', '-O1', '-Wall', '-Wextra', '-Werror', '-pedantic',
                '-I', str(target), '-I', str(ROOT / 'src'), str(ROOT / 'tests/core/reserve_hud_test.cpp'),
                '-o', str(binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            (target / 'compile.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Counterexample compilation failed: ' + name)
            result = subprocess.run([str(binary), str(fixture), str(ROOT / 'LEZAC.EXE')],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
            (target / 'replay.log').write_bytes(result.stdout)
            expected = result.returncode == 0 if replacement is None else (
                result.returncode == 1 and b'reserve_hud=failed' in result.stdout)
            if not expected:
                raise ValueError('Counterexample result differs: ' + name)
            report['variants'].append(dict(name=name, exit_code=result.returncode))
        if source.read_bytes() != original:
            raise ValueError('Production source changed during mutation tests')
        report.update(status='passed', compiled=7, rejected=6, production_source_unchanged=True)
        print('reserve_hud_mutations=ok compiled=7 rejected=6 production_source_unchanged=1', flush=True)
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
