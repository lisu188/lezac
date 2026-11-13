"""Read-only original IRQ-chain observation with a pre-decode host probe."""
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

parser = argparse.ArgumentParser()
parser.add_argument('--inside-xvfb', action='store_true')
parser.add_argument('--run', required=True)
parser.add_argument('--case', choices=('rank8', 'rank7'), required=True)
parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument('--dosbox', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
assert args.run.isalnum()
if not args.inside_xvfb:
    environment = dict(os.environ, SDL_AUDIODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1', TMPDIR='/dev/shm')
    environment.pop('SDL_VIDEODRIVER', None)
    raise SystemExit(subprocess.run(['xvfb-run', '-a', '-s',
        '-screen 0 1024x768x24 -extension MIT-SHM', sys.executable, '-B', __file__,
        '--inside-xvfb', '--run', args.run, '--case', args.case, '--repo', str(args.repo), '--dosbox', str(args.dosbox),
        '--out', str(args.out)], env=environment).returncode)

ROOT = args.repo.resolve(strict=True)
canonical = read_canonical_assets(ROOT)
OUT = args.out.resolve()
HOST = args.dosbox.resolve(strict=True)
assert OUT.is_relative_to(Path('/dev/shm')), 'This capture is RAM-only'
assert not OUT.exists() and os.environ['SDL_AUDIODRIVER'] == 'dummy'
assert shutil.disk_usage('/dev/shm').free > 1503238553
assert HOST.is_file()
host_build = json.loads((HOST.parents[2] / 'build.json').read_text())
assert host_build['build_exit'] == 0 and host_build['host_sha256'] == hashlib.sha256(HOST.read_bytes()).hexdigest()
assert host_build['probe_sha256'] == hashlib.sha256((ROOT / 'tools/original_interrupt_probe/lezac_work_probe.h').read_bytes()).hexdigest()
assert host_build['cpu_source_unchanged'] is True and host_build['guest_instruction_patches'] == 0
OUT.mkdir()
run = OUT / 'run'
run.mkdir()
CAP = 8388608
sha = lambda raw: hashlib.sha256(raw).hexdigest()
def write(path, raw):
    total = sum(item.stat().st_size for item in OUT.rglob('*') if item.is_file())
    previous = path.stat().st_size if path.exists() else 0
    assert total - previous + len(raw) < CAP, 'Owned evidence reserve exceeded'
    path.write_bytes(raw)

def persist():
    write(OUT / 'report.json', (json.dumps(report, indent=2) + '\n').encode())

def xdo(*args):
    return subprocess.check_output(['xdotool', *map(str, args)], text=True, timeout=5).strip()

def frame():
    geometry = validate_geometry(xdo('getwindowgeometry', '--shell', window), window)
    x, y, width, height = (int(geometry[key]) for key in ('X', 'Y', 'WIDTH', 'HEIGHT'))
    assert (width, height) == (320, 200)
    return ImageGrab.grab(xdisplay=os.environ['DISPLAY']).crop((x, y, x + width, y + height)).convert('RGB')

def png(path, image):
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    write(path, buffer.getvalue())

def sample(name):
    ram = os.pread(mem.fileno(), 1048576, base)
    assert len(ram) == 1048576
    expected = bytearray(exe[0x770:])
    for index in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', expected, at, (struct.unpack_from('<H', expected, at)[0] + cs) & 65535)
    assert ram[cs * 16:cs * 16 + 43552] == expected[:43552]
    image = frame()
    png(OUT / (name + '.png'), image)
    png(OUT / (name + '-preview.png'), image.resize((960, 600), Image.Resampling.NEAREST))
    compressed = gzip.compress(ram, mtime=0)
    write(OUT / (name + '.ram.gz'), compressed)
    memory = ram[ds * 16:ds * 16 + 65536]
    result = dict(name=name, scores=list(struct.unpack_from('<i', memory, address)[0] for address in (0x785a, 0x7888)),
        level=memory[0x79b7], frame_counter=struct.unpack_from('<H', memory, 0x78c2)[0],
        bios_ticks=struct.unpack_from('<I', ram, 0x46c)[0],
        record_bytes=memory[0x1b04:0x1b5f].hex(), slot8_bytes=memory[0x1b5f:0x1b6c].hex(),
        ram_sha256=sha(ram), ram_gzip_sha256=sha(compressed), png_sha256=sha((OUT / (name + '.png')).read_bytes()),
        pixels_sha256=sha(image.tobytes()), code_bytes_verified=43552, code_differences=0)
    report['samples'].append(result)
    persist()
    print(json.dumps(dict(sample=name, scores=result['scores'], pixels_sha256=result['pixels_sha256'])), flush=True)
    return result

def key(value):
    xdo('windowfocus', window)
    xdo('key', '--clearmodifiers', value)
    report['events'].append(dict(key=value, observed_utc=datetime.now(timezone.utc).isoformat()))

assets = {}
for name, raw in canonical.items():
    write(run / name, raw)
    assets[name] = dict(bytes=len(raw), sha256=sha(raw))
assert len(assets) == 14 and sum(item['bytes'] for item in assets.values()) < 1048576
exe = (run / 'LEZAC.EXE').read_bytes()
assert sha(exe) == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
mz = struct.unpack_from('<14H', exe)
assert mz[4] * 16 == 0x770
names = (b'tie-one:', b'tie-two:', b'tie-3:::', b'tie-4:::', b'tie-5:::', b'tie-6:::', b'tie-7:::')
entries = [(0 if args.case == 'rank8' or i < 6 else -1, name) for i, name in enumerate(names)]
fixture = b'\x07' + b''.join(struct.pack('<iB8s', score, 8, name) for score, name in entries)
write(run / 'RECS.DAT', fixture)
write(OUT / 'record-fixture.dat', fixture)
write(OUT / 'producer.py', Path(__file__).read_bytes())
write(OUT / 'capture-contract.py', (Path(__file__).resolve().parents[1] / 'original_capture_contract.py').read_bytes())
locator = ROOT / 'tools/seed_original_level.py'
assert sha(locator.read_bytes()) == 'b2e6a4fc80e6e612718baf10ff4aabc8e2c438524f5d24547b9a97fd483551fe'
spec = importlib.util.spec_from_file_location('work_clock_read_only_locator', locator)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
write(OUT / 'read-only-locator.py', locator.read_bytes())
conf = OUT / 'dosbox.conf'
write(conf, b'[sdl]\nfullscreen=false\noutput=surface\n[render]\nframeskip=0\naspect=false\nscaler=none\n[cpu]\ncore=normal\ncycles=fixed 6000\n[mixer]\nnosound=true\n[speaker]\npcspeaker=false\n[sblaster]\nsbtype=none\n[midi]\nmpu401=none\nmididevice=none\n')
report = dict(schema='lezac-instrumented-irq-chain-v1', status='capturing', run=args.run, case=args.case,
    assets=assets, executable_sha256=sha(exe), dosbox_sha256=sha(HOST.read_bytes()),
    producer_sha256=sha(Path(__file__).read_bytes()), samples=[], events=[],
    capture_contract_sha256=sha((Path(__file__).resolve().parents[1] / 'original_capture_contract.py').read_bytes()),
    host_instrumented=True, host_probe_guest_register_writes=0, host_probe_guest_memory_writes=0,
    original_executable_changed=False, natural_wall_clock_fidelity_claim=False,
    trace_clock='normal-core fixed-cycle budget, sampled before decode',
    trace_dispatch='normal-core iterations; REP may charge multiple cycles per iteration',
    record_file_fixture_seeded=True, fixture_scores=[score for score, _ in entries],
    configured_players=1, audio='dummy', process_memory_opened_read_only=True,
    process_memory_writes=0, injected_instructions=0, process_pauses=0,
    gameplay_state_seeded=False, clock_rng_or_heap_seeded=False, cpu_memory_frame_atomic=False,
    complete_frame_sequence_claim=False, whole_game_complete=False, host_commands=[],
    input_injection_failures=[], capture_argv=list(sys.argv))
report.update(host_build=host_build, probe_pre_decode=True,
    arithmetic_flags_claim=False,
    vga_snapshot_format='64000 chained-VGA indices via ((i & ~3) << 2) + (i & 3), then 256 RGB DAC triples',
    vga_snapshot_profile='M_VGA, chained, compatible_chain4, pel_mask=255',
    vga_guest_read_latch_accesses=0, vga_pre_decode_boundary_claim=True,
    screen_pixels_synchronous_with_probe_claim=False)
child = mem = log = None
base = ds_address = cs = ds = window = None
started = time.monotonic()
historical_key = key
historical_sample = sample

def xdo(*arguments):
    command = ['xdotool', *map(str, arguments)]
    before = time.monotonic() - started
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    entry = dict(command=command, exit_code=result.returncode, stdout=result.stdout,
                 stderr=result.stderr, monotonic_before=before, monotonic_after=time.monotonic() - started)
    report['host_commands'].append(entry)
    if result.returncode:
        report['input_injection_failures'].append(entry)
    persist()
    result.check_returncode()
    return result.stdout.strip()

def sample(name):
    before = time.monotonic() - started
    result = historical_sample(name)
    result.update(monotonic_before=before, monotonic_after=time.monotonic() - started,
                  ram_rgb_cpu_atomic=False)
    persist()
    return result

def key(value):
    before = time.monotonic() - started
    historical_key(value)
    report['events'][-1].update(monotonic_before=before, monotonic_after=time.monotonic() - started)

try:
    log = (OUT / 'dosbox.log').open('xb')
    (OUT / 'home').mkdir()
    (OUT / 'tmp').mkdir()
    child_environment = dict(PATH='/usr/bin:/bin', HOME=str(OUT / 'home'), TMPDIR=str(OUT / 'tmp'),
        LANG='C.UTF-8', LC_ALL='C.UTF-8', DISPLAY=os.environ['DISPLAY'],
        XAUTHORITY=os.environ['XAUTHORITY'], SDL_VIDEODRIVER='x11', SDL_AUDIODRIVER='dummy',
        LEZAC_IRQ_TRACE=str(OUT / 'guest-irq.csv'))
    command = [str(HOST), '-conf', str(conf), '-c', 'mount c ' + str(run), '-c', 'c:', '-c', 'LEZAC.EXE']
    report.update(dosbox_argv=command, dosbox_cwd=str(OUT), dosbox_environment=child_environment,
                  dosbox_config=conf.read_text(), environment_is_complete=True)
    persist()
    child = subprocess.Popen(command, stdout=log, stderr=log, cwd=OUT, env=child_environment)
    report['child_pid'] = child.pid
    deadline = time.monotonic() + 20
    candidates = []
    while time.monotonic() < deadline:
        assert child.poll() is None
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
            base, ds_address, cs, ds = candidates[0]
            break
        time.sleep(.05)
    assert len(candidates) == 1
    mem = open('/proc/%d/mem' % child.pid, 'rb', buffering=0)
    window = xdo('search', '--pid', child.pid, '--name', 'DOSBox').splitlines()[-1]
    xdo('windowfocus', window)
    autorepeat = subprocess.run(['xset', 'r', 'off'], capture_output=True, text=True, timeout=5)
    report['private_display_autorepeat_command'] = dict(command=['xset', 'r', 'off'],
        exit_code=autorepeat.returncode, stdout=autorepeat.stdout, stderr=autorepeat.stderr)
    autorepeat.check_returncode()
    report.update(code_segment=cs, data_segment=ds, ram_base=base,
                  private_xvfb_autorepeat_disabled=True)
    time.sleep(20)
    sample('main')
    key('1')
    time.sleep(4)
    sample('intro')
    key('Return')
    time.sleep(1)
    gameplay = sample('gameplay')
    assert gameplay['scores'] == [0, 0] and gameplay['frame_counter'] > 0
    key('Escape')
    time.sleep(5)
    sample('game-over')
    key('1')
    time.sleep(15)
    sample('record-prompt')
    key('q')
    time.sleep(.2)
    sample('player1-q')
    key('Return')
    time.sleep(3)
    sample('after-commit')
    key('r')
    time.sleep(.2)
    sample('after-r')
    key('Return')
    time.sleep(.5)
    sample('after-return')
    time.sleep(2)
    sample('after-wait')
    write(OUT / 'saved-original.dat', (run / 'RECS.DAT').read_bytes())
    xdo('key', '--clearmodifiers', 'ctrl+F9')
    child.wait(timeout=10)
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
    terminal_errors = []
    trace = OUT / 'guest-irq.csv'
    if trace.exists():
        raw = trace.read_bytes()
        report.update(trace_bytes=len(raw), trace_sha256=sha(raw),
                      trace_end_marker=raw.endswith(b'\nend\n'))
        if report['status'] == 'observed':
            if not report['trace_end_marker'] or child.returncode != 0:
                terminal_errors.append('Incomplete trace or unsuccessful emulator exit')
    elif report['status'] == 'observed':
        terminal_errors.append('No IRQ trace produced')
    try:
        report['canonical_assets_unchanged'] = all(sha((ROOT / name).read_bytes()) == pin['sha256']
                                                  for name, pin in assets.items())
    except OSError as error:
        report.update(canonical_assets_unchanged=False, canonical_asset_check_error=repr(error))
    if not report['canonical_assets_unchanged']:
        terminal_errors.append('Canonical assets changed')
    report['vga_snapshots'] = [dict(name=path.name, bytes=path.stat().st_size, sha256=sha(path.read_bytes()))
                              for path in sorted(OUT.glob('guest-irq.csv.vga-*.bin'))]
    if not all(item['bytes'] == 64768 for item in report['vga_snapshots']):
        terminal_errors.append('Incomplete VGA snapshot')
    if terminal_errors:
        report.update(status='failed', passed=False, terminal_validation_errors=terminal_errors)
        report.setdefault('error', '; '.join(terminal_errors))
    persist()
    print(json.dumps(dict(status=report['status'], root=str(OUT), samples=len(report['samples']),
                          trace_bytes=report.get('trace_bytes'), child_exit_code=report['child_exit_code'])), flush=True)
    if terminal_errors:
        raise RuntimeError('; '.join(terminal_errors))
