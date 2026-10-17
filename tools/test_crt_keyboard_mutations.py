"""Check isolated behavioral faults against the CRT keyboard regression."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {
    'status_saved_if': ('if(function==1) saved|=0x200;', 'if(function==1) saved|=0;'),
    'empty_status_zf': ('|(found?0u:0x40u)', '|(found?0x40u:0u)'),
    'pending_not_cleared': ('case 0x312:bus.writeByte(r.ds,0x7f6d,0);', 'case 0x312:bus.writeByte(r.ds,0x7f6d,1);'),
    'extended_ascii_marker': ('if(scan && ascii==0xe0) key&=0xff00;', 'if(scan && ascii==0xe0) key&=0xffff;'),
    'numpad_enter_scan': ('? 0x1c00u : 0x3500u', '? 0x1d00u : 0x3500u'),
    'idle_loop_extra_sti': ('state_.callbackBase+1u);return;', 'state_.callbackBase+0u);return;'),
    'far_return_swap': ('r.ip=ip;r.cs=cs;state_.outcome=', 'r.ip=cs;r.cs=ip;state_.outcome='),
    'timer_si_restore': ('state_.timer.reset();', 'state_.registers.si=0;state_.timer.reset();'),
    'break_flag_not_cleared': ('case 0x14b:bus.writeByte(r.ds,0x7f6e,0);', 'case 0x14b:bus.writeByte(r.ds,0x7f6e,1);'),
}


def run(compiler, out):
    out = out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a fresh RAM-only mutation output directory')
    if shutil.disk_usage('/dev/shm').free < 256 * 1024 * 1024:
        raise RuntimeError('Insufficient RAM-only mutation reserve')
    source = ROOT / 'src/core/crt_keyboard.hpp'
    raw = source.read_bytes()
    original = raw.decode()
    out.mkdir()
    environment = dict(os.environ, TMPDIR='/dev/shm', PYTHONDONTWRITEBYTECODE='1')
    checker = subprocess.run(['python3', '-S', '-B', str(ROOT / 'tools/check_crt_keyboard_fixture.py'),
        '--cpu', str(out / 'cpu.bin'), '--classification', str(out / 'classification.bin'),
        '--pending', str(out / 'pending.bin')], capture_output=True, env=environment, timeout=60)
    (out / 'fixture.log').write_bytes(checker.stdout + checker.stderr)
    checker.check_returncode()
    probes = [[], ['--original', str(out / 'cpu.bin')], ['--classification', str(out / 'classification.bin')],
        ['--pending-oracle', str(out / 'pending.bin')]]
    report = dict(source_sha256=hashlib.sha256(raw).hexdigest(), cases=[], detected=0, equivalent=0)
    for name, change in [('baseline', None), *MUTATIONS.items()]:
        folder = out / name
        (folder / 'core').mkdir(parents=True)
        text = original
        if change:
            before, after = change
            if text.count(before) != 1:
                raise ValueError('Mutation no longer identifies one expression: ' + name)
            text = text.replace(before, after)
        (folder / 'core/crt_keyboard.hpp').write_text(text)
        executable = folder / 'keyboard'
        command = [compiler, '-std=c++23', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(folder),
            '-I', str(ROOT / 'src'), str(ROOT / 'tests/core/crt_keyboard_test.cpp'), '-o', str(executable)]
        built = subprocess.run(command, capture_output=True, env=environment, timeout=180)
        (folder / 'build.log').write_bytes(built.stdout + built.stderr)
        built.check_returncode()
        failures = []
        for index, arguments in enumerate(probes):
            checked = subprocess.run([str(executable), *arguments], capture_output=True, env=environment, timeout=60)
            (folder / ('probe-' + str(index) + '.log')).write_bytes(checked.stdout + checked.stderr)
            if checked.returncode:
                failures.append(dict(probe=arguments, exit=checked.returncode))
        if name == 'baseline' and failures:
            raise RuntimeError('Unmodified keyboard regression failed')
        if change:
            report['detected' if failures else 'equivalent'] += 1
        report['cases'].append(dict(name=name, failures=failures))
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(dict(name=name, rejected=bool(failures))), flush=True)
    if source.read_bytes() != raw:
        raise RuntimeError('Original keyboard source changed during fault checks')
    if report['detected'] != len(MUTATIONS):
        raise RuntimeError('At least one behavioral mutation survived; retained for inspection')
    print('crt_keyboard_mutations=ok detected=9 baseline_probes=4', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='g++')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.compiler, args.out)
