# 📚 My ESP32智慧燈控系統 完整安裝部署流程
1. 樹莓派端：安裝與設定 MQTT Broker (Mosquitto)
(1-1) 安裝 Mosquitto 與 Client工具
```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
```
(1-2) 修改 Mosquitto 允許區域網路連線

編輯設定檔：
```bash
sudo nano /etc/mosquitto/mosquitto.conf
```
新增或確認以下內容：
```bash
listener 1883 0.0.0.0
allow_anonymous true
```
儲存並重啟 Mosquitto：
```bash
sudo systemctl restart mosquitto
```

2. 樹莓派端：確認 MQTT Broker 運作正常
(2-1) 查看 Mosquitto 是否有開在所有 IP 上
```bash
sudo netstat -tnlp | grep 1883
```
看到類似：
```bash
tcp        0      0 0.0.0.0:1883      0.0.0.0:*       LISTEN      xxxx/mosquitto
```
代表成功 ✅

3. ESP32端：燒錄控制程式
(3-1) 硬體連接
ESP32接腳	功能	說明
GPIO26	Relay模組訊號腳	控制繼電器吸合開關燈
5V	Relay模組電源	一般接5V供電
GND	Relay模組地線	共地

ESP32電源由行動電源供應。✅

(3-2) Arduino IDE 安裝必要函式庫 
```bash
    WiFi.h （內建）

    ESPAsyncWebServer 3.7.7 by ESP32Async

    AsyncTCP 3.4.1 by ESP32Async

    PubSubClient 2.8 by Nick O'Leary
```
如果沒有：

在 Arduino IDE →「工具」→「管理程式庫」搜尋並安裝：
```bash
        ESP Async WebServer

        AsyncTCP

        PubSubClient
```
** ＊重點： 上述 Arduino程式庫盡量不要裝太新！ 上面的版本與出處須注意. **


(3-3) 燒錄以下程式碼（修改專屬參數）

請修改：
```cpp
const char* ssid = "你的WiFi名稱";
const char* password = "你的WiFi密碼";
const char* mqtt_server = "你的樹莓派的局域網IP"; // 例如 "192.168.1.50"
```
👉 然後燒錄這份程式：（這是你測試成功的版本）

---

### 🆕 v0.4.0 新增：MQTT Discovery 自動註冊機制
本版本的 ESP32 控制程式支援 **「隨插即用」** 的自動註冊功能。當 ESP32 連上 MQTT Broker 後，它會主動向伺服器發送註冊訊息。

#### 1. 運作方式
在 `connectToMQTT()` 成功後，裝置會自動發布 JSON 訊息至 `home/discovery` 主題：
*   **device_id**: `light_01` (伺服器識別名稱)
*   **aliases**: `["燈", "電燈", "燈光", "lights", "light"]` (語音辨識關鍵字)
*   **control_topic**: `lamp/command` (指令接收主題)
*   **commands**: 定義 `on` 對應 `ON`，`off` 對應 `OFF`

#### 2. 優點
*   **免設定伺服器**：伺服器不需事先寫死裝置資訊，裝置開機即自動出現於控制清單。
*   **即時同步**：如果您修改了 `aliases` 別名，只需重啟 ESP32，伺服器就會自動學會新的語意。

---

4. 測試 HTTP 控制功能

ESP32連上WiFi後，Serial Monitor會顯示IP，例如 192.168.1.123

用瀏覽器打開：

    打開燈 → http://192.168.1.123/on

    關閉燈 → http://192.168.1.123/off

✅ 成功開關，代表 HTTP控制正常！

5. 測試 MQTT 控制功能
(5-1) 先在樹莓派端訂閱燈的狀態Topic
```bash
mosquitto_sub -h 192.168.1.50 -t lamp/status
```
(5-2) 透過 MQTT 發送開關燈指令

### 打開燈
```bash
mosquitto_pub -h 192.168.1.50 -t lamp/command -m "ON"
```
### 關閉燈
```bash
mosquitto_pub -h 192.168.1.50 -t lamp/command -m "OFF"
```
你會看到：
    relay會動作
    燈會亮/滅
    終端機 mosquitto_sub 收到 "ON" 或 "OFF"

✅ 成功，代表 MQTT控制與回報正常！

6. 系統啟動順序與注意事項

    樹莓派（Mosquitto）要先開機並啟動

    確認 WiFi分享器正常運作

    ESP32開機後會自動：
        * 連上WiFi
        * 連上MQTT Broker
        * 啟動HTTP API服務

    任意透過 MQTT 或 HTTP 操控燈

7. 其他補充
