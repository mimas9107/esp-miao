/*
 * wifi_manager.cpp - WiFi 連線管理實作
 * ESP-MIAO v0.7.0
 */

#include "wifi_manager.h"
#include "config.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "sdkconfig.h"
#include <string.h>

static const char *TAG = "WifiManager";

WifiManager::WifiManager()
    : event_group_(nullptr), connected_(false)
{
    ssid_[0]     = '\0';
    password_[0] = '\0';
}

/* ---------- static event handler ---------- */

void WifiManager::event_handler_(void *arg, esp_event_base_t base,
                                 int32_t id, void *data)
{
    WifiManager *self = static_cast<WifiManager *>(arg);

    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();

    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        esp_wifi_connect();
        xEventGroupClearBits(self->event_group_, BIT0);
        ESP_LOGI(TAG, "retry to connect to the AP");

    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = static_cast<ip_event_got_ip_t *>(data);
        ESP_LOGI(TAG, "got ip:" IPSTR, IP2STR(&event->ip_info.ip));
        self->connected_ = true;
        xEventGroupSetBits(self->event_group_, BIT0);
    }
}

/* ---------- NVS 憑證讀取 ---------- */

esp_err_t WifiManager::load_credentials_()
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(NVS_NS, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Error opening NVS: %s", esp_err_to_name(err));
        return err;
    }

    size_t ssid_len = sizeof(ssid_);
    size_t pass_len = sizeof(password_);
    bool   use_defaults = false;

    err = nvs_get_str(handle, "wifi_ssid", ssid_, &ssid_len);
    if (err == ESP_ERR_NVS_NOT_FOUND) use_defaults = true;
    else if (err != ESP_OK) { nvs_close(handle); return err; }

    err = nvs_get_str(handle, "wifi_pass", password_, &pass_len);
    if (err == ESP_ERR_NVS_NOT_FOUND) use_defaults = true;
    else if (err != ESP_OK) { nvs_close(handle); return err; }

    if (use_defaults) {
        ESP_LOGI(TAG, "Credentials not found in NVS. Using Kconfig defaults.");
        strncpy(ssid_,     CONFIG_ESP_MIAO_WIFI_SSID,     sizeof(ssid_) - 1);
        strncpy(password_, CONFIG_ESP_MIAO_WIFI_PASSWORD,  sizeof(password_) - 1);
        ssid_[sizeof(ssid_) - 1]         = '\0';
        password_[sizeof(password_) - 1] = '\0';

        nvs_set_str(handle, "wifi_ssid", ssid_);
        nvs_set_str(handle, "wifi_pass", password_);
        nvs_commit(handle);
        ESP_LOGI(TAG, "Kconfig defaults saved to NVS.");
    } else {
        ESP_LOGI(TAG, "Credentials loaded from NVS.");
    }

    nvs_close(handle);
    return ESP_OK;
}

/* ---------- 儲存憑證 ---------- */

esp_err_t WifiManager::save_credentials(const char *ssid, const char *password)
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(NVS_NS, NVS_READWRITE, &handle);
    if (err != ESP_OK) return err;

    err = nvs_set_str(handle, "wifi_ssid", ssid);
    if (err != ESP_OK) { nvs_close(handle); return err; }
    err = nvs_set_str(handle, "wifi_pass", password);
    if (err != ESP_OK) { nvs_close(handle); return err; }
    err = nvs_commit(handle);
    nvs_close(handle);
    ESP_LOGI(TAG, "Credentials saved to NVS.");
    return err;
}

/* ---------- 主初始化 ---------- */

void WifiManager::init()
{
    event_group_ = xEventGroupCreate();

    ESP_ERROR_CHECK(load_credentials_());

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t inst_any, inst_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &WifiManager::event_handler_, this, &inst_any));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, &WifiManager::event_handler_, this, &inst_got_ip));

    wifi_config_t wifi_config = {};
    strncpy((char *)wifi_config.sta.ssid,     ssid_,     sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password, password_, sizeof(wifi_config.sta.password) - 1);

    ESP_LOGI(TAG, "Connecting to SSID: %s", ssid_);
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    xEventGroupWaitBits(event_group_, BIT0, pdFALSE, pdFALSE, portMAX_DELAY);
    ESP_LOGI(TAG, "WiFi connected.");
}

bool WifiManager::is_connected() const
{
    return connected_;
}
