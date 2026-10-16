"""Validate read-only original frame-pacing traces and their exact recipes."""
import argparse
import configparser
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath

from original_capture_contract import ASSET_PINS, validate_geometry

IPS = dict(identified=0x1fc, frame_before=0x7903, time_begin=0x7919,
           time_result=0x792a, measurement=0x7966, adjust_begin=0x799a,
           adjust_end=0x79cd, delay_before=0x79df, delay_after=0x79e8)
CAPTURE_HASHES = dict(
    dosbox_sha256='b19be3dd86b5d6ee59e67ffd5c4d888069f8624b4d92499babe33f4ae168c7ef',
    producer_sha256='723c70eb1e497f0efb34e4600b9ac8edd3b2cb66802f37580c83edc8fdcc817b')
CAPTURE_CONFIG = dict(sdl=dict(fullscreen='false', output='surface'),
    render=dict(frameskip='0', aspect='false', scaler='none'),
    cpu=dict(core='normal', cycles='fixed 6000'), mixer=dict(nosound='true'),
    speaker=dict(pcspeaker='false'), sblaster=dict(sbtype='none'),
    midi=dict(mpu401='none', mididevice='none'))
CAPTURE_ENVIRONMENT = dict(PATH='/usr/bin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8',
                           SDL_VIDEODRIVER='x11', SDL_AUDIODRIVER='dummy')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_launch(recipe):
    def ram_path(value):
        require(type(value) is str and value.startswith('/dev/shm/') and
                str(PurePosixPath(value)) == value and '..' not in PurePosixPath(value).parts and
                all(character.isascii() and (character.isalnum() or character in '/._-') for character in value),
                'DOSBox launch path differs')
        return PurePosixPath(value)

    cwd = ram_path(recipe.get('dosbox_cwd'))
    capture = recipe.get('capture_argv')
    require(type(capture) is list and len(capture) == 10 and all(type(value) is str for value in capture),
            'DOSBox capture command differs')
    repo, host = ram_path(capture[5]), ram_path(capture[7])
    require(host.parts[-3:] == ('dosbox-0.74-3', 'src', 'dosbox'), 'DOSBox host command differs')
    run = recipe.get('run')
    require(type(run) is str and run.isascii() and run.isalnum(), 'DOSBox capture run differs')
    require(capture == [str(repo / 'tools/frame_pacing_probe/capture.py'), '--inside-xvfb', '--run', run,
                        '--repo', str(repo), '--dosbox', str(host), '--out', str(cwd)],
            'DOSBox capture command differs')
    argv = recipe.get('dosbox_argv')
    require(type(argv) is list and argv == [str(host), '-conf', str(cwd / 'dosbox.conf'),
                '-c', 'mount c ' + str(cwd / 'run'), '-c', 'c:', '-c', 'LEZAC.EXE'],
            'DOSBox launch command differs')
    env = recipe['dosbox_environment']
    require(all(env.get(key) == str(cwd / suffix) for key, suffix in
                [('HOME', 'home'), ('TMPDIR', 'tmp'), ('LEZAC_PACING_TRACE', 'guest-pacing.csv')]),
            'DOSBox launch environment binding differs')


def validate_input_commands(recipe):
    commands = recipe.get('host_commands')
    require(type(commands) is list and len(commands) == 12 and
            all(type(command) is dict and type(command.get('exit_code')) is int and
                command['exit_code'] == 0 for command in commands), 'Input command sequence differs')
    pid = recipe.get('child_pid')
    output = commands[0].get('stdout')
    require(type(pid) is int and pid > 0 and type(output) is str and output.splitlines(),
            'Input command target differs')
    window = output.splitlines()[-1]
    require(window.isascii() and window.isdecimal() and int(window) > 0, 'Input command target differs')
    focus = ['xdotool', 'windowfocus', window]
    geometry = ['xdotool', 'getwindowgeometry', '--shell', window]
    expected = [['xdotool', 'search', '--pid', str(pid), '--name', 'DOSBox'], focus, geometry,
        focus, ['xdotool', 'key', '--clearmodifiers', '1'], geometry,
        focus, ['xdotool', 'key', '--clearmodifiers', 'Return'], geometry, geometry, geometry,
        ['xdotool', 'key', '--clearmodifiers', 'ctrl+F9']]
    require([command.get('command') for command in commands] == expected, 'Input command sequence differs')
    for index in (2, 5, 8, 9, 10):
        validate_geometry(commands[index].get('stdout'), window)

    def interval(item):
        require(type(item) is dict, 'Input command timing differs')
        values = [item.get('monotonic_before'), item.get('monotonic_after')]
        require(all(type(value) in (int, float) and math.isfinite(value) for value in values) and
                0 <= values[0] <= values[1], 'Input command timing differs')
        return values

    times = [interval(command) for command in commands]
    require(all(first[1] <= second[0] for first, second in zip(times, times[1:])),
            'Input command timing differs')
    events = recipe.get('events')
    require(type(events) is list and len(events) == 2 and all(type(event) is dict for event in events) and
            [event.get('key') for event in events] == ['1', 'Return'],
            'Unexpected input recipe')
    for event, focus_index, key_index in zip(events, (3, 6), (4, 7)):
        before, after = interval(event)
        require(before <= times[focus_index][0] <= times[key_index][1] <= after,
                'Input command does not bind its event')
    for sample, index in zip(recipe['samples'], (2, 5, 8, 9, 10)):
        before, after = interval(sample)
        require(before <= times[index][0] <= times[index][1] <= after,
                'Input command does not bind its sample')


def analyze(raw, recipe):
    require(0 < len(raw) < 2 * 1024**2, 'Trace reserve exceeded')
    require(recipe['status'] == 'observed' and recipe['passed'] is True and
            recipe['child_exit_code'] == 0 and recipe['trace_end_marker'] is True, 'Capture did not complete')
    require(recipe['trace_bytes'] == len(raw) and recipe['trace_sha256'] == hashlib.sha256(raw).hexdigest(),
            'Recipe does not bind this exact trace')
    require(recipe['schema'] == 'lezac-instrumented-frame-pacing-v1' and recipe['executable_sha256'] ==
            '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec', 'Wrong original recipe')
    require(all(type(recipe.get(key)) is str and recipe[key] == expected
                for key, expected in CAPTURE_HASHES.items()), 'Capture host or producer differs')
    require(recipe.get('capture_contract_sha256') == hashlib.sha256(
        Path(__file__).with_name('original_capture_contract.py').read_bytes()).hexdigest(), 'Capture contract differs')
    assets = recipe.get('assets')
    require(type(assets) is dict and set(assets) == set(ASSET_PINS), 'Original asset domain differs')
    require(all(type(assets[name]) is dict and type(assets[name].get('bytes')) is int and
        assets[name]['bytes'] == size and assets[name].get('sha256') == pin
        for name, (size, pin) in ASSET_PINS.items()), 'Canonical original asset differs')
    config = configparser.ConfigParser()
    try:
        config.read_string(recipe['dosbox_config'])
        require(not config.defaults() and {section: dict(config[section]) for section in config.sections()} ==
                CAPTURE_CONFIG, 'Wrong capture profile')
    except configparser.Error as error:
        raise ValueError('Wrong capture profile') from error
    require(recipe['environment_is_complete'] is True and not recipe['input_injection_failures'], 'Incomplete input provenance')
    env = recipe['dosbox_environment']
    require(set(env) == {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'DISPLAY', 'XAUTHORITY',
                        'SDL_VIDEODRIVER', 'SDL_AUDIODRIVER', 'LEZAC_PACING_TRACE'} and
            all(type(value) is str and value for value in env.values()) and
            all(env[key] == value for key, value in CAPTURE_ENVIRONMENT.items()),
            'Unexpected emulator environment')
    validate_launch(recipe)
    require(recipe['process_memory_writes'] == 0 and recipe['injected_instructions'] == 0 and
            recipe['process_pauses'] == 0 and recipe['record_file_fixture_seeded'] is False and
            recipe['clock_rng_or_heap_seeded'] is False and recipe['gameplay_state_seeded'] is False and
            recipe['canonical_assets_unchanged'] is True, 'Capture changed original state')
    require(all(type(recipe.get(key)) is int and recipe[key] == 0 for key in
                ('host_probe_guest_register_writes', 'host_probe_guest_memory_writes')) and
            recipe.get('original_executable_changed') is False and
            recipe.get('process_memory_opened_read_only') is True,
            'Read-only guest provenance differs')
    mode_flags = dict(host_instrumented=True, natural_wall_clock_fidelity_claim=False,
                      complete_frame_sequence_claim=False, whole_game_complete=False,
                      cpu_memory_frame_atomic=False, private_xvfb_autorepeat_disabled=True)
    require(all(recipe.get(key) is value for key, value in mode_flags.items()), 'Capture mode claims differ')
    require(recipe.get('audio') == 'dummy' and type(recipe.get('configured_players')) is int and
            recipe['configured_players'] == 1 and
            recipe.get('trace_clock') == 'normal-core fixed-cycle budget, sampled before decode' and
            recipe.get('trace_dispatch') == 'normal-core iterations; REP may charge multiple cycles per iteration',
            'Capture mode profile differs')
    autorepeat = recipe.get('private_display_autorepeat_command')
    require(type(autorepeat) is dict and autorepeat.get('command') == ['xset', 'r', 'off'] and
            type(autorepeat.get('exit_code')) is int and autorepeat['exit_code'] == 0,
            'Capture mode profile differs')
    require(len(recipe['samples']) == 5 and all(sample['code_bytes_verified'] == 43552 and
            sample['code_differences'] == 0 and sample.get('ram_rgb_cpu_atomic') is False
            for sample in recipe['samples']), 'Original code or checkpoint scope differs')
    validate_input_commands(recipe)
    require(raw.endswith(b'\nend\n'), 'Missing terminal trace marker')
    rows = list(csv.DictReader(io.StringIO(raw[:-4].decode('ascii'))))
    require(rows and rows[0]['kind'] == 'identified', 'Original not identified')
    converted = []
    previous_dispatch = previous_clock = -1
    for row in rows:
        kind = row['kind']
        require(kind in IPS and None not in row and all(value is not None for value in row.values()), 'Malformed trace row')
        value = {key: int(item) for key, item in row.items() if key != 'kind'}
        require(value['dispatch'] > previous_dispatch and value['clock'] >= previous_clock, 'Trace order differs')
        previous_dispatch, previous_clock = value['dispatch'], value['clock']
        require(value['ip'] == IPS[kind] and value['ds'] == value['cs'] + 0xaa2, 'Original boundary differs')
        require(value['cs'] == recipe['code_segment'] and value['ds'] == recipe['data_segment'], 'Recipe segment differs')
        require(all(0 <= number <= 65535 for key, number in value.items()
                    if key not in {'dispatch', 'clock', 'pic_ticks'}), 'Word range differs')
        require(all(value[key] <= 255 for key in value if 'minute' in key or 'second' in key or 'hundredth' in key), 'Byte range differs')
        converted.append(dict(kind=kind, **value))
    initial = converted[0]
    require(initial['delay'] == initial['auxiliary'], 'Startup did not seed the mutable delay')
    cursor, completed, adjustments = 1, [], []
    pending = None
    prior_counter, delay = None, initial['delay']
    while cursor < len(converted):
        before = converted[cursor]
        require(before['kind'] == 'frame_before', 'Expected frame boundary')
        require(before['frame_counter'] == (0 if prior_counter is None else prior_counter), 'Frame sequence differs')
        counter = (before['frame_counter'] + 1) & 65535
        require(before['delay'] == delay and before['minimum'] == initial['minimum'], 'Frame pacing word differs')
        required = (['time_begin', 'time_result', 'measurement', 'adjust_begin', 'adjust_end']
                    if counter % 30 == 0 else []) + ['delay_before', 'delay_after']
        cursor += 1
        group = []
        for kind in required:
            if cursor == len(converted):
                pending = dict(counter=counter, next_boundary=kind)
                break
            row = converted[cursor]
            require(row['kind'] == kind and row['frame_counter'] == counter, 'Frame service order differs')
            require(row['minimum'] == initial['minimum'] and row['auxiliary'] == initial['auxiliary'] and
                    row['character'] == initial['character'], 'Calibration changed unexpectedly')
            group.append(row)
            cursor += 1
        if pending:
            break
        if counter % 30 == 0:
            clock, measured, adjust, adjusted = group[1:5]
            clock_fields = [key for key in clock if 'minute' in key or 'second' in key or 'hundredth' in key]
            require(all(row[key] == clock[key] for row in (measured, adjust, adjusted) for key in clock_fields),
                    'Clock operands changed during feedback')
            require(clock['current_minute'] <= 59 and clock['current_second'] <= 59 and
                    clock['current_hundredth'] <= 99, 'DOS time outside range')
            elapsed = ((clock['current_minute'] - clock['previous_minute']) * 6000 +
                       (clock['current_second'] - clock['previous_second']) * 100 +
                       clock['current_hundredth'] - clock['previous_hundredth']) & 65535
            require(measured['measured_word'] == adjust['measured_word'] == adjusted['measured_word'] == elapsed,
                    'Original wrapped measurement differs')
            require(adjust['delay'] == delay and measured['delay'] == delay, 'Delay changed before feedback')
            step = initial['minimum']
            expected = max(0, delay - step) if elapsed > 125 else ((delay + step) & 65535 if elapsed < 120 else delay)
            require(adjusted['delay'] == expected, 'Original feedback differs')
            delay = expected
            for previous, current in [('previous_minute', 'current_minute'), ('previous_second', 'current_second'),
                                      ('previous_hundredth', 'current_hundredth')]:
                require(group[-2][previous] == clock[current], 'Clock sample not carried forward')
            adjustments.append(dict(counter=counter, elapsed=elapsed, before=adjust['delay'], step=step,
                                    after=delay, previous=[clock[key] for key in
                                    ('previous_minute', 'previous_second', 'previous_hundredth')]))
        require(group[-2]['delay'] == group[-1]['delay'] == delay, 'Wrong delay argument or return word')
        require(group[-1]['clock'] > group[-2]['clock'], 'Delay clock did not advance')
        completed.append(dict(counter=counter, delay=delay, elapsed=elapsed if counter % 30 == 0 else -1,
                              before_clock=before['clock'], after_clock=group[-1]['clock']))
        prior_counter = counter
    require(completed and adjustments, 'No complete gameplay pacing evidence')
    return dict(run=recipe['run'], completed_frames=len(completed), measurements=len(adjustments),
                initial_delay=initial['delay'], final_delay=delay, character=initial['character'],
                adjustments=adjustments, pending_frame=pending, frames=completed,
                natural_input=True, host_instrumented=True, natural_wall_clock_fidelity_claim=False,
                synchronized_frame_parity=False, whole_game_parity=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with args.trace.open('rb') as stream:
        raw = stream.read(2 * 1024**2)
    result = analyze(raw, json.loads(args.recipe.read_text()))
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'frames'}))
