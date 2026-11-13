"""Detect isolated DAC/palette faults with the focused C++ regression."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {
    'six_bit_mask_lost': ('vga_dac_writer.hpp', 'value&63u', 'value'),
    'low_bit_replication_lost': ('vga_dac_writer.hpp', '(v<<2)|(v>>4)', '(v<<2)'),
    'write_index_not_advanced': ('vga_dac_writer.hpp', 'next.index+1u', 'next.index+0u'),
    'red_blue_swapped': ('vga_dac_writer.hpp',
        'expand(next.channels[0]),expand(next.channels[1]),expand(next.channels[2])',
        'expand(next.channels[2]),expand(next.channels[1]),expand(next.channels[0])'),
    'write_continuation_lost': ('vga_dac_writer.hpp', 'state_=next;', 'state_=VgaDacWriteSnapshot{};'),
    'dirty_first_lost': ('pacing_device_clock.hpp',
        'palette.first=std::min(palette.first,uint32_t{entry});', 'palette.first=palette.first;'),
    'lut_prematurely_committed': ('pacing_device_clock.hpp',
        'palette.rgb[entry]=(uint32_t{red}<<16)|(uint32_t{green}<<8)|blue;',
        'palette.rgb[entry]=(uint32_t{red}<<16)|(uint32_t{green}<<8)|blue;palette.lut[entry]=palette.rgb[entry];'),
}


def run(out, cxx):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or shutil.disk_usage('/dev/shm').free < 256 * 1024**2:
        raise ValueError('Use a RAM-only mutation directory')
    out.mkdir(exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=out))
    source = {name: (ROOT / 'src/core' / name).read_bytes() for name in ('vga_dac_writer.hpp', 'pacing_device_clock.hpp')}
    unit = ROOT / 'tests/core/vga_dac_writer_test.cpp'
    protected = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in [
        *sorted((ROOT / 'src/core').glob('*.hpp')), unit]}
    environment = dict(os.environ, TMPDIR=str(out), SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
    report = dict(status='failed', cases=[], protected_sha256=protected, original_execution_claim=False)
    try:
        for name, mutation in [('baseline', None), *MUTATIONS.items()]:
            case = out / name
            (case / 'core').mkdir(parents=True)
            for header, raw in source.items():
                text = raw.decode()
                if mutation and header == mutation[0]:
                    if text.count(mutation[1]) != 1:
                        raise ValueError('Mutation anchor differs: ' + name)
                    text = text.replace(mutation[1], mutation[2])
                (case / 'core' / header).write_text(text)
            executable = case / 'probe'
            built = subprocess.run([cxx, '-std=c++23', '-O2', '-Wall', '-Wextra', '-Werror', '-pedantic',
                '-I' + str(case), '-I' + str(ROOT / 'src'), str(unit), '-o', str(executable)],
                capture_output=True, env=environment, timeout=120)
            (case / 'build.log').write_bytes(built.stdout + built.stderr)
            built.check_returncode()
            result = subprocess.run([str(executable)], capture_output=True, env=environment, timeout=30)
            (case / 'probe.log').write_bytes(result.stdout + result.stderr)
            report['cases'].append(dict(name=name, exit_code=result.returncode))
            if (result.returncode != 0) != bool(mutation):
                raise ValueError('Baseline or mutation verdict differs: ' + name)
            print(json.dumps(report['cases'][-1]), flush=True)
        report['protected_inputs_preserved'] = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest
                                                  for p, digest in protected.items())
        if not report['protected_inputs_preserved']:
            raise ValueError('Production source changed during mutation checks')
        report.update(status='passed', mutations_detected=len(MUTATIONS))
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('vga_dac_mutations=ok detected=7 baseline=1 production_source_preserved=1', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    run(args.out, args.cxx)
