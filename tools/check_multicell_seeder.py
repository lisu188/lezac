"""Compare actual-App multi-cell insertion with the unmodified original 370E states."""
from check_monster_object_seeder import SeederFixture, main

FIXTURE = SeederFixture(384, 5949, 5972, b'LZMG0001', b'LZMO0001',
    '1a6982b697f781921c34255dd89137bb577fbe74f8170211e18f878cae6560eb',
    'a75c151aa445fe8af4980ce55ac96842abc1430a6085547c35c4227726eb94bb',
    'f62479bc246f175396365df766ff71bab202a1497569d35153b4d8e06b31954e',
    'tests/fixtures/multicell_seeder_original.bin.gz', '--debug-multicell-seeder-original',
    b'multicell_seeder_app=ok cases=384 compared_bytes=2293248 accepted=384 capacity_rejected=0 '
    b'flagged=0 inactive_salted=1 production_app=1 seeded=1 natural_route=0 whole_game_claim=0',
    'multicell_seeder_fixture=ok cases=384 state_bytes=5972 complete_input_planes=1',
    'multicell_seeder_original=ok cases=384 compared_bytes=2293248 production_app=1 masks=0 '
    'complete_input_planes=1 seeded=1 natural_route=0 whole_game_claim=0', 'multicell-seeder')

if __name__ == '__main__':
    raise SystemExit(main(FIXTURE))
