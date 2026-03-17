#ifndef HARDWARE_CONTROLLER_H
#define HARDWARE_CONTROLLER_H

/* ============================================================
 * hardware_controller.h - LED / GPIO 硬體控制
 * ESP-MIAO v0.7.0
 * ============================================================ */

#include "driver/gpio.h"
#include "config.h"

class HardwareController {
public:
    HardwareController();

    /** 初始化 LED GPIO */
    void init();

    /** 閃爍 LED n 次（各 on_ms/off_ms 毫秒） */
    void blink_led(int times, int on_ms = 100, int off_ms = 100);

    /** 設定 LED 狀態 */
    void set_led(bool on);
};

#endif // HARDWARE_CONTROLLER_H
