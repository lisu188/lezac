"""Compare complete above-cell contact and seeding states with the original."""
from check_monster_object_seeder import SeederFixture, main

FIXTURE = SeederFixture(96, 26727, 26721, b'LZFC0001', b'LZFP0001',
    '28e74fee6ec8cd293883db68186151d48dc0c83c2e4bf1fed05292b170b99b35',
    '523ac03716ed37a80f74fdb010cf41bff20ba06e2939f1447ed14602e72f3f3c',
    'fd41f3c8446c9d13c32a0f920f00b38dee0a31721e68e43632144dd1be7a2074',
    'tests/fixtures/above_contact_staging_original.bin.gz', '--debug-original-fracture-retirement',
    b'fracture_capacity_app=ok cases=96 compared_bytes=2565216 retained_debris=1402 '
    b'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 production_app=1 seeded=1 '
    b'natural_route=0 whole_game_claim=0',
    'above_contact_staging_fixture=ok cases=96 state_bytes=26721 guard_bytes=11 seed_above=1',
    'above_contact_staging_original=ok cases=96 compared_bytes=2565216 production_app=1 masks=0 '
    'guard_bytes=11 seed_above=1 seeded=1 natural_route=0 whole_game_claim=0', 'above-contact-staging')

if __name__ == '__main__':
    raise SystemExit(main(FIXTURE))
