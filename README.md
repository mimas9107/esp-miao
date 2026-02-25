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
* 支援 relay、音效播放與未來 IoT 擴充。

---

## 2. System Architecture

```
User
 ↓
Mic (INMP441) → ESP32 (Edge Impulse)
                 ├─ MFCC Feature Extraction
                 ├─ TFLite Inference (heymiaomiao / noise / unknown)
                 ├─ RMS VAD Gate
                 └─ Wake Action (LED blink)
                      ↓ (future: fallback)
                   Server
                     ├─ ASR
                     ├─ Ollama Intent
                     ├─ Device Mapper
                     └─ Action Router
                      ↓
                   ESP32 Execute
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
| ESP32  | Wake word (Edge Impulse), audio frontend, relay, LED     |
| Server | ASR, LLM intent, device table, routing, logging         |
| LLM    | JSON intent mapping only                                 |

---

## 6. JSON Protocol Design

### 6.1 ESP32 → Server

```json
{
  "type": "command_request",
  "device_id": "esp32_01",
  "timestamp": 17574239,
  "text": "小E 開燈"
}
```

### 6.2 Server → ESP32 Action

```json
{
  "type": "action",
  "action": "relay_set",
  "target": "light",
  "value": "on",
  "sound": "success.wav"
}
```

### 6.3 ESP32 → Server Result

```json
{
  "type": "action_result",
  "status": "success"
}
```

---

## 7. Device Table + LLM

Server 維護裝置表：

```json
{
  "devices": [
    {"name": "light", "type": "relay", "gpio": 26}
  ]
}
```

Prompt 設計：

```
你是控制系統，只能輸出 JSON。
依照裝置表將指令轉成 action。
```

---

## 8. ESP32 State Machine

```
IDLE
 → WAKE (Edge Impulse: heymiaomiao detected)
 → LISTEN
 → RECOGNIZE
 → LOCAL_EXECUTE | FORWARD_SERVER
 → WAIT_RESULT
 → PLAY_FEEDBACK
 → IDLE
```

---

## 9. Project Structure

```
esp-miao/
├── firmware/
│   ├── esp32_edge_impulse/      # Edge Impulse 喚醒詞 (主要)
│   │   ├── main/main.cpp        #   主程式
│   │   ├── CMakeLists.txt       #   ESP-IDF build
│   │   ├── sdkconfig.defaults   #   硬體設定
│   │   ├── edge-impulse-sdk/    #   SDK (copied, not in git)
│   │   ├── tflite-model/        #   TFLite 模型 (git tracked)
│   │   └── model-parameters/    #   模型參數 (git tracked)
│   ├── esp32_client/            # WebSocket client (Arduino)
│   ├── esp32_mic_test*/         # I2S 麥克風實驗
│   └── mic_frontend_v1/         # VAD + Recorder 原型
├── src/esp_miao/
│   ├── server.py                # FastAPI WebSocket server
│   ├── models.py                # Pydantic protocol models
│   ├── esp32_simulator.py       # ESP32 模擬器 CLI
│   └── retry.py                 # Retry utilities
├── tests/
├── SPEC.md                      # Protocol specification
├── WALKTHROUGH.md               # Progress tracking
├── CHANGELOG.md                 # Version history
└── README.md                    # This file
```

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
