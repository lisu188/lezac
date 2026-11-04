"""Nine declared live flame fields, not complete raw-record equivalence."""
import struct

import level1_fidelity as fidelity

FIELDS = ('cell', 'vx8', 'vy8', 'fraction_x', 'fraction_y', 'timer', 'glyph', 'variant', 'mass')
DOMAINS = ((0, 65535), *((-128, 127),) * 4, *((0, 255),) * 4)
EXCLUDED = ('retained word at record +2..3', 'inactive slots', 'other actor fields', 'full DS/RAM')
require = fidelity.require


def validate_projection(rows):
    require(isinstance(rows, list) and len(rows) <= 198, 'flame projection extent differs')
    for row in rows:
        require(isinstance(row, list) and len(row) == len(FIELDS), 'flame projection fields differ')
        for name, value, (low, high) in zip(FIELDS, row, DOMAINS):
            require(fidelity.integer(value, low, high), 'flame projection value differs: ' + name)


def native_flames(data):
    require(isinstance(data, (bytes, bytearray)) and len(data) == 65536, 'original flame DS extent differs')
    count = struct.unpack_from('<H', data, 0x2076)[0]
    require(count <= 198, 'original flame count differs')
    rows = [list(struct.unpack_from('<H2xbbbbBBB', data, 0x2093 + 11 * slot))
            + [data[0x78d5 + slot]] for slot in range(1, count + 1)]
    validate_projection(rows)
    return rows


def cpp_flames(state):
    require(isinstance(state, dict) and 'flames' in state, 'C++ flame projection is missing')
    validate_projection(state['flames'])
    return [list(row) for row in state['flames']]


def compare(state, expected):
    validate_projection(expected)
    actual = cpp_flames(state)
    require(actual == expected, 'original/C++ flame projection differs: ' +
            repr(fidelity.first_difference(expected, actual)))
