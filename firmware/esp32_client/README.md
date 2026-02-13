# ESP32 WebSocket Client for Arduino IDE

這個程式用於測試 ESP32 Dev Kit v1 與 ESP-MIAO Server 的 WebSocket 通訊。

## 硬體需求

- ESP32 Dev Kit v1
- LED on GPIO 2 (內建)
- Relay on GPIO 26 (可選, 用於 light)
- Relay on GPIO 27 (可選, 用於 fan)

## Arduino IDE 設定

### 1. 安裝 ESP32 Board

1. 開啟 Arduino IDE
2. File -> Preferences
3. Additional Board Manager URLs 加入:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Tools -> Board -> Board Manager
5. 搜尋 "esp32" 並安裝 "ESP32 by Espressif Systems"

### 2. 安裝 Libraries

Tools -> Library Manager，安裝以下:

- **ArduinoJson** by Benoit Blanchon (version 6.x)
- **WebSockets** by Markus Sattler (version 2.x)

### 3. Board 設定

- Board: "ESP32 Dev Module"
- Upload Speed: 115200
- Flash Frequency: 80MHz
- Flash Mode: QIO
- Flash Size: 4MB
- Partition Scheme: Default 4MB with spiffs

## 使用方式

### 1. 修改設定

開啟 `esp32_client.ino`，修改以下設定:

```cpp
// WiFi 設定
const char* WIFI_SSID = "YOUR_WIFI_SSID";      // <-- 你的 WiFi 名稱
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";  // <-- 你的 WiFi 密碼

// Server 設定
const char* SERVER_HOST = "192.168.1.100";     // <-- Server IP
const int SERVER_PORT = 8000;
const char* DEVICE_ID = "esp32_01";            // <-- 裝置 ID
```

### 2. 啟動 Server

在電腦上執行:

```bash
cd /path/to/esp-miao
uv run esp-miao
```

Server 會顯示:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3. 上傳程式

1. 連接 ESP32 到電腦
2. 選擇正確的 COM Port (Tools -> Port)
3. 點擊 Upload

### 4. 測試通訊

1. 開啟 Serial Monitor (Tools -> Serial Monitor)
2. Baud Rate: 115200
3. 輸入指令測試

## Serial 指令

| 指令 | 說明 | 範例 |
|------|------|------|
| `0` | 發送 LIGHT_ON | `0` |
| `1` | 發送 LIGHT_OFF | `1` |
| `2` | 發送 FAN_ON | `2` |
| `3` | 發送 FAN_OFF | `3` |
| `t:文字` | 發送 Fallback 請求 | `t:打開電風扇` |
| `s` | 顯示狀態 | `s` |
| `r` | 重新連線 | `r` |
| `h` | 顯示說明 | `h` |

## 預期輸出

```
========================================
  ESP-MIAO: ESP32 WebSocket Client
  Version: 0.1.0
========================================

[GPIO] Initialized: LED=2, LIGHT=26, FAN=27
[WiFi] Connecting to MyWiFi... Connected!
[WiFi] IP: 192.168.1.50
[WS] Connecting to ws://192.168.1.100:8000/ws/esp32_01
[WS] Connected to /ws/esp32_01

Type 'h' for help.

> 0
[STATE] IDLE -> WAKE
[WAKE] Simulated wake word detected
[STATE] WAKE -> RECOGNIZE
[RECOGNIZE] Local command: LIGHT_ON
[STATE] RECOGNIZE -> FORWARD_SERVER
[SEND] {"type":"command_request","device_id":"esp32_01","timestamp":12345,"payload":{"source":"esp-sr","cmd_id":0,"cmd_name":"LIGHT_ON","confidence":0.95}}
[STATE] FORWARD_SERVER -> WAIT_ACTION
[WS] Received: {"device_id":"esp32_01","timestamp":12346,"type":"action","payload":{"action":"relay_set","target":"light","value":"on","sound":"success.wav"}}
[RECV] type=action
[STATE] WAIT_ACTION -> LOCAL_EXECUTE
[ACTION] relay_set(light=on)
[RELAY] light -> on (GPIO 26 = HIGH)
[STATE] LOCAL_EXECUTE -> PLAY_FEEDBACK
[SOUND] Playing: success.wav
[SEND] {"type":"action_result","device_id":"esp32_01","timestamp":12347,"payload":{"status":"success"}}
[STATE] PLAY_FEEDBACK -> IDLE
```

## GPIO 對應

| 裝置 | GPIO | 說明 |
|------|------|------|
| LED | 2 | 內建 LED，用於狀態指示 |
| light | 26 | Relay 控制 (燈) |
| fan | 27 | Relay 控制 (風扇) |

## 故障排除

### WiFi 連線失敗
- 確認 SSID 和密碼正確
- 確認 ESP32 在 WiFi 訊號範圍內
- 嘗試重新啟動 ESP32

### WebSocket 連線失敗
- 確認 Server 正在運行
- 確認 SERVER_HOST IP 正確
- 確認電腦防火牆允許 port 8000
- 確認 ESP32 和 Server 在同一網路

### JSON 解析錯誤
- 確認 Server 版本與 Client 相容
- 檢查 ArduinoJson library 版本 (需 6.x)

## 下一步

這個程式只是通訊測試。完整功能需要加入:

- I2S 麥克風輸入
- esp-sr (WakeNet + MultiNet)
- 實際音效播放 (I2S DAC)
- 斷線重連機制
