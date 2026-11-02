"""Capture four natural original frames, retaining no full guest RAM artifact."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import socket
import struct
import subprocess
import sys
import time

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from original_capture_contract import read_canonical_assets
from frame_active_live_probe.trace import rows
from frame_active_live_probe.project import clock_projection
from frame_iteration_live_probe.transport import receive

sha = lambda raw: hashlib.sha256(raw).hexdigest()
REGS = 'ax bx cx dx si di bp cs ds es ss sp ip'.split()


def project(trace, memories, out, verifier, report):
    metadata = {}
    entry = previous = None
    states = bytearray()
    count = boundaries = irqs = 0
    game = None
    endpoints = []
    for row in rows(trace, metadata):
        kind = row['kind']
        if entry and entry.get('completed'):
            raise ValueError('Original trace continued after the final frame endpoint')
        if kind == 'identified':
            if game is not None:
                raise ValueError('Duplicate original identification')
            game = int(row['cs'])
            continue
        if game is None or int(row['call']) != 1:
            raise ValueError('Original iteration identity differs')
        if kind == 'keyboard_enter':
            if entry is not None or count or int(row['ip']) != 0x7903 or int(row['cs']) != game:
                raise ValueError('Original iteration entry differs')
            entry = row
            previous = int(row['dispatch']) - 1
            continue
        if entry is None or int(row['dispatch']) != previous + 1:
            raise ValueError('Original iteration dispatch is not contiguous')
        previous = int(row['dispatch'])
        if (int(row['cs']), int(row['ip'])) == (game, 0x7903):
            boundaries += 1
            endpoints.append(count)
        irqs += (int(row['cs']), int(row['ip'])) == (0xf000, 0xfea5)
        states.extend(struct.pack('<13H2I', *[int(row[key]) for key in REGS],
                                  int(row['flags']), int(row['defined_flags'])))
        opcode = bytes.fromhex(row['opcode'])
        if len(opcode) != 8:
            raise ValueError('Original opcode scope differs')
        states.extend(opcode)
        count += 1
        if kind == 'keyboard_return':
            if boundaries != 5 or row['target_completed'] != '1':
                raise ValueError('Four-frame original endpoint differs')
            entry['completed'] = True
    if not entry or not entry.get('completed') or count < 2 or count > 2000001 or not irqs:
        raise ValueError('Original four-frame window is incomplete')
    exe = read_canonical_assets(ROOT)['LEZAC.EXE']
    expected = bytearray(exe[0x770:])
    mz = struct.unpack_from('<14H', exe)
    for index in range(mz[3]):
        offset, segment = struct.unpack_from('<HH', exe, mz[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', expected, at, (struct.unpack_from('<H', expected, at)[0] + game) & 65535)
    if any(memory[game * 16:game * 16 + 43552] != expected[:43552] for memory in memories):
        raise ValueError('Original relocated executable changed')
    counters = [struct.unpack_from('<H', memory, int(entry['ds']) * 16 + 0x78c2)[0] for memory in memories]
    if (counters[1] - counters[0]) & 65535 != 4:
        raise ValueError('Original frame counter did not advance by four')
    cpu = bytearray(b'LZFILV01' + struct.pack('<I4H2I', 1, game, int(entry['vector_ip']),
                    int(entry['keyboard_base']), int(entry['psp']), int(entry['id_toggle']), count))
    cpu.extend(memories[0]);cpu.extend(memories[1]);cpu.extend(states)
    clock = clock_projection(trace, [dict(states=count)])
    clock_path = out / 'clock.bin'
    clock_path.write_bytes(clock)
    palette = bytes.fromhex(row['render_palette'].split(';')[4])
    rgb_palette = [tuple(palette[i + j] for j in (1, 2, 3)) for i in range(0, 1024, 4)]
    image = Image.new('RGB', (320, 200))
    image.putdata([rgb_palette[index] for index in memories[1][0xa0000:0xa0000 + 64000]])
    image.save(out / 'original-final.png')
    report['original_final_rgb_sha256'] = sha(image.tobytes())
    report.update(metadata, states=count, original_frames=4, original_irq_entries=irqs,
                  original_frame_boundaries=endpoints, memory_sha256=[sha(x) for x in memories],
                  original_frame_counters=counters,
                  cpu_projection_sha256=sha(cpu), clock_projection_sha256=sha(clock),
                  initial_memory_only_as_input=True, later_state_injected=False,
                  complete_original_code_bytes_verified=43552)
    # The CPU projection contains endpoint RAM, so it exists only as bytes and a pipe.
    result = subprocess.run([str(verifier), '/proc/self/fd/0', str(clock_path), str(out / 'cpp-final')], input=cpu,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900,
                            env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'))
    report['verifier'] = dict(exit_code=result.returncode, stdout=result.stdout.decode(), stderr=result.stderr.decode(),
                              sha256=sha(verifier.read_bytes()))
    (out / 'verifier.log').write_bytes(result.stdout + result.stderr)
    result.check_returncode()
    cpp_rgb = (out / 'cpp-final.rgb').read_bytes()
    cpp = Image.frombytes('RGB', (320, 200), cpp_rgb)
    cpp.save(out / 'cpp-final.png')
    differing = sum(a != b for a, b in zip(image.getdata(), cpp.getdata()))
    report.update(cpp_final_rgb_sha256=sha(cpp_rgb), differing_pixels=differing)
    if differing:
        raise ValueError('Computed full-frame final pixels differ')


def capture(args):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    out = args.out.resolve()
    host = args.dosbox.resolve(strict=True)
    verifier = args.verifier.resolve(strict=True)
    if out.exists() or not out.is_relative_to(Path('/dev/shm')) or shutil.disk_usage('/dev/shm').free < 2 * 1024**3:
        raise ValueError('Use a fresh RAM directory with 2 GiB reserve')
    build_path = host.parents[2] / 'build.json'
    build = json.loads(build_path.read_bytes())
    if (build['schema'], build['status'], build['build_exit'], build['host_sha256']) != (
            'lezac-iteration-stream-observer-v1', 'built', 0, sha(host.read_bytes())):
        raise ValueError('Original observer identity differs')
    if build['iteration_builder_sha256'] != sha(Path(__file__).with_name('build.py').read_bytes()):
        raise ValueError('Observer builder changed')
    for name, digest in build['compiled_source_hashes'].items():
        if sha((host.parents[1] / name).read_bytes()) != digest:
            raise ValueError('Observer compiler input changed: ' + name)
    canonical = read_canonical_assets(ROOT)
    protected = {str(path): sha(path.read_bytes()) for path in sorted((ROOT / 'src/core').glob('*')) if path.is_file()}
    for path in (verifier, host, build_path, Path(__file__), Path(__file__).with_name('transport.py'),
                 Path(__file__).with_name('build.py'), Path(__file__).with_name('memory_stream.h'),
                 ROOT / 'tests/core/frame_active_live_test.cpp', ROOT / 'tools/frame_active_live_probe/trace.py',
                 ROOT / 'tools/frame_active_live_probe/project.py', ROOT / 'tools/original_capture_contract.py'):
        protected[str(path)] = sha(path.read_bytes())
    out.mkdir();run = out / 'run';run.mkdir();(out / 'home').mkdir();(out / 'tmp').mkdir()
    for name, raw in canonical.items():
        (run / name).write_bytes(raw)
    config = out / 'dosbox.conf'
    config.write_text('[sdl]\nfullscreen=false\noutput=surface\n[render]\nframeskip=0\naspect=false\nscaler=none\n'
                      '[cpu]\ncore=normal\ncycles=fixed 6000\n[mixer]\nnosound=true\n[speaker]\npcspeaker=false\n'
                      '[sblaster]\nsbtype=none\n[midi]\nmpu401=none\nmididevice=none\n')
    report = dict(schema='lezac-natural-four-frame-stream-v1', status='capturing', passed=False,
                  full_ram_artifacts=0, core_dumps_enabled=False, guest_memory_streamed_internally=True,
                  guest_instruction_patches=0, process_memory_writes=0, process_pauses=0,
                  gameplay_state_seeded=False, clock_or_irq_state_seeded=False, audio='dummy',
                  physical_keyboard_claim=False, actual_app_integration=False, whole_game_parity=False,
                  producer_sha256=sha(Path(__file__).read_bytes()), host_build_sha256=sha(build_path.read_bytes()),
                  dosbox_sha256=sha(host.read_bytes()), protected_inputs_sha256=protected, commands=[])
    child = None
    parent, inherited = socket.socketpair()
    parent.settimeout(600)
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(receive, parent)
    started = time.monotonic()

    def xdo(*parts):
        result = subprocess.run(['xdotool', *map(str, parts)], capture_output=True, text=True, timeout=10)
        report['commands'].append(dict(argv=result.args, exit_code=result.returncode, stdout=result.stdout,
                                       stderr=result.stderr, monotonic=time.monotonic() - started))
        result.check_returncode()
        return result.stdout.strip()

    try:
        environment = dict(PATH='/usr/bin:/bin', HOME=str(out / 'home'), TMPDIR=str(out / 'tmp'),
            LANG='C.UTF-8', LC_ALL='C.UTF-8', DISPLAY=os.environ['DISPLAY'], XAUTHORITY=os.environ['XAUTHORITY'],
            SDL_VIDEODRIVER='x11', SDL_AUDIODRIVER='dummy', LEZAC_ACTIVE_MEMORY_FD=str(inherited.fileno()),
            LEZAC_FRAME_FOREGROUND_TRACE=str(out / 'trace.csv.gz'),
            LEZAC_FRAME_FOREGROUND_TARGET=str(out / 'complete.txt'))
        command = [str(host), '-conf', str(config), '-c', 'mount c ' + str(run), '-c', 'c:', '-c', 'LEZAC.EXE']
        report.update(dosbox_environment=environment, dosbox_argv=command, dosbox_cwd=str(out))
        with (out / 'dosbox.log').open('xb') as log:
            child = subprocess.Popen(command, cwd=out, env=environment, pass_fds=(inherited.fileno(),), stdout=log, stderr=log)
            inherited.close()
            deadline = time.monotonic() + 20
            window = ''
            while time.monotonic() < deadline and not window:
                found = subprocess.run(['xdotool', 'search', '--pid', str(child.pid), '--name', 'DOSBox'], capture_output=True, text=True)
                if found.returncode == 0:
                    window = found.stdout.splitlines()[-1]
                else:
                    time.sleep(.1)
            if not window:
                raise ValueError('Original private window did not appear')
            xdo('windowfocus', window)
            subprocess.run(['xset', 'r', 'off'], check=True, capture_output=True, timeout=10)
            observed = dict(value.decode().split('=', 1) for value in
                            Path(f'/proc/{child.pid}/environ').read_bytes().split(b'\0') if value)
            mapped = [line for line in Path(f'/proc/{child.pid}/maps').read_text().splitlines() if 'libSDL-1.2.so' in line]
            if observed != environment or {line.split(maxsplit=5)[5] for line in mapped} != {build['expected_sdl_image']}:
                raise ValueError('Actual child environment or SDL image differs')
            if sha(Path(build['expected_sdl_image']).read_bytes()) != build['sdl_runtime_sha256']:
                raise ValueError('Actual SDL bytes differ')
            report.update(actual_environment_verified=True, actual_sdl_maps=mapped)
            time.sleep(20)
            xdo('key', '--clearmodifiers', '1');time.sleep(4)
            xdo('key', '--clearmodifiers', 'Return')
            deadline = time.monotonic() + 480
            while not (out / 'complete.txt').exists():
                if child.poll() is not None or time.monotonic() > deadline:
                    raise ValueError('Original four-frame observation did not complete')
                time.sleep(.1)
            xdo('key', '--clearmodifiers', 'ctrl+F9')
            child.wait(timeout=10)
        if child.returncode != 0:
            raise ValueError('Original child failed')
        memories = future.result(timeout=10)
        project(out / 'trace.csv.gz', memories, out, verifier, report)
        report.update(status='validated', passed=True)
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        if child and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill();child.wait(timeout=5)
        inherited.close()
        try:
            parent.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        parent.close();executor.shutdown(wait=True)
        report['child_exit_code'] = child.returncode if child else None
        try:
            report['canonical_assets_unchanged'] = read_canonical_assets(ROOT) == canonical
        except (OSError, ValueError) as error:
            report.update(canonical_assets_unchanged=False, canonical_asset_error=repr(error))
        if not report['canonical_assets_unchanged']:
            report.update(status='failed', passed=False, error='Canonical original assets changed')
        try:
            report['protected_inputs_preserved'] = all(sha(Path(path).read_bytes()) == digest for path, digest in protected.items())
            if not report['protected_inputs_preserved']:
                report.update(status='failed', passed=False, error='Protected capture input changed')
        except OSError as error:
            report.update(status='failed', passed=False, protected_inputs_preserved=False, protected_input_error=repr(error))
        forbidden = [str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and (
            p.name.endswith(('.ram', '.ram.gz', '.core')) or p.name == 'core' or p.name == 'cpu.bin')]
        report['forbidden_artifacts'] = forbidden
        if forbidden:
            report.update(status='failed', passed=False, error='Forbidden full memory artifact appeared')
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(dict(status=report['status'], passed=report['passed'], out=str(out))), flush=True)
    if not report['passed']:
        raise ValueError('Stream validation failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dosbox', type=Path, required=True)
    parser.add_argument('--verifier', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    capture(args)
