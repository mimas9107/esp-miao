/*
 * time_manager.cpp - NTP 時間同步管理實作
 * ESP-MIAO v0.7.0
 */

#include "time_manager.h"
#include "esp_log.h"
#include "esp_sntp.h"
#include <time.h>
#include <sys/time.h>

static const char *TAG = "TimeManager";

void TimeManager::init(int max_retry)
{
    ESP_LOGI(TAG, "Initializing SNTP...");
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_setservername(1, "time.google.com");
    esp_sntp_init();

    // 設定時區 Taipei (UTC+8)
    setenv("TZ", "CST-8", 1);
    tzset();

    // 等待時間同步
    int retry = 0;
    while (sntp_get_sync_status() == SNTP_SYNC_STATUS_RESET && ++retry < max_retry) {
        ESP_LOGI(TAG, "Waiting for system time to be set... (%d/%d)", retry, max_retry);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }

    time_t now;
    struct tm timeinfo;
    time(&now);
    localtime_r(&now, &timeinfo);

#if TIME_LOG >= TIME_LOG_LEVEL_INFO
    ESP_LOGI(TAG, "Time synchronized: %d-%02d-%02d %02d:%02d:%02d",
             timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
             timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
#endif
}

uint64_t TimeManager::get_timestamp_ms() const
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (uint64_t)tv.tv_sec * 1000 + (tv.tv_usec / 1000);
}

void TimeManager::sync_from_server(long seconds, int ms)
{
    struct timeval tv = {
        .tv_sec  = (time_t)seconds,
        .tv_usec = (suseconds_t)(ms * 1000)
    };
    settimeofday(&tv, NULL);

    struct tm timeinfo;
    localtime_r(&tv.tv_sec, &timeinfo);
    ESP_LOGI(TAG, "RTC synchronized via Server: %d-%02d-%02d %02d:%02d:%02d",
             timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
             timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
}
