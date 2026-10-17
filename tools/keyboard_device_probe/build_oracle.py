"""Compile unchanged original keyboard-controller functions under recorded effect adapters."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
source, out = args.source.resolve(strict=True), args.out.resolve()
assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
usage = shutil.disk_usage('/dev/shm')
assert usage.used + 16 * 1024**2 < usage.total * .90
sha = lambda raw: hashlib.sha256(raw).hexdigest()
pins = {'src/hardware/keyboard.cpp': 'd3ee2544a1cef6c4006e634ceb0729d550f755a6c1fe5aff20020f6e196d5afd',
        'include/keyboard.h': 'e1badf7a53fd38441077402419102e716764b9116f5f6e684f8c9d51cd8b0009'}
raw = {name: (source / name).read_bytes() for name in pins}
assert all(sha(raw[name]) == digest for name, digest in pins.items())
body, header = raw['src/hardware/keyboard.cpp'].decode(), raw['include/keyboard.h'].decode()
assert body.count('#define KEYBUFSIZE 32') == body.count('void KEYBOARD_Init(Section* sec) {') == 1
functions = body[body.index('#define KEYBUFSIZE 32'):body.index('void KEYBOARD_Init(Section* sec) {')]
enum = header[header.index('enum KBD_KEYS {'):header.index('};') + 2]
driver_path = Path(__file__).with_name('oracle_driver.cpp')
driver = driver_path.read_text()
assert driver.count('// ORIGINAL_ENUM') == driver.count('// ORIGINAL_FUNCTIONS') == 1
generated = driver.replace('// ORIGINAL_ENUM', enum).replace('// ORIGINAL_FUNCTIONS', functions)
out.mkdir()
(out / 'oracle.cpp').write_text(generated)
environment = dict(PATH='/usr/bin:/bin', TMPDIR=str(out), LANG='C.UTF-8', LC_ALL='C.UTF-8',
                   SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
command = ['c++', '-std=c++23', '-O2', str(out / 'oracle.cpp'), '-o', str(out / 'oracle')]
result = subprocess.run(command, env=environment, capture_output=True, timeout=90)
(out / 'build.log').write_bytes(result.stdout + result.stderr)
result.check_returncode()
with (out / 'oracle.bin').open('xb') as stream:
    result = subprocess.run([str(out / 'oracle')], env=environment, stdout=stream, stderr=subprocess.PIPE, timeout=30)
(out / 'run.log').write_bytes(result.stderr)
result.check_returncode()
report = dict(schema='lezac-keyboard-device-function-oracle-v1', cases=31296, original_source_sha256=pins,
    enum_sha256=sha(enum.encode()), functions_sha256=sha(functions.encode()),
    driver_sha256=sha(driver_path.read_bytes()), producer_sha256=sha(Path(__file__).read_bytes()),
    generated_source_sha256=sha(generated.encode()), binary_sha256=sha((out / 'oracle').read_bytes()),
    oracle_sha256=sha((out / 'oracle.bin').read_bytes()), oracle_bytes=(out / 'oracle.bin').stat().st_size,
    build_argv=command, complete_environment=environment, original_functions_changed=False,
    original_host_execution=False, machine='VGA',
    adapters='Recorded PIC scheduling/removal/IRQ, A20, gate2/speaker effects; logging discarded',
    app_cadence_claim=False, whole_game_claim=False)
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report), flush=True)
