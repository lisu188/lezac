"""Execute unchanged pinned BIOS keyboard functions under a declared no-layout VGA profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--sdk', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
source, sdk, out = args.source.resolve(strict=True), args.sdk.resolve(strict=True), args.out.resolve()
assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
usage = shutil.disk_usage('/dev/shm')
assert usage.used + 24 * 1024**2 < usage.total * 0.90
sha = lambda raw: hashlib.sha256(raw).hexdigest()
path = source / 'src/ints/bios_keyboard.cpp'
raw = path.read_bytes()
assert sha(raw) == '880ef5796c968db80b7e0d23f2d5f68e86fd3d065b40f141bd77642ad2d89416'
text = raw.decode()
markers = ['#define none 0', 'bool BIOS_AddKeyToBuffer(Bit16u code) {', 'static bool get_key(',
           'static Bitu IRQ1_Handler(void) {', '/* check whether key combination is enhanced or not,']
assert all(text.count(marker) == 1 for marker in markers)
table = text[text.index(markers[0]):text.index(markers[1])]
buffer = text[text.index(markers[1]):text.index(markers[2])]
handler = text[text.index(markers[3]):text.index(markers[4])]
driver_path = Path(__file__).with_name('bios_oracle_driver.cpp')
driver = driver_path.read_text()
assert driver.count('// ORIGINAL_FUNCTIONS') == 1
generated = driver.replace('// ORIGINAL_FUNCTIONS', table + '\n' + buffer + '\n' + handler)
out.mkdir()
(out / 'oracle.cpp').write_text(generated)
version = sdk / 'usr/include/SDL/SDL_version.h'
assert version.is_file()
environment = dict(PATH='/usr/bin:/bin', TMPDIR=str(out), LANG='C.UTF-8', LC_ALL='C.UTF-8',
                   SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy')
command = ['c++', '-std=c++23', '-O2', '-I' + str(version.parent), str(out / 'oracle.cpp'), '-o', str(out / 'oracle')]
result = subprocess.run(command, env=environment, capture_output=True, timeout=90)
(out / 'build.log').write_bytes(result.stdout + result.stderr)
result.check_returncode()
with (out / 'oracle.bin').open('xb') as stream:
    result = subprocess.run([str(out / 'oracle')], env=environment, stdout=stream, stderr=subprocess.PIPE, timeout=30)
(out / 'run.log').write_bytes(result.stderr)
result.check_returncode()
record = dict(schema='lezac-bios-keyboard-function-oracle-v1', cases=65536, source_sha256=sha(raw),
    table_sha256=sha(table.encode()), buffer_functions_sha256=sha(buffer.encode()), handler_sha256=sha(handler.encode()),
    driver_sha256=sha(driver_path.read_bytes()), producer_sha256=sha(Path(__file__).read_bytes()),
    generated_source_sha256=sha(generated.encode()), binary_sha256=sha((out / 'oracle').read_bytes()),
    oracle_sha256=sha((out / 'oracle.bin').read_bytes()), oracle_bytes=(out / 'oracle.bin').stat().st_size,
    sdl_version_header_sha256=sha(version.read_bytes()), build_argv=command,
    build_environment=environment, build_environment_is_complete=True,
    original_functions_changed=False, original_host_execution=False, keyboard_layout='none',
    machine=5, can_use_lock=True, pause_callback_idle_is_explicit_handoff=True,
    external_functions='Bounded BIOS memory, no-layout false result, recorded I/O, explicit Pause idle handoff',
    whole_game_claim=False)
(out / 'report.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
