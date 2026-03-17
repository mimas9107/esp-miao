/*
 * wake_word_detector.cpp - 喚醒詞偵測主控器實作
 * ESP-MIAO v0.7.0
 */

#include "wake_word_detector.h"
#include "config.h"
#include "esp_log.h"
#include "esp_http_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ui_state.h"
#include <stdio.h>
#include <string.h>

/* Edge Impulse SDK */
#include "edge-impulse-sdk/classifier/ei_run_classifier.h"

static const char *TAG = "WakeWord";

/* static 單例（供 ei_get_data_ C-style callback 使用） */
WakeWordDetector *WakeWordDetector::instance_ = nullptr;

/* ------------------------------------------------------------------ */

WakeWordDetector::WakeWordDetector(AudioCapture       &audio,
                                   VAD                &vad,
                                   WebSocketClient    &ws,
                                   HardwareController &hw,
                                   AudioStreamer       &streamer)
    : audio_(audio), vad_(vad), ws_(ws), hw_(hw), streamer_(streamer),
      on_server_action_(nullptr)
{
    instance_ = this;
    memset(slice_buf_, 0, sizeof(slice_buf_));
}

/* ------------------------------------------------------------------ */

int WakeWordDetector::ei_get_data_(size_t offset, size_t length, float *out_ptr)
{
    if (!instance_) return -1;
    memcpy(out_ptr, instance_->slice_buf_ + offset, length * sizeof(float));
    return 0;
}

/* ------------------------------------------------------------------ */

static void send_ack_()
{
    esp_http_client_config_t cfg = {};
    cfg.url        = ACK_URL;
    cfg.method     = HTTP_METHOD_GET;
    cfg.timeout_ms = 800;

    esp_http_client_handle_t c = esp_http_client_init(&cfg);
    if (!c) { ESP_LOGE("ACK", "init failed"); return; }
    esp_err_t err = esp_http_client_perform(c);
    if (err == ESP_OK)
        ESP_LOGI("ACK", "OK status=%d", (int)esp_http_client_get_status_code(c));
    else
        ESP_LOGE("ACK", "FAILED: %s", esp_err_to_name(err));
    esp_http_client_cleanup(c);
}

/* ------------------------------------------------------------------ */

void WakeWordDetector::on_wake_word_detected_(float confidence)
{
    ESP_LOGI(TAG, ">>> WAKE WORD DETECTED! (conf=%.3f)", confidence);
    ui_publish_state(UI_WAKE);

    /* 緊急重連（若 WS 斷線） */
    if (!ws_.is_connected()) {
        ESP_LOGW(TAG, "WS down. Attempting emergency reconnect...");
        bool ok = ws_.emergency_reconnect(2000);
        ESP_LOGI(TAG, "Emergency reconnect %s", ok ? "SUCCESS" : "FAILED");
    }

    /* 提示音 */
    send_ack_();

    /* LED 閃爍 3 次 */
    ui_publish_state(UI_LISTENING);
    hw_.blink_led(3, 100, 100);

    /* 串流音訊 */
    ESP_LOGI(TAG, ">>> Starting 3-sec audio stream...");
    ui_publish_state(UI_THINKING);
    bool ok = streamer_.stream(AUDIO_SAMPLES_3S, confidence);

    if (ok)  ESP_LOGI(TAG, ">>> Stream OK");
    else     { ESP_LOGE(TAG, ">>> Stream FAILED"); ui_publish_state(UI_ERROR); }

    vTaskDelay(pdMS_TO_TICKS(500));
    ui_publish_state(UI_IDLE);
}

/* ------------------------------------------------------------------ */

void WakeWordDetector::run()
{
    printf("\r\n=== Edge Impulse Wake Word Detection ===\r\n");
    printf("Project : %s  (ID %d)\r\n",
           EI_CLASSIFIER_PROJECT_NAME, EI_CLASSIFIER_PROJECT_ID);
    printf("Window  : %d ms, Slices: %d\r\n",
           (int)(EI_CLASSIFIER_RAW_SAMPLE_COUNT * 1000 / EI_CLASSIFIER_FREQUENCY),
           EI_CLASSIFIER_SLICES_PER_MODEL_WINDOW);
    printf("Threshold: %.2f\r\n", (float)EI_CLASSIFIER_THRESHOLD);
    printf("VAD: FFT Energy Threshold = %.0f\r\n\r\n", FFT_ENERGY_THRESHOLD);

    run_classifier_init();

    printf("Warming up microphone...\r\n");
    for (int i = 0; i < 8; i++) {
        audio_.read_audio_slice(slice_buf_, EI_CLASSIFIER_SLICE_SIZE, nullptr);
    }
    printf("Started.\r\n");
    ui_publish_state(UI_IDLE);

    ei_impulse_result_t result = {};

    while (1) {
        float rms = 0.0f, fft_energy = 0.0f;

        if (!audio_.read_audio_slice(slice_buf_, EI_CLASSIFIER_SLICE_SIZE, nullptr)) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        bool vad_passed = vad_.detect(slice_buf_, EI_CLASSIFIER_SLICE_SIZE,
                                      &rms, &fft_energy);

        signal_t signal;
        signal.total_length = EI_CLASSIFIER_SLICE_SIZE;
        signal.get_data     = &WakeWordDetector::ei_get_data_;

        EI_IMPULSE_ERROR res = run_classifier_continuous(&signal, &result, false);
        if (res != EI_IMPULSE_OK) {
            printf("ERR: Inference failed (%d)\r\n", res);
            continue;
        }

        float confidence = 0.0f;
        for (uint16_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
            if (strcmp(ei_classifier_inferencing_categories[i], "heymiaomiao") == 0) {
                confidence = result.classification[i].value;

#if VAD_FFT_DEBUG
                if (confidence > 0.3f) {
                    printf("[DEBUG] Conf: %.3f RMS: %.2f FFT: %.2f(>%.0f?) Pass: %s\n",
                           confidence, rms, fft_energy, FFT_ENERGY_THRESHOLD,
                           vad_passed ? "YES" : "NO");
                }
#endif

                if (confidence >= EI_CLASSIFIER_THRESHOLD && vad_passed) {
                    vad_.record_ml_trigger();
                    on_wake_word_detected_(confidence);
                }
                break;
            }
        }
    }
}
