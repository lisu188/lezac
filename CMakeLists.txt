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
    add_test(NAME validate_assets COMMAND $<TARGET_FILE:lezac_cpp> --validate)
    set_tests_properties(validate_assets PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME level_raw_roundtrip
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-level-raw-roundtrip)
    set_tests_properties(level_raw_roundtrip PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

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
            "player_damage_sound=ok nonlethal_energy=99 nonlethal_cooldown=18 death_energy=100 dead=1 lives=2 cursor=0x2d priority=4 death_cursor=0x56 death_priority=5")

    add_test(NAME original_damage_counters
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-original-damage-counters)
    set_tests_properties(original_damage_counters PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "original_damage_counters=ok p1_hits=3 p1_energy=97 p1_hurt_requests=1 p2_hits=2 p2_energy=98 p2_hurt_requests=1 zero_pass_silent=1 state2_hurt_without_subtract=1 underflow_raw=255 death_dispatch=1")

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
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

    add_test(NAME monster_slots COMMAND $<TARGET_FILE:lezac_cpp> --debug-monster-slots)
    set_tests_properties(monster_slots PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

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

    add_test(NAME passable_objects
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-passable-objects)
    set_tests_properties(passable_objects PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

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
        TIMEOUT 5)

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
