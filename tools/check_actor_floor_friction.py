"""Compare all signed-word C++ friction inputs to the guarded 5B86 sequence."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess

from capture_original_timed_writeback import FRICTION
from capture_original_behavior4_targets import EXE_SHA

ROOT = Path(__file__).resolve().parent.parent


def native_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def emulate(value):
    # 5B97 CWD/XOR/SUB forms a WORD absolute value; 5B9C uses signed JGE.
    sign = 0xFFFF if value < 0 else 0
    magnitude = native_word((value & 0xFFFF) ^ sign)
    magnitude = native_word(magnitude - sign)
    return 0 if magnitude < 43 else native_word(value + (42 if value < 0 else -42))


def fingerprint(values):
    state = 0xCBF29CE484222325
    for value in values:
        for byte in struct.pack('<h', value):
            state = ((state ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f'{state:016x}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    args = parser.parse_args()
    original = (ROOT / 'LEZAC.EXE').read_bytes()
    if hashlib.sha256(original).hexdigest() != EXE_SHA or original[0x770 + 0x5B86:0x770 + 0x5B86 + len(FRICTION)] != FRICTION:
        raise ValueError('original friction instruction window differs')
    if [emulate(v) for v in (-32768, -32767, -43, -42, 0, 42, 43, 32767)] != [0, -32725, -1, 0, 0, 0, 1, 32725]:
        raise ValueError('friction instruction emulator boundary differs')
    expected = fingerprint(emulate(v) for v in range(-32768, 32768))
    airborne = fingerprint(range(-32768, 32768))
    # Verify these mutations do discriminate over the same complete word domain.
    mutants = (fingerprint(0 if abs(v) < 43 else native_word(v + (42 if v < 0 else -42)) for v in range(-32768, 32768)),
               fingerprint(0 if native_word(abs(v)) < 43 else native_word(v + (41 if v < 0 else -41)) for v in range(-32768, 32768)),
               fingerprint(0 if native_word(abs(v)) < 44 else native_word(v + (42 if v < 0 else -42)) for v in range(-32768, 32768)))
    if any(value == expected for value in mutants):
        raise ValueError('friction scan does not discriminate a widened/threshold/step mutation')
    result = subprocess.run([str(args.exe.resolve()), '--debug-actor-floor-friction-scan'], cwd=ROOT,
                            env=dict(os.environ, SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='dummy'),
                            capture_output=True, text=True, timeout=30)
    wanted = f'actor_floor_friction_scan inputs=65536 helper={expected} idle_ground={expected} idle_air={airborne}\n'
    if result.returncode != 0 or result.stdout != wanted:
        raise ValueError('actual compiled helper/player friction differs: ' + result.stdout + result.stderr)
    print('actor_floor_friction_word=ok inputs=65536 compiled_helper=1 compiled_idle_player=1 guarded_static_oracle=1 mutants_discriminated=3 live_original_inputs=0')


if __name__ == '__main__':
    main()
