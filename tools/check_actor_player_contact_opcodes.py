"""Pin both players' original signed-word contact comparisons, not live outcomes."""
import argparse
import hashlib
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent.parent
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
WINDOWS = {
    0x62F5: bytes.fromhex('c47ec6268b052b46d48946fc'),
    0x6301: bytes.fromhex('c47ec6268b45022b46d28946fa'),
    0x6330: bytes.fromhex('c47ec6268b052b46d48946f8'),
    0x633C: bytes.fromhex('c47ec6268b45022b46d28946f6'),
    0x63BE: bytes.fromhex('8b46fc9931d029d03d0a007c03e99100'),
    0x63CE: bytes.fromhex('8b46fa9931d029d03d0a007c03e98100'),
    0x645F: bytes.fromhex('8b46f89931d029d03d0a007c03e99100'),
    0x646F: bytes.fromhex('8b46f69931d029d03d0a007c03e98100'),
    0x63F0: bytes.fromhex('fe06e879'),
    0x6491: bytes.fromhex('fe06e979'),
}


def validate(data, check_hash=True):
    if data[:2] != b'MZ' or len(data) < 10:
        raise ValueError('original MZ header differs')
    base = struct.unpack_from('<H',data,8)[0] * 16
    if base != 0x770:
        raise ValueError('original image base differs')
    for offset,raw in WINDOWS.items():
        if data[base+offset:base+offset+len(raw)] != raw:
            raise ValueError(f'original contact window differs at 1000:{offset:04x}')
    if check_hash and hashlib.sha256(data).hexdigest() != EXE_SHA:
        raise ValueError('original executable fingerprint differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true')
    args = parser.parse_args()
    data = (ROOT / 'LEZAC.EXE').read_bytes()
    validate(data)
    accepted = []
    for word in range(65536):
        # CWD/XOR/SUB leaves 0x8000 unchanged; CMP/JL interprets AX as signed.
        sign = 0xffff if word & 0x8000 else 0
        magnitude = ((word ^ sign) - sign) & 0xffff
        signed = magnitude if magnitude < 0x8000 else magnitude - 65536
        if signed < 10:
            accepted.append(word)
    if accepted != [*range(10),0x8000,*range(0xfff7,0x10000)]:
        raise ValueError('signed-word comparison domain differs')
    if args.self_test:
        mutations = 0
        for offset,raw in WINDOWS.items():
            for index in range(len(raw)):
                changed = bytearray(data)
                changed[0x770+offset+index] ^= 1
                try:
                    validate(changed,check_hash=False)
                except ValueError:
                    mutations += 1
                else:
                    raise ValueError('mutated contact opcode accepted')
        changed = bytearray(data)
        changed[-1] ^= 1
        try:
            validate(changed)
        except ValueError:
            pass
        else:
            raise ValueError('mutated original executable accepted')
        print(f'actor_player_contact_opcode_selftest=ok byte_mutations={mutations} original_mutation=1 native_runtime_claim=0')
    else:
        print('actor_player_contact_opcodes=ok players=2 axes=4 threshold=10 accepted_words=20 min_word_passes=1 native_runtime_claim=0 wrapped_subtractions=4')


if __name__ == '__main__':
    main()
