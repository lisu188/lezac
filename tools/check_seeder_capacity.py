"""Check the actual production seeder against original capacity and stale-record states."""
from check_monster_object_seeder import SeederFixture, main

FIXTURE = SeederFixture(448, 7, 5972, b'LZSC0001', b'LZSO0001',
    '4d09cf11c69273c53df39ea8d2649659592022e5d62d4dfb5488f3c4a017b63a',
    '403fa355373eb72a5cffa191692836c6c305024d9c21e9cf87bd301c0cfb547e',
    '8b3a2daab47d116f1ffea0a8f4bc81db13332f335beac706967e743d6a374858',
    'tests/fixtures/seeder_capacity_original.bin.gz', '--debug-seeder-capacity-original',
    b'seeder_capacity_app=ok cases=448 compared_bytes=2675456 accepted=128 capacity_rejected=128 '
    b'flagged=192 inactive_salted=1 production_app=1 seeded=1 natural_route=0 whole_game_claim=0',
    'seeder_capacity_fixture=ok cases=448 state_bytes=5972 inactive_salted=1',
    'seeder_capacity_original=ok cases=448 compared_bytes=2675456 production_app=1 masks=0 '
    'inactive_salted=1 seeded=1 natural_route=0 whole_game_claim=0', 'seeder-capacity')

if __name__ == '__main__':
    raise SystemExit(main(FIXTURE))
