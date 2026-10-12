"""Compare complete fracture-capacity physical pools with the original."""
from check_monster_object_seeder import SeederFixture, main

FIXTURE = SeederFixture(96, 26727, 26721, b'LZFC0001', b'LZFP0001',
    'dffe65605c50580f9fa65f5b68c720cbaa679517062eabbde4aadbe779da6e6f',
    'd5bb3d34f03c023930f498d974f2359f28cdf01690f294bb1c475a244a886fd7',
    'f4cadfe2cbc4802ad4daf3eac66d79ca22b292d3d0961504f3dd0c76139e20b0',
    'tests/fixtures/fracture_capacity_original.bin.gz', '--debug-original-fracture-retirement',
    b'fracture_capacity_app=ok cases=96 compared_bytes=2565216 retained_debris=1402 '
    b'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 production_app=1 seeded=1 '
    b'natural_route=0 whole_game_claim=0',
    'fracture_capacity_fixture=ok cases=96 state_bytes=26721 capacity_guards=1',
    'fracture_capacity_original=ok cases=96 compared_bytes=2565216 production_app=1 masks=0 '
    'capacity_guards=1 seeded=1 natural_route=0 whole_game_claim=0', 'fracture-capacity', 256 * 1024)

if __name__ == '__main__':
    raise SystemExit(main(FIXTURE))
