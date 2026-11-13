"""Observe natural physical-key IRQ1 execution with an unchanged game and read-only host."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time

from PIL import Image, ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_capture_contract import read_canonical_assets, validate_geometry
from keyboard_irq_probe.trace import inspect_trace
from keyboard_irq_probe.contract import finalize_assets, require_success

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--inside-xvfb', action='store_true')
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--dosbox', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
if not args.inside_xvfb:
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1', TMPDIR='/dev/shm')
    environment.pop('SDL_VIDEODRIVER', None)
    raise SystemExit(subprocess.run(['xvfb-run', '-a', '-s', '-screen 0 1024x768x24 -extension MIT-SHM',
        sys.executable, '-B', __file__, '--inside-xvfb', '--repo', str(args.repo), '--dosbox', str(args.dosbox),
        '--out', str(args.out)], env=environment).returncode)

root, host, out = args.repo.resolve(strict=True), args.dosbox.resolve(strict=True), args.out.resolve()
assert out.is_relative_to(Path('/dev/shm')) and not out.exists() and os.environ['SDL_AUDIODRIVER'] == 'dummy'
usage = shutil.disk_usage('/dev/shm')
assert usage.used + 24 * 1024**2 < usage.total * 0.90
canonical = read_canonical_assets(root)
sha = lambda raw: hashlib.sha256(raw).hexdigest()
host_build = json.loads((host.parents[2] / 'build.json').read_bytes())
source = Path(__file__).parent
assert host_build['host_sha256'] == sha(host.read_bytes()) and host_build['build_exit'] == 0
assert host_build['probe_sha256'] == sha((source / 'lezac_work_probe.h').read_bytes())
assert host_build['keyboard_irq_sources'] == {name: sha((source / name).read_bytes())
    for name in ('keyboard_irq_api.h', 'keyboard_irq_observation.inc')}
assert host_build['cpu_source_unchanged'] and host_build['keyboard_append_only'] and host_build['guest_instruction_patches'] == 0
out.mkdir()
run = out / 'run'
run.mkdir()
for name, raw in canonical.items():
    (run / name).write_bytes(raw)
assets = {name: dict(bytes=len(raw), sha256=sha(raw)) for name, raw in canonical.items()}
exe = canonical['LEZAC.EXE']
assert sha(exe) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
mz = struct.unpack_from('<14H', exe)
locator = root / 'tools/seed_original_level.py'
assert sha(locator.read_bytes()) == 'b2e6a4fc80e6e612718baf10ff4aabc8e2c438524f5d24547b9a97fd483551fe'
spec = importlib.util.spec_from_file_location('keyboard_irq_read_only_locator', locator)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
conf = out / 'dosbox.conf'
conf.write_text('[sdl]\nfullscreen=false\noutput=surface\n[render]\nframeskip=0\naspect=false\nscaler=none\n'
    '[cpu]\ncore=normal\ncycles=fixed 6000\n[mixer]\nnosound=true\n[speaker]\npcspeaker=false\n'
    '[sblaster]\nsbtype=none\n[midi]\nmpu401=none\nmididevice=none\n[dos]\nkeyboardlayout=none\n')
report = dict(schema='lezac-original-keyboard-irq-v1', status='capturing', passed=False, assets=assets,
    executable_sha256=sha(exe), dosbox_sha256=sha(host.read_bytes()), host_build=host_build,
    sources={str(path.relative_to(root)): sha(path.read_bytes()) for path in
        [source / name for name in ('capture.py', 'trace.py', 'rebuild.py', 'contract.py', 'lezac_work_probe.h',
         'keyboard_irq_api.h', 'keyboard_irq_observation.inc')] + [root / 'tools/original_capture_contract.py', locator]},
    process_memory_writes=0, process_memory_opened_read_only=True, process_pauses=0,
    guest_instruction_patches=0, calls_stubbed=0, gameplay_state_seeded=False, input_bytes_seeded=False,
    host_probe_guest_register_writes=0, host_probe_guest_memory_writes=0,
    audio='dummy', original_executable_changed=False, arithmetic_flags_claim=False,
    cpu_ram_rgb_atomic=False, whole_game_claim=False, keyboard_layout='none',
    bios_observation_bytes=152, events=[], host_commands=[], samples=[])
for name, digest in report['sources'].items():
    target = out / 'source-tree' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / name, target)
    assert sha(target.read_bytes()) == digest
child = mem = log = None
base = data_address = cs = ds = window = None
started = time.monotonic()


def persist():
    raw = (json.dumps(report, indent=2) + '\n').encode()
    assert len(raw) < 1048576
    (out / 'report.json').write_bytes(raw)


def xdo(*arguments):
    command = ['xdotool', *map(str, arguments)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=5)
    report['host_commands'].append(dict(command=command, exit=result.returncode, stdout=result.stdout,
        stderr=result.stderr, elapsed=time.monotonic() - started))
    persist()
    result.check_returncode()
    return result.stdout.strip()


def key(name, hold=None):
    before = time.monotonic() - started
    xdo('windowfocus', window)
    if hold is None:
        xdo('key', '--clearmodifiers', name)
    else:
        xdo('keydown', '--clearmodifiers', name)
        time.sleep(hold)
        xdo('keyup', name)
    report['events'].append(dict(key=name, hold_seconds=hold, before=before,
                                after=time.monotonic() - started, utc=datetime.now(timezone.utc).isoformat()))
    persist()


def sample(name):
    ram = os.pread(mem.fileno(), 1048576, base)
    assert len(ram) == 1048576
    image = bytearray(exe[0x770:])
    for index in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + cs) & 65535)
    assert ram[cs * 16:cs * 16 + 43552] == image[:43552]
    compressed = gzip.compress(ram, mtime=0)
    (out / (name + '.ram.gz')).write_bytes(compressed)
    geometry = validate_geometry(xdo('getwindowgeometry', '--shell', window), window)
    x, y, width, height = (int(geometry[field]) for field in ('X', 'Y', 'WIDTH', 'HEIGHT'))
    assert (width, height) == (320, 200)
    frame = ImageGrab.grab(xdisplay=os.environ['DISPLAY']).crop((x, y, x + width, y + height)).convert('RGB')
    frame.save(out / (name + '.png'))
    frame.resize((960, 600), Image.Resampling.NEAREST).save(out / (name + '-preview.png'))
    result = dict(name=name, ram_sha256=sha(ram), ram_gzip_sha256=sha(compressed),
        png_sha256=sha((out / (name + '.png')).read_bytes()), pixels_sha256=sha(frame.tobytes()),
        frame=struct.unpack_from('<H', ram, ds * 16 + 0x78c2)[0], level=ram[ds * 16 + 0x79b7],
        code_bytes_verified=43552, elapsed=time.monotonic() - started)
    report['samples'].append(result)
    persist()
    print(json.dumps(result), flush=True)
    return result


try:
    (out / 'home').mkdir()
    (out / 'tmp').mkdir()
    environment = dict(PATH='/usr/bin:/bin', HOME=str(out / 'home'), TMPDIR=str(out / 'tmp'), LANG='C.UTF-8',
        LC_ALL='C.UTF-8', DISPLAY=os.environ['DISPLAY'], XAUTHORITY=os.environ['XAUTHORITY'],
        SDL_VIDEODRIVER='x11', SDL_AUDIODRIVER='dummy', LEZAC_KEYBOARD_IRQ_TRACE=str(out / 'irq.csv.gz'),
        LEZAC_KEYBOARD_IRQ_ARMED=str(out / 'armed.txt'), LEZAC_KEYBOARD_IRQ_TARGET=str(out / 'target-complete.txt'))
    command = [str(host), '-conf', str(conf), '-c', 'mount c ' + str(run), '-c', 'c:', '-c', 'LEZAC.EXE']
    report.update(dosbox_argv=command, dosbox_environment=environment, environment_is_complete=True,
                  dosbox_config=conf.read_text(), dosbox_cwd=str(out))
    log = (out / 'dosbox.log').open('xb')
    child = subprocess.Popen(command, cwd=out, env=environment, stdout=log, stderr=log)
    report['child_pid'] = child.pid
    deadline = time.monotonic() + 20
    candidates = []
    while time.monotonic() < deadline:
        assert child.poll() is None
        candidates = []
        for address in helper.scan_process(child.pid, helper.DATA_SIGNATURE):
            data = address - helper.DATA_STRING_OFFSET
            with open('/proc/%d/mem' % child.pid, 'rb', buffering=0) as probe:
                callback = os.pread(probe.fileno(), 4, data + 0x1aea)
                if len(callback) != 4:
                    continue
                offset, segment = struct.unpack('<HH', callback)
                code, data_segment = segment - 0x920, segment - 0x920 + 0xaa2
                if offset == 0xa9 and 16 < code < data_segment < 0xa000:
                    ram_base = data - data_segment * 16
                    if os.pread(probe.fileno(), 2, ram_base + (code - 16) * 16) == b'\xcd\x20':
                        candidates.append((ram_base, data, code, data_segment))
        candidates = sorted(set(candidates))
        if len(candidates) == 1:
            base, data_address, cs, ds = candidates[0]
            break
        time.sleep(.05)
    assert len(candidates) == 1
    mem = open('/proc/%d/mem' % child.pid, 'rb', buffering=0)
    window = xdo('search', '--pid', child.pid, '--name', 'DOSBox').splitlines()[-1]
    xdo('windowfocus', window)
    result = subprocess.run(['xset', 'r', 'off'], capture_output=True, text=True, timeout=5)
    result.check_returncode()
    report.update(code_segment=cs, data_segment=ds, ram_base=base, private_xvfb_autorepeat_disabled=True)
    time.sleep(20)
    sample('main')
    key('1')
    time.sleep(4)
    sample('intro')
    key('Return')
    time.sleep(1)
    gameplay = sample('gameplay')
    assert gameplay['frame'] > 0 and gameplay['level'] == 1
    (out / 'armed.txt').write_text('1\n')
    key('z', 1.3)
    time.sleep(.1)
    for name in ('x', 'm', 'n', 'c', 'Left', 'Right', 'Insert', 'Up', 'Down', 'e', 'r', 'a'):
        key(name)
        time.sleep(.1)
    sample('after-input')
    deadline = time.monotonic() + 15
    while not (out / 'target-complete.txt').exists() and time.monotonic() < deadline:
        assert child.poll() is None
        usage = shutil.disk_usage('/dev/shm')
        assert usage.used < usage.total * 0.90 - 4 * 1024**2
        time.sleep(.1)
    assert (out / 'target-complete.txt').read_text() == '1\n'
    xdo('key', '--clearmodifiers', 'ctrl+F9')
    child.wait(timeout=10)
    assert child.returncode == 0
    report.update(inspect_trace(out / 'irq.csv.gz'))
    assert report['validated_target_completed']
    report.update(status='observed', passed=True)
except BaseException as error:
    report.update(status='failed', passed=False, error=repr(error))
    raise
finally:
    if child and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
    if mem:
        mem.close()
    if log:
        log.close()
    report['child_exit_code'] = child.returncode if child else None
    trace = out / 'irq.csv.gz'
    if trace.exists():
        raw = trace.read_bytes()
        report.update(trace_sha256=sha(raw), trace_bytes=len(raw))
    finalize_assets(root, canonical, report)
    if report['child_exit_code'] != 0:
        report.update(status='failed', passed=False)
    persist()
    print(json.dumps(dict(status=report['status'], root=str(out), states=report.get('states'),
                          child_exit_code=report['child_exit_code'])), flush=True)
    if sys.exc_info()[0] is None:
        require_success(report)
