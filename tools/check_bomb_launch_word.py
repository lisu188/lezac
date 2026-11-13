"""Check production bomb launches against the shipped signed-word instructions."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess

from check_actor_floor_friction import fingerprint, native_word
from capture_original_behavior4_targets import EXE_SHA

ROOT = Path(__file__).resolve().parent.parent
LAUNCH = bytes.fromhex('8b46f48bf0d1e001f099b90200f7f9508b46f22df40150')
CLAMP = bytes.fromhex(
    '8b460e9931d029d03dff077e138b460e9931d029d099f77e0e69c0ff0789460e'
    '8b460c9931d029d03dff077e138b460c9931d029d099f77e0c69c0ff0789460c')


def constructor(value):
    # CWD/XOR/SUB leaves a negative absolute value for WORD -32768.
    sign = 0xFFFF if value < 0 else 0
    magnitude = native_word(native_word((value & 0xFFFF) ^ sign) - sign)
    return value if magnitude <= 0x7FF else (-0x7FF if value < 0 else 0x7FF)


def truncate_half(value):
    return -(abs(value) // 2) if value < 0 else value // 2


def velocities(value):
    return constructor(truncate_half(native_word(3 * value))), constructor(native_word(value - 500))


def oracle():
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    if hashlib.sha256(original).hexdigest() != EXE_SHA:
        raise ValueError('original bomb launch executable differs')
    for offset, expected in ((0x6C2B, LAUNCH), (0x2FC1, CLAMP)):
        if original[0x770 + offset:0x770 + offset + len(expected)] != expected:
            raise ValueError(f'original bomb launch instructions differ at {offset:04x}')
    if [velocities(v)[0] for v in (-21846, -21845, -10923, 10923, 21845, 21846)] != [-1, 0, 2047, -2047, 0, 1]:
        raise ValueError('horizontal word-wrap/division boundary differs')
    if [velocities(v)[1] for v in (-32269, -32268, -32267, 500)] != [2047, -32768, -2047, 0]:
        raise ValueError('vertical word-wrap/absolute boundary differs')
    values = range(-32768, 32768)
    expected_x = fingerprint(velocities(v)[0] for v in values)
    expected_y = fingerprint(velocities(v)[1] for v in values)
    wide_clamp = lambda v: max(-0x7FF, min(v, 0x7FF))
    mutants = (
        (fingerprint(wide_clamp(truncate_half(3 * v)) for v in values), expected_x),
        (fingerprint(wide_clamp(v - 500) for v in values), expected_y),
        (fingerprint(wide_clamp(native_word(v - 500)) for v in values), expected_y),
        (fingerprint(constructor(native_word(3 * v) // 2) for v in values), expected_x),
    )
    if any(actual == expected for actual, expected in mutants):
        raise ValueError('word scan does not discriminate a launch arithmetic mutation')
    return expected_x, expected_y


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--exe', type=Path)
    mode.add_argument('--oracle-only', action='store_true')
    args = parser.parse_args()
    expected_x, expected_y = oracle()
    if args.oracle_only:
        print(f'bomb_launch_word_oracle=ok inputs=65536 vx={expected_x} vy={expected_y} '
              'guarded_static_oracle=1 mutants_discriminated=4 live_original_inputs=0')
        return
    result = subprocess.run([str(args.exe.resolve()), '--debug-bomb-launch-word-scan'], cwd=ROOT,
                            env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'),
                            capture_output=True, text=True, timeout=30)
    wanted = ''.join(f'bomb_launch_word_scan inputs=65536 weapon={weapon} owner={owner} '
                     f'vx={expected_x} vy={expected_y}\n' for weapon in range(4) for owner in (1, 2))
    if result.returncode != 0 or result.stdout != wanted:
        raise ValueError('actual compiled bomb constructor differs: ' + result.stdout + result.stderr)
    print('bomb_launch_word=ok inputs=65536 constructors=524288 weapons=4 owners=2 '
          'guarded_static_oracle=1 mutants_discriminated=4 live_original_inputs=0')


if __name__ == '__main__':
    main()
