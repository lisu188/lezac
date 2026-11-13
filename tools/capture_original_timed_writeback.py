"""Observe seeded behavior-2 motion, timers and complete native writeback."""
import hashlib
import struct

import capture_original_monster_writeback as writeback
import capture_original_timed_gravity as timed

flyers = writeback.flyers
SCHEMA = 'lezac-timed-actor-writeback-v1'
HOOKS = (flyers.HOOKS[0], timed.HOOKS[1], writeback.HOOKS[2])
FRICTION = bytes.fromhex('5589e531c09adf0420098b7e04368b45f49931d029d03d2b007d0b8b7e0431c0368945f4eb1c8b7e0436837df4007d0a8b7e04368345f42aeb088b7e0436836df42ac9c20200')
WINDOWS = dict(writeback.WINDOWS) | dict(HOOKS) | {
    0x701C: timed.RAW + bytes.fromhex('807edf00740455e82eebe9'), 0x5B86: FRICTION}
PROFILES = ((32760, 24), (24, 32760), (32760, 32760), (-32760, 24),
            (24, -32760), (-32760, -32760), (24, 32765), (32765, 32765))


def cases():
    rows = []
    def add(kind, mask, glyph, vx, vy, profile=0, x=336, y=99):
        cells = {1: ((41, 12), (41, 13)), 2: ((44, 12), (44, 13)),
                 4: ((42, 11), (43, 11)), 8: ((42, 14), (43, 14))} if kind == 12 else {
                 1: ((41, 13),), 2: ((43, 13),), 4: ((42, 12),), 8: ((42, 14),)}
        rows.append({'index': len(rows), 'kind': kind, 'mask': 0, 'edge_mask': mask, 'glyph': glyph,
                     'vx': vx, 'vy': vy, 'x': x, 'y': y, 'profile': profile,
                     'frac_x': 165, 'frac_y': 90, 'mode': 0, 'frame': 420 + (mask & 1),
                     'ai0': 14, 'ai1': 271, 'ai2': 75, 'hp_byte': 255,
                     'tiles': [[cx, cy, glyph] for bit, positions in cells.items() if mask & bit for cx, cy in positions]})
    for kind in (12, 13):
        for glyph in (0, 1, 0x4C, 0x4D, 0x52, 0x53, 0x75, 0xFF):
            for mask in range(16):
                add(kind, mask, glyph, -513 if mask & 1 else 513, -513 if mask & 4 else 513)
    for kind in (12, 13):
        for mask in (1, 2, 8, 9, 10, 15):
            for vx in (-32768, -32767, -513, -1, 0, 1, 513, 32767):
                for vy in (-32768, -64, 0, 1, 32704):
                    add(kind, mask, 1, vx, vy, 1)
    for profile, (x, y) in enumerate(PROFILES, 2):
        for kind in (12, 13):
            for vx in (-32768, -256, 0, 32767):
                for vy in (-32768, -256, 0, 512, 1983, 32704, 32767):
                    add(kind, 0, 0, vx, vy, profile, x, y)
    if len(rows) != 1184:
        raise RuntimeError('timed actor case coverage changed')
    return tuple(rows)


CASES = cases()


def seed_actor(case):
    actor = bytearray(38)
    actor[0], actor[1], actor[2], actor[4], actor[20], actor[21], actor[36] = case['kind'], 2, 11, 3, 6, 2, 255
    struct.pack_into('<hhHHHHH', actor, 6, case['vx'], case['vy'], 165, 90, 14, 271, 75)
    sprite = 48 if case['kind'] == 12 else 58
    actor[22:29] = bytes((sprite, sprite, sprite, 255, 3, 0, 1))
    return bytes(actor)


def runtime_windows(load_segment):
    return _runtime_with_friction(flyers.runtime_windows, load_segment)


def configure():
    flyers.HOOKS, flyers.WINDOWS, flyers.CASES = HOOKS, WINDOWS, CASES
    flyers.RELOCATIONS, flyers.BEHAVIOR = {0x7134, 0x7146, 0x5B8E}, 2


def self_check():
    configure()
    image = flyers.self_check()
    print('timed_writeback_self_check=ok cases=1184 kinds=12,13 profiles=10 live=0', flush=True)
    return image


def capture(*args):
    configure()
    # The common capture checks loaded far calls before installing any hooks.
    original = flyers.runtime_windows
    flyers.runtime_windows = lambda segment: _runtime_with_friction(original, segment)
    try:
        report = flyers.capture(*args, retain_writeback=True, actor_seed=seed_actor)
    finally:
        flyers.runtime_windows = original
    report.update(schema=SCHEMA, profile_coverage=list(range(10)), complete_coordinate_writeback_observed=True,
                  hotspot_seed=6, timer_seed=11, animation_disabled=True, shared_actor_profiles=True,
                  natural_constructor_claim=False)
    report['support_dependencies_sha256']['capture_original_flyer_contacts.py'] = hashlib.sha256(
        (flyers.ROOT / 'tools/capture_original_flyer_contacts.py').read_bytes()).hexdigest()
    return report


def _runtime_with_friction(original, segment):
    windows = original(segment)
    raw = bytearray(windows[0x5B86])
    struct.pack_into('<H', raw, 8, (struct.unpack_from('<H', raw, 8)[0] + segment) & 0xFFFF)
    windows[0x5B86] = bytes(raw)
    return windows


if __name__ == '__main__':
    configure()
    base = flyers.base
    base.HOOKS, base.WINDOWS, base.CASES = HOOKS, WINDOWS, CASES
    base.self_check, base.trampoline, base.capture = self_check, flyers.trampoline, capture
    base.runtime_windows = runtime_windows
    base.__file__ = __file__
    raise SystemExit(base.main())
