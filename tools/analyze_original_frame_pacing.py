"""Validate read-only original frame-pacing traces and their exact recipes."""
import argparse
import configparser
import csv
import hashlib
import io
import json
from pathlib import Path

IPS = dict(identified=0x1fc, frame_before=0x7903, time_begin=0x7919,
           time_result=0x792a, measurement=0x7966, adjust_begin=0x799a,
           adjust_end=0x79cd, delay_before=0x79df, delay_after=0x79e8)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def analyze(raw, recipe):
    require(0 < len(raw) < 2 * 1024**2, 'Trace reserve exceeded')
    require(recipe['status'] == 'observed' and recipe['passed'] is True and
            recipe['child_exit_code'] == 0 and recipe['trace_end_marker'] is True, 'Capture did not complete')
    require(recipe['trace_bytes'] == len(raw) and recipe['trace_sha256'] == hashlib.sha256(raw).hexdigest(),
            'Recipe does not bind this exact trace')
    require(recipe['schema'] == 'lezac-instrumented-frame-pacing-v1' and recipe['executable_sha256'] ==
            '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec', 'Wrong original recipe')
    config = configparser.ConfigParser()
    config.read_string(recipe['dosbox_config'])
    require(config['cpu']['core'] == 'normal' and config['cpu']['cycles'] == 'fixed 6000' and
            config['mixer']['nosound'] == 'true' and config['speaker']['pcspeaker'] == 'false', 'Wrong capture profile')
    require(recipe['environment_is_complete'] is True and not recipe['input_injection_failures'], 'Incomplete input provenance')
    env = recipe['dosbox_environment']
    require(set(env) == {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'DISPLAY', 'XAUTHORITY',
                        'SDL_VIDEODRIVER', 'SDL_AUDIODRIVER', 'LEZAC_PACING_TRACE'} and
            env['SDL_AUDIODRIVER'] == 'dummy', 'Unexpected emulator environment')
    require(recipe['process_memory_writes'] == 0 and recipe['injected_instructions'] == 0 and
            recipe['process_pauses'] == 0 and recipe['record_file_fixture_seeded'] is False and
            recipe['clock_rng_or_heap_seeded'] is False and recipe['gameplay_state_seeded'] is False and
            recipe['canonical_assets_unchanged'] is True, 'Capture changed original state')
    require(len(recipe['samples']) == 5 and all(sample['code_bytes_verified'] == 43552 and
            sample['code_differences'] == 0 for sample in recipe['samples']), 'Original code verification differs')
    require(recipe['host_commands'] and all(command['exit_code'] == 0 for command in recipe['host_commands']), 'Input command failed')
    require([event['key'] for event in recipe['events']] == ['1', 'Return'], 'Unexpected input recipe')
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
