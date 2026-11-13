"""Compare direct fragment impacts across all original physical storage."""
from check_monster_object_seeder import SeederFixture, main

FIXTURE = SeederFixture(96, 26727, 26721, b'LZFC0001', b'LZFP0001',
    '395aaa29cac7912735f2bd258638c52fd18eb765d4b2733bda8d593fa63db6e5',
    'cfff186bced8419ebbb8cd5951b91e9503764e6836a44775ab9e9e733732f073',
    '1ddf2a88c9c1fea2b2d794409c82aa0c9f6b6135fe93b07dcab3477ecd3c862a',
    'tests/fixtures/debris_contact_pools_original.bin.gz', '--debug-original-debris-contact-pools',
    b'debris_contact_pools_app=ok cases=96 compared_bytes=2565216 retained_debris=1402 '
    b'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 production_app=1 seeded=1 '
    b'natural_route=0 whole_game_claim=0',
    'debris_contact_pools_fixture=ok cases=96 state_bytes=26721 direct_impacts=1',
    'debris_contact_pools_original=ok cases=96 compared_bytes=2565216 production_app=1 masks=0 '
    'direct_impacts=1 seeded=1 natural_route=0 whole_game_claim=0', 'debris-contact-pools', 768 * 1024)

if __name__ == '__main__':
    raise SystemExit(main(FIXTURE))
