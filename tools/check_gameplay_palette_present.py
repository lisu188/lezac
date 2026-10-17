#!/usr/bin/env python3
"""Check the final actual SDL submission, not only the App's RGB buffer."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

from frame_compare import read_ppm
from original_capture_contract import read_canonical_assets


def check(exe, observer, out):
    root = Path(__file__).resolve().parents[1]
    environment = {key: os.environ[key] for key in ('HOME', 'PATH', 'LANG') if key in os.environ}
    environment.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', SDL_RENDER_DRIVER='software',
                       LEZAC_LOAD_ORIGINAL_ASSETS='1', PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(out),
                       LD_PRELOAD=str(observer), LEZAC_PRESENT_LAST_FRAME=str(out / 'last-frame.argb'))
    command = [str(exe), '--debug-gameplay-palette-presentation', str(out / 'frames')]
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    report = dict(argv=command, environment=environment, binary=str(exe), observer=str(observer),
                  natural_route=False, whole_game_parity=False,
                  status='failed')
    try:
        canonical = read_canonical_assets(root)
        report['binary_sha256'] = sha(exe.read_bytes())
        report['observer_sha256'] = sha(observer.read_bytes())
        result = subprocess.run(command, cwd=root, env=environment, capture_output=True, timeout=60)
        (out / 'process.log').write_bytes(result.stdout + result.stderr)
        report['returncode'] = result.returncode
        result.check_returncode()
        rows = re.findall(rb'^sdl_present_observation sequence=(\d+) hash=(\d+) pixels=64000 exact_scale=3$',
                          result.stdout, re.MULTILINE)
        if len(rows) < 80 or [int(row[0]) for row in rows] != list(range(1, len(rows) + 1)):
            raise ValueError('missing or nonconsecutive SDL submissions')
        if b'gameplay_palette_presentation=ok frames=80 ' not in result.stdout:
            raise ValueError('missing App completion')
        width, height, rgb = read_ppm(out / 'frames/frame_80.ppm')
        if (width, height) != (320, 200):
            raise ValueError('unexpected App frame geometry')
        expected = [0xff000000 | (rgb[at] << 16) | (rgb[at + 1] << 8) | rgb[at + 2]
                    for at in range(0, len(rgb), 3)]
        actual = list(struct.unpack('<64000I', (out / 'last-frame.argb').read_bytes()))
        different = sum(left != right for left, right in zip(expected, actual, strict=True))
        report.update(submissions=len(rows), different_pixels=different, pixels=64000,
                      last_sdl_hash=int(rows[-1][1]), app_rgb_sha256=sha(rgb))
        if different:
            raise ValueError(f'last SDL submission differs from the late-palette App frame: {different} pixels')
        if read_canonical_assets(root) != canonical:
            raise ValueError('canonical assets changed')
        report['status'] = 'passed'
        print('gameplay_palette_sdl=ok pixels=64000 exact_scale=3 late_palette_submitted=1 '
              'seeded_scene=1 natural_route=0 whole_game_parity=0')
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', required=True, type=Path)
    parser.add_argument('--observer', required=True, type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        parser.error('SDL interposition is supported only on Linux')
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        check(args.exe.resolve(), args.observer.resolve(), args.out.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='lezac-palette-present-') as temporary:
            check(args.exe.resolve(), args.observer.resolve(), Path(temporary))


if __name__ == '__main__':
    main()
