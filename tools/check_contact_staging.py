"""Compare every physical guard byte across original multi-contact updates."""
from check_monster_object_seeder import SeederFixture, main

FIXTURE = SeederFixture(96, 26727, 26721, b'LZFC0001', b'LZFP0001',
    '8f9d4a27fe3587a8b9dfc377135715eeacdd28e5ae7f9bdc6cbb3b8a95e72be7',
    '98dd3e762def923b6bd4b85043f284eb1e0baeb25500a36d8e607b9a14139592',
    'cd42a242dd437c02719633e4b4661559e2da2fb139c27ad74fa8806973afc74a',
    'tests/fixtures/contact_staging_original.bin.gz', '--debug-original-fracture-retirement',
    b'fracture_capacity_app=ok cases=96 compared_bytes=2565216 retained_debris=1402 '
    b'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 production_app=1 seeded=1 '
    b'natural_route=0 whole_game_claim=0',
    'contact_staging_fixture=ok cases=96 state_bytes=26721 guard_bytes=11',
    'contact_staging_original=ok cases=96 compared_bytes=2565216 production_app=1 masks=0 '
    'guard_bytes=11 seeded=1 natural_route=0 whole_game_claim=0', 'contact-staging')

if __name__ == '__main__':
    raise SystemExit(main(FIXTURE))
