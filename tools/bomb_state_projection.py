"""Declared original/port bomb observations, not a complete actor-record model."""
import copy
import struct

import level1_fidelity as fidelity

FIELDS = ('kind', 'counter', 'pixel_x', 'pixel_y', 'vx8', 'vy8', 'fraction_x_word', 'fraction_y_word', 'behavior')
EXCLUDED = ('owner', 'visual descriptor bytes', 'hotspot', 'unused/stale actor bytes')
require = fidelity.require


def validate_projection(rows):
    require(isinstance(rows, list) and len(rows) <= 30, 'bomb projection extent differs')
    for row in rows:
        require(isinstance(row, dict) and set(row) == set(FIELDS), 'bomb projection fields differ')
        for key, low, high in (('kind', 13, 16), ('counter', 0, 255), ('pixel_x', -32768, 32767),
            ('pixel_y', -32768, 32767), ('vx8', -32768, 32767), ('vy8', -32768, 32767),
            ('fraction_x_word', 0, 65535), ('fraction_y_word', 0, 65535), ('behavior', 2, 2)):
            require(fidelity.integer(row[key], low, high), 'bomb projection value differs: ' + key)


def native_bombs(data):
    require(len(data) == 65536, 'original bomb DS length differs')
    count, visual_count = data[0x208d], data[0xc496]
    require(count <= 30 and visual_count <= 32, 'original bomb actor/visual extent differs')
    result = []
    for index in range(count):
        actor = data[0x1bd4 + index * 38:0x1bd4 + (index + 1) * 38]
        if not 0x0d <= actor[0] <= 0x10:
            continue
        require(actor[1] < visual_count and actor[21] == 2, 'original bomb visual/behavior differs')
        x, y = struct.unpack_from('<hh', data, 0xc21e + actor[1] * 8)
        vx, vy, fraction_x, fraction_y = struct.unpack_from('<hhHH', actor, 6)
        result.append(dict(kind=actor[0], counter=actor[2], pixel_x=x, pixel_y=y, vx8=vx, vy8=vy,
            fraction_x_word=fraction_x, fraction_y_word=fraction_y, behavior=actor[21]))
    validate_projection(result)
    return result


def cpp_bombs(state):
    require(isinstance(state['bombs'], list) and len(state['bombs']) <= 30, 'C++ bomb extent differs')
    result, orders = [], set()
    for bomb in sorted(state['bombs'], key=lambda value: value['order']):
        require(set(bomb) == {'order', 'visual_order', 'owner', 'type', 'position', 'motion', 'fuse'},
            'C++ bomb fields differ')
        require(fidelity.integer(bomb['order'], 1, 2**64 - 1) and bomb['order'] not in orders,
            'C++ bomb order differs')
        orders.add(bomb['order'])
        kind = bomb['type']
        require(fidelity.integer(kind, 0, 3) and len(bomb['position']) == len(bomb['motion']) == 5 and
            len(bomb['fuse']) == 2 and type(bomb['motion'][4]) is int and bomb['motion'][4] == 1,
            'C++ bomb shape/behavior differs')
        require(all(type(value) is int for key in ('position', 'motion', 'fuse') for value in bomb[key]) and
            1 <= bomb['fuse'][0] <= bomb['fuse'][1] and bomb['fuse'][1] == (40, 60, 80, 400)[kind],
            'C++ bomb fuse/integer domain differs')
        result.append(dict(kind=kind + 0x0d, counter=(bomb['fuse'][0] + 1) // 2,
            pixel_x=bomb['position'][2], pixel_y=bomb['position'][3], vx8=bomb['motion'][0],
            vy8=bomb['motion'][1], fraction_x_word=bomb['motion'][2], fraction_y_word=bomb['motion'][3], behavior=2))
    validate_projection(result)
    return result


def compare(state, expected):
    validate_projection(expected)
    actual = cpp_bombs(state)
    require(actual == expected, 'original/C++ bomb projection differs: ' +
        repr(fidelity.first_difference(expected, actual)))


def guard():
    data = bytearray(65536)
    data[0x208d] = data[0xc496] = 1
    actor = 0x1bd4
    data[actor], data[actor + 2], data[actor + 21] = 14, 30, 2
    struct.pack_into('<hhHH', data, actor + 6, 128, -500, 17, 29)
    struct.pack_into('<hh', data, 0xc21e, 100, 300)
    expected = native_bombs(bytes(data))
    state = dict(bombs=[dict(order=3, visual_order=0, owner=1, type=1,
        position=[13, 37, 100, 300, -1], motion=[128, -500, 17, 29, 1], fuse=[60, 60])])
    compare(state, expected)
    rejected = []
    for name, mutate in (
        ('kind', lambda b: b.__setitem__('type', 2)), ('counter', lambda b: b['fuse'].__setitem__(0, 58)),
        ('pixel_x', lambda b: b['position'].__setitem__(2, 101)), ('pixel_y', lambda b: b['position'].__setitem__(3, 301)),
        ('vx8', lambda b: b['motion'].__setitem__(0, 129)), ('vy8', lambda b: b['motion'].__setitem__(1, -499)),
        ('fraction_x', lambda b: b['motion'].__setitem__(2, 18)), ('fraction_y', lambda b: b['motion'].__setitem__(3, 30)),
        ('moving', lambda b: b['motion'].__setitem__(4, 0)), ('maximum_fuse', lambda b: b['fuse'].__setitem__(1, 59)),
    ):
        changed = copy.deepcopy(state)
        mutate(changed['bombs'][0])
        try:
            compare(changed, expected)
        except fidelity.EvidenceError:
            rejected.append(name)
        else:
            raise fidelity.EvidenceError('undetected bomb mutation: ' + name)
    for name, mutate in (
        ('native_actor_extent', lambda d: d.__setitem__(0x208d, 31)),
        ('native_visual_extent', lambda d: d.__setitem__(0xc496, 33)),
        ('native_bomb_visual', lambda d: d.__setitem__(actor + 1, 1)),
        ('native_bomb_behavior', lambda d: d.__setitem__(actor + 21, 3)),
    ):
        changed = bytearray(data)
        mutate(changed)
        try:
            native_bombs(bytes(changed))
        except fidelity.EvidenceError:
            rejected.append(name)
        else:
            raise fidelity.EvidenceError('invalid native bomb scope accepted: ' + name)
    require(len(rejected) == 14, 'bomb control domain differs')
    return rejected
