/*
 * websocket_client.cpp - WebSocket 連線管理實作
 * ESP-MIAO v0.7.0
 */

#include "websocket_client.h"
#include "config.h"
#include "esp_log.h"
#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "WebSocketClient";

WebSocketClient::WebSocketClient()
    : client_(nullptr), connected_(false), on_data_(nullptr)
{}

/* ---------- static event handler ---------- */

void WebSocketClient::event_handler_(void *arg, esp_event_base_t base,
                                     int32_t id, void *data)
{
    WebSocketClient *self = static_cast<WebSocketClient *>(arg);
    esp_websocket_event_data_t *ev = static_cast<esp_websocket_event_data_t *>(data);

    switch (id) {
        case WEBSOCKET_EVENT_CONNECTED:
            ESP_LOGI(TAG, "WEBSOCKET_EVENT_CONNECTED");
            self->connected_ = true;
            break;

        case WEBSOCKET_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "WEBSOCKET_EVENT_DISCONNECTED");
            self->connected_ = false;
            break;

        case WEBSOCKET_EVENT_DATA:
            /* op_code=1: text frame，其餘（binary=2, ping=9, pong=10 等）忽略 */
            if (ev->op_code == 1 && ev->data_len > 0 && self->on_data_) {
                char *buf = static_cast<char *>(malloc(ev->data_len + 1));
                if (buf) {
                    memcpy(buf, ev->data_ptr, ev->data_len);
                    buf[ev->data_len] = '\0';
                    self->on_data_(buf);
                    free(buf);
                }
            }
            break;

        case WEBSOCKET_EVENT_ERROR:
            ESP_LOGE(TAG, "WEBSOCKET_EVENT_ERROR: op_code=%d", ev->op_code);
            self->connected_ = false;
            break;

        default:
            break;
    }
}

/* ---------- init ---------- */

void WebSocketClient::init(const char *uri)
{
    esp_websocket_client_config_t ws_cfg = {};
    ws_cfg.uri                   = uri;
    ws_cfg.reconnect_timeout_ms  = 5000;
    ws_cfg.network_timeout_ms    = 5000;
    ws_cfg.ping_interval_sec     = 5;
    ws_cfg.disable_auto_reconnect = false;

    client_ = esp_websocket_client_init(&ws_cfg);
    esp_websocket_register_events(client_, WEBSOCKET_EVENT_ANY,
                                  &WebSocketClient::event_handler_, this);
    esp_websocket_client_start(client_);
    ESP_LOGI(TAG, "WebSocket started: %s", uri);
}

/* ---------- send ---------- */

bool WebSocketClient::send_text(const char *data, size_t len)
{
    if (!client_ || !connected_) return false;
    return esp_websocket_client_send_text(client_, data, (int)len, portMAX_DELAY) >= 0;
}

bool WebSocketClient::send_binary(const char *data, size_t len)
{
    if (!client_ || !connected_) return false;
    return esp_websocket_client_send_bin(client_, data, (int)len, portMAX_DELAY) >= 0;
}

/* ---------- emergency reconnect ---------- */

bool WebSocketClient::emergency_reconnect(uint32_t wait_ms)
{
    if (!client_) return false;
    ESP_LOGW(TAG, "Emergency reconnect...");
    esp_websocket_client_stop(client_);
    vTaskDelay(pdMS_TO_TICKS(100));
    esp_websocket_client_start(client_);

    uint32_t waited = 0;
    while (waited < wait_ms && (!connected_ || !esp_websocket_client_is_connected(client_))) {
        vTaskDelay(pdMS_TO_TICKS(100));
        waited += 100;
    }

    if (connected_ && esp_websocket_client_is_connected(client_)) {
        ESP_LOGI(TAG, "Emergency reconnect SUCCESS.");
        return true;
    }
    ESP_LOGE(TAG, "Emergency reconnect FAILED.");
    return false;
}
