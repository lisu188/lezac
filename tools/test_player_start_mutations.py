"""Compile isolated locator faults and require original replay to detect them."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def run(cxx, fixture, out):
    out = out / str(time.time_ns())
    out.mkdir(parents=True)
    core, live = 'src/core/player_start.hpp', 'src/gameplay/player_start.hpp'
    originals = {name: (ROOT / name).read_bytes() for name in (core, live)}
    faults = (
        ('key_filter', live, 'if ((portal.marker & marker) != 0)', 'if (portal.key == 0 && (portal.marker & marker) != 0)'),
        ('marker_equality', live, '(portal.marker & marker) != 0', 'portal.marker == marker'),
        ('missing_fallback', live, 'return {uint16_t{17}, uint16_t{17}};', 'return {uint16_t{0}, uint16_t{0}};'),
        ('idle_not_cleared', core, 'case 0x585:bus.writeByte(r.es,static_cast<uint16_t>(r.di+2u),0);',
         'case 0x585:bus.writeByte(r.es,static_cast<uint16_t>(r.di+2u),1);'),
        ('ret_cleanup', core, 'r.sp=static_cast<uint16_t>(r.sp+6u);state_.outcome',
         'r.sp=static_cast<uint16_t>(r.sp+4u);state_.outcome'))
    report = dict(status='failed', faults=[])
    try:
        for name, relative, before, after in faults:
            source = originals[relative].decode('ascii')
            if source.count(before) != 1:
                raise ValueError('Locator mutation site differs: ' + name)
            variant = out / name
            header = variant / Path(relative).relative_to('src')
            header.parent.mkdir(parents=True)
            header.write_text(source.replace(before, after), encoding='ascii')
            exe = variant / 'test'
            built = subprocess.run([cxx, '-std=c++23', '-O2', '-Wall', '-Wextra', '-Werror', '-pedantic',
                '-I', str(variant), '-I', str(ROOT / 'src'), str(ROOT / 'tests/core/player_start_test.cpp'),
                '-o', str(exe)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (variant / 'build.log').write_bytes(built.stdout)
            if built.returncode:
                raise ValueError('Locator mutant did not compile: ' + name)
            result = subprocess.run([str(exe), str(fixture), str(ROOT)], stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=30)
            (variant / 'replay.log').write_bytes(result.stdout)
            if result.returncode != 1 or b'player_start=failed' not in result.stdout:
                raise ValueError('Locator fault was not detected: ' + name)
            report['faults'].append(dict(name=name, exit_code=result.returncode, output=result.stdout.decode()))
        report['status'] = 'passed'
    finally:
        report['source_preserved'] = all((ROOT / name).read_bytes() == raw for name, raw in originals.items())
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if not report['source_preserved']:
        raise ValueError('Locator sources changed during mutation testing')
    print('player_start_mutations=ok faults=5 source_preserved=1')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.cxx, args.fixture, args.out)
