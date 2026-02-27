# ESP32 Voice Agent Project 
## Project id: ESP-MIAO

本專案目標是在 **ESP32 Dev Kit v1** 上實作一個本地語音控制代理，使用 **Edge Impulse MFCC 模型** 進行喚醒詞偵測，搭配 **Local Server + Ollama LLM**，打造一個低延遲、可擴充、工程化的語音控制系統。

ESP32 負責語音感知與硬體控制，Server 負責語意理解與跨裝置協調。

---

## 1. Project Goals

* 在 ESP32 上實作 Always-on Wake Word（嘿喵喵）。
* 使用 Edge Impulse TFLite 模型進行本地喚醒詞推論。
* 對於複雜語意交由 Server + Ollama LLM 解析。
* 建立 JSON Protocol 作為事件傳遞格式。
* 支援 Relay、伺服器端本地音效播放 (aplay) 與未來 IoT 擴充。
* 提供特定動作音效對應（如開燈/關燈專屬音效）。

---

## 2. System Architecture

```
User
 ↓
Mic (INMP441) → ESP32 (Edge Impulse)
                 ├─ MFCC Feature Extraction
                 ├─ TFLite Inference (heymiaomiao / noise / unknown)
                 ├─ RMS VAD Gate
                 ├─ WiFi & WebSocket Client
                 └─ Audio Streamer (Chunked, Base64)
                      ↓
                   Server (Python FastAPI)
                     ├─ WebSocket Handler & Audio Reassembler
                     ├─ ASR (faster-whisper)
                     ├─ LLM Intent Parser (Ollama, Keyword Fallback)
                     ├─ Device Table Manager
                     └─ Action Dispatcher
                      ↓
                   ESP32 (GPIO Control)
                     ├─ JSON Command Parser
                     └─ GPIO Control (Relay, LED)
```

設計原則：

* ESP32 只做即時、低延遲、與自身硬體相關的任務。
* Server 處理語意、跨裝置、策略與安全。

---

## 3. Hardware

### 3.1 硬體需求

* ESP32 DevKit V1 (WROOM, 無 PSRAM)
* INMP441 I2S MEMS 麥克風模組

### 3.2 接線

| INMP441 Pin | ESP32 GPIO | 說明 |
| :--- | :--- | :--- |
| **SCK / BCLK** | **GPIO 32** | Bit Clock |
| **WS / LRCL** | **GPIO 25** | Word Select (Frame Clock) |
| **SD / DIN** | **GPIO 33** | Serial Data In |
| **L/R** | **GND** | 設定為左聲道 (Left Channel) |
| **VDD** | **3.3V** | 電源 |
| **GND** | **GND** | 接地 |

---

## 4. Edge Impulse Wake Word Detection

### 4.1 模型資訊

| 參數 | 值 |
| :--- | :--- |
| Project | esp-miao-mfcc (ID: 905178) |
| 採樣率 | 16000 Hz |
| 視窗大小 | 1000 ms (16000 samples) |
| 推論切片 | 250 ms × 4 slices |
| 分類 | `heymiaomiao`, `noise`, `unknown` |
| 閾值 | 0.7 (模型) + 1000.0 (RMS VAD) |
| DSP | MFCC (512 FFT, 32 filters, 13 cepstral) |
| 推論引擎 | TFLite (EON Compiled, INT8 量化) |

### 4.2 I2S 驅動策略

ESP32 V1 的 I2S 硬體在 Mono 模式下容易出現數據錯位。本專案採取：

1. **強制 Stereo 模式** — 設定為 `I2S_SLOT_MODE_STEREO`
2. **軟體左聲道提取** — 讀取雙聲道數據，手動取偶數索引 (Left)
3. **APLL 時鐘** — 啟用 `I2S_CLK_SRC_APLL` 確保精確 16kHz
4. **數據位移** — INMP441 輸出 24-bit 左對齊，以 `>> 11` 標準化為 16-bit 範圍

### 4.3 VAD (Voice Activity Detection)

使用 RMS 能量閘避免背景雜音誤判：

| 環境 | RMS 值 |
| :--- | :--- |
| 安靜 | < 200 |
| 電視背景音 | 500 ~ 800 |
| 喚醒詞 (近距離) | 1000 ~ 2000 |
| 一般說話 (1公尺) | 2000 ~ 7000 |

### 4.4 編譯與燒錄

```bash
cd firmware/esp32_edge_impulse

# 設定 ESP-IDF 環境
. $HOME/esp/esp-idf/export.sh

# 編譯
idf.py build

# 燒錄並監控
idf.py -p /dev/ttyUSB0 flash monitor
```

偵測成功時，Serial Monitor 顯示 `>>> WAKE WORD DETECTED! <<<`，藍色 LED (GPIO 2) 閃爍三次。

---

## 5. Responsibility Split

| Layer  | Responsibility                                           |
| ------ | -------------------------------------------------------- |
| ESP32  | Wake word (Edge Impulse), I2S audio, WiFi/WS client, GPIO control (relay, LED) |
| Server | Audio reassembly, ASR (faster-whisper), LLM intent (Ollama), device table, routing, logging |
| LLM    | JSON intent mapping only                                 |

---

## 6. JSON Protocol Design

### 6.1 ESP32 → Server (Audio Streaming)

ESP32 會先發送 `audio_start` 訊息，告知伺服器即將開始音訊串流，包含總採樣數。
```json
{
  "device_id": "esp32_01",
  "timestamp": 123456789,
  "type": "audio_start",
  "payload": {
    "audio_format": "pcm_16k_16bit",
    "transfer_mode": "binary",  // 或 "base64"
    "total_samples": 48000,
    "confidence": 0.85
  }
}
```

隨後，ESP32 根據 `transfer_mode` 選擇傳輸方式：

*   **Binary 模式 (推薦)**：ESP32 將原始 PCM 音訊直接以二進位訊框 (Binary Frame) 分塊傳送。伺服器累積位元組直到達標後自動處理。此模式節省 **33%** 頻寬且 CPU 開銷極低。
*   **Base64 模式**：ESP32 將音訊切割成多個 4KB 的區塊，並以 Base64 編碼，分次發送 `audio_chunk` 訊息。

```json
{
  "device_id": "esp32_01",
  "timestamp": 123456790,
  "type": "audio_chunk",
  "payload": {
    "chunk_index": 0,
    "is_last": false,
    "data_base64": "..."
  }
}
```
當 `is_last` 為 `true` (或 Binary 模式下位元組達標) 時，伺服器會將所有區塊組裝成完整的音訊檔進行 ASR 和 LLM 處理。

### 6.2 Server → ESP32 (Action / Play)

伺服器處理完意圖後，會根據結果回傳 `action` 或 `play` 訊息。

**Action 訊息 (控制硬體):**
```json
{
  "device_id": "esp32_01",
  "timestamp": 123456800,
  "type": "action",
  "payload": {
    "action": "relay_set",
    "target": "light",
    "value": "on",
    "sound": "success.wav"
  }
}
```
ESP32 將解析此訊息，並根據 `action`、`target`、`value` 控制對應的 GPIO。

**Play 訊息 (播放音效):**
```json
{
  "device_id": "esp32_01",
  "timestamp": 123456801,
  "type": "play",
  "payload": {
    "audio": "not_understood.wav"
  }
}
```
ESP32 目前僅會記錄此訊息，未來可擴充播放功能。

### 6.3 ESP32 → Server (Action Result)

ESP32 執行完 `action` 後，會回傳 `action_result` 告知伺服器執行結果。

```json
{
  "device_id": "esp32_01",
  "timestamp": 123456810,
  "type": "action_result",
  "payload": {
    "status": "success",
    "error": null
  }
}
```

---

## 7. Device Table + LLM

Server 維護裝置表：

```json
{
  "devices": [
    {"name": "light", "type": "relay", "gpio": 26},
    {"name": "fan", "type": "relay", "gpio": 27},
    {"name": "led", "type": "led", "gpio": 2}
  ]
}
```

LLM Prompt 設計範例 (用於 `qwen2.5:0.5b`)：

```
Task: Convert voice command to JSON.
Available devices: light, fan, led

Examples:
- Command: "幫我開燈" -> {"action": "relay_set", "target": "light", "value": "on"}
- Command: "關掉風扇" -> {"action": "relay_set", "target": "fan", "value": "off"}

Command: "用戶語音指令"
Response in ONE LINE JSON format ONLY:
```

---

## 8. ESP32 State Machine

```
IDLE
 → WAKE (Edge Impulse: heymiaomiao detected)
 → LISTEN (3秒錄音)
 → FORWARD_SERVER (傳輸音訊串流)
 → WAIT_ACTION (等待伺服器指令)
 → LOCAL_EXECUTE (解析 JSON 並控制 GPIO) | PLAY_FEEDBACK (播放音效)
 → IDLE
```

---

## 9. Project Structure

```
esp-miao/
├── firmware/
│   ├── esp32_edge_impulse/      # Edge Impulse 喚醒詞 (主要)
│   │   ├── main/main.cpp        #   主程式 (新增 WebSocket 連線, Audio Streaming, cJSON 解析, GPIO 控制)
│   │   ├── main/CMakeLists.txt  #   ESP-IDF build (新增 json, esp_websocket_client 等依賴)
│   │   ├── main/idf_component.yml #   ESP-IDF Component Manager (聲明 esp_websocket_client 依賴)
│   │   ├── sdkconfig.defaults   #   硬體設定
│   │   ├── edge-impulse-sdk/    #   SDK (copied, not in git)
│   │   ├── tflite-model/        #   TFLite 模型 (git tracked)
│   │   └── model-parameters/    #   模型參數 (git tracked)
│   ├── esp32_client/            # WebSocket client (Arduino)
│   ├── esp32_mic_test*/         # I2S 麥克風實驗
│   └── mic_frontend_v1/         # VAD + Recorder 原型
├── src/esp_miao/
│   ├── server.py                # FastAPI WebSocket server (新增 ASR, Audio Reassembler, LLM Fallback)
│   ├── models.py                # Pydantic protocol models (新增 AudioStreamStart/Chunk)
│   ├── esp32_simulator.py       # ESP32 模擬器 CLI (支援 Audio Request)
│   └── retry.py                 # Retry utilities
├── tests/
│   ├── test_communication.py    # WebSocket 基礎通訊測試
│   └── test_audio.py            # Audio Request (ASR) 流程測試
├── SPEC.md                      # Protocol specification
├── WALKTHROUGH.md               # Progress tracking
├── CHANGELOG.md                 # Version history
└── README.md                    # This file

---

## 10. MVP Implementation Plan

### Phase 1 (Done)

* Edge Impulse wake word detection
* I2S INMP441 audio capture
* RMS VAD gate
* LED feedback

### Phase 2 (Done)

* Server WebSocket + Ollama LLM
* JSON protocol
* ESP32 simulator

### Phase 3 (Future)

* Wake word → Server command forwarding
* Feedback audio playback
* Multi-device support

---

## Related Projects

| 專案 | 說明 |
| :--- | :--- |
| `esp-test` | Edge Impulse 喚醒詞實驗專案 (已整合至本專案) |
| `inmp441_recorder` | INMP441 錄音 + VAD + WiFi 上傳工具 (訓練資料收集) |

---

## Project follow ./WALKTHROUGH.md
## Project specification ./SPEC.md

## Reference 
same as ./REFERENCE.md

* [https://github.com/espressif/esp-sr](https://github.com/espressif/esp-sr)
* [https://docs.espressif.com/projects/esp-sr](https://docs.espressif.com/projects/esp-sr)
* [https://github.com/78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
* [https://github.com/ollama/ollama](https://github.com/ollama/ollama)
* [https://docs.espressif.com/projects/esp-idf](https://docs.espressif.com/projects/esp-idf)
* [https://edgeimpulse.com](https://edgeimpulse.com)
