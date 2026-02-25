# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
