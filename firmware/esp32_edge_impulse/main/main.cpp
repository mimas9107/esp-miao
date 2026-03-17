/*
 * main.cpp - ESP-MIAO v0.7.0 主入口
 *
 * Hardware: ESP32 DevKit V1 + INMP441
 * Model:    esp-miao-mfcc (heymiaomiao / noise / unknown)
 *
 * 架構：物件導向模組化（Phase 1-4 完成）
 *   Config / TimeManager / AudioCapture / VAD /
 *   WifiManager / WebSocketClient /
 *   HardwareController / AudioStreamer / WakeWordDetector
 */

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "sdkconfig.h"
#include "cJSON.h"

#include "Arduino.h"
#include "eye_ui.h"
#include "ui_state.h"

/* ---------- v0.7.0 模組引入 ---------- */
#include "config.h"
#include "time_manager.h"
#include "audio_capture.h"
#include "vad.h"
#include "wifi_manager.h"
#include "websocket_client.h"
#include "hardware_controller.h"
#include "audio_streamer.h"
#include "wake_word_detector.h"

static const char *TAG = "ESP-MIAO";

/* ---------- 全域物件 ---------- */
static TimeManager         g_time_mgr;
static AudioCapture        g_audio;
static VAD                 g_vad;
static WifiManager         g_wifi;
static WebSocketClient     g_ws;
static HardwareController  g_hw;
static AudioStreamer        g_streamer(g_ws, g_audio, g_time_mgr);
static WakeWordDetector    *g_detector = nullptr;

/* ---------- 伺服器動作處理 ---------- */
static void handle_server_action(const char *json_str)
{
    if (!json_str) return;
    ESP_LOGI(TAG, "Server action: %s", json_str);

    cJSON *root = cJSON_Parse(json_str);
    if (!root) { ESP_LOGW(TAG, "Invalid JSON"); return; }

    cJSON *action = cJSON_GetObjectItem(root, "action");
    if (cJSON_IsString(action) && action->valuestring) {
        ESP_LOGI(TAG, "Action: %s", action->valuestring);
    }
    cJSON_Delete(root);
}

/* ---------- 推論 Task wrapper ---------- */
static void inference_task(void *arg)
{
    auto *det = static_cast<WakeWordDetector *>(arg);
    det->run(); // 不返回
}

/* ---------- app_main ---------- */
extern "C" int app_main()
{
    initArduino();

    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    /* UI */
    ui_state_init();
    eye_ui_start();

    /* Display power (GPIO4) */
    gpio_reset_pin((gpio_num_t)DISPLAY_EN_PIN);
    gpio_set_direction((gpio_num_t)DISPLAY_EN_PIN, GPIO_MODE_OUTPUT);
    gpio_set_level((gpio_num_t)DISPLAY_EN_PIN, 0);

    /* 硬體 / 網路初始化 */
    g_hw.init();
    g_wifi.init();
    g_time_mgr.init();

    g_ws.set_data_callback(handle_server_action);
    g_ws.init(SERVER_URL);

    g_audio.init();

    /* 建立 WakeWordDetector */
    static WakeWordDetector detector(g_audio, g_vad, g_ws, g_hw, g_streamer);
    g_detector = &detector;

    xTaskCreate(inference_task, "ei_infer", 16384, g_detector, 5, NULL);
    return 0;
}
