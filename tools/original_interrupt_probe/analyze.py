"""Validate the pinned original IRQ probe; raw image verification is optional."""
import argparse
import configparser
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from original_capture_contract import ASSET_PINS, validate_geometry

EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
HOST_SHA = 'b2ecf617bea4c1b31ba7da8845b31f448bd0018c6ba60d6fe37fff8d9de9d5a3'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()
TEXT_FIELDS = {'kind', 'opcode', 'stack', 'adjacent'}
FIELDS = 'kind,dispatch,clock,pic_ticks,cs,ip,ds,es,ss,sp,ax,bx,cx,dx,si,di,bp,control_flags,bios_ticks,pending_sound,latched_sound,cycle_max,opcode,stack,adjacent'.split(',')
KINDS = {'identified', 'instruction', 'keyboard_enter', 'timer_enter', 'saved_target_changed',
         'changed_keyboard_target', 'vga_after_changed_keyboard', 'vga_after_changed_timer', 'vga_at_changed_target'}
FLAGS = dict(passed=True, host_instrumented=True, host_probe_guest_register_writes=0,
    host_probe_guest_memory_writes=0, original_executable_changed=False,
    natural_wall_clock_fidelity_claim=False, record_file_fixture_seeded=True, configured_players=1,
    process_memory_opened_read_only=True, process_memory_writes=0, injected_instructions=0,
    process_pauses=0, gameplay_state_seeded=False, clock_rng_or_heap_seeded=False,
    cpu_memory_frame_atomic=False, complete_frame_sequence_claim=False, whole_game_complete=False,
    environment_is_complete=True, private_xvfb_autorepeat_disabled=True, canonical_assets_unchanged=True,
    probe_pre_decode=True, arithmetic_flags_claim=False, vga_guest_read_latch_accesses=0,
    vga_pre_decode_boundary_claim=True, screen_pixels_synchronous_with_probe_claim=False,
    trace_end_marker=True, child_exit_code=0)
PROFILE = dict(sdl=dict(fullscreen='false', output='surface'), render=dict(frameskip='0', aspect='false', scaler='none'),
    cpu=dict(core='normal', cycles='fixed 6000'), mixer=dict(nosound='true'), speaker=dict(pcspeaker='false'),
    sblaster=dict(sbtype='none'), midi=dict(mpu401='none', mididevice='none'))
KEYS = ['1', 'Return', 'Escape', '1', 'q', 'Return', 'r', 'Return']
SAMPLES = ['main', 'intro', 'gameplay', 'game-over', 'record-prompt', 'player1-q',
           'after-commit', 'after-r', 'after-return', 'after-wait']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact(actual, expected, message):
    require(type(actual) is type(expected) and actual == expected, message)


def bounded(path, maximum):
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum, 'Input reserve exceeded')
    return raw


def trace_bytes(path):
    raw = bounded(path, 2 * 1024**2)
    if path.suffix == '.gz':
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            raw = stream.read(2 * 1024**2 + 1)
    require(len(raw) <= 2 * 1024**2, 'Expanded trace reserve exceeded')
    return raw


def validate_recipe(recipe, raw):
    for key, expected in FLAGS.items():
        exact(recipe.get(key), expected, 'IRQ capture scope differs: ' + key)
    for key, expected in dict(schema='lezac-instrumented-irq-chain-v1', status='observed', audio='dummy',
        executable_sha256=EXE_SHA, dosbox_sha256=HOST_SHA,
        producer_sha256=SHA((ROOT / 'tools/original_interrupt_probe/capture.py').read_bytes()),
        vga_snapshot_profile='M_VGA, chained, compatible_chain4, pel_mask=255',
        vga_snapshot_format='64000 chained-VGA indices via ((i & ~3) << 2) + (i & 3), then 256 RGB DAC triples',
        trace_clock='normal-core fixed-cycle budget, sampled before decode',
        trace_dispatch='normal-core iterations; REP may charge multiple cycles per iteration').items():
        exact(recipe.get(key), expected, 'IRQ capture profile differs: ' + key)
    exact(recipe.get('trace_bytes'), len(raw), 'Recipe trace size differs')
    exact(recipe.get('trace_sha256'), SHA(raw), 'Recipe trace hash differs')
    exact(recipe.get('capture_contract_sha256'), SHA((ROOT / 'tools/original_capture_contract.py').read_bytes()),
          'Capture contract differs')
    host = recipe['host_build']
    exact(host.get('probe_sha256'), SHA((ROOT / 'tools/original_interrupt_probe/lezac_work_probe.h').read_bytes()), 'Host probe differs')
    exact(host.get('host_sha256'), HOST_SHA, 'Host build differs')
    exact(host.get('cpu_source_unchanged'), True, 'Host core changed')
    exact(host.get('guest_instruction_patches'), 0, 'Guest instructions patched')
    exact(host.get('build_exit'), 0, 'Host build failed')
    exact(host.get('base_cpu_sha256'), '4aa44efa8c6d8788f23d6bcc29d24beb4a4123d3e442b51f03a03bdbdf8c6516', 'Base core differs')
    exact(host.get('base_host_sha256'), '4d8eaba9db5e3f733b49c35f191eff98f1f5730035f7374c5c703693a080c8ac', 'Base host differs')
    exact(host.get('host_instrumented'), True, 'Host instrumentation scope differs')
    exact(host.get('copied_build_products'), True, 'Host build-product scope differs')
    config = configparser.ConfigParser()
    try:
        config.read_string(recipe['dosbox_config'])
    except configparser.Error as error:
        raise ValueError('IRQ device configuration differs') from error
    require(not config.defaults() and {section: dict(config[section]) for section in config.sections()} == PROFILE,
            'IRQ device configuration differs')
    env = recipe['dosbox_environment']
    require(set(env) == {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'DISPLAY', 'XAUTHORITY',
                         'SDL_VIDEODRIVER', 'SDL_AUDIODRIVER', 'LEZAC_IRQ_TRACE'} and
            all(type(value) is str and value for value in env.values()), 'IRQ environment differs')
    for key, expected in dict(PATH='/usr/bin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8',
                              SDL_VIDEODRIVER='x11', SDL_AUDIODRIVER='dummy').items():
        exact(env[key], expected, 'IRQ environment differs: ' + key)
    cwd = recipe.get('dosbox_cwd')
    require(type(cwd) is str and PurePosixPath(cwd).is_relative_to('/dev/shm') and
            '..' not in PurePosixPath(cwd).parts, 'IRQ launch directory differs')
    for key, suffix in [('HOME', '/home'), ('TMPDIR', '/tmp'), ('LEZAC_IRQ_TRACE', '/guest-irq.csv')]:
        exact(env[key], cwd + suffix, 'IRQ launch environment binding differs: ' + key)
    argv = recipe.get('dosbox_argv')
    require(type(argv) is list and len(argv) == 9 and type(argv[0]) is str and
            PurePosixPath(argv[0]).is_relative_to('/dev/shm') and '..' not in PurePosixPath(argv[0]).parts,
            'IRQ launch executable differs')
    exact(argv[1:], ['-conf', cwd + '/dosbox.conf', '-c', 'mount c ' + cwd + '/run', '-c', 'c:', '-c', 'LEZAC.EXE'],
          'IRQ launch command differs')
    exact(recipe.get('input_injection_failures'), [], 'Input injection failed')
    autorepeat = recipe['private_display_autorepeat_command']
    exact(autorepeat.get('command'), ['xset', 'r', 'off'], 'Autorepeat command differs')
    exact(autorepeat.get('exit_code'), 0, 'Autorepeat command failed')
    events = recipe['events']
    require(len(events) == 8 and [event['key'] for event in events] == KEYS, 'IRQ input events differ')
    commands = recipe['host_commands']
    require(len(commands) == 29 and all(type(item['exit_code']) is int and item['exit_code'] == 0 for item in commands),
            'IRQ input commands differ')
    pid, window = recipe['child_pid'], commands[0]['stdout'].splitlines()[-1]
    require(type(pid) is int and pid > 0 and window.isascii() and window.isdecimal() and int(window) > 0,
            'IRQ input target differs')
    focus = ['xdotool', 'windowfocus', window]
    geometry = ['xdotool', 'getwindowgeometry', '--shell', window]
    expected = [['xdotool', 'search', '--pid', str(pid), '--name', 'DOSBox'], focus, geometry]
    for key in KEYS:
        expected.extend([focus, ['xdotool', 'key', '--clearmodifiers', key], geometry])
    expected.extend([geometry, ['xdotool', 'key', '--clearmodifiers', 'ctrl+F9']])
    require([item['command'] for item in commands] == expected, 'IRQ input commands differ')
    for index in [2, *range(5, 27, 3), 27]:
        validate_geometry(commands[index].get('stdout'), window)
    samples = recipe['samples']
    require(len(samples) == 10 and all(type(item['code_bytes_verified']) is int and item['code_bytes_verified'] == 43552 and
            type(item['code_differences']) is int and item['code_differences'] == 0 and
            item['ram_rgb_cpu_atomic'] is False for item in samples), 'IRQ original code/checkpoint scope differs')
    exact([sample['name'] for sample in samples], SAMPLES, 'IRQ sample names differ')
    def interval(item):
        values = [item.get('monotonic_before'), item.get('monotonic_after')]
        require(all(type(value) in (int, float) and 0 <= value <= 3600 and math.isfinite(value) for value in values) and
                values[0] <= values[1], 'IRQ capture interval differs')
        return values
    times = [interval(command) for command in commands]
    require(all(first[1] <= second[0] for first, second in zip(times, times[1:])), 'IRQ command order differs')
    for event, index in zip(events, range(3, 27, 3)):
        before, after = interval(event)
        require(before <= times[index][0] <= times[index+1][1] <= after, 'IRQ command/event binding differs')
    for sample, index in zip(samples, [2, *range(5, 27, 3), 27]):
        before, after = interval(sample)
        require(before <= times[index][0] <= times[index][1] <= after, 'IRQ command/sample binding differs')
    case = recipe['case']
    require(case in ('rank8', 'rank7'), 'Unknown record case')
    exact(recipe['fixture_scores'], [0] * 7 if case == 'rank8' else [0] * 6 + [-1], 'Record fixture differs')
    require(all(type(value) is int for value in recipe['fixture_scores']), 'Record score type differs')
    assets = {name: dict(bytes=size, sha256=pin) for name, (size, pin) in ASSET_PINS.items()}
    require(len(assets) == 14 and set(recipe['assets']) == set(assets), 'Original asset domain differs')
    for name, wanted in assets.items():
        for key, expected in wanted.items():
            exact(recipe['assets'][name].get(key), expected, 'Original asset differs: ' + name)


def analyze(raw, recipe, executable):
    require(0 < len(raw) < 2 * 1024**2 and raw.endswith(b'\nend\n'), 'Incomplete IRQ trace')
    validate_recipe(recipe, raw)
    require(SHA(executable) == EXE_SHA, 'Original executable differs')
    code = recipe['code_segment']
    require(type(code) is int and 16 < code < 0xa000 - 0xaa2 and
            type(recipe['data_segment']) is int and recipe['data_segment'] == code + 0xaa2,
            'Original segment domain differs')
    image = bytearray(executable[0x770:])
    header = struct.unpack_from('<14H', executable)
    require(header[3] == 468 and header[4] * 16 == 0x770, 'Original MZ profile differs')
    for index in range(header[3]):
        offset, segment = struct.unpack_from('<HH', executable, header[12] + index * 4)
        at = segment * 16 + offset
        struct.pack_into('<H', image, at, (struct.unpack_from('<H', image, at)[0] + code) & 65535)
    reader = csv.DictReader(io.StringIO(raw[:-4].decode('ascii')))
    require(reader.fieldnames == FIELDS, 'IRQ trace columns differ')
    rows = []
    for row in reader:
        require(None not in row and all(value is not None for value in row.values()), 'Malformed IRQ row')
        require(row['kind'] in KINDS, 'Unknown IRQ boundary')
        for field, size in [('opcode', 8), ('stack', 64), ('adjacent', 13)]:
            value = row[field]
            require(len(value) == size * 2 and all(letter in '0123456789abcdef' for letter in value), 'IRQ byte span differs')
        for key in set(row) - TEXT_FIELDS:
            row[key] = int(row[key])
            require(row[key] >= 0, 'Negative IRQ value')
            if key not in {'dispatch', 'clock', 'pic_ticks', 'bios_ticks'}:
                require(row[key] <= 65535, 'IRQ word range differs')
        require(row['cycle_max'] == 6000 and row['control_flags'] & ~0x700 == 0, 'IRQ clock/flag scope differs')
        offset = (row['cs'] - code) * 16 + row['ip']
        if 0 <= offset <= 43544:
            require(bytes.fromhex(row['opcode']) == image[offset:offset+8], 'Original trace opcode differs')
        if rows:
            prior = rows[-1]
            require(row['dispatch'] >= prior['dispatch'] and row['clock'] >= prior['clock'], 'IRQ trace order differs')
            if row['dispatch'] == prior['dispatch']:
                require({key: value for key, value in row.items() if key != 'kind'} ==
                        {key: value for key, value in prior.items() if key != 'kind'}, 'Pre-decode state changed without dispatch')
        rows.append(row)
    require(0 < len(rows) <= 4096 and rows[0]['kind'] == 'identified', 'IRQ trace domain differs')
    require((rows[0]['cs'], rows[0]['ip'], rows[0]['ds']) == (code, 0x1fc, code + 0xaa2),
            'Original identification boundary differs')
    changed = [row for row in rows if row['kind'] == 'saved_target_changed']
    faults = [row for row in rows if row['kind'] == 'changed_keyboard_target']
    captures = [row for row in rows if row['kind'].startswith('vga_')]
    require(len(captures) == len(recipe['vga_snapshots']) <= 4, 'VGA snapshot count differs')
    result = dict(case=recipe['case'], trace_rows=len(rows), predecode_guest_state_claim=True,
        arithmetic_flags_claim=False, vga_files_verified=False, full_app_claim=False, whole_game_parity=False)
    if recipe['case'] == 'rank8':
        require(len(changed) == 1 and len(faults) == 16, 'Missing corrupted-handler path')
        first = faults[0]
        saved_ip, saved_cs = struct.unpack_from('<HH', bytes.fromhex(first['adjacent']), 1)
        require((first['ip'], first['cs']) == (saved_ip, saved_cs) == (0, 0x800), 'Corrupted far target differs')
        require(struct.unpack_from('<HH', bytes.fromhex(first['stack'])) == (0x114c, code), 'Far-call return frame differs')
        calls = [row for row in rows if row['kind'] == 'instruction' and row['cs'] == code and row['ip'] == 0x1148 and
                 changed[0]['dispatch'] < row['dispatch'] < first['dispatch']]
        require(calls and calls[-1]['dispatch'] + 1 == first['dispatch'] and calls[-1]['opcode'].startswith('ff1e601b'),
                'Saved keyboard call is not adjacent to its target')
        require(all(row['control_flags'] & 0x200 == 0 and row['ip'] == 0xf699 and row['opcode'].startswith('ffff')
                    for row in faults[1:]), 'Fault loop or interrupt mask differs')
        exceptions = [row for row in rows if row['kind'] == 'instruction' and row['cs'] == 0xf000 and row['ip'] == 0x1060]
        require(exceptions and all(row['opcode'].startswith('fe380300cf') and
            struct.unpack_from('<HH', bytes.fromhex(row['stack'])) == (0xf699, 0x800) for row in exceptions),
            'INT06 return frame differs')
        keyboard = [row for row in captures if row['kind'] == 'vga_after_changed_keyboard']
        require(len(keyboard) == 1, 'Missing pre-decode keyboard VGA state')
        row = keyboard[0]
        ip, cs, flags, start, remaining = struct.unpack_from('<5H', bytes.fromhex(row['stack']))
        require(ip == 0x7ec and cs == code and row['es'] == 0xa000 and row['ax'] == 0 and
            row['di'] == start + 320 - row['cx'] and start % 320 == 0 and remaining == 200 - start // 320,
            'Interrupted clear frame differs')
        terminal = recipe['samples'][-4:]
        require(len({item['bios_ticks'] for item in terminal}) == 1 and len({item['pixels_sha256'] for item in terminal}) == 1 and
            all(item['slot8_bytes'] == '0000000008713a3a3a3a3a3a3a' for item in terminal), 'Rank-eight terminal state differs')
        result.update(destination=row['di'], columns_remaining=row['cx'], row_start=start, rows_remaining=remaining,
            corrupt_call_ip=0x1148, corrupt_target_cs=saved_cs, corrupt_target_ip=saved_ip,
            first_fault_dispatch=faults[1]['dispatch'], fault_ip=0xf699, exception_entries=len(exceptions),
            frozen_rgb_sha256=terminal[0]['pixels_sha256'], bios_ticks_frozen=True)
    else:
        terminal = recipe['samples'][-4:]
        require(not changed and not faults and not captures, 'Rank-seven control reports handler corruption')
        require(all(first['bios_ticks'] < second['bios_ticks'] for first, second in zip(terminal, terminal[1:])),
                'Rank-seven BIOS clock stopped')
        require(len({item['pixels_sha256'] for item in terminal}) == 4 and
                all(item['slot8_bytes'] == rows[0]['adjacent'] for item in terminal), 'Rank-seven control changed handlers')
        result.update(bios_ticks_frozen=False)
    return result, captures


def verify_vga(root, recipe, rows, result):
    from PIL import Image
    compared = []
    for row, item in zip(rows, recipe['vga_snapshots']):
        name = item['name']
        require(name == 'guest-irq.csv.vga-%02d.bin' % len(compared), 'Unsafe VGA filename')
        raw = bounded(root / name, 64768)
        require(len(raw) == 64768 and item['bytes'] == 64768 and SHA(raw) == item['sha256'], 'VGA bytes differ')
        require(all(value < 64 for value in raw[64000:]), 'DAC range differs')
        palette = bytes((value << 2) | (value >> 4) for value in raw[64000:])
        rgb = b''.join(palette[value*3:value*3+3] for value in raw[:64000])
        if row['kind'] != 'vga_after_changed_timer':
            require(SHA(rgb) == result['frozen_rgb_sha256'], 'Pre-decode VGA differs from frozen screen')
        compared.append(dict(name=name, rgb_sha256=SHA(rgb), kind=row['kind']))
    for sample in recipe['samples']:
        png = bounded(root / (sample['name'] + '.png'), 1024**2)
        require(SHA(png) == sample['png_sha256'], 'Screen PNG differs')
        image = Image.open(io.BytesIO(png))
        require(image.size == (320, 200), 'Screen dimensions differ')
        require(SHA(image.convert('RGB').tobytes()) == sample['pixels_sha256'], 'Screen pixels differ')
    result.update(vga_files_verified=bool(compared), screen_pngs_verified=True, vga_comparisons=compared)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--exe', type=Path, default=ROOT / 'LEZAC.EXE')
    parser.add_argument('--capture-root', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    recipe = json.loads(bounded(args.recipe, 1024**2))
    result, rows = analyze(trace_bytes(args.trace), recipe, bounded(args.exe, 1024**2))
    if args.capture_root:
        verify_vga(args.capture_root, recipe, rows, result)
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))
