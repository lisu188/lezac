"""Check the compiled frequency conversion against the pinned original Sound helper."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess

EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
SOUND_HELPER = bytes.fromhex(
    '8bdc368b5f04b8dd34ba12003bd3731af7f38bd8e461a8037508'
    '0c03e661b0b6e6438ac3e6428ac7e642ca0200')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    original = (args.root / 'LEZAC.EXE').read_bytes()
    if hashlib.sha256(original).hexdigest() != EXE_SHA:
        raise RuntimeError('original executable changed')
    if original[0x8ed9:0x8f06] != SOUND_HELPER:
        raise RuntimeError('original Sound helper changed')
    # MOV AX,34dd / MOV DX,0012 / CMP DX,BX / JAE return / DIV BX.
    numerator = struct.unpack_from('<H', SOUND_HELPER, 7)[0]
    threshold = struct.unpack_from('<H', SOUND_HELPER, 10)[0]
    numerator |= threshold << 16
    result = subprocess.run([str(args.exe.resolve()), '--divisors'],
                            capture_output=True, text=True, check=True, timeout=30)
    lines = result.stdout.splitlines()
    if len(lines) != 65536 or any(len(row) != 4 for row in lines):
        raise RuntimeError('compiled conversion scan is incomplete')
    actual = [int(row, 16) for row in lines]
    expected = [0 if frequency <= threshold else numerator // frequency
                for frequency in range(65536)]
    if actual != expected:
        index = next(i for i, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1])
        raise RuntimeError(f'compiled conversion differs at frequency {index}')
    packed = struct.pack('<65536H', *actual)
    raw = (args.root / 'PROEFS.SON').read_bytes()
    count = struct.unpack_from('<H', raw)[0]
    if count != 130 or len(raw) != 2 + count * 6:
        raise RuntimeError('shipped sound-bank shape changed')
    tones = [struct.unpack_from('<H', raw, 2 + index * 6)[0] for index in range(count)]
    tones = [frequency for frequency in tones if frequency != 0x7530]
    if not tones or any(frequency <= threshold for frequency in tones):
        raise RuntimeError('shipped tone requires additional ignored-command evidence')
    mutations = {
        'wrong_numerator': [0 if f <= threshold else (numerator + 1) // f for f in range(65536)],
        'wrong_threshold': [0 if f < 32 else numerator // f for f in range(65536)],
        'no_div_conversion': [0 if f <= threshold else f for f in range(65536)],
    }
    if any(values == actual for values in mutations.values()):
        raise RuntimeError('conversion oracle did not distinguish a regression')
    print(f'sound_pitch_original=ok frequencies={len(actual)} helper_bytes={len(SOUND_HELPER)}'
          f' numerator={numerator} ignored_max={threshold} shipped_tones={len(tones)}'
          f' divisor_sha256={hashlib.sha256(packed).hexdigest()}'
          ' opcode_model=1 native_runtime_claim=0 whole_game_complete=0')


if __name__ == '__main__':
    main()
