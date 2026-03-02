# Engineering Specs

> 最後更新：2026-03-02
>
> 本文件定義 ESP-MIAO 專案的通訊協議、狀態機、硬體配置與系統架構。

---

## 架構總覽

```
ESP32 (邊緣端)                              Server (伺服器端)
┌─────────────────────┐                    ┌──────────────────────────────┐
│ INMP441 I2S Mic     │                    │ FastAPI WebSocket Server     │
│       ↓             │                    │                              │
│ Edge Impulse MFCC   │    WebSocket       │  ┌─ ASR (faster-whisper)     │
│  (wake word detect) │ ──────────────────→│  ├─ LLM Intent (Ollama)      │
│       ↓             │   audio stream     │  └─ MQTT Publish             │
│ 錄音 3s PCM         │                    │         ↓                    │
│       ↓             │                    │   IoT Devices (via MQTT)     │
│ Stream to Server    │←──────────────────│   action / play response     │
└─────────────────────┘   JSON response    └──────────────────────────────┘
```

**角色分工：**

* **ESP32 (邊緣端)**：負責 VAD 喚醒（辨識 "heymiaomiao"），觸發後錄製 3 秒音訊，透過 WebSocket 傳送至伺服器。ESP32 不負責任何 MQTT 指令發送或邏輯判斷。
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
| `timestamp` | int | 時間戳記（Unix epoch 毫秒 或 裝置 uptime 毫秒） |
| `payload` | object | 依訊息類型而異的承載資料 |

---

### 1.2 ESP32 → Server

#### Audio Stream Start

ESP32 喚醒後、開始傳送音訊前發送。通知 Server 準備接收串流。

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

| Payload 欄位 | 型別 | 說明 |
|--------------|------|------|
| `audio_format` | string | 音訊格式，預設 `"pcm_16k_16bit"` |
| `transfer_mode` | `"base64"` \| `"binary"` | 串流傳輸模式 |
| `total_samples` | int | 預期總樣本數（16kHz × 3s = 48000） |
| `confidence` | float? | 喚醒詞信心值 (0.0–1.0)，可選 |

#### Audio Chunk (Base64 模式)

當 `transfer_mode` 為 `"base64"` 時，音訊以 JSON 分塊傳送：

```json
{
  "type": "audio_chunk",
  "device_id": "esp32_01",
  "timestamp": 1709366400100,
  "payload": {
    "chunk_index": 0,
    "is_last": false,
    "data_base64": "AQID..."
  }
}
```

| Payload 欄位 | 型別 | 說明 |
|--------------|------|------|
| `chunk_index` | int | 分塊序號（從 0 開始） |
| `is_last` | bool | 是否為最後一塊 |
| `data_base64` | string | Base64 編碼的 PCM 資料 |

#### Audio Binary (Binary 模式)

當 `transfer_mode` 為 `"binary"` 時，`audio_start` 之後以 WebSocket binary frame 直接傳送原始 PCM bytes。Server 依 `total_samples` 計算預期位元組數，接收完畢即處理。

#### Audio Request (一次性傳送)

替代串流方式，將整段音訊以單一 JSON 傳送（適用於模擬器或小音訊）：

```json
{
  "type": "audio_request",
  "device_id": "esp32_01",
  "timestamp": 1709366400000,
  "payload": {
    "audio_base64": "AQID...",
    "audio_format": "pcm_16k_16bit",
    "duration_ms": 3000,
    "confidence": 0.85
  }
}
```

#### Command Request

本地已辨識的指令（用於模擬器或未來本地辨識場景）：

```json
{
  "type": "command_request",
  "device_id": "esp32_01",
  "timestamp": 1709366400000,
  "payload": {
    "source": "esp-sr",
    "cmd_id": 0,
    "cmd_name": "LIGHT_ON",
    "confidence": 0.91
  }
}
```

#### Fallback Request

文字或音訊 fallback（用於模擬器或文字指令場景）：

```json
{
  "type": "fallback_request",
  "device_id": "esp32_01",
  "timestamp": 1709366400000,
  "payload": {
    "text": "啟動掃地機器人",
    "audio_base64": null,
    "audio_format": "pcm_16k_16bit"
  }
}
```

#### Action Result

ESP32 回報動作執行結果：

```json
{
  "type": "action_result",
  "device_id": "esp32_01",
  "timestamp": 1709366400000,
  "payload": {
    "status": "success",
    "error": null
  }
}
```

---

### 1.3 Server → ESP32

#### Action

Server 指示 ESP32 執行動作（或通知動作已完成）：

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

| Payload 欄位 | 型別 | 說明 |
|--------------|------|------|
| `action` | string | 動作類型（見 §5.2 允許動作清單） |
| `target` | string | 目標裝置名稱（見 §5.1 裝置表） |
| `value` | string | 值：`"on"`, `"off"`, `"toggle"` |
| `sound` | string? | 建議播放的音效檔案，可選 |

#### Play (Feedback Only)

Server 僅指示播放音效（無硬體動作）：

```json
{
  "type": "play",
  "device_id": "esp32_01",
  "timestamp": 1709366400000,
  "payload": {
    "audio": "not_understood.wav"
  }
}
```

---

### 1.4 訊息類型總覽

| type | 方向 | 說明 |
|------|------|------|
| `audio_start` | ESP32 → Server | 音訊串流開始通知 |
| `audio_chunk` | ESP32 → Server | Base64 音訊分塊 |
| `audio_request` | ESP32 → Server | 一次性音訊傳送 |
| `command_request` | ESP32 → Server | 本地已辨識指令 |
| `fallback_request` | ESP32 → Server | 文字/音訊 Fallback |
| `action_result` | ESP32 → Server | 動作執行結果回報 |
| `action` | Server → ESP32 | 動作指令 |
| `play` | Server → ESP32 | 音效播放指令 |

---

## 2. State & Event Definition

### 2.1 ESP32 State Machine

| State | Description |
|-------|-------------|
| IDLE | 待機，等待喚醒詞 |
| WAKE | 喚醒詞偵測到 |
| LISTEN | 錄製音訊中（3 秒） |
| RECOGNIZE | 推論處理中（Edge Impulse） |
| LOCAL_EXECUTE | 執行本地動作（GPIO 控制） |
| FORWARD_SERVER | 傳送資料至 Server |
| WAIT_ACTION | 等待 Server 回應 |
| PLAY_FEEDBACK | 播放音效回饋 |
| ERROR | 錯誤處理 |

### 2.2 主要流程（Edge Impulse 韌體）

```
IDLE → RECOGNIZE (持續推論)
         ↓ wake word detected
       WAKE (LED 閃爍)
         ↓
       LISTEN (錄音 3s)
         ↓
       FORWARD_SERVER (audio_start + binary/base64 stream)
         ↓
       WAIT_ACTION (等待 Server 回應)
         ↓
       action → LOCAL_EXECUTE → PLAY_FEEDBACK → IDLE
       play   → PLAY_FEEDBACK → IDLE
```

### 2.3 主要流程（模擬器 / Arduino Client）

```
IDLE → (使用者輸入 / 模擬喚醒)
         ↓
       WAKE → LISTEN → RECOGNIZE
         ↓
       command_request 或 fallback_request → FORWARD_SERVER
         ↓
       WAIT_ACTION
         ↓
       action → LOCAL_EXECUTE → PLAY_FEEDBACK → IDLE
       play   → PLAY_FEEDBACK → IDLE
```

---

## 3. WebSocket 通訊

### 3.1 連線端點

```
ws://<server-ip>:8000/ws/{device_id}
```

* `device_id` 作為 URL path parameter，用於識別連線裝置。
* Server 端路由：`@app.websocket("/ws/{device_id}")`

### 3.2 ESP32 Client (ESP-IDF v5.x)

```c
#include "esp_websocket_client.h"

#define SERVER_URL "ws://192.168.1.103:8000/ws/esp32_01"

static esp_websocket_client_handle_t ws_client = NULL;
static bool ws_connected = false;

static void websocket_event_handler(void *handler_args, esp_event_base_t base,
                                     int32_t event_id, void *event_data)
{
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;
    switch (event_id) {
        case WEBSOCKET_EVENT_CONNECTED:
            ws_connected = true;
            break;
        case WEBSOCKET_EVENT_DISCONNECTED:
            ws_connected = false;
            break;
        case WEBSOCKET_EVENT_DATA:
            // 解析 JSON → handle_server_action()
            break;
        case WEBSOCKET_EVENT_ERROR:
            break;
    }
}

void init_websocket(void)
{
    esp_websocket_client_config_t ws_cfg = {};
    ws_cfg.uri = SERVER_URL;

    ws_client = esp_websocket_client_init(&ws_cfg);
    esp_websocket_register_events(ws_client, WEBSOCKET_EVENT_ANY,
                                   websocket_event_handler, NULL);
    esp_websocket_client_start(ws_client);
}
```

### 3.3 傳送方式

| 方式 | 函式 | 適用場景 |
|------|------|----------|
| JSON Text | `esp_websocket_client_send_text()` | `audio_start`, `audio_chunk` |
| Binary | `esp_websocket_client_send_bin()` | `transfer_mode: "binary"` 時的 PCM 資料 |

---

## 4. Audio Capture & Edge Impulse Pipeline

> 音訊管線是整個專案的核心路徑。ESP32 以 I2S 擷取麥克風音訊，透過 Edge Impulse MFCC 模型持續偵測喚醒詞。

### 4.1 Hardware

* ESP32 Dev Kit v1
* I2S MEMS Mic: INMP441
* Sample Rate: 16kHz
* Bits: 32bit 讀取，軟體右移至 16bit
* Channel: Stereo 讀取，軟體抽取左聲道（ESP32 HW V1 相容）

### 4.2 I2S Pin Configuration

| Pin | GPIO | 說明 |
|-----|------|------|
| BCK | 32 | Bit Clock |
| WS | 25 | Word Select (L/R Clock) |
| DIN | 33 | Data In |
| LED | 2 | 內建 LED（狀態指示） |

### 4.3 I2S Configuration (ESP-IDF v5.x STD API)

```c
#define SAMPLE_RATE     16000
#define I2S_PORT_NUM    I2S_NUM_0
#define DMA_BUF_COUNT   8
#define DMA_BUF_LEN     256

i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_PORT_NUM, I2S_ROLE_MASTER);
chan_cfg.dma_desc_num  = DMA_BUF_COUNT;
chan_cfg.dma_frame_num = DMA_BUF_LEN;
chan_cfg.auto_clear    = true;

i2s_std_config_t std_cfg = {
    .clk_cfg = {
        .sample_rate_hz = SAMPLE_RATE,
        .clk_src        = I2S_CLK_SRC_APLL,    // APLL 啟用，確保精確 16kHz
        .mclk_multiple  = I2S_MCLK_MULTIPLE_256,
    },
    .slot_cfg = {
        .data_bit_width = I2S_DATA_BIT_WIDTH_32BIT,
        .slot_mode      = I2S_SLOT_MODE_STEREO, // Stereo 讀取 + 軟體左聲道抽取
    },
    .gpio_cfg = {
        .bclk = GPIO_NUM_32,
        .ws   = GPIO_NUM_25,
        .din  = GPIO_NUM_33,
    },
};
```

### 4.4 Audio Read (Stereo → Mono Left)

```c
// Stereo 32bit 讀取，抽取左聲道並右移至 16bit 範圍
int32_t i2s_buf[chunk_frames * 2];
i2s_channel_read(rx_chan, i2s_buf, frames * 2 * sizeof(int32_t), &bytes_read, 1000);

for (size_t i = 0; i < got_frames; i++) {
    int32_t raw_l = i2s_buf[i * 2];       // 左聲道
    int32_t s = raw_l >> 11;              // 右移至 16bit 範圍
    s = clamp(s, -32768, 32767);
    out_buffer[i] = (int16_t)s;           // 或 (float)s 給 EI
}
```

### 4.5 Edge Impulse Inference

* 模型：`esp-miao-mfcc`（MFCC 特徵，3 類別：`heymiaomiao` / `noise` / `unknown`）
* 推論模式：Continuous sliding window（16000 samples，4 slices）
* 喚醒閾值：confidence ≥ `EI_CLASSIFIER_THRESHOLD`（預設 0.6）
* VAD 閾值：RMS > 1500（過濾靜音誤觸發）

```c
run_classifier_init();

// 持續讀取 slice → 推論
read_audio_slice(ei_slice_buffer, EI_CLASSIFIER_SLICE_SIZE, &current_rms);

signal_t signal = { .total_length = EI_CLASSIFIER_SLICE_SIZE,
                    .get_data = &ei_audio_signal_get_data };
run_classifier_continuous(&signal, &result, false);

// 檢查 "heymiaomiao" 類別
if (confidence >= EI_CLASSIFIER_THRESHOLD && current_rms > VAD_THRESHOLD) {
    // → WAKE → 錄音 3s → 傳送
}
```

### 4.6 Recording & Streaming

喚醒後流程：

1. LED 閃爍 3 次指示喚醒
2. 動態分配 96KB 緩衝區（48000 samples × 2 bytes）
3. 呼叫 `read_audio_to_buffer()` 錄音 3 秒
4. 傳送方式由編譯期 `USE_BINARY_STREAM` 巨集決定：
   * `1`：Binary stream（`audio_start` JSON + binary frames）
   * `0`：Base64 stream（`audio_start` + `audio_chunk` JSON）
5. 傳送完畢後釋放緩衝區

### 4.7 Decision Flow

```
I2S Mic → Stereo Read → Mono Left Extract
              ↓
        Edge Impulse MFCC
        (continuous inference)
              ↓
        Wake Word "heymiaomiao"?
         ↓ YES              ↓ NO
     LED 閃爍             continue
     錄音 3s
         ↓
   WebSocket Stream
   (audio_start + binary/base64)
         ↓
     Server ASR (Whisper)
         ↓
     Server LLM Intent
         ↓
     Server MQTT Publish
         ↓
   action / play 回應
```

### 4.8 Bring-Up Checklist

* [x] INMP441 接線正確 (BCK=32, WS=25, DIN=33)
* [x] I2S APLL 時脈穩定 (16kHz)
* [x] PCM buffer 有效（Stereo → Mono 轉換正確）
* [x] Edge Impulse 推論正常運行
* [x] 喚醒詞辨識觸發
* [x] 3 秒錄音完成
* [x] WebSocket 串流傳送成功

---

## 5. Server Pipeline

### 5.1 Device Table

Server 維護一份動態裝置表，支援靜態預設與 MQTT Discovery 動態註冊：

| 裝置名稱 | 類型 | GPIO | MQTT Topic | 指令映射 |
|----------|------|------|------------|----------|
| light | relay | 26 | `lamp/command` | ON / OFF |
| fan | relay | 27 | `home/fan/command` | ON / OFF |
| led | led | 2 | `home/led/command` | ON / OFF |

裝置別名（用於語音辨識匹配）：

| 裝置 | 別名 |
|------|------|
| light | 燈、電燈、燈光、lights |
| fan | 風扇、電風扇、電扇、風山 |
| led | LED、指示燈 |

### 5.2 Safety Validation

| 項目 | 允許值 |
|------|--------|
| Actions | `relay_set`, `led_set`, `play_sound`, `noop` |
| Values | `on`, `off`, `toggle` |
| GPIO Whitelist | 2, 4, 5, 12–19, 21–23, 25–27, 32–33 |

所有動作在執行前經過 `ActionValidator` 驗證，無效動作回傳 `noop` 或 `error.wav`。

### 5.3 Command Mapping Table

用於 `command_request` 的本地指令對應（Server 端查表）：

| cmd_id | cmd_name | target | value |
|--------|----------|--------|-------|
| 0 | LIGHT_ON | light | on |
| 1 | LIGHT_OFF | light | off |
| 2 | FAN_ON | fan | on |
| 3 | FAN_OFF | fan | off |

### 5.4 ASR Pipeline

1. 接收音訊（Base64 stream / binary stream / 一次性 `audio_request`）
2. 組合完整 PCM buffer
3. 寫入暫存 WAV 檔（加 44 byte header）
4. 呼叫 faster-whisper 轉譯（model: `base`, device: `cpu`, language: `zh`）
5. 幻聽過濾（重複字模式、`no_speech_prob` 閾值）
6. 回傳轉譯文字

### 5.5 LLM Intent Parsing

雙層解析策略：

1. **關鍵字攔截層**：先用別名表 + 動作關鍵字匹配
   * 動作關鍵字：開/打開/啟動 → `on`、關/關閉/停止 → `off`
   * 若關鍵字完全匹配，直接回傳結果
   * 若完全沒有裝置關鍵字命中，跳過 LLM
2. **LLM 驗證層**：呼叫 Ollama（`qwen2.5:0.5b`）解析自然語言
   * 動態注入當前可用裝置清單
   * LLM 結果與關鍵字結果交叉驗證，衝突時以關鍵字為準

### 5.6 Processing Flow

```
Server 收到音訊
  ↓
ASR (faster-whisper) → 文字
  ↓
Intent Parsing (Keywords + LLM) → {action, target, value}
  ↓
ActionValidator 安全驗證
  ↓ valid
MQTT Publish (target 裝置的 control_topic)
  +
Server 本地播放音效 (aplay)
  +
回傳 action JSON 至 ESP32
  ↓ invalid
回傳 play JSON (error.wav) 至 ESP32
```

---

## 6. MQTT Protocol

### 6.1 Broker Configuration

| 項目 | 預設值 | 環境變數 |
|------|--------|----------|
| Broker IP | 192.168.1.16 | `MQTT_BROKER` |
| Port | 1883 | `MQTT_PORT` |
| 通用 Topic | home/generic/command | `MQTT_TOPIC` |
| Discovery Topic | home/discovery | — |

### 6.2 Control Topic 結構

每個裝置有專屬的 `control_topic`，MQTT payload 為純文字指令：

| Topic | Payload |
|-------|---------|
| `lamp/command` | `ON` / `OFF` |
| `home/fan/command` | `ON` / `OFF` |
| `home/led/command` | `ON` / `OFF` |

### 6.3 Device Discovery

新裝置可透過 `home/discovery` topic 自我註冊：

```json
{
  "device_id": "heater",
  "device_type": "relay",
  "gpio": 14,
  "aliases": ["暖氣", "暖爐", "heater"],
  "control_topic": "home/heater/command",
  "commands": { "on": "ON", "off": "OFF" }
}
```

Server 收到後自動更新 DynamicDeviceTable 與別名映射。

---

## 7. REST API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check（狀態、裝置數、已連線裝置） |
| GET | `/devices` | 列出所有已註冊裝置 |
| GET | `/devices/{name}` | 查詢單一裝置資訊 |
| GET | `/audio` | 列出所有錄音檔案 |
| GET | `/audio/{filename}` | 下載錄音 WAV 檔案 |
