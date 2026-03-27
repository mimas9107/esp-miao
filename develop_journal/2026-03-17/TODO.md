# 重構 TODO：ESP32 韌體物件導向化

> 日期：2026-03-17
> 最後更新：2026-03-18
> 狀態：**Phase 1-5 全部完成（待 idf.py build 驗證）**

## Phase 1：基礎設施 ✅

- [x] **1.1** 建立 `main/config/` 資料夾與 `Config` 類別
  - [x] config.h - 常數定義 + Debug 等級巨集
  - [x] config.cpp - 實作
- [x] **1.2** 建立 `main/time/` 資料夾與 `TimeManager` 類別
  - [x] time_manager.h
  - [x] time_manager.cpp
  - [x] 整合 NTP 初始化

## Phase 2：硬體抽象 ✅

- [x] **2.1** 建立 `main/audio/` 資料夾與 `AudioCapture` 類別
  - [x] audio_capture.h
  - [x] audio_capture.cpp
  - [x] I2S 初始化
  - [x] read_audio_slice() / read_audio_to_buffer()
- [x] **2.2** 建立 `VAD` 類別
  - [x] vad.h
  - [x] vad.cpp
  - [x] FFT 優化實作
  - [x] vad_detect() 介面
  - [x] 統計數據結構

## Phase 3：網路 ✅

- [x] **3.1** 建立 `main/network/` 資料夾與 `WifiManager` 類別
  - [x] wifi_manager.h（含 `esp_event.h` 引入修正）
  - [x] wifi_manager.cpp
  - [x] NVS 憑證管理
  - [x] WiFi 事件處理
- [x] **3.2** 建立 `WebSocketClient` 類別
  - [x] websocket_client.h
  - [x] websocket_client.cpp
  - [x] 連線/斷線處理
  - [x] send_text() / send_binary()
  - [x] emergency_reconnect()

## Phase 4：邏輯層 ✅

- [x] **4.1** 建立 `WakeWordDetector` 類別
  - [x] wake_word_detector.h
  - [x] wake_word_detector.cpp
  - [x] 推論迴圈（含 FFT VAD 整合）
  - [x] 喚醒後動作協調
- [x] **4.2** 建立 `AudioStreamer` 類別
  - [x] audio_streamer.h
  - [x] audio_streamer.cpp
  - [x] binary 串流（STREAM_CHUNK_SAMPLES）
- [x] **4.3** 建立 `HardwareController` 類別
  - [x] hardware_controller.h
  - [x] hardware_controller.cpp
  - [x] LED init / set_led / blink_led

## Phase 5：系統整合 ✅

- [x] **5.1** `SystemManager` 決定不另建類別
  - 理由：`app_main()` 已足夠清晰，多一層封裝無實際效益
- [x] **5.2** 精簡 `main.cpp`
  - 原始：948 行 → 最終：**~100 行**
  - app_main() 負責初始化順序管理
  - 移除所有舊版全域 ws_client / ws_connected
  - 移除 stream_audio_realtime() / init_wifi() 等 C-style wrapper

---

## 驗證清單

- [x] `idf.py build` 編譯成功（2026-03-18 通過）
- [x] `idf.py flash monitor` 燒錄測試
- [x] 終端機訊息正常輸出（WebSocket ping/binary opcode 過濾修正）
- [x] 功能運作正常（喚醒詞偵測 + 串流）
