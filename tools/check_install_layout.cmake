if(NOT DEFINED BUILD_DIR)
    message(FATAL_ERROR "BUILD_DIR is required")
endif()
if(NOT DEFINED CONFIG)
    set(CONFIG "")
endif()
if(NOT DEFINED INSTALL_DIR)
    message(FATAL_ERROR "INSTALL_DIR is required")
endif()

file(REMOVE_RECURSE "${INSTALL_DIR}")
set(install_command "${CMAKE_COMMAND}" --install "${BUILD_DIR}" --prefix "${INSTALL_DIR}")
if(NOT CONFIG STREQUAL "")
    list(APPEND install_command --config "${CONFIG}")
endif()
execute_process(
    COMMAND ${install_command}
    RESULT_VARIABLE install_result
    OUTPUT_VARIABLE install_output
    ERROR_VARIABLE install_error
)
if(NOT install_result EQUAL 0)
    message(FATAL_ERROR "cmake install failed (${install_result})\n${install_output}\n${install_error}")
endif()

set(exe_path "${INSTALL_DIR}/lezac_cpp")
if(WIN32)
    set(exe_path "${INSTALL_DIR}/lezac_cpp.exe")
endif()
if(NOT EXISTS "${exe_path}")
    message(FATAL_ERROR "installed executable missing: ${exe_path}")
endif()

set(json_resources
    BOMPAL.PAL.json
    SFONLEF.ZBG.json
    CARO.CAR.json
    BOMOMIMK.SPR.json
    PROVA.SPR.json
    FONTS.SPR.json
    RECS.DAT.json
    PROEFS.SON.json
    GRAN.MST.json
    LIVELS.SCH.json
)
set(original_resources
    BOMOMIMK.SPR
    BOMPAL.PAL
    CARO.CAR
    FONTS.SPR
    GRAN.MST
    LIVELS.SCH
    PROEFS.SON
    PROVA.SPR
    RECS.DAT
    SFONLEF.ZBG
)

set(resource_count 0)
foreach(resource IN LISTS json_resources original_resources)
    if(NOT EXISTS "${INSTALL_DIR}/${resource}")
        message(FATAL_ERROR "installed resource missing: ${resource}")
    endif()
    math(EXPR resource_count "${resource_count} + 1")
endforeach()

set(sdl2_runtime 0)
if(WIN32)
    if(NOT EXISTS "${INSTALL_DIR}/SDL2.dll")
        message(FATAL_ERROR "installed SDL2.dll missing")
    endif()
    set(sdl2_runtime 1)
endif()

execute_process(
    COMMAND "${exe_path}" --validate
    WORKING_DIRECTORY "${INSTALL_DIR}"
    RESULT_VARIABLE validate_result
    OUTPUT_VARIABLE validate_output
    ERROR_VARIABLE validate_error
)
if(NOT validate_result EQUAL 0)
    message(FATAL_ERROR "installed executable validation failed (${validate_result})\n${validate_output}\n${validate_error}")
endif()
if(NOT validate_output MATCHES "level_7=140x52 objective_tile=106 required_bonus=1 destruction=10 spawners=0 portals=2 triggers=1")
    message(FATAL_ERROR "installed executable validation output changed\n${validate_output}")
endif()

message("install_layout=ok resources=${resource_count} sdl2_runtime=${sdl2_runtime} validate=1 prefix=${INSTALL_DIR}")
