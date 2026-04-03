#include "eye_ui.h"

#include "Arduino.h"
#include <SPI.h>
#include <TFT_eSPI.h>

#include "esp_heap_caps.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ui_state.h"

// ── Display power control ────────────────────────────────────────────────
#define DISPLAY_EN_PIN   GPIO_NUM_4   // GPIO to control display power
static bool display_is_on = false;

// ── TFT & Sprite instance ─────────────────────────────────────────────────────
static TFT_eSPI tft = TFT_eSPI();
static TFT_eSprite spr = TFT_eSprite(&tft);

// ── Display power control functions ────────────────────────────────────────
static void display_power_on(void) {
    gpio_set_direction((gpio_num_t)DISPLAY_EN_PIN, GPIO_MODE_OUTPUT);
    gpio_set_level((gpio_num_t)DISPLAY_EN_PIN, 1);
    vTaskDelay(pdMS_TO_TICKS(10));
    tft.init();
    tft.setRotation(0);
    display_is_on = true;
    ESP_LOGI("UI", "Display Powered ON");
}

static void display_power_off(void) {
    tft.writecommand(ST7735_SLPIN);
    gpio_set_level((gpio_num_t)DISPLAY_EN_PIN, 0);
    display_is_on = false;
    ESP_LOGI("UI", "Display Powered OFF");
}

// ── UI config ───────────────────────────────────────────────────────────────
#define UI_TEST_MODE 0
#define UI_TEST_STEP_MS 5000
#define UI_IDLE_FPS 20
#define UI_LOG_FPS 0
static const char *TAG_UI = "UI";

#define RGB(r, g, b) (((r & 0xF8) << 8) | ((g & 0xFC) << 3) | ((b) >> 3))
#define PINK RGB(255, 100, 180)

// ── Animation state variables ────────────────────────────────────────────────
static uint32_t anim_start_ms = 0;

static void anim_reset(void) {
    anim_start_ms = millis();
}

static void ui_log_metrics(ui_state_t state) {
    uint32_t free_heap = heap_caps_get_free_size(MALLOC_CAP_8BIT);
    ESP_LOGI(TAG_UI, "State=%d free_heap=%u", (int)state, (unsigned)free_heap);
}

static void ui_apply_state(ui_state_t state) {
    anim_reset();
    ui_log_metrics(state);
}

static uint32_t ui_state_timeout_ms(ui_state_t state) {
    switch (state) {
        case UI_ACTION:
        case UI_ERROR:
        case UI_WAKE:
            return 2000;
        case UI_LISTENING:
            return 5000;
        case UI_THINKING:
            return 8000;
        case UI_SLEEPING:
            return 6000; // 稍長於 5 秒動畫，確保動畫播完
        default:
            return 0;
    }
}

// ── Cat Drawing Primitives (Using Sprite) ───────────────────────────

static void fillEllipse(int cx, int cy, int rx, int ry, uint16_t color) {
    for (int y = -ry; y <= ry; y++) {
        float dy = (float)y / (float)ry;
        float dx = sqrtf(1.0f - dy * dy);
        int x_width = (int)(rx * dx);
        spr.drawFastHLine(cx - x_width, cy + y, x_width * 2 + 1, color);
    }
}

static void drawZ(int x, int y, int size, uint16_t color) {
    spr.drawFastHLine(x, y, size, color);
    for (int i = 0; i < size; i++) {
        spr.drawPixel(x + size - i, y + i, color);
    }
    spr.drawFastHLine(x, y + size, size, color);
}

static void drawThickOmega(int cx, int cy, uint16_t color) {
    int rad = 12;
    for (float a = 0; a < (float)M_PI; a += 0.1f) {
        int lx = cx - rad + (int)(cosf(a) * rad);
        int rx = cx + rad - (int)(cosf(a) * rad);
        int y_pos = cy + (int)(sinf(a) * rad);
        spr.fillRect(lx, y_pos, 2, 2, color);
        spr.fillRect(rx, y_pos, 2, 2, color);
    }
}

static void drawCatFaceBase(int frame, bool isSleeping, uint16_t color = TFT_WHITE) {
    float l_tip_x, l_tip_y, r_tip_x, r_tip_y;
    if (!isSleeping) {
        bool jitter = (frame % 40 > 30);
        l_tip_x = jitter ? 5.0f : 15.0f;
        l_tip_y = 5.0f;
        r_tip_x = jitter ? 123.0f : 113.0f;
        r_tip_y = 5.0f;
    } else {
        int slowCycle = frame % 240;
        l_tip_x = (slowCycle > 20 && slowCycle < 50) ? 2.0f : 8.0f;
        l_tip_y = 25.0f;
        r_tip_x = (slowCycle > 140 && slowCycle < 170) ? 126.0f : 120.0f;
        r_tip_y = 25.0f;
    }
    spr.fillTriangle(10, 32, 45, 32, (int)l_tip_x, (int)l_tip_y, color);
    spr.fillTriangle(83, 32, 118, 32, (int)r_tip_x, (int)r_tip_y, color);
    drawThickOmega(64, 120, color);
    fillEllipse(64, 118, 6, 4, PINK);
}

static void idle_anim_step(void) {
    uint32_t frame = millis() / 50;
    drawCatFaceBase(frame, false);
    if (frame % 100 < 95) {
        fillEllipse(40, 80, 12, 18, TFT_WHITE);
        fillEllipse(88, 80, 12, 18, TFT_WHITE);
    } else {
        spr.fillRect(28, 78, 24, 4, TFT_WHITE);
        spr.fillRect(76, 78, 24, 4, TFT_WHITE);
    }
}

static void thinking_anim_step(void) {
    uint32_t frame = millis() / 50;
    drawCatFaceBase(frame, false);
    for (float a = (float)M_PI; a < 2.0f * (float)M_PI; a += 0.2f) {
        int lx = 40 + (int)(cosf(a) * 15);
        int ly = 85 + (int)(sinf(a) * 10);
        int rx = 88 + (int)(cosf(a) * 15);
        int ry = 85 + (int)(sinf(a) * 10);
        spr.fillRect(lx, ly, 3, 3, TFT_WHITE);
        spr.fillRect(rx, ry, 3, 3, TFT_WHITE);
    }
}

static void listening_anim_step(void) {
    uint32_t frame = millis() / 50;
    drawCatFaceBase(frame, false);
    int ox = (rand() % 5) - 2;
    int oy = (rand() % 5) - 2;
    fillEllipse(40 + ox, 80 + oy, 8, 8, TFT_WHITE);
    fillEllipse(88 - ox, 80 - oy, 8, 8, TFT_WHITE);
}

static void sleep_anim_step(void) {
    uint32_t frame = millis() / 50;
    drawCatFaceBase(frame, true);
    for (float a = 0; a < (float)M_PI; a += 0.2f) {
        int lx = 40 + (int)(cosf(a) * 15);
        int ly = 80 + (int)(sinf(a) * 5);
        int rx = 88 + (int)(cosf(a) * 15);
        int ry = 80 + (int)(sinf(a) * 5);
        spr.fillRect(lx, ly, 3, 3, TFT_WHITE);
        spr.fillRect(rx, ry, 3, 3, TFT_WHITE);
    }
    int cycle = frame % 120;
    drawZ(100, 50 - (cycle / 3), 8, TFT_WHITE);
    if (cycle > 40) drawZ(110, 40 - ((cycle - 40) / 3), 5, TFT_WHITE);
    if (cycle > 80) drawZ(115, 30 - ((cycle - 80) / 3), 3, TFT_WHITE);
}

static void action_anim_step(void) {
    thinking_anim_step();
}

static void error_anim_step(void) {
    uint32_t frame = millis() / 50;
    drawCatFaceBase(frame, false, RGB(255, 40, 40));
    int ox = (rand() % 5) - 2;
    int oy = (rand() % 5) - 2;
    fillEllipse(40 + ox, 80 + oy, 8, 8, RGB(255, 40, 40));
    fillEllipse(88 - ox, 80 - oy, 8, 8, RGB(255, 40, 40));
}

// ── Arduino setup / loop ─────────────────────────────────────────────────────
static void setup_ui(void) {
    tft.init();
    tft.setRotation(0);
    tft.fillScreen(ST7735_BLACK);
    
    spr.setColorDepth(16);
    if (spr.createSprite(128, 160) == NULL) {
        ESP_LOGE(TAG_UI, "Failed to create sprite!");
    }
}

static void loop_ui(ui_state_t state) {
    spr.fillSprite(ST7735_BLACK);
    switch (state) {
        case UI_IDLE:      idle_anim_step(); break;
        case UI_WAKE:      idle_anim_step(); break;
        case UI_LISTENING: listening_anim_step(); break;
        case UI_THINKING:  thinking_anim_step(); break;
        case UI_ACTION:    action_anim_step(); break;
        case UI_ERROR:     error_anim_step(); break;
        case UI_SLEEPING:  sleep_anim_step(); break;
        default:           break;
    }
    spr.pushSprite(0, 0);
}

// ── Display task ─────────────────────────────────────────────────────────────
static void display_task(void *arg) {
    (void)arg;
    setup_ui();
    anim_reset();

    ui_state_t current_state = UI_IDLE;
    ui_apply_state(current_state);
    uint32_t state_enter_ms = (uint32_t)millis();
    uint32_t last_activity_ms = state_enter_ms;

    const TickType_t frame_ticks = pdMS_TO_TICKS(1000 / UI_IDLE_FPS);
    TickType_t last_wake = xTaskGetTickCount();
    ui_event_t ev;
    
    const uint32_t IDLE_TIMEOUT_MS = 30000;

    while (true) {
        if (ui_pop_state(&ev, 0)) {
            current_state = ev.state;
            ui_apply_state(current_state);
            state_enter_ms = (uint32_t)millis();
            last_activity_ms = state_enter_ms;
            
            // 重要：任何新狀態事件都要點亮螢幕
            if (!display_is_on) {
                display_power_on();
            }
        }

        // 執行動畫 (只有螢幕亮著才繪製)
        if (display_is_on) {
            loop_ui(current_state);
        }

        // 狀態自動回歸邏輯
        if (current_state != UI_IDLE) {
            uint32_t timeout_ms = ui_state_timeout_ms(current_state);
            if (timeout_ms > 0 && ((uint32_t)millis() - state_enter_ms) >= timeout_ms) {
                current_state = UI_IDLE;
                ui_apply_state(current_state);
                last_activity_ms = (uint32_t)millis();
            }
        }

        // SLEEPING 專屬邏輯：延遲關閉螢幕
        if (current_state == UI_SLEEPING && display_is_on) {
            if ((uint32_t)millis() - state_enter_ms >= 5000) {
                display_power_off();
            }
        }

        // IDLE 省電邏輯：超時後切換到 SLEEPING 狀態以顯示動畫，而不是直接關閉
        if (current_state == UI_IDLE && display_is_on) {
            if ((uint32_t)millis() - last_activity_ms >= IDLE_TIMEOUT_MS) {
                ESP_LOGI(TAG_UI, "IDLE timeout, transitioning to SLEEPING animation");
                current_state = UI_SLEEPING;
                ui_apply_state(current_state);
                state_enter_ms = (uint32_t)millis(); // 重置時間以開始 5 秒動畫計時
            }
        }

        vTaskDelayUntil(&last_wake, frame_ticks);
    }
}

void eye_ui_start(void) {
    static bool started = false;
    if (started) return;
    started = true;
    ui_state_init();
    ui_publish_state(UI_IDLE);
    xTaskCreatePinnedToCore(display_task, "display", 8192, NULL, 2, NULL, 1);
}
