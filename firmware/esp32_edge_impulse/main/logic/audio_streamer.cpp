/*
 * audio_streamer.cpp - 實時二進位音訊串流實作
 * ESP-MIAO v0.7.0
 */

#include "audio_streamer.h"
#include "config.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *TAG = "AudioStreamer";

AudioStreamer::AudioStreamer(WebSocketClient &ws, AudioCapture &audio, TimeManager &timemgr)
    : ws_(ws), audio_(audio), timemgr_(timemgr)
{}

bool AudioStreamer::stream(size_t total_samples, float confidence)
{
    if (!ws_.is_connected()) {
        ESP_LOGE(TAG, "WebSocket not connected, cannot stream");
        return false;
    }

    /* 1. 發送 audio_start JSON */
    char start_json[256];
    snprintf(start_json, sizeof(start_json),
             "{\"device_id\":\"%s\",\"timestamp\":%llu,\"type\":\"audio_start\","
             "\"payload\":{\"total_samples\":%zu,\"confidence\":%.3f,"
             "\"transfer_mode\":\"binary\"}}",
             DEVICE_ID, (unsigned long long)timemgr_.get_timestamp_ms(),
             total_samples, confidence);

    if (!ws_.send_text(start_json, strlen(start_json))) {
        ESP_LOGE(TAG, "Failed to send audio_start");
        return false;
    }

    /* 2. 分塊串流 PCM */
    const size_t CHUNK = STREAM_CHUNK_SAMPLES;
    int16_t *buf = (int16_t *)malloc(CHUNK * sizeof(int16_t));
    if (!buf) {
        ESP_LOGE(TAG, "OOM: cannot allocate chunk buffer");
        return false;
    }

    size_t sent = 0;
    bool   ok   = true;

    while (sent < total_samples) {
        size_t to_read = total_samples - sent;
        if (to_read > CHUNK) to_read = CHUNK;

        if (audio_.read_audio_to_buffer(buf, to_read)) {
            if (!ws_.send_binary((const char *)buf, to_read * sizeof(int16_t))) {
                ESP_LOGE(TAG, "Binary send failed at sample %zu", sent);
                ok = false;
                break;
            }
            sent += to_read;
        } else {
            ESP_LOGE(TAG, "I2S read failed during streaming");
            ok = false;
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(2)); // 讓 TCP stack 喘氣
    }

    free(buf);
    if (ok) ESP_LOGI(TAG, "Streamed %zu samples OK", sent);
    return ok;
}
