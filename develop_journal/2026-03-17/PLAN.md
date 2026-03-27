# 重構計畫：ESP32 韌體 main.cpp 物件導向化

> 日期：2026-03-17
> 版本：v0.6.6 → v0.7.0

## 目標

將 `main.cpp`（948 行）重構為物件導向模組化架構，提升可維護性與可擴充性。

## 重構原則

1. **逐步替換**：保留原 C 風格函數作為 wrapper，確保向後相容
2. **條件編譯**：各模組提供 Debug 等級控制（如 `LOG_LEVEL`、`UI_LOG_FPS`）
3. **每 Phase 編譯測試**：確保功能正常後才進入下一階段

## Phase 1：基礎設施

### 1.1 Config（系統配置）
- GPIO 腳位定義（I2S、TFT、LED）
- I2S 參數（SAMPLE_RATE、DMA_buf）
- VAD 參數（FFT_SIZE、閾值）
- 伺服器 URL（WebSocket、ACK）
- 錄音參數（3秒、緩衝區大小）
- **Debug 等級**：`CONFIG_LOG_LEVEL`

### 1.2 TimeManager（時間管理）
- NTP 初始化
- `get_timestamp_ms()`
- 時區設定（UTC+8）
- **Debug 等級**：`TIME_LOG`

## Phase 2：硬體抽象

### 2.1 AudioCapture（音訊擷取）
- I2S 初始化
- `read_audio_slice()` - 推論用 float 資料
- `read_audio_to_buffer()` - 串流用 int16_t 資料
- Stereo → Mono 轉換
- **Debug 等級**：`AUDIO_LOG`

### 2.2 VAD（語音偵測）
- FFT Twiddle Factor 初始化
- `vad_detect()` - 主偵測介面
- 統計數據（fft_triggers、ml_triggered）
- **Debug 等級**：`VAD_LOG`

## Phase 3：網路

### 3.1 WifiManager（WiFi 管理）
- NVS 憑證讀寫
- WiFi 連線/斷線事件處理
- 連線狀態查詢
- **Debug 等級**：`WIFI_LOG`

### 3.2 WebSocketClient（WebSocket 管理）
- 連線/斷線事件處理
- `send_text()` / `send_binary()`
- 接收指令回調註冊
- **Debug 等級**：`WS_LOG`

## Phase 4：邏輯層

### 4.1 WakeWordDetector（喚醒詞偵測）
- Edge Impulse 初始化
- 推論連續執行迴圈
- VAD + ML 信心度判定
- **Debug 等級**：`WAKE_LOG`

### 4.2 AudioStreamer（音訊串流）
- `audio_start` JSON 發送
- Binary chunk 串流傳輸
- **Debug 等級**：`STREAM_LOG`

### 4.3 HardwareController（硬體控制）
- LED 控制
- 繼電器 GPIO mapping（light、fan）
- 指令解析（JSON → action）
- **Debug 等級**：`HW_LOG`

## Phase 5：系統整合

### 5.1 SystemManager（系統管理器）
- 整合所有元件初始化順序
- Task 建立（inference_task）
- UI State / Eye UI 整合

### 5.2 main.cpp 精簡化
- `app_main()` 簡化為 `new SystemManager()->run()`

## 條件編譯範例

```c
// config.h
#define LOG_NONE   0
#define LOG_ERROR  1
#define LOG_INFO   2
#define LOG_DEBUG  3

#ifndef CONFIG_LOG_LEVEL
#define CONFIG_LOG_LEVEL LOG_INFO
#endif

// 使用方式
#if CONFIG_LOG_LEVEL >= LOG_DEBUG
    ESP_LOGD("TAG", "Debug message");
#endif
```

## 預期效益

- 主程式 `main.cpp` 從 948 行減少至 ~50 行
- 各模組獨立測試
- Debug 等級彈性控制
- 未來擴充（如多喚醒詞）更易實作
