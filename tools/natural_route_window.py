"""Strict four-phase trace comparison for ordinary natural-gameplay windows."""
import hashlib

import level1_fidelity as fidelity

require = fidelity.require


def compare_window(case, *, first, last, settings, events, expected, asset_root, compare_state):
    require(fidelity.integer(first, 1, last), 'natural window range differs')
    frames = count = boundaries = 0
    previous = footer = None
    with (case / 'run/trace.jsonl').open(encoding='utf-8') as stream:
        first_line = stream.readline()
        require(bool(first_line), 'natural window header missing')
        header = fidelity.strict_json(first_line)
        require(isinstance(header, dict) and set(header) == fidelity.HEADER_KEYS | {'capture_from_tick', 'candidate_only'} and
            header['kind'] == 'header' and header['schema'] == 'lezac.level1.scout.v1' and
            header['source'] == 'cpp' and header['candidate_only'] is True and
            header['ticks'] == last and header['capture_from_tick'] == first and
            header['original_fidelity_claim'] is False and header['phase_model'] == 'cpp-pre-actors-v2' and
            header['state_scope'] == 'level1-observations-v2' and
            header['input_model'] == 'sdl-events-original-intro-wait-v1' and
            all(type(header[key]) is int for key in
                ('ticks', 'capture_from_tick', 'width', 'height', 'seed', 'step_us')) and
            (header['width'], header['height']) == (320, 200) and
            header['seed'] == settings['seed'] and header['step_us'] == settings['step_us'] and
            header['route_fnv1a64'] == fidelity.fnv1a64((case / 'route.txt').read_bytes()) and
            header['asset_fnv1a64'] == {name: fidelity.fnv1a64((asset_root / name).read_bytes())
                for name in fidelity.ASSETS}, 'natural window C++ header differs')
        for line in stream:
            row = fidelity.strict_json(line)
            require(isinstance(row, dict), 'natural window record is not an object')
            require(footer is None, 'natural window data after footer')
            if row.get('kind') == 'complete':
                footer = row
                require(set(row) == {'kind', 'ticks', 'frames', 'retained_checkpoints', 'checkpoints', 'events',
                    'capture_from_tick', 'candidate_only', 'level1_route_complete', 'original_fidelity_claim',
                    'port_functionally_complete'} and previous is not None and
                    all(fidelity.integer(row[key], 0, 2**64 - 1) for key in
                        ('ticks', 'frames', 'retained_checkpoints', 'checkpoints', 'events', 'capture_from_tick')) and
                    row['ticks'] == last and row['capture_from_tick'] == first and
                    row['frames'] == frames == last - first + 1 and
                    row['retained_checkpoints'] == count == frames * 4 and row['checkpoints'] == previous + 1 and
                    row['events'] == sum(map(len, events.values())) and row['candidate_only'] is True and
                    row['level1_route_complete'] is True and row['original_fidelity_claim'] is False and
                    row['port_functionally_complete'] is False, 'natural window C++ footer differs')
                continue
            tick = first + count // 4
            phase = ('input', 'present', 'after_nonplayers', 'post_update')[count % 4]
            keys = {'kind', 'seq', 'tick', 'phase', 'time_ms', 'events', 'state'} | (
                {'frame', 'rgb_fnv1a64'} if phase == 'present' else set())
            require(set(row) == keys and row['kind'] == 'checkpoint' and
                (row['tick'], row['phase']) == (tick, phase) and tick <= last and
                type(row['tick']) is int and type(row['time_ms']) is int and
                fidelity.integer(row['seq'], 0, 2**64 - 1) and
                (previous is None or row['seq'] == previous + 1) and
                row['events'] == events.get(tick - 1, []) and
                row['time_ms'] == (tick - 1) * settings['step_us'] // 1000,
                'natural window C++ phase/input/time differs')
            fidelity.validate_state(row['state'])
            if phase in ('present', 'post_update'):
                compare_state(row['state'], expected[tick, phase])
                boundaries += 1
            if phase == 'present':
                require(row['frame'] == f'frame_{tick:06d}.ppm', 'natural window RGB filename differs')
                pixels = fidelity.read_ppm(fidelity.safe_file(case / 'run', row['frame']))
                require(fidelity.fnv1a64(pixels) == row['rgb_fnv1a64'] and
                    hashlib.sha256(pixels).hexdigest() == expected[tick, phase]['rgb_sha256'],
                    'natural window original RGB differs')
                frames += 1
            previous, count = row['seq'], count + 1
    require(footer is not None and boundaries == frames * 2, 'natural window C++ stream incomplete')
    return dict(status='match', first=first, last=last, frames=frames, boundaries=boundaries,
        checkpoints=count, pixels=frames * 64000)
