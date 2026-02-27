# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.5] - 2026-02-27

### Added
- **Binary Audio Streaming (二進位音訊串流)**
  - 在 ESP32 韌體與 Server 端同步實作「純二進位」傳輸模式。
  - 頻寬節省約 **33%**，並大幅降低 ESP32 的 CPU 與記憶體開銷（免去 Base64 編碼與 JSON 封裝）。
  - 在 `audio_start` 協議中新增 `transfer_mode` 欄位以支援雙模式（`base64` 與 `binary`）。
- **Protocol Flexibility**
  - ESP32 韌體新增 `USE_BINARY_STREAM` 巨集，方便在不同環境下測試傳輸效能。

### Fixed
- **WebSocket Stability (Server-side)**
  - 修復了 `RuntimeError: Cannot call "receive" once a disconnect message has been received` 錯誤。
  - 正確處理 WebSocket 斷線事件訊息，確保伺服器在客戶端斷開後能平穩清理資源。

## [0.3.4] - 2026-02-26

### Optimized
- **Memory Management (ESP32 DevKit V1 Optimization)**
  - 將 3 秒錄音緩衝區 (`recording_buffer`) 從靜態分配改為動態分配 (`malloc`/`free`)。
  - 成功釋放 **96KB** 的靜態 DRAM 空間，使系統平時運行的 DRAM 剩餘量從 **30KB** 提升至 **126KB**。
  - 大幅提升了無 PSRAM 機種在處理 WebSocket 與 JSON 訊息時的穩定性。

### Changed
- **Threshold Fine-tuning**
  - 調降 `VAD_THRESHOLD` 從 `2000` 至 **`1500`**，找回更好的語音活動偵測靈敏度。
  - 調降 `EI_CLASSIFIER_THRESHOLD` 從 `0.9` 至 **`0.85`**，在保持穩定性的同時提升喚醒詞辨識的易用性。

## [0.3.3] - 2026-02-26

### Added
- **Keyword Pre-filtering Layer (關鍵字預篩選攔截)**
  - 在 Server 端導入「關鍵字先行」策略：若 ASR 辨識出的文字不包含任何裝置別名（如燈、風扇）或動作關鍵字（如開、關），則直接判定為誤觸，不再送往 LLM 解析。
  - 大幅減少對「哈哈笑聲」、「非控制用語」的無效 LLM 解析負擔，並提升系統反應速度。
- **LLM Prompt Optimization**
  - 在 Prompt 中加入反例（如「哈哈笑」-> `unknown`），引導 LLM 在遇到無法解析的內容時主動回傳 unknown，而非胡亂發明動作。
- **Enhanced Hallucination Filtering**
  - 調低重複字過濾門檻，現在能攔截更短的重複幻聽（如 "哈哈哈哈"）。

## [0.3.2] - 2026-02-26

### Added
- **ASR Hallucination Filtering**
  - 在 Server 端加入 `no_speech_threshold=0.6` 參數，強化 Whisper 對無聲/底噪的過濾。
  - 實作「重複短語過濾機制」，自動攔截常見的 Whisper 幻聽模式（如 "我認識了我認識了"）。
- **Documentation Update**
  - 在 `TROUBLESHOOTS.md` 中詳細紀錄了 Whisper 幻聽（Hallucination）的現象分析與應對方案。

### Fixed
- **Threshold Optimization**
  - 將 `EI_CLASSIFIER_THRESHOLD` 進一步從 `0.8` 提升至 **`0.9`**，以應對高分誤判的環境底噪（曾觀測到 0.895 的底噪誤觸）。

## [0.3.1] - 2026-02-26

### Added
- **Confidence Score Tracking**
  - ESP32 韌體現在會在 `audio_start` 訊息中傳送 Edge Impulse 的推論信心分數。
  - Server 端會將信心分數紀錄於 Log 中，並在儲存 `.wav` 檔時將分數加入檔名（例如 `conf0.85_recorded_...wav`），方便偵錯與分析。
- **Enhanced Debug Logging**
  - ESP32 增加 `Probable hit` 日誌，即使未達觸發門檻也會輸出 RMS 與 Confidence 數值，方便調校 VAD 與模型門檻。

### Fixed
- **False Trigger Reduction (誤觸發攔截)**
  - 調高 `EI_CLASSIFIER_THRESHOLD` 從 `0.7` 至 `0.8`。
  - 調高 `VAD_THRESHOLD` 從 `1000` 至 `2000`，有效攔截環境底噪造成的安靜誤觸。
  - 修正 Server 端在清空緩衝區前未正確擷取信心分數的邏輯錯誤。
- **ASR Silence Handling**
  - Server 端增加 ASR 空值攔截邏輯：若 Whisper 辨識結果為空（代表純雜訊或安靜），則跳過意圖解析並直接回傳 `not_understood.wav`。

## [0.3.0] - 2026-02-26

### Added

#### Server-side AI Processing & Communication
- **ASR (Automatic Speech Recognition) Integration**
  - 使用 `faster-whisper` 整合語音轉文字功能。
  - `transcribe_audio` 函式現在能夠將 Base64 編碼的 PCM 音訊轉換為文本。
  - 強制 Whisper 模型使用 `zh` 語言，顯著提高中文語音辨識準確度。
- **Chunked Audio Streaming Protocol**
  - **Server 支援**：新增 `audio_start` 和 `audio_chunk` 訊息類型，伺服器能夠接收分塊傳送的音訊資料，並在收到所有區塊後重新組裝成完整的音訊檔進行 ASR 處理。
  - 改善 ESP32 記憶體使用效率，解決了單次傳輸大檔案造成的記憶體分配失敗問題。
- **Enhanced LLM Intent Parsing**
  - 優化 `parse_intent_with_llm` 的 Prompt，加入明確範例以引導 0.5b 小型 Ollama 模型產生更精確的 JSON 意圖。
  - 強化了 **Keyword Fallback (關鍵字後備機制)**：當 LLM 的解析結果不符預期（例如 `target` 或 `value` 錯誤）時，系統將優先採用關鍵字比對的結果，大幅提升了語意辨識的可靠性與強健性。

#### ESP32 Firmware Functionality
- **WiFi & WebSocket Client**
  - 實作了 ESP32 端的 WiFi 連線和 WebSocket 客戶端功能。
  - 現在能夠穩定連接到伺服器並進行雙向通訊。
- **Audio Streaming Implementation**
  - 新增 `send_audio_stream` 函式，將喚醒詞偵測後的 3 秒音訊以 4KB 區塊透過 WebSocket 傳輸至伺服器。
  - 解決了 ESP32 記憶體不足的問題。
- **Server Action Execution**
  - 整合 `cJSON` 函式庫，使 ESP32 能夠解析伺服器傳來的 JSON 動作指令。
  - 實作 `handle_server_action` 函式，根據伺服器的 `action` (例如 `relay_set`, `led_set`) 和 `target` (例如 `light`, `fan`)，控制對應的 GPIO 腳位 (目前映射 light -> GPIO 26, fan -> GPIO 27, led -> GPIO 2)。
  - 支援 `play` 動作指令（韌體端目前僅記錄，未實作音效播放）。
- **Build System Updates**
  - 更新 `firmware/esp32_edge_impulse/main/CMakeLists.txt`，正確聲明 `esp_websocket_client`, `json`, `driver` 等組件依賴，確保編譯順利。
  - 建立了 `firmware/esp32_edge_impulse/main/idf_component.yml`，以支援 ESP-IDF Managed Components。

#### Testing & Tools
- **ESP32 Simulator Enhancement**
  - `esp32_simulator.py` 現在支援發送 `audio_request`（`a <filename>` 指令），允許開發者在無實體硬體情況下測試伺服器的 ASR 和 LLM 管線。
- **New Test Scripts**
  - `tests/test_communication.py`：驗證 WebSocket 基礎通訊。
  - `tests/test_audio.py`：驗證伺服器對音訊請求的處理，包括儲存和 ASR 流程。

### Changed
- **`firmware/esp32_edge_impulse/main/main.cpp`**：
  - 移除了 Base64 編碼，改為使用 `mbedtls/base64.h`。
  - 移除了單次大檔案 Base64 和 JSON 緩衝區分配。
- **`src/esp_miao/server.py`**：
  - 移除了舊的 `handle_audio_request` 邏輯，改由 `process_complete_audio` 處理完整音訊。
  - `ConnectionManager` 增加了 `audio_buffers` 用於音訊分塊組裝。

### Fixed
- 修正了 `firmware/esp32_edge_impulse/main/main.cpp` 在沒有明確宣告 `esp_websocket_client`, `json`, `driver` 等組件依賴時造成的編譯錯誤 (`fatal error: ...: No such file or directory`)。
- 解決了 ESP32 在嘗試一次性分配大量記憶體來傳輸完整 Base64 音訊時的 `Failed to allocate b64 buffer` 錯誤，透過分塊傳輸策略避免了記憶體溢出。

## [0.2.0] - 2026-02-25

### Added

#### Edge Impulse Wake Word Integration
- **Edge Impulse TFLite 喚醒詞偵測** — 從 `esp-test` 實驗專案整合至 `firmware/esp32_edge_impulse/`
  - 模型: `esp-miao-mfcc` (Edge Impulse Project ID: 905178)
  - 喚醒詞: `heymiaomiao` (3 類: heymiaomiao / noise / unknown)
  - DSP: MFCC (512 FFT, 32 filters, 13 cepstral coefficients)
  - 推論引擎: TFLite EON Compiled, INT8 量化
- **連續滑動視窗推論** — 1000ms window, 每 250ms 推論一次 (4 slices)
- **I2S Stereo + 軟體左聲道提取** — 解決 ESP32 V1 硬體 Mono 模式數據錯位問題
  - 固定接線: BCK=GPIO32, WS=GPIO25, DIN=GPIO33
  - 時鐘: APLL 啟用，提供精確 16kHz 取樣
- **RMS VAD 能量閘** — 閾值 1000.0，雙重觸發 (模型信心 + 音量) 降低誤判
- **LED 回饋** — 偵測成功時 GPIO 2 藍色 LED 閃爍三次
- **Kconfig 支援** — `EI_WAKE_WORD` 和 `EI_VAD_THRESHOLD` 可透過 menuconfig 調整
- **sdkconfig.defaults** — 預設 ESP32 最佳化設定 (APLL, Performance optimization, Large partition)

#### Build System
- **ESP-IDF CMakeLists.txt** — 完整的 Edge Impulse SDK + TFLite 模型建置系統
- **直接複製架構** — `edge-impulse-sdk/`, `tflite-model/`, `model-parameters/` 從 `esp-test` 直接複製，專案完全自包含
  - `edge-impulse-sdk/` (1374 files) 排除於 git 追蹤，需從 `esp-test` 重新複製
  - `tflite-model/` 與 `model-parameters/` 納入 git 追蹤

### Removed
- **BOOTSTRAP.md** — 已廢止，內容為早期 esp-sr skeleton code，不再適用於 Edge Impulse 架構

### Changed
- **README.md** — 全面改寫，反映 Edge Impulse 取代 esp-sr 的架構變更
  - 新增硬體接線表、模型參數表、VAD 參考值、專案結構圖
  - 更新系統架構圖為 Edge Impulse pipeline
- **WALKTHROUGH.md** — 更新進度，標記 Edge Impulse 整合完成，esp-sr 方案標記為已放棄
- **.gitignore** — 排除 Edge Impulse SDK (大型, 1374 files)、ESP-IDF build cache；追蹤 tflite-model 與 model-parameters

### Technical Notes
- Edge Impulse 取代 esp-sr 的原因: esp-sr (WakeNet/MultiNet) 在標準 ESP32-WROOM (無 PSRAM) 上記憶體不足
- Binary size: 0x415c0 bytes (~267KB)，佔 Large partition (0x177000) 的 17%
- 模型 Arena size: 6227 bytes，記憶體佔用極低

---

## [0.1.0] - 2026-02-03

### Added

#### Server Side
- **WebSocket Server** - FastAPI WebSocket endpoint (`/ws/{device_id}`) for ESP32 communication
- **JSON Protocol Models** - Pydantic models for all message types defined in SPEC.md
  - `CommandRequest` - ESP32 sends recognized command from esp-sr
  - `FallbackRequest` - ESP32 sends text/audio for LLM processing
  - `ActionResult` - ESP32 reports action execution result
  - `Action` - Server sends action command to ESP32
  - `Play` - Server sends audio playback command
- **Ollama LLM Integration** - Intent parsing with qwen2.5:0.5b model
- **Keyword Validation Layer** - Pre-validation before LLM to ensure device exists
  - Device aliases mapping (燈/電燈/light, 風扇/電風扇/fan, etc.)
  - Action keywords mapping (開/打開/on, 關/關閉/off, etc.)
- **Device Table Manager** - Configurable device registry with GPIO mapping
- **Action Router** - Routes parsed intents to appropriate actions
- **Feedback Audio API** - Endpoints for serving audio files (`/audio/{filename}`)
- **Logging** - Structured logging for debugging and monitoring

#### Protocol
- **JSON Schema** - Complete protocol definition matching SPEC.md
- **Timeout Handling** - Configurable WebSocket response timeout (10s default)
- **Retry Logic** - `retry.py` module with exponential backoff support

#### Safety
- **GPIO Whitelist** - Only safe GPIO pins allowed (避免 flash/boot pins)
- **Action Validation** - Validates action, target, and value before execution
- **Fail-safe Default** - Invalid actions return `noop` or error response

#### Testing & Tools
- **ESP32 Simulator** (`esp32-sim`) - Interactive CLI tool to simulate ESP32 device
  - State machine implementation matching SPEC.md
  - Command simulation (0-3 for local commands)
  - Fallback text request simulation
  - Full wake->listen->recognize flow simulation
- **Communication Test** - Non-interactive test script for WebSocket validation

### Project Structure

```
esp-miao/
├── src/esp_miao/
│   ├── __init__.py          # Package init (version 0.1.0)
│   ├── models.py             # Pydantic models, State Machine, Safety validators
│   ├── server.py             # FastAPI WebSocket server
│   ├── retry.py              # Retry utilities
│   ├── esp32_simulator.py    # ESP32 simulator CLI
│   └── audio/                # Feedback audio files
├── tests/
│   └── test_communication.py # WebSocket communication test
├── pyproject.toml            # Project config with uv
├── CHANGELOG.md              # This file
├── WALKTHROUGH.md            # Progress tracking
└── ...
```

### Usage

```bash
# Start server
uv run esp-miao

# Start ESP32 simulator (another terminal)
uv run esp32-sim

# Run communication test
uv run python tests/test_communication.py
```

### Dependencies
- fastapi >= 0.128.0
- uvicorn >= 0.40.0
- websockets >= 16.0
- ollama >= 0.6.1
- python-dotenv >= 1.2.1

[0.2.0]: https://github.com/user/esp-miao/releases/tag/v0.2.0
[0.1.0]: https://github.com/user/esp-miao/releases/tag/v0.1.0
