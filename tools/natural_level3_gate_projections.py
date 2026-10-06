"""Bounded Level 3 native monster/corpse, marker and terrain projections."""
import struct

import level1_fidelity as fidelity
import level1_original as original
import capture_original_shipped_monster_profiles as shipped
from original_debris_table import decode_live_debris

require = fidelity.require
PROFILES = {(raw[11], raw[26], slot + 1) for level, slot, _, raw in shipped.profiles() if level == 3}
require(PROFILES == {(4, 3, 1), (2, 4, 2), (1, 3, 3)}, 'Level 3 shipped profiles differ')


def native_monsters(state):
    actors, visuals = bytes.fromhex(state['actors']), bytes.fromhex(state['visuals'])
    require(len(actors) == state['actor_count'] * 38 and state['actor_count'] <= 30, 'native actor extent differs')
    result = []
    for index in range(state['actor_count']):
        actor = actors[index * 38:(index + 1) * 38]
        if not 1 <= actor[0] <= 8 and actor[0] != 12:
            continue
        corpse = actor[0] == 12
        if corpse:
            require(actor[21] == 2 and actor[37] in {p[2] for p in PROFILES} and
                    1 <= actor[2] <= 25 and actor[27] == 0, 'native corpse scope differs')
        else:
            require((actor[0], actor[21], actor[37]) in PROFILES, 'native monster scope differs')
        require(actor[1] * 8 + 8 <= len(visuals), 'native monster visual differs')
        x, y = struct.unpack_from('<hh', visuals, actor[1] * 8)
        row = dict(identity=[actor[0], actor[21], actor[37] - 1, 0 if corpse else 1],
                   position=[x, y - actor[20], actor[20]], motion=list(struct.unpack_from('<hhHH', actor, 6)),
                   ai=list(struct.unpack_from('<HHH', actor, 14)),
                   animation=[actor[22] - 1, actor[23] - 1, actor[24] - 1, actor[25], actor[26],
                              actor[27], struct.unpack_from('b', actor, 28)[0]])
        row['raw_countdown' if corpse else 'hp'] = actor[2] if corpse else actor[36] + 1
        result.append(row)
    return result


def cpp_monsters(state):
    result, orders = [], set()
    for monster in sorted(state['monsters'], key=lambda item: item['order']):
        require(monster['order'] not in orders and monster['health'][1] == 1, 'C++ actor order/liveness differs')
        orders.add(monster['order'])
        kind, behavior, slot, attached = monster['identity']
        corpse = kind == 12
        if corpse:
            require(behavior == 2 and slot + 1 in {p[2] for p in PROFILES} and attached == 0 and
                    1 <= monster['health'][2] <= 50 and monster['animation'][5] == 0 and
                    monster['health'][4:6] == [1, 1], 'C++ corpse scope differs')
        else:
            require((kind, behavior, slot + 1) in PROFILES and attached == 1, 'C++ monster scope differs')
        row = dict(identity=monster['identity'], position=monster['position'], motion=monster['motion'],
                   ai=monster['ai'][:3], animation=[monster['animation'][i] for i in (0, 2, 3, 7, 4, 5, 6)])
        row['raw_countdown' if corpse else 'hp'] = (monster['health'][2] + 1) // 2 if corpse else monster['health'][0]
        result.append(row)
    return result


def native_terrain(segment):
    require(len(segment) == 65536, 'native DS extent differs')
    last_live, debris = decode_live_debris(segment)
    count = original.word(segment, 0x2080)
    require(count <= 250, 'native collapse extent differs')
    return dict(last_live_debris=last_live,
                debris=[list(struct.unpack('<HHbbbbBBB', bytes.fromhex(raw))) for _, raw in debris],
                collapse=[list(struct.unpack_from('<HHHBBbbHBBB', segment, 0x6620 + index * 15))
                          for index in range(count)])


def cpp_terrain(state):
    return dict(last_live_debris=199 + len(state['debris']), debris=state['debris'],
                collapse=[[record[i] for i in (2, 3, 5, 6, 7, 8, 9, 12, 10, 11, 13)]
                          for record in state['collapse']])


def native_markers(state):
    actors, visuals = bytes.fromhex(state['actors']), bytes.fromhex(state['visuals'])
    result = []
    for index in range(state['actor_count']):
        raw = actors[index * 38:(index + 1) * 38]
        visual = visuals[raw[1] * 8:raw[1] * 8 + 8]
        if raw[0] == 11 and raw[20] == 10 and list(visual[4:6]) == [20, 6]:
            result.append(dict(xy=list(struct.unpack_from('<hh', visual)),
                               motion=list(struct.unpack_from('<hhHH', raw, 6)),
                               kind=raw[0], timer=raw[2], hotspot=raw[20]))
    return result


def cpp_markers(state):
    return [dict(xy=row['state'][:2], motion=row['state'][2:6], kind=row['state'][6],
                 timer=row['state'][7], hotspot=row['state'][8])
            for row in sorted(state['transients'], key=lambda item: item['order'])
            if row['state'][6] == 11 and row['state'][9] == 88]


def native_gate(segment):
    return dict(bonus_flag=segment[0x79c5], destruction_flag=segment[0x79c6],
                collapse_count=original.word(segment, 0x2080))


def eligible(gate):
    return bool(gate['bonus_flag'] and gate['destruction_flag'] and gate['collapse_count'] == 0)
