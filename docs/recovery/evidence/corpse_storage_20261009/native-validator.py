"""Independently validate the original-only constructor streams and semantic controls."""
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import traceback

VIS = Path('/mnt/c/Users/andrz/.codex/visualizations/2026/07/05/019f3283-94f8-7603-b1b5-c9d78bf86769')
ORIGINAL = Path('/tmp/lezac-reward-construction-original-20261009-t93-v3')
REPEAT = Path('/tmp/lezac-reward-construction-repeat-20261009-t93-v3')
INITIAL = Path('/tmp/lezac-reward-construction-original-20261009-t93')
OUT = Path('/tmp/lezac-reward-construction-validation-20261009-t93-v2')
CAP, STATE, RECORD, HEADER = 8 * 1024**2, 1593, 1600, 6320
report = dict(passed=False, recorded_utc=datetime.now(timezone.utc).isoformat(),
    validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    full_cpp_comparison=False, actual_app_executed=False, whole_game_claim=False,
    natural_route=False, seeded=True, masks_applied=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(path):
    packed = path.read_bytes()
    assert len(packed) < 1024**2
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(CAP + 1)
    assert len(raw) < CAP
    return raw


def rng_step(seed):
    return (seed * 0x08088405 + 1) & 0xffffffff


def expected_kind(roll):
    if roll < 40:
        return 0
    return 0x13 + next(index for index, upper in enumerate((65, 71, 78, 83, 89, 93, 100)) if roll <= upper)


def signed_word(value):
    value &= 65535
    return value if value < 32768 else value - 65536


def signed_byte(value):
    return value if value < 128 else value - 256


def validate_motion(before, after, case, tick, tiles, descriptors):
    start = case['corpse_slot'] * 38
    actor = bytearray(before[start:start + 38])
    assert actor[0] == 12 and actor[21] == 2
    visual_at = 1178 + actor[1] * 8
    visual = bytearray(before[visual_at:visual_at + 8])
    current, first, last, counter, delay, mode, step = actor[22:29]
    advanced = False
    if mode:
        counter = (counter + 1) & 255
        if counter > delay:
            advanced = True; counter = 0
            current = (current + signed_byte(step)) & 255
            if mode == 2:
                if current >= last or current <= first: step = (-signed_byte(step)) & 255
            elif current > last:
                current = first
                if mode == 3: current, first, last, counter, delay, mode, step = actor[29:36]
    actor[22:29] = bytes((current, first, last, counter, delay, mode, step))
    if advanced: visual[6:8] = descriptors[current * 4 + 2:current * 4 + 4]
    x, y = struct.unpack_from('<hh', visual)
    y = signed_word(y - signed_byte(actor[20]))
    vx, vy = struct.unpack_from('<hh', actor, 6)
    fx, fy = actor[10], actor[12]
    column, row = (x + 4) >> 3, y >> 3
    def solid(c, r, bottom=False):
        tile = 1 if c < 0 or c >= 60 or r < 0 or r >= 33 else tiles[r * 60 + c]
        return 1 <= tile <= (0x52 if bottom else 0x4c)
    top = solid(column, row - 1) or solid(column + 1, row - 1)
    bottom = solid(column, row + 2, True) or solid(column + 1, row + 2, True)
    left = solid(column - 1, row) or solid(column - 1, row + 1)
    right = solid(column + 2, row) or solid(column + 2, row + 1)
    if not bottom or vy < 0: vy = min(2047, signed_word(vy + 64))
    elif vy > 0: vy = 0; y &= ~7
    if bottom:
        magnitude = signed_word(-vx) if vx < 0 else vx
        vx = 0 if magnitude < 43 else signed_word(vx + (42 if vx < 0 else -42))
    if top and vy < 0: vy = 1
    if left and right: vx = 0
    elif left and vx < 0 or right and vx > 0:
        reflected = signed_word(-vx)
        vx = (abs(reflected) // 2) * (-1 if reflected < 0 else 1)
        x += -1 if vx < 0 else 1
    y = signed_word(y + (fy + vy) // 256); fy = (fy + vy) & 255
    x = signed_word(x + (fx + vx) // 256); fx = (fx + vx) & 255
    actor[6:14] = struct.pack('<hhHH', vx, vy, fx, fy)
    actor[2] = (actor[2] - (tick & 1)) & 255
    visual[:4] = struct.pack('<hh', x, signed_word(y + signed_byte(actor[20])))
    if after[start:start + 38] != actor or after[visual_at:visual_at + 8] != visual:
        for label, actual, expected in (('actor', after[start:start + 38], actor), ('visual', after[visual_at:visual_at + 8], visual)):
            if actual != expected:
                offset = next(index for index, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1])
                raise AssertionError(dict(case=case['label'], tick=tick, area=label, offset=offset, actual=actual[offset], expected=expected[offset]))


def validate_constructor(before, after, case, descriptors):
    assert len(before) == len(after) == STATE
    slot = case['corpse_slot']; at = slot * 38
    actor = bytearray(before[at:at + 38])
    assert actor[0] == 12 and actor[21] == 2 and actor[2] in (0, 255)
    expected = bytearray(before)
    kind = expected_kind(case['roll'])
    sprite = 69 if kind == 0 else 62 + kind - 0x13
    descriptor = descriptors[sprite * 4:(sprite + 1) * 4]
    assert len(descriptor) == 4
    actor[0], actor[2], actor[20] = kind, 18 if kind == 0 else 100, (16 - descriptor[1]) & 255
    if kind:
        actor[8:10] = struct.pack('<H', (struct.unpack_from('<H', actor, 8)[0] - 200) & 65535)
        actor[27] = 0
    else:
        actor[6:10] = bytes(4)
        actor[21] = 5
        actor[22:29] = bytes((69, 69, 79, 2, 2, 1, 1))
    expected[at:at + 38] = actor
    visual_at = 1178 + actor[1] * 8
    expected[visual_at + 4:visual_at + 8] = descriptor
    first = rng_step(case['rng']); second = rng_step(first)
    assert (first >> 16) % 100 == case['roll']
    cursor = 0xea74 + (second >> 16) % 20
    expected[1575:1579] = struct.pack('<I', second)
    expected[1585] = case['roll']
    expected[1586:1588] = struct.pack('<H', cursor)
    expected[1588] = 4
    priority = (before[1589] - 1) & 255
    signed_priority = priority if priority < 128 else priority - 256
    if not before[1592] or signed_priority < 4:
        expected[1589] = 4
        expected[1590:1592] = struct.pack('<H', cursor)
        expected[1592] = 1
    if after != expected:
        at = next(index for index, pair in enumerate(zip(after, expected)) if pair[0] != pair[1])
        raise AssertionError(dict(case=case['label'], state_offset=at, actual=after[at], expected=expected[at]))


try:
    assert not OUT.exists() and shutil.disk_usage('/dev/shm').free > 1503238553
    OUT.mkdir()
    originals = [json.loads((root / 'original-reward-construction.json').read_bytes()) for root in (ORIGINAL, REPEAT)]
    producer_sha = sha((VIS / 'capture-reward-construction-t93-v3.py').read_bytes())
    assert all(row['passed'] and row['case_count'] == 940 and row['operations'] == 3252 for row in originals)
    assert all(row['producer_sha256'] == producer_sha and row['construction_boundaries'] == 1880 for row in originals)
    assert all(not row['original_instructions_patched'] and not row['original_calls_stubbed'] and not row['hardware_io_permitted'] for row in originals)
    streams = {}
    for name in ('requests', 'expected', 'construction'):
        paths = [root / (name + '.bin.gz') for root in (ORIGINAL, REPEAT)]
        assert paths[0].read_bytes() == paths[1].read_bytes()
        value = decode(paths[0])
        for row in originals:
            assert sha(paths[0].read_bytes()) == row[name]['sha256']
            assert sha(value) == row[name]['raw_sha256'] and len(value) == row[name]['bytes']
        streams[name] = value
    for name in ('requests', 'expected'):
        initial_value = decode(INITIAL / (name + '.bin.gz'))
        assert streams[name][:8] == initial_value[:8] and streams[name][12:len(initial_value)] == initial_value[12:]
    requests, expected, construction = (streams[name] for name in ('requests', 'expected', 'construction'))
    assert requests[:12] == b'LZRC0001' + struct.pack('<I', 3252)
    assert expected[:12] == b'LZCO0001' + struct.pack('<I', 3252) and len(expected) == 12 + 3252 * STATE
    assert construction[:12] == b'LZCB0001' + struct.pack('<I', 1880) and len(construction) == 12 + 1880 * RECORD
    descriptors = requests[HEADER - 368:HEADER]
    tiles = requests[12:1992]
    states = [expected[12 + index * STATE:12 + (index + 1) * STATE] for index in range(3252)]
    parsed, cursor = [], HEADER
    for operation in range(3252):
        command = requests[cursor:cursor + 1]; cursor += 1
        if command == b'S':
            seed = requests[cursor:cursor + STATE]; cursor += STATE
            assert len(seed) == STATE and seed == states[operation]
            parsed.append(('S', seed))
        else:
            assert command == b'U'
            tick = struct.unpack_from('<H', requests, cursor)[0]; cursor += 2
            parsed.append(('U', tick))
    assert cursor == len(requests)
    assert sum(command == 'S' for command, _ in parsed) == 940
    assert sum(command == 'U' for command, _ in parsed) == 2312
    mid = []
    for index in range(1880):
        start = 12 + index * RECORD
        case, tick, phase = struct.unpack_from('<IHB', construction, start)
        mid.append((case, tick, phase, construction[start + 7:start + RECORD]))
    controls_base = {}
    kinds, allocation_results, delayed = {}, {}, 0
    next_first, corpse_motion_steps, continuing_corpse_steps = 0, 0, 0
    motion_control = None
    for index, case in enumerate(originals[0]['cases']):
        first = case['first_operation'] - 1
        assert first == next_first and parsed[first][0] == 'S'
        next_first += case['updates'] + 1
        seed = states[first]
        assert seed[1570] == case['count'] and seed[1571] == case['count'] + 2
        assert seed[case['corpse_slot'] * 38] == 12
        seen = set()
        for slot in range(1, case['count'] + 1):
            reference = seed[slot * 38 + 1]
            assert 2 <= reference < seed[1571] and reference not in seen
            seen.add(reference)
        conversions = 0
        for update, row in enumerate(case['ticks']):
            operation = first + update + 1
            state = states[operation]
            assert row['operation'] == operation + 1 and parsed[operation] == ('U', row['tick'])
            assert state[1579:1585] == seed[1579:1585]
            actor_at = case['corpse_slot'] * 38
            assert state[actor_at:actor_at + 38].hex() == row['actor']
            assert state[1575:1579].hex() == row['rng']
            if not row['random_calls']:
                assert not row['construction_boundaries']
                previous = states[operation - 1]
                if previous[actor_at] == 12:
                    validate_motion(previous, state, case, row['tick'], tiles, descriptors)
                    assert state[actor_at + 2] not in (0, 255)
                    corpse_motion_steps += 1; continuing_corpse_steps += 1
                    motion_control = (previous, state, case, row['tick'])
                assert state[1575:1579] == previous[1575:1579]
                continue
            conversions += 1
            if update: delayed += 1
            assert [item['span'] for item in row['random_calls']] == [100, 20, 600, 600, 600, 600]
            assert [point['phase'] for point in row['construction_boundaries']] == [0, 1]
            points = [mid[point['index']] for point in row['construction_boundaries']]
            assert all(item[0] == index and item[1] == row['tick'] for item in points)
            assert [item[2] for item in points] == [0, 1]
            before, after = points[0][3], points[1][3]
            validate_motion(states[operation - 1], before, case, row['tick'], tiles, descriptors)
            corpse_motion_steps += 1
            assert before[1575:1579] == struct.pack('<I', case['rng'])
            validate_constructor(before, after, case, descriptors)
            assert state[actor_at:actor_at + 38] == after[actor_at:actor_at + 38], 'converted actor dispatched twice'
            reference = state[actor_at + 1]; visual_at = 1178 + reference * 8
            assert state[visual_at:visual_at + 8] == after[visual_at:visual_at + 8]
            assert state[1570] == min(30, case['count'] + 2) and state[1571] == state[1570] + 2
            for slot in range(case['count'] + 1, state[1570] + 1):
                particle = state[slot * 38:(slot + 1) * 38]
                assert particle[0] == 11 and particle[2] == 15 - (row['tick'] & 1) and particle[21] == 5
                assert particle[22:29] == bytes((70, 69, 79, 0, 2, 2, 1)), 'appended particle was not updated in the creation pass'
                visual = state[1178 + particle[1] * 8:1178 + (particle[1] + 1) * 8]
                assert visual[4:6] == descriptors[13 * 4:13 * 4 + 2]
                assert visual[6:8] == descriptors[70 * 4 + 2:70 * 4 + 4]
            success = struct.unpack_from('<H', state, 1573)[0]
            assert success == (1 if case['count'] <= 28 else 0)
            rng = case['rng']
            for _ in range(6): rng = rng_step(rng)
            assert state[1575:1579] == struct.pack('<I', rng)
            assert state[1585:] == after[1585:]
            kind = state[actor_at]
            kinds[kind] = kinds.get(kind, 0) + 1
            allocation_results[case['count']] = allocation_results.get(case['count'], 0) + 1
            controls_base.setdefault('reward' if kind else 'fade', (before, after, case))
        assert conversions == 1
    assert set(kinds) == {0, *range(0x13, 0x1a)}
    assert set(allocation_results) == {1, 28, 29, 30} and delayed == 24
    assert next_first == 3252 and continuing_corpse_steps == 404 and corpse_motion_steps == 1344
    negative = []
    for label, base, location, value in (
        ('reward_kind', 'reward', 0, 0), ('reward_timer', 'reward', 2, 99),
        ('reward_impulse', 'reward', 8, None), ('reward_mode', 'reward', 27, 1),
        ('backup_preservation', 'reward', 29, None), ('opaque_preservation', 'fade', 3, None),
        ('fraction_preservation', 'fade', 10, None), ('fade_behavior', 'fade', 21, 2),
        ('fade_animation_delay', 'fade', 26, 1), ('rng_second_draw', 'reward', 1575, None),
        ('request_priority', 'reward', 1588, 5), ('active_sound_cursor', 'fade', 1590, None),
        ('early_allocation', 'reward', 1570, 3), ('pending_bonus_preservation', 'reward', 1579, 0),
        ('unused_actor_tail', 'reward', 30 * 38 + 3, None), ('unused_link_tail', 'fade', 1500, None),
        ('visual_dimensions', 'reward', 'descriptor', None), ('visual_position', 'reward', 'position', None)):
        before, after, case = controls_base[base]
        changed = bytearray(after)
        offset = (case['corpse_slot'] * 38 + location) if isinstance(location, int) and location < 38 else location
        if location in ('descriptor', 'position'):
            reference = after[case['corpse_slot'] * 38 + 1]
            offset = 1178 + reference * 8 + (4 if location == 'descriptor' else 2)
        changed[offset] = changed[offset] ^ 1 if value is None else value
        assert changed != after
        try:
            validate_constructor(before, bytes(changed), case, descriptors)
        except AssertionError:
            negative.append(label)
        else:
            raise AssertionError('semantic constructor mutant survived: ' + label)
    motion_negative = []
    previous, actual, case, tick = motion_control
    actor_at = case['corpse_slot'] * 38
    visual_at = 1178 + previous[actor_at + 1] * 8
    for label, offset in (('velocity_x', actor_at + 6), ('velocity_y', actor_at + 8),
        ('fraction_x', actor_at + 10), ('fraction_y', actor_at + 12), ('timer', actor_at + 2),
        ('animation', actor_at + 22), ('visual_x', visual_at), ('visual_y', visual_at + 2),
        ('visual_dimensions', visual_at + 4), ('opaque', actor_at + 3), ('backup', actor_at + 29)):
        changed = bytearray(actual); changed[offset] ^= 1
        try:
            validate_motion(previous, bytes(changed), case, tick, tiles, descriptors)
        except AssertionError:
            motion_negative.append(label)
        else:
            raise AssertionError('semantic corpse-motion mutant survived: ' + label)
    report.update(passed=True, cases=940, operations=3252, construction_boundaries=1880,
        native_bytes_compared_per_execution=5180436, original_repeat_equal=True,
        additional_observer_output_neutrality=True, full_constructor_states_validated=940,
        corpse_motion_steps_verified=corpse_motion_steps, continuing_corpse_steps_verified=continuing_corpse_steps,
        complete_countdown_cases=8, corpse_motion_negative_controls_rejected=motion_negative,
        conversion_kinds=kinds, pool_cases=allocation_results, delayed_expiry_cases=delayed,
        semantic_negative_controls_rejected=negative,
        streams={name: dict(bytes=len(value), raw_sha256=sha(value)) for name, value in streams.items()},
        full_cpp_comparison=False, actual_app_executed=False, reward_allocation_executed=False,
        constructors='corpse in-place reward/fade conversion plus full-pass particle allocation; no direct reward allocation',
        sound='request/priority latch only; no interrupt or playback parity')
except BaseException:
    report['failure'] = traceback.format_exc()
finally:
    OUT.mkdir(exist_ok=True)
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    assert sum(path.stat().st_size for path in OUT.rglob('*') if path.is_file()) < CAP
    print(json.dumps(report), flush=True)
if not report['passed']:
    raise SystemExit(1)
