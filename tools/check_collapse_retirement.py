"""Compare normal-retirement physical storage with the unmodified original."""
from check_monster_object_seeder import SeederFixture, main

FIXTURE = SeederFixture(176, 6033, 6027, b'LZRT0001', b'LZRO0001',
    'b8b9afdc566ceabcb608751474cf7038d3c7c9f8bc3400e6ce64d01e1ba8d5da',
    '34396a2cf00e8b40f1ee1e29924dc5c40c636df7e3017f0365dc33fd474ceed3',
    '76be0e1ca3b563c17a6af6576ee23287c5b1fc05ce075bd846ab1877d029195e',
    'tests/fixtures/collapse_retirement_original.bin.gz', '--debug-original-collapse-retirement',
    b'collapse_retirement_app=ok cases=176 compared_bytes=1060752 retained_records=5 '
    b'production_app=1 seeded=1 natural_route=0 whole_game_claim=0',
    'collapse_retirement_fixture=ok cases=176 state_bytes=6027 retained_records=5',
    'collapse_retirement_original=ok cases=176 compared_bytes=1060752 production_app=1 masks=0 '
    'retained_records=5 seeded=1 natural_route=0 whole_game_claim=0', 'collapse-retirement')

if __name__ == '__main__':
    raise SystemExit(main(FIXTURE))
