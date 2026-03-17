cmake_minimum_required(VERSION 3.13.1)

set(MODEL_FOLDER ..)
set(EI_SDK_FOLDER ../edge-impulse-sdk)

if(NOT CMAKE_BUILD_EARLY_EXPANSION)
    add_definitions(-DEI_CLASSIFIER_TFLITE_ENABLE_ESP_NN=1)
    add_definitions(-DEIDSP_USE_ESP_DSP=1)
    if(${IDF_TARGET} STREQUAL "esp32s3")
        add_definitions(-DEI_CLASSIFIER_TFLITE_ENABLE_ESP_NN_S3=1)
    endif()
endif()

OPTION(DEFINE_DEBUG
    "Build the project using debugging code"
    OFF)
IF(DEFINE_DEBUG)
    MESSAGE("Adding Debug flag...")
    ADD_DEFINITIONS(-DDEBUG)
    SET(CMAKE_BUILD_TYPE Debug)
    MESSAGE("Build type is " ${CMAKE_BUILD_TYPE})
ENDIF(DEFINE_DEBUG)

set(include_dirs
    ${MODEL_FOLDER}
    ${MODEL_FOLDER}/tflite-model
    ${MODEL_FOLDER}/model-parameters
    ${EI_SDK_FOLDER}
    ${EI_SDK_FOLDER}/porting/espressif/esp-dsp/modules/fft/include
    ${EI_SDK_FOLDER}/porting/espressif/esp-dsp/modules/common/include
    # v0.7.0 模組化子資料夾（Phase 1-4）
    ${CMAKE_CURRENT_SOURCE_DIR}/config
    ${CMAKE_CURRENT_SOURCE_DIR}/time
    ${CMAKE_CURRENT_SOURCE_DIR}/audio
    ${CMAKE_CURRENT_SOURCE_DIR}/network
    ${CMAKE_CURRENT_SOURCE_DIR}/logic
)

include(${EI_SDK_FOLDER}/cmake/utils.cmake)

RECURSIVE_FIND_FILE_EXCLUDE_DIR(SOURCE_FILES "../edge-impulse-sdk" "CMSIS" "*.cpp")
RECURSIVE_FIND_FILE_EXCLUDE_DIR(MODEL_FILES "../tflite-model" "CMSIS" "*.cpp")
RECURSIVE_FIND_FILE_EXCLUDE_DIR(CC_FILES "../edge-impulse-sdk" "CMSIS" "*.cc")
RECURSIVE_FIND_FILE_EXCLUDE_DIR(C_FILES "../edge-impulse-sdk" "CMSIS" "*.c")

RECURSIVE_FIND_FILE_EXCLUDE_DIR(S_FILES_ESP_NN "${EI_SDK_FOLDER}/porting/espressif/ESP-NN" "CMSIS" "*.s")
RECURSIVE_FIND_FILE_EXCLUDE_DIR(S_FILES_ESP_DSP "${EI_SDK_FOLDER}/porting/espressif/esp-dsp/modules/fft" "CMSIS" "*.s")

list(APPEND SOURCE_FILES ${C_FILES})
list(APPEND SOURCE_FILES ${CC_FILES})
list(APPEND SOURCE_FILES ${MODEL_FILES})
list(APPEND SOURCE_FILES ${S_FILES_ESP_NN})
list(APPEND SOURCE_FILES ${S_FILES_ESP_DSP})

# v0.7.0 模組化來源檔（Phase 1-4）
set(MODULE_SRCS
    config/config.cpp
    time/time_manager.cpp
    audio/audio_capture.cpp
    audio/vad.cpp
    network/wifi_manager.cpp
    network/websocket_client.cpp
    logic/hardware_controller.cpp
    logic/audio_streamer.cpp
    logic/wake_word_detector.cpp
)

idf_component_register(SRCS "main.cpp" "${SOURCE_FILES}" "${MODULE_SRCS}"
                       INCLUDE_DIRS "${include_dirs}"
                       REQUIRES esp_http_client esp_websocket_client esp_wifi esp_event nvs_flash esp_netif driver esp_timer esp_system esp_common json eye_ui ui_state TFT_eSPI)

target_compile_options(${COMPONENT_LIB} PRIVATE -std=gnu++17)
