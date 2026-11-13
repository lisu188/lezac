"""Build the pinned configured observation host in a new RAM directory."""
import argparse
import difflib
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
assert source.is_relative_to(Path('/dev/shm')) and out.is_relative_to(Path('/dev/shm'))
assert not out.exists() and shutil.disk_usage('/dev/shm').free > 2 * 1024**3
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
pins = {
    'src/dosbox': '4d8eaba9db5e3f733b49c35f191eff98f1f5730035f7374c5c703693a080c8ac',
    'src/dos/dos.cpp': 'c563c5c0df429350ccba90019252abc0d6bcca2264fa36a3971b512ecd6ac002',
    'src/cpu/core_normal.cpp': '4aa44efa8c6d8788f23d6bcc29d24beb4a4123d3e442b51f03a03bdbdf8c6516',
    'src/cpu/callback.cpp': '945f1b696b2f031f6f5e4ffc00aecd77103eaf5be4a9cf7051814517ce6e74bf',
    'src/cpu/cpu.cpp': '0e897027875de7eea33a35b9eeefcd5a7cd15facb4a409172e3e712766b08098',
    'include/dos_inc.h': 'c044eedc836ddcd1f18c0f16ad8f62861078fe065cf858094513ffdea9589e3a',
    'config.h': '01aca5c63f5c70af786ea29d8a769b9a475edfcb9a36e2d762af00bbc204f786',
    'src/hardware/pic.cpp': 'f1a6d6b330a24a72440c7f1581ac804530e534714c7f79109f47afce100ae12a',
    'src/hardware/timer.cpp': '6adc0ea61440ff684275172385edc0cc4a1b43f1f32e75a702aaf1c86380793a',
    'include/pic.h': '9b8c4449d68e1619e9620a19a98585354412d0a3c61bd10dbfe9f5f2a6e1a052',
    'src/dosbox.cpp': 'e77e0cbc5c14158984fa77a33a19495640280d2a8f3ec6528bb5619f4e41941b',
    'src/cpu/core_normal/prefix_none.h': '28bc5ff795eaab25672fe46068b0655bda169171e04df710fa6a423baceb9b1c',
    'src/ints/bios.cpp': 'b07734c610138cefb7383782aafdbf49d19dcc95c8b0113555261fcfdd71baa5',
    'src/hardware/iohandler.cpp': 'd7ef9acf52269924d8331b1b46140e5b5f621cc386a7bf733c95b6985d313393',
    'src/hardware/vga_draw.cpp': '1526c501a3d523a68677092b9d75f01eb53eb544d2c557d7150118860050df1e',
    'src/gui/render.cpp': '3bce9f5aded634ec34497a0ee8875e89e0b90cdb7de6e72bbbb81482c09dc7fc',
    'src/hardware/keyboard.cpp': '37a37ca16f09370bdd103aa82348f52526a7d82cb430157c781208acecef804c',
    'src/hardware/mixer.cpp': 'f8a6ff503cd6730dc078688e2a92ce68e93fbcb42b12032e3f815d365320e475',
    'src/ints/bios_keyboard.cpp': '880ef5796c968db80b7e0d23f2d5f68e86fd3d065b40f141bd77642ad2d89416',
}
assert all(sha(source / name) == pin for name, pin in pins.items())
out.mkdir()
root = out / 'dosbox-0.74-3'
shutil.copytree(source, root)
header = Path(__file__).with_name('lezac_work_probe.h')
patch = Path(__file__).with_name('dos_time_hook.patch')
clock_patch = Path(__file__).with_name('clock_hook.patch')
clock_api = Path(__file__).with_name('lezac_clock_observation.h')
shutil.copy2(header, root / 'src/cpu/lezac_work_probe.h')
shutil.copy2(clock_api, root / 'src/cpu/lezac_clock_observation.h')
fragments = {
    'src/hardware/pic.cpp': 'pic_tickers_observation.inc',
    'src/hardware/vga_draw.cpp': 'vga_clock_observation.inc',
    'src/gui/render.cpp': 'render_clock_observation.inc',
    'src/hardware/keyboard.cpp': 'keyboard_clock_observation.inc',
    'src/hardware/mixer.cpp': 'mixer_clock_observation.inc',
}
device_patch = out / 'device-getters.patch'
pieces = []
for name, fragment in fragments.items():
    shutil.copy2(Path(__file__).with_name(fragment), root / 'src/cpu' / fragment)
    before = (source / name).read_text()
    after = before + '\n#include "../cpu/' + fragment + '"\n'
    pieces.extend(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile='a/' + name, tofile='b/' + name))
device_patch.write_text(''.join(pieces))
report = dict(base_host_sha256=pins['src/dosbox'], source_hashes=pins,
    probe_sha256=sha(header), patch_sha256=sha(patch), clock_patch_sha256=sha(clock_patch),
    clock_api_sha256=sha(clock_api), copied_build_products=True,
    host_instrumented=True, guest_instruction_patches=0, source_filesystem='tmpfs', output_filesystem='tmpfs')
report.update(device_fragment_hashes={name: sha(Path(__file__).with_name(name)) for name in fragments.values()},
    device_patch_sha256=sha(device_patch), callback_identity='direct original function pointer equality')
(out / 'preflight.json').write_text(json.dumps(report, indent=2) + '\n')
environment = dict(os.environ, TMPDIR='/dev/shm')
try:
    patched = subprocess.run(['patch', '--batch', '--forward', '-p1', '-i', str(patch)], cwd=root,
        capture_output=True, env=environment, timeout=30)
    (out / 'patch.log').write_bytes(patched.stdout + patched.stderr)
    patched.check_returncode()
    clock_patched = subprocess.run(['patch', '--batch', '--forward', '-p1', '-i', str(clock_patch)], cwd=root,
        capture_output=True, env=environment, timeout=30)
    (out / 'clock-patch.log').write_bytes(clock_patched.stdout + clock_patched.stderr)
    clock_patched.check_returncode()
    device_patched = subprocess.run(['patch', '--batch', '--forward', '-p1', '-i', str(device_patch)], cwd=root,
        capture_output=True, env=environment, timeout=30)
    (out / 'device-patch.log').write_bytes(device_patched.stdout + device_patched.stderr)
    device_patched.check_returncode()
    assert sha(root / 'src/dos/dos.cpp') == '77790a3b5ab163cdf9a0e9cfc26cb5bfc25588898a575e758943097b2a448674'
    built = subprocess.run(['make', '-j2'], cwd=root, capture_output=True, env=environment, timeout=600)
    (out / 'build.log').write_bytes(built.stdout + built.stderr)
    report.update(build_exit=built.returncode, host_sha256=sha(root / 'src/dosbox'),
        patched_dos_sha256=sha(root / 'src/dos/dos.cpp'),
        patched_pic_sha256=sha(root / 'src/hardware/pic.cpp'),
        patched_timer_sha256=sha(root / 'src/hardware/timer.cpp'),
        cpu_source_unchanged=sha(root / 'src/cpu/core_normal.cpp') == pins['src/cpu/core_normal.cpp'])
    report['patched_device_sources'] = {name: sha(root / name) for name in fragments}
    built.check_returncode()
    assert report['cpu_source_unchanged']
except BaseException as error:
    report.update(status='failed', error=repr(error))
    (out / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    raise
report['status'] = 'built'
(out / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2), flush=True)
