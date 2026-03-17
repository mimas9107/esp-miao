#ifndef WEBSOCKET_CLIENT_H
#define WEBSOCKET_CLIENT_H

/* ============================================================
 * websocket_client.h - WebSocket 連線管理
 * ESP-MIAO v0.7.0
 * ============================================================ */

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include "esp_idf_version.h"

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
#include "esp_websocket_client.h"
#endif

/* Debug 等級控制 */
#define WS_LOG_NONE   0
#define WS_LOG_ERROR  1
#define WS_LOG_INFO   2
#define WS_LOG_DEBUG  3

#ifndef WS_LOG
#define WS_LOG WS_LOG_INFO
#endif

/**
 * 收到文字訊息時的回調（由外部模組注入）。
 * @param data  NULL-terminated 文字字串
 */
typedef void (*ws_data_callback_t)(const char *data);

class WebSocketClient {
public:
    WebSocketClient();

    /**
     * 設定收到文字訊息時的回調（需在 init() 前呼叫）。
     */
    void set_data_callback(ws_data_callback_t cb) { on_data_ = cb; }

    /**
     * 初始化並啟動 WebSocket 連線。
     * @param uri  WebSocket URI (e.g. "ws://192.168.1.16:8000/ws/esp32_01")
     */
    void init(const char *uri);

    /** 是否已連線 */
    bool is_connected() const { return connected_; }

    /**
     * 傳送文字訊息。
     * @return true = 成功
     */
    bool send_text(const char *data, size_t len);

    /**
     * 傳送二進位訊息。
     * @return true = 成功
     */
    bool send_binary(const char *data, size_t len);

    /**
     * 緊急重連（喚醒詞偵測到但 WS 斷線時使用）。
     * @param wait_ms 最多等待毫秒數
     * @return true = 重連成功
     */
    bool emergency_reconnect(uint32_t wait_ms = 2000);

    /** 取得原始 handle（供 stream_audio_realtime 暫時使用） */
    esp_websocket_client_handle_t handle() const { return client_; }

private:
    esp_websocket_client_handle_t client_;
    bool                          connected_;
    ws_data_callback_t            on_data_;

    static void event_handler_(void *arg, esp_event_base_t base,
                               int32_t id, void *data);
};

#endif // WEBSOCKET_CLIENT_H
