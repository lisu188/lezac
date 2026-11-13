"""Observe complete behavior-4 coordinate writeback at both map edges."""
import hashlib

import capture_original_flyer_contacts as flyers

SCHEMA = 'lezac-monster-coordinate-writeback-v1'
WRITEBACK = bytes.fromhex('8a46ed30e48bf8c1e70381c71ec2897ec68c5ec88b46d4c47ec62689058b46d2c47ec626894502c47e04897ec68c46c88a46f030e4c47ec62689450a8a46ef30e4c47ec62689450c8b46f4c47ec6268945068b46f2c47ec626894508807ef1')
HOOKS = (flyers.HOOKS[0], flyers.HOOKS[1], (0x777F, bytes.fromhex('c9c20400')))
WINDOWS = dict(flyers.WINDOWS) | dict(HOOKS) | {0x7530: WRITEBACK}


def cases():
    rows = []
    for profile, (x, y) in enumerate(((448, 240), (24, 24))):
        for kind in range(1, 9):
            for vx in (-32768, -256, 0, 32767):
                for vy in (-32768, -256, 0, 32767):
                    rows.append({'index': len(rows), 'kind': kind, 'profile': profile,
                                 'x': x, 'y': y, 'mask': 0, 'glyph': 0,
                                 'vx': vx, 'vy': vy, 'frac_x': 165, 'frac_y': 90,
                                 'mode': 0, 'frame': 421, 'ai0': 14, 'ai1': 271, 'ai2': 75})
    return tuple(rows)


CASES = cases()
DEPENDENCIES = dict(flyers.DEPENDENCIES)


def configure():
    flyers.HOOKS, flyers.WINDOWS, flyers.CASES = HOOKS, WINDOWS, CASES


def self_check():
    configure()
    image = flyers.self_check()
    print('monster_writeback_self_check=ok cases=256 kinds=1..8 profiles=2 live=0', flush=True)
    return image


def capture(pid, location, output, image, window, load_segment):
    configure()
    report = flyers.capture(pid, location, output, image, window, load_segment, retain_writeback=True)
    report.update(schema=SCHEMA, profile_coverage=[0, 1], complete_coordinate_writeback_observed=True)
    report['support_dependencies_sha256']['capture_original_flyer_contacts.py'] = hashlib.sha256(
        (flyers.ROOT / 'tools/capture_original_flyer_contacts.py').read_bytes()).hexdigest()
    return report


if __name__ == '__main__':
    configure()
    base = flyers.base
    base.HOOKS, base.WINDOWS, base.CASES = HOOKS, WINDOWS, CASES
    base.self_check, base.trampoline, base.capture = self_check, flyers.trampoline, capture
    base.runtime_windows = flyers.runtime_windows
    base.__file__ = __file__
    raise SystemExit(base.main())
