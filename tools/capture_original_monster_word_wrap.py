"""Observe full native coordinate writebacks at both signed-word boundaries."""
import hashlib

import capture_original_monster_writeback as writeback

flyers = writeback.flyers
SCHEMA = 'lezac-monster-coordinate-word-wrap-v1'
HOOKS, WINDOWS, WRITEBACK = writeback.HOOKS, writeback.WINDOWS, writeback.WRITEBACK
PROFILES = ((32760, 24), (24, 32760), (32760, 32760),
            (-32760, 24), (24, -32760), (-32760, -32760))
DEPENDENCIES = dict(writeback.DEPENDENCIES) | {
    'capture_original_monster_writeback.py': '3e8e3e6dae7ba8be5ce189e6c2e377f67f0bbc75b34c3bf0e2999b3d02cc1a94',
}


def cases():
    rows = []
    for profile, (x, y) in enumerate(PROFILES):
        for kind in range(1, 9):
            for vx in (-32768, -256, 0, 32767):
                for vy in (-32768, -256, 0, 32767):
                    rows.append({'index': len(rows), 'kind': kind, 'profile': profile,
                                 'x': x, 'y': y, 'mask': 0, 'glyph': 0,
                                 'vx': vx, 'vy': vy, 'frac_x': 165, 'frac_y': 90,
                                 'mode': 0, 'frame': 421, 'ai0': 14, 'ai1': 271, 'ai2': 75})
    return tuple(rows)


CASES = cases()


def configure():
    flyers.HOOKS, flyers.WINDOWS, flyers.CASES = HOOKS, WINDOWS, CASES


def self_check():
    configure()
    for name, digest in DEPENDENCIES.items():
        if flyers.base.sha(flyers.ROOT / 'tools' / name) != digest:
            raise RuntimeError(f'word-wrap observer dependency differs: {name}')
    image = flyers.self_check()
    print('monster_word_wrap_self_check=ok cases=768 kinds=1..8 profiles=6 live=0', flush=True)
    return image


def capture(*args):
    configure()
    report = flyers.capture(*args, retain_writeback=True)
    report.update(schema=SCHEMA, profile_coverage=list(range(6)),
                  complete_coordinate_writeback_observed=True)
    for name in ('capture_original_flyer_contacts.py', 'capture_original_monster_writeback.py'):
        report['support_dependencies_sha256'][name] = hashlib.sha256(
            (flyers.ROOT / 'tools' / name).read_bytes()).hexdigest()
    return report


if __name__ == '__main__':
    configure()
    base = flyers.base
    base.HOOKS, base.WINDOWS, base.CASES = HOOKS, WINDOWS, CASES
    base.self_check, base.trampoline, base.capture = self_check, flyers.trampoline, capture
    base.runtime_windows = flyers.runtime_windows
    base.__file__ = __file__
    raise SystemExit(base.main())
