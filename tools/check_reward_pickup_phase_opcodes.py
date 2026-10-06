"""Pin reward conversion, per-player latches and grant draws in the original."""
import argparse
import hashlib
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent.parent
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
WINDOWS = {
    0x63F6: bytes.fromhex('803eae790075628a46f130e42d1200a2ae79'),
    0x6447: bytes.fromhex('6a039aa81320094031d2b99cffbbffff9a2a0920098946f2'),
    0x6497: bytes.fromhex('803eaf790075628a46f130e42d1200a2af79'),
    0x64E8: bytes.fromhex('6a039aa81320094031d2b99cffbbffff9a2a0920098946f2'),
    0x61C2: bytes.fromhex('a0ae798846e4c646e301'),
    0x622F: bytes.fromhex('a0af798846e4c646e302'),
    0x6E42: bytes.fromhex('807ee4007703e94501'),
    0x6EAD: bytes.fromhex('6a0a9aa813200940506a63e85ae8'),
    0x6ECB: bytes.fromhex('6a049aa813200940506a63e83ce8'),
    0x6F0A: bytes.fromhex('6a0d9aa813200940506a63e8fde7'),
    0x6F28: bytes.fromhex('6a059aa81320094040506a63e8dee7'),
    0x6F47: bytes.fromhex('6a029aa813200940506a63e8c0e7'),
    0xAA64: bytes.fromhex('5800560057005800590056005a00'),
}


def validate(data, check_hash=True):
    if data[:2] != b'MZ' or len(data) < 10 or struct.unpack_from('<H', data, 8)[0] * 16 != 0x770:
        raise ValueError('original MZ image base differs')
    for offset, raw in WINDOWS.items():
        if data[0x770 + offset:0x770 + offset + len(raw)] != raw:
            raise ValueError(f'original reward pickup window differs at 1000:{offset:04x}')
    if check_hash and hashlib.sha256(data).hexdigest() != EXE_SHA:
        raise ValueError('original executable fingerprint differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    data = (ROOT / 'LEZAC.EXE').read_bytes()
    validate(data)
    if args.self_test:
        mutations = 0
        for offset, raw in WINDOWS.items():
            for index in range(len(raw)):
                changed = bytearray(data)
                changed[0x770 + offset + index] ^= 1
                try:
                    validate(changed, check_hash=False)
                except ValueError:
                    mutations += 1
                else:
                    raise ValueError('mutated reward pickup opcode accepted')
        print(f'reward_pickup_opcode_selftest=ok byte_mutations={mutations} native_runtime_claim=0')
    else:
        print('reward_pickup_opcodes=ok windows=13 players=2 conversion_range=3 '
              'normal_ranges=10,4 super_ranges=13,5,2 marker_sprites=88,86,87,88,89,86,90 '
              'deferred_player_grant=1 native_runtime_claim=0')


if __name__ == '__main__':
    main()
