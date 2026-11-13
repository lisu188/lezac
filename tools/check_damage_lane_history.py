"""Compare prior-phase fragment updates, including retained low-data writes."""
from check_monster_object_seeder import SeederFixture, main

FIXTURE = SeederFixture(112, 26730, 26724, b'LZDH0001', b'LZDO0001',
    '38751aa9e1f2d7b2874483901d133743b5997c36bffeeeb285c965fdede6a4fa',
    '9d7e6cfc103ef8d09f25d94a76b8a3df9333995500cde80a23f2847a0e4ba2e4',
    '46d706465cae439edab657dd4671f79da23d3ea89c6f3ecdd807fc686da07aef',
    'tests/fixtures/damage_lane_history_original.bin.gz', '--debug-original-damage-lane-history',
    b'damage_lane_history_app=ok cases=112 compared_bytes=2993088 retained_debris=1402 '
    b'retained_collapse=251 actor_bank_bytes=1575 sound_bytes=7 history_bytes=3 production_app=1 '
    b'seeded=1 natural_route=0 whole_game_claim=0',
    'damage_lane_history_fixture=ok cases=112 state_bytes=26724 prior_phase=1 low_data=2',
    'damage_lane_history_original=ok cases=112 compared_bytes=2993088 production_app=1 masks=0 '
    'prior_phase=1 low_data=2 seeded=1 natural_route=0 whole_game_claim=0', 'damage-lane-history', 768 * 1024)

if __name__ == '__main__':
    raise SystemExit(main(FIXTURE))
