#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

/* ============================================================
 * wifi_manager.h - WiFi 連線管理（NVS 憑證 + 事件處理）
 * ESP-MIAO v0.7.0
 * ============================================================ */

#include "esp_err.h"
#include "esp_event.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

/* Debug 等級控制 */
#define WIFI_LOG_NONE   0
#define WIFI_LOG_ERROR  1
#define WIFI_LOG_INFO   2
#define WIFI_LOG_DEBUG  3

#ifndef WIFI_LOG
#define WIFI_LOG WIFI_LOG_INFO
#endif

class WifiManager {
public:
    WifiManager();

    /**
     * 初始化 WiFi（讀取 NVS 憑證 → 連線 → 阻塞等待取得 IP）。
     * 需在 nvs_flash_init() 之後呼叫。
     */
    void init();

    /** 是否已取得 IP（已連線） */
    bool is_connected() const;

    /**
     * 儲存 WiFi 憑證至 NVS（供未來使用）。
     */
    esp_err_t save_credentials(const char *ssid, const char *password);

private:
    EventGroupHandle_t event_group_;
    bool               connected_;

    char ssid_[32];
    char password_[64];

    /* NVS partition name */
    static constexpr const char *NVS_NS = "storage";

    esp_err_t load_credentials_();

    static void event_handler_(void *arg, esp_event_base_t base,
                               int32_t id, void *data);
};

#endif // WIFI_MANAGER_H
