"""Original-backed health pickup, inherited animation and kind-11 actor replay."""
import argparse
import copy
import gzip
import os
from pathlib import Path
import struct
import subprocess
import uuid

import level1_fidelity as fidelity
import level1_original as original
import natural_level3_handoff as recovered
from capture_original_monster_sprite_consumption_procmem import parse_sprite_bank

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/natural_level4_health_reward'
FIXTURE_SHA256 = 'b516c145eb34b84fa90a336c2e5a8aa8800460e7d7ac5de023e57a52ab7fc732'
ROUTE_SHA256 = '81594166e42931e46af8e9257a0444b09f01c864fa3b72834a548ec27548e0d0'
FIRST, ENTRY, LAST = 8905, 9422, 11360
require = fidelity.require


def descriptors():
    bank = parse_sprite_bank(ROOT / 'BOMOMIMK.SPR')
    require(bank['count'] == 91 and bank['payload_bytes'] == 19985, 'original sprite bank differs')
    return bytes(4) + b''.join(struct.pack('<BBH', *size, offset)
        for size, offset in zip(bank['dimensions'], bank['pixel_offsets']))


def check_route(path):
    require(fidelity.sha256(path) == ROUTE_SHA256, 'health reward route differs')
    settings, events = fidelity.read_route(path)
    require(settings['ticks'] == LAST, 'health reward route length differs')
    return settings, events


def fixture():
    path = FIXTURE / 'native.json.gz'
    require(fidelity.sha256(path) == FIXTURE_SHA256, 'health reward native fixture differs')
    data = fidelity.strict_json(gzip.decompress(path.read_bytes()).decode())
    require(data['schema'] == 'lezac.native-level4-health-reward.v1' and
        data['expected_bytes_source'] == 'original_only' and data['state_injections'] is False and
        data['normalized_bytes'] == data['coherence_differences'] == 0 and
        data['raw_coherent_boundaries'] == 5878 and data['whole_game_complete'] is False and
        data['original_fidelity_claim'] is False and data['assets'] == {
            name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, 'native evidence scope differs')
    require(len(data['reference_rows']) == 3942 and len(data['actor_rows']) == 3878,
        'health reward fixture cardinality differs')
    keys = [(row['tick'], row['phase']) for row in data['actor_rows']]
    require(keys == [(tick, phase) for tick in range(ENTRY, LAST + 1)
        for phase in ('present', 'post_update')], 'native actor boundaries differ')
    require(sum(len(row['kind11']) for row in data['actor_rows']) == 1590 and
        sum(len(row['rewards']) for row in data['actor_rows']) == 552, 'native actor observations differ')
    mapped = {(row['section'], row['index'], row['phase']): row['projection']['mapped']
        for row in data['reference_rows'][1:-1]}
    require(mapped['level4', 11306, 'present']['players'][0]['energy'] == 22 and
        mapped['level4', 11306, 'post_update']['players'][0]['energy'] == 55 and
        mapped['level4', LAST, 'post_update']['progress'] == [2, 144],
        'native health pickup timing or endpoint differs')
    check_route(FIXTURE / 'route.txt')
    return data


def cpp_actors(state, table):
    actors, orders = [], set()

    def add(order, value, frame, animation):
        require(order > 0 and order not in orders, 'duplicate/invalid C++ kind-11 actor order')
        orders.add(order)
        offset = frame * 4
        require(0 < offset <= len(table) - 4, 'C++ sprite descriptor out of range')
        value['descriptor'] = table[offset:offset + 4].hex()
        value['animation'] = [part & 255 for part in animation]
        actors.append((order, value))

    for row in state['transients']:
        x, y, vx, vy, fx, fy, kind, timer, hotspot, sprite = row['state']
        if kind == 11:
            add(row['order'], dict(xy=[x, y], motion=[vx, vy, fx, fy], kind=kind,
                timer=timer, hotspot=hotspot), sprite + 1, row['animation'])
    for row in state['markers']:
        x, y, fx, fy, vx, vy, timer, frame, kind, mode = row['state']
        require(kind == 11 and mode == 5, 'C++ marker dispatch differs')
        require(0 < frame * 4 <= len(table) - 4, 'C++ marker descriptor out of range')
        add(row['order'], dict(xy=[x, y], motion=[vx, vy, fx, fy], kind=kind,
            timer=timer, hotspot=16 - table[frame * 4 + 1]), frame, row['animation'])
    rewards = []
    for row in sorted(state['rewards'], key=lambda value: value['order']):
        kind, vx, vy, fx, fy, hotspot, timer, collected = row['state']
        require(0 <= kind <= 6 and not collected, 'C++ reward kind/liveness differs')
        require(row['x'] == int(row['x']) and row['y'] == int(row['y']),
            'C++ reward position is not an integral original pixel coordinate')
        at = (62 + kind) * 4
        rewards.append(dict(xy=[int(row['x']), int(row['y'])], motion=[vx, vy, fx, fy],
            kind=19 + kind, timer=timer, hotspot=hotspot, descriptor=table[at:at + 4].hex(),
            animation=[part & 255 for part in row['animation']]))
    return dict(kind11=[value for _, value in sorted(actors)], rewards=rewards)


def check_actor_state(state, expected, table):
    actual = cpp_actors(state, table)
    difference = fidelity.first_difference({name: expected[name] for name in ('kind11', 'rewards')}, actual)
    require(difference is None, 'health reward actor differs: ' + str(difference))


def compare(cpp):
    data = fixture()
    report = recovered.compare(cpp, data['reference_rows'], last=LAST,
        route_validator=check_route, expected_frames=2000)
    wanted = {(row['tick'], row['phase']): row for row in data['actor_rows']}
    table, seen = descriptors(), set()
    for line in (cpp / 'trace.jsonl').open(encoding='utf-8'):
        row = fidelity.strict_json(line)
        key = row.get('tick'), row.get('phase')
        if key in wanted:
            require(key not in seen, 'duplicate C++ health-reward actor boundary')
            check_actor_state(row['state'], wanted[key], table)
            seen.add(key)
    require(seen == set(wanted), 'missing health-reward actor boundaries')
    return dict(report, actor_boundaries=len(seen), kind11_observations=1590,
        reward_observations=552, health_pickup_tick=11306, health_before=22, health_after=55,
        inherited_animation_bytes=7, level4_completion_claim=False, whole_game_complete=False)


def replay(exe, out):
    fixture()
    out.mkdir(parents=True, exist_ok=True)
    cpp = out.resolve() / ('run-' + uuid.uuid4().hex)
    command = [str(exe.resolve()), '--replay-level1-scout', str(FIXTURE / 'route.txt'),
        str(cpp), str(FIRST), '--original-intro-wait', '--result-reels']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=550,
        env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy',
            LEZAC_LOAD_JSON_ASSETS='0', LEZAC_LOAD_ORIGINAL_ASSETS='1'))
    require(cpp.is_dir(), 'health reward replay produced no evidence')
    for name, content in (('stdout.txt', result.stdout), ('stderr.txt', result.stderr)):
        (cpp / name).write_text(content, encoding='utf-8')
    (cpp / 'child-result.json').write_bytes(original.json_bytes(dict(exit_code=result.returncode)))
    (cpp / 'route.txt').write_bytes((FIXTURE / 'route.txt').read_bytes())
    (cpp / 'command.json').write_bytes(original.json_bytes(dict(command=command,
        source=fidelity.source_version(ROOT), executable_sha256=fidelity.sha256(exe),
        assets={name: fidelity.sha256(ROOT / name) for name in fidelity.ASSETS}, audio='dummy',
        video='dummy', state_injections=False, whole_game_complete=False)))
    require(result.returncode == 0, 'health reward replay failed: ' + result.stderr.strip())
    report = compare(cpp)
    (cpp / 'comparison.json').write_bytes(original.json_bytes(report))
    return report


def guard():
    fixture()
    state = dict(transients=[dict(order=1, state=[548, 361, 0, -36, 48, 252, 11, 25, 10, 86],
        animation=[44, 44, 45, 254, 2, 0, 1])], markers=[], rewards=[])
    table = descriptors()
    expected = cpp_actors(state, table)
    rejected = 0
    for index in range(7):
        changed = copy.deepcopy(state)
        changed['transients'][0]['animation'][index] ^= 1
        try:
            check_actor_state(changed, expected, table)
        except fidelity.EvidenceError:
            rejected += 1
        else:
            raise fidelity.EvidenceError('ignored inherited animation byte')
    # Equal dimensions are not sufficient to select the sprite-88 projection.
    import natural_level3_gate_projections as projection
    for sprite in (85, 86, 87, 88):
        raw = bytearray(38)
        raw[0], raw[20] = 11, 10
        at = (sprite + 1) * 4
        native = dict(actor_count=1, actors=raw.hex(), visuals=(bytes(4) + table[at:at + 4]).hex())
        require(bool(projection.native_markers(native)) == (sprite == 88),
            'native score-marker classifier conflates equal-sized sprites')
    fractional = 0
    for coordinate in ('x', 'y'):
        reward = dict(order=1, x=388.0, y=181.0, state=[2, 0, 184, 46, 100, 6, 100, 0],
            animation=[51, 50, 52, 254, 2, 0, 1])
        reward[coordinate] += 0.5
        try:
            cpp_actors(dict(transients=[], markers=[], rewards=[reward]), table)
        except fidelity.EvidenceError:
            fractional += 1
        else:
            raise fidelity.EvidenceError('fractional C++ reward coordinate was truncated')
    return dict(status='guarded', animation_mutations_rejected=rejected,
        equal_size_descriptor_cases=4, fractional_coordinate_mutations_rejected=fractional,
        original_runtime_claim=False, whole_game_complete=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('replay', 'compare', 'guard'))
    for name in ('exe', 'out', 'cpp'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.command == 'replay':
        require(args.exe is not None and args.out is not None, 'health reward executable/output required')
        report = replay(args.exe, args.out)
    elif args.command == 'compare':
        require(args.cpp is not None, 'health reward C++ evidence required')
        report = compare(args.cpp)
    else:
        report = guard()
    print(original.json_bytes(report).decode(), flush=True)


if __name__ == '__main__':
    main()
