# Merge Eye Animation UI to ESP32 Edge Impulse Project - Finalized

## 1. Goal
將 `esp_eye_v2` 專案中的眼睛動畫 UI (ST7735 驅動) 整合至 `firmware/esp32_edge_impulse`。
讓設備在「待機、喚醒、錄音中、思考中、執行指令、錯誤」等狀態下有視覺反饋。

## 2. Architecture
- **Firmware Logic**: `firmware/esp32_edge_impulse/main/main.cpp`
  - 負責 VAD, Wake Word (Edge Impulse), **Real-time Audio Streaming (Optimized)**.
- **UI Component**: `components/eye_ui` (New)
  - 基於 `arduino-esp32` + `TFT_eSPI`。
  - 運行於 Core 1 (獨立 Task)，避免干擾 Core 0 的語音處理。
- **State Bridge**: `components/ui_state` (New)
  - 使用 FreeRTOS Queue (`xQueueOverwrite`) 進行跨 Task 狀態傳遞。

## 3. Integration Plan - Execution Results
### Phase 1: Preparation [Success]
- 複製組件：`eye_ui`, `ui_state`, `TFT_eSPI`。
- 修改 `idf_component.yml` 加入 `arduino-esp32`。
- 修改 `main/CMakeLists.txt` 加入元件依賴。

### Phase 2: Implementation [Success]
- **Initialization**: 在 `app_main()` 中加入 `initArduino()`, `ui_state_init()`, `eye_ui_start()`。
- **Optimization**: 發現 96KB 連續記憶體申請導致 OOM，將「錄音後傳送」架構重構為 **「即時串流 (Real-time Streaming)」**。
- **State Updates**: 成功在語音流程中同步 UI 狀態。

### Phase 3: Configuration [Success]
- 透過 `sdkconfig.defaults` 設定 TFT_eSPI 腳位與關閉 Arduino 自動啟動。

### Phase 4: Validation [Success]
- 實機驗證通過：狀態鏈 (Idle -> Wake -> Listening -> Thinking -> Action -> Idle) 運作流暢。
- Heap 剩餘約 118KB，資源狀況健康。

## 4. Pin Mapping Summary
- **I2S (Mic)**: BCK=32, WS=25, DIN=33
- **SPI (TFT)**: MOSI=23, SCLK=18, CS=16, DC=5, RST=17
- **LED**: 2 (Status)
