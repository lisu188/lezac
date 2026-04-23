cmake_minimum_required(VERSION 3.16)

project(lezac_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(PkgConfig REQUIRED)
pkg_check_modules(SDL2 REQUIRED sdl2)

add_executable(lezac_cpp src/main.cpp)
target_include_directories(lezac_cpp PRIVATE ${SDL2_INCLUDE_DIRS})
target_link_libraries(lezac_cpp PRIVATE ${SDL2_LIBRARIES})
target_compile_options(lezac_cpp PRIVATE ${SDL2_CFLAGS_OTHER})

set(LEZAC_JSON_RESOURCES
    src/BOMPAL.PAL.json
    src/SFONLEF.ZBG.json
    src/CARO.CAR.json
    src/BOMOMIMK.SPR.json
    src/PROVA.SPR.json
    src/FONTS.SPR.json
    src/RECS.DAT.json
    src/PROEFS.SON.json
    src/GRAN.MST.json
    src/LIVELS.SCH.json
)

foreach(resource IN LISTS LEZAC_JSON_RESOURCES)
    get_filename_component(resource_name ${resource} NAME)
    add_custom_command(
        TARGET lezac_cpp POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                ${CMAKE_CURRENT_SOURCE_DIR}/${resource}
                $<TARGET_FILE_DIR:lezac_cpp>/${resource_name}
        VERBATIM
    )
endforeach()

include(CTest)

if(BUILD_TESTING)
    find_package(Python3 COMPONENTS Interpreter QUIET)

    add_test(NAME validate_assets COMMAND $<TARGET_FILE:lezac_cpp> --validate)
    set_tests_properties(validate_assets PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME level_raw_roundtrip
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-level-raw-roundtrip)
    set_tests_properties(level_raw_roundtrip PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME fixed_point_integration
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-fixed)
    set_tests_properties(fixed_point_integration PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "vel=64 ticks=4 pos=1 frac=0[ \n\r\t]+vel=-64 ticks=1 pos=-1 frac=192[ \n\r\t]+vel=-64 ticks=4 pos=-1 frac=0[ \n\r\t]+vel=256 ticks=4 pos=4 frac=0[ \n\r\t]+vel=-256 ticks=4 pos=-4 frac=0")

    add_test(NAME ui_smoke_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --smoke-ui 3)
    set_tests_properties(ui_smoke_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME ui_controls_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --smoke-controls)
    set_tests_properties(ui_controls_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME level1_frame_inspection_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-level1-frame-inspection)
    set_tests_properties(level1_frame_inspection_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "level1_frame_inspection=ok level=1 size=60x33 p1_xy=104,168 p1_bomb_tile=13,22 initial_small=200 after_n_small=199 bombs=1 menu_uniform=0 gameplay_uniform=0 menu_game_different=1 hud_nonempty=1 world_nonempty=1 player_visible=1 bomb_visible=1 explosion_visible=1 completion_visible=1 advanced_level=2")

    add_test(NAME frame_sequence_capture_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --capture-frame-sequence level1_bomb_route
                ${CMAKE_CURRENT_BINARY_DIR}/frame_sequence_capture)
    set_tests_properties(frame_sequence_capture_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^frame_sequence=ok scenario=level1_bomb_route frames=7 size=320x200")

    add_test(NAME autoplayer_level1_bomb_route_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer level1_bomb_route)
    set_tests_properties(autoplayer_level1_bomb_route_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=level1_bomb_route route_frames=[0-9]+ .*p1_bomb_tile=24,22 bombs=1 explosion=1 frame_inspection=1")

    add_test(NAME autoplayer_death_reentry_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer death_reentry)
    set_tests_properties(autoplayer_death_reentry_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=death_reentry death_state_ticks=60 lives=2 energy=100 reentered=1 frame_inspection=1")

    add_test(NAME autoplayer_death_visuals_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer death_visuals)
    set_tests_properties(autoplayer_death_visuals_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=death_visuals death_state_ticks=60 start_frame=0x4a tick1_frame=0x4b tick5_frame=0x4c frame_inspection=1 visual_claim=0")

    add_test(NAME autoplayer_level_transition_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer level_transition)
    set_tests_properties(autoplayer_level_transition_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=level_transition start_level=1 completed_bonus=[0-9]+ completed_destruction=[0-9]+ transition_frames=101 advanced_level=2 frame_inspection=1")

    add_test(NAME autoplayer_records_flow_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer records_flow)
    set_tests_properties(autoplayer_records_flow_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=records_flow record_score=999999 record_level=3 name=bot frame_inspection=1")

    add_test(NAME autoplayer_two_player_route_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer two_player_route)
    set_tests_properties(autoplayer_two_player_route_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=two_player_route .*p2_bomb_tile=[0-9]+,[0-9]+ bombs=1 frame_inspection=1")

    add_test(NAME autoplayer_two_player_progression_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer two_player_progression)
    set_tests_properties(autoplayer_two_player_progression_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=two_player_progression p1_moved=1 p2_death_timer=60 p2_reentered=1 p2_bomb_tile=[0-9]+,[0-9]+ p2_score=1000 collected=1 frame_inspection=1")

    if(Python3_Interpreter_FOUND)
        add_test(NAME frame_compare_identical
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/frame_compare.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/frame_compare/a.pnm
                    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/frame_compare/b.pnm)
        set_tests_properties(frame_compare_identical PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^frame_compare=ok size=2x2 normalized=none pixels=4 exact_match=1 exact_different_pixels=0 threshold=0 threshold_different_pixels=0 max_delta=0")
    endif()

    add_test(NAME records_update_temp
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-record-update
                ${CMAKE_CURRENT_BINARY_DIR}/records_test.dat)
    set_tests_properties(records_update_temp PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME records_name_entry_temp
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-record-name-entry
                ${CMAKE_CURRENT_BINARY_DIR}/records_name_test.dat)
    set_tests_properties(records_name_entry_temp PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME records_save_failure_temp
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-record-save-failure
                ${CMAKE_CURRENT_BINARY_DIR}/missing_records_dir/records_test.dat)
    set_tests_properties(records_save_failure_temp PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME end_flow_records_temp
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-end-flow-records
                ${CMAKE_CURRENT_BINARY_DIR}/end_flow_records_test.dat)
    set_tests_properties(end_flow_records_temp PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^end_flow_records=ok completion_level=2 p1_record=999997 p2_record=999998 records=7")

    add_test(NAME sound_render COMMAND $<TARGET_FILE:lezac_cpp> --debug-sound-render)
    set_tests_properties(sound_render PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME sound_cursor_segments
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-sound-cursor-segments)
    set_tests_properties(sound_cursor_segments PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION "sound_cursor_segments=ok")

    add_test(NAME son_raw_roundtrip
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-son-raw-roundtrip)
    set_tests_properties(son_raw_roundtrip PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^son_raw_roundtrip=ok raw_size=782 step_count=130 payload_size=780 json_chunks=6")

    add_test(NAME son_step_fields
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-son-step-fields)
    set_tests_properties(son_step_fields PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "son_step_fields=ok steps=130 first_period=0x00f7 first_stop_cursor=0x0005 final_stop_cursor=0x0082 unknown_pair_nonzero_steps=118")

    add_test(NAME gran_raw_roundtrip
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-gran-raw-roundtrip)
    set_tests_properties(gran_raw_roundtrip PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^gran_raw_roundtrip=ok raw_size=399 record_size=57 records=7 payload_size=399 json_records=7")

    add_test(NAME sound_priority_latch
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-sound-priority-latch)
    set_tests_properties(sound_priority_latch PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION "sound_latch=ok")

    add_test(NAME sound_selector_map
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-sound-selector-map)
    set_tests_properties(sound_selector_map PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION "sound_selector_map=ok")

    add_test(NAME bomb_object_sound
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-bomb-object-sound)
    set_tests_properties(bomb_object_sound PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION "bomb_object_sound=ok")

    add_test(NAME player_damage_sound
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-player-damage-sound)
    set_tests_properties(player_damage_sound PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "player_damage_sound=ok nonlethal_energy=99 second_energy=98 nonlethal_cooldown=0 death_energy=100 dead=1 lives=2 cursor=0x2d priority=4 death_cursor=0x56 death_priority=5")

    add_test(NAME original_damage_counters
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-original-damage-counters)
    set_tests_properties(original_damage_counters PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "original_damage_counters=ok p1_hits=3 p1_energy=97 p1_hurt_requests=1 p2_hits=2 p2_energy=98 p2_hurt_requests=1 zero_pass_silent=1 state2_hurt_without_subtract=1 underflow_raw=255 death_dispatch=1 live_p1_energy=97 live_p2_energy=98 live_underflow_dead=1 live_state2_energy=100")

    add_test(NAME player_state2_death_fields
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-player-state2-death-fields)
    set_tests_properties(player_state2_death_fields PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "player_state2_death_fields=ok reentry_dead=1 reentry_lives=2 reentry_energy=100 reentry_timer=180 death_state_timer=60 vx=0 vy=0 grounded=0 death_cursor=0x56 death_priority=5 early_reentry_blocked=1 after_59_blocked=1 reentered=1 cooldown=18 zero_lives=0 zero_timer=0 zero_death_state_after_tick=59 no_gameover_with_p1=1")

    add_test(NAME original_state2_return_model
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-original-state2-return-model)
    set_tests_properties(original_state2_return_model PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "original_state2_return_model=ok timer_start=60 timer_after_59=1 timer_after_60=0 gate0_blocked=1 effect_wait_blocked=1 placement_blocked=1 gate1_restored=1 p1_status=1 p1_actor_state=0 p1_energy=100 p1_cleared=1 p2_status=1 p2_actor_state=1 p2_energy=100 p2_cleared=1 zero_life_status=0 active_players_after_p2_out=1 active_players_after_both_out=0")

    add_test(NAME state2_animation_init_model
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-original-state2-animation-init)
    set_tests_properties(state2_animation_init_model PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "original_state2_animation_init=ok actor_offset=0x16 bytes=12,12,8,6,6,4,1 duplicate_0a=1 duplicate_06=1 terminator=1 ghidra=1000:06ab")

    add_test(NAME state2_animation_advance_model
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-original-state2-animation-advance)
    set_tests_properties(state2_animation_advance_model PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "original_state2_animation_advance=ok death_start=0x72 death_end=0x79 delay=3 mode1_first_frame=0x73 mode1_after_5=0x74 wrap_frame=0x72 wrap_counter=0 mode2_seq=4,3,2,3 mode2_final_step=1 mode3_backup_frame=5 mode3_backup_mode=3 mode0_unchanged=1 ghidra=1000:6053")

    add_test(NAME state2_runtime_frame_oracle_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-state2-runtime-frame-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/state2_runtime_frame_oracle_synthetic.txt)
    set_tests_properties(state2_runtime_frame_oracle_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "state2_runtime_frame_oracle=ok fixture=state2_runtime_frame_oracle_synthetic runtime_cs=0x1a2b runtime_ds=0x2b3c death_cursor=0x56 death_start=0x72 death_end=0x79 table_entry_base=0xc322 first_entry_addr=0xc4ea frame_rows=8 first_row=10,18,20,00 last_row=17,18,20,00 rows=72@c4ea:10,18,20,00;73@c4ee:11,18,20,00;74@c4f2:12,18,20,00;75@c4f6:13,18,20,00;76@c4fa:14,18,20,00;77@c4fe:15,18,20,00;78@c502:16,18,20,00;79@c506:17,18,20,00 effect0_xy=0x0018,0x0028 breaks=4 temp_copy=1 visual_claim=0")

    add_test(NAME state2_runtime_frame_oracle_original
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-state2-runtime-frame-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/state2_runtime_frame_oracle_original.txt)
    set_tests_properties(state2_runtime_frame_oracle_original PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "state2_runtime_frame_oracle=ok fixture=state2_runtime_frame_oracle_original runtime_cs=0x01ed runtime_ds=0x0c8f death_cursor=0x45 death_start=0x4a death_end=0x4f table_entry_base=0xc322 first_entry_addr=0xc44a frame_rows=6 first_row=10,10,7d,43 last_row=10,10,7d,48 rows=4a@c44a:10,10,7d,43;4b@c44e:10,10,7d,44;4c@c452:10,10,7d,45;4d@c456:10,10,7d,46;4e@c45a:10,10,7d,47;4f@c45e:10,10,7d,48 effect0_xy=0x0068,0x00a8 breaks=5 temp_copy=1 visual_claim=0")

    add_test(NAME state2_runtime_frame_oracle_bad_segment
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-state2-runtime-frame-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/state2_runtime_frame_oracle_bad_segment.txt
                --expect-error)
    set_tests_properties(state2_runtime_frame_oracle_bad_segment PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "state2_runtime_frame_oracle=error fixture=state2_runtime_frame_oracle_bad_segment reason=dump_segment_mismatch expected=0x2b3c actual=0xffff address=0060")

    add_test(NAME state2_runtime_frame_oracle_bad_breakpoint
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-state2-runtime-frame-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/state2_runtime_frame_oracle_bad_breakpoint.txt
                --expect-error)
    set_tests_properties(state2_runtime_frame_oracle_bad_breakpoint PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "state2_runtime_frame_oracle=error fixture=state2_runtime_frame_oracle_bad_breakpoint reason=breakpoint_offset_mismatch expected=3108 actual=3109")

    add_test(NAME state2_runtime_frame_oracle_missing_global_byte
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-state2-runtime-frame-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/state2_runtime_frame_oracle_missing_global_byte.txt
                --expect-error)
    set_tests_properties(state2_runtime_frame_oracle_missing_global_byte PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "state2_runtime_frame_oracle=error fixture=state2_runtime_frame_oracle_missing_global_byte reason=missing_byte address=006a")

    add_test(NAME state2_runtime_frame_oracle_missing_table_row
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-state2-runtime-frame-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/state2_runtime_frame_oracle_missing_table_row.txt
                --expect-error)
    set_tests_properties(state2_runtime_frame_oracle_missing_table_row PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "state2_runtime_frame_oracle=error fixture=state2_runtime_frame_oracle_missing_table_row reason=missing_byte address=c506")

    add_test(NAME explosion_playback_oracle_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_synthetic.txt)
    set_tests_properties(explosion_playback_oracle_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_synthetic runtime_cs=0x1a2b runtime_ds=0x2b3c dispatcher_break=1 damage_break=1 playback_breaks=4 debris_base=0x2093 debris_stride=11 .* collapse_base=0x6611 collapse_stride=15 .* temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_bad_segment
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_bad_segment.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_bad_segment PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_bad_segment reason=dump_segment_mismatch expected=0x2b3c actual=0xffff address=2090")

    add_test(NAME state2_effect_placement_model
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-original-state2-effect-placement)
    set_tests_properties(state2_effect_placement_model PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "original_state2_effect_placement=ok base=0xc21e slot0=0xc21e slot1=0xc226 slot2=0xc22e x_tile=3 y_tile=6 map_offset=363 open_descended=1 y_after=39 floor_stops=1 solid_blocked=1 marker_blocked=1 right_solid_blocked=1 gate_after_descent=1")

    add_test(NAME player_state2_return_active
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-player-state2-return-active)
    set_tests_properties(player_state2_return_active PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "player_state2_return_active=ok p1_death_timer=60 p1_after_59=1 p1_after_60=0 gate0_dead=1 gate0_energy=100 gate1_reentered=1 p1_energy=100 p1_cooldown=18 p1_death_timer_clear=0 p1_reentry_timer_clear=0 p2_gate1_reentered=1 p2_energy=100 p2_cooldown=18 p2_death_timer_clear=0 p2_reentry_timer_clear=0 no_gameover_with_p1=1")

    add_test(NAME sprite_transparency
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-sprite-transparency)
    set_tests_properties(sprite_transparency PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^sprite_transparency=ok zero_only=1 ff_pixels=369 primary=104 prova=114 fonts=151")

    add_test(NAME sprite_raw_roundtrip
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-sprite-raw-roundtrip)
    set_tests_properties(sprite_raw_roundtrip PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^sprite_raw_roundtrip=ok banks=3 raw_bytes=46843 sprites=250 pixels=46340 zero=21396 nonzero=24944 ff=369 max=48x20 bomomimk=91 prova=91 fonts=68")

    add_test(NAME sprite_blit_contract
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-sprite-blit-contract)
    set_tests_properties(sprite_blit_contract PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^sprite_blit_contract=ok width=4 height=2 drawn=6 skipped_zero=2 ff_visible=2 bg_preserved=2 outside_preserved=2")

    add_test(NAME monster_slots COMMAND $<TARGET_FILE:lezac_cpp> --debug-monster-slots)
    set_tests_properties(monster_slots PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "monster_slots=ok initial_slots=2 returned_immediate=1 death_ticks=25")

    add_test(NAME monster_motion_model
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-monster-motion-model)
    set_tests_properties(monster_motion_model PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "monster_motion_model=ok carry_pos=11 carry_frac=4 neg_pos=9 neg_frac=254 b3_init_vx=256 b3_init_frame=45-46 b3_ledge_vx=-256 b3_ledge_vy=64 b3_ledge_frame=43-44 b4_chase_vx=512 b4_chase_vy=0 b4_timer=6 b4_frame=39-41")

    add_test(NAME spawners_summary
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-spawners)
    set_tests_properties(spawners_summary PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "spawner_total=15[ \n\r\t]+monster_kind_counts=1:7,2:2,3:3,4:3[ \n\r\t]+behavior_counts=3:9,4:6")

    add_test(NAME bonus_rewards COMMAND $<TARGET_FILE:lezac_cpp> --debug-bonuses)
    set_tests_properties(bonus_rewards PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME monster_blast_damage
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-monster-blast-damage)
    set_tests_properties(monster_blast_damage PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME bomb_fuse COMMAND $<TARGET_FILE:lezac_cpp> --debug-bomb-fuse)
    set_tests_properties(bomb_fuse PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME explosion_profiles
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosions)
    set_tests_properties(explosion_profiles PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_profiles=ok types=4 states=4,5,6,7 sound_offsets=0xea74,0xea7e,0xea88,0xeace")

    add_test(NAME damage_queues
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-damage-queues)
    set_tests_properties(damage_queues PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "damage_queues=ok debris_stride=11 collapse_stride=15 damaged_bit=0x8000 deferred_threshold=0x4000 collapse_flagged=0x8006 debris_flagged=0xc000 collapse_count=7 collapse_forward=2 collapse_reverse=3 debris_lookup=107 debris_forward=4 debris_reverse=5")

    add_test(NAME bomb_object_explosion_effects
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-bomb-object-explosion-effects)
    set_tests_properties(bomb_object_explosion_effects PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "bomb_object_explosion_effects=ok cases=2 .*score_each=50 sound_offset=0xea74")

    add_test(NAME passable_objects
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-passable-objects)
    set_tests_properties(passable_objects PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^passable_objects=ok bomb=1 portal=1 solid=1 footprint_clear=1 consumed_clear=1 level1_word_clear=1 high_word_solid=1 level1_route_clear=1")

    add_test(NAME trigger_accounting
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-trigger-accounting)
    set_tests_properties(trigger_accounting PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME trigger_sound
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-trigger-sound)
    set_tests_properties(trigger_sound PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION "trigger_sound=ok")

    add_test(NAME portal_sound
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-portal-sound)
    set_tests_properties(portal_sound PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION "portal_sound=ok")

    add_test(NAME portal_cooldowns
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-portal-cooldowns)
    set_tests_properties(portal_cooldowns PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME collision_pushout
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-collision-pushout)
    set_tests_properties(collision_pushout PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        TIMEOUT 5
        PASS_REGULAR_EXPRESSION
            "^collision_pushout=ok player_h_clear=1 player_v_clear=1 monster_h_clear=1 monster_v_clear=1 monster_b4_half=1 passable_clear=1 solid_tile=2")

    find_program(BASH_EXECUTABLE bash)
    find_program(XVFB_RUN_EXECUTABLE xvfb-run)
    find_program(XDOTOOL_EXECUTABLE xdotool)
    if(BASH_EXECUTABLE AND XVFB_RUN_EXECUTABLE AND XDOTOOL_EXECUTABLE)
        add_test(NAME ui_xdotool_xvfb
            COMMAND ${CMAKE_COMMAND} -E env SDL_AUDIODRIVER=dummy
                    ${XVFB_RUN_EXECUTABLE} -a
                    ${BASH_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/test_ui_xdotool.sh
                    $<TARGET_FILE:lezac_cpp>)
        set_tests_properties(ui_xdotool_xvfb PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
    endif()
endif()
