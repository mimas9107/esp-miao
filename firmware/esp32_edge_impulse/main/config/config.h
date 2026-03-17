#ifndef CONFIG_H
#define CONFIG_H

/* ============================================================
 * config.h - 系統全域配置與 Debug 等級定義
 * ESP-MIAO v0.7.0
 * ============================================================ */

/* ---------- Debug 等級定義 ---------- */

#define LOG_LEVEL_NONE   0
#define LOG_LEVEL_ERROR  1
#define LOG_LEVEL_INFO   2
#define LOG_LEVEL_DEBUG  3

/* 各模組可於編譯時個別覆寫（在 CMakeLists.txt 或此處設定） */
#ifndef CONFIG_LOG_LEVEL
#define CONFIG_LOG_LEVEL LOG_LEVEL_INFO
#endif

/* ---------- 伺服器網路配置 ---------- */

#define SERVER_URL  "ws://192.168.1.16:8000/ws/esp32_01"
#define ACK_URL     "http://192.168.1.16:8000/ack"

/* ---------- 時區 ---------- */

#define TZ_OFFSET   (8 * 3600)   // UTC+8

/* ---------- GPIO 腳位定義 ---------- */

#define LED_PIN         GPIO_NUM_2

#define I2S_BCK_GPIO    GPIO_NUM_32
#define I2S_WS_GPIO     GPIO_NUM_25
#define I2S_DIN_GPIO    GPIO_NUM_33

// ST7735 TFT Display Power (GPIO4)
#define DISPLAY_EN_PIN  4

/* ---------- I2S 音訊配置 ---------- */

#define SAMPLE_RATE     16000
#define I2S_PORT_NUM    I2S_NUM_0
#define DMA_BUF_COUNT   8
#define DMA_BUF_LEN     256

/* ---------- 錄音配置 ---------- */

#define RECORD_DURATION_SEC  3
#define AUDIO_SAMPLES_3S     (SAMPLE_RATE * RECORD_DURATION_SEC)
// 2KB chunk: 1024 samples x 2 bytes
#define STREAM_CHUNK_SAMPLES 1024

/* ---------- VAD (FFT) 參數 ---------- */

#define FFT_SIZE              512
#define FFT_FREQ_MIN          300       // 人聲最低頻率 (Hz)
#define FFT_FREQ_MAX          3400      // 人聲最高頻率 (Hz)
#define FFT_ENERGY_THRESHOLD  25000.0f  // 閾值 (根據 2026-03-03 測試建議)
#define FFT_GAIN              1.0f      // 增益因子

#define VAD_FFT_DEBUG         0         // 1=開啟 VAD 統計 Debug 日誌

#define PRINT_STATS_INTERVAL  30        // 每多少幀打印一次統計

/* ---------- Wake Word 配置 ---------- */

#define USE_BINARY_STREAM     1         // 固定使用 Binary 串流模式

/* ---------- WiFi 設備 ID ---------- */

#define DEVICE_ID   "esp32_01"

#endif // CONFIG_H
