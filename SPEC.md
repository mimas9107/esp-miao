# Engineering Specs

## 1. JSON Protocol Definition

### 1.1 Common Envelope

```json
{
  "type": "event_type",
  "device_id": "esp32_01",
  "timestamp": 0,
  "payload": {}
}
```

---

### 1.2 ESP32 → Server

#### Command Request

```json
{
  "type": "command_request",
  "device_id": "esp32_01",
  "timestamp": 17574239,
  "payload": {
    "source": "esp-sr",
    "cmd_id": 1,
    "cmd_name": "LIGHT_ON",
    "confidence": 0.91
  }
}
```

#### Fallback Audio/Text

```json
{
  "type": "fallback_request",
  "device_id": "esp32_01",
  "timestamp": 17574240,
  "payload": {
    "text": "啟動掃地機器人"
  }
}
```

---

### 1.3 Server → ESP32

#### Action

```json
{
  "type": "action",
  "device_id": "esp32_01",
  "timestamp": 17574241,
  "payload": {
    "action": "relay_set",
    "target": "light",
    "value": "on",
    "sound": "success.wav"
  }
}
```

#### Feedback Only

```json
{
  "type": "play",
  "device_id": "esp32_01",
  "timestamp": 17574242,
  "payload": {
    "audio": "endpoint.wav"
  }
}
```

---

## 2. State & Event Definition

### 2.1 ESP32 State Machine

| State          | Description             |
| -------------- | ----------------------- |
| IDLE           | Standby waiting wake    |
| WAKE           | Wake word detected      |
| LISTEN         | Capturing command       |
| RECOGNIZE      | esp-sr processing       |
| LOCAL_EXECUTE  | Execute local action    |
| FORWARD_SERVER | Send to server          |
| WAIT_ACTION    | Waiting server response |
| PLAY_FEEDBACK  | Play audio feedback     |
| ERROR          | Error handling          |

---

### 2.2 Event Types

| Event           | Source | Description           |
| --------------- | ------ | --------------------- |
| wake_detected   | esp-sr | Wake word hit         |
| command_local   | esp-sr | Local command matched |
| command_unknown | esp-sr | No local match        |
| action_execute  | server | Action instruction    |
| action_result   | esp32  | Execution result      |
| play_audio      | server | Feedback audio        |
| error           | both   | Error condition       |

---

## 3. ESP32 WebSocket Client Skeleton

```c
#include "esp_websocket_client.h"
#include "esp_log.h"

static esp_websocket_client_handle_t client;

static void ws_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data)
{
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;

    switch (event_id) {
        case WEBSOCKET_EVENT_CONNECTED:
            ESP_LOGI("WS", "Connected");
            break;
        case WEBSOCKET_EVENT_DATA:
            ESP_LOGI("WS", "Received: %.*s", data->data_len, (char *)data->data_ptr);
            break;
        case WEBSOCKET_EVENT_DISCONNECTED:
            ESP_LOGI("WS", "Disconnected");
            break;
    }
}

void ws_start(void)
{
    esp_websocket_client_config_t cfg = {
        .uri = "ws://server-ip:8000/ws",
    };

    client = esp_websocket_client_init(&cfg);
    esp_websocket_register_events(client, WEBSOCKET_EVENT_ANY, ws_event_handler, NULL);
    esp_websocket_client_start(client);
}

void ws_send(const char *msg)
{
    esp_websocket_client_send_text(client, msg, strlen(msg), portMAX_DELAY);
}
```
# Critical Path: Audio Pipeline Spec

這一段是整個專案最容易卡死的地方：**沒有穩定的音訊管線，WakeNet / MultiNet 全部無法工作。**

因此第一個必須完成的是：

> ESP32 I2S Mic → DMA Buffer → esp-sr Frontend → WakeNet → MultiNet

---

## 4. Audio Capture & esp-sr Pipeline

### 4.1 Hardware Assumption

* ESP32 Dev Kit v1
* I2S MEMS Mic (e.g. INMP441)
* Sample Rate: 16kHz
* Bits: 16bit
* Channel: Mono

---

### 4.2 I2S Configuration (ESP-IDF)

```c
#define I2S_PORT I2S_NUM_0

void i2s_init()
{
    i2s_config_t i2s_config = {
        .mode = I2S_MODE_MASTER | I2S_MODE_RX,
        .sample_rate = 16000,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = 256,
        .use_apll = false
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num = 26,
        .ws_io_num = 25,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = 33
    };

    i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
    i2s_set_pin(I2S_PORT, &pin_config);
}
```

---

### 4.3 Audio Read Loop

```c
int16_t pcm_buffer[512];
size_t bytes_read;

i2s_read(I2S_PORT, pcm_buffer, sizeof(pcm_buffer), &bytes_read, portMAX_DELAY);
```

此 buffer 將直接餵給 esp-sr。

---

### 4.4 esp-sr Frontend Pipeline

```c
srmodel_list_t *models = esp_srmodel_init("model");

const esp_wn_iface_t *wakenet = esp_wn_handle_from_name(models, "wn9_hiesp");
const esp_mn_iface_t *multinet = esp_mn_handle_from_name(models, "mn6_cn");

void *wn = wakenet->create(models, 16000);
void *mn = multinet->create(models, 16000);
```

Processing:

```c
if (wakenet->detect(wn, pcm_buffer)) {
    state = WAKE;
}

int cmd = multinet->detect(mn, pcm_buffer);
if (cmd >= 0) {
    emit_command(cmd);
}
```

---

### 4.5 Command Mapping Table

```c
typedef enum {
    CMD_LIGHT_ON = 0,
    CMD_LIGHT_OFF,
    CMD_UNKNOWN
} command_t;
```

```c
command_t map_cmd(int id)
{
    switch(id) {
        case 0: return CMD_LIGHT_ON;
        case 1: return CMD_LIGHT_OFF;
        default: return CMD_UNKNOWN;
    }
}
```

---

### 4.6 Decision Flow

```
I2S → esp-sr → WakeNet
              ↓
           MultiNet
              ↓
        map_cmd()
          ↓        ↓
      local      fallback
```

Local: relay, led, sound
Fallback: WebSocket → Server

---

### 4.7 Minimal Bring-Up Checklist

* [ ] Mic wiring correct
* [ ] I2S clock stable
* [ ] PCM buffer valid
* [ ] WakeNet fires
* [ ] MultiNet returns id
* [ ] Mapping table works
* [ ] State machine transitions
