"""Validate instrumented normal-core traces without treating dispatches as cycles."""
import argparse
import collections
import configparser
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath

from original_capture_contract import ASSET_PINS, validate_geometry

CAPTURE_HASHES = dict(
    producer_sha256='3dbd83ac74c7409273f53bbacf1556b0491931801ece26e9e250164d8467a30b',
    dosbox_sha256='4d8eaba9db5e3f733b49c35f191eff98f1f5730035f7374c5c703693a080c8ac',
    executable_sha256='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec')
LEGACY_RECIPE_PINS = {
    '1b23903d54c66604cb20854d8b563793c47e0a81aa6e6204b9be21fdc58dcbfa',
    '23b8534774ce23c94992d8fde68aa9d7db51b8323360b80b0bf2aa038ef2e252',
}
FULL_RECIPE_PINS = {
    'db0c014c2bf1aa400a2fd404c6c564035bf2efc57e95cf86a6053fffb1364aef',
    'c13912c95673cdf2d1a52aa35c399afdf3e3dc76ddbe65d47e12798914d66ef1',
}
CAPTURE_CONFIG = dict(sdl=dict(fullscreen='false', output='surface'),
    render=dict(frameskip='0', aspect='false', scaler='none'),
    cpu=dict(core='normal', cycles='fixed 6000'), mixer=dict(nosound='true'),
    speaker=dict(pcspeaker='false'), sblaster=dict(sbtype='none'),
    midi=dict(mpu401='none', mididevice='none'))

COLUMNS = ('kind,page,dispatch,clock,exclusive_dispatch,exclusive_clock,pic_ticks,'
           'cs,ip,ss,sp,bp,frame_valid,index,fraction,phase,destination,h,v,'
           'ax,cx,dx,di,irq_depth,cycle_max,dac,delay_argument,delay_calibration').split(',')
MARKERS = ('horizontal', 'row_check', 'row_work', 'color', 'write', 'after_write', 'tail')
MARKER_IP = dict(zip(MARKERS, (0x251, 0x264, 0x273, 0x2e1, 0x2f9, 0x2fc, 0x2ff)))
EXPECTED_INDICES = {row * 320 + offset for row in range(200) for offset in (0, 1)} | {63998, 63999}
KINDS = set(MARKERS) | {'identified', 'end', 'begin', 'clear_return', 'palette_ready',
    'finish', 'irq8_enter', 'irq8_return', 'irq9_enter', 'irq9_return', 'delay_begin', 'delay_end'}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def read_rows(path):
    with path.open('rb') as stream:
        raw = stream.read(6 * 1024 * 1024 + 1)
    require(len(raw) <= 6 * 1024 * 1024, 'Trace file exceeds size limit')
    if path.suffix == '.gz':
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            raw = stream.read(6 * 1024 * 1024 + 1)
        require(len(raw) <= 6 * 1024 * 1024, 'Expanded trace exceeds size limit')
    source_raw = raw
    with io.StringIO(source_raw.decode('ascii'), newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == COLUMNS, 'Unexpected trace schema')
        rows = []
        for number, raw in enumerate(reader, 2):
            require(None not in raw and all(value is not None for value in raw.values()),
                    f'Incomplete trace row {number}')
            row = dict(raw)
            for key in COLUMNS:
                if key not in ('kind', 'dac'):
                    try:
                        row[key] = int(row[key])
                    except ValueError as error:
                        raise ValueError(f'Invalid integer at row {number}: {key}') from error
            require(row['cycle_max'] == 6000, 'Trace is not fixed 6000 cycles')
            require(len(row['dac']) == 42 and all(c in '0123456789abcdef' for c in row['dac']),
                    'Invalid DAC sample')
            require(row['kind'] in KINDS, 'Unknown marker or producer failure')
            require(all(row[key] >= 0 for key in COLUMNS if key not in ('kind', 'dac', 'fraction')),
                    'Negative unsigned value')
            require(-32768 <= row['fraction'] <= 32767, 'Fraction outside signed word')
            require(all(row[key] <= 65535 for key in ('cs', 'ip', 'ss', 'sp', 'bp', 'phase',
                'destination', 'ax', 'cx', 'dx', 'di', 'delay_argument', 'delay_calibration')),
                    'Guest value outside word')
            require(row['frame_valid'] in (0, 1), 'Invalid frame flag')
            rows.append(row)
    require(rows and rows[0]['kind'] == 'identified' and rows[-1]['kind'] == 'end',
            'Missing identification or clean exit')
    require(sum(row['kind'] == 'identified' for row in rows) == 1
            and sum(row['kind'] == 'end' for row in rows) == 1, 'Duplicate stream boundary')
    for previous, current in zip(rows, rows[1:]):
        for key in ('dispatch', 'clock', 'exclusive_dispatch', 'exclusive_clock', 'pic_ticks'):
            require(current[key] >= previous[key], f'Non-monotonic {key}')
    return rows, source_raw

def delta(begin, end, key='exclusive_dispatch'):
    return end[key] - begin[key]


def validate_provenance(recipe):
    require(all(type(recipe.get(key)) is str and recipe[key] == value
                for key, value in CAPTURE_HASHES.items()), 'Capture host, producer or executable differs')
    assets = recipe.get('assets')
    require(type(assets) is dict and set(assets) == set(ASSET_PINS), 'Capture asset domain differs')
    require(all(type(assets[name]) is dict and set(assets[name]) == {'bytes', 'sha256'} and
        type(assets[name]['bytes']) is int and assets[name]['bytes'] == size and
        type(assets[name]['sha256']) is str and assets[name]['sha256'] == pin
        for name, (size, pin) in ASSET_PINS.items()), 'Canonical capture asset differs')
    common = dict(process_memory_writes=0, process_pauses=0, gameplay_state_seeded=False,
                  clock_rng_or_heap_seeded=False, record_file_fixture_seeded=True,
                  child_exit_code=0, canonical_assets_unchanged=True, audio='dummy')
    require(all(type(recipe.get(key)) is type(value) and recipe[key] == value
                for key, value in common.items()), 'Read-only capture contract differs')
    require(type(recipe.get('fixture_scores')) is list and
            all(type(value) is int for value in recipe['fixture_scores']) and
            recipe['fixture_scores'] == [0, 0, 0, 0, 0, 0, -1], 'Record fixture contract differs')
    config = configparser.ConfigParser()
    try:
        require(type(recipe.get('dosbox_config')) is str, 'Capture profile differs')
        config.read_string(recipe['dosbox_config'])
        require(not config.defaults() and {section: dict(config[section]) for section in config.sections()} ==
                CAPTURE_CONFIG, 'Capture profile differs')
    except configparser.Error as error:
        raise ValueError('Capture profile differs') from error
    try:
        identity = hashlib.sha256(json.dumps(recipe, sort_keys=True, separators=(',', ':'),
                                            allow_nan=False).encode()).hexdigest()
    except (ValueError, TypeError) as error:
        raise ValueError('Capture recipe is not canonical JSON') from error
    # Historical compact recipes omit fields. Only their exact pinned values are accepted.
    if identity in LEGACY_RECIPE_PINS:
        return True
    scope = dict(schema='lezac-instrumented-work-clock-v1', passed=True, host_instrumented=True,
        host_probe_guest_register_writes=0, host_probe_guest_memory_writes=0,
        original_executable_changed=False, natural_wall_clock_fidelity_claim=False,
        injected_instructions=0, configured_players=1, process_memory_opened_read_only=True,
        cpu_memory_frame_atomic=False, complete_frame_sequence_claim=False, whole_game_complete=False,
        trace_end_marker=True, private_xvfb_autorepeat_disabled=True,
        trace_clock='normal-core fixed-cycle budget, sampled before decode',
        trace_dispatch='normal-core iterations; REP may charge multiple cycles per iteration')
    require(all(type(recipe.get(key)) is type(value) and recipe[key] == value
                for key, value in scope.items()), 'Complete capture provenance differs')
    expected_fields = set(common) | set(scope) | set(CAPTURE_HASHES) | {
        'assets', 'capture_argv', 'child_pid', 'code_segment', 'data_segment', 'dosbox_argv',
        'dosbox_config', 'dosbox_cwd', 'dosbox_environment', 'environment_is_complete', 'events',
        'fixture_scores', 'host_commands', 'input_injection_failures', 'private_display_autorepeat_command',
        'ram_base', 'run', 'samples', 'status', 'trace_bytes', 'trace_sha256'}
    require(set(recipe) == expected_fields, 'Complete capture field domain differs')
    require(type(recipe['code_segment']) is int and 16 < recipe['code_segment'] < 65535 and
        type(recipe['data_segment']) is int and recipe['data_segment'] == recipe['code_segment'] + 0xaa2 and
        type(recipe['ram_base']) is int and recipe['ram_base'] >= 0, 'Capture module identity differs')
    autorepeat = recipe.get('private_display_autorepeat_command')
    require(type(autorepeat) is dict and autorepeat.get('command') == ['xset', 'r', 'off'] and
            type(autorepeat.get('exit_code')) is int and autorepeat['exit_code'] == 0,
            'Capture autorepeat contract differs')
    samples = recipe.get('samples')
    require(type(samples) is list and all(type(sample) is dict and
        type(sample.get('code_bytes_verified')) is int and sample['code_bytes_verified'] == 43552 and
        type(sample.get('code_differences')) is int and sample['code_differences'] == 0 and
        sample.get('ram_rgb_cpu_atomic') is False for sample in samples), 'Original code or checkpoint scope differs')
    validate_full_capture_commands(recipe)
    return identity in FULL_RECIPE_PINS


def validate_full_capture_commands(recipe):
    def absolute_path(value):
        require(type(value) is str and value.startswith('/') and not value.startswith('//') and
            str(PurePosixPath(value)) == value and '..' not in PurePosixPath(value).parts and
            all(character.isprintable() for character in value), 'Capture launch path differs')
        return PurePosixPath(value)

    root = absolute_path(recipe.get('dosbox_cwd'))
    require(root.is_relative_to('/dev/shm') and root != PurePosixPath('/dev/shm'), 'Capture escaped RAM')
    capture = recipe.get('capture_argv')
    require(type(capture) is list and len(capture) == 10 and all(type(value) is str for value in capture),
            'Capture producer command differs')
    repo, host = absolute_path(capture[5]), absolute_path(capture[7])
    run = recipe.get('run')
    require(type(run) is str and run.isalnum() and bool(host.name) and capture == [
        str(repo / 'tools/original_work_probe/capture.py'), '--inside-xvfb', '--run', run,
        '--repo', str(repo), '--dosbox', str(host), '--out', str(root)], 'Capture producer command differs')
    require(type(recipe.get('dosbox_argv')) is list and recipe['dosbox_argv'] == [str(host),
        '-conf', str(root / 'dosbox.conf'), '-c', 'mount c ' + str(root / 'run'),
        '-c', 'c:', '-c', 'LEZAC.EXE'], 'Unexpected DOSBox command')
    commands = recipe.get('host_commands')
    require(type(commands) is list and len(commands) == 22 and all(type(command) is dict and
        type(command.get('exit_code')) is int and command['exit_code'] == 0 for command in commands),
        'Capture host command sequence differs')
    pid, output = recipe.get('child_pid'), commands[0].get('stdout')
    require(type(pid) is int and pid > 0 and type(output) is str and output.splitlines(),
            'Capture input target differs')
    window = output.splitlines()[-1]
    require(window.isascii() and window.isdecimal() and int(window) > 0, 'Capture input target differs')
    focus = ['xdotool', 'windowfocus', window]
    geometry = ['xdotool', 'getwindowgeometry', '--shell', window]
    expected = [['xdotool', 'search', '--pid', str(pid), '--name', 'DOSBox'], focus, geometry]
    for key in ('1', 'Return', 'Escape', '1', 'q', 'Return'):
        expected.extend([focus, ['xdotool', 'key', '--clearmodifiers', key], geometry])
    expected.append(['xdotool', 'key', '--clearmodifiers', 'ctrl+F9'])
    require([command.get('command') for command in commands] == expected, 'Capture host command sequence differs')

    def interval(item):
        require(type(item) is dict, 'Capture command timing differs')
        values = [item.get('monotonic_before'), item.get('monotonic_after')]
        require(all(type(value) in (int, float) and math.isfinite(value) for value in values) and
                0 <= values[0] <= values[1], 'Capture command timing differs')
        return values

    times = [interval(command) for command in commands]
    require(all(first[1] <= second[0] for first, second in zip(times, times[1:])), 'Capture command timing differs')
    events, samples = recipe.get('events'), recipe['samples']
    require(type(events) is list and len(events) == 6 and len(samples) == 7, 'Capture checkpoint count differs')
    for index, event in enumerate(events):
        before, after = interval(event)
        require(before <= times[3 + index * 3][0] <= times[4 + index * 3][1] <= after,
                'Capture input event binding differs')
    for index, sample in enumerate(samples):
        command_index = 2 + index * 3
        validate_geometry(commands[command_index].get('stdout'), window)
        before, after = interval(sample)
        require(before <= times[command_index][0] <= times[command_index][1] <= after,
                'Capture sample binding differs')


def validate_capture_recipe(recipe, trace_raw):
    require(type(recipe) is dict, 'Capture recipe is not an object')
    require(recipe.get('environment_is_complete') is True, 'Incomplete capture environment')
    authenticated_recipe = validate_provenance(recipe)
    environment = recipe.get('dosbox_environment', {})
    require(type(environment) is dict and all(type(value) is str and value for value in environment.values()),
            'Invalid capture environment')
    require(set(environment) == {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'DISPLAY',
        'XAUTHORITY', 'SDL_VIDEODRIVER', 'SDL_AUDIODRIVER', 'LEZAC_WORK_TRACE'}, 'Unexpected environment keys')
    root = recipe.get('dosbox_cwd', '')
    require(type(root) is str and root.startswith('/dev/shm/') and '..' not in PurePosixPath(root).parts,
            'Capture escaped RAM')
    require(environment['PATH'] == '/usr/bin:/bin' and environment['HOME'] == root + '/home'
            and environment['TMPDIR'] == root + '/tmp' and environment['LANG'] == environment['LC_ALL'] == 'C.UTF-8'
            and environment['SDL_VIDEODRIVER'] == 'x11' and environment['SDL_AUDIODRIVER'] == 'dummy'
            and environment['LEZAC_WORK_TRACE'] == root + '/guest-work.csv', 'Capture environment changed')
    require(environment['DISPLAY'].startswith(':') and environment['XAUTHORITY'].startswith('/dev/shm/'),
            'Unexpected private display')
    command = recipe.get('dosbox_argv', [])
    require(len(command) == 9 and command[1:] == ['-conf', root + '/dosbox.conf', '-c',
        'mount c ' + root + '/run', '-c', 'c:', '-c', 'LEZAC.EXE'], 'Unexpected DOSBox command')
    require(recipe.get('status') == 'observed' and recipe.get('child_exit_code') == 0
            and recipe.get('canonical_assets_unchanged') is True, 'Capture did not finish successfully')
    require(recipe.get('input_injection_failures') == [], 'Input injection failed')
    commands = recipe.get('host_commands', [])
    require(commands and all(item['exit_code'] == 0 for item in commands), 'Host command failed')
    for previous, current in zip(commands, commands[1:]):
        require(0 <= previous['monotonic_before'] <= previous['monotonic_after'] <= current['monotonic_before'],
                'Command times are not ordered')
    inputs = [item['command'] for item in commands if item['command'][:2] == ['xdotool', 'key']]
    require(inputs == [['xdotool', 'key', '--clearmodifiers', key]
        for key in ('1', 'Return', 'Escape', '1', 'q', 'Return', 'ctrl+F9')], 'Capture input sequence changed')
    events = recipe.get('events', [])
    require([item['key'] for item in events] == ['1', 'Return', 'Escape', '1', 'q', 'Return'],
            'Missing timed key event')
    require(all(0 <= item['monotonic_before'] <= item['monotonic_after'] for item in events),
            'Invalid key event timing')
    require([item['name'] for item in recipe.get('samples', [])] ==
        ['main', 'intro', 'gameplay', 'game-over', 'record-prompt', 'player1-q', 'after-commit'],
        'Missing capture checkpoints')
    require(recipe.get('trace_bytes') == len(trace_raw)
            and recipe.get('trace_sha256') == hashlib.sha256(trace_raw).hexdigest(),
            'Recipe does not match analyzed trace')
    if recipe.get('schema') == 'lezac-instrumented-work-clock-v1':
        first = next(csv.DictReader(io.StringIO(trace_raw.decode('ascii'))))
        require(int(first['cs']) == recipe['code_segment'], 'Trace module differs from capture')
    return authenticated_recipe


def validate_marker_segments(rows):
    code = rows[0]['cs']
    require(16 < code < 0xa000 - 0xaa2, 'Original code relocation differs')
    game_ips = dict(MARKER_IP, identified=0x1fc, begin=0x1fc, clear_return=0x219,
                    palette_ready=0x247, finish=0x309)
    # Linked game, CRT-delay, floating-point and runtime code units in LEZAC.EXE.
    unit_sizes = {code: 0x84a0, code + 0x84a: 0x620,
                  code + 0x8ac: 0x740, code + 0x920: 0x1820}
    for row in rows:
        kind, cs, ip = row['kind'], row['cs'], row['ip']
        if kind in game_ips:
            require(cs == code and ip == game_ips[kind], 'Game marker code segment or offset differs')
        elif kind == 'delay_begin':
            require((cs, ip) == (code + 0x84a, 0x29c), 'CRT delay marker segment or offset differs')
        elif kind == 'delay_end':
            require(cs == code and ip in (0x1619, 0x79e8), 'CRT delay caller segment or offset differs')
        elif kind == 'irq8_enter':
            require((cs, ip) == (0xf000, 0xfea5), 'Timer IRQ vector differs')
        elif kind == 'irq9_enter':
            require((cs, ip) == (code, 0x1091), 'Keyboard IRQ vector differs')
        elif kind in ('irq8_return', 'irq9_return'):
            require(cs == 0xf000 or cs in unit_sizes and ip < unit_sizes[cs],
                    'IRQ return code segment or offset differs')
        # The host-exit row is terminal metadata, not an attributed guest instruction.

def analyze(path, recipe=None):
    rows, raw = read_rows(path)
    validate_marker_segments(rows)
    if recipe is not None:
        authenticated_recipe = validate_capture_recipe(recipe, raw)
    pages = collections.defaultdict(list)
    irq_stack = []
    delay = None
    delays = []
    irq_pairs = 0
    for row in rows:
        kind = row['kind']
        if kind in ('irq8_enter', 'irq9_enter'):
            irq_stack.append(row)
            require(row['irq_depth'] == len(irq_stack), 'IRQ entry depth mismatch')
        elif kind in ('irq8_return', 'irq9_return'):
            require(irq_stack and irq_stack[-1]['kind'].replace('enter', 'return') == kind,
                    'Unpaired IRQ return')
            begin = irq_stack.pop()
            require(row['irq_depth'] == len(irq_stack), 'IRQ return depth mismatch')
            require(delta(begin, row) == 0 and delta(begin, row, 'exclusive_clock') == 0,
                    'IRQ work leaked into exclusive counts')
            irq_pairs += 1
        else:
            require(row['irq_depth'] == len(irq_stack), 'IRQ depth mismatch')
        if kind == 'delay_begin':
            require(delay is None, 'Overlapping delay')
            delay = row
        elif kind == 'delay_end':
            require(delay is not None, 'Delay end without start')
            argument, calibration = delay['delay_argument'], delay['delay_calibration']
            require((argument, calibration) == (row['delay_argument'], row['delay_calibration']),
                    'Delay input changed')
            expected = 5 if argument == 0 else 9 + argument * (11 * calibration + 5)
            actual = delta(delay, row)
            require(actual == expected, 'CRT delay dispatch formula mismatch')
            delays.append(dict(argument=argument, calibration=calibration,
                               dispatches=actual, cycle_clock=delta(delay, row, 'exclusive_clock')))
            delay = None
        if kind in MARKERS or kind in ('begin', 'clear_return', 'palette_ready', 'finish'):
            require(row['page'] > 0, 'Page marker without page')
            require(row['irq_depth'] == 0, 'Pattern marker inside IRQ')
            pages[row['page']].append(row)
    require(not irq_stack, 'Unfinished IRQ at exit')
    require(pages and sorted(pages) == list(range(1, len(pages) + 1)), 'Missing background page')
    require(delays, 'No completed CRT delay')
    reports = []
    row_costs = None
    for number, page in sorted(pages.items()):
        boundaries = {}
        pixels = collections.defaultdict(dict)
        for row in page:
            kind = row['kind']
            if kind in MARKERS:
                require(row['frame_valid'] == 1, 'Pattern frame missing')
                require(row['ip'] == MARKER_IP[kind], 'Wrong pixel instruction boundary')
                require(kind not in pixels[row['index']], 'Duplicate pattern marker')
                pixels[row['index']][kind] = row
            else:
                require(kind not in boundaries, 'Duplicate pattern boundary')
                boundaries[kind] = row
        require(set(boundaries) == {'begin', 'clear_return', 'palette_ready', 'finish'},
                'Incomplete background boundaries')
        require(set(pixels) == EXPECTED_INDICES, 'Incomplete background pixel sampling')
        begin, clear, ready, finish = (boundaries[key] for key in
                                     ('begin', 'clear_return', 'palette_ready', 'finish'))
        require(begin['ip'] == 0x1fc and clear['ip'] == 0x219 and ready['ip'] == 0x247
                and finish['ip'] == 0x309, 'Wrong routine boundary')
        require(all(delta(a, b) > 0 for a, b in zip((begin, clear, ready), (clear, ready, finish))),
                'Out-of-order fill boundaries')
        require(finish['frame_valid'] == 1 and finish['destination'] == 64000
                and finish['index'] == 63999, 'Incomplete background destination')
        h, v = finish['h'], finish['v']
        require(1 <= h <= 80 and 1 <= v <= 80, 'Invalid fill parameters')
        costs = []
        pairs = 0
        for index, pixel in sorted(pixels.items()):
            expected_markers = set(MARKERS) - (set() if index % 320 == 0 else {'row_work'})
            require(set(pixel) == expected_markers, 'Missing pixel boundary')
            horizontal, check, color, write, after, tail = (pixel[key] for key in
                ('horizontal', 'row_check', 'color', 'write', 'after_write', 'tail'))
            for row in pixel.values():
                require((row['h'], row['v'], row['destination']) == (h, v, index + (row['kind'] == 'tail')),
                        'Inconsistent pixel state')
            require(all((row['fraction'], row['phase']) == (color['fraction'], color['phase'])
                        for row in (write, after, tail)), 'Post-color cursor changed')
            ordered = [pixel[key] for key in MARKERS if key in pixel]
            require(all(delta(a, b) > 0 for a, b in zip(ordered, ordered[1:])),
                    'Misordered pixel boundaries')
            carry = int(horizontal['fraction'] + h > 100)
            require(delta(horizontal, check) == 4 + 2 * carry, 'Horizontal dispatch count mismatch')
            require(check['fraction'] == horizontal['fraction'] + h - 100 * carry
                    and check['phase'] == (horizontal['phase'] + carry) % 65536,
                    'Horizontal cursor mismatch')
            if index % 320:
                require(delta(check, color) == 7, 'Non-row dispatch count mismatch')
                require((check['fraction'], check['phase']) == (color['fraction'], color['phase']),
                        'Non-row cursor changed')
            else:
                work = pixel['row_work']
                require(delta(check, work) == 7, 'Row-check dispatch count mismatch')
                vertical_carry = (color['phase'] - check['phase']) % 65536
                require(vertical_carry in (0, 1), 'Invalid vertical carry')
                costs.append(delta(work, color) - 2 * vertical_carry)
            require(delta(color, write) == 11, 'Color dispatch count mismatch')
            require(delta(write, after) == 1, 'Pixel write dispatch count mismatch')
            require(delta(after, tail) == 1, 'Destination increment dispatch count mismatch')
            if index + 1 in pixels:
                require(delta(after, pixels[index + 1]['horizontal']) == 5,
                        'Pixel-tail dispatch count mismatch')
                pairs += 1
        require(delta(pixels[63999]['after_write'], finish) == 3, 'Final-pixel tail mismatch')
        require(len(costs) == 200, 'Incomplete software-float row profile')
        if row_costs is None:
            row_costs = costs
        require(costs == row_costs, 'Row work differs across fill parameters')
        reports.append(dict(page=number, horizontal=h, vertical=v,
            sampled_pixels=len(pixels), consecutive_pairs=pairs,
            dispatches=delta(begin, finish), cycle_clock=delta(begin, finish, 'exclusive_clock'),
            clear_dispatches=delta(begin, clear), clear_cycle_clock=delta(begin, clear, 'exclusive_clock'),
            palette_dispatches=delta(clear, ready), palette_cycle_clock=delta(clear, ready, 'exclusive_clock')))
    groups = collections.defaultdict(list)
    for row in delays:
        groups[(row['argument'], row['calibration'], row['dispatches'])].append(row['cycle_clock'])
    result = dict(schema='lezac-normal-core-work-profile-v1', trace_sha256=hashlib.sha256(raw).hexdigest(),
        trace_rows=len(rows), pages=reports, irq_pairs=irq_pairs,
        completed_delays=len(delays), unfinished_delays_at_host_exit=int(delay is not None),
        delays=[dict(argument=k[0], calibration=k[1], dispatches=k[2], observations=len(v),
                     cycle_clock_min=min(v), cycle_clock_max=max(v)) for k, v in sorted(groups.items())],
        row_work_dispatches_without_vertical_carry=row_costs,
        dispatches_are_cycle_clock=False, host_instrumented=True, natural_wall_clock_fidelity_claim=False)
    if recipe is not None:
        result.update(capture_recipe_verified=authenticated_recipe, capture_recipe_run=recipe['run'],
                      capture_execution_contract_valid=True,
                      capture_checkpoint_metadata_authenticated=authenticated_recipe,
                      raw_checkpoint_files_verified=False)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('trace', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--recipe', type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Output already exists')
    recipe = json.loads(args.recipe.read_text()) if args.recipe else None
    result = analyze(args.trace, recipe=recipe)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in result if key != 'row_work_dispatches_without_vertical_carry'}, indent=2))

if __name__ == '__main__':
    main()
