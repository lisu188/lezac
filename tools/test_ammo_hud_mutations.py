"""Compile ammunition/drawing counterexamples in copies, never production files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from check_ammo_hud_fixture import read_fixture

ROOT = Path(__file__).resolve().parents[1]
HUD = 'src/core/frame_hud.hpp'
DRAW = 'src/core/frame_drawing.hpp'
MUTANTS = {
    'dirty_gate': (HUD, 'case 0x32b0:branch(flag(1)||flag(0x40),', 'case 0x32b0:branch(flag(0x40),'),
    'count_clamp': (HUD, 'case 0x3332:bus.writeByte(r.ss,stackOffset(-2),99)', 'case 0x3332:bus.writeByte(r.ss,stackOffset(-2),100)'),
    'shared_scratch': (HUD, 'case 0x32c1:bus.writeByte(r.ds,0x79a3,18)', 'case 0x32c1:bus.writeByte(r.ds,0x79a3,0)'),
    'pascal_cleanup': (HUD, 'case 0x3355:r.ip=pop(bus);r.sp=static_cast<uint16_t>(r.sp+6u)',
                       'case 0x3355:r.ip=pop(bus);r.sp=static_cast<uint16_t>(r.sp+4u)'),
    'signed_center': (HUD, 'r.ax=static_cast<uint16_t>(r.ax>>1);r.flags=',
                      'r.ax=static_cast<uint16_t>(std::bit_cast<int16_t>(r.ax)/2);r.flags='),
    'clear_stride': (DRAW, 'case 0x7ef:r.di=arithmetic(r.di,0x140,false)', 'case 0x7ef:r.di=arithmetic(r.di,0x13f,false)'),
    'transparent_background': (DRAW, 'case 0x134f:al(static_cast<uint8_t>(r.ax>>8))', 'case 0x134f:al(0)'),
    'index_one_ink': (DRAW, 'case 0x135c:al(lo(r.bx))', 'case 0x135c:al(0)'),
}


def run(compiler, fixture, out):
    if fixture.read_bytes() != read_fixture():
        raise ValueError('Mutation input is not the authenticated original corpus')
    originals = {name: (ROOT / name).read_bytes() for name in (HUD, DRAW)}
    if out.is_symlink():
        raise ValueError('Mutation output parent must not be a symbolic link')
    out.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    report = dict(status='failed', original_sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()}, variants=[])
    try:
        for name, mutation in dict(control=None, **MUTANTS).items():
            target = folder / name
            (target / 'core').mkdir(parents=True)
            if mutation is not None:
                relative, before, after = mutation
                text = originals[relative].decode('ascii')
                if text.count(before) != 1:
                    raise ValueError('Mutation anchor differs: ' + name)
                (target / 'core' / Path(relative).name).write_text(text.replace(before, after, 1))
            binary = target / 'replay'
            built = subprocess.run([compiler, '-std=c++23', '-O1', '-Wall', '-Wextra', '-Werror', '-pedantic',
                '-I', str(target), '-I', str(ROOT / 'src'), str(ROOT / 'tests/core/ammo_hud_test.cpp'),
                '-o', str(binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            (target / 'compile.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Counterexample compilation failed: ' + name)
            result = subprocess.run([str(binary), str(fixture), str(ROOT / 'LEZAC.EXE')],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            (target / 'replay.log').write_bytes(result.stdout)
            expected = result.returncode == 0 if mutation is None else (
                result.returncode == 1 and b'ammo_hud=failed' in result.stdout)
            if not expected:
                raise ValueError('Counterexample result differs: ' + name)
            report['variants'].append(dict(name=name, exit_code=result.returncode))
        if any((ROOT / name).read_bytes() != raw for name, raw in originals.items()):
            raise ValueError('Production source changed during mutation tests')
        report.update(status='passed', compiled=9, rejected=8, production_source_unchanged=True)
        print('ammo_hud_mutations=ok compiled=9 rejected=8 production_source_unchanged=1', flush=True)
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
