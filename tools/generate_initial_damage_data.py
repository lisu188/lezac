"""Generate logical-loader low DS data, not a natural-startup memory snapshot."""
import argparse
import hashlib
from pathlib import Path
import struct


def render(root):
    raw = (root / 'LEZAC.EXE').read_bytes()
    if hashlib.sha256(raw).hexdigest() != '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec':
        raise ValueError('original executable pin mismatch')
    header = struct.unpack_from('<14H', raw)
    if header[3] != 468 or header[4] * 16 != 0x770:
        raise ValueError('original loader layout mismatch')
    image = bytearray(raw[0x770:])
    for index in range(header[3]):
        offset, segment = struct.unpack_from('<HH', raw, header[12] + 4 * index)
        address = segment * 16 + offset
        struct.pack_into('<H', image, address, (struct.unpack_from('<H', image, address)[0] + 0x1000) & 65535)
    data = image[0xaa20:]
    if len(data) != 6928 or data[0xa06:0xa08] != bytes(2):
        raise ValueError('original low data layout mismatch')
    rows = ['    ' + ', '.join(f'0x{byte:02x}' for byte in data[index:index + 16]) + ','
        for index in range(0, len(data), 16)]
    return ('#pragma once\n\n#include <algorithm>\n#include <array>\n#include <cstdint>\n\n'
        'namespace lezac::gameplay {\n\n'
        '// Generated from pinned LEZAC.EXE with logical load segment 1000.\n'
        '// This is loader data, not a complete initialized DOS runtime image.\n'
        'inline std::array<uint8_t, 65536> initialDamageLaneData() {\n'
        '    static constexpr std::array<uint8_t, 6928> data{{\n' + '\n'.join(rows) + '\n    }};\n'
        '    std::array<uint8_t, 65536> bytes{};\n'
        '    std::copy(data.begin(), data.end(), bytes.begin());\n'
        '    return bytes;\n}\n\n}  // namespace lezac::gameplay\n').encode()


def verify_generated(actual, expected):
    # Git may check text out with CRLF; all non-newline bytes remain exact.
    if actual.replace(b'\r\n', b'\n') != expected:
        raise ValueError('generated low data differs from original loader')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    expected = render(args.root)
    if args.output:
        if args.output.exists():
            raise ValueError('refusing to overwrite generated output')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(expected)
    else:
        verify_generated((args.root / 'src/gameplay/initial_damage_data.hpp').read_bytes(), expected)
    print('damage_lane_initial_data=ok source_bytes=6928 executable_pinned=1 natural_startup=0')


if __name__ == '__main__':
    main()
