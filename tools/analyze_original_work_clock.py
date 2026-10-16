"""Validate instrumented normal-core traces without treating dispatches as cycles."""
import argparse
import collections
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

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

def validate_capture_recipe(recipe, trace_raw):
    require(recipe.get('environment_is_complete') is True, 'Incomplete capture environment')
    environment = recipe.get('dosbox_environment', {})
    require(set(environment) == {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'DISPLAY',
        'XAUTHORITY', 'SDL_VIDEODRIVER', 'SDL_AUDIODRIVER', 'LEZAC_WORK_TRACE'}, 'Unexpected environment keys')
    root = recipe.get('dosbox_cwd', '')
    require(root.startswith('/dev/shm/') and '..' not in Path(root).parts, 'Capture escaped RAM')
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

def analyze(path, recipe=None):
    rows, raw = read_rows(path)
    if recipe is not None:
        validate_capture_recipe(recipe, raw)
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
        result.update(capture_recipe_verified=True, capture_recipe_run=recipe['run'])
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
