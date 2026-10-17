"""Append read-only keyboard observation to a verified owned DOSBox build."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--host', type=Path, required=True)
parser.add_argument('--retain', type=Path, required=True)
args = parser.parse_args()
host = args.host.resolve(strict=True)
retain = args.retain.resolve()
assert host.is_relative_to(Path('/dev/shm')) and retain.is_relative_to(Path('/dev/shm')) and not retain.exists()
source = Path(__file__).parent
root = host / 'dosbox-0.74-3'
record = json.loads((host / 'build.json').read_bytes())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
binary, keyboard = root / 'src/dosbox', root / 'src/hardware/keyboard.cpp'
assert sha(binary) == record['host_sha256'] and sha(keyboard) == record['patched_device_sources']['src/hardware/keyboard.cpp']
assert sha(root / 'src/cpu/core_normal.cpp') == record['source_hashes']['src/cpu/core_normal.cpp']
old = {'lezac_work_probe.h': record['probe_sha256'], 'lezac_clock_observation.h': record['clock_api_sha256'], **record['device_fragment_hashes']}
assert all(sha(root / 'src/cpu' / name) == digest for name, digest in old.items())
assert all(sha(root / name) == digest for name, digest in record['patched_device_sources'].items())
users = subprocess.run(['fuser', str(binary)], capture_output=True, text=True)
assert users.returncode == 1 and not users.stdout.strip() and not users.stderr.strip()
usage = shutil.disk_usage('/dev/shm')
assert usage.used + 64 * 1024**2 < usage.total * 0.90
retain.mkdir()
for path, name in [(binary, 'dosbox'), (host / 'build.json', 'build.json'), (keyboard, 'keyboard.cpp'),
                   (root / 'src/cpu/lezac_work_probe.h', 'lezac_work_probe.h')]:
    shutil.copy2(path, retain / name)
    assert sha(path) == sha(retain / name)
for name in ('lezac_work_probe.h', 'keyboard_irq_api.h', 'keyboard_irq_observation.inc'):
    shutil.copy2(source / name, root / 'src/cpu' / name)
before = keyboard.read_text()
include = '\n#include "../cpu/keyboard_irq_observation.inc"\n'
assert before.count(include) <= 1
after = before if include in before else before + include
base_source = before.removesuffix(include)
base_source_sha = hashlib.sha256(base_source.encode()).hexdigest()
assert base_source_sha == record.get('keyboard_base_source_sha256', sha(keyboard))
patch = ''.join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                  fromfile='a/src/hardware/keyboard.cpp', tofile='b/src/hardware/keyboard.cpp'))
patch_path = retain / 'keyboard-getter.patch'
patch_path.write_text(patch)
if patch:
    result = subprocess.run(['patch', '--batch', '--forward', '-p1', '-i', str(patch_path)], cwd=root,
                            capture_output=True, timeout=30)
    (retain / 'patch.log').write_bytes(result.stdout + result.stderr)
    result.check_returncode()
environment = dict(PATH='/usr/bin:/bin', TMPDIR=str(retain), LANG='C.UTF-8', LC_ALL='C.UTF-8')
with (retain / 'build.log').open('xb') as log:
    child = subprocess.Popen(['make', '-j2'], cwd=root, env=environment, stdout=log, stderr=log, start_new_session=True)
    deadline = time.monotonic() + 600
    while child.poll() is None:
        usage = shutil.disk_usage('/dev/shm')
        if usage.used >= usage.total * 0.90 - 4 * 1024**2 or time.monotonic() >= deadline:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=10)
            raise RuntimeError('Owned rebuild storage/time guard reached; evidence retained')
        time.sleep(.1)
assert child.returncode == 0
assert keyboard.read_text() == after
record.update(host_sha256=sha(binary), probe_sha256=sha(source / 'lezac_work_probe.h'),
    keyboard_irq_sources={name: sha(source / name) for name in ('keyboard_irq_api.h', 'keyboard_irq_observation.inc')},
    keyboard_base_source_sha256=base_source_sha, keyboard_append_only=True,
    keyboard_getter_patch_sha256=sha(patch_path), previous_host_retained=str(retain),
    rebuild_producer_sha256=sha(Path(__file__)), build_environment=environment,
    build_environment_is_complete=True, build_exit=0, status='built')
record['patched_device_sources']['src/hardware/keyboard.cpp'] = sha(keyboard)
(host / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(dict(host_sha256=record['host_sha256'], cpu_source_unchanged=True,
                     keyboard_callback_bodies_unchanged=True)), flush=True)
