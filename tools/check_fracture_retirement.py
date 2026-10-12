"""Compare complete fracture-retirement banks with the unmodified original."""
from check_monster_object_seeder import SeederFixture, main

FIXTURE = SeederFixture(288, 7670, 7664, b'LZFR0001', b'LZFO0001',
    '6f9ba3655fc473b04aa32c2cd804876d39b2697f79299a7aee25092a5475bf2e',
    'f8d6ab0d8a0d75e23cac33c662a477243fcf76488e254da8085b76d354755cbf',
    '7a89bfbf40eed17b11749341841da5515580f6e5c386fab0783b2066dca01311',
    'tests/fixtures/fracture_retirement_original.bin.gz', '--debug-original-fracture-retirement',
    b'fracture_retirement_app=ok cases=288 compared_bytes=2207232 retained_debris=5 '
    b'retained_collapse=5 actor_bank_bytes=1575 sound_bytes=7 production_app=1 seeded=1 '
    b'natural_route=0 whole_game_claim=0',
    'fracture_retirement_fixture=ok cases=288 state_bytes=7664 complete_physical_banks=1',
    'fracture_retirement_original=ok cases=288 compared_bytes=2207232 production_app=1 masks=0 '
    'complete_physical_banks=1 seeded=1 natural_route=0 whole_game_claim=0', 'fracture-retirement')

if __name__ == '__main__':
    raise SystemExit(main(FIXTURE))
