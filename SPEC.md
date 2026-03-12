# Engineering Specs

> 最後更新：2026-03-12
>
> 本文件定義 ESP-MIAO 專案的通訊協議、狀態機、硬體配置與系統架構。

---

## 架構總覽

```
ESP32 (邊緣端 - Core 0 & Core 1)             Server (伺服器端)
┌────────────────────────────────┐          ┌──────────────────────────────┐
│ Core 0: Audio Pipeline         │          │ FastAPI WebSocket Server     │
│  ┌──────────────────────┐      │          │                              │
│  │ INMP441 I2S Mic      │      │          │  ┌─ ASR (faster-whisper)     │
│  │       ↓              │      │ WebSocket│  ├─ LLM Intent (Ollama)      │
│  │ Edge Impulse MFCC    │      │ binary   │  └─ MQTT Publish             │
│  │  (wake word detect)  │──────┼─────────→│         ↓                    │
│  │       ↓              │      │ stream   │   IoT Devices (via MQTT)     │
│  │ Real-time Streaming  │      │          │   action / play response     │
│  └──────────────────────┘      │          │                              │
│             ↓ ui_state queue   │          │                              │
│ Core 1: UI Pipeline            │          │                              │
│  ┌──────────────────────┐      │ JSON     │                              │
│  │ ST7735 Eye UI        │←─────┼──────────┤                              │
│  │ (Animation States)   │      │ response │                              │
│  └──────────────────────┘      │          │                              │
└────────────────────────────────┘          └──────────────────────────────┘
```

**角色分工：**

* **ESP32 (邊緣端)**：
    * **主邏輯 (Core 0)**：負責 VAD 喚醒（辨識 "heymiaomiao"）、即時音訊串流傳送至伺服器。
    * **顯示 UI (Core 1)**：負責視覺反饋，基於 Arduino 框架運行，根據主邏輯發布的狀態顯示動畫。
* **Server (伺服器端)**：接收音訊 → ASR 辨識 → LLM 意圖解析 → MQTT 指令發送。所有控制決策均在伺服器端執行。

---

## 1. JSON Protocol Definition

### 1.1 Common Envelope

所有 WebSocket 訊息皆遵循以下基礎結構：

```json
{
  "type": "message_type",
  "device_id": "esp32_01",
  "timestamp": 1709366400000,
  "payload": {}
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `type` | string | 訊息類型（見下方各節定義） |
| `device_id` | string | 裝置識別碼，例如 `"esp32_01"` |
| `timestamp` | int | 時間戳記（Unix Epoch 毫秒） |
| `payload` | object | 依訊息類型而異的承載資料 |

---

### 1.2 ESP32 → Server

#### Audio Stream Start

ESP32 喚醒後、開始傳送音訊前發送。

```json
{
  "type": "audio_start",
  "device_id": "esp32_01",
  "timestamp": 1709366400000,
  "payload": {
    "audio_format": "pcm_16k_16bit",
    "transfer_mode": "binary",
    "total_samples": 48000,
    "confidence": 0.85
  }
}
```

#### Audio Binary (Binary 模式 - 推烈)

當 `transfer_mode` 為 `"binary"` 時，`audio_start` 之後以 WebSocket binary frame 直接分塊傳送原始 PCM bytes。Server 接收完畢即處理。

---

### 1.3 Server → ESP32

#### Action

Server 指示 ESP32 執行動作：

```json
{
  "type": "action",
  "device_id": "esp32_01",
  "timestamp": 1709366400000,
  "payload": {
    "action": "relay_set",
    "target": "light",
    "value": "on",
    "sound": "lightopen.wav"
  }
}
```

---

## 2. State & Event Definition

### 2.1 ESP32 Logic & UI State Mapping

ESP32 內部採用非阻塞式的 UI 狀態機，透過 FreeRTOS Queue 進行通訊：

| Logic State | UI State Code | Animation Mapping | Description |
|-------------|---------------|-------------------|-------------|
| IDLE        | `UI_IDLE`     | Blinking eyes     | 待機，隨機眨眼 |
| WAKE        | `UI_WAKE`     | Surprised eyes    | 喚醒詞偵測到，驚訝表情 |
| LISTEN      | `UI_LISTENING`| Narrowed eyes     | 準備錄音中 |
| FORWARD     | `UI_THINKING` | Rolling eyes      | 即時音訊串流傳輸中 |
| ACTION      | `UI_ACTION`   | Happy/Heart eyes  | 收到 Server 指令並執行 |
| ERROR       | `UI_ERROR`    | Sad/Cross eyes    | 傳輸失敗或發生錯誤 |

### 2.2 整合處理流程 (Edge Impulse 韌體)

```
IDLE (Blink) ──────────→ Wake Word Detected ──────────→ UI_WAKE (Surprise)
                                 ↓
UI_THINKING (Roll) ←──── 即時串流 3s PCM (Binary) ←──── UI_LISTENING
      ↓
WAIT_ACTION (Thinking) ──────────→ 收到 Action ───────→ UI_ACTION (Happy)
                                 ↓
                               回歸 IDLE (Blink)
```

---

## 4. Audio Capture & Edge Impulse Pipeline

### 4.1 Hardware & Format

* Sample Rate: 16kHz, 16bit Mono.
* APLL 啟用，確保時脈精確。

### 4.6 Recording & Streaming (Memory Optimized)

> **重要更新 (v0.6.0)**: 為避免 96KB 連續記憶體申請導致的 OOM 錯誤，本專案改用 **「即時串流 (Real-time Streaming)」**。

1. **最小緩衝區**: 使用 2KB (`1024 samples`) 的暫存緩衝區。
2. **邊讀邊傳**: I2S 每讀滿一個 Chunk 立即透過 WebSocket 發送 Binary Frame。
3. **優點**: 記憶體需求極低，反應延遲顯著降低。

---

## 5. Hardware Configuration

### 5.1 I2S Microphone (INMP441)

| Pin | GPIO | Function |
|-----|------|----------|
| BCK | 32   | Bit Clock |
| WS  | 25   | Word Select |
| DIN | 33   | Data In |

### 5.2 ST7735 TFT Display (SPI)

| Pin  | GPIO | Function |
|------|------|----------|
| MOSI | 23   | SPI Data |
| SCLK | 18   | SPI Clock|
| CS   | 16   | Chip Select|
| DC   | 5    | Data/Command|
| RST  | 17   | Reset |

### 5.3 System Status LED

| Pin | GPIO | Function |
|-----|------|----------|
| LED | 2    | Internal Status LED |

---

## 8. Versioning & Development Standards

*   **唯一基準**: `CHANGELOG.md` 為專案版本號的 **Single Source of Truth (SSOT)**。
*   **版本格式**: Semantic Versioning 2.0.0。
