"""Compare complete original moving-contact pools with the production App."""
from check_monster_object_seeder import SeederFixture, main

FIXTURE = SeederFixture(96, 26727, 26721, b'LZFC0001', b'LZFP0001',
    '9075ffca72bcdaa17392fee1f2626ae40368c6f3c59a20f0f35fee47eb6ad507',
    '1955f2e3eec9bcc5fe2e943105fcc9cdaca103ba115e3bb4c8f09719b0444ea3',
    'aa7eff66ab2542f12532951eb1e1e160815e101687ecc618ae9013682a558e0a',
    'tests/fixtures/collapse_contact_pools_original.bin.gz', '--debug-original-fracture-retirement',
    b'fracture_capacity_app=ok cases=96 compared_bytes=2565216 retained_debris=1402 '
    b'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 production_app=1 seeded=1 '
    b'natural_route=0 whole_game_claim=0',
    'collapse_contact_pools_fixture=ok cases=96 state_bytes=26721 capacity_guards=1',
    'collapse_contact_pools_original=ok cases=96 compared_bytes=2565216 production_app=1 masks=0 '
    'capacity_guards=1 seeded=1 natural_route=0 whole_game_claim=0', 'collapse-contact-pools', 512 * 1024)

if __name__ == '__main__':
    raise SystemExit(main(FIXTURE))
