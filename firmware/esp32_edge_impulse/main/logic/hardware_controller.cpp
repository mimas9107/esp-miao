/*
 * hardware_controller.cpp - LED / GPIO 硬體控制實作
 * ESP-MIAO v0.7.0
 */

#include "hardware_controller.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_idf_version.h"

static const char *TAG = "HW";

HardwareController::HardwareController() {}

void HardwareController::init()
{
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
    esp_rom_gpio_pad_select_gpio(LED_PIN);
#elif ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(4, 0, 0)
    gpio_pad_select_gpio(LED_PIN);
#endif
    gpio_set_direction(LED_PIN, GPIO_MODE_OUTPUT);
    gpio_set_level(LED_PIN, 0);
    ESP_LOGI(TAG, "LED init on GPIO %d", (int)LED_PIN);
}

void HardwareController::set_led(bool on)
{
    gpio_set_level(LED_PIN, on ? 1 : 0);
}

void HardwareController::blink_led(int times, int on_ms, int off_ms)
{
    for (int i = 0; i < times; i++) {
        set_led(true);
        vTaskDelay(pdMS_TO_TICKS(on_ms));
        set_led(false);
        vTaskDelay(pdMS_TO_TICKS(off_ms));
    }
}
