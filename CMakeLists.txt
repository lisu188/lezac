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

include(CTest)

if(BUILD_TESTING)
    add_test(NAME validate_assets COMMAND $<TARGET_FILE:lezac_cpp> --validate)
    set_tests_properties(validate_assets PROPERTIES
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

    add_test(NAME sound_render COMMAND $<TARGET_FILE:lezac_cpp> --debug-sound-render)
    set_tests_properties(sound_render PROPERTIES
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

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
