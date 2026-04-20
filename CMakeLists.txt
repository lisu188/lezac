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

    add_test(NAME sound_render COMMAND $<TARGET_FILE:lezac_cpp> --debug-sound-render)
    set_tests_properties(sound_render PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

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
