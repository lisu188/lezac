cmake_minimum_required(VERSION 3.16)

project(lezac_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(PkgConfig REQUIRED)
pkg_check_modules(SDL2 REQUIRED sdl2)

add_executable(lezac_cpp src/main.cpp)
target_compile_definitions(lezac_cpp PRIVATE SDL_MAIN_HANDLED)
target_include_directories(lezac_cpp PRIVATE ${SDL2_INCLUDE_DIRS})
target_link_directories(lezac_cpp PRIVATE ${SDL2_LIBRARY_DIRS})
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

    add_test(NAME frame_sequence_capture_monster_bomb_reward_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --capture-frame-sequence monster_bomb_reward
                ${CMAKE_CURRENT_BINARY_DIR}/frame_sequence_capture_monster_bomb_reward)
    set_tests_properties(frame_sequence_capture_monster_bomb_reward_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^frame_sequence=ok scenario=monster_bomb_reward frames=5 size=320x200")

    add_test(NAME frame_sequence_capture_monster_spawner_behavior4_level2_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --capture-frame-sequence
                monster_spawner_behavior4_level2
                ${CMAKE_CURRENT_BINARY_DIR}/frame_sequence_capture_monster_spawner_behavior4_level2)
    set_tests_properties(frame_sequence_capture_monster_spawner_behavior4_level2_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^frame_sequence=ok scenario=monster_spawner_behavior4_level2 frames=4 size=320x200")

    add_test(NAME frame_sequence_capture_monster_spawner_behavior4_level3_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --capture-frame-sequence
                monster_spawner_behavior4_level3
                ${CMAKE_CURRENT_BINARY_DIR}/frame_sequence_capture_monster_spawner_behavior4_level3)
    set_tests_properties(frame_sequence_capture_monster_spawner_behavior4_level3_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^frame_sequence=ok scenario=monster_spawner_behavior4_level3 frames=4 size=320x200")

    add_test(NAME frame_sequence_capture_monster_behavior4_target_selection_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --capture-frame-sequence
                monster_behavior4_target_selection
                ${CMAKE_CURRENT_BINARY_DIR}/frame_sequence_capture_monster_behavior4_target_selection)
    set_tests_properties(frame_sequence_capture_monster_behavior4_target_selection_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^frame_sequence=ok scenario=monster_behavior4_target_selection frames=6 size=320x200")

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

    add_test(NAME autoplayer_portal_weapon_route_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer portal_weapon_route)
    set_tests_properties(autoplayer_portal_weapon_route_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=portal_weapon_route level=[0-9]+ switched_weapon=2 medium_bomb=1 portal_key=[0-9]+ portal_from=[0-9]+,[0-9]+ portal_to=[0-9]+,[0-9]+ cooldown=30 frame_inspection=1")

    add_test(NAME autoplayer_records_flow_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer records_flow)
    set_tests_properties(autoplayer_records_flow_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=records_flow record_score=999999 record_level=3 name=bot frame_inspection=1")

    add_test(NAME autoplayer_monster_bomb_reward_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer monster_bomb_reward)
    set_tests_properties(autoplayer_monster_bomb_reward_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=monster_bomb_reward monster_dead=1 reward_collected=1 score_delta=[0-9]+ frame_inspection=1")

    add_test(NAME autoplayer_monster_behavior3_multihit_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer monster_behavior3_multihit)
    set_tests_properties(autoplayer_monster_behavior3_multihit_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=monster_behavior3_multihit moved_px=[0-9]+ first_hit_hp=2 second_hit_kill=1 reward_collected=1 score_delta=[0-9]+ frame_inspection=1")

    add_test(NAME autoplayer_monster_behavior4_chase_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer monster_behavior4_chase)
    set_tests_properties(autoplayer_monster_behavior4_chase_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=monster_behavior4_chase chase_dx=[0-9]+ timer_after=1 killed=1 frame_inspection=1")

    add_test(NAME autoplayer_monster_spawner_cycle_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer monster_spawner_cycle)
    set_tests_properties(autoplayer_monster_spawner_cycle_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=monster_spawner_cycle spawner_index=1 reserved_slot=1 released_slot=1 respawned=1 frame_inspection=1")

    add_test(NAME autoplayer_monster_spawner_behavior4_level2_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer monster_spawner_behavior4_level2)
    set_tests_properties(autoplayer_monster_spawner_behavior4_level2_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=monster_spawner_behavior4_level2 level=2 spawner_index=[0-9]+ ai0=[0-9]+ ai1=[0-9]+ ai2=[0-9]+ hp=[0-9]+ vx8=[0-9-]+ vy8=[0-9-]+ frame_inspection=1")

    add_test(NAME autoplayer_monster_spawner_behavior4_level3_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer monster_spawner_behavior4_level3)
    set_tests_properties(autoplayer_monster_spawner_behavior4_level3_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=monster_spawner_behavior4_level3 level=3 spawner_index=[0-9]+ ai0=[0-9]+ ai1=[0-9]+ ai2=[0-9]+ hp=[0-9]+ vx8=[0-9-]+ vy8=[0-9-]+ frame_inspection=1")

    add_test(NAME autoplayer_monster_behavior4_target_selection_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer monster_behavior4_target_selection)
    set_tests_properties(autoplayer_monster_behavior4_target_selection_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=monster_behavior4_target_selection level=3 spawner_index=[0-9]+ initial_target=2 retarget_p1=1 retarget_p2=1 frame_inspection=1")

    add_test(NAME autoplayer_collapse_playback_route_dummy
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-autoplayer collapse_playback_route)
    set_tests_properties(autoplayer_collapse_playback_route_dummy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^autoplayer=ok scenario=collapse_playback_route collapse_started=1 collapse_count=[0-9]+ playback_frames=24 frame_inspection=1")

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
        add_test(NAME python_tool_syntax_lane_result_preflight
            COMMAND ${Python3_EXECUTABLE} -B -m py_compile
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_write_runtime.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_explosion_procmem.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_dispatch_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_dispatch_ready_pipeline.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_dispatch_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_dispatch_gate_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_dispatch_gate_sweep_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_contact_evidence_map.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_contact_callsite_context.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_contact_callsite_scan.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_contact_route_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_contact_procmem_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_update_dispatch_gates.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_update_debug_capture_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_update_runtime_oracle_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_behavior4_debug_capture_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_behavior4_runtime_oracle_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_optional_original_oracle_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_contact_scanner_debug_capture_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_contact_scanner_runtime_oracle_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_debug_capture_batch_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_debug_capture_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_debug_capture_ready_pipeline.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_debug_capture_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_debug_capture_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_evidence_map.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_lane_result_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_lane_result_layout.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_lane_result_orchestrator.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_lane_result_preflight.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_lane_result_wrapper.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_gran_data_evidence_map.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_frame_compare_bundle_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_frame_compare_workflow.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_state2_visual_compare_workflow.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_original_evidence_blocker_note.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_original_evidence_environment.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_record_flow_evidence_map.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_result_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_result_ready_pipeline.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_result_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_result_route_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_result_route_sweep_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_write_route_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_write_route_sweep_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_write_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_write_ready_pipeline.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_write_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_gran_usage_guardrail.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_ready_fixture_provenance_contract.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_runtime_evidence_guardrail.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_guardrail.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_promotion_candidate.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_promotion_entry.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_promotion_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_promotion_plan.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_promotion_workflow.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_state2_visual_frame_capture_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_table_debug_capture_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_table_oracle_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_native_windows_validation_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/run_actor_dispatch_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/run_debug_capture_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/run_lane_result_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/run_lane_write_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/preflight_original_evidence_environment.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/compare_state2_visual_row_game_previews.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/ready_result_checker_support.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/ready_result_fixture_guardrails.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/summarize_actor_dispatch_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/summarize_actor_dispatch_gate_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/summarize_debug_capture_batch.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/summarize_debug_capture.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/summarize_debug_capture_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/summarize_frame_compare_bundle.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/summarize_lane_result_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/summarize_lane_result_route_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/summarize_lane_write_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/summarize_lane_write_route_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_actor_dispatch_gates.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_actor_contact_routes.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_lane_write_routes.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_lane_result_routes.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/plan_visual_claim_promotions.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_visual_claim_promotion_candidate.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/write_visual_claim_promotion_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/write_visual_claim_promotion_entry.py)
        set_tests_properties(python_tool_syntax_lane_result_preflight PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

        add_test(NAME actor_dispatch_gate_sweep_summary_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_dispatch_gate_sweep_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_dispatch_gate_sweep_summary_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_dispatch_gate_sweep_summary_check=ok cases=19")

        add_test(NAME actor_dispatch_ready_manifest_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_dispatch_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_dispatch_ready_manifest_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_dispatch_ready_manifest_check=ok cases=18")

        add_test(NAME actor_dispatch_ready_results_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_dispatch_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_dispatch_ready_results_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_dispatch_ready_results_check=ok cases=29")

        add_test(NAME actor_dispatch_ready_pipeline_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_dispatch_ready_pipeline.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_dispatch_ready_pipeline_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_dispatch_ready_pipeline_check=ok cases=4")

        add_test(NAME original_evidence_environment_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_original_evidence_environment.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(original_evidence_environment_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^original_evidence_environment_check=ok cases=11")

        add_test(NAME gran_data_evidence_map
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_gran_data_evidence_map.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(gran_data_evidence_map PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^gran_data_evidence_map=ok raw_size=399 record_size=57 records=7 sha256=3f0cf17706d557ca863d6e39bfa6641fba777a88815ba3f0a22e5ac89e0e39e2 zero_bytes=150 ctests=2 docs=3 source_guards=5 opaque_claim=1")

        add_test(NAME original_evidence_blocker_note_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_original_evidence_blocker_note.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(original_evidence_blocker_note_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^original_evidence_blocker_note=ok docs=1 ctest=1 commands=3 blocker=windows_no_default_wsl_distro")

        add_test(NAME frame_compare_identical
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/frame_compare.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/frame_compare/a.pnm
                    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/frame_compare/b.pnm)
        set_tests_properties(frame_compare_identical PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^frame_compare=ok size=2x2 normalized=none pixels=4 exact_match=1 exact_different_pixels=0 threshold=0 threshold_different_pixels=0 max_delta=0")

        add_test(NAME frame_compare_workflow_contract
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_frame_compare_workflow.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(frame_compare_workflow_contract PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^frame_compare_workflow=ok wrapper=1 helpers=4 docs=1 ctest=2 scenarios=2 original_preflight=1 failure_manifest=1")

        add_test(NAME frame_compare_bundle_summary_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_frame_compare_bundle_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(frame_compare_bundle_summary_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^frame_compare_bundle_summary_check=ok cases=5")

        add_test(NAME state2_visual_compare_workflow
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_state2_visual_compare_workflow.py
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    $<TARGET_FILE:lezac_cpp>
                    ${CMAKE_CURRENT_BINARY_DIR}/state2_visual_compare_workflow)
        set_tests_properties(state2_visual_compare_workflow PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^state2_visual_compare_workflow=ok helpers=2 docs=1 ctest=1 compared=12")

        add_test(NAME state2_visual_frame_capture_helper_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_state2_visual_frame_capture_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    ${CMAKE_CURRENT_BINARY_DIR}/state2_visual_frame_capture_helper)
        set_tests_properties(state2_visual_frame_capture_helper_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^state2_visual_frame_capture_helper=ok scenarios=1 frames=6 docs=3 ctest=2 dry_run=")

        add_test(NAME explosion_freeze_patch_describe_lane_result_3d3f
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_explosion_procmem.py
                    ${CMAKE_CURRENT_BINARY_DIR}/freeze_patch_describe
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --describe-freeze-patch
                    --freeze-ghidra-offset 1000:3D3F
                    --freeze-patch-mode lane-result-cs-scratch)
        set_tests_properties(explosion_freeze_patch_describe_lane_result_3d3f PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "freeze_patch_description=ok .*ghidra_offset=0x3d3f .*file_offset=0x44af .*patch_mode=lane-result-cs-scratch .*expected_original_bytes=268805 original_bytes=268805 patch_bytes=e9beb4 .*scratch_offset=0xf280 scratch_length=18 body_offset=0xf200 body_length=65")

        add_test(NAME explosion_freeze_patch_describe_lane_result_3ed3
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_explosion_procmem.py
                    ${CMAKE_CURRENT_BINARY_DIR}/freeze_patch_describe
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --describe-freeze-patch
                    --freeze-ghidra-offset 1000:3ED3
                    --freeze-patch-mode lane-result-cs-scratch)
        set_tests_properties(explosion_freeze_patch_describe_lane_result_3ed3 PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "freeze_patch_description=ok .*ghidra_offset=0x3ed3 .*file_offset=0x4643 .*patch_mode=lane-result-cs-scratch .*expected_original_bytes=268805 original_bytes=268805 patch_bytes=e92ab3 .*scratch_offset=0xf280 scratch_length=18 body_offset=0xf200 body_length=65")

        add_test(NAME explosion_freeze_patch_describe_lane_result_wrong_offset
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_explosion_procmem.py
                    ${CMAKE_CURRENT_BINARY_DIR}/freeze_patch_describe
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --describe-freeze-patch
                    --freeze-ghidra-offset 1000:3D2D
                    --freeze-patch-mode lane-result-cs-scratch)
        set_tests_properties(explosion_freeze_patch_describe_lane_result_wrong_offset PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "lane-result-cs-scratch is only valid at 1000:3D3F or 1000:3ED3")

        add_test(NAME explosion_lane_result_preflight
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_lane_result_preflight.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_result_preflight PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_preflight=ok .*offsets=1000:3D3F,1000:3ED3 .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_fixture_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_lane_result_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox)
        set_tests_properties(explosion_lane_result_fixture_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_fixtures=ok files=13 valid=2 malformed=11 cmake_tests=13")

        add_test(NAME explosion_lane_result_layout_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_lane_result_layout.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_result_layout_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_layout=ok fields=9 writer_loops=2")

        add_test(NAME explosion_lane_result_orchestrator_cmake_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_lane_result_orchestrator.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/CMakeLists.txt)
        set_tests_properties(explosion_lane_result_orchestrator_cmake_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_orchestrator_cmake=ok tests=15 will_fail=3")

        add_test(NAME explosion_lane_result_wrapper_output_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_lane_result_wrapper.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_result_wrapper_output_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_wrapper_output=ok cases=15")

        add_test(NAME explosion_evidence_map
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_explosion_evidence_map.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_evidence_map PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^explosion_evidence_map=ok fixtures=47 playback_ctests=47 lane_result_helper_ctests=24 critical_offsets=16 .*oracle_flag=--debug-explosion-playback-oracle docs=3")

        add_test(NAME explosion_lane_result_route_sweep_dry_run
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_lane_result_routes.py
                    /tmp/lezac-lane-result-route-sweep-dry-run
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle
                    --route x:2.00,c:0.50
                    --route x:1.50,z:0.50)
        set_tests_properties(explosion_lane_result_route_sweep_dry_run PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_route_sweep=ok mode=dry_run .*offset=forward routes=2 route_labels=x2p00_c0p50,x1p50_z0p50 capture_commands=2 oracle_commands=0")

        add_test(NAME explosion_lane_result_route_sweep_default_dry_run
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_lane_result_routes.py
                    /tmp/lezac-lane-result-route-sweep-default-dry-run
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle)
        set_tests_properties(explosion_lane_result_route_sweep_default_dry_run PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_route_sweep=ok mode=dry_run .*offset=forward routes=4 route_labels=x2p00,x2p00_c0p50,x1p50_z0p50,x2p00_m0p35 capture_commands=4 oracle_commands=0 .*environment_preflight=1")

        add_test(NAME explosion_lane_result_route_sweep_output_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_result_route_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_result_route_sweep_output_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_route_sweep_output=ok cases=11")

        add_test(NAME explosion_lane_result_route_sweep_summary_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_result_route_sweep_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_result_route_sweep_summary_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_route_sweep_summary_check=ok cases=10")

        add_test(NAME explosion_lane_write_route_sweep_default_dry_run
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_lane_write_routes.py
                    /tmp/lezac-lane-write-route-sweep-default-dry-run
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle)
        set_tests_properties(explosion_lane_write_route_sweep_default_dry_run PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_write_route_sweep=ok mode=dry_run .*offsets=2 offset_labels=3d2d,3ec1 offset_addresses=1000:3D2D,1000:3EC1 routes=4 route_labels=x2p00,x2p00_c0p50,x1p50_z0p50,x2p00_m0p35 capture_commands=8 oracle_commands=0 runtime_freeze_preset=late-collapse .*environment_preflight=1")

        add_test(NAME explosion_lane_write_route_sweep_output_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_write_route_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_write_route_sweep_output_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_write_route_sweep_output=ok cases=11")

        add_test(NAME explosion_lane_write_route_sweep_summary_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_write_route_sweep_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_write_route_sweep_summary_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_write_route_sweep_summary_check=ok cases=10")

        add_test(NAME explosion_lane_write_ready_manifest_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_write_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_write_ready_manifest_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_write_ready_manifest_check=ok cases=19")

        add_test(NAME explosion_lane_write_ready_results_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_write_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_write_ready_results_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_write_ready_results_check=ok cases=25")

        add_test(NAME explosion_lane_write_ready_pipeline_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_write_ready_pipeline.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_write_ready_pipeline_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_write_ready_pipeline_check=ok cases=9")

        add_test(NAME explosion_lane_result_ready_manifest_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_result_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_result_ready_manifest_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_ready_manifest_check=ok cases=19")

        add_test(NAME explosion_lane_result_ready_results_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_result_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_result_ready_results_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_ready_results_check=ok cases=25")

        add_test(NAME explosion_lane_result_ready_pipeline_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_lane_result_ready_pipeline.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_result_ready_pipeline_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_ready_pipeline_check=ok cases=9")

        add_test(NAME actor_contact_route_sweep_dry_run
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_actor_contact_routes.py
                    /tmp/lezac-actor-contact-route-sweep-dry-run
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --target contact_scanner_start
                    --timing before_route
                    --route x:5.00,m:0.50,x:2.00
                    --route x:3.00,z:0.50,x:2.00)
        set_tests_properties(actor_contact_route_sweep_dry_run PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_contact_route_sweep=ok mode=dry_run .*target=contact_scanner_start timings=before_route routes=2 route_labels=x5p00_m0p50_x2p00,x3p00_z0p50_x2p00 capture_commands=2")

        add_test(NAME actor_contact_route_sweep_default_dry_run
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_actor_contact_routes.py
                    /tmp/lezac-actor-contact-route-sweep-default-dry-run
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run)
        set_tests_properties(actor_contact_route_sweep_default_dry_run PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_contact_route_sweep=ok mode=dry_run .*target=contact_scanner_start timings=before_bomb,before_route routes=4 .*route_labels=x2p00,x5p00_m0p50_x2p00,x3p00_z0p50_x2p00,x1p50_left0p50_x2p00 .*capture_commands=8 .*environment_preflight=1")

        add_test(NAME actor_contact_route_sweep_output_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_contact_route_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_contact_route_sweep_output_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_contact_route_sweep_output=ok cases=8")

        add_test(NAME actor_dispatch_gate_sweep_dry_run
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_actor_dispatch_gates.py
                    /tmp/lezac-actor-dispatch-gate-sweep-dry-run
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --target actor_update_gate5
                    --target actor_update_gate6
                    --timing both
                    --route x:2.00,c:0.50
                    --route Left:0.25,space:0.75)
        set_tests_properties(actor_dispatch_gate_sweep_dry_run PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_dispatch_gate_sweep=ok mode=dry_run .*targets=2 .*target_labels=actor_update_gate5,actor_update_gate6 .*timings=before_bomb,before_route routes=2 .*sweep_commands=2 .*capture_commands=8")

        add_test(NAME actor_dispatch_gate_sweep_default_dry_run
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_actor_dispatch_gates.py
                    /tmp/lezac-actor-dispatch-gate-sweep-default-dry-run
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run)
        set_tests_properties(actor_dispatch_gate_sweep_default_dry_run PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_dispatch_gate_sweep=ok mode=dry_run .*targets=5 .*target_labels=actor_update_gate5,actor_update_gate5_integration,actor_update_gate5_exit,actor_update_gate6,contact_scanner_callsite .*timings=before_route routes=4 .*route_labels=x2p00,x5p00_m0p50_x2p00,x3p00_z0p50_x2p00,x1p50_left0p50_x2p00 .*sweep_commands=5 .*capture_commands=20 .*environment_preflight=1")

        add_test(NAME actor_dispatch_gate_sweep_all_targets_dry_run
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/sweep_original_actor_dispatch_gates.py
                    /tmp/lezac-actor-dispatch-gate-sweep-all-targets-dry-run
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --target-set all)
        set_tests_properties(actor_dispatch_gate_sweep_all_targets_dry_run PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_dispatch_gate_sweep=ok mode=dry_run .*targets=9 .*target_labels=actor_update_start,actor_update_end,actor_update_gate5,actor_update_gate5_integration,actor_update_gate5_exit,actor_update_gate6,contact_scanner_callsite,contact_scanner_start,contact_scanner_end .*timings=before_route routes=4 .*sweep_commands=9 .*capture_commands=36 .*environment_preflight=1")

        add_test(NAME actor_dispatch_gate_sweep_output_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_dispatch_gate_sweep.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_dispatch_gate_sweep_output_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_dispatch_gate_sweep_output=ok cases=9")

        add_test(NAME actor_contact_callsite_scan
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_contact_callsite_scan.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_contact_callsite_scan PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_contact_callsite_scan=ok .*scanner_entry=1000:5CB0 .*scanner_return=1000:604F .*scanner_calls=1000:6555 .*callsite_bytes=e858f7 .*actor_update_entry=1000:6053")

        add_test(NAME actor_contact_callsite_context
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_contact_callsite_context.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_contact_callsite_context PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_contact_callsite_context=ok .*gate=1000:654E .*gate_bytes=807ecf06 .*skip_target=1000:655B .*callsite=1000:6555 .*call_target=1000:5CB0 .*integration=1000:73E5 .*sibling_gate=1000:65A2 .*sibling_end_target=1000:777F .*integration_jumps=1000:6558,1000:65D7")

        add_test(NAME actor_update_dispatch_gates
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_update_dispatch_gates.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_update_dispatch_gates PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_update_dispatch_gates=ok .*gates=1000:654E=06,1000:65A2=05,1000:7595=05 .*gate6_call_target=1000:5CB0 .*gate5_integration_target=1000:73E5 .*gate5_exit_target=1000:777F")

        find_program(BASH_EXECUTABLE bash)
        if(BASH_EXECUTABLE)
            add_test(NAME behavior4_debug_capture_helper_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_BEHAVIOR4_DEBUG_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_behavior4_debug.sh
                        /tmp/lezac-behavior4-debug-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        monster_behavior4_target_selection)
            set_tests_properties(behavior4_debug_capture_helper_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^behavior4_debug_capture=ok mode=dry_run scenario=monster_behavior4_target_selection route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run")

            add_test(NAME behavior4_debug_capture_helper_level2_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_BEHAVIOR4_DEBUG_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_behavior4_debug.sh
                        /tmp/lezac-behavior4-debug-level2-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        monster_spawner_behavior4_level2)
            set_tests_properties(behavior4_debug_capture_helper_level2_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^behavior4_debug_capture=ok mode=dry_run scenario=monster_spawner_behavior4_level2 route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run")

            add_test(NAME behavior4_debug_capture_helper_level3_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_BEHAVIOR4_DEBUG_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_behavior4_debug.sh
                        /tmp/lezac-behavior4-debug-level3-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        monster_spawner_behavior4_level3)
            set_tests_properties(behavior4_debug_capture_helper_level3_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^behavior4_debug_capture=ok mode=dry_run scenario=monster_spawner_behavior4_level3 route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run")

            add_test(NAME actor_update_debug_capture_helper_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_UPDATE_DEBUG_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_update_debug.sh
                        /tmp/lezac-actor-update-debug-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        object_collision_jump_live)
            set_tests_properties(actor_update_debug_capture_helper_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_update_debug_capture=ok mode=dry_run scenario=object_collision_jump_live route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run")

            add_test(NAME actor_update_debug_capture_helper_contact_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_UPDATE_DEBUG_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_update_debug.sh
                        /tmp/lezac-actor-update-debug-contact-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        monster_contact_damage_live)
            set_tests_properties(actor_update_debug_capture_helper_contact_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_update_debug_capture=ok mode=dry_run scenario=monster_contact_damage_live route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run")

            add_test(NAME actor_update_debug_capture_helper_behavior4_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_UPDATE_DEBUG_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_update_debug.sh
                        /tmp/lezac-actor-update-debug-behavior4-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        monster_behavior4_chase)
            set_tests_properties(actor_update_debug_capture_helper_behavior4_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_update_debug_capture=ok mode=dry_run scenario=monster_behavior4_chase route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run")

            add_test(NAME contact_scanner_debug_capture_helper_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_CONTACT_SCANNER_DEBUG_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_contact_scanner_debug.sh
                        /tmp/lezac-contact-scanner-debug-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        monster_contact_damage_live)
            set_tests_properties(contact_scanner_debug_capture_helper_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^contact_scanner_debug_capture=ok mode=dry_run scenario=monster_contact_damage_live route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run")

            add_test(NAME contact_scanner_debug_capture_helper_object_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_CONTACT_SCANNER_DEBUG_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_contact_scanner_debug.sh
                        /tmp/lezac-contact-scanner-debug-object-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        object_collision_jump_live)
            set_tests_properties(contact_scanner_debug_capture_helper_object_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^contact_scanner_debug_capture=ok mode=dry_run scenario=object_collision_jump_live route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run")

            add_test(NAME contact_scanner_debug_capture_helper_behavior4_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_CONTACT_SCANNER_DEBUG_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_contact_scanner_debug.sh
                        /tmp/lezac-contact-scanner-debug-behavior4-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        monster_behavior4_chase)
            set_tests_properties(contact_scanner_debug_capture_helper_behavior4_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^contact_scanner_debug_capture=ok mode=dry_run scenario=monster_behavior4_chase route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run")

            add_test(NAME visual_table_debug_capture_helper_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_VISUAL_TABLE_DEBUG_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_visual_table_debug.sh
                        /tmp/lezac-visual-table-debug-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        state2_death_table_consumption)
            set_tests_properties(visual_table_debug_capture_helper_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^visual_table_debug_capture=ok mode=dry_run scenario=state2_death_table_consumption route=debugger_seeded .*manifest=.*raw_dump=.*candidate_fixture=.*environment_preflight=dry_run")

            add_test(NAME state2_visual_frame_capture_helper_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_STATE2_VISUAL_FRAME_CAPTURE_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_state2_visual_frames.sh
                        /tmp/lezac-state2-visual-frame-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        state2_death_table_consumption)
            set_tests_properties(state2_visual_frame_capture_helper_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^state2_visual_frame_capture=ok mode=dry_run scenario=state2_death_table_consumption route=debugger_seeded expected_frames=6 .*manifest=.*frame_plan=.*environment_preflight=dry_run")

            add_test(NAME actor_contact_procmem_helper_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_contact_procmem.sh
                        /tmp/lezac-actor-contact-procmem-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        actor_update_start)
            set_tests_properties(actor_contact_procmem_helper_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_contact_procmem=ok mode=dry_run target=actor_update_start ghidra=1000:6053 .*procmem_out=.*environment_preflight=dry_run")

            add_test(NAME actor_contact_procmem_helper_actor_update_end_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_contact_procmem.sh
                        /tmp/lezac-actor-contact-procmem-actor-update-end-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        actor_update_end)
            set_tests_properties(actor_contact_procmem_helper_actor_update_end_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_contact_procmem=ok mode=dry_run target=actor_update_end ghidra=1000:777F .*procmem_out=.*environment_preflight=dry_run")

            add_test(NAME actor_contact_procmem_helper_actor_update_gate5_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_contact_procmem.sh
                        /tmp/lezac-actor-contact-procmem-gate5-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        actor_update_gate5)
            set_tests_properties(actor_contact_procmem_helper_actor_update_gate5_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_contact_procmem=ok mode=dry_run target=actor_update_gate5 ghidra=1000:65A2 .*procmem_out=.*environment_preflight=dry_run")

            add_test(NAME actor_contact_procmem_helper_actor_update_gate5_integration_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_contact_procmem.sh
                        /tmp/lezac-actor-contact-procmem-gate5-integration-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        actor_update_gate5_integration)
            set_tests_properties(actor_contact_procmem_helper_actor_update_gate5_integration_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_contact_procmem=ok mode=dry_run target=actor_update_gate5_integration ghidra=1000:65D7 .*procmem_out=.*environment_preflight=dry_run")

            add_test(NAME actor_contact_procmem_helper_actor_update_gate5_exit_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_contact_procmem.sh
                        /tmp/lezac-actor-contact-procmem-gate5-exit-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        actor_update_gate5_exit)
            set_tests_properties(actor_contact_procmem_helper_actor_update_gate5_exit_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_contact_procmem=ok mode=dry_run target=actor_update_gate5_exit ghidra=1000:7595 .*procmem_out=.*environment_preflight=dry_run")

            add_test(NAME actor_contact_procmem_helper_actor_update_gate6_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_contact_procmem.sh
                        /tmp/lezac-actor-contact-procmem-gate6-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        actor_update_gate6)
            set_tests_properties(actor_contact_procmem_helper_actor_update_gate6_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_contact_procmem=ok mode=dry_run target=actor_update_gate6 ghidra=1000:654E .*procmem_out=.*environment_preflight=dry_run")

            add_test(NAME actor_contact_procmem_helper_contact_scanner_callsite_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_contact_procmem.sh
                        /tmp/lezac-actor-contact-procmem-contact-callsite-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        contact_scanner_callsite)
            set_tests_properties(actor_contact_procmem_helper_contact_scanner_callsite_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_contact_procmem=ok mode=dry_run target=contact_scanner_callsite ghidra=1000:6555 .*procmem_out=.*environment_preflight=dry_run")

            add_test(NAME actor_contact_procmem_helper_contact_scanner_start_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_contact_procmem.sh
                        /tmp/lezac-actor-contact-procmem-contact-start-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        contact_scanner_start)
            set_tests_properties(actor_contact_procmem_helper_contact_scanner_start_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_contact_procmem=ok mode=dry_run target=contact_scanner_start ghidra=1000:5CB0 .*procmem_out=.*environment_preflight=dry_run")

            add_test(NAME actor_contact_procmem_helper_contact_scanner_end_dry_run
                COMMAND ${CMAKE_COMMAND} -E env LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN=1
                        ${BASH_EXECUTABLE}
                        ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_actor_contact_procmem.sh
                        /tmp/lezac-actor-contact-procmem-contact-end-dry-run
                        ${CMAKE_CURRENT_SOURCE_DIR}
                        contact_scanner_end)
            set_tests_properties(actor_contact_procmem_helper_contact_scanner_end_dry_run PROPERTIES
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                PASS_REGULAR_EXPRESSION
                    "^actor_contact_procmem=ok mode=dry_run target=contact_scanner_end ghidra=1000:604F .*procmem_out=.*environment_preflight=dry_run")
        endif()

        add_test(NAME behavior4_debug_capture_helper_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_behavior4_debug_capture_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(behavior4_debug_capture_helper_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^behavior4_debug_capture_helper=ok scenarios=3 anchors=6 outputs=7 cmake_tests=3 docs=2")

        add_test(NAME actor_update_debug_capture_helper_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_update_debug_capture_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_update_debug_capture_helper_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_update_debug_capture_helper=ok scenarios=3 anchors=4 outputs=7 cmake_tests=3 docs=2")

        add_test(NAME contact_scanner_debug_capture_helper_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_contact_scanner_debug_capture_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(contact_scanner_debug_capture_helper_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^contact_scanner_debug_capture_helper=ok scenarios=3 anchors=2 outputs=7 cmake_tests=3 docs=2")

        add_test(NAME visual_table_debug_capture_helper_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_table_debug_capture_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(visual_table_debug_capture_helper_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^visual_table_debug_capture_helper=ok scenarios=1 anchors=5 outputs=7 cmake_test=1 docs=3")

        add_test(NAME debug_capture_summary_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_debug_capture_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(debug_capture_summary_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^debug_capture_summary_check=ok cases=9")

        add_test(NAME debug_capture_batch_summary_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_debug_capture_batch_summary.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(debug_capture_batch_summary_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^debug_capture_batch_summary_check=ok cases=7")

        add_test(NAME debug_capture_ready_manifest_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_debug_capture_ready_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(debug_capture_ready_manifest_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^debug_capture_ready_manifest_check=ok cases=12")

        add_test(NAME debug_capture_ready_results_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_debug_capture_ready_results.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(debug_capture_ready_results_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^debug_capture_ready_results_check=ok cases=24")

        add_test(NAME debug_capture_ready_pipeline_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_debug_capture_ready_pipeline.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(debug_capture_ready_pipeline_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^debug_capture_ready_pipeline_check=ok cases=4")

        add_test(NAME actor_contact_procmem_helper_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_contact_procmem_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_contact_procmem_helper_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_contact_procmem_helper=ok targets=9 cmake_tests=9 docs=2")

        add_test(NAME actor_contact_evidence_map
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_contact_evidence_map.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(actor_contact_evidence_map PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_contact_evidence_map=ok targets=9 gate_targets=5 actor_update_fixtures=5 contact_scanner_fixtures=4 ctests=26 oracle_flags=2 docs=3")

        add_test(NAME actor_update_runtime_oracle_fixture_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_actor_update_runtime_oracle_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox
                    --cmake ${CMAKE_CURRENT_SOURCE_DIR}/CMakeLists.txt
                    --source ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)
        set_tests_properties(actor_update_runtime_oracle_fixture_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^actor_update_runtime_oracle_fixtures=ok files=5 valid=2 malformed=3 original=0 cmake_tests=5 source_command=1")

        add_test(NAME contact_scanner_runtime_oracle_fixture_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_contact_scanner_runtime_oracle_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox
                    --cmake ${CMAKE_CURRENT_SOURCE_DIR}/CMakeLists.txt
                    --source ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)
        set_tests_properties(contact_scanner_runtime_oracle_fixture_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^contact_scanner_runtime_oracle_fixtures=ok files=4 valid=1 malformed=3 original=0 cmake_tests=4 source_command=1")

        add_test(NAME behavior4_runtime_oracle_fixture_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_behavior4_runtime_oracle_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox
                    --cmake ${CMAKE_CURRENT_SOURCE_DIR}/CMakeLists.txt
                    --source ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)
        set_tests_properties(behavior4_runtime_oracle_fixture_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^behavior4_runtime_oracle_fixtures=ok files=4 valid=1 malformed=3 original=0 cmake_tests=4 source_command=1")

        add_test(NAME visual_table_oracle_fixture_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_table_oracle_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox
                    --cmake ${CMAKE_CURRENT_SOURCE_DIR}/CMakeLists.txt
                    --source ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)
        set_tests_properties(visual_table_oracle_fixture_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^visual_table_oracle_fixtures=ok files=6 valid=2 malformed=4 original=1 cmake_tests=6 source_command=1")

        add_test(NAME optional_original_oracle_fixture_conventions
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_optional_original_oracle_fixtures.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(optional_original_oracle_fixture_conventions PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^optional_original_oracle_fixtures=ok lanes=4 scripts=4 prefixes=4 original_counts=4 cmake=4 docs=3")

        add_test(NAME native_windows_validation_helper_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_native_windows_validation_helper.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(native_windows_validation_helper_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^native_windows_validation_helper=ok script=1 cmake=1 docs=2")

        add_test(NAME gran_usage_guardrail
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_gran_usage_guardrail.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(gran_usage_guardrail PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^gran_usage_guardrail=ok source_refs=16 load_refs=1 debug_refs=14 member_refs=1 live_refs=0 ctest=1 docs=3")

        add_test(NAME gran_usage_guardrail_selftest
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_gran_usage_guardrail.py
                    --self-test)
        set_tests_properties(gran_usage_guardrail_selftest PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^gran_usage_guardrail_selftest=ok positive=1 live_ref=1 missing_debug=1 docs=1")

        add_test(NAME ready_fixture_provenance_contract
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_ready_fixture_provenance_contract.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(ready_fixture_provenance_contract PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^ready_fixture_provenance_contract=ok docs=1 validator=1 writers=4 runners=4 result_summaries=4 dry_run_missing_fixture_bypass=4 ledger_selftests=9")

        add_test(NAME visual_claim_guardrail
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_guardrail.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(visual_claim_guardrail PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^visual_claim_guardrail=ok fixtures=76 claim0=76 claim1=0 ledger=1 promoted=0 ctest=1 docs=3")

        add_test(NAME visual_claim_guardrail_selftest
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_guardrail.py
                    --self-test)
        set_tests_properties(visual_claim_guardrail_selftest PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^visual_claim_guardrail_selftest=ok positive=1 missing_artifact=1 unready_bundle=1 mismatch=1")

        add_test(NAME visual_claim_promotion_entry_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_promotion_entry.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(visual_claim_promotion_entry_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^visual_claim_promotion_entry_check=ok cases=4")

        add_test(NAME visual_claim_promotion_candidate_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_promotion_candidate.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(visual_claim_promotion_candidate_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^visual_claim_promotion_candidate_check=ok cases=5")

        add_test(NAME visual_claim_promotion_plan_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_promotion_plan.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(visual_claim_promotion_plan_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^visual_claim_promotion_plan_check=ok cases=8")

        add_test(NAME visual_claim_promotion_manifest_expectations
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_promotion_manifest.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(visual_claim_promotion_manifest_expectations PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^visual_claim_promotion_manifest_check=ok cases=6")

        add_test(NAME visual_claim_promotion_workflow
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_visual_claim_promotion_workflow.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(visual_claim_promotion_workflow PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^visual_claim_promotion_workflow=ok docs=1 tools=6 ctest=6")

        add_test(NAME runtime_evidence_guardrail
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_runtime_evidence_guardrail.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(runtime_evidence_guardrail PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^runtime_evidence_guardrail=ok fixtures=76 original_runtime=21 visual_claim0=21 temp_copy=21 runtime_segments=21 ledger=1 ctest=1 docs=3")

        add_test(NAME runtime_evidence_guardrail_selftest
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_runtime_evidence_guardrail.py
                    --self-test)
        set_tests_properties(runtime_evidence_guardrail_selftest PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^runtime_evidence_guardrail_selftest=ok positive=1 missing_fixture_doc=1 bad_segment=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_preflight
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    --preflight-only
                    --asset-dir ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_result_capture_orchestrator_preflight PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_capture_orchestrator=ok mode=preflight .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_preflight_positional
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --preflight-only)
        set_tests_properties(explosion_lane_result_capture_orchestrator_preflight_positional PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_capture_orchestrator=ok mode=preflight .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_dry_run
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-dry-run
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle)
        set_tests_properties(explosion_lane_result_capture_orchestrator_dry_run PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_capture_orchestrator=ok mode=dry_run .*environment_preflight=1 .*offsets=2 capture_commands=2 oracle_commands=0 offset_labels=3d3f,3ed3 offset_addresses=1000:3D3F,1000:3ED3 .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_dry_run_with_oracle
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-dry-run-oracle
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --cpp-exe ${CMAKE_CURRENT_BINARY_DIR}/lezac_cpp)
        set_tests_properties(explosion_lane_result_capture_orchestrator_dry_run_with_oracle PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_capture_orchestrator=ok mode=dry_run .*offsets=2 capture_commands=2 oracle_commands=2 offset_labels=3d3f,3ed3 offset_addresses=1000:3D3F,1000:3ED3 .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_dry_run_single_offset
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-dry-run-one
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle
                    --offset 3D3F)
        set_tests_properties(explosion_lane_result_capture_orchestrator_dry_run_single_offset PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_capture_orchestrator=ok mode=dry_run .*offsets=1 capture_commands=1 oracle_commands=0 offset_labels=3d3f offset_addresses=1000:3D3F .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_dry_run_reverse_alias
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-dry-run-reverse
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle
                    --offset reverse)
        set_tests_properties(explosion_lane_result_capture_orchestrator_dry_run_reverse_alias PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_capture_orchestrator=ok mode=dry_run .*offsets=1 capture_commands=1 oracle_commands=0 offset_labels=3ed3 offset_addresses=1000:3ED3 .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_dry_run_mixed_order
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-dry-run-mixed-order
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle
                    --offset reverse
                    --offset forward)
        set_tests_properties(explosion_lane_result_capture_orchestrator_dry_run_mixed_order PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_capture_orchestrator=ok mode=dry_run .*offsets=2 capture_commands=2 oracle_commands=0 offset_labels=3ed3,3d3f offset_addresses=1000:3ED3,1000:3D3F .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_dry_run_timing_args
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-dry-run-timing
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle
                    --offset forward
                    --runtime-freeze-after-bomb-seconds 0.125
                    --level-start-seconds 2.25
                    --right-hold-seconds 3.5
                    --sample-seconds 6.75
                    --sample-interval 0.015
                    --route-state-interval 0.5
                    --route-step x:1.25
                    --route-step Left:0.50
                    --tail-freeze-check-seconds 1.25)
        set_tests_properties(explosion_lane_result_capture_orchestrator_dry_run_timing_args PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "--runtime-freeze-after-bomb-seconds 0\\.125 .*--level-start-seconds 2\\.25 .*--right-hold-seconds 3\\.5 .*--sample-seconds 6\\.75 .*--sample-interval 0\\.015 .*--route-state-interval 0\\.5 .*--tail-freeze-check-seconds 1\\.25 .*--route-step x:1\\.25 .*--route-step Left:0\\.50")

        add_test(NAME explosion_lane_result_capture_orchestrator_dry_run_natural_forward
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-dry-run-natural-forward
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle
                    --offset forward
                    --route-step x:2.00
                    --route-step c:0.50
                    --sample-seconds 5.0
                    --sample-interval 0.005
                    --route-state-interval 0
                    --tail-freeze-check-seconds 0.75)
        set_tests_properties(explosion_lane_result_capture_orchestrator_dry_run_natural_forward PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_capture_orchestrator=ok mode=dry_run .*offsets=1 capture_commands=1 oracle_commands=0 offset_labels=3d3f offset_addresses=1000:3D3F .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_dry_run_alias_offsets
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-dry-run-aliases
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle
                    --offset forward
                    --offset reverse)
        set_tests_properties(explosion_lane_result_capture_orchestrator_dry_run_alias_offsets PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_capture_orchestrator=ok mode=dry_run .*offsets=2 capture_commands=2 oracle_commands=0 offset_labels=3d3f,3ed3 offset_addresses=1000:3D3F,1000:3ED3 .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_dry_run_duplicate_offset
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-dry-run-duplicate
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle
                    --offset 3D3F
                    --offset 1000:3D3F)
        set_tests_properties(explosion_lane_result_capture_orchestrator_dry_run_duplicate_offset PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^lane_result_capture_orchestrator=ok mode=dry_run .*offsets=1 capture_commands=1 oracle_commands=0 offset_labels=3d3f offset_addresses=1000:3D3F .*result_tail=1 result_tail_bytes=8b46f63b46f075c58a46f3c47e04268805c9c20600 .*wrong_offset_guard=1")

        add_test(NAME explosion_lane_result_capture_orchestrator_bad_offset
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-dry-run-bad-offset
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle
                    --offset sideways)
        set_tests_properties(explosion_lane_result_capture_orchestrator_bad_offset PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            WILL_FAIL TRUE)

        add_test(NAME explosion_lane_result_capture_orchestrator_refuses_repo_output
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/lane-result-runtime-refusal
                    ${CMAKE_CURRENT_SOURCE_DIR}
                    --dry-run
                    --skip-oracle)
        set_tests_properties(explosion_lane_result_capture_orchestrator_refuses_repo_output PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            WILL_FAIL TRUE)

        add_test(NAME explosion_lane_result_capture_orchestrator_requires_approval
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/capture_original_lane_result_runtime.py
                    /tmp/lezac-lane-result-runtime-refusal
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(explosion_lane_result_capture_orchestrator_requires_approval PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            WILL_FAIL TRUE)
    endif()

    add_test(NAME records_update_temp
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-record-update
                ${CMAKE_CURRENT_BINARY_DIR}/records_test.dat)
    set_tests_properties(records_update_temp PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^record_update=ok top=999999 level=9 name=TEST")

    add_test(NAME records_name_entry_temp
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-record-name-entry
                ${CMAKE_CURRENT_BINARY_DIR}/records_name_test.dat)
    set_tests_properties(records_name_entry_temp PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^record_name_entry=ok top=999999 name=test")

    add_test(NAME records_save_failure_temp
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-record-save-failure
                ${CMAKE_CURRENT_BINARY_DIR}/missing_records_dir/records_test.dat)
    set_tests_properties(records_save_failure_temp PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "record_save_failure=ok pending=999999")

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

    add_test(NAME son_tail_field_mutation
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-son-tail-field-mutation)
    set_tests_properties(son_tail_field_mutation PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^son_tail_fields_mutation=ok steps=130 mutated_steps=130 compared_cursors=14 .* unknown_pair_nonzero_steps=118 ignored_tail_bytes=4,5")

    add_test(NAME gran_raw_roundtrip
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-gran-raw-roundtrip)
    set_tests_properties(gran_raw_roundtrip PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^gran_raw_roundtrip=ok raw_size=399 record_size=57 records=7 payload_size=399 json_records=7")

    add_test(NAME gran_summary
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-gran)
    set_tests_properties(gran_summary PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^gran_record_size=57 records=7 words_per_record=28 trailing_byte=yes")

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

    if(Python3_Interpreter_FOUND)
        add_test(NAME sound_callsite_map
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_sound_callsite_map.py
                    ${CMAKE_CURRENT_SOURCE_DIR})
        set_tests_properties(sound_callsite_map PROPERTIES
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            PASS_REGULAR_EXPRESSION
                "^sound_callsite_map=ok cues=6 .*direct_sweeps=4 .*priority_latch=1000:165a\\.\\.167d .*tick_window=1000:0fbe\\.\\.1088 .*tests=10")
    endif()

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

    add_test(NAME state2_visual_row_model
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-original-state2-visual-row-model)
    set_tests_properties(state2_visual_row_model PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "original_state2_visual_row_model=ok frame_range=0x4a..0x4f rows=4a:10,10,7d,43;4b:10,10,7d,44;4c:10,10,7d,45;4d:10,10,7d,46;4e:10,10,7d,47;4f:10,10,7d,48 row0_sequence=10,10,10,10,10,10 row1_sequence=10,10,10,10,10,10 row2_sequence=7d,7d,7d,7d,7d,7d row3_sequence=43,44,45,46,47,48 sprite_bank=BOMOMIMK sprite_source=row_byte3 sprite_candidates=67,68,69,70,71,72 draw_offset_candidate=16,16 row2_constant=0x7d range_guard=1 visual_claim=0 ghidra=1000:6053")

    add_test(NAME state2_visual_row_assets
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-original-state2-visual-row-assets)
    set_tests_properties(state2_visual_row_assets PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "original_state2_visual_row_assets=ok bank=BOMOMIMK row3_sprites=67:16x16:nonzero147:bbox0,0,14,15;68:16x16:nonzero39:bbox3,4,11,11;69:16x16:nonzero67:bbox2,2,12,12;70:16x16:nonzero138:bbox0,0,15,15;71:16x16:nonzero145:bbox0,0,15,15;72:16x16:nonzero76:bbox0,0,15,15 row3_nonzero_sequence=147,39,67,138,145,76 row3_all_in_bounds=1 row3_all_16x16=1 cursor_sprites=74:16x16:nonzero140:bbox1,2,15,13;75:16x16:nonzero198:bbox0,0,15,14;76:16x16:nonzero224:bbox0,0,15,15;77:16x16:nonzero197:bbox0,0,15,15;78:16x16:nonzero113:bbox0,0,15,15;79:10x5:nonzero22:bbox0,0,8,4 cursor_nonzero_sequence=140,198,224,197,113,22 row3_minus_frame=-7 cursor_matches_row3=0 visual_claim=0 ghidra=1000:6053")

    add_test(NAME state2_visual_row_preview
        COMMAND $<TARGET_FILE:lezac_cpp> --capture-state2-visual-row-preview
                ${CMAKE_CURRENT_BINARY_DIR}/state2_visual_row_preview)
    set_tests_properties(state2_visual_row_preview PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^state2_visual_row_preview=ok frames=6 outputs=12 row3_sprites=67,68,69,70,71,72 cursor_sprites=74,75,76,77,78,79 row3_minus_frame=-7 row3_cursor_hash_mismatch=1 visual_claim=0 .* manifest=manifest.txt")

    add_test(NAME state2_visual_row_game_preview
        COMMAND $<TARGET_FILE:lezac_cpp> --capture-state2-visual-row-game-preview
                ${CMAKE_CURRENT_BINARY_DIR}/state2_visual_row_game_preview)
    set_tests_properties(state2_visual_row_game_preview PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^state2_visual_row_game_preview=ok frames=6 outputs=12 current_sprites=74,75,76,77,78,79 candidate_sprites=67,68,69,70,71,72 candidate_minus_current=-7 candidate_hash_mismatch=1 candidate_renderer=debug_only visual_claim=0 .* manifest=manifest.txt")

    add_test(NAME behavior4_runtime_oracle_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-behavior4-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/behavior4_runtime_oracle_synthetic.txt)
    set_tests_properties(behavior4_runtime_oracle_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "behavior4_runtime_oracle=ok fixture=behavior4_runtime_oracle_synthetic scenario=monster_behavior4_target_selection level=3 runtime_cs=0x1a2b runtime_ds=0x2b3c spawner_index=5 spawner_behavior=4 spawner_ai=20,214,66 spawner_hp=4 actor_slot=0 before_xy=0x0068,0x00a8 after_xy=0x0069,0x00a8 velocity8=32,0 motion_timer=1 target_before=2 target_after=1 players_dead=0,1 breaks=6 dump_bytes=32 temp_copy=1 visual_claim=0")

    add_test(NAME behavior4_runtime_oracle_bad_segment
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-behavior4-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/behavior4_runtime_oracle_bad_segment.txt
                --expect-error)
    set_tests_properties(behavior4_runtime_oracle_bad_segment PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "behavior4_runtime_oracle=error fixture=behavior4_runtime_oracle_bad_segment reason=breakpoint_segment_mismatch expected=0x1a2b actual=0xffff")

    add_test(NAME behavior4_runtime_oracle_missing_actor_after
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-behavior4-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/behavior4_runtime_oracle_missing_actor_after.txt
                --expect-error)
    set_tests_properties(behavior4_runtime_oracle_missing_actor_after PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "behavior4_runtime_oracle=error fixture=behavior4_runtime_oracle_missing_actor_after reason=actor_after_missing")

    add_test(NAME behavior4_runtime_oracle_bad_behavior
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-behavior4-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/behavior4_runtime_oracle_bad_behavior.txt
                --expect-error)
    set_tests_properties(behavior4_runtime_oracle_bad_behavior PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "behavior4_runtime_oracle=error fixture=behavior4_runtime_oracle_bad_behavior reason=spawner_behavior_not_4 actual=3")

    add_test(NAME actor_update_runtime_oracle_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-actor-update-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/actor_update_runtime_oracle_synthetic.txt)
    set_tests_properties(actor_update_runtime_oracle_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "actor_update_runtime_oracle=ok fixture=actor_update_runtime_oracle_synthetic scenario=object_collision_jump_live level=1 runtime_cs=0x1a2b runtime_ds=0x2b3c actor_slot=0 behavior=3 kind=1 before_xy=0x0068,0x00a8 after_xy=0x0069,0x00a8 velocity8=32,0 state=0,0 contact_flags=0x0000,0x0005 scan_subject=0 scan_other=1 scan_contact=1 player_contact=0 monster_contact=0 object_contact=1 damage_pending=0 tile_probe=13,22 tile=0x0025 object=0x0013 passable=0 standable=1 breaks=4 dump_bytes=32 temp_copy=1 visual_claim=0")

    add_test(NAME actor_update_runtime_oracle_dispatch_gates_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-actor-update-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/actor_update_runtime_oracle_dispatch_gates_synthetic.txt)
    set_tests_properties(actor_update_runtime_oracle_dispatch_gates_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "actor_update_runtime_oracle=ok fixture=actor_update_runtime_oracle_dispatch_gates_synthetic scenario=monster_contact_damage_live level=1 runtime_cs=0x1a2b runtime_ds=0x2b3c actor_slot=0 behavior=3 kind=1 before_xy=0x0068,0x00a8 after_xy=0x0069,0x00a8 velocity8=32,0 state=0,0 contact_flags=0x0000,0x0005 scan_subject=0 scan_other=1 scan_contact=1 player_contact=0 monster_contact=0 object_contact=1 damage_pending=0 tile_probe=13,22 tile=0x0025 object=0x0013 passable=0 standable=1 breaks=9 dump_bytes=32 temp_copy=1 visual_claim=0 dispatch_gates=actor_update_gate5,actor_update_gate5_integration,actor_update_gate5_exit,actor_update_gate6,contact_scanner_callsite")

    add_test(NAME actor_update_runtime_oracle_bad_segment
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-actor-update-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/actor_update_runtime_oracle_bad_segment.txt
                --expect-error)
    set_tests_properties(actor_update_runtime_oracle_bad_segment PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "actor_update_runtime_oracle=error fixture=actor_update_runtime_oracle_bad_segment reason=breakpoint_segment_mismatch expected=0x1a2b actual=0xffff")

    add_test(NAME actor_update_runtime_oracle_missing_contact_scan
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-actor-update-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/actor_update_runtime_oracle_missing_contact_scan.txt
                --expect-error)
    set_tests_properties(actor_update_runtime_oracle_missing_contact_scan PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "actor_update_runtime_oracle=error fixture=actor_update_runtime_oracle_missing_contact_scan reason=contact_scan_missing")

    add_test(NAME actor_update_runtime_oracle_bad_actor_slot
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-actor-update-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/actor_update_runtime_oracle_bad_actor_slot.txt
                --expect-error)
    set_tests_properties(actor_update_runtime_oracle_bad_actor_slot PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "actor_update_runtime_oracle=error fixture=actor_update_runtime_oracle_bad_actor_slot reason=actor_slot_changed before=0 after=2")

    add_test(NAME contact_scanner_runtime_oracle_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-contact-scanner-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/contact_scanner_runtime_oracle_synthetic.txt)
    set_tests_properties(contact_scanner_runtime_oracle_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "contact_scanner_runtime_oracle=ok fixture=contact_scanner_runtime_oracle_synthetic scenario=monster_contact_damage_live level=1 runtime_cs=0x1a2b runtime_ds=0x2b3c subject_slot=0 other_slot=1 subject_kind=0 other_kind=1 subject_xy=0x0068,0x00a8 other_xy=0x0070,0x00aa subject_size=16,24 other_size=16,16 subject_flags=0x0000,0x0003 contact=1 player_contact=1 monster_contact=1 object_contact=0 damage_pending=2 overlap=8,14 breaks=2 dump_bytes=16 temp_copy=1 visual_claim=0")

    add_test(NAME contact_scanner_runtime_oracle_bad_segment
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-contact-scanner-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/contact_scanner_runtime_oracle_bad_segment.txt
                --expect-error)
    set_tests_properties(contact_scanner_runtime_oracle_bad_segment PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "contact_scanner_runtime_oracle=error fixture=contact_scanner_runtime_oracle_bad_segment reason=breakpoint_segment_mismatch expected=0x1a2b actual=0xffff")

    add_test(NAME contact_scanner_runtime_oracle_missing_contact_scan
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-contact-scanner-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/contact_scanner_runtime_oracle_missing_contact_scan.txt
                --expect-error)
    set_tests_properties(contact_scanner_runtime_oracle_missing_contact_scan PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "contact_scanner_runtime_oracle=error fixture=contact_scanner_runtime_oracle_missing_contact_scan reason=contact_scan_missing")

    add_test(NAME contact_scanner_runtime_oracle_bad_subject_flags
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-contact-scanner-runtime-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/contact_scanner_runtime_oracle_bad_subject_flags.txt
                --expect-error)
    set_tests_properties(contact_scanner_runtime_oracle_bad_subject_flags PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "contact_scanner_runtime_oracle=error fixture=contact_scanner_runtime_oracle_bad_subject_flags reason=contact_flags_before_mismatch actor=0x0001 scan=0x0000")

    add_test(NAME sound_callsite_oracle_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-sound-callsite-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/sound_callsite_oracle_synthetic.txt)
    set_tests_properties(sound_callsite_oracle_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "sound_callsite_oracle=ok fixture=sound_callsite_oracle_synthetic scenario=player_damage_sound level=1 runtime_cs=0x1a2b runtime_ds=0x2b3c label=hurt callsite=0x1000:7f9a latch=0x1000:165a cursor=0x002d priority=4 active_before=0 current_priority_before=0 accepted=1 active_after=1 current_priority_after=4 current_cursor_after=0x002d direct_sweep=0 breaks=2 dump_bytes=42 temp_copy=1 visual_claim=0")

    add_test(NAME sound_callsite_oracle_bad_segment
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-sound-callsite-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/sound_callsite_oracle_bad_segment.txt
                --expect-error)
    set_tests_properties(sound_callsite_oracle_bad_segment PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "sound_callsite_oracle=error fixture=sound_callsite_oracle_bad_segment reason=breakpoint_segment_mismatch expected=0x1a2b actual=0xffff")

    add_test(NAME sound_callsite_oracle_missing_request
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-sound-callsite-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/sound_callsite_oracle_missing_request.txt
                --expect-error)
    set_tests_properties(sound_callsite_oracle_missing_request PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "sound_callsite_oracle=error fixture=sound_callsite_oracle_missing_request reason=sound_request_missing")

    add_test(NAME sound_callsite_oracle_bad_pending_cursor
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-sound-callsite-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/sound_callsite_oracle_bad_pending_cursor.txt
                --expect-error)
    set_tests_properties(sound_callsite_oracle_bad_pending_cursor PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "sound_callsite_oracle=error fixture=sound_callsite_oracle_bad_pending_cursor reason=pending_cursor_dump_mismatch expected=0x002d actual=0x002e")

    add_test(NAME visual_table_oracle_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-visual-table-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/visual_table_oracle_synthetic.txt)
    set_tests_properties(visual_table_oracle_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "visual_table_oracle=ok fixture=visual_table_oracle_synthetic scenario=state2_death_table_consumption runtime_cs=0x1a2b runtime_ds=0x2b3c actor_slot=0 actor_state=2 anim_current=0x72 anim_range=0x72..0x79 anim_mode=1 visual_frame=0x72 row_addr=0xc4ea row=10,18,20,00 bank=BOMOMIMK sprite_index=16 sprite_source=row_byte0 draw_offset=24,32 effect_slot=0 effect_before_xy=0x0018,0x0028 effect_after_xy=0x0018,0x0028 effect_after_frame=0x72 breaks=5 temp_copy=1 visual_claim=0")

    add_test(NAME visual_table_oracle_original_state2_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-visual-table-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/visual_table_oracle_original_state2_runtime.txt)
    set_tests_properties(visual_table_oracle_original_state2_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "visual_table_oracle=ok fixture=visual_table_oracle_original_state2_runtime scenario=state2_death_table_consumption runtime_cs=0x01ed runtime_ds=0x0c8f actor_slot=0 actor_state=2 anim_current=0x4a anim_range=0x4a..0x4f anim_mode=1 visual_frame=0x4a row_addr=0xc44a row=10,10,7d,43 bank=BOMOMIMK sprite_index=67 sprite_source=row_byte3 draw_offset=16,16 effect_slot=0 effect_before_xy=0x0068,0x00a8 effect_after_xy=0x0068,0x00a8 effect_after_frame=0x4a breaks=5 temp_copy=1 visual_claim=0")

    add_test(NAME visual_table_oracle_bad_segment
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-visual-table-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/visual_table_oracle_bad_segment.txt
                --expect-error)
    set_tests_properties(visual_table_oracle_bad_segment PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "visual_table_oracle=error fixture=visual_table_oracle_bad_segment reason=breakpoint_segment_mismatch expected=0x1a2b actual=0xffff")

    add_test(NAME visual_table_oracle_missing_row_byte
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-visual-table-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/visual_table_oracle_missing_row_byte.txt
                --expect-error)
    set_tests_properties(visual_table_oracle_missing_row_byte PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "visual_table_oracle=error fixture=visual_table_oracle_missing_row_byte reason=missing_byte address=c4ed")

    add_test(NAME visual_table_oracle_sprite_without_row
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-visual-table-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/visual_table_oracle_sprite_without_row.txt
                --expect-error)
    set_tests_properties(visual_table_oracle_sprite_without_row PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "visual_table_oracle=error fixture=visual_table_oracle_sprite_without_row reason=visual_row_missing_for_sprite")

    add_test(NAME visual_table_oracle_bad_row_byte3_sprite
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-visual-table-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/visual_table_oracle_bad_row_byte3_sprite.txt
                --expect-error)
    set_tests_properties(visual_table_oracle_bad_row_byte3_sprite PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "visual_table_oracle=error fixture=visual_table_oracle_bad_row_byte3_sprite reason=sprite_index_row3_mismatch row3=67 sprite_index=66")

    add_test(NAME state2_runtime_frame_oracle_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-state2-runtime-frame-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/state2_runtime_frame_oracle_synthetic.txt)
    set_tests_properties(state2_runtime_frame_oracle_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "state2_runtime_frame_oracle=ok fixture=state2_runtime_frame_oracle_synthetic runtime_cs=0x1a2b runtime_ds=0x2b3c death_cursor=0x56 death_start=0x72 death_end=0x79 table_entry_base=0xc322 first_entry_addr=0xc4ea frame_rows=8 first_row=10,18,20,00 last_row=17,18,20,00 rows=72@c4ea:10,18,20,00;73@c4ee:11,18,20,00;74@c4f2:12,18,20,00;75@c4f6:13,18,20,00;76@c4fa:14,18,20,00;77@c4fe:15,18,20,00;78@c502:16,18,20,00;79@c506:17,18,20,00 row0_sequence=10,11,12,13,14,15,16,17 row1_sequence=18,18,18,18,18,18,18,18 row2_sequence=20,20,20,20,20,20,20,20 row3_sequence=00,00,00,00,00,00,00,00 effect0_xy=0x0018,0x0028 breaks=4 temp_copy=1 visual_claim=0")

    add_test(NAME state2_runtime_frame_oracle_original
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-state2-runtime-frame-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/state2_runtime_frame_oracle_original.txt)
    set_tests_properties(state2_runtime_frame_oracle_original PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "state2_runtime_frame_oracle=ok fixture=state2_runtime_frame_oracle_original runtime_cs=0x01ed runtime_ds=0x0c8f death_cursor=0x45 death_start=0x4a death_end=0x4f table_entry_base=0xc322 first_entry_addr=0xc44a frame_rows=6 first_row=10,10,7d,43 last_row=10,10,7d,48 rows=4a@c44a:10,10,7d,43;4b@c44e:10,10,7d,44;4c@c452:10,10,7d,45;4d@c456:10,10,7d,46;4e@c45a:10,10,7d,47;4f@c45e:10,10,7d,48 row0_sequence=10,10,10,10,10,10 row1_sequence=10,10,10,10,10,10 row2_sequence=7d,7d,7d,7d,7d,7d row3_sequence=43,44,45,46,47,48 effect0_xy=0x0068,0x00a8 breaks=5 temp_copy=1 visual_claim=0")

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
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_synthetic .*playback_breaks=15 .*debris0_tile_index=0x0393 debris0_flagged=0xc000 debris0_forward=0x04 debris0_reverse=0x05 debris0_lookup=0x6b .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 collapse0_forward=0x02 collapse0_reverse=0x03 .*high_debris_target_delta=0x0001 high_debris_target_offset=0x0394 .*high_debris_target_byte=0x75 high_debris_word_layer_value=0x8009 .*effect0_xy=0x0018,0x0028 effect0_sprite=0x84 effect0_detail=0x75 effect0_timer=0x08 effect0_variant=0x05 temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_lane_div_scratch_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_div_scratch_synthetic.txt)
    set_tests_properties(explosion_playback_oracle_lane_div_scratch_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_lane_div_scratch_synthetic .*playback_breaks=16 observed_freeze_count=1 observed_freeze_offset=0x3ce3 .*observed_lane_forward_divide=1 observed_lane_reverse_divide=0 .*lane_div_scratch_present=1 lane_div_kind=forward lane_div_cs_offset=0x3d23 lane_div_ax=0xfff7 lane_div_dx=0xffff lane_div_cx=0x0001 lane_div_bx=0x0000 lane_div_active_count=0x0001 lane_div_loop_index=0x0001 lane_div_weight_local=0x0001 lane_div_numerator_low=0xfff7 lane_div_numerator_high=0xffff .*debris0_tile_index=0x0393 debris0_flagged=0xc000 .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_lane_result_scratch_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_scratch_synthetic.txt)
    set_tests_properties(explosion_playback_oracle_lane_result_scratch_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_lane_result_scratch_synthetic .*playback_breaks=16 observed_freeze_count=1 observed_freeze_offset=0x3d3f .*observed_lane_forward_result=1 observed_lane_reverse_result=0 .*lane_result_scratch_present=1 lane_result_kind=forward lane_result_cs_offset=0xf280 lane_result_output=0x0004 lane_result_es=0x2b3c lane_result_di=0x78d2 lane_result_arg_offset=0x78d2 lane_result_arg_segment=0x2b3c lane_result_result_local=0x0004 lane_result_active_count=0x0001 lane_result_loop_index=0x0001 lane_result_target_before=0x0010 .*freeze_expected_old_bytes_present=1 freeze_expected_old_bytes=268805 freeze_old_bytes=268805 .*debris0_tile_index=0x0393 debris0_flagged=0xc000 .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_lane_result_reverse_scratch_synthetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_reverse_scratch_synthetic.txt)
    set_tests_properties(explosion_playback_oracle_lane_result_reverse_scratch_synthetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_lane_result_reverse_scratch_synthetic .*playback_breaks=16 observed_freeze_count=1 observed_freeze_offset=0x3ed3 .*observed_lane_forward_result=0 observed_lane_reverse_result=1 .*lane_result_scratch_present=1 lane_result_kind=reverse lane_result_cs_offset=0xf280 lane_result_output=0x0000 lane_result_es=0x2b3c lane_result_di=0x78d4 lane_result_arg_offset=0x78d4 lane_result_arg_segment=0x2b3c lane_result_result_local=0x0000 lane_result_active_count=0x0001 lane_result_loop_index=0x0001 lane_result_target_before=0x0004 .*freeze_expected_old_bytes_present=1 freeze_expected_old_bytes=268805 freeze_old_bytes=268805 .*debris0_tile_index=0x0393 debris0_flagged=0xc000 .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt)
    set_tests_properties(explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded .*playback_breaks=25 observed_freeze_count=1 observed_freeze_offset=0x3d3f .*observed_lane_forward_result=1 observed_lane_reverse_result=0 .*lane_result_scratch_present=1 lane_result_kind=forward lane_result_cs_offset=0xf280 lane_result_output=0x00fa lane_result_es=0x0c44 lane_result_di=0x78d2 lane_result_arg_offset=0x78d2 lane_result_arg_segment=0x0c44 lane_result_result_local=0x00fa lane_result_active_count=0x0001 lane_result_loop_index=0x0001 lane_result_target_before=0x00f3 .*freeze_expected_old_bytes_present=1 freeze_expected_old_bytes=268805 freeze_old_bytes=268805 .*runtime_seeded=1 runtime_seed_kind=debris-writeback runtime_seed_direction=forward runtime_seed_word=0xc004 runtime_seed_patch_applied=1 .*lane_globals_present=1 lane_update_flag=0x01 lane_word_global_value=0xc004 lane_target_offset_global_value=0x0a7a effect_input_globals_present=1 effect_forward_input_global_value=0xf3 effect_reverse_input_global_value=0x00 .*debris_count=0x00ca debris_count_base=0x2941 debris_base=0x2941 .*collapse_count=0x0002 collapse_count_base=0x662f collapse_base=0x662f .*collapse0_start=0x07a0 collapse0_end=0x07be collapse0_word=0x0002 collapse0_flagged=0x8002 .*effect0_xy=0x00a8,0x00a8 effect0_sprite=0x10 effect0_detail=0x10 effect0_timer=0x7d effect0_variant=0x45 temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze.txt)
    set_tests_properties(explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze .*playback_breaks=25 observed_freeze_count=0 observed_freeze_offset=0x0000 .*observed_lane_forward_result=0 observed_lane_reverse_result=0 .*lane_result_scratch_present=0 freeze_expected_old_bytes_present=1 freeze_expected_old_bytes=268805 freeze_old_bytes=268805 runtime_seeded=0 lane_globals_present=1 lane_update_flag=0x05 lane_word_global_value=0x0004 lane_target_offset_global_value=0x072c effect_input_globals_present=1 effect_forward_input_global_value=0x00 effect_reverse_input_global_value=0xfb .*debris_count=0x00ca debris_count_base=0x2941 debris_base=0x2941 .*debris0_tile_index=0x03a3 debris0_flagged=0xc002 .*collapse_count=0x0004 collapse_count_base=0x664d collapse_base=0x664d .*collapse0_start=0x0562 collapse0_end=0x0742 collapse0_word=0x0005 collapse0_flagged=0x8005 .*effect0_xy=0x00f0,0x00b0 effect0_sprite=0x10 effect0_detail=0x10 effect0_timer=0x7d effect0_variant=0x3f temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3ed3_lane_result_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3ed3_lane_result_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_3ed3_lane_result_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3ed3_lane_result_runtime .*playback_breaks=25 observed_freeze_count=1 observed_freeze_offset=0x3ed3 .*observed_lane_forward_result=0 observed_lane_reverse_result=1 .*lane_result_scratch_present=1 lane_result_kind=reverse lane_result_cs_offset=0xf280 lane_result_output=0x00ef lane_result_es=0x18b3 lane_result_di=0x3fe6 lane_result_arg_offset=0x3fe6 lane_result_arg_segment=0x18b3 lane_result_result_local=0x00ef lane_result_active_count=0x0001 lane_result_loop_index=0x0001 lane_result_target_before=0x00de .*freeze_expected_old_bytes_present=1 freeze_expected_old_bytes=268805 freeze_old_bytes=268805 .*lane_globals_present=1 lane_update_flag=0x00 lane_word_global_value=0x0000 lane_target_offset_global_value=0x0000 effect_input_globals_present=1 effect_forward_input_global_value=0x10 effect_reverse_input_global_value=0xd6 .*debris_count=0x00c7 debris_count_base=0x2920 debris_base=0x209e .*debris0_tile_index=0x0540 debris0_flagged=0x0000 .*collapse_count=0x0001 collapse_count_base=0x6620 collapse_base=0x6620 .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 collapse0_forward=0x0f collapse0_reverse=0xd6 .*effect0_xy=0x00bf,0x00b0 effect0_sprite=0x10 effect0_detail=0x10 effect0_timer=0x7d effect0_variant=0x40 temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_lane_result_missing_target_before
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_missing_target_before.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_missing_target_before PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_missing_target_before reason=lane_result_field_missing field=target_before")

    add_test(NAME explosion_playback_oracle_lane_result_bad_far_pointer
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_bad_far_pointer.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_bad_far_pointer PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_bad_far_pointer reason=lane_result_far_pointer_mismatch")

    add_test(NAME explosion_playback_oracle_lane_result_bad_output_local
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_bad_output_local.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_bad_output_local PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_bad_output_local reason=lane_result_output_local_mismatch")

    add_test(NAME explosion_playback_oracle_lane_result_bad_expected_old_bytes
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_bad_expected_old_bytes.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_bad_expected_old_bytes PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_bad_expected_old_bytes reason=freeze_expected_old_bytes_mismatch")

    add_test(NAME explosion_playback_oracle_lane_result_expected_without_old_bytes
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_expected_without_old_bytes.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_expected_without_old_bytes PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_expected_without_old_bytes reason=freeze_expected_without_old_bytes")

    add_test(NAME explosion_playback_oracle_lane_result_missing_expected_old_bytes
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_missing_expected_old_bytes.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_missing_expected_old_bytes PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_missing_expected_old_bytes reason=lane_result_expected_old_bytes_missing")

    add_test(NAME explosion_playback_oracle_lane_result_bad_scratch_offset
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_bad_scratch_offset.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_bad_scratch_offset PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_bad_scratch_offset reason=lane_result_scratch_offset_mismatch")

    add_test(NAME explosion_playback_oracle_lane_result_bad_kind
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_bad_kind.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_bad_kind PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_bad_kind reason=lane_result_forward_kind_without_forward_freeze")

    add_test(NAME explosion_playback_oracle_lane_result_bad_loop_bounds
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_bad_loop_bounds.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_bad_loop_bounds PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_bad_loop_bounds reason=lane_result_loop_bounds")

    add_test(NAME explosion_playback_oracle_lane_result_bad_target_before_width
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_bad_target_before_width.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_bad_target_before_width PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_bad_target_before_width reason=lane_result_target_before_width")

    add_test(NAME explosion_playback_oracle_lane_result_field_without_present
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_result_field_without_present.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_result_field_without_present PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_result_field_without_present reason=lane_result_field_without_present")

    add_test(NAME explosion_playback_oracle_selected_bases
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_selected_bases.txt)
    set_tests_properties(explosion_playback_oracle_selected_bases PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_selected_bases .*debris_base=0x209e .*debris0_tile_index=0x0393 debris0_flagged=0xc000 .*collapse_base=0x662f .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 .*effect_base=0xc22e .*effect0_xy=0x0018,0x0028 effect0_sprite=0x84 effect0_detail=0x75 effect0_timer=0x08 effect0_variant=0x05 temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_count_selected
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_count_selected.txt)
    set_tests_properties(explosion_playback_oracle_count_selected PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_count_selected .*debris_count_present=1 debris_count=0x0001 debris_count_base=0x209e debris_base=0x209e .*collapse_count_present=1 collapse_count=0x0001 collapse_count_base=0x6620 collapse_base=0x6620 .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 .*effect_base=0xc22e .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_sparse_count
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_sparse_count.txt)
    set_tests_properties(explosion_playback_oracle_sparse_count PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_sparse_count .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*debris0_tile_index=0x0540 debris0_flagged=0xc004 .*debris0_lookup=0x67 .*collapse_count_base=0x6620 collapse_base=0x6620 .*effect_base=0xc22e .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_4b6a_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_4b6a_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_4b6a_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_4b6a_runtime .*playback_breaks=13 observed_freeze_count=1 observed_freeze_offset=0x4b6a observed_high_zero_branch=1 observed_high_word_gate=0 observed_effect_forward_call=0 observed_effect_reverse_call=0 .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*debris0_tile_index=0x0540 debris0_flagged=0xc004 debris0_forward=0x3b debris0_reverse=0x00 debris0_lookup=0x67 .*collapse_count=0x0002 collapse_count_base=0x662f collapse_base=0x662f .*collapse0_start=0x0916 collapse0_end=0x0918 collapse0_word=0x000a collapse0_flagged=0x800a .*high_debris_target_offset=0x0541 .*high_debris_target_byte=0x00 high_debris_word_layer_value=0x0000 .*effect_base=0xc22e .*effect0_xy=0x00a9,0x00b0 effect0_sprite=0x10 effect0_detail=0x10 effect0_timer=0x7d effect0_variant=0x40 temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_4c75_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_4c75_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_4c75_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_4c75_runtime .*playback_breaks=13 observed_freeze_count=1 observed_freeze_offset=0x4c75 observed_high_zero_branch=0 observed_high_word_gate=1 observed_effect_forward_call=0 observed_effect_reverse_call=0 .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*debris0_tile_index=0x0541 debris0_flagged=0xc004 debris0_forward=0x3a debris0_reverse=0x00 debris0_lookup=0x67 .*collapse_count=0x0003 collapse_count_base=0x663e collapse_base=0x663e .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 .*high_debris_target_offset=0x05b9 .*high_debris_target_byte=0x00 high_debris_word_layer_value=0x0000 .*effect_base=0xc22e .*effect0_xy=0x00af,0x00b0 effect0_sprite=0x10 effect0_detail=0x10 effect0_timer=0x7d effect0_variant=0x40 temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_4c75_bp4_scratch_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_4c75_bp4_scratch_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_4c75_bp4_scratch_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_4c75_bp4_scratch_runtime .*playback_breaks=15 observed_freeze_count=1 observed_freeze_offset=0x4c75 observed_high_zero_branch=0 observed_high_word_gate=1 observed_effect_forward_call=0 observed_effect_reverse_call=0 .*bp4_local_present=1 bp4_local_cs_offset=0x4c7e bp4_local_value=0x0003 .*lane_globals_present=1 lane_update_flag=0x00 lane_word_global_value=0x0000 lane_target_offset_global_value=0x0000 effect_input_globals_present=1 effect_forward_input_global_value=0xf7 effect_reverse_input_global_value=0xfc .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*high_debris_target_offset=0x05b9 .*high_debris_target_byte=0x00 high_debris_word_layer_value=0x0000 .*effect_base=0xc22e .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime .*playback_breaks=19 observed_freeze_count=1 observed_freeze_offset=0x3cd4 .*observed_lane_forward_divide=1 observed_lane_reverse_divide=0 .*lane_div_scratch_present=1 lane_div_kind=forward lane_div_cs_offset=0x3d24 lane_div_ax=0xfff8 lane_div_dx=0xffff lane_div_cx=0x0005 lane_div_bx=0x0000 lane_div_active_count=0x0001 lane_div_loop_index=0x0001 lane_div_weight_local=0x0005 lane_div_numerator_low=0xfff8 lane_div_numerator_high=0xffff .*lane_globals_present=1 lane_update_flag=0x01 lane_word_global_value=0x8009 lane_target_offset_global_value=0x0a7a .*debris_count=0x00ca debris_count_base=0x2941 debris_base=0x2941 .*collapse_count=0x0002 collapse_count_base=0x662f collapse_base=0x662f .*collapse0_start=0x07a0 collapse0_end=0x07be collapse0_word=0x0002 collapse0_flagged=0x8002 .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime .*playback_breaks=19 observed_freeze_count=1 observed_freeze_offset=0x3ce3 .*observed_lane_forward_divide=1 observed_lane_reverse_divide=0 .*lane_div_scratch_present=1 lane_div_kind=forward lane_div_cs_offset=0x3d33 lane_div_ax=0x001c lane_div_dx=0x0000 lane_div_cx=0x0010 lane_div_bx=0x0000 lane_div_active_count=0x0001 lane_div_loop_index=0x0001 lane_div_weight_local=0x0010 lane_div_numerator_low=0x001c lane_div_numerator_high=0x0000 .*lane_globals_present=1 lane_update_flag=0x00 lane_word_global_value=0x0000 lane_target_offset_global_value=0x0000 .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*collapse_count=0x0001 collapse_count_base=0x6620 collapse_base=0x6620 .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 collapse0_forward=0x09 collapse0_reverse=0xf5 .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime .*playback_breaks=23 observed_freeze_count=1 observed_freeze_offset=0x3d1b .*observed_lane_forward_write=1 observed_lane_reverse_write=0 observed_lane_collapse_write=1 observed_lane_debris_write=0 .*lane_write_scratch_present=1 lane_write_kind=forward lane_write_target=collapse lane_write_cs_offset=0x3d6b lane_write_output=0x0001 lane_write_di=0x002d lane_write_tag=0x0003 lane_write_active_count=0x0001 lane_write_loop_index=0x0001 lane_write_result_local=0x0001 .*collapse_count=0x0001 collapse_count_base=0x6620 collapse_base=0x6620 .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 collapse0_forward=0x11 collapse0_reverse=0xec .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3d1b_lane_write_trampoline_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3d1b_lane_write_trampoline_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_3d1b_lane_write_trampoline_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3d1b_lane_write_trampoline_runtime .*playback_breaks=23 observed_freeze_count=1 observed_freeze_offset=0x3d1b .*observed_lane_forward_write=1 observed_lane_reverse_write=0 observed_lane_collapse_write=1 observed_lane_debris_write=0 .*lane_write_scratch_present=1 lane_write_kind=forward lane_write_target=collapse lane_write_cs_offset=0xf080 lane_write_output=0x0004 lane_write_di=0x003c lane_write_tag=0x0004 lane_write_active_count=0x0001 lane_write_loop_index=0x0001 lane_write_result_local=0x0004 .*collapse_count=0x0003 collapse_count_base=0x663e collapse_base=0x663e .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 collapse0_forward=0x0e collapse0_reverse=0x10 .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3d2d_lane_write_trampoline_no_freeze
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3d2d_lane_write_trampoline_no_freeze.txt)
    set_tests_properties(explosion_playback_oracle_original_3d2d_lane_write_trampoline_no_freeze PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3d2d_lane_write_trampoline_no_freeze .*playback_breaks=23 observed_freeze_count=0 observed_freeze_offset=0x0000 .*observed_lane_forward_write=0 observed_lane_reverse_write=0 observed_lane_collapse_write=0 observed_lane_debris_write=0 .*lane_write_scratch_present=0 .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*collapse_count=0x0003 collapse_count_base=0x663e collapse_base=0x663e .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3d2d_lane_write_runtime_seeded
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3d2d_lane_write_runtime_seeded.txt)
    set_tests_properties(explosion_playback_oracle_original_3d2d_lane_write_runtime_seeded PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3d2d_lane_write_runtime_seeded .*playback_breaks=23 observed_freeze_count=1 observed_freeze_offset=0x3d2d .*observed_lane_forward_write=1 observed_lane_reverse_write=0 observed_lane_collapse_write=0 observed_lane_debris_write=1 .*lane_write_scratch_present=1 lane_write_kind=forward lane_write_target=debris lane_write_cs_offset=0xf080 lane_write_output=0x0035 lane_write_di=0x0898 lane_write_tag=0x4ee8 lane_write_active_count=0x0001 lane_write_loop_index=0x0001 lane_write_result_local=0x0035 .*runtime_seeded=1 runtime_seed_kind=debris-writeback runtime_seed_direction=forward runtime_seed_word=0xc004 runtime_seed_patch_applied=1 .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*debris0_tile_index=0x0542 debris0_flagged=0xc004 .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3eaf_lane_write_trampoline_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3eaf_lane_write_trampoline_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_3eaf_lane_write_trampoline_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3eaf_lane_write_trampoline_runtime .*playback_breaks=23 observed_freeze_count=1 observed_freeze_offset=0x3eaf .*observed_lane_forward_write=0 observed_lane_reverse_write=1 observed_lane_collapse_write=1 observed_lane_debris_write=0 .*lane_write_scratch_present=1 lane_write_kind=reverse lane_write_target=collapse lane_write_cs_offset=0xf080 lane_write_output=0x0000 lane_write_di=0x003c lane_write_tag=0x0004 lane_write_active_count=0x0001 lane_write_loop_index=0x0001 lane_write_result_local=0x0000 .*collapse_count=0x0003 collapse_count_base=0x663e collapse_base=0x663e .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 collapse0_forward=0x0e collapse0_reverse=0x10 .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3ec1_lane_write_trampoline_no_freeze
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3ec1_lane_write_trampoline_no_freeze.txt)
    set_tests_properties(explosion_playback_oracle_original_3ec1_lane_write_trampoline_no_freeze PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3ec1_lane_write_trampoline_no_freeze .*playback_breaks=23 observed_freeze_count=0 observed_freeze_offset=0x0000 .*observed_lane_forward_write=0 observed_lane_reverse_write=0 observed_lane_collapse_write=0 observed_lane_debris_write=0 .*lane_write_scratch_present=0 .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*collapse_count=0x0003 collapse_count_base=0x663e collapse_base=0x663e .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_3ec1_lane_write_runtime_seeded
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_3ec1_lane_write_runtime_seeded.txt)
    set_tests_properties(explosion_playback_oracle_original_3ec1_lane_write_runtime_seeded PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_3ec1_lane_write_runtime_seeded .*playback_breaks=23 observed_freeze_count=1 observed_freeze_offset=0x3ec1 .*observed_lane_forward_write=0 observed_lane_reverse_write=1 observed_lane_collapse_write=0 observed_lane_debris_write=1 .*lane_write_scratch_present=1 lane_write_kind=reverse lane_write_target=debris lane_write_cs_offset=0xf080 lane_write_output=0x0000 lane_write_di=0x0898 lane_write_tag=0x4ee8 lane_write_active_count=0x0001 lane_write_loop_index=0x0001 lane_write_result_local=0x0000 .*runtime_seeded=1 runtime_seed_kind=debris-writeback runtime_seed_direction=reverse runtime_seed_word=0xc004 runtime_seed_patch_applied=1 .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*debris0_tile_index=0x0543 debris0_flagged=0xc004 .*temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_4c96_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_4c96_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_4c96_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_4c96_runtime .*playback_breaks=13 observed_freeze_count=1 observed_freeze_offset=0x4c96 observed_high_zero_branch=0 observed_high_word_gate=0 observed_effect_forward_call=1 observed_effect_reverse_call=0 .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*debris0_tile_index=0x0541 debris0_flagged=0xc004 debris0_forward=0x3a debris0_reverse=0x00 debris0_lookup=0x67 .*collapse_count=0x0003 collapse_count_base=0x663e collapse_base=0x663e .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 .*high_debris_target_offset=0x05b9 .*high_debris_target_byte=0x00 high_debris_word_layer_value=0x0000 .*effect_base=0xc22e .*effect0_xy=0x00af,0x00b0 effect0_sprite=0x10 effect0_detail=0x10 effect0_timer=0x7d effect0_variant=0x40 temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_4ca9_runtime
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_4ca9_runtime.txt)
    set_tests_properties(explosion_playback_oracle_original_4ca9_runtime PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_4ca9_runtime .*playback_breaks=13 observed_freeze_count=1 observed_freeze_offset=0x4ca9 observed_high_zero_branch=0 observed_high_word_gate=0 observed_effect_forward_call=0 observed_effect_reverse_call=1 .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*debris0_tile_index=0x0541 debris0_flagged=0xc004 debris0_forward=0x3a debris0_reverse=0x00 debris0_lookup=0x67 .*collapse_count=0x0003 collapse_count_base=0x663e collapse_base=0x663e .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 .*high_debris_target_offset=0x05b9 .*high_debris_target_byte=0x00 high_debris_word_layer_value=0x0000 .*effect_base=0xc22e .*effect0_xy=0x00af,0x00b0 effect0_sprite=0x10 effect0_detail=0x10 effect0_timer=0x7d effect0_variant=0x40 temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_4c99_temp_copy
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_4c99_temp_copy.txt)
    set_tests_properties(explosion_playback_oracle_original_4c99_temp_copy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_4c99_temp_copy .*playback_breaks=15 observed_freeze_count=1 observed_freeze_offset=0x4c99 observed_high_zero_branch=0 observed_high_word_gate=0 observed_effect_forward_call=0 observed_effect_reverse_call=0 observed_effect_forward_return=1 observed_effect_reverse_return=0 .*bp4_local_present=0 .*lane_globals_present=1 lane_update_flag=0x00 lane_word_global_value=0x0000 lane_target_offset_global_value=0x0000 effect_input_globals_present=1 effect_forward_input_global_value=0xf7 effect_reverse_input_global_value=0xfc .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*debris0_tile_index=0x0541 debris0_flagged=0xc004 debris0_forward=0x26 debris0_reverse=0x00 debris0_lookup=0x67 .*collapse_count=0x0003 collapse_count_base=0x663e collapse_base=0x663e .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 collapse0_forward=0x00 collapse0_reverse=0x04 .*high_debris_target_offset=0x05b9 .*high_debris_target_byte=0x00 high_debris_word_layer_value=0x0000 .*effect_base=0xc22e .*effect0_xy=0x00a4,0x00b0 effect0_sprite=0x10 effect0_detail=0x10 effect0_timer=0x7d effect0_variant=0x41 temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_original_4cac_temp_copy
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_original_4cac_temp_copy.txt)
    set_tests_properties(explosion_playback_oracle_original_4cac_temp_copy PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=ok fixture=explosion_playback_oracle_original_4cac_temp_copy .*playback_breaks=15 observed_freeze_count=1 observed_freeze_offset=0x4cac observed_high_zero_branch=0 observed_high_word_gate=0 observed_effect_forward_call=0 observed_effect_reverse_call=0 observed_effect_forward_return=0 observed_effect_reverse_return=1 .*bp4_local_present=0 .*lane_globals_present=1 lane_update_flag=0x00 lane_word_global_value=0x0000 lane_target_offset_global_value=0x0000 effect_input_globals_present=1 effect_forward_input_global_value=0xf7 effect_reverse_input_global_value=0xfc .*debris_count=0x00c8 debris_count_base=0x292b debris_base=0x292b .*debris0_tile_index=0x0541 debris0_flagged=0xc004 debris0_forward=0x26 debris0_reverse=0x00 debris0_lookup=0x67 .*collapse_count=0x0003 collapse_count_base=0x663e collapse_base=0x663e .*collapse0_start=0x0a06 collapse0_end=0x0a08 collapse0_word=0x0009 collapse0_flagged=0x8009 collapse0_forward=0x00 collapse0_reverse=0x04 .*high_debris_target_offset=0x05b9 .*high_debris_target_byte=0x00 high_debris_word_layer_value=0x0000 .*effect_base=0xc22e .*effect0_xy=0x00a4,0x00b0 effect0_sprite=0x10 effect0_detail=0x10 effect0_timer=0x7d effect0_variant=0x41 temp_copy=1 visual_claim=0")

    add_test(NAME explosion_playback_oracle_bad_segment
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_bad_segment.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_bad_segment PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_bad_segment reason=dump_segment_mismatch expected=0x2b3c actual=0xffff address=2090")

    add_test(NAME explosion_playback_oracle_missing_effect_byte
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_missing_effect_byte.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_missing_effect_byte PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_missing_effect_byte reason=missing_byte address=c225")

    add_test(NAME explosion_playback_oracle_freeze_missing_break
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_freeze_missing_break.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_freeze_missing_break PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_freeze_missing_break reason=instrumented_freeze_without_observed_break")

    add_test(NAME explosion_playback_oracle_freeze_without_instrumented_flag
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_freeze_without_instrumented_flag.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_freeze_without_instrumented_flag PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_freeze_without_instrumented_flag reason=observed_break_without_instrumented_freeze")

    add_test(NAME explosion_playback_oracle_freeze_without_runtime_patch
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_freeze_without_runtime_patch.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_freeze_without_runtime_patch PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_freeze_without_runtime_patch reason=observed_break_without_runtime_patch")

    add_test(NAME explosion_playback_oracle_multiple_freeze_breaks
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_multiple_freeze_breaks.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_multiple_freeze_breaks PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_multiple_freeze_breaks reason=multiple_observed_freeze_breaks")

    add_test(NAME explosion_playback_oracle_top_freeze_without_runtime_patch
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_top_freeze_without_runtime_patch.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_top_freeze_without_runtime_patch PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_top_freeze_without_runtime_patch reason=instrumented_freeze_without_runtime_patch")

    add_test(NAME explosion_playback_oracle_bp4_local_without_word_gate
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_bp4_local_without_word_gate.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_bp4_local_without_word_gate PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_bp4_local_without_word_gate reason=bp4_local_without_word_gate_freeze")

    add_test(NAME explosion_playback_oracle_lane_div_without_divide_freeze
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_div_without_divide_freeze.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_div_without_divide_freeze PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_div_without_divide_freeze reason=lane_div_scratch_without_lane_divide_freeze")

    add_test(NAME explosion_playback_oracle_lane_write_bad_di
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-explosion-playback-oracle
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/dosbox/explosion_playback_oracle_lane_write_bad_di.txt
                --expect-error)
    set_tests_properties(explosion_playback_oracle_lane_write_bad_di PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "explosion_playback_oracle=error fixture=explosion_playback_oracle_lane_write_bad_di reason=lane_write_collapse_tag_di_mismatch")

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
            "damage_queues=ok debris_stride=11 collapse_stride=15 damaged_bit=0x8000 deferred_threshold=0x4000 collapse_flagged=0x8006 debris_flagged=0xc000 collapse_count=7 collapse_forward=2 collapse_reverse=3 debris_lookup=107 debris_forward=4 debris_reverse=5 consumer_forward=0x3bb2 consumer_reverse=0x3d46 lookup_forward=0x3a7e lookup_reverse=0x3b18 effect_update=0x45fa high_target_sample=0x4b3f high_target_byte_gate=0x4b61 high_zero_branch=0x4b6a high_nonzero_branch=0x4c20 high_word_load=0x4c64 high_word_gate=0x4c75 high_word_gate_skip=0x4cae effect_forward_call=0x4c96 effect_reverse_call=0x4ca9 effect_forward_return=0x4c99 effect_reverse_return=0x4cac effect_forward_input_global=0x78d2 effect_reverse_input_global=0x78d4 lane_target_offset_global=0x659a lane_word_global=0x655e lane_update_flag=0x2078 collapse_slot=1 collapse_weight=14 collapse_forward_write=0x6626 collapse_reverse_write=0x6627 debris_slot=1 debris_tag=0x4e21 debris_forward_write=0x20a2 debris_reverse_write=0x20a3")

    add_test(NAME lane_helper_model
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-lane-helper-model)
    set_tests_properties(lane_helper_model PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "lane_helper_model=ok helper_forward=0x3bb2 helper_reverse=0x3d46 lookup_forward=0x3a7e lookup_reverse=0x3b18 input_forward_global=0x78d2 input_reverse_global=0x78d4 ret_bytes=6 input_far_pointer_arg=bp4 weight_byte_arg=bp8 signed_input_byte=1 active_count_global=0x2078 staging_word_base=0x655c staging_word_first=0x655e staging_target_base=0x6598 staging_target_first=0x659a staging_tag_base=0x65d4 staging_tag_first=0x65d6 selector_global=0x2074 debris_count_global=0x207e collapse_count_global=0x2080 high_tag_base=0x4e20 neighbor_lane_scratch=0x661e collapse_forward_base=0x6617 collapse_reverse_base=0x6618 collapse_weight_base=0x661f collapse_forward_record_offset=6 collapse_reverse_record_offset=7 collapse_weight_record_offset=14 debris_forward_base=0x2097 debris_reverse_base=0x2098 debris_forward_record_offset=4 debris_reverse_record_offset=5 blend_far=0x0920:0x0945 writes_input_byte=1 writes_staged_tags=1 exact_arithmetic=signed_32_divide_toward_zero")

    add_test(NAME lane_blend_arithmetic
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-lane-blend-arithmetic)
    set_tests_properties(lane_blend_arithmetic PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "lane_blend_arithmetic=ok routine=0x0920:0x0945 operation=signed_32_by_32_divide dividend_reg=dx:ax divisor_reg=bx:cx quotient_reg=dx:ax quotient_byte=al remainder_reg=bx:cx quotient_rounding=toward_zero remainder_sign=dividend zero_divisor_branch=0x09ac zero_divisor_error_ax=0x00c8 lane_numerator=signed_lane_byte_times_unsigned_weight_sum lane_denominator=unsigned_weight_sum caller_forward=0x3bb2 caller_reverse=0x3d46 caller_forward_call=0x3ce3 caller_reverse_call=0x3e77 sample_neg9_div1_q=0xfff7 sample_neg9_div1_al=0xf7 sample_neg9_div2_q=0xfffc sample_neg9_div2_al=0xfc sample_pos9_div4_q=0x0002 sample_pos9_div4_al=0x02 sample_neg1_div2_q=0x0000 sample_neg1_div2_al=0x00")

    add_test(NAME bomb_object_explosion_effects
        COMMAND $<TARGET_FILE:lezac_cpp> --debug-bomb-object-explosion-effects)
    set_tests_properties(bomb_object_explosion_effects PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "bomb_object_explosion_effects=ok cases=2 .*collapse_level=1 collapse_tile=24,22 collapse_count=2 collapse_start_off=0x0a06 collapse_end_off=0x0a08 collapse_word=0x0009 collapse_flagged=0x8009 .*collapse_affected_bytes=4 .*score_each=50 sound_offset=0xea74")

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

    add_test(NAME monster_bomb_kill_live
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-monster-bomb-kill-live)
    set_tests_properties(monster_bomb_kill_live PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^monster_bomb_kill_live=ok bomb_type=4 damage=4 killed=1 removed=1 reward=1 frame_inspection=1")

    add_test(NAME player_damage_death_live
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-player-damage-death-live)
    set_tests_properties(player_damage_death_live PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^player_damage_death_live=ok first_energy=99 frames_to_life_loss=[0-9]+ lives=2 reentry_state=1 frame_inspection=1")

    add_test(NAME monster_contact_damage_live
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-monster-contact-damage-live)
    set_tests_properties(monster_contact_damage_live PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^monster_contact_damage_live=ok p1_pending=2 p2_pending=1 p1_energy=98 p2_energy=99 hurt_cue=0x002d death_cue=0x0056 state2_preserved=1 fatal_dead=1 frame_inspection=1")

    add_test(NAME object_collision_jump_live
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-object-collision-jump-live)
    set_tests_properties(object_collision_jump_live PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^object_collision_jump_live=ok support_cell=17,22 jump_vy=-[0-9]+ route_clear=1 frame_inspection=1")

    add_test(NAME hud_stats_live
        COMMAND ${CMAKE_COMMAND} -E env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
                $<TARGET_FILE:lezac_cpp> --debug-hud-stats-live)
    set_tests_properties(hud_stats_live PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        PASS_REGULAR_EXPRESSION
            "^hud_stats_live=ok hp_visible=1 lives_visible=1 bombs_visible=1 progress_visible=1 frame_inspection=1")

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
