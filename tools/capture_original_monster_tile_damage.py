"""Observe full native monster motion, embedding damage and impact writeback."""
import hashlib

import capture_original_monster_writeback as writeback

flyers = writeback.flyers
SCHEMA = 'lezac-monster-tile-damage-v1'
HOOKS, WRITEBACK = writeback.HOOKS, writeback.WRITEBACK
DAMAGE = bytes.fromhex('c6061e6600b904008b1e7220c706722000008e06fec18b3e7420268a053c75750c893e7220fe0e1e66fe0e1e6639d97e123c01720e3c4c770aa01e662a068c20a21e6683f904750347eb1183f9037506033e04c2eb0683f90275014fe2bcc3')
IMPACT = bytes.fromhex('807ef1017303e9f000807ef1087603e9e700807ef11f7503e9de0031c0a372208b46d6030604c240a37420c6068c2001e865e2803e1e66007503e9bc00837ef4007e06c646ee02eb04c646ee018a46ee30e48bd08a46f130e48bf8d1e703fa8a8577005055e8efe5c47e0481c71600897ec68c46c8c47ec6268a450430e42d0400c47ec626884503a01e66988bd0c47e04268a452430e403c209c07d44c47e0426c6451b00c47e04897ec68c46c8c47ec626c6451502c47ec626c6050cc47ec626c6450219c47ec626807d25007610c47ec6268a452530e46bf81efe85b274eb18a01e66988bd0c47e04268a452430e403c2c47e0426884524c47e04268a451498998bc88bda8b46d231d203c113d38946d2')
WINDOWS = dict(writeback.WINDOWS) | {0x56B6: DAMAGE, 0x741E: IMPACT}
GLYPHS = (0, 1, 0x4C, 0x4D, 0x52, 0x53, 0x75, 0xFF)
CELLS = ((42, 12), (43, 12), (43, 13), (42, 13))


def cases():
    rows = []
    for kind in range(1, 9):
        for glyph in GLYPHS:
            for cell_mask in range(16):
                rows.append({'index': len(rows), 'kind': kind, 'glyph': glyph, 'mask': 0,
                             'cell_mask': cell_mask, 'profile': 0, 'x': 336, 'y': 99,
                             'vx': -513 if cell_mask & 1 else 513, 'vy': 513,
                             'frac_x': 165, 'frac_y': 90, 'mode': 0, 'frame': 421,
                             'ai0': 14, 'ai1': 271, 'ai2': 75, 'hp_byte': 10,
                             'tiles': [[x, y, glyph] for bit, (x, y) in enumerate(CELLS)
                                       if cell_mask & (1 << bit)]})
    for profile in (1, 2, 3):
        for kind in range(1, 9):
            for glyph in (1, 0x75):
                for cell_mask in (1, 15):
                    for direction in (-1, 0, 1):
                        vx = direction * (513 if profile == 3 else 8192)
                        vy = 513 if profile == 3 else 8192
                        shift_x, shift_y = (direction * 4, 4) if profile == 2 else (0, 0)
                        rows.append({'index': len(rows), 'kind': kind, 'glyph': glyph, 'mask': 0,
                                     'cell_mask': cell_mask, 'profile': profile, 'x': 336, 'y': 99,
                                     'vx': vx, 'vy': vy, 'frac_x': 165, 'frac_y': 90,
                                     'mode': 0, 'frame': 421, 'ai0': 14, 'ai1': 271, 'ai2': 75,
                                     'hp_byte': 0 if profile == 3 else 10,
                                     'tiles': [[x + shift_x, y + shift_y, glyph]
                                               for bit, (x, y) in enumerate(CELLS)
                                               if cell_mask & (1 << bit)]})
    return tuple(rows)


CASES = cases()


def configure():
    flyers.HOOKS, flyers.WINDOWS, flyers.CASES = HOOKS, WINDOWS, CASES


def self_check():
    configure()
    image = flyers.self_check()
    print('monster_tile_damage_self_check=ok cases=1312 kinds=1..8 glyphs=8 footprint_masks=16 profiles=4 live=0', flush=True)
    return image


def capture(*args):
    configure()
    report = flyers.capture(*args, retain_writeback=True)
    report.update(schema=SCHEMA, profile_coverage=[0, 1, 2, 3], complete_coordinate_writeback_observed=True,
                  seeded_health_bytes=[0, 10], health_byte_offset=0x24, shared_actor_profiles=True,
                  natural_constructor_claim=False)
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
