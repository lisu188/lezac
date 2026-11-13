"""Offline all-uint32 check against the exact pinned host-source expression, not a DOS runtime replay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--count', type=int, default=2**32)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
out = args.out.resolve()
assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
assert 0 < args.count <= 2**32 and shutil.disk_usage('/dev/shm').free > 1024**3
source = args.source.read_bytes()
sha = lambda raw: hashlib.sha256(raw).hexdigest()
assert sha(source) == 'c563c5c0df429350ccba90019252abc0d6bcca2264fa36a3971b512ecd6ac002'
case = source.decode().split('case 0x2c:', 1)[1].split('case 0x2d:', 1)[0]
body = case[case.index('Bitu ticks='):case.index('\n\t\t}')]
wrapper = r'''
#include "core/dos_time.hpp"
#include <cstdint>
#include <iostream>
using Bitu = uint64_t;
using Bit8u = uint8_t;
volatile uint32_t input;
uint32_t mem_readd(unsigned) { return input; }
constexpr unsigned BIOS_TIMER = 0x46c;
__attribute__((noinline)) lezac::core::DosTimeFields reference() {
    uint8_t reg_ch, reg_cl, reg_dh, reg_dl;
@BODY@
    return {reg_ch, reg_cl, reg_dh, reg_dl};
}
int main() {
    for (uint64_t index = 0; index < @COUNT@ULL; ++index) {
        input = static_cast<uint32_t>(index);
        if (reference() != lezac::core::dosTimeFromBiosTicks(static_cast<uint32_t>(index))) {
            std::cerr << "clock_mismatch=" << index << '\n';
            return 1;
        }
    }
    std::cout << "host_expression_clock=ok inputs=@COUNT@ source_expression=1 memory_read_shim=1 full_handler=0\n";
}
'''.replace('@BODY@', body).replace('@COUNT@', str(args.count))
out.mkdir()
(out / 'clock.cpp').write_text(wrapper)
environment = dict(os.environ, TMPDIR='/dev/shm', SDL_AUDIODRIVER='dummy')
command = ['g++', '-std=c++23', '-O3', '-Wall', '-Wextra', '-I' + str(root / 'src'),
           str(out / 'clock.cpp'), '-o', str(out / 'clock')]
report = dict(original_dos_source_sha256=sha(source), extracted_expression_sha256=sha(body.encode()),
    wrapper_sha256=sha(wrapper.encode()), header_sha256=sha((root / 'src/core/dos_time.hpp').read_bytes()),
    inputs=args.count, source_expression=True, memory_read_shim=True, full_handler=False,
    guest_cpu_replay=False, natural_clock=False, whole_game_parity=False, compile_command=command,
    compiler=subprocess.check_output(['g++', '--version'], text=True))
try:
    built = subprocess.run(command, env=environment, capture_output=True, timeout=120)
    (out / 'build.log').write_bytes(built.stdout + built.stderr)
    report['compile_exit'] = built.returncode
    built.check_returncode()
    started = time.monotonic()
    checked = subprocess.run([str(out / 'clock')], env=environment, capture_output=True, timeout=600)
    (out / 'check.log').write_bytes(checked.stdout + checked.stderr)
    report.update(check_exit=checked.returncode, check_seconds=time.monotonic() - started)
    checked.check_returncode()
    report['status'] = 'passed'
except BaseException as error:
    report.update(status='failed', error=repr(error))
    raise
finally:
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
